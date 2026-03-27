import os
import json
import asyncio
import httpx
from typing import TypedDict, List, Dict, Any
from urllib.parse import urlparse

from langgraph.graph import StateGraph, END
from sqlmodel import Session, select, create_engine
from exa_py import Exa
from dotenv import load_dotenv

from app.models.domain import Lead, LeadStatus, CampaignBrief, LeadCategory

load_dotenv()
exa = Exa(api_key=os.getenv("EXA_API_KEY"))

from app.core.config import settings
engine = create_engine(settings.DATABASE_URL, echo=False)

gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

class OrchestratorState(TypedDict, total=False):
    user_id: int
    brief_id: int
    brief: Dict[str, Any]
    current_queries: List[str]
    found_leads: List[Dict[str, Any]]
    rejected_leads: List[Dict[str, Any]]
    target_count: int
    attempts: int
    max_attempts: int

async def _fast_ping(client: httpx.AsyncClient, url: str) -> bool:
    try:
        resp = await client.get(url, timeout=5.0, follow_redirects=True)
        return resp.status_code < 400
    except Exception:
        return False

async def search_node(state: OrchestratorState) -> OrchestratorState:
    queries = state.get("current_queries", [])
    found_leads = state.get("found_leads", [])
    rejected_leads = state.get("rejected_leads", [])
    target_count = state.get("target_count", 100)
    attempts = state.get("attempts", 0)
    brief_id = state.get("brief_id")
    user_id = state.get("user_id")
    
    with Session(engine) as session:
        # Calculate needed from ONLY current brief's leads
        brief_statement = select(Lead).where(Lead.campaign_brief_id == brief_id)
        existing_brief_leads = session.exec(brief_statement).all()
        
        completed_count = 0
        queued_count = 0
        
        for lead in existing_brief_leads:
            if lead.status in [LeadStatus.COMPLETED, LeadStatus.DRAFTING]:
                completed_count += 1
            elif lead.status == LeadStatus.QUEUED:
                queued_count += 1
                
        # Query ALL leads for this user to build exclude list across campaigns
        user_statement = select(Lead).where(Lead.user_id == user_id)
        all_user_leads = session.exec(user_statement).all()
        
    needed = target_count - (completed_count + queued_count) - len(found_leads)
    if needed <= 0:
        print(f"[Orchestrator] Enough leads found or queued (Completed: {completed_count}, Queued: {queued_count}, Current State Found: {len(found_leads)}). Stopping search.")
        return {**state, "attempts": attempts + 1}
        
    current_query = queries.pop(0) if queries else "B2B companies"
    print(f"[Orchestrator] Attempt {attempts + 1}: Searching Exa with query: '{current_query}'")
    
    exclude_domains = []
    
    # Add newly found domains in memory
    for l in found_leads + rejected_leads:
        try:
            d = urlparse(l["website_url"]).netloc.replace("www.", "")
            if d: exclude_domains.append(d)
        except Exception: pass
        
    # Add ALL existing DB domains for the user to prevent duplicate fetching globally
    for lead in all_user_leads:
        if lead.website_url:
            try:
                d = urlparse(lead.website_url).netloc.replace("www.", "")
                if d: exclude_domains.append(d)
            except Exception: pass
            
    # Deduplicate the exclude_domains list before passing to Exa
    exclude_domains = list(set(exclude_domains))

    # --- MOCK MODE INTERCEPT ---
    if os.getenv("USE_MOCK_DATA") == "True":
        await asyncio.sleep(2) # Simulate internet search
        
        if attempts == 0:
            print("[MOCK] First attempt. Pretending Exa found 0 results to test the Agent's rewrite logic!")
            return {
                **state,
                "found_leads": [],
                "attempts": attempts + 1,
            }
        else:
            print("[MOCK] Second attempt. Exa magically found 5 perfect leads!")
            mock_leads = [
                {"company_name": f"Mock Logistics {i}", "website_url": f"https://mocklogistics{i}.com", "description": "A fake company."}
                for i in range(1, 6)
            ]
            return {
                **state,
                "found_leads": mock_leads,
                "attempts": attempts + 1,
            }
    # --- END MOCK MODE ---
        
    try:
        response = exa.search_and_contents(
            current_query,
            type="neural",
            num_results=needed * 5,
            category="company",
            summary=True,
            exclude_domains=exclude_domains if exclude_domains else None,
        )
        
        candidates = []
        for result in response.results:
            if not result.url: continue
            candidates.append({
                "company_name": result.title or "Unknown Company",
                "website_url": result.url,
                "description": result.summary or ""
            })
            
        async with httpx.AsyncClient(verify=False) as client:
            ping_tasks = [_fast_ping(client, c["website_url"]) for c in candidates]
            ping_results = await asyncio.gather(*ping_tasks)
            
            for c, is_alive in zip(candidates, ping_results):
                if is_alive:
                    found_leads.append(c)
                    if len(found_leads) >= target_count:
                        break
                else:
                    c["reason"] = "Connection Timeout / Dead Link"
                    rejected_leads.append(c)
    except Exception as e:
        print(f"[Orchestrator] Exa search failed: {e}")
        
    return {
        **state,
        "found_leads": found_leads,
        "rejected_leads": rejected_leads,
        "attempts": attempts + 1,
        "current_queries": queries 
    }

