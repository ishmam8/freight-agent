import os
import asyncio
from dotenv import load_dotenv

import httpx

load_dotenv("/Users/macbook25/Work/projects/global-llc-agents/denim-agent-backend/.env")

async def test():
    GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    system_prompt = "Return valid JSON only. {\"test\": 1}"
    
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": '{"test": 1}'},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
        print("Status Code 8b:", response.status_code)
        
    payload["model"] = "llama-3.3-70b-versatile"
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
        print("Status Code 70b:", response.status_code)

if __name__ == "__main__":
    asyncio.run(test())
