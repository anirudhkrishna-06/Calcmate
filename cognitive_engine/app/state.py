from __future__ import annotations

from datetime import datetime, timezone

from .problem_intelligence import get_problem_payload_for_topic, get_random_problem_payload
from .contracts import (
    AcousticProfile,
    CognitiveChunk,
    CognitiveIntent,
    CognitiveTrajectory,
    FrontendAudioFeatures,
    IntentCertainty,
    ProblemPayload,
    SemanticIntentResult,
    SessionLifecycle,
    SessionPhase,
    SessionState,
    TimelineMetrics,
    TranscriptResult,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


INTENT_TO_PHASE: dict[CognitiveIntent, SessionPhase] = {
    CognitiveIntent.PROBLEM_UNDERSTANDING: SessionPhase.UNDERSTANDING,
    CognitiveIntent.PARAMETER_RECOGNITION: SessionPhase.UNDERSTANDING,
    CognitiveIntent.CONCEPTUAL_EXPLANATION: SessionPhase.UNDERSTANDING,
    CognitiveIntent.WORKING_MEMORY_RETRIEVAL: SessionPhase.UNDERSTANDING,
    CognitiveIntent.STRATEGY_SELECTION: SessionPhase.STRATEGY,
    CognitiveIntent.COMPARISON_ANALYSIS: SessionPhase.STRATEGY,
    CognitiveIntent.DEVIATION: SessionPhase.STRATEGY,
    CognitiveIntent.EXECUTION_START: SessionPhase.EXECUTION,
    CognitiveIntent.VERIFICATION: SessionPhase.EXECUTION,
    CognitiveIntent.SOLUTION_SUMMARY: SessionPhase.EXECUTION,
    CognitiveIntent.ERROR_CORRECTION: SessionPhase.REFLECTION,
    CognitiveIntent.META_COGNITION: SessionPhase.REFLECTION,
    CognitiveIntent.STUCK_STATE: SessionPhase.REFLECTION,
    CognitiveIntent.CONFIDENCE_EXPRESSION: SessionPhase.REFLECTION,
    CognitiveIntent.SILENCE_REFLECTION: SessionPhase.REFLECTION,
    CognitiveIntent.UNKNOWN: SessionPhase.UNKNOWN,
}


def default_problem_payload() -> ProblemPayload:
    return get_random_problem_payload()


def topic_problem_payload(topic: str | None) -> ProblemPayload:
    return get_problem_payload_for_topic(topic)


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
            "verification_time_seconds": 0.0,
            "decision_efficiency_score": 0.0,
        },
    )


def normalize_frontend_features(features: FrontendAudioFeatures | dict | None) -> FrontendAudioFeatures:
    if features is None:
        return FrontendAudioFeatures()
    if isinstance(features, FrontendAudioFeatures):
        return features
    return FrontendAudioFeatures.model_validate(features)


