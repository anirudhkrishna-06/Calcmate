import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_engine.app.agents import ReportGeneratorAgent, StrategyValidatorAgent
from cognitive_engine.app.contracts import (
    AcousticProfile,
    CognitiveChunk,
    CognitiveIntent,
    EngineEvent,
    EngineEventType,
    ProblemPayload,
    ProblemStructure,
    SemanticSignals,
    SessionPhase,
    SolutionGraph,
    SolutionGraphNode,
)
from cognitive_engine.app.state import build_timeline_metrics, make_session_state


def _chunk(chunk_id: str, intent: CognitiveIntent, transcript: str, start: float, end: float) -> CognitiveChunk:
    return CognitiveChunk.model_validate(
        {
            "chunk_id": chunk_id,
            "timestamp": {"start_time": start, "end_time": end},
            "intent": intent.value,
            "intent_raw": intent.value,
            "intent_refined": intent.value,
            "confidence": 0.82,
            "raw_confidence": 0.82,
            "refined_confidence": 0.82,
            "certainty": "weak",
            "trajectory": "stable_progress",
            "deviation_flag": False,
            "exploration_valid": False,
            "llm_used": False,
            "llm_reason": None,
            "ambiguity_score": 0.0,
            "keyword_strength": 0.4,
            "acoustic_profile": AcousticProfile().model_dump(mode="json"),
            "transcript": transcript,
            "transcript_confidence": 0.9,
            "transcript_words": [],
            "semantic_signals": SemanticSignals(problem_keyword_hits=["distance", "speed"]).model_dump(mode="json"),
            "latency_seconds": 0.0,
            "audio_reference": None,
        }
    )


def test_strategy_validator_uses_session_phase_without_name_error() -> None:
    state = make_session_state("session_phase_guard", ProblemPayload(raw_text="A car travels 150 km in 3 hours."))
    state.phase = SessionPhase.UNDERSTANDING
    state.problem_structure = ProblemStructure(problem_id="problem_1", domain="applied_math", concepts=["speed_distance_time"])
    state.solution_graph = SolutionGraph(
        nodes=[
            SolutionGraphNode(
                node_id="method_rate_formula",
                label="Rate Formula",
                node_type="method",
                priority="critical",
                expected_order=1,
                keywords=["speed", "distance", "time"],
            )
        ],
        edges={},
        optimal_paths=[["method_rate_formula"]],
        all_node_ids={"method_rate_formula"},
    )
    chunk = _chunk("chunk_1", CognitiveIntent.STRATEGY_SELECTION, "Use the speed distance time formula", 0.0, 2.0)
    event = EngineEvent(
        event_type=EngineEventType.INTENT_CLASSIFIED,
        session_id=state.session_id,
        payload={"chunk": chunk.model_dump(mode="json")},
    )

    events = asyncio.run(StrategyValidatorAgent().process(event, state))

    assert [item.event_type for item in events][:2] == [
        EngineEventType.PATH_UPDATE,
        EngineEventType.VALIDATION_STATE_UPDATED,
    ]


def test_report_time_analysis_uses_session_phase_without_name_error() -> None:
    state = make_session_state("report_phase_guard", ProblemPayload(raw_text="A car travels 150 km in 3 hours."))
    state.chunks = [
        _chunk("c1", CognitiveIntent.PROBLEM_UNDERSTANDING, "We need the average speed", 0.0, 2.0),
        _chunk("c2", CognitiveIntent.STRATEGY_SELECTION, "Use the rate formula distance over time", 2.0, 5.0),
        _chunk("c3", CognitiveIntent.SILENCE_REFLECTION, "Let me check that once", 5.0, 6.0),
    ]
    metrics = build_timeline_metrics(state)

    time_analysis = ReportGeneratorAgent()._build_time_analysis(state, metrics)

    assert time_analysis["mapping_time_seconds"] >= 3.0
    assert time_analysis["decision_time_seconds"] >= 1.0
