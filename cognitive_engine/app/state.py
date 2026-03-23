from __future__ import annotations

from datetime import datetime, timezone

from .contracts import (
    AudioFeatures,
    CognitiveChunk,
    CognitiveIntent,
    ProblemPayload,
    SessionLifecycle,
    SessionPhase,
    SessionState,
    TimelineMetrics,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


INTENT_TO_PHASE: dict[CognitiveIntent, SessionPhase] = {
    CognitiveIntent.PROBLEM_UNDERSTANDING: SessionPhase.UNDERSTANDING,
    CognitiveIntent.PARAMETER_RECOGNITION: SessionPhase.UNDERSTANDING,
    CognitiveIntent.STRATEGY_SELECTION: SessionPhase.STRATEGY,
    CognitiveIntent.EXECUTION_START: SessionPhase.EXECUTION,
    CognitiveIntent.DEVIATION: SessionPhase.STRATEGY,
    CognitiveIntent.SILENCE_REFLECTION: SessionPhase.REFLECTION,
    CognitiveIntent.UNKNOWN: SessionPhase.UNKNOWN,
}


def default_problem_payload() -> ProblemPayload:
    return ProblemPayload(
        raw_text="A triangle has side lengths 13 cm, 14 cm, and 15 cm. Find its area, and decide which method gives the cleanest path to the answer.",
        structured_representation={
            "concept": "triangle_area",
            "valid_methods": ["Heron", "Base-Height"],
            "optimal": "Heron",
        },
        valid_methods=["Heron", "Base-Height"],
        optimal_method="Heron",
    )


def make_session_state(session_id: str, problem_payload: ProblemPayload) -> SessionState:
    return SessionState(
        session_id=session_id,
        lifecycle_state=SessionLifecycle.INITIALIZING,
        phase=SessionPhase.UNDERSTANDING,
        problem_payload=problem_payload,
        metrics={
            "understanding_time_seconds": 0.0,
            "strategy_delay_seconds": 0.0,
            "deviation_time_seconds": 0.0,
            "execution_time_seconds": 0.0,
            "decision_efficiency_score": 0.0,
        },
    )


def infer_audio_features(features: AudioFeatures | dict | None) -> AudioFeatures:
    if features is None:
        return AudioFeatures()
    if isinstance(features, AudioFeatures):
        return features
    return AudioFeatures.model_validate(features)


def classify_intent(features: AudioFeatures, transcript_hint: str | None) -> tuple[CognitiveIntent, float]:
    transcript = (transcript_hint or "").lower()
    silence_ratio = features.silence_ratio or 0.0
    pause_before = features.pause_before_seconds or 0.0
    speech_density = features.speech_density or 0.0
    speech_energy = features.speech_energy or 0.0
    trailing_silence = float(features.extra.get("trailing_silence_seconds", 0.0))
    voiced_frames = float(features.extra.get("voiced_frames_ratio", speech_density))

    if silence_ratio >= 0.92 and voiced_frames <= 0.08 and max(pause_before, trailing_silence) >= 1.8:
        return CognitiveIntent.SILENCE_REFLECTION, 0.8
    if any(word in transcript for word in ["wrong", "confused", "trig", "trigonometry", "another method"]):
        return CognitiveIntent.DEVIATION, 0.74
    if any(word in transcript for word in ["use", "method", "strategy", "approach", "heron", "formula"]):
        return CognitiveIntent.STRATEGY_SELECTION, 0.83
    if any(word in transcript for word in ["calculate", "solve", "multiply", "subtract", "divide", "semiperimeter"]):
        return CognitiveIntent.EXECUTION_START, 0.81
    if any(word in transcript for word in ["given", "find", "triangle", "angle", "side", "radius"]):
        return CognitiveIntent.PARAMETER_RECOGNITION, 0.77
    if speech_density >= 0.18 and speech_energy >= 0.015:
        return CognitiveIntent.PROBLEM_UNDERSTANDING, 0.62
    if speech_density >= 0.1 and speech_energy >= 0.01:
        return CognitiveIntent.PROBLEM_UNDERSTANDING, 0.52
    return CognitiveIntent.UNKNOWN, 0.42


def build_chunk(
    chunk_id: str,
    start_time: float,
    end_time: float,
    features: AudioFeatures,
    transcript_hint: str | None,
) -> CognitiveChunk:
    try:
        intent, confidence = classify_intent(features, transcript_hint)
    except Exception:
        intent, confidence = CognitiveIntent.UNKNOWN, 0.2
    latency = max(features.pause_before_seconds or 0.0, 0.0)
    return CognitiveChunk(
        chunk_id=chunk_id,
        timestamp={"start_time": start_time, "end_time": end_time},
        audio_features=features,
        intent=intent,
        confidence=confidence,
        latency_seconds=latency,
        transcript_excerpt=transcript_hint,
    )


def should_transition_to_solving(chunk: CognitiveChunk) -> bool:
    trailing_silence = float(chunk.audio_features.extra.get("trailing_silence_seconds", 0.0))
    speech_density = chunk.audio_features.speech_density or 0.0
    return (
        chunk.intent == CognitiveIntent.SILENCE_REFLECTION
        and speech_density <= 0.08
        and (trailing_silence >= 2.5 or (chunk.audio_features.pause_before_seconds or 0.0) >= 2.5)
    )


def build_timeline_metrics(state: SessionState) -> TimelineMetrics:
    understanding = 0.0
    strategy = 0.0
    deviation = 0.0
    execution = 0.0

    for chunk in state.chunks:
        duration = chunk.timestamp.end_time - chunk.timestamp.start_time
        if chunk.intent in {CognitiveIntent.PROBLEM_UNDERSTANDING, CognitiveIntent.PARAMETER_RECOGNITION}:
            understanding += duration
        elif chunk.intent == CognitiveIntent.STRATEGY_SELECTION:
            strategy += duration
        elif chunk.intent == CognitiveIntent.DEVIATION:
            deviation += duration
        elif chunk.intent == CognitiveIntent.EXECUTION_START:
            execution += duration

    denominator = understanding + strategy + deviation + execution
    efficiency = 0.0 if denominator == 0 else max(0.0, 100.0 - ((deviation + strategy) / denominator) * 100.0)
    return TimelineMetrics(
        understanding_time_seconds=round(understanding, 2),
        strategy_delay_seconds=round(strategy, 2),
        deviation_time_seconds=round(deviation, 2),
        execution_time_seconds=round(execution, 2),
        decision_efficiency_score=round(efficiency, 2),
    )
