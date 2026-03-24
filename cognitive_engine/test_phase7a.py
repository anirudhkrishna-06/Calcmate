"""Phase 7A — Integration Tests.

Verifies:
  1. Solution graph construction from ProblemStructure
  2. Node mapping from transcript chunks
  3. Cognitive path tracking
  4. Graph alignment (LCS, overlap, transition validity)
  5. Metric calculations
"""
from __future__ import annotations

import sys
import os

# Ensure the cognitive_engine package can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.contracts import (
    CognitiveChunk,
    CognitiveIntent,
    CognitivePath,
    CognitivePathNode,
    CognitiveTrajectory,
    IntentCertainty,
    MethodDefinition,
    ProblemStructure,
    SemanticSignals,
    SolutionGraph,
    SolutionGraphNode,
    ValidationState,
    AcousticProfile,
    TimestampRange,
    TranscriptWord,
)
from app.strategy_validation.solution_graph import build_enriched_solution_graph
from app.strategy_validation.node_mapper import NodeMapper
from app.strategy_validation.cognitive_path import CognitivePathEngine
from app.strategy_validation.graph_alignment import GraphAlignmentEngine
from app.strategy_validation.metrics import MetricsEngine

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} — {detail}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_triangle_problem() -> ProblemStructure:
    """Triangle area problem with three sides → Heron as optimal."""
    return ProblemStructure(
        problem_id="test_triangle",
        domain="geometry",
        concepts=["triangle_area"],
        parameters={"sides": [5, 6, 7], "numbers": [5, 6, 7]},
        constraints=[],
        methods=[
            MethodDefinition(
                name="Heron",
                requirements=["three_sides_known"],
                steps=["compute_semiperimeter", "apply_heron_formula"],
                equations=["s = (a + b + c)/2", "Area = sqrt(s*(s-a)*(s-b)*(s-c))"],
                keywords=["heron", "semiperimeter", "all sides", "three sides"],
                score=9.5,
            ),
            MethodDefinition(
                name="Base-Height",
                requirements=["base_known", "height_known"],
                steps=["identify_base", "identify_height", "apply_area_formula"],
                equations=["Area = (1/2) * base * height"],
                keywords=["base", "height", "altitude"],
                score=8.5,
            ),
        ],
        optimal_path=["Heron"],
        keyword_bank=["heron", "semiperimeter", "triangle", "area", "sides"],
    )


def make_chunk(
    chunk_id: str,
    transcript: str,
    intent: CognitiveIntent,
    start: float,
    end: float,
    keyword_hits: list[str] | None = None,
    concepts: list[str] | None = None,
    formula_refs: list[str] | None = None,
    confidence: float = 0.75,
) -> CognitiveChunk:
    return CognitiveChunk(
        chunk_id=chunk_id,
        timestamp={"start_time": start, "end_time": end},
        intent=intent,
        intent_raw=intent,
        intent_refined=intent,
        confidence=confidence,
        raw_confidence=confidence,
        refined_confidence=confidence,
        certainty=IntentCertainty.WEAK,
        trajectory=CognitiveTrajectory.STABLE_PROGRESS,
        deviation_flag=False,
        exploration_valid=False,
        llm_used=False,
        ambiguity_score=0.1,
        keyword_strength=0.5,
        acoustic_profile=AcousticProfile(),
        transcript=transcript,
        transcript_confidence=0.85,
        semantic_signals=SemanticSignals(
            concepts=concepts or [],
            problem_keyword_hits=keyword_hits or [],
            formula_references=formula_refs or [],
            problem_alignment_score=0.5,
        ),
        latency_seconds=0.1,
    )


# ===========================================================================
# TEST 1: Solution Graph Construction
# ===========================================================================
print("\n=== TEST 1: Solution Graph Construction ===")

ps = make_triangle_problem()
graph = build_enriched_solution_graph(ps)

check("Graph has nodes", len(graph.nodes) > 0, f"got {len(graph.nodes)}")
check("Graph has edges", len(graph.edges) > 0, f"got {len(graph.edges)}")
check("Has optimal path", len(graph.optimal_paths) > 0)
check("Has alternative paths", len(graph.alternative_paths) > 0)