def build_acoustic_profile(features: FrontendAudioFeatures, start_time: float, end_time: float) -> AcousticProfile:
    duration = max(end_time - start_time, 0.01)
    speech_density = float(
        features.speech_ratio
        if features.speech_ratio is not None
        else features.speech_density
        if features.speech_density is not None
        else 0.0
    )
    speech_density = min(max(speech_density, 0.0), 1.0)
    silence_ratio = float(features.silence_ratio if features.silence_ratio is not None else features.extra.get("silence_ratio", max(0.0, 1.0 - speech_density)))
    silence_ratio = min(max(silence_ratio, 0.0), 1.0)
    leading_silence = float(features.leading_silence if features.leading_silence is not None else features.pause_before_seconds if features.pause_before_seconds is not None else 0.0)
    trailing_silence = float(features.trailing_silence or 0.0)
    rms_energy = float(features.rms_energy if features.rms_energy is not None else features.speech_energy if features.speech_energy is not None else 0.0)
    noise_floor = float(features.noise_floor or 0.0)
    voiced_frames = float(features.voiced_frames if features.voiced_frames is not None else speech_density)
    effective_speech_duration = max(duration * speech_density, 0.0)
    energy_variance = max(0.0, abs(float(features.extra.get("peak_energy", rms_energy)) - rms_energy))
    hesitation_score = min(
        1.0,
        max(
            0.0,
            (leading_silence * 0.22)
            + (trailing_silence * 0.18)
            + (silence_ratio * 0.38)
            + (max(0.0, 0.18 - speech_density) * 1.4)
            + (0.18 if rms_energy < max(noise_floor * 1.5, 0.012) else 0.0),
        ),
    )
    normalized_energy = 0.0 if rms_energy <= 0 else min(1.0, rms_energy / max(noise_floor + 0.02, 0.03))

    return AcousticProfile(
        effective_speech_duration=round(effective_speech_duration, 3),
        silence_ratio=round(silence_ratio, 3),
        speech_density=round(speech_density, 3),
        hesitation_score=round(hesitation_score, 3),
        energy_variance=round(energy_variance, 3),
        normalized_energy=round(normalized_energy, 3),
        pause_before_seconds=round(leading_silence, 2),
        leading_silence_seconds=round(leading_silence, 2),
        trailing_silence_seconds=round(trailing_silence, 2),
        voiced_frames_ratio=round(voiced_frames, 3),
        frontend_validated=True,
        raw_features=features.model_dump(mode="json"),
    )


def should_transcribe(acoustic_profile: AcousticProfile) -> tuple[bool, str | None]:
    if acoustic_profile.speech_density < 0.06 and acoustic_profile.effective_speech_duration < 0.35:
        return False, "low_speech_density"
    if acoustic_profile.silence_ratio > 0.985 and acoustic_profile.effective_speech_duration < 0.2 and acoustic_profile.normalized_energy < 0.42:
        return False, "mostly_silence"
    return True, None


def fallback_intent_from_acoustics(acoustic_profile: AcousticProfile, previous_phase: SessionPhase) -> tuple[CognitiveIntent, float, str]:
    if acoustic_profile.silence_ratio >= 0.975 and acoustic_profile.trailing_silence_seconds >= 2.8:
        return CognitiveIntent.SILENCE_REFLECTION, 0.76, "Acoustic silence pattern suggests reflective pause."
    if acoustic_profile.speech_density >= 0.62 and acoustic_profile.hesitation_score <= 0.28:
        return CognitiveIntent.PROBLEM_UNDERSTANDING, 0.58, "Speech was continuous but no semantic transcript was available."
    if previous_phase == SessionPhase.STRATEGY and acoustic_profile.trailing_silence_seconds >= 2.6:
        return CognitiveIntent.EXECUTION_START, 0.54, "Prior strategy phase followed by silence suggests execution onset."
    return CognitiveIntent.UNKNOWN, 0.35, "Acoustics alone were insufficient for a strong semantic classification."


def keyword_strength_from_semantics(semantic_result: SemanticIntentResult) -> float:
    signals = semantic_result.semantic_signals
    marker_count = (
        len(signals.strategy_markers)
        + len(signals.formula_references)
        + len(signals.parameter_markers)
        + len(signals.decision_markers)
        + len(signals.verification_markers)
        + len(signals.deviation_markers)
        + len(signals.problem_keyword_hits)
    )
    base = min(1.0, marker_count / 8)
    return round(min(1.0, base + (signals.problem_alignment_score * 0.35)), 3)


def certainty_from(*, confidence: float, transcript_confidence: float, acoustic_profile: AcousticProfile, keyword_strength: float) -> IntentCertainty:
    if confidence >= 0.8 and transcript_confidence >= 0.75 and keyword_strength >= 0.35 and acoustic_profile.hesitation_score <= 0.45:
        return IntentCertainty.STRONG
    if confidence >= 0.58 and transcript_confidence >= 0.45:
        return IntentCertainty.WEAK
    return IntentCertainty.AMBIGUOUS


