import os
import asyncio
import httpx
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

async def test_hunter():
    if not HUNTER_API_KEY:
        print("ERROR: HUNTER_API_KEY is missing from your .env file!")
        return

    url = "https://api.hunter.io/v2/domain-search"
    
    # Hunter takes the API key in the URL parameters, not the headers
    params = {
        "domain": "searchandrescuedenim.com",
        "api_key": HUNTER_API_KEY,
        "limit": 10  # Keeping this low so we only burn 1 credit!
    }

    print(f"Pinging Hunter API for shelleyklassen.com...")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params)
        
        print(f"STATUS: {response.status_code}\n")
        
        if response.status_code == 200:
            data = response.json().get("data", {})
            
            # Print the high-level domain pattern info
            print("--- DOMAIN INFO ---")
            print(f"Pattern: {data.get('pattern')}")
            print(f"Total Emails Hunter knows about: {data.get('emails_count')}\n")
            
            # Print the actual people found
            print("--- PEOPLE FOUND ---")
            emails = data.get("emails", [])
            if not emails:
                print("No emails found for this domain.")
                
            for person in emails:
                name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                email = person.get("value")
                position = person.get("position", "No title")
                confidence = person.get("confidence")
                
                print(f"Name:  {name if name else 'Unknown'}")
                print(f"Title: {position}")
                print(f"Email: {email} (Confidence: {confidence}%)")
                print("-" * 30)
                
        else:
            print("ERROR RESPONSE:")
            print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(test_hunter())