# Check specific nodes
concept_nodes = [n for n in graph.nodes if n.node_type == "concept"]
method_nodes = [n for n in graph.nodes if n.node_type == "method"]
step_nodes = [n for n in graph.nodes if n.node_type == "step"]
equation_nodes = [n for n in graph.nodes if n.node_type == "equation"]

check("Has concept node for triangle_area", len(concept_nodes) >= 1, f"got {len(concept_nodes)}")
check("Has method nodes (Heron + Base-Height)", len(method_nodes) == 2, f"got {len(method_nodes)}")
check("Heron steps exist", any(n.label.lower().replace(" ", "_") == "compute_semiperimeter" for n in step_nodes), f"steps: {[n.label for n in step_nodes]}")
check("Optimal path contains Heron", "method:heron" in graph.optimal_paths[0], f"optimal: {graph.optimal_paths}")

# Check adjacency
heron_id = "method:heron"
check("Heron has outgoing edges", heron_id in graph.edges and len(graph.edges[heron_id]) > 0)
check("is_on_graph works", graph.is_on_graph(heron_id))
check("is_on_graph false for invalid", not graph.is_on_graph("method:fake"))


# ===========================================================================
# TEST 2: Node Mapping
# ===========================================================================
print("\n=== TEST 2: Node Mapping ===")

mapper = NodeMapper()

# Chunk that mentions heron keywords
chunk1 = make_chunk("c1", "let me use heron's formula for the semiperimeter", CognitiveIntent.STRATEGY_SELECTION, 0, 5, keyword_hits=["heron", "semiperimeter"])
node1 = mapper.map_chunk(chunk1, graph, ps)

check("On-graph match for Heron keywords", node1.is_on_graph, f"mapped: {node1.node_label} (graph_id: {node1.mapped_graph_node_id})")
check("Mapped to a method or step node", node1.node_type in {"method", "step"}, f"type: {node1.node_type}")
check("Has confidence weight > 0", node1.confidence_weight > 0, f"weight: {node1.confidence_weight}")

# Chunk that mentions irrelevant physics
chunk2 = make_chunk("c2", "maybe I should use equations of motion from physics", CognitiveIntent.DEVIATION, 5, 10, keyword_hits=[])
node2 = mapper.map_chunk(chunk2, graph, ps)

check("Off-graph for physics content", not node2.is_on_graph, f"mapped: {node2.node_label}")

# Silent / filler chunk
chunk3 = make_chunk("c3", "", CognitiveIntent.SILENCE_REFLECTION, 10, 12)
chunk3_signals = chunk3.semantic_signals
node3 = mapper.map_chunk(chunk3, graph, ps)

check("Off-graph for empty transcript", not node3.is_on_graph)

# Chunk with formula reference
chunk4 = make_chunk("c4", "the area formula is half base height", CognitiveIntent.STRATEGY_SELECTION, 12, 16, keyword_hits=["base", "height", "area"], formula_refs=["Area = (1/2) * base * height"])
node4 = mapper.map_chunk(chunk4, graph, ps)

check("Maps formula reference chunk to graph", node4.is_on_graph, f"mapped: {node4.node_label}")


# ===========================================================================
# TEST 3: Cognitive Path Tracking
# ===========================================================================
print("\n=== TEST 3: Cognitive Path Tracking ===")

path_engine = CognitivePathEngine()
path = CognitivePath()

path_engine.add_node(path, node1, graph)
check("Path has 1 node after first add", len(path.nodes) == 1)
check("No transitions after first add", len(path.transitions) == 0)

path_engine.add_node(path, node2, graph)
check("Path has 2 nodes", len(path.nodes) == 2)
check("Has 1 transition", len(path.transitions) == 1)

path_engine.add_node(path, node3, graph)
path_engine.add_node(path, node4, graph)
check("Path has 4 nodes total", len(path.nodes) == 4)
check("On-graph count >= 2", path.on_graph_count() >= 2, f"on_graph: {path.on_graph_count()}")
check("Off-graph count >= 1", path.off_graph_count() >= 1, f"off_graph: {path.off_graph_count()}")

# Methods visited
methods = path_engine.get_unique_methods_visited(path)
check("At least one method visited", len(methods) >= 1, f"methods: {methods}")


