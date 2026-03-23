from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionLifecycle(str, Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    SOLVING = "solving"
    COMPLETED = "completed"
    CLOSED = "closed"


class SessionPhase(str, Enum):
    UNDERSTANDING = "understanding"
    STRATEGY = "strategy_selection"
    EXECUTION = "execution"
    REFLECTION = "reflection"
    UNKNOWN = "unknown"


class CognitiveIntent(str, Enum):
    PROBLEM_UNDERSTANDING = "problem_understanding"
    PARAMETER_RECOGNITION = "parameter_recognition"
    STRATEGY_SELECTION = "strategy_selection"
    EXECUTION_START = "execution_start"
    DEVIATION = "deviation"
    SILENCE_REFLECTION = "silence_reflection"
    UNKNOWN = "unknown"


class InterventionReason(str, Enum):
    DEVIATION = "deviation"
    SILENCE = "silence"
    CONFUSION_LOOP = "confusion_loop"


class EngineEventType(str, Enum):
    SESSION_STARTED = "SESSION_STARTED"
    AUDIO_CHUNK_RECEIVED = "AUDIO_CHUNK_RECEIVED"
    INTENT_CLASSIFIED = "INTENT_CLASSIFIED"
    TIMELINE_UPDATED = "TIMELINE_UPDATED"
    DEVIATION_DETECTED = "DEVIATION_DETECTED"
    INTERVENTION_TRIGGERED = "INTERVENTION_TRIGGERED"
    SESSION_ENDED = "SESSION_ENDED"
    STATUS_UPDATED = "STATUS_UPDATED"
    PHASE_TRANSITION_SUGGESTED = "PHASE_TRANSITION_SUGGESTED"
    AGENT_FAILED = "AGENT_FAILED"


class TimestampRange(BaseModel):
    start_time: float = Field(..., description="Chunk start in seconds relative to session start.")
    end_time: float = Field(..., description="Chunk end in seconds relative to session start.")


class AudioFeatures(BaseModel):
    pause_before_seconds: float | None = None
    speech_density: float | None = None
    speech_energy: float | None = None
    silence_ratio: float | None = None
    token_density: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class CognitiveChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    timestamp: TimestampRange
    audio_features: AudioFeatures = Field(default_factory=AudioFeatures)
    intent: CognitiveIntent
    confidence: float = Field(..., ge=0.0, le=1.0)
    latency_seconds: float = Field(..., ge=0.0)
    transcript_excerpt: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ProblemPayload(BaseModel):
    problem_id: str = Field(default_factory=lambda: f"problem_{uuid4().hex[:8]}")
    raw_text: str = "Problem context pending CalcMate integration."
    structured_representation: dict[str, Any] = Field(default_factory=dict)
    valid_methods: list[str] = Field(default_factory=list)
    optimal_method: str | None = None


class TimelineEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:10]}")
    event_type: str
    at_seconds: float
    message: str
    category: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class EngineEvent(BaseModel):
    event_type: EngineEventType
    session_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


class SessionState(BaseModel):
    session_id: str
    lifecycle_state: SessionLifecycle = SessionLifecycle.INITIALIZING
    phase: SessionPhase = SessionPhase.UNDERSTANDING
    problem_payload: ProblemPayload | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
    chunks: list[CognitiveChunk] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    deviation_score: float = 0.0
    intervention_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None


class AgentDescriptor(BaseModel):
    agent_id: str
    name: str
    role: str
    consumes: list[str]
    emits: list[str]


class AgentGraph(BaseModel):
    nodes: list[AgentDescriptor]
    edges: list[dict[str, str]]


class StartSessionRequest(BaseModel):
    problem_payload: ProblemPayload | None = None
    user_id: str | None = None
    session_metadata: dict[str, Any] = Field(default_factory=dict)


class StartSessionResponse(BaseModel):
    session_id: str
    session_token: str
    problem_payload: ProblemPayload
    initial_state: SessionState
    agent_graph: AgentGraph


class StreamAudioChunkRequest(BaseModel):
    session_id: str
    chunk_id: str
    timestamp: TimestampRange
    audio_payload_b64: str = Field(..., description="Base64 encoded audio bytes.")
    frontend_features: AudioFeatures | None = None
    transcript_hint: str | None = None


class StreamAudioChunkResponse(BaseModel):
    session_id: str
    chunk_id: str
    detected_intent: CognitiveIntent
    confidence: float
    intervention_recommended: bool
    current_phase: SessionPhase


class InterventionEventRequest(BaseModel):
    session_id: str
    intervention_id: str
    trigger_reason: InterventionReason
    message: str


class InterventionEventResponse(BaseModel):
    session_id: str
    intervention_id: str
    logged: bool
    intervention_count: int


class EndSessionRequest(BaseModel):
    session_id: str
    final_timestamps: TimestampRange
    image_reference: str | None = None


class EndSessionResponse(BaseModel):
    session_id: str
    lifecycle_state: SessionLifecycle
    closed_at: datetime
    total_chunks: int
    total_interventions: int


class TimelineMetrics(BaseModel):
    understanding_time_seconds: float = 0.0
    strategy_delay_seconds: float = 0.0
    deviation_time_seconds: float = 0.0
    execution_time_seconds: float = 0.0
    decision_efficiency_score: float = 0.0


class DeviationAnalysis(BaseModel):
    deviation_score: float
    deviation_events: int
    summary: str


class StrategyEvaluation(BaseModel):
    strategy_status: str
    optimal_method: str | None = None
    summary: str


class GenerateReportRequest(BaseModel):
    session_id: str


class GenerateReportResponse(BaseModel):
    session_id: str
    timeline_metrics: TimelineMetrics
    deviation_analysis: DeviationAnalysis
    strategy_evaluation: StrategyEvaluation
    improvement_suggestions: list[str]
    report_generated_at: datetime = Field(default_factory=utc_now)


class WebSocketEnvelope(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)
