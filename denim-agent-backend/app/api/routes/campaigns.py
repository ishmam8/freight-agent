from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlmodel import Session, select

from app.api.deps import get_current_user, get_db
from app.models.domain import User, Lead, LeadStatus, OutreachDraft, CampaignBrief, Conversation, ChatMessage
from app.models.schemas import PromptRequest, LaunchRequest
from app.services.brief_parser import parse_campaign_brief
from app.services.orchestrator_graph import build_orchestrator_graph

router = APIRouter()


@router.post("/draft-brief")
async def draft_brief(
    request: PromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    # 1. Manage the Conversation Thread
    if request.conversation_id:
        conv = db.get(Conversation, request.conversation_id)
        if not conv or conv.user_id != current_user.id:
            return {"status": "error", "message": "Conversation not found"}
    else:
        # Create a new conversation, use the first 30 chars of the prompt as the title
        title = request.prompt[:30] + "..." if len(request.prompt) > 30 else request.prompt
        conv = Conversation(user_id=current_user.id, title=title)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        
    # 2. Save the User's Message
    user_msg = ChatMessage(conversation_id=conv.id, role="user", content=request.prompt)
    db.add(user_msg)
    db.commit()

    # 3. Call your AI to parse the brief
    parsed_schema = await parse_campaign_brief(request.prompt)
    
    # 4. Save the AI's standard response
    ai_content = "I've drafted a Campaign Blueprint based on your request. Please review it on the right and edit anything if needed."
    ai_msg = ChatMessage(conversation_id=conv.id, role="ai", content=ai_content)
    db.add(ai_msg)
    db.commit()
    
    draft_brief_data = parsed_schema.model_dump() if hasattr(parsed_schema, "model_dump") else parsed_schema.dict()
    draft_brief_data["original_prompt"] = request.prompt
    
    return {
        "status": "success", 
        "conversation_id": conv.id, # Send this back so React knows which chat it's in!
        "draft_brief": draft_brief_data
    }


@router.post("/launch")
async def launch_campaign(
    request: LaunchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Takes an approved brief, saves it, and orchestrates the search graph in the background.
    """
    # 1. Create the Brief
    brief = CampaignBrief(
        user_id=current_user.id,
        original_prompt=request.original_prompt,
        target_audience=request.target_audience,
        banned_terms=request.banned_terms,
        buyer_titles=request.buyer_titles,
        value_proposition=request.value_proposition,
        exa_search_queries=request.exa_search_queries,
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)

    # 2. Link the brief to the chat conversation!
    # (Checking safely in case conversation_id isn't in the request yet)
    conv_id = getattr(request, "conversation_id", None)
    if conv_id:
        conv = db.get(Conversation, conv_id)
        if conv:
            conv.campaign_brief_id = brief.id
            db.add(conv)
            db.commit()

    # 3. Define the Orchestrator Background Task
    async def run_brain_in_background():
        state = {
            "user_id": current_user.id,
            "brief_id": brief.id,
            "brief": request.model_dump() if hasattr(request, "model_dump") else request.dict(),
            "current_queries": request.exa_search_queries.copy(),
            "found_leads": [],
            "target_count": 5,
            "attempts": 0,
            "max_attempts": 3
        }
        graph = build_orchestrator_graph()
        await graph.ainvoke(state)

    # 4. Hand off to FastAPI Background Tasks
    background_tasks.add_task(run_brain_in_background)
    
    return {"status": "success", "message": "Campaign launched", "brief_id": brief.id}


@router.get("/conversations")
def get_sidebar_conversations(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Fetches the list of chats for the left sidebar."""
    convs = db.exec(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    ).all()
    return {"status": "success", "conversations": convs}


@router.get("/conversations/{id}")
def get_conversation_history(
    id: int, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Fetches the chat history and the linked blueprint when a user clicks a sidebar item."""
    conv = db.get(Conversation, id)
    if not conv or conv.user_id != current_user.id:
        return {"status": "error", "message": "Not found"}
        
    msgs = db.exec(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    
    # If they already launched this campaign, grab the brief so the UI can show the active Mission Control
    brief = None
    if conv.campaign_brief_id:
        brief = db.get(CampaignBrief, conv.campaign_brief_id)
        
    return {
        "status": "success", 
        "conversation": conv, 
        "messages": msgs, 
        "brief": brief
    }


@router.get("/results")
def get_campaign_results(
    brief_id: Optional[int] = None,  # <-- 1. Add the optional filter here
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Fetches the pipeline status and draft content for leads.
    If brief_id is provided, it ONLY returns leads for that specific campaign.
    """
    results = []
    
    # 2. Start building the query
    query = select(Lead).where(
        Lead.user_id == current_user.id,
        Lead.status != LeadStatus.FETCH_FAILED
    )
    
    # 3. Apply the specific campaign filter if the UI asked for it
    if brief_id is not None:
        query = query.where(Lead.campaign_brief_id == brief_id)
        
    # 4. Execute the query
    leads = db.exec(query.order_by(Lead.id.desc())).all()
    
    from app.models.domain import EnrichedLead

    for lead in leads:
        item = {
            "id": lead.id,
            "company_name": lead.company_name,
            "website_url": lead.website_url,
            "status": lead.status,
            "contact_name": None,
            "contact_email": None,
            "subject": None,
            "body": None
        }
        
        if lead.status in [LeadStatus.DRAFTING, LeadStatus.COMPLETED]:
            enriched = db.exec(select(EnrichedLead).where(EnrichedLead.lead_id == lead.id)).first()
            if enriched:
                from app.models.domain import SelectedContact
                sc = db.exec(select(SelectedContact).where(SelectedContact.enriched_lead_id == enriched.id)).first()
                if sc:
                    draft = db.exec(
                        select(OutreachDraft)
                        .where(OutreachDraft.selected_contact_id == sc.id)
                    ).first()
                else:
                    draft = None
                if draft:
                    item["contact_name"] = draft.contact_name
                    item["contact_email"] = draft.contact_email
                    item["subject"] = draft.subject
                    item["body"] = draft.body
                    
        results.append(item)
        
    return {"status": "success", "results": results}


@router.get("/{id}/status")
def get_campaign_status(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Fetches the current dynamic pipeline status.
    """
    lead = db.exec(
        select(Lead).where(Lead.id == id, Lead.user_id == current_user.id)
    ).first()
    if not lead:
        return {"status": "error", "message": "Campaign not found"}
    return {"status": "success", "pipeline_status": lead.status, "confidence": lead.investigation_confidence}


@router.get("/{id}/drafts")
def get_campaign_drafts(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Fetches completed drafts for a specific campaign (lead).
    We map lead -> enriched_lead -> outreach_drafts.
    """
    # Verify the lead belongs to current user
    lead = db.exec(
        select(Lead).where(
            Lead.id == id,
            Lead.user_id == current_user.id
        )
    ).first()
    
    if not lead:
        return {"status": "error", "message": "Campaign not found or unauthorized"}
        
    from app.models.domain import EnrichedLead
    
    enriched = db.exec(select(EnrichedLead).where(EnrichedLead.lead_id == id)).first()
    if not enriched:
        return {"status": "success", "drafts": []}
        
    drafts = db.exec(
        select(OutreachDraft)
        .where(
            OutreachDraft.enriched_lead_id == enriched.id,
            OutreachDraft.user_id == current_user.id
        )
    ).all()
    
    return {"status": "success", "drafts": drafts}
