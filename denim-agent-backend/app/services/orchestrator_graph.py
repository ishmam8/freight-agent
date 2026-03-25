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

DATABASE_URL = "sqlite:///denim_leads.db"
engine = create_engine(DATABASE_URL, echo=False)

gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

class OrchestratorState(TypedDict, total=False):
    user_id: int
    brief_id: int
    brief: Dict[str, Any]
    current_queries: List[str]
    found_leads: List[Dict[str, Any]]
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
    target_count = state.get("target_count", 5)
    attempts = state.get("attempts", 0)
    
    if not queries:
        return {**state, "attempts": attempts + 1}
        
    needed = target_count - len(found_leads)
    if needed <= 0:
        return {**state, "attempts": attempts + 1}
        
    current_query = queries[0] 
    print(f"[Orchestrator] Attempt {attempts + 1}: Searching Exa with query: '{current_query}'")
    
    exclude_domains = []
    for l in found_leads:
        try:
            d = urlparse(l["website_url"]).netloc
            if d: exclude_domains.append(d)
        except Exception: pass

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
            num_results=needed * 2,
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
    except Exception as e:
        print(f"[Orchestrator] Exa search failed: {e}")
        
    return {
        **state,
        "found_leads": found_leads,
        "attempts": attempts + 1,
        "current_queries": queries[1:] if len(queries) > 1 else queries 
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
        if text_output.startswith("```json"):
            text_output = text_output[7:-3].strip()
        elif text_output.startswith("```"):
            text_output = text_output[3:-3].strip()
            
        parsed = json.loads(text_output)
        new_queries = parsed.get("new_queries", [])
        if new_queries:
            return {
                **state,
                "current_queries": new_queries
            }
    except Exception as e:
        print(f"[Orchestrator] Failed to rewrite queries: {e}")
        
    return state

async def enqueue_node(state: OrchestratorState) -> OrchestratorState:
    found_leads = state.get("found_leads", [])
    user_id = state["user_id"]
    brief_id = state["brief_id"]
    
    print(f"[Orchestrator] Enqueueing {len(found_leads)} leads for user {user_id}, brief {brief_id}")
    
    if not found_leads:
        print("[Orchestrator] No leads found to enqueue.")
        return state
        
    from arq import create_pool
    from arq.connections import RedisSettings
    from app.core.config import settings
    
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    
    with Session(engine) as session:
        for lead_data in found_leads:
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
                
    await redis_pool.close()
    return state

def evaluate_router(state: OrchestratorState) -> str:
    found_leads = state.get("found_leads", [])
    target_count = state.get("target_count", 5)
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
