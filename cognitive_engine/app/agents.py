from __future__ import annotations

import logging

from .contracts import (
    AgentDescriptor,
    AgentGraph,
    CognitiveChunk,
    CognitiveIntent,
    EngineEvent,
    EngineEventType,
    InterventionReason,
    SessionState,
)
from .state import build_chunk, infer_audio_features, should_transition_to_solving

logger = logging.getLogger("cognitive_engine.agents")


class ProblemStructuringAgent:
    def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.SESSION_STARTED:
            return []
        return [
            EngineEvent(
                event_type=EngineEventType.TIMELINE_UPDATED,
                session_id=event.session_id,
                payload={
                    "category": "system",
                    "message": "Cognitive session initialized.",
                    "at_seconds": 0.0,
                },
            )
        ]


class AudioCognitionAgent:
    def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.AUDIO_CHUNK_RECEIVED:
            return []

        payload = event.payload
        try:
            features = infer_audio_features(payload.get("frontend_features"))
            audio_payload_b64 = payload.get("audio_payload_b64") or ""
            logger.info(
                "Audio chunk received | session=%s chunk=%s window=%.2f-%.2f audio_b64_chars=%s transcript_present=%s features=pause=%.2f density=%.3f energy=%.3f silence=%.3f lead=%.2f trail=%.2f floor=%.4f threshold=%.4f mime=%s bytes=%s",
                event.session_id,
                payload.get("chunk_id"),
                payload.get("timestamp", {}).get("start_time", 0.0),
                payload.get("timestamp", {}).get("end_time", 0.0),
                len(audio_payload_b64),
                bool(payload.get("transcript_hint")),
                features.pause_before_seconds or 0.0,
                features.speech_density or 0.0,
                features.speech_energy or 0.0,
                features.silence_ratio or 0.0,
                float(features.extra.get("leading_silence_seconds", 0.0)),
                float(features.extra.get("trailing_silence_seconds", 0.0)),
                float(features.extra.get("noise_floor", 0.0)),
                float(features.extra.get("speech_threshold", 0.0)),
                features.extra.get("mime_type", "<unknown>"),
                features.extra.get("chunk_size_bytes", 0),
            )
            chunk = build_chunk(
                chunk_id=payload["chunk_id"],
                start_time=payload["timestamp"]["start_time"],
                end_time=payload["timestamp"]["end_time"],
                features=features,
                transcript_hint=payload.get("transcript_hint"),
            )
        except Exception as exc:
            logger.exception(
                "Audio cognition failed | session=%s chunk=%s error=%s",
                event.session_id,
                payload.get("chunk_id"),
                exc,
            )
            return [
                EngineEvent(
                    event_type=EngineEventType.AGENT_FAILED,
                    session_id=event.session_id,
                    payload={"agent": "audio_cognition", "error": str(exc)},
                )
            ]

        logger.info(
            "Intent classified | session=%s chunk=%s intent=%s confidence=%.2f latency=%.2f transcript=%s",
            event.session_id,
            chunk.chunk_id,
            chunk.intent.value,
            chunk.confidence,
            chunk.latency_seconds,
            chunk.transcript_excerpt if chunk.transcript_excerpt else "<none>",
        )
        return [
            EngineEvent(
                event_type=EngineEventType.INTENT_CLASSIFIED,
                session_id=event.session_id,
                payload={
                    "chunk": chunk.model_dump(mode="json"),
                    "intent": chunk.intent.value,
                    "confidence": chunk.confidence,
                },
            )
        ]


class TimelineEngineAgent:
    def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.INTENT_CLASSIFIED:
            return []

        chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        mapped = {
            CognitiveIntent.PROBLEM_UNDERSTANDING: ("understanding", "Understanding detected"),
            CognitiveIntent.PARAMETER_RECOGNITION: ("parameter", "Parameter recognition"),
            CognitiveIntent.STRATEGY_SELECTION: ("strategy", "Strategy identified"),
            CognitiveIntent.DEVIATION: ("deviation", "Deviation detected"),
            CognitiveIntent.EXECUTION_START: ("execution", "Execution started"),
            CognitiveIntent.SILENCE_REFLECTION: ("delay", "Strategy delay"),
            CognitiveIntent.UNKNOWN: ("signal", "Signal received"),
        }
        category, message = mapped.get(chunk.intent, ("signal", "Signal received"))
        detail = {
            CognitiveIntent.PROBLEM_UNDERSTANDING: "The system detected active framing of the problem.",
            CognitiveIntent.PARAMETER_RECOGNITION: "Important givens and constraints are being surfaced.",
            CognitiveIntent.STRATEGY_SELECTION: "A concrete method appears to be emerging.",
            CognitiveIntent.DEVIATION: "The reasoning path appears to be drifting from the most direct route.",
            CognitiveIntent.EXECUTION_START: "The learner has shifted from selecting a method to carrying it out.",
            CognitiveIntent.SILENCE_REFLECTION: "A sustained pause suggests transition toward silent solving.",
            CognitiveIntent.UNKNOWN: "The engine captured a chunk but confidence is still low.",
        }[chunk.intent]

        events = [
            EngineEvent(
                event_type=EngineEventType.TIMELINE_UPDATED,
                session_id=event.session_id,
                payload={
                    "category": category,
                    "message": message,
                    "detail": detail,
                    "at_seconds": chunk.timestamp.end_time,
                    "chunk_id": chunk.chunk_id,
                    "intent": chunk.intent.value,
                },
            )
        ]

        if should_transition_to_solving(chunk):
            logger.info(
                "Lifecycle transition suggested | session=%s chunk=%s target=solving reason=silence_threshold",
                event.session_id,
                chunk.chunk_id,
            )
            events.append(
                EngineEvent(
                    event_type=EngineEventType.PHASE_TRANSITION_SUGGESTED,
                    session_id=event.session_id,
                    payload={
                        "lifecycle_state": "solving",
                        "reason": "silence_threshold",
                        "at_seconds": chunk.timestamp.end_time,
                    },
                )
            )
        return events


