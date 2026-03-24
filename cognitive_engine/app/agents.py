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
    DeviationType,
    EngineEvent,
    EngineEventType,
    InterventionReason,
    InterventionType,
    IntentCertainty,
    LLMRefinementResult,
    ProblemPayload,
    SemanticIntentResult,
    SessionState,
    SessionReport,
    TranscriptResult,
    TranscriptSegment,
    ValidationState,
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
from .strategy_validation.node_mapper import NodeMapper
from .strategy_validation.cognitive_path import CognitivePathEngine
from .strategy_validation.metrics import MetricsEngine
from .strategy_validation.validation_logger import validation_logger

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
    """Simplified timeline — emits clean, student-friendly labels.

    All technical details stay in backend logs only.
    The frontend sees simple, human-readable messages.
    """

    # Clean label mapping: intent → (category, friendly_message)
    _LABEL_MAP = {
        CognitiveIntent.PROBLEM_UNDERSTANDING: ("understanding", "Understanding the problem"),
        CognitiveIntent.PARAMETER_RECOGNITION: ("parameter", "Identifying values"),
        CognitiveIntent.CONCEPTUAL_EXPLANATION: ("understanding", "Good conceptual thinking"),
        CognitiveIntent.WORKING_MEMORY_RETRIEVAL: ("understanding", "Recalling relevant knowledge"),
        CognitiveIntent.STRATEGY_SELECTION: ("strategy", "Strategy identified"),
        CognitiveIntent.COMPARISON_ANALYSIS: ("strategy", "Comparing approaches"),
        CognitiveIntent.DEVIATION: ("deviation", "Exploring a different approach"),
        CognitiveIntent.EXECUTION_START: ("execution", "Starting to solve"),
        CognitiveIntent.VERIFICATION: ("execution", "Checking the answer"),
        CognitiveIntent.SOLUTION_SUMMARY: ("execution", "Wrapping up the solution"),
        CognitiveIntent.ERROR_CORRECTION: ("deviation", "Self-correction — good catch!"),
        CognitiveIntent.META_COGNITION: ("delay", "Reflecting on the approach"),
        CognitiveIntent.STUCK_STATE: ("delay", "Seems stuck — take a step back"),
        CognitiveIntent.CONFIDENCE_EXPRESSION: ("signal", "Feeling confident"),
        CognitiveIntent.SILENCE_REFLECTION: ("delay", "Taking a moment to think"),
        CognitiveIntent.UNKNOWN: ("signal", "Thinking..."),
    }

    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.INTENT_CLASSIFIED:
            return []
        chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        category, message = self._LABEL_MAP.get(chunk.intent_refined, ("signal", "Thinking..."))

        # Slightly adjust message based on context
        if chunk.intent_refined == CognitiveIntent.UNKNOWN and chunk.transcript:
            message = "Student observation"

        # Detail shows ONLY the transcript for frontend — keep it simple
        detail = f'"{chunk.transcript}"' if chunk.transcript else ""

        # Log technical detail to backend console only
        vs = session_state.validation_state
        logger.info(
            "Timeline event | session=%s chunk=%s category=%s message=%s | "
            "intent=%s certainty=%s trajectory=%s alignment=%.2f | "
            "v7_align=%.3f v7_dev=%.3f v7_progress=%.1f%%",
            event.session_id, chunk.chunk_id, category, message,
            chunk.intent_refined.value, chunk.certainty.value,
            chunk.trajectory.value, chunk.semantic_signals.problem_alignment_score,
            vs.path_alignment_score if vs.nodes_visited > 0 else 0.0,
            vs.deviation_score if vs.nodes_visited > 0 else 0.0,
            (vs.progress_ratio * 100) if vs.nodes_visited > 0 else 0.0,
        )

        return [EngineEvent(event_type=EngineEventType.TIMELINE_UPDATED, session_id=event.session_id, payload={"category": category, "message": message, "detail": detail, "at_seconds": chunk.timestamp.end_time, "chunk_id": chunk.chunk_id, "intent": chunk.intent_refined.value, "transcript": chunk.transcript, "trajectory": chunk.trajectory.value, "certainty": chunk.certainty.value, "alignment_score": chunk.semantic_signals.problem_alignment_score, "validation_alignment": vs.path_alignment_score if vs.nodes_visited > 0 else None, "progress_ratio": vs.progress_ratio if vs.nodes_visited > 0 else None})] + (
            [EngineEvent(event_type=EngineEventType.PHASE_TRANSITION_SUGGESTED, session_id=event.session_id, payload={"lifecycle_state": "solving", "reason": "trajectory_execution_commitment", "at_seconds": chunk.timestamp.end_time})]
            if should_transition_to_solving(chunk, session_state.lifecycle_state)
            else []
        )


