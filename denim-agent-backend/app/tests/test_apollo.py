import os
import asyncio
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")

async def organization_enrichment():
    # Using the standard enrichment endpoint
    url = "https://api.apollo.io/api/v1/organizations/enrich"
    
    headers = {
        "x-api-key": APOLLO_API_KEY,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    
    # Passing the domain in the payload
    payload = {
        "domain": "pisourcingltd.com"
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Some Apollo endpoints respond better to POST for enrichment
        response = await client.post(url, headers=headers, json=payload)
        
        print(f"STATUS: {response.status_code}")
        
        try:
            data = response.json()
            if response.status_code == 200:
                org = data.get("organization", {})
                print("--- COMPANY DATA FOUND ---")
                print(f"Name: {org.get('name')}")
                print(f"Website: {org.get('website_url')}")
                print(f"LinkedIn: {org.get('linkedin_url')}")
                print(f"Industry: {org.get('industry')}")
                print(f"Employee Count: {org.get('estimated_num_employees')}")
            else:
                print("ERROR DETAIL:", data)
        except Exception as e:
            print(f"Failed to parse JSON: {e}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(organization_enrichment())