class StrategyValidatorAgent:
    def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.INTENT_CLASSIFIED:
            return []

        chunk = CognitiveChunk.model_validate(event.payload["chunk"])
        if chunk.intent != CognitiveIntent.DEVIATION:
            return []

        wasted_time = max(chunk.timestamp.end_time - chunk.timestamp.start_time, 1.0)
        logger.info(
            "Deviation detected | session=%s chunk=%s wasted_time=%.2f",
            event.session_id,
            chunk.chunk_id,
            wasted_time,
        )
        return [
            EngineEvent(
                event_type=EngineEventType.DEVIATION_DETECTED,
                session_id=event.session_id,
                payload={
                    "reason": "suboptimal_strategy_path",
                    "time_wasted_seconds": wasted_time,
                    "at_seconds": chunk.timestamp.end_time,
                    "chunk_id": chunk.chunk_id,
                },
            )
        ]


class InterventionAgent:
    def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.DEVIATION_DETECTED:
            return []
        if session_state.intervention_count >= 3:
            logger.info(
                "Intervention suppressed | session=%s count=%s reason=max_interventions",
                event.session_id,
                session_state.intervention_count,
            )
            return []

        logger.info(
            "Intervention triggered | session=%s reason=%s at=%.2f",
            event.session_id,
            event.payload.get("reason"),
            event.payload.get("at_seconds", 0.0),
        )
        return [
            EngineEvent(
                event_type=EngineEventType.INTERVENTION_TRIGGERED,
                session_id=event.session_id,
                payload={
                    "reason": InterventionReason.DEVIATION.value,
                    "message": "Pause for a moment. Which method uses only the values already given?",
                    "at_seconds": event.payload.get("at_seconds", 0.0),
                },
            )
        ]


class ReportGeneratorAgent:
    def process(self, event: EngineEvent, session_state: SessionState) -> list[EngineEvent]:
        if event.event_type != EngineEventType.SESSION_ENDED:
            return []
        return [
            EngineEvent(
                event_type=EngineEventType.STATUS_UPDATED,
                session_id=event.session_id,
                payload={"status": "Session archived.", "at_seconds": event.payload.get("at_seconds", 0.0)},
            )
        ]


problem_structuring_agent = ProblemStructuringAgent()
audio_cognition_agent = AudioCognitionAgent()
timeline_engine_agent = TimelineEngineAgent()
strategy_validator_agent = StrategyValidatorAgent()
intervention_agent = InterventionAgent()
report_generator_agent = ReportGeneratorAgent()


def build_agent_graph() -> AgentGraph:
    nodes = [
        AgentDescriptor(
            agent_id="problem_structuring",
            name="Problem Structuring Agent",
            role="Initializes structured problem context at session start.",
            consumes=[EngineEventType.SESSION_STARTED.value],
            emits=[EngineEventType.TIMELINE_UPDATED.value],
        ),
        AgentDescriptor(
            agent_id="audio_cognition",
            name="Audio Cognition Agent",
            role="Transforms audio chunk events into classified cognitive chunks.",
            consumes=[EngineEventType.AUDIO_CHUNK_RECEIVED.value],
            emits=[EngineEventType.INTENT_CLASSIFIED.value],
        ),
        AgentDescriptor(
            agent_id="timeline_engine",
            name="Timeline Engine",
            role="Converts classified intent into human-readable cognitive milestones.",
            consumes=[EngineEventType.INTENT_CLASSIFIED.value],
            emits=[EngineEventType.TIMELINE_UPDATED.value, EngineEventType.PHASE_TRANSITION_SUGGESTED.value],
        ),
        AgentDescriptor(
            agent_id="strategy_validator",
            name="Strategy Validator",
            role="Checks whether the current reasoning path is deviating from the expected method.",
            consumes=[EngineEventType.INTENT_CLASSIFIED.value],
            emits=[EngineEventType.DEVIATION_DETECTED.value],
        ),
        AgentDescriptor(
            agent_id="intervention_agent",
            name="Intervention Agent",
            role="Generates minimal interventions when deviation thresholds are reached.",
            consumes=[EngineEventType.DEVIATION_DETECTED.value],
            emits=[EngineEventType.INTERVENTION_TRIGGERED.value],
        ),
        AgentDescriptor(
            agent_id="report_generator",
            name="Report Generator",
            role="Finalizes post-session analytics and archive status.",
            consumes=[EngineEventType.SESSION_ENDED.value],
            emits=[EngineEventType.STATUS_UPDATED.value],
        ),
    ]

    edges = [
        {"from": "problem_structuring", "to": "timeline_engine"},
        {"from": "audio_cognition", "to": "timeline_engine"},
        {"from": "audio_cognition", "to": "strategy_validator"},
        {"from": "strategy_validator", "to": "intervention_agent"},
        {"from": "timeline_engine", "to": "report_generator"},
    ]
    return AgentGraph(nodes=nodes, edges=edges)
