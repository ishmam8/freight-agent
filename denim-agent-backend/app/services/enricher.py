import os
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from dotenv import load_dotenv
from sqlmodel import Session, select, SQLModel, create_engine

from app.models.domain import Lead, LeadStatus, EnrichedLead

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

DATABASE_URL = "sqlite:///denim_leads.db"
engine = create_engine(DATABASE_URL, echo=False)

EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")


def strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def normalize_domain(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    domain = domain.strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def normalize_email(email: str) -> str:
    return email.strip().lower()


def dedupe_list(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def format_address(parts: List[Optional[str]]) -> Optional[str]:
    cleaned = [str(p).strip() for p in parts if p and str(p).strip()]
    return ", ".join(cleaned) if cleaned else None


async def apollo_get_org(domain: str, client: httpx.AsyncClient) -> Dict[str, Any]:
    if not APOLLO_API_KEY:
        return {}

    url = "https://api.apollo.io/api/v1/organizations/enrich"
    headers = {
        "x-api-key": APOLLO_API_KEY,
        "Cache-Control": "no-cache",
    }

    try:
        response = await client.get(url, headers=headers, params={"domain": domain})
        response.raise_for_status()
        data = response.json()
        return data.get("organization", {}) or {}
    except Exception as e:
        print(f"[Apollo] Failed for {domain}: {e}")
        return {}


async def hunter_get_domain_data(domain: str, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    if not HUNTER_API_KEY:
        return []

    url = "https://api.hunter.io/v2/domain-search"
    params = {
        "domain": domain,
        "api_key": HUNTER_API_KEY,
        "limit": 10,
    }

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json().get("data", {})
        return data.get("emails", []) or []
    except Exception as e:
        print(f"[Hunter] Failed for {domain}: {e}")
        return []


def extract_regex_emails_from_text(text: Optional[str]) -> List[str]:
    if not text:
        return []
    matches = EMAIL_REGEX.findall(text)
    normalized = [normalize_email(email) for email in matches]
    return dedupe_list(normalized)


async def gemini_web_extract(company_name: str, website_url: str, scraped_text: str, client: httpx.AsyncClient) -> Dict[str, Any]:
    """
    Uses Gemini generateContent + Google Search grounding.
    Returns only explicit facts found on the internet.
    """
    if not GEMINI_API_KEY:
        return {"founders": [], "emails": [], "sources": []}

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    prompt = f"""
        You are a strict data extraction assistant.

        Search the web for this company and extract only explicit facts.
        Do not guess.
        Do not infer missing emails.
        Only return founders, owners, or CEOs explicitly tied to the company.
        Only return email addresses explicitly shown in  xthe grounded web material.
        Include source URLs.

        Return ONLY valid JSON in this exact shape:
        {{
        "founders": [
            {{"name": "Full Name", "title": "Title or null", "source_url": "https://..."}}
        ],
        "emails": [
            {{"email": "name@example.com", "source_url": "https://..."}}
        ],
        "sources": ["https://...", "https://..."]
        }}

        Company name: {company_name}
        Website URL: {website_url}

        Website scraped text:
        {(scraped_text or "")[:6000]}

        Search the web for founder, owner, CEO, about, contact, team, press, interview, and official pages related to this company.
        Extract only explicit facts.
        """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0},
    }

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=45.0)
        response.raise_for_status()
        data = response.json()

        text_output = None
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts and "text" in parts[0]:
                text_output = parts[0]["text"]

        if not text_output:
            return {"founders": [], "emails": [], "sources": []}

        clean_text = strip_json_fence(text_output)
        parsed = json.loads(clean_text)

        founders = parsed.get("founders", []) or []
        emails = parsed.get("emails", []) or []
        sources = parsed.get("sources", []) or []

        normalized_emails = []
        for item in emails:
            if isinstance(item, dict):
                email = item.get("email")
                source_url = item.get("source_url")
                if email and source_url:
                    normalized_emails.append({
                        "email": normalize_email(email),
                        "source_url": source_url.strip(),
                    })

        normalized_sources = []
        seen_sources = set()
        for source in sources:
            if isinstance(source, str):
                source = source.strip()
                if source and source not in seen_sources:
                    seen_sources.add(source)
                    normalized_sources.append(source)

        return {
            "founders": founders,
            "emails": normalized_emails,
            "sources": normalized_sources,
        }
    except Exception as e:
        print(f"[Gemini Web] Failed for {company_name}: {e}")
        return {"founders": [], "emails": [], "sources": []}


def get_employee_count_from_apollo(org_data: Dict[str, Any]) -> Optional[int]:
    raw = org_data.get("estimated_num_employees")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def get_address_from_apollo(org_data: Dict[str, Any]) -> Optional[str]:
    return format_address([
        org_data.get("city"),
        org_data.get("state"),
        org_data.get("country"),
    ])


