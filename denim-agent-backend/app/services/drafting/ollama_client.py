import json
import os
from typing import Dict, Any

import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")


def strip_json_fence(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


async def generate_draft_with_ollama(brief: Dict[str, Any]) -> Dict[str, Any]:
    # We unpack the brief to make it crystal clear to the model
    # Ensure your tasks.py passes 'scraped_context', 'contact_name', etc., into this brief dictionary!
    
    system_prompt = """
You are an elite B2B outbound copywriter. Your job is to draft a hyper-personalized, ultra-short cold email.

STRICT RULES:
1. LENGTH: Absolute maximum of 150 words. Shorter is better.
2. NO PLEASANTRIES: Never say "I hope this finds you well", "How are you", "My name is...", or "I am reaching out because".
3. THE HOOK: The first sentence MUST reference something specific from the company's website context (e.g., their specific niche, a feature they have, their mission).
4. THE PIVOT: The second sentence connects their context to our 'value_proposition'.
5. THE CTA: End with a low-friction, soft call to action (e.g., "Open to seeing how?", "Worth a chat?").
6. TONE: Casual, direct, peer-to-peer. No corporate jargon. Act like you are writing to a coworker.

Return valid JSON only in this exact shape:
{
  "subject": "string (Under 5 words, entirely lowercase, no punctuation)",
  "body": "string (The email body, using \n\n for paragraph breaks)",
  "draft_mode": "string (e.g., 'aggressive', 'soft', 'value-led')",
  "personalization_points": ["string (What specific thing did you reference in the hook?)"],
  "notes": "string (Why did you choose this angle?)"
}
""".strip()

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(brief, ensure_ascii=False, indent=2)},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.4 # Keep this low for strict formatting, but high enough for creative hooks
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

    content = data.get("message", {}).get("content", "")
    clean = strip_json_fence(content)
    parsed = json.loads(clean)

    return {
        "subject": parsed.get("subject", "").strip(),
        "body": parsed.get("body", "").strip(),
        "draft_mode": parsed.get("draft_mode", "").strip(),
        "personalization_points": parsed.get("personalization_points", []),
        "notes": parsed.get("notes", "").strip(),
    }