def build_rule_chunk(
    *,
    chunk_id: str,
    start_time: float,
    end_time: float,
    acoustic_profile: AcousticProfile,
    transcript_result: TranscriptResult,
    semantic_result: SemanticIntentResult,
    audio_reference: str | None,
    previous_phase: SessionPhase,
) -> CognitiveChunk:
    transcript = transcript_result.transcript.strip() if transcript_result.transcript else None
    raw_intent = semantic_result.intent
    raw_confidence = semantic_result.confidence

    if raw_intent == CognitiveIntent.UNKNOWN:
        raw_intent, raw_confidence, _ = fallback_intent_from_acoustics(acoustic_profile, previous_phase)

    keyword_strength = keyword_strength_from_semantics(semantic_result)
    uncertainty_penalty = 0.12 if semantic_result.semantic_signals.uncertainty else 0.0
    decision_bonus = 0.08 if semantic_result.semantic_signals.decision else 0.0
    hesitation_penalty = acoustic_profile.hesitation_score * 0.18
    transcript_bonus = min(0.12, transcript_result.confidence * 0.12) if transcript else 0.0
    fused_confidence = raw_confidence + decision_bonus + transcript_bonus - uncertainty_penalty - hesitation_penalty

    if raw_intent == CognitiveIntent.SILENCE_REFLECTION:
        fused_confidence = max(fused_confidence, 0.72)
    if raw_intent == CognitiveIntent.DEVIATION and semantic_result.semantic_signals.deviation_markers:
        fused_confidence += 0.08
    if raw_intent == CognitiveIntent.STRATEGY_SELECTION and semantic_result.semantic_signals.formula_references:
        fused_confidence += 0.07

    fused_confidence = min(max(fused_confidence, 0.0), 0.98)
    certainty = certainty_from(
        confidence=fused_confidence,
        transcript_confidence=transcript_result.confidence,
        acoustic_profile=acoustic_profile,
        keyword_strength=keyword_strength,
    )
    latency = max(acoustic_profile.pause_before_seconds, acoustic_profile.trailing_silence_seconds, 0.0)

    return CognitiveChunk(
        chunk_id=chunk_id,
        timestamp={"start_time": start_time, "end_time": end_time},
        intent=raw_intent,
        intent_raw=raw_intent,
        intent_refined=raw_intent,
        confidence=round(fused_confidence, 3),
        raw_confidence=round(fused_confidence, 3),
        refined_confidence=round(fused_confidence, 3),
        certainty=certainty,
        trajectory=CognitiveTrajectory.ISOLATED_SIGNAL,
        deviation_flag=False,
        exploration_valid=False,
        llm_used=False,
        llm_reason=None,
        ambiguity_score=0.0,
        keyword_strength=keyword_strength,
        acoustic_profile=acoustic_profile,
        transcript=transcript,
        transcript_confidence=round(transcript_result.confidence, 3),
        transcript_words=transcript_result.words,
        semantic_signals=semantic_result.semantic_signals,
        latency_seconds=round(latency, 3),
        audio_reference=audio_reference,
    )


def apply_context_refinement(chunk: CognitiveChunk, *, refined_intent: CognitiveIntent, confidence: float, certainty: IntentCertainty, trajectory: CognitiveTrajectory, deviation_flag: bool, exploration_valid: bool, ambiguity_score: float) -> CognitiveChunk:
    return chunk.model_copy(update={
        "intent": refined_intent,
        "intent_refined": refined_intent,
        "confidence": round(confidence, 3),
        "refined_confidence": round(confidence, 3),
        "certainty": certainty,
        "trajectory": trajectory,
        "deviation_flag": deviation_flag,
        "exploration_valid": exploration_valid,
        "ambiguity_score": round(ambiguity_score, 3),
    })


