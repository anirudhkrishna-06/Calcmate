from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


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


class IntentCertainty(str, Enum):
    STRONG = "strong"
    WEAK = "weak"
    AMBIGUOUS = "ambiguous"


class CognitiveTrajectory(str, Enum):
    ISOLATED_SIGNAL = "isolated_signal"
    STABLE_PROGRESS = "stable_progress"
    EXPLORATION_ACTIVE = "exploration_active"
    EXPLORATION_CONVERGING = "exploration_converging"
    DEVIATION_PERSISTENT = "deviation_persistent"
    CONFUSION_BUILDING = "confusion_building"
    DEEP_REFLECTION = "deep_reflection"
    EXECUTION_COMMITMENT = "execution_commitment"


class CognitiveIntent(str, Enum):
    PROBLEM_UNDERSTANDING = "problem_understanding"
    PARAMETER_RECOGNITION = "parameter_recognition"
    STRATEGY_SELECTION = "strategy_selection"
    EXECUTION_START = "execution_start"
    DEVIATION = "deviation"
    VERIFICATION = "verification"
    SILENCE_REFLECTION = "silence_reflection"
    ERROR_CORRECTION = "error_correction"
    SOLUTION_SUMMARY = "solution_summary"
    CONCEPTUAL_EXPLANATION = "conceptual_explanation"
    COMPARISON_ANALYSIS = "comparison_analysis"
    META_COGNITION = "meta_cognition"
    WORKING_MEMORY_RETRIEVAL = "working_memory_retrieval"
    STUCK_STATE = "stuck_state"
    CONFIDENCE_EXPRESSION = "confidence_expression"
    UNKNOWN = "unknown"


class InterventionReason(str, Enum):
    DEVIATION = "deviation"
    SILENCE = "silence"
    CONFUSION_LOOP = "confusion_loop"


class EngineEventType(str, Enum):
    SESSION_STARTED = "SESSION_STARTED"
    PROBLEM_STRUCTURED = "PROBLEM_STRUCTURED"
    AUDIO_CHUNK_RECEIVED = "AUDIO_CHUNK_RECEIVED"
    ACOUSTIC_PROFILE_COMPUTED = "ACOUSTIC_PROFILE_COMPUTED"
    TRANSCRIPTION_COMPLETED = "TRANSCRIPTION_COMPLETED"
    SEMANTIC_INTENT_INFERRED = "SEMANTIC_INTENT_INFERRED"
    RULE_INTENT_CLASSIFIED = "RULE_INTENT_CLASSIFIED"
    CONTEXT_REFINED = "CONTEXT_REFINED"
    LLM_REFINEMENT_COMPLETED = "LLM_REFINEMENT_COMPLETED"
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


class FrontendAudioFeatures(BaseModel):
    rms_energy: float | None = None
    speech_ratio: float | None = None
    leading_silence: float | None = None
    trailing_silence: float | None = None
    noise_floor: float | None = None
    voiced_frames: float | None = None
    pause_before_seconds: float | None = None
    speech_density: float | None = None
    speech_energy: float | None = None
    silence_ratio: float | None = None
    token_density: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AcousticProfile(BaseModel):
    effective_speech_duration: float = 0.0
    silence_ratio: float = 1.0
    speech_density: float = 0.0
    hesitation_score: float = 0.0
    energy_variance: float = 0.0
    normalized_energy: float = 0.0
    pause_before_seconds: float = 0.0
    leading_silence_seconds: float = 0.0
    trailing_silence_seconds: float = 0.0
    voiced_frames_ratio: float = 0.0
    frontend_validated: bool = True
    raw_features: dict[str, Any] = Field(default_factory=dict)


class TranscriptWord(BaseModel):
    word: str
    start: float = 0.0
    end: float = 0.0
    confidence: float | None = None


class TranscriptSegment(BaseModel):
    segment_id: str
    transcript: str | None = None
    start: float = 0.0
    end: float = 0.0
    confidence: float = 0.0
    words: list[TranscriptWord] = Field(default_factory=list)


class TranscriptResult(BaseModel):
    transcript: str | None = None
    confidence: float = 0.0
    words: list[TranscriptWord] = Field(default_factory=list)
    segments: list[TranscriptSegment] = Field(default_factory=list)
    provider: str = "deepgram"
    model: str | None = None
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None


class SemanticSignals(BaseModel):
    concepts: list[str] = Field(default_factory=list)
    uncertainty: bool = False
    decision: bool = False
    formula_references: list[str] = Field(default_factory=list)
    uncertainty_markers: list[str] = Field(default_factory=list)
    decision_markers: list[str] = Field(default_factory=list)
    deviation_markers: list[str] = Field(default_factory=list)
    verification_markers: list[str] = Field(default_factory=list)
    parameter_markers: list[str] = Field(default_factory=list)
    strategy_markers: list[str] = Field(default_factory=list)
    error_markers: list[str] = Field(default_factory=list)
    summary_markers: list[str] = Field(default_factory=list)
    conceptual_markers: list[str] = Field(default_factory=list)
    confidence_markers: list[str] = Field(default_factory=list)
    hesitation_markers: list[str] = Field(default_factory=list)
    quantitative_markers: list[str] = Field(default_factory=list)
    temporal_markers: list[str] = Field(default_factory=list)
    problem_keyword_hits: list[str] = Field(default_factory=list)
    off_topic_markers: list[str] = Field(default_factory=list)
    problem_alignment_score: float = 0.0
    filler_only: bool = False


