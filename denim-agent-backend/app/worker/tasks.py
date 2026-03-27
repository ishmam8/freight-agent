import asyncio
import httpx
from sqlmodel import Session, select

from app.core.database import engine
from app.models.domain import Lead, LeadStatus, EnrichedLead, SelectedContact, CampaignBrief
from app.services.investigator import investigate_lead
from app.services.enricher import enrich_one_lead
from app.services.selector import build_candidates, pick_best_candidate, upsert_selected_contact
from app.services.drafting.drafter_graph import build_drafter_graph
from app.services.research.researcher import run_prompt_research
from app.services.orchestrator_graph import build_orchestrator_graph
from app.services.billing import decrement_user_credits

from urllib.parse import urlparse

async def _fast_ping(client: httpx.AsyncClient, url: str) -> bool:
    try:
        resp = await client.get(url, timeout=5.0, follow_redirects=True)
        return resp.status_code < 400
    except Exception:
        return False

async def run_campaign_from_prompt(ctx, prompt: str, user_id: int, brief_id: int):
    print(f"Running campaign for prompt: {prompt}")
    redis_pool = ctx.get("redis")
    
    desired_count = 100
    successful_leads = []
    exclude_domains = []
    
    with Session(engine) as session:
        existing_leads = session.exec(select(Lead)).all()
        for l in existing_leads:
            try:
                domain = urlparse(str(l.website_url)).netloc
                if domain: exclude_domains.append(domain)
            except Exception: pass
            
    exclude_domains = list(set(exclude_domains))
    attempts = 0
    max_attempts = 4
    
    async with httpx.AsyncClient(verify=False) as client:
        while len(successful_leads) < desired_count and attempts < max_attempts:
            attempts += 1
            needed = desired_count - len(successful_leads)
            print(f"Attempt {attempts}: Asking Exa for {needed} leads (excluding {len(exclude_domains)} known domains)...")
            
            try:
                new_leads = await run_prompt_research(prompt, num_results=needed, exclude_domains=exclude_domains)
            except Exception as e:
                print(f"Exa search failed: {e}")
                break
                
            if not new_leads:
                print("Exa returned no more leads. Stopping.")
                break
                
            for lc in new_leads:
                try:
                    domain = urlparse(str(lc.website_url)).netloc
                    if domain: exclude_domains.append(domain)
                except Exception: pass
                
            ping_tasks = [_fast_ping(client, str(lc.website_url)) for lc in new_leads]
            ping_results = await asyncio.gather(*ping_tasks)
            
            for lc, is_alive in zip(new_leads, ping_results):
                if is_alive:
                    successful_leads.append(lc)
                    if len(successful_leads) == desired_count:
                        break
                else:
                    print(f"Pre-vetting failed for {lc.website_url}. Discarding.")
                    
    print(f"Finished collecting {len(successful_leads)} alive leads. Queuing them now...")
    
    with Session(engine) as session:
        for lead_create in successful_leads:
            new_lead = Lead(
                user_id=user_id,
                campaign_brief_id=brief_id,
                company_name=lead_create.company_name,
                website_url=str(lead_create.website_url),
                category=lead_create.category,
                description=lead_create.description,
                source=lead_create.source,
                status=LeadStatus.QUEUED
            )
            session.add(new_lead)
            try:
                session.commit()
                session.refresh(new_lead)
                
                if redis_pool:
                    await redis_pool.enqueue_job('run_full_pipeline', new_lead.id, user_id, brief_id)
            except Exception as e:
                session.rollback()
                print(f"Failed to insert alive lead {lead_create.website_url}: {e}")

async def run_orchestrator_job(ctx, user_id: int, brief_id: int):
    print(f"[Worker] Waking up orchestrator for brief {brief_id}")
    with Session(engine) as session:
        brief = session.get(CampaignBrief, brief_id)
        if not brief:
            print(f"[Worker] Brief {brief_id} not found.")
            return
            
        brief_dict = brief.model_dump() if hasattr(brief, "model_dump") else brief.dict()
        current_queries = brief_dict.get("exa_search_queries", [])
        
    state = {
        "user_id": user_id,
        "brief_id": brief_id,
        "brief": brief_dict,
        "current_queries": current_queries.copy() if current_queries else [],
        "found_leads": [],
        "target_count": 100,
        "attempts": 0,
        "max_attempts": 3
    }
    
    graph = build_orchestrator_graph()
    await graph.ainvoke(state)