def split_hunter_results(hunter_people: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
    people = []
    emails = []

    for person in hunter_people:
        email = person.get("value")
        first_name = person.get("first_name")
        last_name = person.get("last_name")
        position = person.get("position")
        confidence = person.get("confidence")
        verification = person.get("verification", {})
        verification_status = verification.get("status") if isinstance(verification, dict) else None

        people.append({
            "first_name": first_name,
            "last_name": last_name,
            "position": position,
            "email": email,
            "confidence": confidence,
            "verification_status": verification_status,
        })

        if email:
            emails.append(normalize_email(email))

    return people, dedupe_list(emails)


def build_enrichment_notes(
    org_data: Dict[str, Any],
    hunter_people_count: int,
    regex_email_count: int,
    web_founder_count: int,
    web_email_count: int,
) -> str:
    notes = {
        "apollo_org_found": bool(org_data),
        "hunter_people_found": hunter_people_count,
        "regex_emails_found": regex_email_count,
        "web_founders_found": web_founder_count,
        "web_emails_found": web_email_count,
    }
    return json.dumps(notes, ensure_ascii=False)


def upsert_enriched_lead(
    session: Session,
    lead: Lead,
    employee_count: Optional[int],
    address: Optional[str],
    hunter_people: List[Dict[str, Any]],
    hunter_emails: List[str],
    regex_emails: List[str],
    web_founders: List[Dict[str, Any]],
    web_emails: List[Dict[str, Any]],
    web_sources: List[str],
    enrichment_notes: str,
):
    existing = session.exec(
        select(EnrichedLead).where(EnrichedLead.lead_id == lead.id)
    ).first()

    payload = {
        "company_name": lead.company_name,
        "website_url": lead.website_url,
        "canonical_domain": lead.canonical_domain,
        "employee_count": employee_count,
        "address": address,
        "hunter_people_json": json.dumps(hunter_people, ensure_ascii=False),
        "hunter_emails_json": json.dumps(hunter_emails, ensure_ascii=False),
        "regex_emails_json": json.dumps(regex_emails, ensure_ascii=False),
        "web_founders_json": json.dumps(web_founders, ensure_ascii=False),
        "web_emails_json": json.dumps(web_emails, ensure_ascii=False),
        "web_sources_json": json.dumps(web_sources, ensure_ascii=False),
        "enrichment_notes": enrichment_notes,
    }

    if existing:
        existing.company_name = payload["company_name"]
        existing.website_url = payload["website_url"]
        existing.canonical_domain = payload["canonical_domain"]
        existing.employee_count = payload["employee_count"]
        existing.address = payload["address"]
        existing.hunter_people_json = payload["hunter_people_json"]
        existing.hunter_emails_json = payload["hunter_emails_json"]
        existing.regex_emails_json = payload["regex_emails_json"]
        existing.web_founders_json = payload["web_founders_json"]
        existing.web_emails_json = payload["web_emails_json"]
        existing.web_sources_json = payload["web_sources_json"]
        existing.enrichment_notes = payload["enrichment_notes"]
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        row = EnrichedLead(
            lead_id=lead.id,
            **payload
        )
        session.add(row)


from app.models.domain import User

async def enrich_one_lead(lead: Lead, client: httpx.AsyncClient, session: Session):
    domain = normalize_domain(lead.canonical_domain)

    if not domain:
        lead.status = LeadStatus.REJECTED
        lead.rejection_reason = "Missing canonical domain"
        session.add(lead)
        session.commit()
        print(f"[Rejected] {lead.company_name} -> missing canonical domain")
        return

    print(f"[Enriching] {lead.company_name} -> {domain}")

    user = session.get(User, lead.user_id) if lead.user_id else None
    tier = user.subscription_tier if user else "free"

    if tier == "free":
        print(f"[Tier] Free tier detected, skipping Apollo and Hunter")
        org_data = {}
        hunter_raw = []
    else:
        org_task = apollo_get_org(domain, client)
        hunter_task = hunter_get_domain_data(domain, client)
        org_data, hunter_raw = await asyncio.gather(org_task, hunter_task)
    
    regex_emails = extract_regex_emails_from_text(lead.scraped_context)

    hunter_people, hunter_emails = split_hunter_results(hunter_raw)
    web_data = await gemini_web_extract(
        company_name=lead.company_name,
        website_url=lead.website_url,
        scraped_text=lead.scraped_context or "",
        client=client,
    )
    web_founders = web_data.get("founders", []) or []
    web_emails = web_data.get("emails", []) or []
    web_sources = web_data.get("sources", []) or []

    employee_count = get_employee_count_from_apollo(org_data)
    address = get_address_from_apollo(org_data)

    enrichment_notes = build_enrichment_notes(
        org_data=org_data,
        hunter_people_count=len(hunter_people),
        regex_email_count=len(regex_emails),
        web_founder_count=len(web_founders),
        web_email_count=len(web_emails),
    )

    upsert_enriched_lead(
        session=session,
        lead=lead,
        employee_count=employee_count,
        address=address,
        hunter_people=hunter_people,
        hunter_emails=hunter_emails,
        regex_emails=regex_emails,
        web_founders=web_founders,
        web_emails=web_emails,
        web_sources=web_sources,
        enrichment_notes=enrichment_notes,
    )

    # Keep only investigated or rejected
    found_anything = bool(hunter_emails or regex_emails or web_emails)
    if found_anything:
        lead.enrichment_notes = "Enriched"
    else:
        lead.enrichment_notes = "No usable emails found from Hunter, regex, or web extraction"
    lead.status = LeadStatus.DRAFTING
    session.add(lead)
    session.commit()

    print(
        f"[Saved] {lead.company_name} | "
        f"hunter_people={len(hunter_people)} | "
        f"hunter_emails={len(hunter_emails)} | "
        f"regex_emails={len(regex_emails)} | "
        f"web_founders={len(web_founders)} | "
        f"web_emails={len(web_emails)}"
    )


async def run_phase_3_enrichment(batch_size: int = 10):
    create_db_and_tables()

    with Session(engine) as session:
        statement = (
            select(Lead)
            .where(Lead.status.in_([LeadStatus.ENRICHING]))
            .limit(batch_size)
        )
        leads = session.exec(statement).all()

        if not leads:
            print("No INVESTIGATED leads found.")
            return

        print(f"Found {len(leads)} leads to enrich.")

        async with httpx.AsyncClient(timeout=20.0) as client:
            for lead in leads:
                await enrich_one_lead(lead, client, session)

        print("Phase 3 enrichment complete.")


if __name__ == "__main__":
    asyncio.run(run_phase_3_enrichment(batch_size=30))