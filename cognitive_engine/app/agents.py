from __future__ import annotations

import base64
import logging

from .context_engine import context_window_engine
from .contracts import (
    AcousticProfile,
    AgentDescriptor,
    AgentGraph,
    CognitiveChunk,
    CognitiveIntent,
    EngineEvent,
    EngineEventType,
    InterventionReason,
    IntentCertainty,
    LLMRefinementResult,
    ProblemPayload,
    SemanticIntentResult,
    SessionState,
    TranscriptResult,
    TranscriptSegment,
)
from .deepgram_client import transcription_client
from .llm_refiner import llm_refinement_client
from .problem_intelligence import problem_structuring_pipeline
from .problem_intelligence.concept_mapper import detect_concepts_from_text
from .semantic_rules import classify_semantic_intent
from .state import (
    apply_context_refinement,
    apply_llm_refinement,
    build_acoustic_profile,
    build_rule_chunk,
    normalize_frontend_features,
    should_transition_to_solving,
    should_transcribe,
)

logger = logging.getLogger("cognitive_engine.agents")


class ProblemStructuringAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.SESSION_STARTED:
            return []
        payload = ProblemPayload.model_validate(event.payload.get("problem_payload") or {})
        structure = await problem_structuring_pipeline.build(payload)
        logger.info(
            "Problem structured | session=%s domain=%s concepts=%s methods=%s optimal=%s",
            event.session_id,
            structure.domain or "general_math",
            ",".join(structure.concepts) if structure.concepts else "<none>",
            ",".join(method.name for method in structure.methods) if structure.methods else "<none>",
            ",".join(structure.optimal_path) if structure.optimal_path else "<none>",
        )
        return [
            EngineEvent(event_type=EngineEventType.PROBLEM_STRUCTURED, session_id=event.session_id, payload={"problem_structure": structure.model_dump(mode="json")}),
            EngineEvent(
                event_type=EngineEventType.TIMELINE_UPDATED,
                session_id=event.session_id,
                payload={
                    "category": "system",
                    "message": "Problem structure ready",
                    "detail": (
                        f"Domain: {structure.domain or 'general_math'}. "
                        f"Detected concepts: {', '.join(structure.concepts) if structure.concepts else 'none'}. "
                        f"Valid methods: {', '.join(method.name for method in structure.methods) if structure.methods else 'none'}. "
                        f"Optimal path: {', '.join(structure.optimal_path) if structure.optimal_path else 'undetermined'}."
                    ),
                    "at_seconds": 0.0,
                },
            ),
        ]


class AcousticFeatureAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.AUDIO_CHUNK_RECEIVED:
            return []
        payload = event.payload
        try:
            features = normalize_frontend_features(payload.get("frontend_features"))
            start_time = float(payload.get("start_time") or 0.0)
            end_time = float(payload.get("end_time") or 0.0)
            audio_blob = payload.get("audio_blob") or ""
            audio_bytes = base64.b64decode(audio_blob) if audio_blob else b""
            acoustic_profile = build_acoustic_profile(features, start_time, end_time)
            mime_type = str(features.extra.get("mime_type") or "application/octet-stream")
            audio_reference = transcription_client.maybe_store_audio(event.session_id, str(payload.get("chunk_id")), mime_type, audio_bytes)
        except Exception as exc:
            logger.exception("Acoustic profiling failed | session=%s chunk=%s error=%s", event.session_id, payload.get("chunk_id"), exc)
            return [EngineEvent(event_type=EngineEventType.AGENT_FAILED, session_id=event.session_id, payload={"agent": "acoustic_feature", "error": str(exc)})]

        logger.info(
            "Acoustic profile computed | session=%s chunk=%s window=%.2f-%.2f bytes=%s density=%.3f silence=%.3f hesitation=%.3f energy=%.3f",
            event.session_id,
            payload.get("chunk_id"),
            start_time,
            end_time,
            len(audio_bytes),
            acoustic_profile.speech_density,
            acoustic_profile.silence_ratio,
            acoustic_profile.hesitation_score,
            acoustic_profile.normalized_energy,
        )
        return [EngineEvent(event_type=EngineEventType.ACOUSTIC_PROFILE_COMPUTED, session_id=event.session_id, payload={**payload, "frontend_features": features.model_dump(mode="json"), "acoustic_profile": acoustic_profile.model_dump(mode="json"), "audio_reference": audio_reference, "audio_bytes": audio_bytes})]


class TranscriptionAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.ACOUSTIC_PROFILE_COMPUTED:
            return []
        payload = event.payload
        acoustic_profile = AcousticProfile.model_validate(payload.get("acoustic_profile") or {})
        should_run, skip_reason = should_transcribe(acoustic_profile)
        if not should_run:
            transcript_result = TranscriptResult(provider="deepgram", model=transcription_client.settings.model, skipped=True, skip_reason=skip_reason)
            logger.info("Transcription skipped | session=%s chunk=%s reason=%s", event.session_id, payload.get("chunk_id"), skip_reason)
        else:
            transcript_result = await transcription_client.transcribe_chunk(
                session_id=event.session_id,
                chunk_id=str(payload.get("chunk_id")),
                audio_bytes=payload.get("audio_bytes") or b"",
                mime_type=(payload.get("frontend_features") or {}).get("extra", {}).get("mime_type"),
            )

        sentence_events: list[EngineEvent] = []
        segments = transcript_result.segments or []
        if segments:
            chunk_start = float(payload.get("start_time") or 0.0)
            for index, segment in enumerate(segments, start=1):
                sentence_result = TranscriptResult(
                    transcript=segment.transcript,
                    confidence=segment.confidence,
                    words=segment.words,
                    segments=[segment],
                    provider=transcript_result.provider,
                    model=transcript_result.model,
                    skipped=transcript_result.skipped,
                    skip_reason=transcript_result.skip_reason,
                    error=transcript_result.error,
                )
                sentence_events.append(
                    EngineEvent(
                        event_type=EngineEventType.TRANSCRIPTION_COMPLETED,
                        session_id=event.session_id,
                        payload={
                            **payload,
                            "chunk_id": f"{payload.get('chunk_id')}_s{index}",
                            "parent_chunk_id": payload.get("chunk_id"),
                            "start_time": round(chunk_start + segment.start, 3),
                            "end_time": round(chunk_start + segment.end, 3),
                            "transcript_result": sentence_result.model_dump(mode="json"),
                            "audio_bytes": None,
                            "sentence_index": index,
                        },
                    )
                )
        else:
            sentence_events.append(EngineEvent(event_type=EngineEventType.TRANSCRIPTION_COMPLETED, session_id=event.session_id, payload={**payload, "transcript_result": transcript_result.model_dump(mode="json"), "audio_bytes": None, "sentence_index": 1}))

        logger.info(
            "Sentence segmentation complete | session=%s chunk=%s sentences=%s",
            event.session_id,
            payload.get("chunk_id"),
            len(sentence_events),
        )
        return sentence_events


class SemanticIntentAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.TRANSCRIPTION_COMPLETED:
            return []
        payload = event.payload
        transcript_result = TranscriptResult.model_validate(payload.get("transcript_result") or {})
        acoustic_profile = AcousticProfile.model_validate(payload.get("acoustic_profile") or {})
        semantic_result = classify_semantic_intent(transcript_result.transcript, acoustic_profile, session_state)
        logger.info(
            "Semantic intent inferred | session=%s chunk=%s intent=%s confidence=%.2f certainty=%s alignment=%.2f transcript=%s",
            event.session_id,
            payload.get("chunk_id"),
            semantic_result.intent.value,
            semantic_result.confidence,
            semantic_result.certainty.value,
            semantic_result.semantic_signals.problem_alignment_score,
            transcript_result.transcript if transcript_result.transcript else "<none>",
        )
        return [EngineEvent(event_type=EngineEventType.SEMANTIC_INTENT_INFERRED, session_id=event.session_id, payload={**payload, "semantic_result": semantic_result.model_dump(mode="json")})]


class RuleClassificationAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.SEMANTIC_INTENT_INFERRED:
            return []
        payload = event.payload
        transcript_result = TranscriptResult.model_validate(payload.get("transcript_result") or {})
        semantic_result = SemanticIntentResult.model_validate(payload.get("semantic_result") or {})
        acoustic_profile = AcousticProfile.model_validate(payload.get("acoustic_profile") or {})
        chunk = build_rule_chunk(
            chunk_id=str(payload.get("chunk_id")),
            start_time=float(payload.get("start_time") or 0.0),
            end_time=float(payload.get("end_time") or 0.0),
            acoustic_profile=acoustic_profile,
            transcript_result=transcript_result,
            semantic_result=semantic_result,
            audio_reference=payload.get("audio_reference"),
            previous_phase=session_state.phase,
        )
        return [EngineEvent(event_type=EngineEventType.RULE_INTENT_CLASSIFIED, session_id=event.session_id, payload={"chunk": chunk.model_dump(mode="json")})]


class ContextRefinementAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.RULE_INTENT_CLASSIFIED:
            return []
        raw_chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        context_result = context_window_engine.refine(current_chunk=raw_chunk, session_state=session_state)
        refined_chunk = apply_context_refinement(
            raw_chunk,
            refined_intent=context_result.refined_intent,
            confidence=context_result.confidence,
            certainty=context_result.certainty,
            trajectory=context_result.trajectory,
            deviation_flag=context_result.deviation_flag,
            exploration_valid=context_result.exploration_valid,
            ambiguity_score=context_result.ambiguity_score,
        )
        return [EngineEvent(event_type=EngineEventType.CONTEXT_REFINED, session_id=event.session_id, payload={"chunk": refined_chunk.model_dump(mode="json"), "context_result": context_result.model_dump(mode="json")})]


class LLMRefinementAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.CONTEXT_REFINED:
            return []
        chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        should_use_llm = chunk.certainty == IntentCertainty.AMBIGUOUS or chunk.ambiguity_score >= 0.55
        llm_result = LLMRefinementResult(used=False)
        final_chunk = chunk
        if should_use_llm:
            llm_result = await llm_refinement_client.refine(current_chunk=chunk, session_state=session_state)
            if llm_result.used and llm_result.intent is not None:
                final_chunk = apply_llm_refinement(chunk, refined_intent=llm_result.intent, confidence=llm_result.confidence, certainty=llm_result.certainty, reason=llm_result.reason, used=True)
        return [EngineEvent(event_type=EngineEventType.LLM_REFINEMENT_COMPLETED, session_id=event.session_id, payload={"chunk": final_chunk.model_dump(mode="json"), "llm_result": llm_result.model_dump(mode="json")})]


class FinalIntentAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.LLM_REFINEMENT_COMPLETED:
            return []
        chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        return [EngineEvent(event_type=EngineEventType.INTENT_CLASSIFIED, session_id=event.session_id, payload={"chunk": chunk.model_dump(mode="json")})]


class TimelineEngineAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.INTENT_CLASSIFIED:
            return []
        chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        mapped = {
            CognitiveIntent.PROBLEM_UNDERSTANDING: ("understanding", "Understanding detected"),
            CognitiveIntent.PARAMETER_RECOGNITION: ("parameter", "Parameter recognition"),
            CognitiveIntent.CONCEPTUAL_EXPLANATION: ("understanding", "Conceptual explanation detected"),
            CognitiveIntent.WORKING_MEMORY_RETRIEVAL: ("understanding", "Recall sequence detected"),
            CognitiveIntent.STRATEGY_SELECTION: ("strategy", "Strategy identified"),
            CognitiveIntent.COMPARISON_ANALYSIS: ("strategy", "Method comparison detected"),
            CognitiveIntent.DEVIATION: ("deviation", "Deviation detected"),
            CognitiveIntent.EXECUTION_START: ("execution", "Execution started"),
            CognitiveIntent.VERIFICATION: ("execution", "Verification started"),
            CognitiveIntent.SOLUTION_SUMMARY: ("execution", "Solution summary detected"),
            CognitiveIntent.ERROR_CORRECTION: ("deviation", "Self-correction detected"),
            CognitiveIntent.META_COGNITION: ("delay", "Meta-cognitive reflection detected"),
            CognitiveIntent.STUCK_STATE: ("delay", "Stuck state detected"),
            CognitiveIntent.CONFIDENCE_EXPRESSION: ("signal", "Confidence expression detected"),
            CognitiveIntent.SILENCE_REFLECTION: ("delay", "Reflective silence detected"),
            CognitiveIntent.UNKNOWN: ("signal", "Signal received"),
        }
        category, message = mapped.get(chunk.intent_refined, ("signal", "Signal received"))
        detail = f"Raw intent: {chunk.intent_raw.value}. Refined intent: {chunk.intent_refined.value}. Certainty: {chunk.certainty.value}. Trajectory: {chunk.trajectory.value}."
        if session_state.problem_structure:
            detail += f" Domain: {session_state.problem_structure.domain or 'general_math'}."
            if session_state.problem_structure.optimal_path:
                detail += f" Optimal method: {', '.join(session_state.problem_structure.optimal_path)}."
        if chunk.semantic_signals.problem_keyword_hits:
            detail += f" Problem keywords matched: {', '.join(chunk.semantic_signals.problem_keyword_hits[:6])}."
        detail += f" Alignment score: {chunk.semantic_signals.problem_alignment_score:.2f}."
        if chunk.exploration_valid:
            detail += " The engine considers this productive exploration."
        if chunk.deviation_flag:
            detail += " Deviation has been confirmed by context and the problem method graph."
        if chunk.llm_used and chunk.llm_reason:
            detail += f" LLM refinement reason: {chunk.llm_reason}"
        if chunk.transcript:
            detail += f" Transcript: {chunk.transcript}"
        return [EngineEvent(event_type=EngineEventType.TIMELINE_UPDATED, session_id=event.session_id, payload={"category": category, "message": message, "detail": detail, "at_seconds": chunk.timestamp.end_time, "chunk_id": chunk.chunk_id, "intent": chunk.intent_refined.value, "transcript": chunk.transcript, "trajectory": chunk.trajectory.value, "certainty": chunk.certainty.value, "alignment_score": chunk.semantic_signals.problem_alignment_score})] + (
            [EngineEvent(event_type=EngineEventType.PHASE_TRANSITION_SUGGESTED, session_id=event.session_id, payload={"lifecycle_state": "solving", "reason": "trajectory_execution_commitment", "at_seconds": chunk.timestamp.end_time})]
            if should_transition_to_solving(chunk, session_state.lifecycle_state)
            else []
        )


class StrategyValidatorAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.INTENT_CLASSIFIED:
            return []
        chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        transcript = (chunk.transcript or "").lower().strip()
        signals = chunk.semantic_signals

        if not transcript or signals.filler_only:
            return []
        if len(transcript.split()) <= 2 and signals.problem_alignment_score < 0.2:
            return []
        if chunk.exploration_valid:
            return []
        if chunk.intent_refined not in {CognitiveIntent.DEVIATION, CognitiveIntent.UNKNOWN, CognitiveIntent.COMPARISON_ANALYSIS, CognitiveIntent.STUCK_STATE} and not chunk.deviation_flag:
            return []
        if signals.problem_alignment_score >= 0.32 or len(signals.problem_keyword_hits) >= 3:
            return []

        if not session_state.problem_structure:
            if not chunk.deviation_flag:
                return []
            reason = "contextual_deviation_without_problem_structure"
        else:
            valid_methods = {method.name.lower() for method in session_state.problem_structure.methods}
            method_keywords = {keyword.lower() for method in session_state.problem_structure.methods for keyword in method.keywords}
            mentioned_concepts = set(detect_concepts_from_text(transcript))
            allowed_concepts = set(session_state.problem_structure.concepts)
            mentions_valid_method = any(method in transcript for method in valid_methods)
            mentions_method_keyword = any(keyword in transcript for keyword in method_keywords)
            concept_mismatch = bool(mentioned_concepts and not mentioned_concepts.issubset(allowed_concepts))
            if mentions_valid_method or mentions_method_keyword:
                return []
            if not concept_mismatch and signals.problem_alignment_score >= 0.18 and len(signals.problem_keyword_hits) >= 2:
                return []
            reason = "outside_valid_method_graph" if concept_mismatch or signals.off_topic_markers else "low_alignment_with_problem_structure"

        wasted_time = max(chunk.timestamp.end_time - chunk.timestamp.start_time, 0.35)
        return [EngineEvent(event_type=EngineEventType.DEVIATION_DETECTED, session_id=event.session_id, payload={"reason": reason, "time_wasted_seconds": wasted_time, "at_seconds": chunk.timestamp.end_time, "chunk_id": chunk.chunk_id, "trajectory": chunk.trajectory.value, "certainty": chunk.certainty.value, "exploration_valid": chunk.exploration_valid, "transcript": chunk.transcript, "alignment_score": signals.problem_alignment_score})]


class InterventionAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.DEVIATION_DETECTED:
            return []
        if session_state.intervention_count >= 3 or bool(event.payload.get("exploration_valid", False)):
            return []
        transcript = (event.payload.get("transcript") or "").lower()
        if len(transcript.split()) <= 2:
            return []
        optimal = session_state.problem_structure.optimal_path[0] if session_state.problem_structure and session_state.problem_structure.optimal_path else None
        domain = session_state.problem_structure.domain if session_state.problem_structure else None
        alignment_score = float(event.payload.get("alignment_score", 0.0))
        if alignment_score >= 0.2:
            return []
        if optimal and domain == "geometry":
            message = f"Check the givens again. Which geometry method uses them most directly, and does {optimal} fit best?"
        elif optimal and domain == "algebra":
            message = f"Stay with the algebraic structure of the problem. Would {optimal} keep you closer to the given equations?"
        elif optimal and domain == "applied_math":
            message = f"Use the quantities in the problem directly. Does {optimal} connect the given values more directly than your current path?"
        elif optimal and domain == "arithmetic":
            message = f"Stay with the arithmetic relationship in the problem. Does {optimal} use the given percent, ratio, or value directly?"
        elif optimal and domain == "statistics":
            message = f"Focus on the quantities in the question. Which statistics method matches them most directly, and is {optimal} the cleaner route?"
        elif any(token in transcript for token in ["trigonometry", "sin", "cos", "tan"]):
            message = "Do the givens actually support trigonometry here, or is that outside the problem's valid method set?"
        else:
            message = "Pause and compare your current idea with the valid methods for this problem. Which one matches the givens most directly?"
        return [EngineEvent(event_type=EngineEventType.INTERVENTION_TRIGGERED, session_id=event.session_id, payload={"reason": InterventionReason.DEVIATION.value, "message": message, "at_seconds": event.payload.get("at_seconds", 0.0), "trajectory": event.payload.get("trajectory"), "certainty": event.payload.get("certainty")})]


class ReportGeneratorAgent:
    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.SESSION_ENDED:
            return []
        return [EngineEvent(event_type=EngineEventType.STATUS_UPDATED, session_id=event.session_id, payload={"status": "Session archived.", "at_seconds": event.payload.get("at_seconds", 0.0)})]


problem_structuring_agent = ProblemStructuringAgent()
acoustic_feature_agent = AcousticFeatureAgent()
transcription_agent = TranscriptionAgent()
semantic_intent_agent = SemanticIntentAgent()
rule_classification_agent = RuleClassificationAgent()
context_refinement_agent = ContextRefinementAgent()
llm_refinement_agent = LLMRefinementAgent()
final_intent_agent = FinalIntentAgent()
timeline_engine_agent = TimelineEngineAgent()
strategy_validator_agent = StrategyValidatorAgent()
intervention_agent = InterventionAgent()
report_generator_agent = ReportGeneratorAgent()