# ===========================================================================
# TEST 4: Graph Alignment
# ===========================================================================
print("\n=== TEST 4: Graph Alignment ===")

alignment_engine = GraphAlignmentEngine()
alignment = alignment_engine.compute(path, graph)

check("Alignment result has node_overlap > 0", alignment.node_overlap_ratio > 0, f"overlap: {alignment.node_overlap_ratio}")
check("Overall alignment between 0 and 1", 0 <= alignment.overall_alignment <= 1, f"alignment: {alignment.overall_alignment}")
check("Progress ratio >= 0", alignment.progress_ratio >= 0, f"progress: {alignment.progress_ratio}")

# Test LCS
lcs_result = alignment_engine._longest_common_subsequence(["a", "b", "c"], ["a", "c", "d"])
check("LCS of [a,b,c] and [a,c,d] = [a,c]", lcs_result == ["a", "c"], f"got: {lcs_result}")

lcs_empty = alignment_engine._longest_common_subsequence([], ["a", "b"])
check("LCS with empty = []", lcs_empty == [], f"got: {lcs_empty}")


# ===========================================================================
# TEST 5: Metric Calculations
# ===========================================================================
print("\n=== TEST 5: Metric Calculations ===")

metrics_engine = MetricsEngine()
validation_state = metrics_engine.compute_validation_state(path, graph, session_start_time=0.0)

check("ValidationState is a ValidationState", isinstance(validation_state, ValidationState))
check("alignment_score between 0-1", 0 <= validation_state.path_alignment_score <= 1, f"alignment: {validation_state.path_alignment_score}")
check("deviation_score >= 0", validation_state.deviation_score >= 0, f"deviation: {validation_state.deviation_score}")
check("delay_score >= 0", validation_state.delay_score >= 0, f"delay: {validation_state.delay_score}")
check("inefficiency_score >= 0", validation_state.inefficiency_score >= 0, f"inefficiency: {validation_state.inefficiency_score}")
check("oscillation_index >= 0", validation_state.oscillation_index >= 0, f"oscillation: {validation_state.oscillation_index}")
check("nodes_visited == 4", validation_state.nodes_visited == 4, f"visited: {validation_state.nodes_visited}")
check("progress_ratio >= 0", validation_state.progress_ratio >= 0, f"progress: {validation_state.progress_ratio}")

# Test oscillation with a deliberately oscillating path
osc_path = CognitivePath()
for i, gid in enumerate(["method:heron", "method:base-height", "method:heron", "method:base-height", "method:heron"]):
    osc_path.nodes.append(CognitivePathNode(
        node_label=gid.split(":")[-1],
        mapped_graph_node_id=gid,
        source_chunk_id=f"osc_{i}",
        timestamp=float(i),
        confidence_weight=0.7,
        is_on_graph=True,
        node_type="method",
    ))
osc_index = metrics_engine.compute_oscillation_index(osc_path)
check("High oscillation for A-B-A-B-A pattern", osc_index > 0.3, f"oscillation: {osc_index}")

# Test with perfectly aligned path
perfect_path = CognitivePath()
if graph.optimal_paths:
    for i, nid in enumerate(graph.optimal_paths[0]):
        gnode = graph.get_node(nid)
        perfect_path.nodes.append(CognitivePathNode(
            node_label=gnode.label if gnode else nid,
            mapped_graph_node_id=nid,
            source_chunk_id=f"perf_{i}",
            timestamp=float(i),
            confidence_weight=0.9,
            is_on_graph=True,
            node_type=gnode.node_type if gnode else "step",
        ))
    perfect_alignment = alignment_engine.compute(perfect_path, graph)
    check("Perfect path has subsequence_ratio == 1.0", perfect_alignment.subsequence_ratio == 1.0, f"ratio: {perfect_alignment.subsequence_ratio}")
    check("Perfect path has progress_ratio == 1.0", perfect_alignment.progress_ratio == 1.0, f"progress: {perfect_alignment.progress_ratio}")


# ===========================================================================
# Summary
# ===========================================================================
print(f"\n{'='*50}")
print(f"Phase 7A Tests:  {passed} passed, {failed} failed")
print(f"{'='*50}")

sys.exit(0 if failed == 0 else 1)
