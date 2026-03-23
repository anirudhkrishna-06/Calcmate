from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .agents import (
    audio_cognition_agent,
    build_agent_graph,
    intervention_agent,
    problem_structuring_agent,
    report_generator_agent,
    strategy_validator_agent,
    timeline_engine_agent,
)
from .contracts import (
    CognitiveChunk,
    DeviationAnalysis,
    EndSessionRequest,
    EndSessionResponse,
    EngineEvent,
    EngineEventType,
    GenerateReportResponse,
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
from .state import INTENT_TO_PHASE, build_timeline_metrics, default_problem_payload, make_session_state
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

        event = EngineEvent(
            event_type=EngineEventType.SESSION_STARTED,
            session_id=session_id,
            payload={"problem_payload": problem_payload.model_dump(mode="json")},
        )

        async with store.get_lock(session_id):
            state = self._apply_event(state, event)
            for derived_event in problem_structuring_agent.process(event, state):
                state = self._apply_event(state, derived_event)
                await self._dispatch_output(state, derived_event)
            state = self._transition_lifecycle(state, SessionLifecycle.ACTIVE)
            store.save(state)

        await self._dispatch_output(
            state,
            EngineEvent(
                event_type=EngineEventType.STATUS_UPDATED,
                session_id=session_id,
                payload={"status": "Listening..."},
            ),
        )
        await self._dispatch_phase(state)
        return StartSessionResponse(
            session_id=session_id,
            session_token=session_token,
            problem_payload=problem_payload,
            initial_state=state,
            agent_graph=build_agent_graph(),
        )

    async def stream_audio_chunk(self, payload: StreamAudioChunkRequest) -> StreamAudioChunkResponse:
        state = store.get(payload.session_id)
        if state is None:
            raise KeyError("Session not found.")
        if state.lifecycle_state in {SessionLifecycle.COMPLETED, SessionLifecycle.CLOSED}:
            raise ValueError("Session has already ended.")

        root_event = EngineEvent(
            event_type=EngineEventType.AUDIO_CHUNK_RECEIVED,
            session_id=payload.session_id,
            payload=payload.model_dump(mode="json"),
        )

        latest_chunk: CognitiveChunk | None = None
        intervention_recommended = False

        async with store.get_lock(payload.session_id):
            state = store.get(payload.session_id)
            if state is None:
                raise KeyError("Session not found.")

            await self._dispatch_output(
                state,
                EngineEvent(
                    event_type=EngineEventType.STATUS_UPDATED,
                    session_id=payload.session_id,
                    payload={"status": "Analyzing..."},
                ),
            )

            for classified_event in audio_cognition_agent.process(root_event, state):
                state = self._apply_event(state, classified_event)
                if classified_event.event_type == EngineEventType.INTENT_CLASSIFIED:
                    latest_chunk = CognitiveChunk.model_validate(classified_event.payload["chunk"])

                for timeline_event in timeline_engine_agent.process(classified_event, state):
                    state = self._apply_event(state, timeline_event)
                    await self._dispatch_output(state, timeline_event)
                    if timeline_event.event_type == EngineEventType.PHASE_TRANSITION_SUGGESTED:
                        lifecycle_name = timeline_event.payload.get("lifecycle_state")
                        if lifecycle_name:
                            state = self._transition_lifecycle(state, SessionLifecycle(lifecycle_name))
                            await self._dispatch_phase(state)

                for deviation_event in strategy_validator_agent.process(classified_event, state):
                    state = self._apply_event(state, deviation_event)
                    await self._dispatch_output(state, deviation_event)
                    for intervention_event in intervention_agent.process(deviation_event, state):
                        state = self._apply_event(state, intervention_event)
                        intervention_recommended = True
                        await self._dispatch_output(state, intervention_event)

            store.save(state)

        await self._dispatch_output(
            state,
            EngineEvent(
                event_type=EngineEventType.STATUS_UPDATED,
                session_id=payload.session_id,
                payload={"status": "Listening..." if payload.frontend_features and (payload.frontend_features.speech_energy or 0.0) > 0.02 else "Idle..."},
            ),
        )

        if latest_chunk is None:
            latest_chunk = CognitiveChunk.model_validate(
                {
                    "chunk_id": payload.chunk_id,
                    "timestamp": payload.timestamp.model_dump(),
                    "audio_features": (payload.frontend_features or {}).model_dump() if payload.frontend_features else {},
                    "intent": "unknown",
                    "confidence": 0.0,
                    "latency_seconds": 0.0,
                    "transcript_excerpt": payload.transcript_hint,
                    "created_at": utc_now(),
                }
            )

        return StreamAudioChunkResponse(
            session_id=payload.session_id,
            chunk_id=payload.chunk_id,
            detected_intent=latest_chunk.intent,
            confidence=latest_chunk.confidence,
            intervention_recommended=intervention_recommended,
            current_phase=state.phase,
        )

    async def manual_intervention(self, payload) -> tuple[SessionState, int]:
        state = store.get(payload.session_id)
        if state is None:
            raise KeyError("Session not found.")
        intervention_event = EngineEvent(
            event_type=EngineEventType.INTERVENTION_TRIGGERED,
            session_id=payload.session_id,
            payload={
                "reason": payload.trigger_reason.value,
                "message": payload.message,
                "at_seconds": float(len(state.timeline)),
                "intervention_id": payload.intervention_id,
            },
        )
        async with store.get_lock(payload.session_id):
            state = self._apply_event(state, intervention_event)
            store.save(state)
        await self._dispatch_output(state, intervention_event)
        return state, state.intervention_count

    async def end_session(self, payload: EndSessionRequest) -> EndSessionResponse:
        state = store.get(payload.session_id)
        if state is None:
            raise KeyError("Session not found.")

        event = EngineEvent(
            event_type=EngineEventType.SESSION_ENDED,
            session_id=payload.session_id,
            payload={
                "at_seconds": payload.final_timestamps.end_time,
                "image_reference": payload.image_reference,
            },
        )

        async with store.get_lock(payload.session_id):
            state = self._apply_event(state, event)
            state = self._transition_lifecycle(state, SessionLifecycle.COMPLETED)
            await self._dispatch_phase(state)
            for derived_event in report_generator_agent.process(event, state):
                state = self._apply_event(state, derived_event)
                await self._dispatch_output(state, derived_event)
            state = self._transition_lifecycle(state, SessionLifecycle.CLOSED)
            state.closed_at = utc_now()
            state.updated_at = state.closed_at
            store.save(state)

        await self._dispatch_phase(state)
        return EndSessionResponse(
            session_id=payload.session_id,
            lifecycle_state=state.lifecycle_state,
            closed_at=state.closed_at or utc_now(),
            total_chunks=len(state.chunks),
            total_interventions=state.intervention_count,
        )

    def generate_report(self, session_id: str) -> GenerateReportResponse:
        state = store.get(session_id)
        if state is None:
            raise KeyError("Session not found.")

        metrics = build_timeline_metrics(state)
        deviation_events = sum(1 for chunk in state.chunks if chunk.intent.value == "deviation")
        deviation_analysis = DeviationAnalysis(
            deviation_score=round(state.deviation_score, 2),
            deviation_events=deviation_events,
            summary="Deviation remained low." if deviation_events == 0 else "Deviation was detected and should be reviewed.",
        )
        strategy_evaluation = StrategyEvaluation(
            strategy_status="phase_3_live_pipeline",
            optimal_method=state.problem_payload.optimal_method if state.problem_payload else None,
            summary="The report is generated from live orchestrator state accumulated through the event pipeline.",
        )
        suggestions = [
            "Commit to the strongest available strategy sooner once the givens are stable.",
            "Use silent reflection briefly, then transition decisively into execution.",
            "Reduce time spent exploring methods that require information the problem does not provide.",
        ]
        return GenerateReportResponse(
            session_id=session_id,
            timeline_metrics=metrics,
            deviation_analysis=deviation_analysis,
            strategy_evaluation=strategy_evaluation,
            improvement_suggestions=suggestions,
        )

    async def send_snapshot(self, session_id: str) -> None:
        state = store.get(session_id)
        if state is None:
            return
        await ws_manager.broadcast(
            session_id,
            WebSocketEnvelope(
                type="session_snapshot",
                data={
                    "session_id": state.session_id,
                    "lifecycle_state": state.lifecycle_state.value,
                    "phase": state.phase.value,
                    "timeline": [item.model_dump(mode="json") for item in state.timeline],
                },
            ),
        )

    def _apply_event(self, state: SessionState, event: EngineEvent) -> SessionState:
        if event.event_type == EngineEventType.SESSION_STARTED:
            state.timeline.append(
                TimelineEvent(
                    event_type=event.event_type.value,
                    at_seconds=0.0,
                    category="system",
                    message="Session started",
                    payload=event.payload,
                )
            )
        elif event.event_type == EngineEventType.INTENT_CLASSIFIED:
            chunk = CognitiveChunk.model_validate(event.payload["chunk"])
            state.chunks.append(chunk)
            state.phase = INTENT_TO_PHASE.get(chunk.intent, SessionPhase.UNKNOWN)
        elif event.event_type == EngineEventType.TIMELINE_UPDATED:
            state.timeline.append(
                TimelineEvent(
                    event_type=event.event_type.value,
                    at_seconds=float(event.payload.get("at_seconds", 0.0)),
                    category=event.payload.get("category", "signal"),
                    message=event.payload.get("message", "Timeline updated"),
                    payload=event.payload,
                )
            )
        elif event.event_type == EngineEventType.DEVIATION_DETECTED:
            state.deviation_score += float(event.payload.get("time_wasted_seconds", 0.0))
        elif event.event_type == EngineEventType.INTERVENTION_TRIGGERED:
            state.intervention_count += 1
            state.timeline.append(
                TimelineEvent(
                    event_type=event.event_type.value,
                    at_seconds=float(event.payload.get("at_seconds", 0.0)),
                    category="intervention",
                    message="Intervention triggered",
                    payload=event.payload,
                )
            )
        elif event.event_type == EngineEventType.SESSION_ENDED:
            state.timeline.append(
                TimelineEvent(
                    event_type=event.event_type.value,
                    at_seconds=float(event.payload.get("at_seconds", 0.0)),
                    category="system",
                    message="Session ended",
                    payload=event.payload,
                )
            )
        state.updated_at = utc_now()
        metrics = build_timeline_metrics(state)
        state.metrics = metrics.model_dump()
        return state

    def _transition_lifecycle(self, state: SessionState, lifecycle_state: SessionLifecycle) -> SessionState:
        state.lifecycle_state = lifecycle_state
        state.updated_at = utc_now()
        return state

    async def _dispatch_phase(self, state: SessionState) -> None:
        await ws_manager.broadcast(
            state.session_id,
            WebSocketEnvelope(
                type="phase_change",
                data={
                    "session_id": state.session_id,
                    "phase": state.phase.value,
                    "lifecycle_state": state.lifecycle_state.value,
                },
            ),
        )

    async def _dispatch_output(self, state: SessionState, event: EngineEvent) -> None:
        if event.event_type == EngineEventType.TIMELINE_UPDATED:
            await ws_manager.broadcast(
                state.session_id,
                WebSocketEnvelope(
                    type="timeline_event",
                    data={
                        "message": event.payload.get("message", "Timeline updated"),
                        "detail": event.payload.get("detail", ""),
                        "timestamp": event.payload.get("at_seconds", 0.0),
                        "category": event.payload.get("category", "signal"),
                        "event_id": state.timeline[-1].event_id if state.timeline else None,
                    },
                ),
            )
        elif event.event_type == EngineEventType.INTERVENTION_TRIGGERED:
            await ws_manager.broadcast(
                state.session_id,
                WebSocketEnvelope(
                    type="intervention",
                    data={
                        "message": event.payload.get("message", "Intervention triggered"),
                        "reason": event.payload.get("reason"),
                        "timestamp": event.payload.get("at_seconds", 0.0),
                    },
                ),
            )
        elif event.event_type == EngineEventType.STATUS_UPDATED:
            await ws_manager.broadcast(
                state.session_id,
                WebSocketEnvelope(
                    type="status_update",
                    data={"status": event.payload.get("status", "Idle...")},
                ),
            )


orchestrator = SessionOrchestrator()