def apply_llm_refinement(chunk: CognitiveChunk, *, refined_intent: CognitiveIntent | None, confidence: float | None, certainty: IntentCertainty | None, reason: str | None, used: bool) -> CognitiveChunk:
    intent_value = refined_intent or chunk.intent_refined
    confidence_value = chunk.refined_confidence if confidence is None else max(0.0, min(confidence, 0.98))
    certainty_value = certainty or chunk.certainty
    return chunk.model_copy(update={
        "intent": intent_value,
        "intent_refined": intent_value,
        "confidence": round(confidence_value, 3),
        "refined_confidence": round(confidence_value, 3),
        "certainty": certainty_value,
        "llm_used": used,
        "llm_reason": reason,
    })


def resolve_phase(chunk: CognitiveChunk) -> SessionPhase:
    if chunk.trajectory == CognitiveTrajectory.EXECUTION_COMMITMENT:
        return SessionPhase.EXECUTION
    if chunk.trajectory in {CognitiveTrajectory.CONFUSION_BUILDING, CognitiveTrajectory.DEEP_REFLECTION}:
        return SessionPhase.REFLECTION
    return INTENT_TO_PHASE.get(chunk.intent_refined, SessionPhase.UNKNOWN)


def should_transition_to_solving(chunk: CognitiveChunk, current_lifecycle: SessionLifecycle) -> bool:
    if current_lifecycle in {SessionLifecycle.COMPLETED, SessionLifecycle.CLOSED}:
        return False
    return (
        chunk.intent_refined in {CognitiveIntent.SILENCE_REFLECTION, CognitiveIntent.EXECUTION_START, CognitiveIntent.SOLUTION_SUMMARY}
        and chunk.acoustic_profile.speech_density <= 0.16
        and (
            chunk.acoustic_profile.trailing_silence_seconds >= 2.2
            or chunk.acoustic_profile.pause_before_seconds >= 2.2
            or chunk.trajectory == CognitiveTrajectory.EXECUTION_COMMITMENT
        )
    )


def build_timeline_metrics(state: SessionState) -> TimelineMetrics:
    understanding = 0.0
    strategy = 0.0
    deviation = 0.0
    execution = 0.0
    verification = 0.0

    for chunk in state.chunks:
        duration = chunk.timestamp.end_time - chunk.timestamp.start_time
        if chunk.intent_refined in {CognitiveIntent.PROBLEM_UNDERSTANDING, CognitiveIntent.PARAMETER_RECOGNITION, CognitiveIntent.CONCEPTUAL_EXPLANATION, CognitiveIntent.WORKING_MEMORY_RETRIEVAL}:
            understanding += duration
        elif chunk.intent_refined in {CognitiveIntent.STRATEGY_SELECTION, CognitiveIntent.COMPARISON_ANALYSIS}:
            strategy += duration
        elif chunk.deviation_flag or chunk.intent_refined in {CognitiveIntent.DEVIATION, CognitiveIntent.STUCK_STATE}:
            deviation += duration
        elif chunk.intent_refined in {CognitiveIntent.EXECUTION_START, CognitiveIntent.SOLUTION_SUMMARY, CognitiveIntent.ERROR_CORRECTION, CognitiveIntent.CONFIDENCE_EXPRESSION}:
            execution += duration
        elif chunk.intent_refined == CognitiveIntent.VERIFICATION:
            verification += duration

    denominator = understanding + strategy + deviation + execution + verification
    efficiency = 0.0 if denominator == 0 else max(0.0, 100.0 - ((deviation + strategy) / denominator) * 100.0)
    return TimelineMetrics(
        understanding_time_seconds=round(understanding, 2),
        strategy_delay_seconds=round(strategy, 2),
        deviation_time_seconds=round(deviation, 2),
        execution_time_seconds=round(execution, 2),
        verification_time_seconds=round(verification, 2),
        decision_efficiency_score=round(efficiency, 2),
    )

