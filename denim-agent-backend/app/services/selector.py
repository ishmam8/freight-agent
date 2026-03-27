import json
import re
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlmodel import Session, select, SQLModel, create_engine

from app.models.domain import Lead, LeadStatus, EnrichedLead, SelectedContact

'''
This module is splitting between two layers: 
Layer1: it implements the logic for selecting the best contact from the enriched data for each lead.
Layer2 TODO: it implements a LLM verification on the top 1 to 3 candidates only.
Ask: which one is real & best for this outreach objective? why? is there any red flag?
'''

from app.core.config import settings
engine = create_engine(settings.DATABASE_URL, echo=False)

GENERIC_PREFIXES = {
    "info", "hello", "contact", "support", "sales", "wholesale", "team", "orders"
}

FOUNDER_KEYWORDS = {"founder", "co-founder", "owner", "cofounder"}
SENIOR_KEYWORDS = {
    "ceo", "president", "director", "head", "buyer",
    "sourcing", "operations", "merchandising", "manager"
}


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def normalize_domain(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    domain = domain.strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower()


def parse_json_field(raw: Optional[str], default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def email_domain(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].lower().strip()


def email_local(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[0].lower().strip()


def is_company_domain_email(email: Optional[str], canonical_domain: Optional[str]) -> bool:
    if not email or not canonical_domain:
        return False
    return email_domain(email) == normalize_domain(canonical_domain)


def is_generic_email(email: Optional[str]) -> bool:
    local = email_local(email)
    return local in GENERIC_PREFIXES if local else False


def classify_contact_type(name: Optional[str], title: Optional[str], email: Optional[str]) -> str:
    lowered_title = (title or "").lower()

    if any(k in lowered_title for k in FOUNDER_KEYWORDS):
        return "founder"

    if any(k in lowered_title for k in SENIOR_KEYWORDS):
        return "senior_human"

    if name and email and not is_generic_email(email):
        return "human"

    if email and is_generic_email(email):
        return "company_email"

    return "unknown"


def source_score(source: str, source_url: Optional[str]) -> int:
    if source == "regex":
        return 30

    if source == "hunter":
        return 25

    if source == "gemini_web":
        if source_url and any(x in source_url.lower() for x in ["team", "about", "contact", "official"]):
            return 20
        return 15

    return 5


def role_score(contact_type: str) -> int:
    if contact_type == "founder":
        return 100
    if contact_type == "senior_human":
        return 80
    if contact_type == "human":
        return 55
    if contact_type == "company_email":
        return 25
    return 0


def email_score(email: Optional[str], canonical_domain: Optional[str], contact_type: str) -> int:
    if not email:
        return 0

    if is_company_domain_email(email, canonical_domain):
        if contact_type == "company_email":
            return 20
        return 40

    return 5


def candidate_score(candidate: Dict[str, Any], canonical_domain: Optional[str], target_titles: List[str] = None) -> int:
    score = 0

    contact_type = candidate.get("contact_type", "unknown")
    email = candidate.get("email")
    source = candidate.get("source", "unknown")
    source_url = candidate.get("source_url")

    score += role_score(contact_type)
    score += email_score(email, canonical_domain, contact_type)
    score += source_score(source, source_url)

    if email and not is_company_domain_email(email, canonical_domain) and contact_type in {"human", "senior_human", "founder"}:
        score -= 20

    if target_titles and candidate.get("title"):
        cond = candidate["title"].lower()
        if any(t.lower() in cond for t in target_titles):
            score += 200

    return score


def dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []

    for c in candidates:
        key = (
            (c.get("name") or "").strip().lower(),
            (c.get("title") or "").strip().lower(),
            (c.get("email") or "").strip().lower(),
            (c.get("source") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(c)

    return out


def build_candidates(enriched: EnrichedLead, target_titles: List[str] = None) -> List[Dict[str, Any]]:
    canonical_domain = normalize_domain(enriched.canonical_domain)

    hunter_people = parse_json_field(enriched.hunter_people_json, [])
    hunter_emails = parse_json_field(enriched.hunter_emails_json, [])
    regex_emails = parse_json_field(enriched.regex_emails_json, [])
    web_founders = parse_json_field(enriched.web_founders_json, [])
    web_emails = parse_json_field(enriched.web_emails_json, [])

    candidates: List[Dict[str, Any]] = []

    for person in hunter_people:
        email = normalize_email(person.get("email"))
        name = " ".join(
            [
                (person.get("first_name") or "").strip(),
                (person.get("last_name") or "").strip(),
            ]
        ).strip() or None
        title = person.get("position")
        contact_type = classify_contact_type(name, title, email)

        candidates.append({
            "name": name,
            "title": title,
            "email": email,
            "contact_type": contact_type,
            "source": "hunter",
            "source_url": None,
            "company_domain_email": is_company_domain_email(email, canonical_domain),
            "generic_email": is_generic_email(email) if email else False,
        })

    for email in regex_emails:
        email = normalize_email(email)
        candidates.append({
            "name": None,
            "title": None,
            "email": email,
            "contact_type": "company_email" if is_generic_email(email) else "human",
            "source": "regex",
            "source_url": enriched.website_url,
            "company_domain_email": is_company_domain_email(email, canonical_domain),
            "generic_email": is_generic_email(email),
        })

    for founder in web_founders:
        name = founder.get("name")
        title = founder.get("title")
        source_url = founder.get("source_url")
        candidates.append({
            "name": name,
            "title": title,
            "email": None,
            "contact_type": classify_contact_type(name, title, None),
            "source": "gemini_web",
            "source_url": source_url,
            "company_domain_email": False,
            "generic_email": False,
        })

    for item in web_emails:
        email = normalize_email(item.get("email"))
        source_url = item.get("source_url")
        candidates.append({
            "name": None,
            "title": None,
            "email": email,
            "contact_type": "company_email" if is_generic_email(email) else "human",
            "source": "gemini_web",
            "source_url": source_url,
            "company_domain_email": is_company_domain_email(email, canonical_domain),
            "generic_email": is_generic_email(email),
        })

    candidates = dedupe_candidates(candidates)

    for c in candidates:
        c["score"] = candidate_score(c, canonical_domain, target_titles)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def pick_best_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    top = candidates[0]

    # Require an email for selection in v1
    if not top.get("email"):
        email_candidates = [c for c in candidates if c.get("email")]
        if email_candidates:
            return email_candidates[0]
        return None

    return top


def selection_confidence(score: int) -> float:
    if score >= 140:
        return 0.95
    if score >= 120:
        return 0.88
    if score >= 95:
        return 0.78
    if score >= 70:
        return 0.65
    return 0.50


def selection_reason(candidate: Dict[str, Any]) -> str:
    parts = []

    if candidate.get("contact_type"):
        parts.append(f"type={candidate['contact_type']}")

    if candidate.get("email"):
        parts.append("has_email")

    if candidate.get("company_domain_email"):
        parts.append("company_domain_email")

    if candidate.get("generic_email"):
        parts.append("generic_email")

    if candidate.get("source"):
        parts.append(f"source={candidate['source']}")

    return ", ".join(parts)


def upsert_selected_contact(
    session: Session,
    lead: Lead,
    enriched: EnrichedLead,
    selected: Optional[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
):
    existing = session.exec(
        select(SelectedContact).where(SelectedContact.lead_id == lead.id)
    ).first()

    payload = {
        "lead_id": lead.id,
        "enriched_lead_id": enriched.id,
        "company_name": enriched.company_name,
        "website_url": enriched.website_url,
        "canonical_domain": enriched.canonical_domain,
        "selected_contact_name": selected.get("name") if selected else None,
        "selected_contact_title": selected.get("title") if selected else None,
        "selected_email": selected.get("email") if selected else None,
        "selected_contact_type": selected.get("contact_type") if selected else None,
        "selected_source": selected.get("source") if selected else None,
        "selected_source_url": selected.get("source_url") if selected else None,
        "selection_score": selected.get("score") if selected else None,
        "selection_confidence": selection_confidence(selected["score"]) if selected else None,
        "selection_reason": selection_reason(selected) if selected else "no_candidate_selected",
        "all_candidate_contacts_json": json.dumps(candidates, ensure_ascii=False),
    }

    if existing:
        existing.enriched_lead_id = payload["enriched_lead_id"]
        existing.company_name = payload["company_name"]
        existing.website_url = payload["website_url"]
        existing.canonical_domain = payload["canonical_domain"]
        existing.selected_contact_name = payload["selected_contact_name"]
        existing.selected_contact_title = payload["selected_contact_title"]
        existing.selected_email = payload["selected_email"]
        existing.selected_contact_type = payload["selected_contact_type"]
        existing.selected_source = payload["selected_source"]
        existing.selected_source_url = payload["selected_source_url"]
        existing.selection_score = payload["selection_score"]
        existing.selection_confidence = payload["selection_confidence"]
        existing.selection_reason = payload["selection_reason"]
        existing.all_candidate_contacts_json = payload["all_candidate_contacts_json"]
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        session.add(SelectedContact(**payload))


async def run_phase_4a_selector(batch_size: int = 25):
    create_db_and_tables()

    with Session(engine) as session:
        statement = (
            select(Lead, EnrichedLead)
            .join(EnrichedLead, EnrichedLead.lead_id == Lead.id)
            .where(Lead.status == LeadStatus.DRAFTING)
            .limit(batch_size)
        )

        rows = session.exec(statement).all()

        if not rows:
            print("No ENRICHED leads found for selection.")
            return

        print(f"Found {len(rows)} ENRICHED leads to select from.")

        for lead, enriched in rows:
            candidates = build_candidates(enriched)
            selected = pick_best_candidate(candidates)

            upsert_selected_contact(
                session=session,
                lead=lead,
                enriched=enriched,
                selected=selected,
                candidates=candidates,
            )

            session.commit()

            if selected:
                print(
                    f"[Selected] {enriched.company_name} -> "
                    f"{selected.get('email')} | {selected.get('contact_type')} | score={selected.get('score')}"
                )
            else:
                print(f"[No Selection] {enriched.company_name}")

        print("Phase 4A selector complete.")