from __future__ import annotations

import json
import logging
from urllib.parse import urlparse

import httpx

from .config import get_settings

logger = logging.getLogger("cognitive_engine.local_llm")


def _safe_excerpt(text: str, limit: int = 280) -> str:
    return " ".join((text or "").split())[:limit]


def _candidate_models(configured_model: str) -> list[str]:
    candidates: list[str] = []
    for model in [configured_model, "qwen2.5:7b", "qwen2.5", "qwen3.5:397b-cloud"]:
        if model and model not in candidates:
            candidates.append(model)
    return candidates


def _endpoint_candidates(base_url: str) -> list[tuple[str, str]]:
    normalized = base_url.rstrip("/")
    parsed = urlparse(normalized)
    path = parsed.path.rstrip("/")
    root = normalized[: -len(path)] if path else normalized
    if path == "/v1":
        native_root = root
        openai_root = normalized
    else:
        native_root = normalized
        openai_root = f"{normalized}/v1"
    return [
        ("ollama_native", f"{native_root}/api/chat"),
        ("openai_compatible", f"{openai_root}/chat/completions"),
    ]


def _native_payload(model: str, messages: list[dict[str, str]], temperature: float) -> dict:
    return {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }


def _openai_payload(model: str, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> dict:
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }


def _extract_content(kind: str, data: dict) -> str:
    if kind == "ollama_native":
        return str((data.get("message") or {}).get("content", "")).strip()
    return str((data.get("choices") or [{}])[0].get("message", {}).get("content", "")).strip()


async def call_ollama(
    prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 512,
    system_prompt: str | None = None,
) -> tuple[str | None, str | None]:
    settings = get_settings().ollama
    if not settings.enabled:
        return None, "Ollama is disabled."

    base_url = settings.base_url.rstrip("/")
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    logger.info(
        "Ollama request starting | base_url=%s configured_model=%s prompt_chars=%d",
        base_url,
        settings.model,
        len(prompt),
    )

    last_error = "Ollama request did not produce a response."
    for kind, url in _endpoint_candidates(base_url):
        for model in _candidate_models(settings.model):
            payload = _native_payload(model, messages, temperature) if kind == "ollama_native" else _openai_payload(model, messages, temperature, max_tokens)
            headers = {"Content-Type": "application/json"}
            if kind == "openai_compatible":
                headers["Authorization"] = "Bearer ollama"
            try:
                logger.info(
                    "Ollama request prepared | kind=%s endpoint=%s model=%s payload=%s",
                    kind,
                    url,
                    model,
                    json.dumps(payload, ensure_ascii=True)[:1200],
                )
                async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                content = _extract_content(kind, data)
                if not content:
                    last_error = f"Ollama returned an empty response from {kind}."
                    logger.warning(
                        "Ollama response empty | kind=%s endpoint=%s model=%s body=%s",
                        kind,
                        url,
                        model,
                        _safe_excerpt(response.text),
                    )
                    continue
                logger.info(
                    "Ollama response generated | kind=%s endpoint=%s model=%s chars=%d preview=%s",
                    kind,
                    url,
                    model,
                    len(content),
                    _safe_excerpt(content),
                )
                return content, None
            except httpx.HTTPStatusError as exc:
                body = exc.response.text if exc.response is not None else ""
                last_error = (
                    f"Ollama {kind} endpoint failed with status "
                    f"{exc.response.status_code if exc.response is not None else 'unknown'}."
                )
                logger.warning(
                    "Ollama request failed | kind=%s endpoint=%s model=%s status=%s body=%s",
                    kind,
                    url,
                    model,
                    exc.response.status_code if exc.response is not None else "<unknown>",
                    _safe_excerpt(body),
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Ollama request failed | kind=%s endpoint=%s model=%s error=%s",
                    kind,
                    url,
                    model,
                    exc,
                )

    return None, last_error
