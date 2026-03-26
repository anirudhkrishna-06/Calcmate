from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_engine.app.context_engine import context_window_engine
from cognitive_engine.app.contracts import (
    AcousticProfile,
    CognitiveChunk,
    CognitiveIntent,
    FrontendAudioFeatures,
    ProblemPayload,
    ProblemStructure,
    SemanticSignals,
    SessionState,
    SolutionGraph,
    SolutionGraphNode,
    TranscriptWord,
)
from cognitive_engine.app.state import make_session_state


def _chunk(chunk_id: str, transcript: str, intent: CognitiveIntent) -> CognitiveChunk:
    return CognitiveChunk.model_validate(
        {
            "chunk_id": chunk_id,
            "timestamp": {"start_time": 0.0, "end_time": 5.0},
            "intent": intent.value,
            "intent_raw": intent.value,
            "intent_refined": intent.value,
            "confidence": 0.28,
            "raw_confidence": 0.28,
            "refined_confidence": 0.28,
            "certainty": "ambiguous",
            "trajectory": "isolated_signal",
            "deviation_flag": False,
            "exploration_valid": False,
            "llm_used": False,
            "llm_reason": None,
            "ambiguity_score": 0.0,
            "keyword_strength": 0.0,
            "acoustic_profile": AcousticProfile().model_dump(mode="json"),
            "transcript": transcript,
            "transcript_confidence": 0.9,
            "transcript_words": [TranscriptWord(word="formula")],
            "semantic_signals": SemanticSignals(problem_keyword_hits=["formula", "heron"]).model_dump(mode="json"),
            "latency_seconds": 0.0,
            "audio_reference": None,
        }
    )


def test_context_engine_uses_local_similarity_for_strategy() -> None:
    state = make_session_state("session_test", ProblemPayload(raw_text="Find triangle area using Heron's formula"))
    state.problem_structure = ProblemStructure.model_validate(
        {
            "problem_id": "prob_1",
            "domain": "geometry",
            "concepts": ["triangle_area"],
            "methods": [
                {
                    "name": "Heron's Formula",
                    "keywords": ["heron", "semiperimeter", "formula"],
                    "steps": ["Compute semiperimeter"],
                    "requirements": [],
                    "equations": [],
                    "score": 0.9,
                }
            ],
            "optimal_path": ["Heron's Formula"],
            "keyword_bank": ["heron", "semiperimeter", "formula", "triangle area"],
        }
    )
    state.chunks = [
        _chunk("chunk_1", "we should use heron formula", CognitiveIntent.STRATEGY_SELECTION),
        _chunk("chunk_2", "the semiperimeter helps here", CognitiveIntent.STRATEGY_SELECTION),
    ]
    current = _chunk("chunk_3", "formula semiperimeter triangle area", CognitiveIntent.UNKNOWN)

    result = context_window_engine.refine(current_chunk=current, session_state=state)

    assert result.refined_intent == CognitiveIntent.STRATEGY_SELECTION
    assert result.llm_recommended is False


def test_context_engine_uses_solution_graph_for_execution() -> None:
    state = make_session_state("session_exec", ProblemPayload(raw_text="Solve the equation"))
    state.problem_structure = ProblemStructure.model_validate(
        {
            "problem_id": "prob_2",
            "domain": "algebra",
            "concepts": ["linear_equation"],
            "methods": [
                {
                    "name": "Balance Method",
                    "keywords": ["balance", "isolate", "divide both sides"],
                    "steps": ["Subtract 3 from both sides", "Divide by 2"],
                    "requirements": [],
                    "equations": ["2x+3=11"],
                    "score": 0.95,
                }
            ],
            "optimal_path": ["Balance Method"],
            "keyword_bank": ["balance", "isolate", "subtract", "divide both sides"],
        }
    )
    state.solution_graph = SolutionGraph.model_validate(
        {
            "nodes": [
                SolutionGraphNode(
                    node_id="method:balance_method",
                    label="Balance Method",
                    node_type="method",
                    keywords=["balance", "isolate"],
                ).model_dump(mode="json"),
                SolutionGraphNode(
                    node_id="method:balance_method:step:0",
                    label="Subtract 3 from both sides",
                    node_type="step",
                    keywords=["subtract", "both", "sides"],
                ).model_dump(mode="json"),
            ],
            "edges": {},
            "optimal_paths": [],
            "alternative_paths": [],
            "all_node_ids": ["method:balance_method", "method:balance_method:step:0"],
        }
    )
    current = _chunk("chunk_exec", "subtract 3 from both sides", CognitiveIntent.UNKNOWN)

    result = context_window_engine.refine(current_chunk=current, session_state=state)

    assert result.refined_intent == CognitiveIntent.EXECUTION_START
    assert result.confidence >= 0.7
