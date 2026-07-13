import os
import json
import time
import asyncio
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, ValidationError
from flask import has_request_context
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.ai_call_log import AICallLog


def get_ai_client():
    """Return the configured AI client based on AI_PROVIDER env var."""
    provider = os.environ.get("AI_PROVIDER", "groq").lower()

    if provider == "openai":
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY", "")
        if key:
            key = key.strip('"').strip("'")
        return OpenAI(api_key=key), "openai"
    else:
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY", "")
        if key:
            key = key.strip('"').strip("'")
        return Groq(api_key=key), "groq"


def get_async_ai_client():
    """Return the configured Async AI client based on AI_PROVIDER env var."""
    provider = os.environ.get("AI_PROVIDER", "groq").lower()

    if provider == "openai":
        from openai import AsyncOpenAI
        key = os.environ.get("OPENAI_API_KEY", "")
        if key:
            key = key.strip('"').strip("'")
        return AsyncOpenAI(api_key=key), "openai"
    else:
        from groq import AsyncGroq
        key = os.environ.get("GROQ_API_KEY", "")
        if key:
            key = key.strip('"').strip("'")
        return AsyncGroq(api_key=key), "groq"


def get_model_name(provider: str) -> str:
    if provider == "openai":
        return "gpt-4o-mini"
    return "llama-3.3-70b-versatile"


