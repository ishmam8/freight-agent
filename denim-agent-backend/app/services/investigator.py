from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
import os
import json
from sqlmodel import Session, select

from app.models.domain import Lead, LeadCategory, LeadStatus, CampaignBrief

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


APPAREL_TERMS = {
    "apparel",
    "fashion",
    "clothing",
    "wear",
    "menswear",
    "womenswear",
    "streetwear",
    "denim",
    "jeans",
    "jacket",
    "pants",
    "shirt",
    "hoodie",
    "collection",
    "shop",
    "store",
}

BRAND_TERMS = {
    "our brand",
    "designed in",
    "designed for",
    "founded",
    "founded in",
    "we design",
    "we make",
    "our collection",
    "shop now",
    "new arrivals",
    "lookbook",
    "crafted",
}

RETAILER_TERMS = {
    "boutique",
    "retailer",
    "stores",
    "locations",
    "shop all",
    "in store",
    "online store",
    "our stores",
}

PRIVATE_LABEL_TERMS = {
    "private label",
    "in-house label",
    "house brand",
    "our label",
    "our own brand",
    "exclusive collection",
    "exclusive line",
}

HARD_REJECTION_TERMS = {
    "manufacturer",
    "manufacturing",
    "factory",
    "supplier",
    "wholesaler",
    "wholesale manufacturer",
    "sourcing company",
    "buying house",
    "oem",
    "private label manufacturer",
    "cut and sew",
    "bulk production",
    "custom manufacturing",
    "uniform supplier",
    "print on demand",
    "dropshipping",
    "directory",
    "marketplace",
}

SOFT_B2B_TERMS = {
    "b2b",
    "bulk order",
    "minimum order quantity",
    "moq",
    "exporter",
    "distributor",
}

SOCIAL_DOMAINS = {
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "tiktok.com",
    "www.tiktok.com",
    "linktr.ee",
    "www.linktr.ee",
}


@dataclass
class PageContent:
    url: str
    text: str
    title: str = ""
    meta_description: str = ""


@dataclass
class InvestigationResult:
    status: LeadStatus
    canonical_domain: Optional[str]
    scraped_context: Optional[str]
    investigation_notes: str
    rejection_reason: Optional[str]
    investigation_confidence: float


def normalize_website_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        return ""

    if not raw_url.startswith(("http://", "https://")):
        raw_url = f"https://{raw_url}"

    parsed = urlparse(raw_url)
    if not parsed.netloc:
        return ""

    normalized = f"{parsed.scheme}://{parsed.netloc}"
    return normalized.rstrip("/")


def extract_domain(raw_url: str) -> Optional[str]:
    normalized = normalize_website_url(raw_url)
    if not normalized:
        return None
    parsed = urlparse(normalized)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None


def candidate_urls(base_url: str) -> list[str]:
    paths = ["", "/about", "/about-us", "/our-story", "/contact", "/contact-us"]
    return [urljoin(base_url + "/", path.lstrip("/")) for path in paths]


