import os
import httpx
from pydantic import BaseModel
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings
from typing import List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user, get_db
from app.models.domain import User, Lead, LeadStatus, OutreachDraft, CampaignBrief, Conversation, ChatMessage
from app.models.schemas import PromptRequest, LaunchRequest, DraftUpdateRequest
from app.services.brief_parser import parse_campaign_brief
from app.services.orchestrator_graph import build_orchestrator_graph

router = APIRouter()

class ChatTurn(BaseModel):
    role: str
    content: str

class PlannerChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    messages: list[ChatTurn]

@router.post("/planner/chat")
async def planner_chat(
    request: PlannerChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    if request.conversation_id:
        conv = db.get(Conversation, request.conversation_id)
        if not conv or conv.user_id != current_user.id:
            return {"status": "error", "message": "Conversation not found"}
        
        if request.messages:
            last_msg = request.messages[-1]
            db.add(ChatMessage(conversation_id=conv.id, role=last_msg.role, content=last_msg.content))
            db.commit()
    else:
        user_msgs = [m.content for m in request.messages if m.role == "user"]
        title_text = user_msgs[0] if user_msgs else "New Campaign Chat"
        title = title_text[:30] + "..." if len(title_text) > 30 else title_text
        
        conv = Conversation(user_id=current_user.id, title=title)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        
        for m in request.messages:
            db.add(ChatMessage(conversation_id=conv.id, role=m.role, content=m.content))
        db.commit()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {"status": "error", "message": "GEMINI_API_KEY is missing from the environment."}
        
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    
    system_instruction = (
        "You are an elite B2B Campaign Planner Agent. Help the user draft a highly effective outbound campaign brief conversationally. "
        "Your goal is to collect or collaboratively brainstorm 7 key parameters for their campaign.\n\n"
        "STEPS:\n"
        "1. First, establish the core: Ask the user for their Target Audience (ICP) and what their Value Proposition is. Just focus on these two if they haven't provided them.\n"
        "2. Once you have the core, suggest 3-4 Ideal Buyer Titles (e.g., 'VP of Sales', 'Operations Director') that make sense for their audience and ask if they look good.\n"
        "3. Ask if there are any specific Banned Terms or types of companies they definitely want to AVOID (e.g., 'B2C', 'retailers', 'agencies').\n"
        "4. Ask for their Name (Sender Name) and Company (Sender Company).\n\n"
        "RULES:\n"
        "- Be conversational, consultative, and concise. Don't overwhelm the user with all questions at once.\n"
        "- Generate highly optimized 'exa_search_queries' silently in the background (3 to 5 Google-like queries tailored to find only the target companies).\n"
        "- Once all fields are confirmed, summarize the campaign beautifully. Then ask: 'Are you ready to approve and launch this campaign?'\n"
        "- IF AND ONLY IF the user explicitly approves and says yes to launching, output ONLY a raw JSON block wrapped in ```json ... ``` containing ALL of the following keys:\n"
        "  target_audience (string), value_proposition (string), sender_name (string), sender_company (string), "
        "buyer_titles (array of strings), banned_terms (array of strings), and exa_search_queries (array of strings)."
    )
    
    formatted_messages = [
        {"role": "model" if msg.role == "ai" else msg.role, "parts": [{"text": msg.content}]} 
        for msg in request.messages
    ]
    
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": formatted_messages,
        "generationConfig": {
            "temperature": 0.7
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    text_output = ""
    candidates = data.get("candidates", [])
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if parts and "text" in parts[0]:
            text_output = parts[0]["text"]
            
    if text_output.strip():
        db.add(ChatMessage(conversation_id=conv.id, role="ai", content=text_output.strip()))
        db.commit()
            
    return {"status": "success", "response": text_output.strip(), "conversation_id": conv.id}


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Takes an approved brief, saves it, and orchestrates the search graph via ARQ background worker.
    """
    if current_user.credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Out of Credits, please buy more credits or wait for 3 days"
        )

    # 1. Create the Brief
    brief = CampaignBrief(
        user_id=current_user.id,
        original_prompt=request.original_prompt,
        target_audience=request.target_audience,
        banned_terms=request.banned_terms,
        buyer_titles=request.buyer_titles,
        value_proposition=request.value_proposition,
        exa_search_queries=request.exa_search_queries,
        sender_name=request.sender_name,
        sender_company=request.sender_company,
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
        else:
            title = f"Campaign: {request.target_audience[:20]}..."
            conv = Conversation(user_id=current_user.id, title=title, campaign_brief_id=brief.id)
            db.add(conv)
            db.commit()
    else:
        title = f"Campaign: {request.target_audience[:20]}..."
        conv = Conversation(user_id=current_user.id, title=title, campaign_brief_id=brief.id)
        db.add(conv)
        db.commit()

    # 3. Trigger the Orchestrator via ARQ Redis
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        await redis_pool.enqueue_job('run_orchestrator_job', current_user.id, brief.id)
    finally:
        await redis_pool.close()
    
    return {"status": "success", "message": "Campaign launched via background worker", "brief_id": brief.id}


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
            "rejection_reason": lead.rejection_reason,
            "subject": None,
            "body": None,
            "draft_notes": None,
            "personalization_json": None,
            "hook_type": None,
            "word_count": None
        }
        
        if lead.status in [LeadStatus.DRAFTING, LeadStatus.COMPLETED]:
            enriched = db.exec(select(EnrichedLead).where(EnrichedLead.lead_id == lead.id)).first()
            if enriched:
                item["web_founders_json"] = enriched.web_founders_json
                item["web_emails_json"] = enriched.web_emails_json
                
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
                    item["draft_notes"] = draft.draft_notes
                    item["personalization_json"] = draft.personalization_json
                    item["hook_type"] = draft.hook_type
                    item["word_count"] = draft.word_count
                    
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


@router.patch("/{lead_id}/draft")
def update_lead_draft(
    lead_id: int,
    request: DraftUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Updates the outreach draft for a specific lead.
    Verifies ownership and queries down the chain Lead -> EnrichedLead -> SelectedContact -> OutreachDraft.
    """
    # 1. Verify Lead belongs to current_user
    lead = db.exec(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.user_id == current_user.id
        )
    ).first()
    
    if not lead:
        return {"status": "error", "message": "Lead not found or unauthorized"}
    
    # 2. Query down the chain
    from app.models.domain import EnrichedLead, SelectedContact
    
    enriched = db.exec(select(EnrichedLead).where(EnrichedLead.lead_id == lead.id)).first()
    if not enriched:
        return {"status": "error", "message": "Enriched lead not found"}
        
    sc = db.exec(select(SelectedContact).where(SelectedContact.enriched_lead_id == enriched.id)).first()
    if not sc:
        return {"status": "error", "message": "Selected contact not found"}
        
    draft = db.exec(
        select(OutreachDraft)
        .where(OutreachDraft.selected_contact_id == sc.id)
    ).first()
    
    if not draft:
        return {"status": "error", "message": "Draft not found"}
        
    # 3. Update the draft
    draft.subject = request.subject
    draft.body = request.body
    draft.updated_at = datetime.utcnow()
    
    db.add(draft)
    db.commit()
    
    return {"status": "success", "message": "Draft updated"}

