from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..config import get_settings

logger = logging.getLogger("cognitive_engine.problem_intelligence.gemini")


class GeminiProblemParser:
    def __init__(self) -> None:
        self.settings = get_settings().gemini

    def enabled(self) -> bool:
        return self.settings.enabled and bool(self.settings.api_key)

    async def parse(self, problem_text: str) -> dict[str, Any] | None:
        if not self.enabled():
            return None
        url = self.settings.base_url_template.format(model=self.settings.model)
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Extract a math problem into strict JSON with keys entities, goal, hints, parameters, constraints, keyword_bank. "
                                "keyword_bank must be a concise list of around 25 to 40 short math-relevant words or short phrases that a student would likely say while reasoning through this exact problem. "
                                "Return only JSON. Problem: " + problem_text
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.post(url, params={"key": self.settings.api_key}, json=body)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.exception("Gemini problem parse failed | error=%s", exc)
            return None

        text = self._extract_text(payload)
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                parsed = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        return parsed if isinstance(parsed, dict) else None

    def _extract_text(self, payload: dict[str, Any]) -> str | None:
        for candidate in payload.get("candidates", []):
            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                text = part.get("text")
                if text:
                    return text
        return None


gemini_problem_parser = GeminiProblemParser()
