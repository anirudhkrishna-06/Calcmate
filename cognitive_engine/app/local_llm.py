from __future__ import annotations

import logging

import httpx

from .config import get_settings

logger = logging.getLogger("cognitive_engine.local_llm")


async def call_ollama(prompt: str, *, temperature: float = 0.1, max_tokens: int = 512, system_prompt: str | None = None) -> tuple[str | None, str | None]:
    settings = get_settings().ollama
    if not settings.enabled:
        return None, "Ollama is disabled."

    base_url = settings.base_url.rstrip("/")
    urls = [f"{base_url}/chat/completions"]
    if not base_url.endswith("/v1"):
        urls.append(f"{base_url}/v1/chat/completions")
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for url in urls:
        try:
            async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": "Bearer ollama"},
                    json={
                        "model": settings.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                response.raise_for_status()
                data = response.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content or not str(content).strip():
                last_error = "Ollama returned an empty response."
                continue

            logger.info("Ollama response generated | model=%s endpoint=%s", settings.model, url)
            return str(content).strip(), None
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Ollama request failed | endpoint=%s error=%s", url, exc)

    return None, last_error
