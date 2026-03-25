import os
from datetime import datetime
from dotenv import load_dotenv
from exa_py import Exa
from typing import Optional

from app.models.schemas import LeadCreate, ResearchRequest
from app.models.domain import LeadCategory
from app.services.research.vertical_exhibit_scraper import scrape_expo_directory

load_dotenv()
exa = Exa(api_key=os.getenv("EXA_API_KEY"))


def clean_company_name(title: Optional[str]) -> str:
    if not title:
        return "Unknown Company"

    cleaned = title.split("|")[0].split(" - ")[0].strip()
    return cleaned or "Unknown Company"


def is_canadian_result(title, summary, url):
    text = f"{title or ''} {summary or ''}".lower()

    canada_terms = [
        "canada",
        "canadian",
        "vancouver",
        "toronto",
        "montreal",
        "calgary",
        "ottawa"
    ]

    return any(term in text for term in canada_terms)


def is_obviously_irrelevant(title: Optional[str], summary: Optional[str], url: Optional[str]) -> bool:
    text = f"{title or ''} {summary or ''} {url or ''}".lower()

    banned_terms = [
        "manufacturer",
        "manufacturing",
        "factory",
        "supplier",
        "wholesaler",
        "production house",
        "garment factory",
        "textile mill",
        "oem",
        "private label manufacturer",
        "apparel manufacturer",
        "clothing manufacturer",
        "cut and sew",
        "bulk production",
        "custom manufacturing",
    ]

    if any(term in text for term in banned_terms):
        return True

    if not is_canadian_result(title, summary, url):
        return True

    return False


def build_exa_prompt(category: LeadCategory, location: str, current_year: int) -> str:
    if category == LeadCategory.INDEPENDENT_BRAND:
        return f"""
Official websites of active, consumer-facing independent apparel brands based in {location} in {current_year}
that sell denim, jeans, streetwear, or contemporary fashion.

Exclude manufacturers, factories, sourcing companies, wholesalers, exporters,
buying houses, and B2B production companies.
""".strip()

    if category == LeadCategory.PRIVATE_LABEL_RETAILER:
        return f"""
Official websites of clothing retailers or boutique chains based in {location} in {current_year}
that sell their own private-label or in-house apparel, including denim or jeans.

Exclude manufacturers, factories, sourcing companies, wholesalers, exporters,
buying houses, and B2B production companies.
""".strip()

    raise ValueError("Unsupported category for Exa research.")


async def run_prompt_research(prompt: str, num_results: int = 5, exclude_domains: Optional[list[str]] = None) -> list[LeadCreate]:
    print(f"Triggering Exa.ai Search for custom prompt: {prompt}...")

    leads: list[LeadCreate] = []

    try:
        response = exa.search_and_contents(
            prompt,
            type="neural",
            num_results=num_results,
            category="company",
            summary=True,
            exclude_domains=exclude_domains,
        )

        for result in response.results:
            title = result.title or ""
            summary = result.summary or ""
            url = result.url

            if not url:
                print(f"Skipping result with missing URL: {title}")
                continue

            print(f"Keeping result: {title} | {url}")

            try:
                leads.append(
                    LeadCreate(
                        company_name=clean_company_name(title),
                        website_url=url,
                        category=LeadCategory.INDEPENDENT_BRAND,
                        description=summary,
                        source="MVP Command Center Prompt",
                    )
                )
            except Exception as validation_error:
                print(f"Skipping invalid result: {title} | {url} | Error: {validation_error}")

    except Exception as e:
        print(f"Exa search failed: {e}")

    return leads

async def run_hybrid_research(request: ResearchRequest) -> list[LeadCreate]:
    # Route 1, vertical scraper for expo exhibitor pages
    if request.category == LeadCategory.EXPO_EXHIBITOR:
        if not request.target_url:
            raise ValueError("target_url is required for expo_exhibitor category.")
        return await scrape_expo_directory(str(request.target_url))

    # Route 2, Exa search for brand and retailer discovery
    current_year = datetime.now().year
    print(f"Triggering Exa.ai Search for {request.category.value} in {request.location} ({current_year})...")

    prompt = build_exa_prompt(
        category=request.category,
        location=request.location,
        current_year=current_year,
    )

    leads: list[LeadCreate] = []

    try:
        response = exa.search_and_contents(
            prompt,
            type="neural",
            num_results=request.num_results,
            category="company",
            summary=True,
        )

        for result in response.results:
            title = result.title or ""
            summary = result.summary or ""
            url = result.url

            if not url:
                print(f"Skipping result with missing URL: {title}")
                continue

            if is_obviously_irrelevant(title, summary, url):
                print(f"Skipping irrelevant result: {title} | {url}")
                continue

            print(f"Keeping result: {title} | {url}")

            try:
                leads.append(
                    LeadCreate(
                        company_name=clean_company_name(title),
                        website_url=url,
                        category=request.category,
                        description=summary,
                        source="Exa.ai Neural Search",
                    )
                )
            except Exception as validation_error:
                print(f"Skipping invalid result: {title} | {url} | Error: {validation_error}")

    except Exception as e:
        print(f"Exa search failed: {e}")

    return leads