def calculate_llm_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate token cost in USD."""
    # Prices per 1M tokens
    if "gpt-4o-mini" in model_name:
        input_rate = 0.150 / 1000000.0
        output_rate = 0.600 / 1000000.0
    else:
        # Defaults to llama-3.3-70b rates
        input_rate = 0.59 / 1000000.0
        output_rate = 0.79 / 1000000.0

    return (prompt_tokens * input_rate) + (completion_tokens * output_rate)


def _log_call(
    agent_name: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    status: str,
    error_msg: str = None
):
    """Log the AI completion to the database call logger."""
    if not has_request_context():
        return # Cannot write to SQLite db safely outside active request contexts without sessions

    try:
        user_id = None
        org_id = None
        
        try:
            current_user_id = get_jwt_identity()
            if current_user_id:
                user_id = current_user_id
                user = User.query.get(current_user_id)
                if user:
                    org_id = user.organization_id
        except Exception:
            pass

        cost = calculate_llm_cost(model_name, prompt_tokens, completion_tokens)
        
        log = AICallLog(
            user_id=user_id,
            organization_id=org_id,
            agent_name=agent_name,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            cost=cost,
            status=status,
            error_message=error_msg
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"[AI Observability Log Error]: {e}")


def chat_completion(
    system_prompt: str,
    user_prompt: str,
    agent_name: str = "UnknownAgent",
    temperature: float = 0.3,
    max_tokens: int = 1500,
) -> Optional[str]:
    """
    Unified chat completion call. Returns raw text response.
    Returns None on failure. Logs usage details.
    """
    start_time = time.time()
    provider_name = "unknown"
    model = "unknown"
    
    try:
        client, provider_name = get_ai_client()
        model = get_model_name(provider_name)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        latency = int((time.time() - start_time) * 1000)
        
        # Extract token usage metadata safely
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        
        result_text = response.choices[0].message.content
        
        # Log to Observability
        _log_call(
            agent_name=agent_name,
            model_name=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency,
            status="success"
        )
        
        return result_text
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        print(f"[AI Client] Error: {e}")
        _log_call(
            agent_name=agent_name,
            model_name=model,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=latency,
            status="failure",
            error_msg=str(e)
        )
        return None


async def async_chat_completion(
    system_prompt: str,
    user_prompt: str,
    agent_name: str = "UnknownAgent",
    temperature: float = 0.3,
    max_tokens: int = 1500,
) -> Optional[str]:
    """
    Asynchronous unified completion call.
    Logs usage details. Supports automatic retries with exponential backoff on rate limits
    and automatic failover to backup models/providers.
    """
    start_time = time.time()
    
    groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
    openai_models = ["gpt-4o-mini", "gpt-4o"]
    
    provider_pref = os.environ.get("AI_PROVIDER", "groq").lower()
    
    attempts_to_try = []
    if provider_pref == "openai" and os.environ.get("OPENAI_API_KEY"):
        for m in openai_models:
            attempts_to_try.append(("openai", m))
        if os.environ.get("GROQ_API_KEY"):
            for m in groq_models:
                attempts_to_try.append(("groq", m))
    else:
        if os.environ.get("GROQ_API_KEY"):
            for m in groq_models:
                attempts_to_try.append(("groq", m))
        if os.environ.get("OPENAI_API_KEY"):
            for m in openai_models:
                attempts_to_try.append(("openai", m))
                
    if not attempts_to_try:
        attempts_to_try.append((provider_pref, get_model_name(provider_pref)))

    for provider, model in attempts_to_try:
        max_retries = 2
        retry_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                if provider == "openai":
                    from openai import AsyncOpenAI
                    key = os.environ.get("OPENAI_API_KEY", "").strip('"').strip("'")
                    client = AsyncOpenAI(api_key=key)
                else:
                    from groq import AsyncGroq
                    key = os.environ.get("GROQ_API_KEY", "").strip('"').strip("'")
                    client = AsyncGroq(api_key=key)

                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                latency = int((time.time() - start_time) * 1000)
                usage = response.usage
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0
                
                result_text = response.choices[0].message.content
                
                _log_call(
                    agent_name=agent_name,
                    model_name=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency,
                    status="success"
                )
                
                return result_text
                
            except Exception as e:
                err_msg = str(e)
                is_rate_limit = "rate limit" in err_msg.lower() or "429" in err_msg or "rate_limit_exceeded" in err_msg
                
                if is_rate_limit and attempt < max_retries:
                    backoff_time = retry_delay * (2 ** attempt)
                    print(f"[AI Async Client] Rate limit hit for model {model}. Retrying in {backoff_time}s...")
                    await asyncio.sleep(backoff_time)
                    continue
                
                print(f"[AI Async Client] Model {model} failed: {err_msg}. Trying next backup model/provider...")
                break
                
    latency = int((time.time() - start_time) * 1000)
    _log_call(
        agent_name=agent_name,
        model_name="all-failed",
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=latency,
        status="failure",
        error_msg="All configured AI models and providers failed."
    )
    return None


def structured_json_completion(
    system_prompt: str,
    user_prompt: str,
    agent_name: str = "UnknownAgent",
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
        agent_name=agent_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if not raw:
        return None
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        return json.loads(cleaned)
    except Exception as e:
        print(f"[AI Client] JSON parse error: {e}\nRaw: {raw}")
        return None


async def async_structured_json_completion(
    system_prompt: str,
    user_prompt: str,
    agent_name: str = "UnknownAgent",
    temperature: float = 0.2,
    max_tokens: int = 1500,
) -> Optional[Dict[str, Any]]:
    """
    Asynchronous JSON completion call.
    """
    raw = await async_chat_completion(
        system_prompt=system_prompt + "\n\nYou MUST respond with valid JSON only. No extra text.",
        user_prompt=user_prompt,
        agent_name=agent_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if not raw:
        return None
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        return json.loads(cleaned)
    except Exception as e:
        print(f"[AI Async Client] JSON parse error: {e}\nRaw: {raw}")
        return None


async def async_guarded_json_completion(
    system_prompt: str,
    user_prompt: str,
    response_model: Type[BaseModel],
    agent_name: str = "UnknownAgent",
    temperature: float = 0.2,
    max_tokens: int = 1500,
    max_retries: int = 2
) -> Optional[Dict[str, Any]]:
    """
    Asynchronous JSON completion call with Pydantic Guardrails.
    """
    current_user_prompt = user_prompt
    
    for attempt in range(max_retries + 1):
        raw_json = await async_structured_json_completion(
            system_prompt=system_prompt,
            user_prompt=current_user_prompt,
            agent_name=agent_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not raw_json:
            return None
            
        try:
            # Enforce Guardrails
            validated = response_model.model_validate(raw_json)
            return validated.model_dump()
        except ValidationError as e:
            error_msg = f"Guardrail Validation Failed:\\n{e.json()}\\nPlease fix these errors and return valid JSON."
            print(f"[{agent_name}] Guardrail hit! Retrying (Attempt {attempt+1}/{max_retries})... Error: {e}")
            current_user_prompt += f"\\n\\nERROR ON PREVIOUS ATTEMPT:\\n{error_msg}"
            
    print(f"[{agent_name}] Failed to pass guardrails after {max_retries} attempts.")
    return None