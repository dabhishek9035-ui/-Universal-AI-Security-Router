"""LLM backends: local Ollama + any OpenAI-compatible API. Both via httpx."""
from __future__ import annotations

import time

import httpx

from .. import config


class LLMNotConfigured(Exception):
    pass


async def complete_local(prompt: str, system: str | None = None,
                         timeout: float = 60.0) -> dict:
    """Ollama /api/generate."""
    body: dict = {
        "model": config.LOCAL_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        body["system"] = system
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(f"{config.OLLAMA_BASE_URL}/api/generate", json=body)
            resp.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            # unreachable, wrong port, or wrong server version -> escalate to big
            raise LLMNotConfigured(
                f"Ollama not usable at {config.OLLAMA_BASE_URL}: {e}") from e
    data = resp.json()
    latency = (time.perf_counter() - start) * 1000
    return {
        "text": (data.get("response") or "").strip(),
        "model": config.LOCAL_MODEL,
        "backend": "ollama",
        "tier": "local",
        "latency_ms": round(latency, 1),
    }


async def complete_big(prompt: str, system: str | None = None,
                       timeout: float = 90.0) -> dict:
    """OpenAI-compatible /chat/completions."""
    if not config.OPENAI_API_KEY:
        raise LLMNotConfigured("OPENAI_API_KEY not set")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(
                f"{config.OPENAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                json={"model": config.BIG_MODEL, "messages": messages},
            )
            resp.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            raise LLMNotConfigured(f"big-model API error: {e}") from e
    data = resp.json()
    latency = (time.perf_counter() - start) * 1000
    return {
        "text": (data["choices"][0]["message"]["content"] or "").strip(),
        "model": config.BIG_MODEL,
        "backend": config.OPENAI_BASE_URL,
        "tier": "big",
        "latency_ms": round(latency, 1),
    }


async def complete(prompt: str, tier: str, system: str | None = None) -> dict:
    """Complete with the chosen tier; local failures escalate to big once."""
    if tier == "local":
        try:
            return await complete_local(prompt, system)
        except LLMNotConfigured:
            # escalation path: local unavailable -> big model
            return await complete_big(prompt, system)
    return await complete_big(prompt, system)
