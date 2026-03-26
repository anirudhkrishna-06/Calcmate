from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_engine.app.contracts import AcousticProfile, CognitiveChunk, CognitiveIntent, ProblemPayload, SemanticSignals
from cognitive_engine.app.state import build_phase_spans, make_session_state


def _chunk(chunk_id: str, intent: CognitiveIntent, transcript: str, start: float, end: float) -> CognitiveChunk:
    return CognitiveChunk.model_validate(
        {
            "chunk_id": chunk_id,
            "timestamp": {"start_time": start, "end_time": end},
            "intent": intent.value,
            "intent_raw": intent.value,
            "intent_refined": intent.value,
            "confidence": 0.82,
            "raw_confidence": 0.82,
            "refined_confidence": 0.82,
            "certainty": "weak",
            "trajectory": "stable_progress",
            "deviation_flag": False,
            "exploration_valid": False,
            "llm_used": False,
            "llm_reason": None,
            "ambiguity_score": 0.0,
            "keyword_strength": 0.4,
            "acoustic_profile": AcousticProfile().model_dump(mode="json"),
            "transcript": transcript,
            "transcript_confidence": 0.9,
            "transcript_words": [],
            "semantic_signals": SemanticSignals().model_dump(mode="json"),
            "latency_seconds": 0.0,
            "audio_reference": None,
        }
    )


def test_phase_spans_absorb_micro_chunks() -> None:
    state = make_session_state("session_spans", ProblemPayload(raw_text="Test"))
    state.chunks = [
        _chunk("c1", CognitiveIntent.PROBLEM_UNDERSTANDING, "we need to find the area", 0.0, 3.0),
        _chunk("c2", CognitiveIntent.PARAMETER_RECOGNITION, "2000", 3.1, 3.5),
        _chunk("c3", CognitiveIntent.PARAMETER_RECOGNITION, "the values given", 3.6, 5.0),
    ]

    spans = build_phase_spans(state)

    assert len(spans) == 1
    assert spans[0]["duration_seconds"] >= 5.0
