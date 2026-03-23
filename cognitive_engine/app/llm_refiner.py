from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .config import get_settings
from .contracts import CognitiveChunk, CognitiveIntent, IntentCertainty, LLMRefinementResult, SessionState

logger = logging.getLogger("cognitive_engine.llm")


class LLMRefinementClient:
    def __init__(self) -> None:
        self.settings = get_settings().llm

    def enabled(self) -> bool:
        return self.settings.enabled and bool(self.settings.api_key)

    async def refine(self, *, current_chunk: CognitiveChunk, session_state: SessionState) -> LLMRefinementResult:
        if not self.enabled():
            return LLMRefinementResult(used=False, error="LLM refinement disabled or missing OPENAI_API_KEY.")

        window = [chunk for chunk in session_state.chunks[-(self.settings.window_size - 1):] if chunk.transcript]
        window.append(current_chunk)
        transcripts = [
            {
                "chunk_id": chunk.chunk_id,
                "transcript": chunk.transcript,
                "intent": chunk.intent_refined.value,
                "trajectory": chunk.trajectory.value,
            }
            for chunk in window
            if chunk.transcript
        ]
        if not transcripts:
            return LLMRefinementResult(used=False, error="No transcript context available for LLM refinement.")

        prompt = {
            "problem": session_state.problem_payload.raw_text if session_state.problem_payload else None,
            "recent_chunks": transcripts,
            "current_raw_intent": current_chunk.intent_raw.value,
            "current_certainty": current_chunk.certainty.value,
            "current_trajectory": current_chunk.trajectory.value,
            "task": "Return only JSON with keys intent, confidence, certainty, reason. intent must be one of the known cognitive intents. No explanation outside JSON.",
        }

        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.settings.model,
            "input": json.dumps(prompt),
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.post(self.settings.base_url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException:
            logger.warning("LLM refinement timed out | chunk=%s", current_chunk.chunk_id)
            return LLMRefinementResult(used=False, timed_out=True, error="timeout")
        except Exception as exc:
            logger.exception("LLM refinement failed | chunk=%s error=%s", current_chunk.chunk_id, exc)
            return LLMRefinementResult(used=False, error=str(exc))

        text = self._extract_text(payload)
        if not text:
            return LLMRefinementResult(used=False, error="empty_llm_response")

        parsed = self._parse_json_block(text)
        if parsed is None:
            return LLMRefinementResult(used=False, error="invalid_llm_json")

        try:
            intent = CognitiveIntent(parsed.get("intent", current_chunk.intent_refined.value))
        except Exception:
            intent = current_chunk.intent_refined
        try:
            certainty = IntentCertainty(parsed.get("certainty", current_chunk.certainty.value))
        except Exception:
            certainty = current_chunk.certainty

        return LLMRefinementResult(
            intent=intent,
            confidence=float(parsed.get("confidence", current_chunk.refined_confidence)),
            certainty=certainty,
            reason=parsed.get("reason"),
            used=True,
        )

    def _extract_text(self, payload: dict[str, Any]) -> str | None:
        if isinstance(payload.get("output_text"), str) and payload.get("output_text"):
            return payload["output_text"]
        for item in payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    return text
        return None

    def _parse_json_block(self, text: str) -> dict[str, Any] | None:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    return None
            return None


llm_refinement_client = LLMRefinementClient()
