from __future__ import annotations

import re
from uuid import uuid4

from .contracts import TranscriptResult, TranscriptSegment, TranscriptWord

SENTENCE_ENDINGS = {".", "?", "!"}
FILLER_TOKENS = {"um", "uh", "er", "ah", "hmm", "okay", "so", "well", "like"}
CONTINUATION_PREFIXES = (
    "and",
    "but",
    "so",
    "then",
    "because",
    "on looking",
    "looking at",
    "the values",
    "value given",
    "values given",
)
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


def segment_transcript_result(transcript_result: TranscriptResult) -> list[TranscriptSegment]:
    if transcript_result.segments:
        return transcript_result.segments

    words = transcript_result.words
    if not words:
        if transcript_result.transcript:
            return [
                TranscriptSegment(
                    segment_id=f"seg_{uuid4().hex[:10]}",
                    transcript=transcript_result.transcript,
                    start=0.0,
                    end=0.0,
                    confidence=transcript_result.confidence,
                    words=[],
                )
            ]
        return []

    segments: list[TranscriptSegment] = []
    current_words: list[TranscriptWord] = []

    def flush() -> None:
        nonlocal current_words
        if not current_words:
            return
        transcript = " ".join(word.word for word in current_words).strip()
        transcript = transcript.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
        confidence_values = [word.confidence for word in current_words if word.confidence is not None]
        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else transcript_result.confidence
        segments.append(
            TranscriptSegment(
                segment_id=f"seg_{uuid4().hex[:10]}",
                transcript=transcript,
                start=current_words[0].start,
                end=current_words[-1].end,
                confidence=float(confidence),
                words=list(current_words),
            )
        )
        current_words = []

    previous_end = words[0].start
    for word in words:
        current_words.append(word)
        gap = max(0.0, word.start - previous_end)
        previous_end = word.end
        token = word.word.strip()
        ends_sentence = any(token.endswith(ending) for ending in SENTENCE_ENDINGS)
        long_pause = gap >= 0.85 and len(current_words) >= 3
        if ends_sentence or long_pause:
            flush()

    flush()
    return merge_segments_into_thought_units(segments)


def merge_segments_into_thought_units(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    if len(segments) <= 1:
        return segments

    merged: list[TranscriptSegment] = []
    current: TranscriptSegment | None = None

    for segment in segments:
        if current is None:
            current = segment
            continue

        if _should_merge_segments(current, segment):
            current = _merge_pair(current, segment)
        else:
            merged.append(current)
            current = segment

    if current is not None:
        merged.append(current)
    return merged


def _should_merge_segments(left: TranscriptSegment, right: TranscriptSegment) -> bool:
    left_text = (left.transcript or "").strip().lower()
    right_text = (right.transcript or "").strip().lower()
    if not left_text or not right_text:
        return True

    gap = max(0.0, right.start - left.end)
    left_tokens = _tokens(left_text)
    right_tokens = _tokens(right_text)
    total_tokens = len(left_tokens) + len(right_tokens)

    left_fragment = _is_fragment(left_text, left_tokens)
    right_fragment = _is_fragment(right_text, right_tokens)
    numeric_fragment = _is_numeric_fragment(left_tokens) or _is_numeric_fragment(right_tokens)
    continuation = any(right_text.startswith(prefix) for prefix in CONTINUATION_PREFIXES)
    open_ended = not left_text.endswith((".", "?", "!"))

    if gap <= 0.95 and (left_fragment or right_fragment):
        return True
    if gap <= 0.75 and numeric_fragment:
        return True
    if gap <= 1.1 and continuation and open_ended:
        return True
    if gap <= 0.65 and total_tokens <= 8:
        return True
    return False


def _merge_pair(left: TranscriptSegment, right: TranscriptSegment) -> TranscriptSegment:
    transcript = " ".join(part for part in [left.transcript, right.transcript] if part).strip()
    transcript = transcript.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
    combined_words = [*left.words, *right.words]
    confidence_values = [value for value in [left.confidence, right.confidence] if value is not None]
    confidence = max(confidence_values) if confidence_values else 0.0
    return TranscriptSegment(
        segment_id=f"{left.segment_id}_{right.segment_id}",
        transcript=transcript,
        start=left.start,
        end=right.end,
        confidence=confidence,
        words=combined_words,
    )


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _is_numeric_fragment(tokens: list[str]) -> bool:
    if not tokens:
        return True
    digit_like = sum(1 for token in tokens if any(char.isdigit() for char in token))
    return digit_like >= max(1, len(tokens) - 1)


def _is_fragment(text: str, tokens: list[str]) -> bool:
    if not tokens:
        return True
    meaningful = [token for token in tokens if token not in FILLER_TOKENS]
    if len(meaningful) <= 1:
        return True
    if len(tokens) <= 3 and not text.endswith((".", "?", "!")):
        return True
    return False