def clean_html_to_text(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.extract()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    meta_description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        meta_description = meta["content"].strip()

    body_text = soup.get_text(separator=" ", strip=True)
    body_text = " ".join(body_text.split())

    return title, meta_description, body_text


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[PageContent]:
    try:
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None

        title, meta_description, text = clean_html_to_text(response.text)
        if not text:
            return None

        return PageContent(
            url=str(response.url),
            title=title,
            meta_description=meta_description,
            text=text,
        )
    except Exception:
        return None


def combine_page_content(pages: list[PageContent], max_chars: int = 5000) -> str:
    chunks: list[str] = []
    seen = set()

    for page in pages:
        for part in [page.title, page.meta_description, page.text]:
            part = (part or "").strip()
            if not part or part in seen:
                continue
            seen.add(part)
            chunks.append(part)

    combined = "\n\n".join(chunks)
    return combined[:max_chars]


def find_matches(text: str, keywords: set[str]) -> list[str]:
    lowered = text.lower()
    return sorted([kw for kw in keywords if kw in lowered])


async def classify_lead_with_llm(scraped_text: str, brief: CampaignBrief, client: httpx.AsyncClient) -> InvestigationResult:
    prompt = f"""
    You are a lead qualification AI. Read this company's website text.
    
    Target Audience: {brief.target_audience}
    Must NOT be: {brief.banned_terms}
    
    Website Text:
    {scraped_text[:4000]}
    
    Determine if this website matches the Target Audience.
    Return ONLY JSON:
    {{
        "is_match": true/false,
        "confidence": 0.0 to 1.0,
        "reasoning": "1 sentence explaining why"
    }}
    """

    if not GEMINI_API_KEY:
        return InvestigationResult(
            status=LeadStatus.REJECTED,
            canonical_domain=None,
            scraped_context=scraped_text[:5000],
            investigation_notes="Gemini API Key missing.",
            rejection_reason="Gemini API Key missing.",
            investigation_confidence=0.0,
        )

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        text_output = None
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts and "text" in parts[0]:
                text_output = parts[0]["text"]

        if text_output:
            text_output = text_output.strip()
            if text_output.startswith("```json"):
                text_output = text_output[7:-3].strip()
            elif text_output.startswith("```"):
                text_output = text_output[3:-3].strip()

            parsed = json.loads(text_output)
            is_match = parsed.get("is_match", False)
            confidence = float(parsed.get("confidence", 0.0))
            reasoning = parsed.get("reasoning", "")
        else:
            is_match = False
            confidence = 0.0
            reasoning = "LLM returned empty output."

    except Exception as e:
        is_match = False
        confidence = 0.0
        reasoning = f"LLM error: {e}"

    if is_match:
        return InvestigationResult(
            status=LeadStatus.ENRICHING,
            canonical_domain=None,
            scraped_context=scraped_text[:5000],
            investigation_notes=reasoning,
            rejection_reason=None,
            investigation_confidence=confidence,
        )
    else:
        return InvestigationResult(
            status=LeadStatus.REJECTED,
            canonical_domain=None,
            scraped_context=scraped_text[:5000],
            investigation_notes="Rejected by LLM",
            rejection_reason=reasoning,
            investigation_confidence=confidence,
        )


async def investigate_lead(lead: Lead, brief: CampaignBrief) -> InvestigationResult:
    # --- MOCK MODE INTERCEPT ---
    if os.getenv("USE_MOCK_DATA") == "True":
        print(f"[MOCK] Skipping web scraping for {lead.website_url}. Instantly approving.")
        return InvestigationResult(
            status=LeadStatus.ENRICHING,
            canonical_domain="mocklogistics.com",
            scraped_context="This is a mock logistics company that perfectly matches the criteria.",
            investigation_notes="Mock Mode: Auto-approved.",
            rejection_reason=None,
            investigation_confidence=0.99,
        )
    # --- END MOCK MODE ---
    
    base_url = normalize_website_url(lead.website_url)
    domain = extract_domain(lead.website_url)

    if not base_url or not domain:
        return InvestigationResult(
            status=LeadStatus.FETCH_FAILED,
            canonical_domain=None,
            scraped_context=None,
            investigation_notes="Invalid or empty website URL.",
            rejection_reason=None,
            investigation_confidence=0.0,
        )

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(
        timeout=12.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        pages: list[PageContent] = []

        for url in candidate_urls(base_url):
            page = await fetch_page(client, url)
            if page:
                pages.append(page)

    if not pages:
        return InvestigationResult(
            status=LeadStatus.FETCH_FAILED,
            canonical_domain=domain,
            scraped_context=None,
            investigation_notes="Could not fetch usable HTML content from homepage/about/contact pages.",
            rejection_reason=None,
            investigation_confidence=0.0,
        )

    combined_text = combine_page_content(pages)
    if len(combined_text.strip()) < 150:
        return InvestigationResult(
            status=LeadStatus.FETCH_FAILED,
            canonical_domain=domain,
            scraped_context=combined_text or None,
            investigation_notes="Fetched content was too thin to classify reliably.",
            rejection_reason=None,
            investigation_confidence=0.1,
        )

    async with httpx.AsyncClient(timeout=30.0) as llm_client:
        result = await classify_lead_with_llm(combined_text, brief, llm_client)
        result.canonical_domain = domain
        return result


async def run_phase_2_investigation(session: Session, batch_size: int = 50) -> dict[str, int]:
    statement = (
        select(Lead)
        .where(Lead.status == LeadStatus.QUEUED)
        .limit(batch_size)
    )
    leads = session.exec(statement).all()

    results = {
        "processed": 0,
        "investigated": 0,
        "rejected": 0,
        "fetch_failed": 0,
    }

    for lead in leads:
        brief = session.get(CampaignBrief, lead.campaign_brief_id) if lead.campaign_brief_id else None
        if not brief:
            continue
        result = await investigate_lead(lead, brief)

        lead.canonical_domain = result.canonical_domain
        lead.scraped_context = result.scraped_context
        lead.investigation_notes = result.investigation_notes
        lead.rejection_reason = result.rejection_reason
        lead.investigation_confidence = result.investigation_confidence
        lead.status = result.status

        session.add(lead)
        session.commit()

        results["processed"] += 1

        if result.status == LeadStatus.ENRICHING:
            results["investigated"] += 1
        elif result.status == LeadStatus.REJECTED:
            results["rejected"] += 1
        elif result.status == LeadStatus.FETCH_FAILED:
            results["fetch_failed"] += 1

    return results