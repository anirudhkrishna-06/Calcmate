"""Node Mapper — Phase 7A.

Maps incoming CognitiveChunks (intent, keywords, transcript) to
SolutionGraphNodes.  This is the bridge between the semantic layer
(what the student said) and the structural layer (where they are
in the solution graph).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..contracts import (
    CognitiveChunk,
    CognitiveIntent,
    CognitivePathNode,
    ProblemStructure,
    SolutionGraph,
    SolutionGraphNode,
)

logger = logging.getLogger("cognitive_engine.strategy_validation.node_mapper")

# ---------------------------------------------------------------------------
# Intent → concept type mapping
# ---------------------------------------------------------------------------
INTENT_CONCEPT_MAP: dict[CognitiveIntent, str] = {
    CognitiveIntent.PROBLEM_UNDERSTANDING: "concept",
    CognitiveIntent.PARAMETER_RECOGNITION: "concept",
    CognitiveIntent.CONCEPTUAL_EXPLANATION: "concept",
    CognitiveIntent.WORKING_MEMORY_RETRIEVAL: "concept",
    CognitiveIntent.STRATEGY_SELECTION: "method",
    CognitiveIntent.COMPARISON_ANALYSIS: "method",
    CognitiveIntent.EXECUTION_START: "step",
    CognitiveIntent.VERIFICATION: "step",
    CognitiveIntent.SOLUTION_SUMMARY: "step",
    CognitiveIntent.ERROR_CORRECTION: "step",
}


class NodeMapper:
    """Maps a CognitiveChunk to a CognitivePathNode using the SolutionGraph."""

    def map_chunk(
        self,
        chunk: CognitiveChunk,
        solution_graph: SolutionGraph,
        problem_structure: ProblemStructure | None = None,
    ) -> CognitivePathNode:
        """Map a single chunk to its best-matching solution graph node.

        Returns a CognitivePathNode with `mapped_graph_node_id` set to
        the matching SolutionGraphNode's ID, or None if off-graph.
        """
        transcript = (chunk.transcript or "").lower().strip()
        signals = chunk.semantic_signals
        intent = chunk.intent_refined

        # Skip pure silence / filler
        if not transcript or signals.filler_only:
            return self._off_graph_node(chunk, reason="silence_or_filler")

        # Build candidate scores for every node in the graph
        best_node: SolutionGraphNode | None = None
        best_score: float = 0.0

        for node in solution_graph.nodes:
            score = self._score_match(node, chunk, transcript, signals, intent)
            if score > best_score:
                best_score = score
                best_node = node

        # Minimum threshold to consider a match valid
        if best_node is None or best_score < 0.15:
            if (
                chunk.exploration_valid
                or intent in {CognitiveIntent.STRATEGY_SELECTION, CognitiveIntent.COMPARISON_ANALYSIS, CognitiveIntent.META_COGNITION}
            ):
                fallback = self._strategy_fallback_node(chunk, solution_graph)
                if fallback is not None:
                    return fallback
            return self._off_graph_node(chunk, reason="no_match")

        logger.debug(
            "Node mapped | chunk=%s -> node=%s (score=%.3f)",
            chunk.chunk_id, best_node.node_id, best_score,
        )

        return CognitivePathNode(
            node_label=best_node.label,
            mapped_graph_node_id=best_node.node_id,
            source_chunk_id=chunk.chunk_id,
            timestamp=chunk.timestamp.end_time,
            confidence_weight=round(min(chunk.confidence * best_score, 1.0), 3),
            intent=intent,
            is_on_graph=True,
            node_type=best_node.node_type,
        )

    # -----------------------------------------------------------------------
    # Scoring logic
    # -----------------------------------------------------------------------

    def _score_match(
        self,
        node: SolutionGraphNode,
        chunk: CognitiveChunk,
        transcript: str,
        signals: Any,
        intent: CognitiveIntent,
    ) -> float:
        """Score how well a chunk matches a given solution graph node."""
        score = 0.0

        # 1) Keyword overlap — strongest signal
        keyword_hits = sum(
            1 for kw in node.keywords if kw and kw.lower() in transcript
        )
        if node.keywords:
            score += (keyword_hits / len(node.keywords)) * 0.40

        # 2) Problem keyword hits overlap with node keywords
        problem_kw_hits = set(
            kw.lower() for kw in (signals.problem_keyword_hits or [])
        )
        node_kw_set = set(kw.lower() for kw in node.keywords)
        overlap = len(problem_kw_hits & node_kw_set)
        if node_kw_set:
            score += (overlap / len(node_kw_set)) * 0.20

        # 3) Intent → node type alignment
        expected_type = INTENT_CONCEPT_MAP.get(intent)
        if expected_type and expected_type == node.node_type:
            score += 0.15

        # 4) Concept overlap from semantic signals
        concept_hits = sum(
            1 for c in (signals.concepts or [])
            if c.lower().replace("_", " ") in (node.label.lower() or "")
            or any(c.lower() in kw for kw in node.keywords)
        )
        if concept_hits > 0:
            score += min(concept_hits * 0.08, 0.20)

        # 5) Formula reference match
        if signals.formula_references and node.node_type == "equation":
            for ref in signals.formula_references:
                if ref.lower() in node.label.lower():
                    score += 0.15
                    break

        # 6) Direct label substring match in transcript
        label_lower = node.label.lower().replace("_", " ")
        if len(label_lower) > 3 and label_lower in transcript:
            score += 0.15

        return min(score, 1.0)

    # -----------------------------------------------------------------------
    # Off-graph node
    # -----------------------------------------------------------------------

    def _off_graph_node(self, chunk: CognitiveChunk, reason: str) -> CognitivePathNode:
        """Create an off-graph cognitive path node."""
        return CognitivePathNode(
            node_label=f"off_graph:{reason}",
            mapped_graph_node_id=None,
            source_chunk_id=chunk.chunk_id,
            timestamp=chunk.timestamp.end_time,
            confidence_weight=round(chunk.confidence * 0.3, 3),
            intent=chunk.intent_refined,
            is_on_graph=False,
            node_type="off_graph",
        )

    def _strategy_fallback_node(
        self,
        chunk: CognitiveChunk,
        solution_graph: SolutionGraph,
    ) -> CognitivePathNode | None:
        method_nodes = [node for node in solution_graph.nodes if node.node_type == "method"]
        if not method_nodes:
            return None
        target = next((node for node in method_nodes if node.priority == "critical"), method_nodes[0])
        return CognitivePathNode(
            node_label=f"{target.label} (exploration)",
            mapped_graph_node_id=target.node_id,
            source_chunk_id=chunk.chunk_id,
            timestamp=chunk.timestamp.end_time,
            confidence_weight=round(max(chunk.confidence * 0.45, 0.18), 3),
            intent=chunk.intent_refined,
            is_on_graph=True,
            node_type=target.node_type,
        )
