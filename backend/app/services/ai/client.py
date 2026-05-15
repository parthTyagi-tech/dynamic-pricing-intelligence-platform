import os
import json
from typing import Any, Dict, Optional


def get_ai_client():
    """Return the configured AI client based on AI_PROVIDER env var."""
    provider = os.environ.get("AI_PROVIDER", "groq").lower()

    if provider == "openai":
        from openai import OpenAI
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY")), "openai"
    else:
        from groq import Groq
        return Groq(api_key=os.environ.get("GROQ_API_KEY")), "groq"


def get_model_name(provider: str) -> str:
    if provider == "openai":
        return "gpt-4o-mini"
    return "llama3-70b-8192"


def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1500,
) -> Optional[str]:
    """
    Unified chat completion call. Returns raw text response.
    Returns None on failure.
    """
    try:
        client, provider = get_ai_client()
        model = get_model_name(provider)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[AI Client] Error: {e}")
        return None


def structured_json_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1500,
) -> Optional[Dict[str, Any]]:
    """
    Chat completion that returns a parsed JSON dict.
    Falls back to None on failure.
    """
    raw = chat_completion(
        system_prompt=system_prompt + "\n\nYou MUST respond with valid JSON only. No extra text.",
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if not raw:
        return None
    try:
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        return json.loads(cleaned)
    except Exception as e:
        print(f"[AI Client] JSON parse error: {e}\nRaw: {raw}")
        return None