from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from .config import get_settings
from .contracts import TranscriptResult, TranscriptSegment, TranscriptWord
from .sentence_segmenter import segment_transcript_result

logger = logging.getLogger("cognitive_engine.deepgram")


class DeepgramTranscriptionClient:
    def __init__(self) -> None:
        self.settings = get_settings().deepgram
        self._cache: dict[str, TranscriptResult] = {}

    def is_configured(self) -> bool:
        return bool(self.settings.api_key)

    def maybe_store_audio(self, session_id: str, chunk_id: str, mime_type: str | None, audio_bytes: bytes) -> str | None:
        if not self.settings.store_audio_locally:
            return None
        suffix = ".webm"
        if mime_type:
            if "mp4" in mime_type:
                suffix = ".mp4"
            elif "wav" in mime_type:
                suffix = ".wav"
            elif "ogg" in mime_type:
                suffix = ".ogg"
        session_dir = self.settings.audio_storage_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        target = session_dir / f"{chunk_id}{suffix}"
        target.write_bytes(audio_bytes)
        return str(target)

    async def transcribe_chunk(
        self,
        *,
        session_id: str,
        chunk_id: str,
        audio_bytes: bytes,
        mime_type: str | None,
        keywords: list[str] | None = None,
    ) -> TranscriptResult:
        if not audio_bytes:
            return TranscriptResult(skipped=True, skip_reason="empty_audio_blob", provider="deepgram", model=self.settings.model)

        digest = hashlib.sha1(audio_bytes).hexdigest()
        if digest in self._cache:
            cached = self._cache[digest]
            logger.info("Deepgram cache hit | session=%s chunk=%s digest=%s", session_id, chunk_id, digest[:12])
            return cached

        if not self.is_configured():
            return TranscriptResult(
                provider="deepgram",
                model=self.settings.model,
                skipped=True,
                skip_reason="missing_api_key",
                error="DEEPGRAM_API_KEY is not configured.",
            )

        requested_keyword_boosting = self.settings.use_keywords or bool(keywords)
        try:
            payload = await self._request_transcription(
                audio_bytes=audio_bytes,
                mime_type=mime_type,
                use_keyword_boosting=requested_keyword_boosting,
                extra_keywords=keywords or [],
            )
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text if exc.response is not None else "<no body>"
            logger.warning(
                "Deepgram primary request failed | session=%s chunk=%s status=%s body=%s",
                session_id,
                chunk_id,
                exc.response.status_code if exc.response is not None else "<unknown>",
                response_text[:500],
            )
            if requested_keyword_boosting:
                try:
                    payload = await self._request_transcription(
                        audio_bytes=audio_bytes,
                        mime_type=mime_type,
                        use_keyword_boosting=False,
                        extra_keywords=[],
                    )
                    logger.info("Deepgram retry succeeded without keyword boosting | session=%s chunk=%s", session_id, chunk_id)
                except Exception as retry_exc:
                    logger.exception("Deepgram transcription retry failed | session=%s chunk=%s error=%s", session_id, chunk_id, retry_exc)
                    return TranscriptResult(provider="deepgram", model=self.settings.model, skipped=False, error=str(retry_exc))
            else:
                return TranscriptResult(provider="deepgram", model=self.settings.model, skipped=False, error=str(exc))
        except Exception as exc:
            logger.exception("Deepgram transcription failed | session=%s chunk=%s error=%s", session_id, chunk_id, exc)
            return TranscriptResult(provider="deepgram", model=self.settings.model, skipped=False, error=str(exc))

        transcript_result = self._parse_response(payload)
        self._cache[digest] = transcript_result
        logger.info(
            "Deepgram transcription complete | session=%s chunk=%s confidence=%.2f transcript=%s segments=%s",
            session_id,
            chunk_id,
            transcript_result.confidence,
            transcript_result.transcript if transcript_result.transcript else "<none>",
            len(transcript_result.segments),
        )
        return transcript_result

    async def _request_transcription(
        self,
        *,
        audio_bytes: bytes,
        mime_type: str | None,
        use_keyword_boosting: bool,
        extra_keywords: list[str],
    ) -> dict[str, Any]:
        params: list[tuple[str, Any]] = [
            ("model", self.settings.model),
            ("language", self.settings.language),
            ("smart_format", str(self.settings.smart_format).lower()),
            ("punctuate", str(self.settings.punctuate).lower()),
            ("utterances", str(self.settings.utterances).lower()),
            ("filler_words", str(self.settings.filler_words).lower()),
            ("diarize", str(self.settings.diarize).lower()),
        ]
        if use_keyword_boosting:
            merged_keywords = list(dict.fromkeys([*self.settings.keywords, *extra_keywords]))
            keyword_param = self._keyword_param_name()
            for keyword in merged_keywords[:20]:
                params.append((keyword_param, keyword))

        headers = {
            "Authorization": f"Token {self.settings.api_key}",
            "Content-Type": mime_type or "application/octet-stream",
        }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(
                self.settings.base_url,
                params=params,
                headers=headers,
                content=audio_bytes,
            )
            response.raise_for_status()
            return response.json()

    def _keyword_param_name(self) -> str:
        model_name = (self.settings.model or "").strip().lower()
        return "keyterm" if model_name.startswith("nova-3") else "keywords"

    def _parse_response(self, payload: dict[str, Any]) -> TranscriptResult:
        results = payload.get("results") or {}
        channels = results.get("channels") or []
        alternatives = channels[0].get("alternatives") if channels else []
        best = alternatives[0] if alternatives else {}
        transcript = (best.get("transcript") or "").strip() or None
        confidence = float(best.get("confidence") or 0.0)
        words = [
            TranscriptWord(
                word=item.get("word", ""),
                start=float(item.get("start") or 0.0),
                end=float(item.get("end") or 0.0),
                confidence=float(item.get("confidence")) if item.get("confidence") is not None else None,
            )
            for item in (best.get("words") or [])
            if item.get("word")
        ]
        segments = self._merge_short_utterances(self._parse_utterances(results.get("utterances") or []))
        result = TranscriptResult(
            transcript=transcript,
            confidence=confidence,
            words=words,
            segments=segments,
            provider="deepgram",
            model=self.settings.model,
            skipped=False,
        )
        if not result.segments:
            result = result.model_copy(update={"segments": segment_transcript_result(result)})
        return result

    def _parse_utterances(self, utterances: list[dict[str, Any]]) -> list[TranscriptSegment]:
        segments: list[TranscriptSegment] = []
        for index, utterance in enumerate(utterances, start=1):
            transcript = (utterance.get("transcript") or "").strip() or None
            utterance_words = [
                TranscriptWord(
                    word=item.get("word", ""),
                    start=float(item.get("start") or 0.0),
                    end=float(item.get("end") or 0.0),
                    confidence=float(item.get("confidence")) if item.get("confidence") is not None else None,
                )
                for item in (utterance.get("words") or [])
                if item.get("word")
            ]
            if not transcript and not utterance_words:
                continue
            start = float(utterance.get("start") or (utterance_words[0].start if utterance_words else 0.0))
            end = float(utterance.get("end") or (utterance_words[-1].end if utterance_words else start))
            confidence = float(utterance.get("confidence") or 0.0)
            segments.append(
                TranscriptSegment(
                    segment_id=f"utt_{index}",
                    transcript=transcript,
                    start=start,
                    end=end,
                    confidence=confidence,
                    words=utterance_words,
                )
            )
        return segments

    def _merge_short_utterances(self, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        if len(segments) <= 1:
            return segments

        merged: list[TranscriptSegment] = []
        index = 0
        while index < len(segments):
            current = segments[index]
            token_count = len((current.transcript or "").split())
            should_merge = token_count <= 1 or current.confidence < 0.25
            if should_merge and index + 1 < len(segments):
                nxt = segments[index + 1]
                merged_words = [*current.words, *nxt.words]
                merged_text = " ".join(part for part in [current.transcript, nxt.transcript] if part).strip()
                merged.append(
                    TranscriptSegment(
                        segment_id=f"{current.segment_id}_{nxt.segment_id}",
                        transcript=merged_text or current.transcript or nxt.transcript,
                        start=current.start,
                        end=nxt.end,
                        confidence=max(current.confidence, nxt.confidence),
                        words=merged_words,
                    )
                )
                index += 2
                continue

            merged.append(current)
            index += 1

        return merged


transcription_client = DeepgramTranscriptionClient()