class StrategyValidatorAgent:
    """Phase 7A — Graph-aware strategy validator.

    Maps each incoming chunk to a solution graph node, updates the
    cognitive path, computes all five quantitative metrics, and emits
    structured validation events.
    """

    def __init__(self) -> None:
        self._node_mapper = NodeMapper()
        self._path_engine = CognitivePathEngine()
        self._metrics_engine = MetricsEngine()

    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.INTENT_CLASSIFIED:
            return []

        chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        events: list[EngineEvent] = []

        # --- Guard: need solution graph for graph-based validation ----------
        if not session_state.solution_graph or not session_state.problem_structure:
            # Fall back to legacy deviation check
            return self._legacy_deviation_check(chunk, event, session_state)

        graph = session_state.solution_graph
        path = session_state.cognitive_path

        # 1. Map chunk → graph node
        path_node = self._node_mapper.map_chunk(
            chunk, graph, session_state.problem_structure
        )
        validation_logger.log_node_mapping(chunk, path_node, graph)

        # 2. Update cognitive path
        self._path_engine.add_node(path, path_node, graph)

        # 3. Compute validation metrics
        validation_state = self._metrics_engine.compute_validation_state(
            path, graph, session_start_time=0.0
        )
        session_state.validation_state = validation_state
        validation_logger.log_alignment_update(chunk.chunk_id, validation_state)

        at_seconds = chunk.timestamp.end_time

        # 4. Always emit PATH_UPDATE
        events.append(EngineEvent(
            event_type=EngineEventType.PATH_UPDATE,
            session_id=event.session_id,
            payload={
                "chunk_id": chunk.chunk_id,
                "mapped_node": path_node.node_label,
                "mapped_graph_id": path_node.mapped_graph_node_id,
                "is_on_graph": path_node.is_on_graph,
                "at_seconds": at_seconds,
                "path_length": len(path.nodes),
                "on_graph_count": path.on_graph_count(),
                "off_graph_count": path.off_graph_count(),
                "alignment_score": validation_state.path_alignment_score,
            },
        ))

        # 5. Emit VALIDATION_STATE_UPDATED
        events.append(EngineEvent(
            event_type=EngineEventType.VALIDATION_STATE_UPDATED,
            session_id=event.session_id,
            payload={
                "at_seconds": at_seconds,
                "validation_state": validation_state.model_dump(mode="json"),
            },
        ))

        # 6. Conditional events based on metric thresholds
        if validation_state.deviation_score >= 0.40:
            deviation_type = (
                DeviationType.HARD_DEVIATION.value
                if not path_node.is_on_graph
                else DeviationType.SOFT_DEVIATION.value
            )
            events.append(EngineEvent(
                event_type=EngineEventType.DEVIATION_DETECTED,
                session_id=event.session_id,
                payload={
                    "reason": deviation_type,
                    "deviation_score": validation_state.deviation_score,
                    "time_wasted_seconds": max(chunk.timestamp.end_time - chunk.timestamp.start_time, 0.35),
                    "at_seconds": at_seconds,
                    "chunk_id": chunk.chunk_id,
                    "trajectory": chunk.trajectory.value,
                    "certainty": chunk.certainty.value,
                    "exploration_valid": chunk.exploration_valid,
                    "transcript": chunk.transcript,
                    "alignment_score": validation_state.path_alignment_score,
                    "active_deviations": validation_state.active_deviations,
                },
            ))
            validation_logger.log_deviation_trigger(
                chunk.chunk_id, deviation_type,
                validation_state.deviation_score,
                validation_state.path_alignment_score,
                chunk.transcript,
            )

        if validation_state.delay_score >= 0.50:
            events.append(EngineEvent(
                event_type=EngineEventType.DELAY_DETECTED,
                session_id=event.session_id,
                payload={
                    "delay_score": validation_state.delay_score,
                    "at_seconds": at_seconds,
                    "chunk_id": chunk.chunk_id,
                    "message": "Delayed strategy selection detected — student has not reached key method steps",
                },
            ))
            validation_logger.log_delay_trigger(chunk.chunk_id, validation_state.delay_score)

        if validation_state.inefficiency_score >= 0.40:
            events.append(EngineEvent(
                event_type=EngineEventType.INEFFICIENCY_DETECTED,
                session_id=event.session_id,
                payload={
                    "inefficiency_score": validation_state.inefficiency_score,
                    "oscillation_index": validation_state.oscillation_index,
                    "at_seconds": at_seconds,
                    "chunk_id": chunk.chunk_id,
                    "message": "Inefficient method switching detected — excessive exploration without convergence",
                },
            ))
            validation_logger.log_inefficiency_trigger(
                chunk.chunk_id,
                validation_state.inefficiency_score,
                validation_state.oscillation_index,
            )

        if path_node.is_on_graph and validation_state.progress_ratio > 0:
            events.append(EngineEvent(
                event_type=EngineEventType.PATH_PROGRESS,
                session_id=event.session_id,
                payload={
                    "progress_ratio": validation_state.progress_ratio,
                    "at_seconds": at_seconds,
                    "chunk_id": chunk.chunk_id,
                    "mapped_node": path_node.node_label,
                    "message": f"Valid strategy progression — {validation_state.progress_ratio:.0%} through optimal path",
                },
            ))
            validation_logger.log_path_progress(
                chunk.chunk_id, path_node.node_label, validation_state.progress_ratio
            )

        # Log path snapshot periodically (every 5 chunks)
        if len(path.nodes) % 5 == 0:
            validation_logger.log_path_snapshot(event.session_id, path)

        return events

    # -----------------------------------------------------------------------
    # Legacy fallback (when no solution graph is available)
    # -----------------------------------------------------------------------

    def _legacy_deviation_check(
        self,
        chunk: CognitiveChunk,
        event: EngineEvent,
        session_state: SessionState,
    ) -> list[EngineEvent]:
        """Original Phase 6 deviation detection as a fallback."""
        transcript = (chunk.transcript or "").lower().strip()
        signals = chunk.semantic_signals

        if not transcript or signals.filler_only:
            return []
        if len(transcript.split()) <= 2 and signals.problem_alignment_score < 0.2:
            return []
        if chunk.exploration_valid:
            return []
        if chunk.intent_refined not in {
            CognitiveIntent.DEVIATION, CognitiveIntent.UNKNOWN,
            CognitiveIntent.COMPARISON_ANALYSIS, CognitiveIntent.STUCK_STATE,
        } and not chunk.deviation_flag:
            return []
        if signals.problem_alignment_score >= 0.32 or len(signals.problem_keyword_hits) >= 3:
            return []

        if not session_state.problem_structure:
            if not chunk.deviation_flag:
                return []
            reason = "contextual_deviation_without_problem_structure"
        else:
            valid_methods = {m.name.lower() for m in session_state.problem_structure.methods}
            method_keywords = {kw.lower() for m in session_state.problem_structure.methods for kw in m.keywords}
            mentioned_concepts = set(detect_concepts_from_text(transcript))
            allowed_concepts = set(session_state.problem_structure.concepts)
            if any(m in transcript for m in valid_methods) or any(kw in transcript for kw in method_keywords):
                return []
            concept_mismatch = bool(mentioned_concepts and not mentioned_concepts.issubset(allowed_concepts))
            if not concept_mismatch and signals.problem_alignment_score >= 0.18 and len(signals.problem_keyword_hits) >= 2:
                return []
            reason = "outside_valid_method_graph" if concept_mismatch or signals.off_topic_markers else "low_alignment_with_problem_structure"

        wasted_time = max(chunk.timestamp.end_time - chunk.timestamp.start_time, 0.35)
        return [EngineEvent(
            event_type=EngineEventType.DEVIATION_DETECTED,
            session_id=event.session_id,
            payload={
                "reason": reason,
                "time_wasted_seconds": wasted_time,
                "at_seconds": chunk.timestamp.end_time,
                "chunk_id": chunk.chunk_id,
                "trajectory": chunk.trajectory.value,
                "certainty": chunk.certainty.value,
                "exploration_valid": chunk.exploration_valid,
                "transcript": chunk.transcript,
                "alignment_score": signals.problem_alignment_score,
            },
        )]


