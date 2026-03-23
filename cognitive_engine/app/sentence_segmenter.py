from __future__ import annotations

from uuid import uuid4

from .contracts import TranscriptResult, TranscriptSegment, TranscriptWord

SENTENCE_ENDINGS = {".", "?", "!"}


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
    return segments
