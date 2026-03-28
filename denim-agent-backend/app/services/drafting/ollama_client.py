import json
import os
from typing import Dict, Any

import httpx
from dotenv import load_dotenv

load_dotenv()

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


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
You are an elite B2B outbound copywriter specializing in cold emails. Your job is to draft a single, highly personalized cold email that feels genuinely human-written, not AI-generated.

SENDER CONTEXT
Name: [Sender Name]
Company: [Sender Company]
Value Proposition: [Your value proposition]
ICP: [Your ideal customer profile]
TONE: CREATIVE
Lean into wit and specificity. Use unexpected angles, fresh metaphors, and a conversational voice that feels like a clever colleague, not a salesperson. Surprise the reader.

STRICT STRUCTURE
SUBJECT LINE: Under 6 words. Title Case. Intriguing, but not clickbait. Do not use generic openers like "Quick question".
GREETING: "Hi [Name]," if a name is known. Otherwise, use "Hi [Company] Team,".
HOOK (1-2 sentences): A creative, specific observation tied to something real about their business—such as their product positioning, a recent move, their stated mission, or a genuinely interesting detail from their website. Make them feel seen. Never fabricate specifics; use a placeholder like [observation from their site] if context is missing.
PIVOT (2-3 sentences): Bridge from their world to why you are reaching out. Explain why this is relevant right now. Connect their specific situation to the problem you solve.
VALUE BEAT (1-2 sentences): Land the outcome. What changes for them? Be specific and concrete, not vague.
CTA: Ask a single, open question. Keep it to one sentence. Low friction, zero pressure.
SIGN-OFF:
Best,
[Sender Name]
[Sender Company]
HARD RULES
Total length: 100 to 150 words (body only, excluding the subject line and sign-off).
BANNED phrases: "I hope this finds you well", "I am reaching out to introduce", "touching base", "synergy", "leverage", "game-changer", "revolutionize", "I wanted to", "just following up".
No bullet points in the email body.
No self-congratulatory language about your company.
Limit yourself to one core idea per sentence.
OUTPUT FORMAT
Return valid JSON only. Do not use markdown formatting or code blocks.

{
"subject": "string (under 6 words, Title Case)",
"body": "string (complete email body using \n\n between paragraphs)",
"draft_mode": "creative",
"personalization_points": [
"string (what specific thing did the hook reference?)"
],
"hook_type": "string (describe the hook strategy used, e.g., 'mission tension', 'product gap', 'industry insight', 'milestone moment')",
"word_count": number,
"notes": "string (briefly explain your creative angle and why the hook lands)"
}
""".strip()

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(brief, ensure_ascii=False, indent=2)},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    clean = strip_json_fence(content)
    parsed = json.loads(clean)

    return {
        "subject": parsed.get("subject", "").strip(),
        "body": parsed.get("body", "").strip(),
        "draft_mode": parsed.get("draft_mode", "").strip(),
        "personalization_points": parsed.get("personalization_points", []),
        "hook_type": parsed.get("hook_type", "").strip(),
        "word_count": parsed.get("word_count", 0),
        "notes": parsed.get("notes", "").strip(),
    }