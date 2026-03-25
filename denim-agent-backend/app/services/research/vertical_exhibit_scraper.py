import httpx
from bs4 import BeautifulSoup
from app.models.schemas import LeadCreate
from app.models.domain import LeadCategory

async def scrape_expo_directory(url: str) -> list[LeadCreate]:
    print(f"Triggering Vertical Scraper for: {url}")
    leads = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # Mock extraction
            mock_exhibitors = [
                {"name": "Grimwood Agencies", "url": "https://www.grimwoodagencies.com/"},
                {"name": "Gary Gates Sales", "url": "http://garygates.ca"}
            ]
            
            for ex in mock_exhibitors:
                leads.append(LeadCreate(
                    company_name=ex["name"],
                    website_url=ex["url"],
                    category=LeadCategory.EXPO_EXHIBITOR,
                    description="Extracted from Trade Show Exhibitor List",
                    source="In-House Vertical Scraper"
                ))
    except Exception as e:
        print(f"Scraping failed for {url}: {e}")
    return leads