class InterventionAgent:
    """Phase 8 — Real-time cognitive coach.

    Delivers minimal, high-precision, non-intrusive Socratic interventions.
    Strictly capped at 3 interventions per session.
    Uses a cooldown system + silence streak tracking.
    """

    MAX_INTERVENTIONS = 3
    COOLDOWN_SECONDS = 12.0  # Min seconds between interventions
    SILENCE_STREAK_THRESHOLD = 3  # Consecutive silence chunks before prompting

    def __init__(self) -> None:
        self._last_intervention_at: float = -999.0
        self._silence_streak: int = 0

    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        # Hard cap — never exceed max interventions
        if session_state.intervention_count >= self.MAX_INTERVENTIONS:
            return []

        at_seconds = float(event.payload.get("at_seconds", 0.0))

        # Cooldown — don't intervene too frequently
        if (at_seconds - self._last_intervention_at) < self.COOLDOWN_SECONDS:
            return []

        # Track silence
        if event.event_type == EngineEventType.DELAY_DETECTED:
            self._silence_streak += 1
        else:
            self._silence_streak = 0

        result: list[EngineEvent] = []

        if event.event_type == EngineEventType.DEVIATION_DETECTED:
            result = self._handle_deviation(event, session_state)
        elif event.event_type == EngineEventType.DELAY_DETECTED:
            result = self._handle_delay(event, session_state)
        elif event.event_type == EngineEventType.INEFFICIENCY_DETECTED:
            result = self._handle_inefficiency(event, session_state)

        if result:
            self._last_intervention_at = at_seconds
            self._silence_streak = 0

        return result

    # -----------------------------------------------------------------------
    # Socratic prompt templates (Layer 1 — fast, deterministic)
    # -----------------------------------------------------------------------

    def _get_context(self, session_state: SessionState) -> tuple[str | None, str | None]:
        """Extract optimal method and domain from session."""
        ps = session_state.problem_structure
        optimal = ps.optimal_path[0] if ps and ps.optimal_path else None
        domain = ps.domain if ps else None
        return optimal, domain

    def _handle_deviation(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if bool(event.payload.get("exploration_valid", False)):
            return []

        deviation_score = float(event.payload.get("deviation_score", 0.0))
        alignment_score = float(event.payload.get("alignment_score", 0.0))

        # Smarter threshold: only intervene on significant deviation with low alignment
        if deviation_score < 0.50 or alignment_score >= 0.25:
            return []

        transcript = (event.payload.get("transcript") or "").lower()
        if len(transcript.split()) <= 2:
            return []

        optimal, domain = self._get_context(session_state)

        # Domain-aware Socratic prompts
        if optimal and domain == "geometry":
            message = f"What values does the problem give you? Does {optimal} use them directly?"
        elif optimal and domain == "algebra":
            message = f"Look at the equation in the problem. Which method connects those variables?"
        elif optimal and domain == "applied_math":
            message = f"What quantities are given? Is there a formula that directly connects them?"
        elif optimal:
            message = f"What information does the problem give you? How does {optimal} use that information?"
        else:
            message = "What values are given in the problem? Which method uses them most directly?"

        return [EngineEvent(
            event_type=EngineEventType.INTERVENTION_TRIGGERED,
            session_id=event.session_id,
            payload={
                "reason": InterventionReason.DEVIATION.value,
                "intervention_type": InterventionType.REDIRECT.value,
                "message": message,
                "at_seconds": event.payload.get("at_seconds", 0.0),
            },
        )]

    def _handle_delay(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        delay_score = float(event.payload.get("delay_score", 0.0))

        # Only intervene on significant delay OR extended silence
        if delay_score < 0.60 and self._silence_streak < self.SILENCE_STREAK_THRESHOLD:
            return []

        optimal, domain = self._get_context(session_state)

        if self._silence_streak >= self.SILENCE_STREAK_THRESHOLD:
            # Long silence — gentle nudge
            if optimal:
                message = f"Take your time, but here's a hint: what formula connects the given quantities? Consider {optimal}."
            else:
                message = "What values are given in the problem? Try identifying what the question is asking for."
        elif optimal:
            message = f"You've been thinking for a while. Can you identify which formula uses the given values? Try {optimal}."
        else:
            message = "What is the problem asking you to find? What information do you already have?"

        return [EngineEvent(
            event_type=EngineEventType.INTERVENTION_TRIGGERED,
            session_id=event.session_id,
            payload={
                "reason": "delay",
                "intervention_type": InterventionType.PROMPT.value,
                "message": message,
                "at_seconds": event.payload.get("at_seconds", 0.0),
            },
        )]

    def _handle_inefficiency(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        inefficiency = float(event.payload.get("inefficiency_score", 0.0))
        oscillation = float(event.payload.get("oscillation_index", 0.0))

        if inefficiency < 0.45 and oscillation < 0.40:
            return []

        optimal, _ = self._get_context(session_state)

        if oscillation >= 0.40:
            message = f"You're switching between methods. Pick one{f' — try {optimal}' if optimal else ''} and follow it through step by step."
        else:
            message = f"You've explored enough. Commit to the method that best fits the given values{f' — {optimal} looks strong' if optimal else ''} and work through it."

        return [EngineEvent(
            event_type=EngineEventType.INTERVENTION_TRIGGERED,
            session_id=event.session_id,
            payload={
                "reason": "inefficiency",
                "intervention_type": InterventionType.HINT.value,
                "message": message,
                "at_seconds": event.payload.get("at_seconds", 0.0),
            },
        )]


class ReportGeneratorAgent:
    """Phase 9 — Generates intelligent session reports with Gemini-powered insights."""

    async def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.SESSION_ENDED:
            return []

        from .state import build_timeline_metrics

        vs = session_state.validation_state
        path = session_state.cognitive_path
        metrics = build_timeline_metrics(session_state)

        # Build thinking graph string from cognitive path
        thinking_graph = self._build_thinking_graph(path)

        # Generate Gemini-powered insight
        insight, improvement_rule = await self._generate_gemini_insight(
            session_state, thinking_graph, metrics, vs
        )

        report: dict = {
            "status": "Session archived.",
            "at_seconds": event.payload.get("at_seconds", 0.0),
            "total_chunks": len(session_state.chunks),
            "total_interventions": session_state.intervention_count,
            "thinking_graph": thinking_graph,
            "insight": insight,
            "improvement_rule": improvement_rule,
            "timeline_metrics": metrics.model_dump(mode="json"),
            "validation_state": vs.model_dump(mode="json") if vs else None,
        }

        logger.info(
            "Report generated | session=%s chunks=%d interventions=%d thinking_graph=%s",
            event.session_id, len(session_state.chunks),
            session_state.intervention_count, thinking_graph,
        )

        return [EngineEvent(
            event_type=EngineEventType.STATUS_UPDATED,
            session_id=event.session_id,
            payload=report,
        )]

    def _build_thinking_graph(self, path) -> str:
        """Build a readable thinking path string from the cognitive path."""
        if not path or not path.nodes:
            return "No cognitive path recorded."

        # Map node types to readable labels
        phase_labels = []
        seen = set()
        for node in path.nodes:
            if node.node_type == "off_graph":
                label = "exploring"
            elif node.node_type == "method":
                label = "strategy"
            elif node.node_type == "step":
                label = "execution"
            elif node.node_type == "equation":
                label = "applying formula"
            elif node.node_type == "concept":
                label = "understanding"
            elif node.intent.value == "silence_reflection":
                label = "reflection"
            elif node.intent.value == "error_correction":
                label = "correction"
            else:
                label = "thinking"

            # Avoid repeating consecutive labels
            if not phase_labels or phase_labels[-1] != label:
                phase_labels.append(label)

        return " → ".join(phase_labels)

    async def _generate_gemini_insight(
        self, session_state, thinking_graph: str, metrics, vs
    ) -> tuple[str, str]:
        """Use Gemini2 to generate a personalized insight and improvement rule."""
        from .config import get_settings
        settings = get_settings()
        api_key = settings.gemini2.api_key

        if not api_key:
            # Fallback: generate rule-based insight
            return self._fallback_insight(session_state, thinking_graph, vs)

        problem_text = session_state.problem_payload.raw_text if session_state.problem_payload else ""
        prompt = (
            f"A student just completed a math thinking session. Analyze their performance and give feedback.\n\n"
            f"Problem: {problem_text[:300]}\n\n"
            f"Thinking path: {thinking_graph}\n"
            f"Understanding time: {metrics.understanding_time_seconds:.1f}s\n"
            f"Strategy delay: {metrics.strategy_delay_seconds:.1f}s\n"
            f"Deviation time: {metrics.deviation_time_seconds:.1f}s\n"
            f"Execution time: {metrics.execution_time_seconds:.1f}s\n"
            f"Interventions needed: {session_state.intervention_count}\n"
            f"Alignment score: {vs.path_alignment_score:.2f}\n"
            f"Progress: {vs.progress_ratio:.0%}\n\n"
            f"Respond in EXACTLY this format (2 lines only):\n"
            f"INSIGHT: <1-2 sentence observation about their thinking process>\n"
            f"IMPROVE: <1 sentence actionable improvement suggestion>"
        )

        try:
            import httpx
            model = settings.gemini2.model
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

            async with httpx.AsyncClient(timeout=settings.gemini2.timeout_seconds) as client:
                response = await client.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 256},
                })
                response.raise_for_status()
                data = response.json()

            text = ""
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                text += part.get("text", "")

            # Parse response
            insight = ""
            improvement = ""
            for line in text.strip().split("\n"):
                if line.startswith("INSIGHT:"):
                    insight = line[len("INSIGHT:"):].strip()
                elif line.startswith("IMPROVE:"):
                    improvement = line[len("IMPROVE:"):].strip()

            if insight and improvement:
                logger.info("Gemini insight generated successfully")
                return insight, improvement

        except Exception as exc:
            logger.warning("Gemini insight generation failed | error=%s", exc)

        return self._fallback_insight(session_state, thinking_graph, vs)

    def _fallback_insight(self, session_state, thinking_graph: str, vs) -> tuple[str, str]:
        """Rule-based fallback when Gemini is unavailable."""
        if vs.progress_ratio >= 0.8:
            insight = "You made excellent progress through the solution, demonstrating strong problem-solving skills."
        elif vs.deviation_score >= 0.5:
            insight = "You explored multiple approaches but strayed from the optimal path. Focus on the given values before branching out."
        elif vs.delay_score >= 0.6:
            insight = "You took some time before committing to a strategy. Try identifying the key formula earlier."
        elif session_state.intervention_count >= 2:
            insight = "You needed some guidance during the session. Review the problem structure before starting next time."
        else:
            insight = "You showed a thoughtful approach to the problem. Keep building on your reasoning skills."

        optimal = session_state.problem_structure.optimal_path[0] if session_state.problem_structure and session_state.problem_structure.optimal_path else None
        if optimal and vs.delay_score >= 0.5:
            improvement = f"Try identifying {optimal} as the method earlier — look for the quantities that match its formula."
        elif vs.oscillation_index >= 0.3:
            improvement = "Commit to one method and follow it through before switching to another."
        elif vs.deviation_score >= 0.5:
            improvement = "Focus on the values given in the problem and choose the method that uses them most directly."
        else:
            improvement = "Continue thinking aloud clearly — your reasoning shows good analytical thinking."

        return insight, improvement


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
        AgentDescriptor(agent_id="strategy_validator", name="Strategy Validator", role="Phase 7A graph-aware validator: maps chunks to solution graph nodes, tracks cognitive path, computes deviation/delay/inefficiency/oscillation metrics.", consumes=[EngineEventType.INTENT_CLASSIFIED.value], emits=[EngineEventType.PATH_UPDATE.value, EngineEventType.DEVIATION_DETECTED.value, EngineEventType.DELAY_DETECTED.value, EngineEventType.INEFFICIENCY_DETECTED.value, EngineEventType.PATH_PROGRESS.value, EngineEventType.VALIDATION_STATE_UPDATED.value]),
        AgentDescriptor(agent_id="intervention_agent", name="Intervention Agent", role="Triggers domain-aware interventions based on deviation, delay, and inefficiency metrics.", consumes=[EngineEventType.DEVIATION_DETECTED.value, EngineEventType.DELAY_DETECTED.value, EngineEventType.INEFFICIENCY_DETECTED.value], emits=[EngineEventType.INTERVENTION_TRIGGERED.value]),
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