def build_agent_graph() -> AgentGraph:
    nodes = [
        AgentDescriptor(agent_id="problem_structuring", name="Problem Structuring Agent", role="Converts the raw problem into a domain-aware method graph, keyword bank, and symbolic structure at session start.", consumes=[EngineEventType.SESSION_STARTED.value], emits=[EngineEventType.PROBLEM_STRUCTURED.value, EngineEventType.TIMELINE_UPDATED.value]),
        AgentDescriptor(agent_id="acoustic_feature_engine", name="Acoustic Feature Engine", role="Normalizes frontend audio features and computes acoustic profiles.", consumes=[EngineEventType.AUDIO_CHUNK_RECEIVED.value], emits=[EngineEventType.ACOUSTIC_PROFILE_COMPUTED.value]),
        AgentDescriptor(agent_id="transcription_engine", name="Transcription Engine", role="Converts transport chunks into sentence-level transcript segments with precise timings.", consumes=[EngineEventType.ACOUSTIC_PROFILE_COMPUTED.value], emits=[EngineEventType.TRANSCRIPTION_COMPLETED.value]),
        AgentDescriptor(agent_id="semantic_intent_engine", name="Semantic Intent Engine", role="Scores each sentence against the active problem keyword bank and semantic rules.", consumes=[EngineEventType.TRANSCRIPTION_COMPLETED.value], emits=[EngineEventType.SEMANTIC_INTENT_INFERRED.value]),
        AgentDescriptor(agent_id="rule_classification_engine", name="Rule Classification Engine", role="Builds the initial sentence-level chunk with confidence and certainty.", consumes=[EngineEventType.SEMANTIC_INTENT_INFERRED.value], emits=[EngineEventType.RULE_INTENT_CLASSIFIED.value]),
        AgentDescriptor(agent_id="context_window_engine", name="Context Window Engine", role="Refines sentence-level intent using the last 3-5 chunks and detects trajectory.", consumes=[EngineEventType.RULE_INTENT_CLASSIFIED.value], emits=[EngineEventType.CONTEXT_REFINED.value]),
        AgentDescriptor(agent_id="llm_refinement_engine", name="LLM Refinement Engine", role="Handles rare ambiguous cases without blocking the fast path.", consumes=[EngineEventType.CONTEXT_REFINED.value], emits=[EngineEventType.LLM_REFINEMENT_COMPLETED.value]),
        AgentDescriptor(agent_id="final_intent_engine", name="Final Intent Engine", role="Publishes the final refined sentence-level cognitive chunk.", consumes=[EngineEventType.LLM_REFINEMENT_COMPLETED.value], emits=[EngineEventType.INTENT_CLASSIFIED.value]),
        AgentDescriptor(agent_id="timeline_engine", name="Timeline Engine", role="Converts refined chunks into explainable timeline updates.", consumes=[EngineEventType.INTENT_CLASSIFIED.value], emits=[EngineEventType.TIMELINE_UPDATED.value, EngineEventType.PHASE_TRANSITION_SUGGESTED.value]),
        AgentDescriptor(agent_id="strategy_validator", name="Strategy Validator", role="Confirms deviation against the active problem graph while ignoring filler sentences.", consumes=[EngineEventType.INTENT_CLASSIFIED.value], emits=[EngineEventType.DEVIATION_DETECTED.value]),
        AgentDescriptor(agent_id="intervention_agent", name="Intervention Agent", role="Triggers domain-aware interventions only when low-alignment drift is real.", consumes=[EngineEventType.DEVIATION_DETECTED.value], emits=[EngineEventType.INTERVENTION_TRIGGERED.value]),
        AgentDescriptor(agent_id="report_generator", name="Report Generator", role="Finalizes post-session analytics and archive status.", consumes=[EngineEventType.SESSION_ENDED.value], emits=[EngineEventType.STATUS_UPDATED.value]),
    ]
    edges = [
        {"from": "problem_structuring", "to": "strategy_validator"},
        {"from": "problem_structuring", "to": "intervention_agent"},
        {"from": "acoustic_feature_engine", "to": "transcription_engine"},
        {"from": "transcription_engine", "to": "semantic_intent_engine"},
        {"from": "semantic_intent_engine", "to": "rule_classification_engine"},
        {"from": "rule_classification_engine", "to": "context_window_engine"},
        {"from": "context_window_engine", "to": "llm_refinement_engine"},
        {"from": "llm_refinement_engine", "to": "final_intent_engine"},
        {"from": "final_intent_engine", "to": "timeline_engine"},
        {"from": "final_intent_engine", "to": "strategy_validator"},
        {"from": "strategy_validator", "to": "intervention_agent"},
        {"from": "timeline_engine", "to": "report_generator"},
    ]
    return AgentGraph(nodes=nodes, edges=edges)
