"""LLM client for any OpenAI-compatible server (vLLM serving N-ATLaS-LLM, or a hosted backup API).

Callers must handle LLMUnavailable and fall back to rules, so the service still works with LLM_BACKEND=mock.
"""
import json
import re
from typing import Any, Dict

import httpx

from app.config import settings


class LLMUnavailable(RuntimeError):
    pass


def _extract_json(text: str) -> Dict[str, Any]:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(text[start : end + 1])


async def chat_text(system: str, user: str, temperature: float = 0.0) -> str:
    if settings.llm_backend == "mock":
        raise LLMUnavailable("LLM_BACKEND=mock")
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    payload = {
        "model": settings.llm_model,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{settings.llm_base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise LLMUnavailable(f"LLM call failed: {exc}") from exc


async def chat_json(system: str, user: str, retries: int = 2) -> Dict[str, Any]:
    """Ask for a JSON object; retry with a stricter reminder if the output is not valid JSON."""
    last_error: Exception = ValueError("no attempt made")
    for _ in range(retries + 1):
        text = await chat_text(system, user)
        try:
            return _extract_json(text)
        except ValueError as exc:  # includes json.JSONDecodeError
            last_error = exc
            user = user + "\n\nReturn ONLY one valid JSON object and nothing else."
    raise LLMUnavailable(f"LLM did not return valid JSON: {last_error}")
