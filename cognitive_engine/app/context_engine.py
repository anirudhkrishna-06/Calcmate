from __future__ import annotations

from .contracts import (
    CognitiveChunk,
    CognitiveIntent,
    CognitiveTrajectory,
    ContextRefinementResult,
    IntentCertainty,
    SessionState,
)

WINDOW_SIZE = 5


class ContextWindowEngine:
    def refine(self, *, current_chunk: CognitiveChunk, session_state: SessionState) -> ContextRefinementResult:
        history = session_state.chunks[-(WINDOW_SIZE - 1):]
        window = [*history, current_chunk]
        intents = [chunk.intent_refined for chunk in window]
        notes: list[str] = []

        strategy_like = {CognitiveIntent.STRATEGY_SELECTION, CognitiveIntent.COMPARISON_ANALYSIS}
        deviation_like = {CognitiveIntent.DEVIATION, CognitiveIntent.STUCK_STATE}
        correction_like = {CognitiveIntent.ERROR_CORRECTION, CognitiveIntent.STRATEGY_SELECTION, CognitiveIntent.COMPARISON_ANALYSIS}

        strategy_count = sum(1 for intent in intents if intent in strategy_like)
        deviation_count = sum(1 for intent in intents if intent in deviation_like)
        correction_count = sum(1 for intent in intents if intent in correction_like)
        unknown_count = sum(1 for intent in intents if intent == CognitiveIntent.UNKNOWN)

        refined_intent = current_chunk.intent_raw
        confidence = current_chunk.raw_confidence
        trajectory = CognitiveTrajectory.ISOLATED_SIGNAL
        deviation_flag = False
        exploration_valid = False
        ambiguity_score = 0.0

        if strategy_count >= 2 and correction_count >= 2:
            trajectory = CognitiveTrajectory.EXPLORATION_CONVERGING
            exploration_valid = True
            refined_intent = CognitiveIntent.STRATEGY_SELECTION
            confidence = max(confidence, 0.84)
            notes.append("Multiple recent chunks explored methods and converged on a strategy.")
        elif strategy_count >= 2 and deviation_count >= 1:
            trajectory = CognitiveTrajectory.EXPLORATION_ACTIVE
            exploration_valid = True
            if current_chunk.intent_raw == CognitiveIntent.DEVIATION:
                refined_intent = CognitiveIntent.COMPARISON_ANALYSIS
                confidence = max(confidence, 0.71)
                notes.append("Potential deviation appears inside an active comparison window, so it is treated as exploration.")
            else:
                refined_intent = current_chunk.intent_raw if current_chunk.intent_raw != CognitiveIntent.UNKNOWN else CognitiveIntent.STRATEGY_SELECTION
                confidence = max(confidence, 0.76)
                notes.append("The recent window shows active strategy exploration rather than isolated drift.")
        elif deviation_count >= 2 and correction_count <= 1:
            trajectory = CognitiveTrajectory.DEVIATION_PERSISTENT
            deviation_flag = True
            refined_intent = CognitiveIntent.DEVIATION
            confidence = max(confidence, 0.84)
            notes.append("Deviation persisted across the recent context window without corrective reasoning.")
        elif current_chunk.intent_raw == CognitiveIntent.SILENCE_REFLECTION:
            if strategy_count >= 1 or correction_count >= 1:
                trajectory = CognitiveTrajectory.DEEP_REFLECTION
                confidence = max(confidence, 0.74)
                notes.append("Silence followed structured reasoning, so it is treated as deep reflection.")
            else:
                trajectory = CognitiveTrajectory.CONFUSION_BUILDING
                ambiguity_score += 0.2
                notes.append("Silence lacks recent semantic progress and may indicate confusion.")
        elif current_chunk.intent_raw == CognitiveIntent.EXECUTION_START and strategy_count >= 2:
            trajectory = CognitiveTrajectory.EXECUTION_COMMITMENT
            confidence = max(confidence, 0.82)
            notes.append("The recent window shows planning that now resolves into execution.")
        elif current_chunk.intent_raw == CognitiveIntent.UNKNOWN and strategy_count >= 2:
            trajectory = CognitiveTrajectory.EXPLORATION_CONVERGING
            exploration_valid = True
            refined_intent = CognitiveIntent.STRATEGY_SELECTION
            confidence = max(confidence, 0.7)
            ambiguity_score += 0.12
            notes.append("The current chunk is locally ambiguous, but the recent context strongly indicates strategy formation.")
        elif unknown_count >= 2 and current_chunk.acoustic_profile.hesitation_score >= 0.6:
            trajectory = CognitiveTrajectory.CONFUSION_BUILDING
            ambiguity_score += 0.28
            notes.append("Repeated ambiguity with hesitation suggests unresolved confusion.")
        else:
            trajectory = CognitiveTrajectory.STABLE_PROGRESS
            confidence = max(confidence, current_chunk.raw_confidence)
            notes.append("The current chunk is consistent with the recent reasoning trajectory.")

        if current_chunk.semantic_signals.uncertainty and not exploration_valid:
            ambiguity_score += 0.14
        if current_chunk.intent_raw == CognitiveIntent.UNKNOWN:
            ambiguity_score += 0.18
        if current_chunk.transcript_confidence < 0.65:
            ambiguity_score += 0.12
        if current_chunk.acoustic_profile.hesitation_score >= 0.7:
            ambiguity_score += 0.1
        if deviation_flag and exploration_valid:
            ambiguity_score += 0.2

        ambiguity_score = min(max(ambiguity_score, 0.0), 0.95)
        certainty = self._certainty_from(confidence=confidence, ambiguity_score=ambiguity_score)
        llm_recommended = ambiguity_score >= 0.55 or (current_chunk.intent_raw != refined_intent and confidence < 0.82)

        return ContextRefinementResult(
            refined_intent=refined_intent,
            confidence=round(min(max(confidence, 0.0), 0.98), 3),
            certainty=certainty,
            trajectory=trajectory,
            deviation_flag=deviation_flag,
            exploration_valid=exploration_valid,
            ambiguity_score=round(ambiguity_score, 3),
            llm_recommended=llm_recommended,
            notes=notes,
        )

    def _certainty_from(self, *, confidence: float, ambiguity_score: float) -> IntentCertainty:
        if confidence >= 0.8 and ambiguity_score <= 0.3:
            return IntentCertainty.STRONG
        if confidence >= 0.6 and ambiguity_score <= 0.58:
            return IntentCertainty.WEAK
        return IntentCertainty.AMBIGUOUS


context_window_engine = ContextWindowEngine()
