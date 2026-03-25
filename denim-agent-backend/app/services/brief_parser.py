import os
import json
import httpx
from pydantic import BaseModel, Field
from typing import List

class CampaignBriefSchema(BaseModel):
    target_audience: str = Field(description="Who is the campaign targeting?")
    banned_terms: List[str] = Field(description="Terms that disqualify a lead, based on user instructions like 'ignore X'.")
    buyer_titles: List[str] = Field(description="Titles of the ideal contacts to reach out to (e.g., 'Founder', 'VP of Sales', 'Director').")
    value_proposition: str = Field(description="The core value proposition or offering of the campaign.")
    exa_search_queries: List[str] = Field(description="Generate 3 to 5 optimized search queries for Exa.ai to find companies matching the target audience. Do not include search operators.")

async def parse_campaign_brief(prompt: str) -> CampaignBriefSchema:
    # --- MOCK MODE INTERCEPT ---
    if os.getenv("USE_MOCK_DATA") == "True":
        import asyncio
        await asyncio.sleep(1.5) # Simulate AI "thinking" for the UI
        
        # We must return the Pydantic schema your campaigns.py expects
        
        mock_data = {
            "target_audience": "B2B Logistics Companies in the UK",
            "banned_terms": ["consumer", "retail", "B2C"],
            "buyer_titles": ["Head of Supply Chain", "Operations Director"],
            "value_proposition": "We automate freight matching using AI.",
            "exa_search_queries": [
                "B2B logistics company UK", 
                "freight forwarding operations UK"
            ]
        }
        return CampaignBriefSchema(**mock_data)
    # --- END MOCK MODE ---

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from the environment. Cannot parse campaign brief.")
        
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    
    system_instruction = """
    You are a B2B campaign analysis AI. Extract key target audience and value proposition parameters from the user's prompt to generate a structured campaign brief.
    Return ONLY valid JSON matching this exact schema, without markdown formatting:
    {
      "target_audience": "string",
      "banned_terms": ["string"],
      "buyer_titles": ["string"],
      "value_proposition": "string",
      "exa_search_queries": ["string"]
    }
    """
    
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0, 
            "responseMimeType": "application/json"
        },
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
    text_output = ""
    candidates = data.get("candidates", [])
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if parts and "text" in parts[0]:
            text_output = parts[0]["text"]
            
    text_output = text_output.strip()
    if text_output.startswith("```json"):
        text_output = text_output[7:-3].strip()
    elif text_output.startswith("```"):
        text_output = text_output[3:-3].strip()
        
    parsed = json.loads(text_output)
    return CampaignBriefSchema(**parsed)