class SemanticIntentResult(BaseModel):
    intent: CognitiveIntent = CognitiveIntent.UNKNOWN
    confidence: float = 0.0
    certainty: IntentCertainty = IntentCertainty.AMBIGUOUS
    keyword_strength: float = 0.0
    semantic_signals: SemanticSignals = Field(default_factory=SemanticSignals)
    rationale: str = ""


class GraphNode(BaseModel):
    node_id: str
    label: str
    node_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class MethodDefinition(BaseModel):
    name: str
    requirements: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    score: float = 0.0


class SymbolicRepresentation(BaseModel):
    type: str = "graph"
    equations: list[str] = Field(default_factory=list)
    wl_subtrees: list[list[str]] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class ProblemStructure(BaseModel):
    problem_id: str
    domain: str | None = None
    concepts: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    methods: list[MethodDefinition] = Field(default_factory=list)
    optimal_path: list[str] = Field(default_factory=list)
    representation: SymbolicRepresentation = Field(default_factory=SymbolicRepresentation)
    parsing_summary: dict[str, Any] = Field(default_factory=dict)
    keyword_bank: list[str] = Field(default_factory=list)


class ContextRefinementResult(BaseModel):
    refined_intent: CognitiveIntent = CognitiveIntent.UNKNOWN
    confidence: float = 0.0
    certainty: IntentCertainty = IntentCertainty.AMBIGUOUS
    trajectory: CognitiveTrajectory = CognitiveTrajectory.ISOLATED_SIGNAL
    deviation_flag: bool = False
    exploration_valid: bool = False
    ambiguity_score: float = 0.0
    llm_recommended: bool = False
    notes: list[str] = Field(default_factory=list)


class LLMRefinementResult(BaseModel):
    intent: CognitiveIntent | None = None
    confidence: float = 0.0
    certainty: IntentCertainty = IntentCertainty.AMBIGUOUS
    reason: str | None = None
    used: bool = False
    timed_out: bool = False
    error: str | None = None


class CognitiveChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    timestamp: TimestampRange
    intent: CognitiveIntent
    intent_raw: CognitiveIntent
    intent_refined: CognitiveIntent
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    refined_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    certainty: IntentCertainty = IntentCertainty.AMBIGUOUS
    trajectory: CognitiveTrajectory = CognitiveTrajectory.ISOLATED_SIGNAL
    deviation_flag: bool = False
    exploration_valid: bool = False
    llm_used: bool = False
    llm_reason: str | None = None
    ambiguity_score: float = 0.0
    keyword_strength: float = 0.0
    acoustic_profile: AcousticProfile = Field(default_factory=AcousticProfile)
    transcript: str | None = None
    transcript_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    transcript_words: list[TranscriptWord] = Field(default_factory=list)
    semantic_signals: SemanticSignals = Field(default_factory=SemanticSignals)
    latency_seconds: float = Field(..., ge=0.0)
    audio_reference: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ProblemPayload(BaseModel):
    problem_id: str = Field(default_factory=lambda: f"problem_{uuid4().hex[:8]}")
    raw_text: str = "Problem context pending cognitive problem structuring."
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
    problem_structure: ProblemStructure | None = None
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
    start_time: float | None = None
    end_time: float | None = None
    timestamp: TimestampRange | None = None
    audio_blob: str | None = Field(default=None, validation_alias=AliasChoices("audio_blob", "audio_payload_b64"))
    frontend_features: FrontendAudioFeatures | None = None
    transcript_hint: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("timestamp") and (data.get("start_time") is None or data.get("end_time") is None):
            timestamp = data.get("timestamp") or {}
            data = {
                **data,
                "start_time": timestamp.get("start_time"),
                "end_time": timestamp.get("end_time"),
            }
        return data

    @property
    def time_range(self) -> TimestampRange:
        if self.timestamp is not None:
            return self.timestamp
        return TimestampRange(start_time=self.start_time or 0.0, end_time=self.end_time or 0.0)


class StreamAudioChunkResponse(BaseModel):
    session_id: str
    chunk_id: str
    detected_intent: CognitiveIntent
    confidence: float
    certainty: IntentCertainty = IntentCertainty.AMBIGUOUS
    trajectory: CognitiveTrajectory = CognitiveTrajectory.ISOLATED_SIGNAL
    llm_used: bool = False
    intervention_recommended: bool
    current_phase: SessionPhase
    transcript_excerpt: str | None = None
    transcript_confidence: float = 0.0


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
    verification_time_seconds: float = 0.0
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
