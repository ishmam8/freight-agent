import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def strip_json_fence(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


async def gemini_web_extract(
    company_name: str,
    website_url: str,
    client: httpx.AsyncClient,
) -> dict:
    if not GEMINI_API_KEY:
        return {"founders": [], "emails": [], "sources": [], "error": "Missing GEMINI_API_KEY"}

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
        Only return email addresses explicitly shown in the grounded web material.
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

        Search the web for founder, owner, CEO, about, contact, and official pages.
        """

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "tools": [
            {"google_search": {}}
        ],
        "generationConfig": {
            "temperature": 0
        }
    }

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=45.0)
        print("STATUS:", response.status_code)
        print("RAW:", response.text[:4000])

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
            return {"founders": [], "emails": [], "sources": [], "error": "No text output"}

        clean_text = strip_json_fence(text_output)

        try:
            parsed = json.loads(clean_text)
        except Exception as e:
            return {
                "founders": [],
                "emails": [],
                "sources": [],
                "error": f"JSON parse failed: {e}",
                "raw_text": text_output,
                "clean_text": clean_text,
            }

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
                        "email": email.strip().lower(),
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
        return {"founders": [], "emails": [], "sources": [], "error": str(e)}


async def main():
    async with httpx.AsyncClient() as client:
        result = await gemini_web_extract(
            company_name="shop4studios",
            website_url="shop4studios.com",
            client=client,
        )

    print("\nPARSED RESULT:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())