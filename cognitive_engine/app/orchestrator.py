from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .agents import (
    acoustic_feature_agent,
    build_agent_graph,
    context_refinement_agent,
    final_intent_agent,
    intervention_agent,
    llm_refinement_agent,
    problem_structuring_agent,
    report_generator_agent,
    rule_classification_agent,
    semantic_intent_agent,
    strategy_validator_agent,
    timeline_engine_agent,
    transcription_agent,
)
from .contracts import (
    CognitiveChunk,
    DeviationAnalysis,
    EndSessionRequest,
    EndSessionResponse,
    EngineEvent,
    EngineEventType,
    GenerateReportResponse,
    ProblemStructure,
    SessionLifecycle,
    SessionPhase,
    SessionState,
    StartSessionRequest,
    StartSessionResponse,
    StrategyEvaluation,
    StreamAudioChunkRequest,
    StreamAudioChunkResponse,
    TimelineEvent,
    WebSocketEnvelope,
)
from .session_store import store
from .state import build_timeline_metrics, default_problem_payload, make_session_state, resolve_phase
from .ws_manager import ws_manager


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionOrchestrator:
    async def start_session(self, payload: StartSessionRequest) -> StartSessionResponse:
        session_id = f"session_{uuid4().hex}"
        session_token = f"token_{uuid4().hex}"
        problem_payload = payload.problem_payload or default_problem_payload()
        state = make_session_state(session_id, problem_payload)
        store.create(state)
        event = EngineEvent(event_type=EngineEventType.SESSION_STARTED, session_id=session_id, payload={"problem_payload": problem_payload.model_dump(mode="json")})

        async with store.get_lock(session_id):
            state = self._apply_event(state, event)
            for derived_event in await problem_structuring_agent.process(event, state):
                state = self._apply_event(state, derived_event)
                await self._dispatch_output(state, derived_event)
            state = self._transition_lifecycle(state, SessionLifecycle.ACTIVE)
            store.save(state)

        await self._dispatch_output(state, EngineEvent(event_type=EngineEventType.STATUS_UPDATED, session_id=session_id, payload={"status": "Listening..."}))
        await self._dispatch_phase(state)
        return StartSessionResponse(session_id=session_id, session_token=session_token, problem_payload=problem_payload, initial_state=state, agent_graph=build_agent_graph())

    async def stream_audio_chunk(self, payload: StreamAudioChunkRequest) -> StreamAudioChunkResponse:
        state = store.get(payload.session_id)
        if state is None:
            raise KeyError("Session not found.")
        if state.lifecycle_state in {SessionLifecycle.COMPLETED, SessionLifecycle.CLOSED}:
            raise ValueError("Session has already ended.")

        root_event = EngineEvent(event_type=EngineEventType.AUDIO_CHUNK_RECEIVED, session_id=payload.session_id, payload={"session_id": payload.session_id, "chunk_id": payload.chunk_id, "start_time": payload.time_range.start_time, "end_time": payload.time_range.end_time, "audio_blob": payload.audio_blob, "frontend_features": payload.frontend_features.model_dump(mode="json") if payload.frontend_features else {}, "transcript_hint": payload.transcript_hint})
        latest_chunk: CognitiveChunk | None = None
        intervention_recommended = False

        async with store.get_lock(payload.session_id):
            state = store.get(payload.session_id)
            if state is None:
                raise KeyError("Session not found.")
            await self._dispatch_output(state, EngineEvent(event_type=EngineEventType.STATUS_UPDATED, session_id=payload.session_id, payload={"status": "Analyzing..."}))

            acoustic_events = await acoustic_feature_agent.process(root_event, state)
            for acoustic_event in acoustic_events:
                for transcription_event in await transcription_agent.process(acoustic_event, state):
                    for semantic_event in await semantic_intent_agent.process(transcription_event, state):
                        for rule_event in await rule_classification_agent.process(semantic_event, state):
                            for context_event in await context_refinement_agent.process(rule_event, state):
                                for llm_event in await llm_refinement_agent.process(context_event, state):
                                    for final_event in await final_intent_agent.process(llm_event, state):
                                        state = self._apply_event(state, final_event)
                                        latest_chunk = CognitiveChunk.model_validate(final_event.payload["chunk"])

                                        for timeline_event in await timeline_engine_agent.process(final_event, state):
                                            if timeline_event.event_type == EngineEventType.PHASE_TRANSITION_SUGGESTED:
                                                lifecycle_name = timeline_event.payload.get("lifecycle_state")
                                                if lifecycle_name:
                                                    state = self._transition_lifecycle(state, SessionLifecycle(lifecycle_name))
                                                    await self._dispatch_phase(state)
                                                continue
                                            state = self._apply_event(state, timeline_event)
                                            await self._dispatch_output(state, timeline_event)

                                        for deviation_event in await strategy_validator_agent.process(final_event, state):
                                            state = self._apply_event(state, deviation_event)
                                            await self._dispatch_output(state, deviation_event)
                                            for intervention_event in await intervention_agent.process(deviation_event, state):
                                                state = self._apply_event(state, intervention_event)
                                                intervention_recommended = True
                                                await self._dispatch_output(state, intervention_event)

            store.save(state)

        await self._dispatch_output(state, EngineEvent(event_type=EngineEventType.STATUS_UPDATED, session_id=payload.session_id, payload={"status": "Listening..." if latest_chunk and latest_chunk.acoustic_profile.speech_density >= 0.16 else "Idle..."}))

        if latest_chunk is None:
            latest_chunk = CognitiveChunk.model_validate({
                "chunk_id": payload.chunk_id,
                "timestamp": payload.time_range.model_dump(),
                "intent": "unknown",
                "intent_raw": "unknown",
                "intent_refined": "unknown",
                "confidence": 0.0,
                "raw_confidence": 0.0,
                "refined_confidence": 0.0,
                "certainty": "ambiguous",
                "trajectory": "isolated_signal",
                "deviation_flag": False,
                "exploration_valid": False,
                "llm_used": False,
                "llm_reason": None,
                "ambiguity_score": 0.0,
                "keyword_strength": 0.0,
                "acoustic_profile": {},
                "transcript": payload.transcript_hint,
                "transcript_confidence": 0.0,
                "transcript_words": [],
                "semantic_signals": {},
                "latency_seconds": 0.0,
                "audio_reference": None,
                "created_at": utc_now(),
            })

        return StreamAudioChunkResponse(session_id=payload.session_id, chunk_id=payload.chunk_id, detected_intent=latest_chunk.intent_refined, confidence=latest_chunk.refined_confidence, certainty=latest_chunk.certainty, trajectory=latest_chunk.trajectory, llm_used=latest_chunk.llm_used, intervention_recommended=intervention_recommended, current_phase=state.phase, transcript_excerpt=latest_chunk.transcript, transcript_confidence=latest_chunk.transcript_confidence)

    async def manual_intervention(self, payload) -> tuple[SessionState, int]:
        state = store.get(payload.session_id)
        if state is None:
            raise KeyError("Session not found.")
        intervention_event = EngineEvent(event_type=EngineEventType.INTERVENTION_TRIGGERED, session_id=payload.session_id, payload={"reason": payload.trigger_reason.value, "message": payload.message, "at_seconds": float(len(state.timeline)), "intervention_id": payload.intervention_id})
        async with store.get_lock(payload.session_id):
            state = self._apply_event(state, intervention_event)
            store.save(state)
        await self._dispatch_output(state, intervention_event)
        return state, state.intervention_count

    async def end_session(self, payload: EndSessionRequest) -> EndSessionResponse:
        state = store.get(payload.session_id)
        if state is None:
            raise KeyError("Session not found.")
        event = EngineEvent(event_type=EngineEventType.SESSION_ENDED, session_id=payload.session_id, payload={"at_seconds": payload.final_timestamps.end_time, "image_reference": payload.image_reference})
        async with store.get_lock(payload.session_id):
            state = self._apply_event(state, event)
            state = self._transition_lifecycle(state, SessionLifecycle.COMPLETED)
            await self._dispatch_phase(state)
            for derived_event in await report_generator_agent.process(event, state):
                state = self._apply_event(state, derived_event)
                await self._dispatch_output(state, derived_event)
            state = self._transition_lifecycle(state, SessionLifecycle.CLOSED)
            state.closed_at = utc_now()
            state.updated_at = state.closed_at
            store.save(state)
        await self._dispatch_phase(state)
        return EndSessionResponse(session_id=payload.session_id, lifecycle_state=state.lifecycle_state, closed_at=state.closed_at or utc_now(), total_chunks=len(state.chunks), total_interventions=state.intervention_count)

    def generate_report(self, session_id: str) -> GenerateReportResponse:
        state = store.get(session_id)
        if state is None:
            raise KeyError("Session not found.")
        metrics = build_timeline_metrics(state)
        deviation_events = sum(1 for chunk in state.chunks if chunk.deviation_flag)
        llm_chunks = sum(1 for chunk in state.chunks if chunk.llm_used)
        exploration_chunks = sum(1 for chunk in state.chunks if chunk.exploration_valid)
        optimal_method = state.problem_structure.optimal_path[0] if state.problem_structure and state.problem_structure.optimal_path else None
        strategy_evaluation = StrategyEvaluation(
            strategy_status="phase_6_problem_structure_comparator",
            optimal_method=optimal_method,
            summary=f"The report is grounded in the problem method graph. {exploration_chunks} chunks were marked as productive exploration, and LLM refinement was used on {llm_chunks} chunks.",
        )
        deviation_analysis = DeviationAnalysis(
            deviation_score=round(state.deviation_score, 2),
            deviation_events=deviation_events,
            summary="Deviation remained low or exploratory." if deviation_events == 0 else "Deviation was confirmed only after contextual checks against the valid method graph.",
        )
        suggestions = [
            "Stay inside the valid method set identified for the problem before branching out.",
            "When multiple methods are valid, verbalize why one is more direct so the system can confirm productive exploration.",
            f"If you already have the givens for {optimal_method}, commit earlier to reduce strategy delay." if optimal_method else "Commit earlier once the strongest valid method is clear.",
        ]
        return GenerateReportResponse(session_id=session_id, timeline_metrics=metrics, deviation_analysis=deviation_analysis, strategy_evaluation=strategy_evaluation, improvement_suggestions=suggestions)

    async def send_snapshot(self, session_id: str) -> None:
        state = store.get(session_id)
        if state is None:
            return
        await ws_manager.broadcast(session_id, WebSocketEnvelope(type="session_snapshot", data={"session_id": state.session_id, "lifecycle_state": state.lifecycle_state.value, "phase": state.phase.value, "timeline": [item.model_dump(mode="json") for item in state.timeline], "metrics": state.metrics, "problem_structure": state.problem_structure.model_dump(mode="json") if state.problem_structure else None}))

    def _apply_event(self, state: SessionState, event: EngineEvent) -> SessionState:
        if event.event_type == EngineEventType.SESSION_STARTED:
            state.timeline.append(TimelineEvent(event_type=event.event_type.value, at_seconds=0.0, category="system", message="Session started", payload=event.payload))
        elif event.event_type == EngineEventType.PROBLEM_STRUCTURED:
            state.problem_structure = ProblemStructure.model_validate(event.payload["problem_structure"])
        elif event.event_type == EngineEventType.INTENT_CLASSIFIED:
            chunk = CognitiveChunk.model_validate(event.payload["chunk"])
            state.chunks.append(chunk)
            state.phase = resolve_phase(chunk)
        elif event.event_type == EngineEventType.TIMELINE_UPDATED:
            state.timeline.append(TimelineEvent(event_type=event.event_type.value, at_seconds=float(event.payload.get("at_seconds", 0.0)), category=event.payload.get("category", "signal"), message=event.payload.get("message", "Timeline updated"), payload=event.payload))
        elif event.event_type == EngineEventType.DEVIATION_DETECTED:
            state.deviation_score += float(event.payload.get("time_wasted_seconds", 0.0))
        elif event.event_type == EngineEventType.INTERVENTION_TRIGGERED:
            state.intervention_count += 1
            state.timeline.append(TimelineEvent(event_type=event.event_type.value, at_seconds=float(event.payload.get("at_seconds", 0.0)), category="intervention", message="Intervention triggered", payload=event.payload))
        elif event.event_type == EngineEventType.SESSION_ENDED:
            state.timeline.append(TimelineEvent(event_type=event.event_type.value, at_seconds=float(event.payload.get("at_seconds", 0.0)), category="system", message="Session ended", payload=event.payload))
        state.updated_at = utc_now()
        state.metrics = build_timeline_metrics(state).model_dump()
        return state

    def _transition_lifecycle(self, state: SessionState, lifecycle_state: SessionLifecycle) -> SessionState:
        state.lifecycle_state = lifecycle_state
        state.updated_at = utc_now()
        return state

    async def _dispatch_phase(self, state: SessionState) -> None:
        await ws_manager.broadcast(state.session_id, WebSocketEnvelope(type="phase_change", data={"session_id": state.session_id, "phase": state.phase.value, "lifecycle_state": state.lifecycle_state.value}))

    async def _dispatch_output(self, state: SessionState, event: EngineEvent) -> None:
        if event.event_type == EngineEventType.TIMELINE_UPDATED:
            await ws_manager.broadcast(state.session_id, WebSocketEnvelope(type="timeline_event", data={"message": event.payload.get("message", "Timeline updated"), "detail": event.payload.get("detail", ""), "timestamp": event.payload.get("at_seconds", 0.0), "category": event.payload.get("category", "signal"), "event_id": state.timeline[-1].event_id if state.timeline else None, "transcript": event.payload.get("transcript"), "trajectory": event.payload.get("trajectory"), "certainty": event.payload.get("certainty")}))
        elif event.event_type == EngineEventType.INTERVENTION_TRIGGERED:
            await ws_manager.broadcast(state.session_id, WebSocketEnvelope(type="intervention", data={"message": event.payload.get("message", "Intervention triggered"), "reason": event.payload.get("reason"), "timestamp": event.payload.get("at_seconds", 0.0)}))
        elif event.event_type == EngineEventType.STATUS_UPDATED:
            await ws_manager.broadcast(state.session_id, WebSocketEnvelope(type="status_update", data={"status": event.payload.get("status", "Idle...")}))


orchestrator = SessionOrchestrator()