async def rewrite_node(state: OrchestratorState) -> OrchestratorState:
    # --- MOCK MODE INTERCEPT ---
    if os.getenv("USE_MOCK_DATA") == "True":
        print("[MOCK] Agent is 'rewriting' the search queries...")
        return {
            **state,
            "current_queries": ["mocked broader query 1", "mocked broader query 2"]
        }
    # --- END MOCK MODE ---
    
    brief = state["brief"]
    current_queries = state.get("current_queries", [])
    found_leads = state.get("found_leads", [])
    
    print(f"[Orchestrator] Rewriting queries. Found {len(found_leads)} so far.")
    
    prompt = f"""
    You are an expert search strategist. We are looking for {brief.get('target_audience', 'companies')}.
    We tried searching {current_queries} but only found {len(found_leads)} leads.
    Generate 3 new, slightly broader or alternative Exa search queries to find more targets.
    Do NOT use these banned terms: {brief.get('banned_terms', [])}.
    
    Return ONLY valid JSON matching this schema exactly, without markdown formatting:
    {{
      "new_queries": ["query1", "query2", "query3"]
    }}
    """
    
    if not gemini_api_key:
        print("[Orchestrator] No Gemini API key, cannot rewrite.")
        return state
        
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "x-goog-api-key": gemini_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7, 
            "responseMimeType": "application/json"
        },
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
        text_output = ""
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts and "text" in parts[0]:
                text_output = parts[0]["text"]
                
        text_output = text_output.strip()
        print(f"[Orchestrator] Raw LLM rewrite response: {text_output}")
        
        # Robustly strip markdown
        if "```json" in text_output:
            text_output = text_output.split("```json")[1].split("```")[0].strip()
        elif "```" in text_output:
            text_output = text_output.split("```")[1].split("```")[0].strip()
            
        parsed = json.loads(text_output)
        new_queries = parsed.get("new_queries", [])
        
        print(f"[Orchestrator] Parsed new queries: {new_queries}")
        
        if new_queries:
            current_queries.extend(new_queries)
            return {
                **state,
                "current_queries": current_queries
            }
    except Exception as e:
        print(f"[Orchestrator] Failed to rewrite queries or parse JSON: {e}. Raw response: {text_output if 'text_output' in locals() else 'None'}")
        
        fallback_query = f"{brief.get('target_audience', 'companies')} B2B list"
        print(f"[Orchestrator] Applying fallback query: {fallback_query}")
        current_queries.append(fallback_query)
        return {
            **state,
            "current_queries": current_queries
        }
        
    return state

async def enqueue_node(state: OrchestratorState) -> OrchestratorState:
    found_leads = state.get("found_leads", [])
    rejected_leads = state.get("rejected_leads", [])
    user_id = state["user_id"]
    brief_id = state["brief_id"]
    
    print(f"[Orchestrator] Enqueueing {len(found_leads)} leads for user {user_id}, brief {brief_id} (Rejected: {len(rejected_leads)})")
    
    if not found_leads and not rejected_leads:
        print("[Orchestrator] No leads found to enqueue or reject.")
        return state
        
    from arq import create_pool
    from arq.connections import RedisSettings
    from app.core.config import settings
    
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    
    with Session(engine) as session:
        statement = select(Lead.website_url).where(Lead.campaign_brief_id == brief_id)
        existing_urls = set(session.exec(statement).all())
        
        for lead_data in found_leads:
            url = lead_data["website_url"]
            if url in existing_urls:
                continue
                
            new_lead = Lead(
                user_id=user_id,
                campaign_brief_id=brief_id,
                company_name=lead_data["company_name"],
                website_url=lead_data["website_url"],
                category=LeadCategory.INDEPENDENT_BRAND, 
                description=lead_data.get("description", ""),
                source="Macro-Graph Orchestrator",
                status=LeadStatus.QUEUED
            )
            session.add(new_lead)
            try:
                session.commit()
                session.refresh(new_lead)
                await redis_pool.enqueue_job('run_full_pipeline', new_lead.id, user_id, brief_id)
            except Exception as e:
                session.rollback()
                print(f"[Orchestrator] Failed to insert lead {lead_data['website_url']}: {e}")
                
        for r_lead in rejected_leads:
            url = r_lead["website_url"]
            if url in existing_urls:
                continue
                
            new_lead = Lead(
                user_id=user_id,
                campaign_brief_id=brief_id,
                company_name=r_lead["company_name"],
                website_url=url,
                category=LeadCategory.INDEPENDENT_BRAND, 
                description=r_lead.get("description", ""),
                source="Macro-Graph Orchestrator",
                status=LeadStatus.REJECTED,
                rejection_reason=r_lead.get("reason", "Unknown Rejection")
            )
            session.add(new_lead)
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                print(f"[Orchestrator] Failed to insert rejected lead {r_lead['website_url']}: {e}")
                
    await redis_pool.close()
    return state

def evaluate_router(state: OrchestratorState) -> str:
    found_leads = state.get("found_leads", [])
    target_count = state.get("target_count", 100)
    attempts = state.get("attempts", 0)
    max_attempts = state.get("max_attempts", 3)
    
    if len(found_leads) >= target_count:
        return "enqueue_node"
        
    if attempts >= max_attempts:
        return "enqueue_node"
        
    return "rewrite_node"

def build_orchestrator_graph():
    graph = StateGraph(OrchestratorState)
    
    graph.add_node("search_node", search_node)
    graph.add_node("rewrite_node", rewrite_node)
    graph.add_node("enqueue_node", enqueue_node)
    
    graph.set_entry_point("search_node")
    
    graph.add_conditional_edges(
        "search_node",
        evaluate_router,
        {
            "enqueue_node": "enqueue_node",
            "rewrite_node": "rewrite_node",
        }
    )
    
    graph.add_edge("rewrite_node", "search_node")
    graph.add_edge("enqueue_node", END)
    
    return graph.compile()
