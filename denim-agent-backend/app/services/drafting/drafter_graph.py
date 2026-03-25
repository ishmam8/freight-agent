import json
from datetime import datetime
from typing import TypedDict, Optional, Dict, Any, List

from langgraph.graph import StateGraph, END
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.domain import (
    Lead,
    EnrichedLead,
    SelectedContact,
    OutreachDraft,
)
from app.services.drafting.draft_brief import build_outreach_brief
from app.services.drafting.ollama_client import generate_draft_with_ollama
from app.services.drafting.gmail_draft_graph import create_gmail_draft

DATABASE_URL = "sqlite:///denim_leads.db"
engine = create_engine(DATABASE_URL, echo=False)


class DraftState(TypedDict, total=False):
    selected_contact_id: int
    campaign_brief: Dict[str, Any]

    lead: Dict[str, Any]
    enriched: Dict[str, Any]
    selected: Dict[str, Any]

    outreach_brief: Dict[str, Any]
    generated_draft: Dict[str, Any]

    validation_errors: List[str]
    outreach_draft_id: Optional[int]
    gmail_draft_id: Optional[str]

    status: str
    error: Optional[str]


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def model_to_dict(obj) -> Dict[str, Any]:
    return obj.model_dump() if hasattr(obj, "model_dump") else dict(obj)


def load_context(state: DraftState) -> DraftState:
    selected_contact_id = state["selected_contact_id"]

    with Session(engine) as session:
        selected = session.exec(
            select(SelectedContact).where(SelectedContact.id == selected_contact_id)
        ).first()

        if not selected:
            return {
                **state,
                "status": "failed",
                "error": f"SelectedContact {selected_contact_id} not found",
            }

        lead = session.exec(
            select(Lead).where(Lead.id == selected.lead_id)
        ).first()

        enriched = session.exec(
            select(EnrichedLead).where(EnrichedLead.lead_id == selected.lead_id)
        ).first()

        if not lead or not enriched:
            return {
                **state,
                "status": "failed",
                "error": "Lead or EnrichedLead missing for selected contact",
            }

    return {
        **state,
        "lead": model_to_dict(lead),
        "enriched": model_to_dict(enriched),
        "selected": model_to_dict(selected),
        "status": "context_loaded",
    }


def build_brief_node(state: DraftState) -> DraftState:
    lead = Lead(**state["lead"])
    enriched = EnrichedLead(**state["enriched"])
    selected = SelectedContact(**state["selected"])
    campaign_brief = state.get("campaign_brief", {})

    brief = build_outreach_brief(
        lead=lead,
        enriched=enriched,
        selected=selected,
        campaign_brief_dict=campaign_brief,
    )

    return {
        **state,
        "outreach_brief": brief,
        "status": "brief_built",
    }


async def draft_with_ollama_node(state: DraftState) -> DraftState:
    brief = state["outreach_brief"]
    draft = await generate_draft_with_ollama(brief)

    return {
        **state,
        "generated_draft": draft,
        "status": "draft_generated",
    }


def validate_draft_node(state: DraftState) -> DraftState:
    errors: List[str] = []
    draft = state.get("generated_draft", {})
    selected = state.get("selected", {})

    subject = (draft.get("subject") or "").strip()
    body = (draft.get("body") or "").strip()
    email = (selected.get("selected_email") or "").strip()

    if not email:
        errors.append("Missing selected email")

    if not subject:
        errors.append("Missing subject")

    if not body:
        errors.append("Missing body")

    if len(body.split()) > 160:
        errors.append("Body too long")

    if "YOUR_COMPANY_NAME" in body or "YOUR_COMPANY_NAME" in subject:
        errors.append("Placeholder company name still present")

    status = "valid" if not errors else "invalid"

    return {
        **state,
        "validation_errors": errors,
        "status": status,
    }


def validation_router(state: DraftState) -> str:
    return "save_outreach_draft" if state.get("status") == "valid" else "mark_failed"


def save_outreach_draft_node(state: DraftState) -> DraftState:
    lead = state["lead"]
    enriched = state["enriched"]
    selected = state["selected"]
    draft = state["generated_draft"]

    with Session(engine) as session:
        existing = session.exec(
            select(OutreachDraft).where(
                OutreachDraft.selected_contact_id == selected["id"]
            )
        ).first()

        payload = {
            "lead_id": lead["id"],
            "user_id": lead.get("user_id"),
            "enriched_lead_id": enriched["id"],
            "selected_contact_id": selected["id"],
            "company_name": selected["company_name"],
            "contact_name": selected.get("selected_contact_name"),
            "contact_title": selected.get("selected_contact_title"),
            "contact_email": selected.get("selected_email"),
            "subject": draft["subject"],
            "body": draft["body"],
            "draft_mode": draft.get("draft_mode"),
            "personalization_json": json.dumps(
                draft.get("personalization_points", []),
                ensure_ascii=False,
            ),
            "draft_notes": draft.get("notes"),
            "draft_status": "generated",
        }

        if existing:
            existing.company_name = payload["company_name"]
            existing.contact_name = payload["contact_name"]
            existing.contact_title = payload["contact_title"]
            existing.contact_email = payload["contact_email"]
            existing.subject = payload["subject"]
            existing.body = payload["body"]
            existing.draft_mode = payload["draft_mode"]
            existing.personalization_json = payload["personalization_json"]
            existing.draft_notes = payload["draft_notes"]

            if not existing.gmail_draft_id:
                existing.draft_status = "generated"

            existing.updated_at = datetime.utcnow()
            session.add(existing)
            session.commit()
            outreach_draft_id = existing.id
        else:
            row = OutreachDraft(**payload)
            session.add(row)
            session.commit()
            session.refresh(row)
            outreach_draft_id = row.id

    return {
        **state,
        "outreach_draft_id": outreach_draft_id,
        "status": "draft_saved",
    }


def create_gmail_draft_node(state: DraftState) -> DraftState:
    return {
        **state,
        "status": "saved_to_db_only",
        "gmail_draft_id": "bypassed",
    }


def finalize_node(state: DraftState) -> DraftState:
    return {
        **state,
        "status": "done",
    }


def mark_failed_node(state: DraftState) -> DraftState:
    error = "; ".join(state.get("validation_errors", [])) or state.get("error") or "unknown_error"
    return {
        **state,
        "status": "failed",
        "error": error,
    }


def build_drafter_graph():
    graph = StateGraph(DraftState)

    graph.add_node("load_context", load_context)
    graph.add_node("build_brief", build_brief_node)
    graph.add_node("draft_with_ollama", draft_with_ollama_node)
    graph.add_node("validate_draft", validate_draft_node)
    graph.add_node("save_outreach_draft", save_outreach_draft_node)
    graph.add_node("create_gmail_draft", create_gmail_draft_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("mark_failed", mark_failed_node)

    graph.set_entry_point("load_context")

    graph.add_edge("load_context", "build_brief")
    graph.add_edge("build_brief", "draft_with_ollama")
    graph.add_edge("draft_with_ollama", "validate_draft")

    graph.add_conditional_edges(
        "validate_draft",
        validation_router,
        {
            "save_outreach_draft": "save_outreach_draft",
            "mark_failed": "mark_failed",
        },
    )

    graph.add_edge("save_outreach_draft", "create_gmail_draft")
    graph.add_edge("create_gmail_draft", "finalize")
    graph.add_edge("mark_failed", END)
    graph.add_edge("finalize", END)

    return graph.compile()