async def run_full_pipeline(ctx, lead_id: int, user_id: int, brief_id: int):
    # 1. Investigating
    with Session(engine) as session:
        lead = session.get(Lead, lead_id)
        if not lead:
            print(f"Lead {lead_id} not found.")
            return
            
        lead.status = LeadStatus.INVESTIGATING
        session.add(lead)
        session.commit()
    
    with Session(engine) as session:
        lead = session.get(Lead, lead_id)
        brief = session.get(CampaignBrief, brief_id)
        if not brief:
            print(f"Brief {brief_id} not found.")
            return

        result = await investigate_lead(lead, brief)
        
        lead.canonical_domain = result.canonical_domain
        lead.scraped_context = result.scraped_context
        lead.investigation_notes = result.investigation_notes
        lead.rejection_reason = result.rejection_reason
        lead.investigation_confidence = result.investigation_confidence
        
        if result.status in [LeadStatus.REJECTED, LeadStatus.FETCH_FAILED]:
            lead.status = result.status
            session.add(lead)
            session.commit()
            print(f"Lead {lead_id} rejected or fetch failed.")
            return
            
        lead.status = LeadStatus.ENRICHING
        session.add(lead)
        session.commit()
        
    # 2. Enriching
    async with httpx.AsyncClient(timeout=35.0) as client:
        with Session(engine) as session:
            lead = session.get(Lead, lead_id)
            await enrich_one_lead(lead, client, session)
            
            # enrich_one_lead saves status to DRAFTING; verify it
            session.refresh(lead)
            if lead.status in [LeadStatus.REJECTED, LeadStatus.FETCH_FAILED]:
                print(f"Lead {lead_id} failed during enrichment.")
                return
            
    # 3. Selector
    with Session(engine) as session:
        lead = session.get(Lead, lead_id)
        enriched = session.exec(select(EnrichedLead).where(EnrichedLead.lead_id == lead.id)).first()
        
        if not enriched:
            print(f"Could not find enriched data for lead {lead_id}")
            return
            
        brief = session.get(CampaignBrief, brief_id)
        candidates = build_candidates(enriched, target_titles=brief.buyer_titles if brief else None)
        selected = pick_best_candidate(candidates)
        
        upsert_selected_contact(
            session=session,
            lead=lead,
            enriched=enriched,
            selected=selected,
            candidates=candidates
        )
        session.commit()

        if not selected:
             lead.status = LeadStatus.COMPLETED
             lead.enrichment_notes = (lead.enrichment_notes or "") + " | No valid contact selected"
             session.add(lead)
             session.commit()
             print(f"No contact selected for lead {lead_id}")
             return

        selected_row = session.exec(
            select(SelectedContact).where(SelectedContact.lead_id == lead.id)
        ).first()

    # 4. Drafting
    # --- MOCK MODE INTERCEPT ---
    import os
    if os.getenv("USE_MOCK_DATA") == "True":
        print(f"[MOCK] Skipping LLM Drafting for lead {lead_id}. Injecting fake email.")
        import asyncio
        await asyncio.sleep(2)
        
        with Session(engine) as session:
            from app.models.domain import OutreachDraft
            lead = session.get(Lead, lead_id)
            
            # Create a fake draft attached to the selected contact
            fake_draft = OutreachDraft(
                user_id=user_id,
                company_name=lead.company_name,
                enriched_lead_id=selected_row.enriched_lead_id,
                selected_contact_id=selected_row.id,
                contact_name="Mock Contact",
                contact_email="mock@example.com",
                subject="Quick question about your freight matching",
                body="Hi Mock,\n\nI noticed Mock Logistics is growing. Are you open to automating your freight matching?\n\nBest,\nMe",
                status="drafted"
            )
            session.add(fake_draft)
            
            lead.status = LeadStatus.COMPLETED
            session.add(lead)
            
            # --- TOLL BOOTH DEDUCTION (MOCK) ---
            try:
                decrement_user_credits(session, user_id, amount=1)
                print(f"Deducted 1 credit for user {user_id} (MOCK)")
            except Exception as e:
                print(f"Failed to deduct credit for user {user_id}: {e}")
            # --- END TOLL BOOTH DEDUCTION ---
            
            session.commit()
            print(f"Lead {lead_id} pipeline COMPLETED (MOCKED).")
            return
    # --- END MOCK MODE ---

    graph = build_drafter_graph()
    try:
        with Session(engine) as session:
            brief = session.get(CampaignBrief, brief_id)
            brief_dict = brief.model_dump() if brief else {}
            
        draft_result = await graph.ainvoke({
            "selected_contact_id": selected_row.id,
            "campaign_brief": brief_dict
        })
        print(f"Draft result for lead {lead_id}: {draft_result.get('status')}")
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e) or 'Unknown error'}"
        print(f"Error during drafting for lead {lead_id}: {error_msg}")
        traceback.print_exc()
        with Session(engine) as session:
            lead = session.get(Lead, lead_id)
            lead.enrichment_notes = (lead.enrichment_notes or "") + f" | Draft failed: {error_msg}"
            session.add(lead)
            session.commit()
    
    try:
        with Session(engine) as session:
            lead = session.get(Lead, lead_id)
            lead.status = LeadStatus.COMPLETED
            session.add(lead)
            
            # --- TOLL BOOTH DEDUCTION ---
            try:
                decrement_user_credits(session, user_id, amount=1)
                print(f"Deducted 1 credit for user {user_id}")
            except Exception as e:
                print(f"Failed to deduct credit for user {user_id}: {e}")
            # --- END TOLL BOOTH DEDUCTION ---
            
            session.commit()
            print(f"Lead {lead_id} pipeline COMPLETED.")
    finally:
        # Recursive wake-up logic
        with Session(engine) as session:
            # Count leads that successfully completed or are still being processed
            completed_leads = session.exec(
                select(Lead).where(
                    Lead.campaign_brief_id == brief_id,
                    Lead.status.in_([LeadStatus.COMPLETED, LeadStatus.DRAFTING])
                )
            ).all()
            completed_count = len(completed_leads)
            
            # Count leads currently queued
            queued_leads = session.exec(
                select(Lead).where(
                    Lead.campaign_brief_id == brief_id,
                    Lead.status == LeadStatus.QUEUED
                )
            ).all()
            queued_count = len(queued_leads)
            
            if completed_count < 100 and queued_count == 0:
                print(f"[Worker] Target missed (Completed: {completed_count}, Queued: 0). Waking orchestrator...")
                redis_pool = ctx.get("redis")
                if redis_pool:
                    await redis_pool.enqueue_job('run_orchestrator_job', user_id, brief_id)
