"""Graph Alignment Engine — Phase 7A.

Compares the observed CognitivePath against the expected SolutionGraph
using structure-aware comparison: subsequence matching, node overlap
scoring, and invalid-jump detection.

This is NOT string matching — it is graph-aware structural comparison.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..contracts import (
    CognitivePath,
    SolutionGraph,
)

logger = logging.getLogger("cognitive_engine.strategy_validation.graph_alignment")


@dataclass
class AlignmentResult:
    """Result of comparing a cognitive path against the solution graph."""

    # Core scores (0.0 — 1.0)
    node_overlap_ratio: float = 0.0    # fraction of observed nodes that are on-graph
    subsequence_ratio: float = 0.0     # LCS length / optimal path length
    transition_validity: float = 0.0   # fraction of transitions that are valid edges

    # Progress tracking
    optimal_nodes_reached: list[str] = field(default_factory=list)
    progress_ratio: float = 0.0        # furthest optimal step reached / total optimal steps
    current_position_in_optimal: int = 0

    # Jump tracking
    invalid_jumps: list[dict[str, str]] = field(default_factory=list)
    valid_transitions_count: int = 0
    invalid_transitions_count: int = 0

    # Composite
    overall_alignment: float = 0.0     # weighted blend of the above


class GraphAlignmentEngine:
    """Computes alignment between a CognitivePath and a SolutionGraph."""

    def compute(
        self,
        path: CognitivePath,
        graph: SolutionGraph,
    ) -> AlignmentResult:
        """Run full alignment computation and return an AlignmentResult."""
        result = AlignmentResult()

        if not path.nodes or not graph.nodes:
            return result

        # --- 1. Node overlap ratio ---
        total = len(path.nodes)
        on_graph = path.on_graph_count()
        result.node_overlap_ratio = round(on_graph / total, 4) if total > 0 else 0.0

        # --- 2. Subsequence alignment against optimal path ---
        observed_ids = [
            n.mapped_graph_node_id
            for n in path.nodes
            if n.mapped_graph_node_id is not None
        ]

        best_lcs_len = 0
        best_optimal_path: list[str] = []
        for optimal_path in graph.optimal_paths:
            lcs = self._longest_common_subsequence(observed_ids, optimal_path)
            if len(lcs) > best_lcs_len:
                best_lcs_len = len(lcs)
                best_optimal_path = optimal_path
                result.optimal_nodes_reached = lcs

        optimal_len = len(best_optimal_path) if best_optimal_path else 1
        result.subsequence_ratio = round(best_lcs_len / optimal_len, 4)

        # --- 3. Progress ratio ---
        if best_optimal_path and result.optimal_nodes_reached:
            last_reached = result.optimal_nodes_reached[-1]
            try:
                pos = best_optimal_path.index(last_reached)
                result.current_position_in_optimal = pos
                result.progress_ratio = round((pos + 1) / len(best_optimal_path), 4)
            except ValueError:
                result.progress_ratio = 0.0

        # --- 4. Transition validity ---
        valid_count = 0
        invalid_count = 0
        for transition in path.transitions:
            if transition.from_graph_id and transition.to_graph_id:
                if transition.is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
                    result.invalid_jumps.append({
                        "from": transition.from_node,
                        "to": transition.to_node,
                        "from_graph_id": transition.from_graph_id or "",
                        "to_graph_id": transition.to_graph_id or "",
                    })

        result.valid_transitions_count = valid_count
        result.invalid_transitions_count = invalid_count
        total_graph_transitions = valid_count + invalid_count
        result.transition_validity = (
            round(valid_count / total_graph_transitions, 4)
            if total_graph_transitions > 0 else 1.0
        )

        # --- 5. Overall alignment (weighted composite) ---
        result.overall_alignment = round(
            result.node_overlap_ratio * 0.30
            + result.subsequence_ratio * 0.35
            + result.transition_validity * 0.20
            + result.progress_ratio * 0.15,
            4,
        )

        logger.info(
            "Alignment computed | overlap=%.3f subseq=%.3f transitions=%.3f progress=%.3f overall=%.3f",
            result.node_overlap_ratio,
            result.subsequence_ratio,
            result.transition_validity,
            result.progress_ratio,
            result.overall_alignment,
        )
        return result

    # -----------------------------------------------------------------------
    # LCS implementation
    # -----------------------------------------------------------------------

    @staticmethod
    def _longest_common_subsequence(seq_a: list[str], seq_b: list[str]) -> list[str]:
        """Compute the longest common subsequence between two lists of strings.

        This is the classic O(m*n) DP algorithm.  Both sequences are expected
        to be short (tens of items at most), so performance is not a concern.
        """
        m, n = len(seq_a), len(seq_b)
        if m == 0 or n == 0:
            return []

        # Build DP table
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq_a[i - 1] == seq_b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        # Backtrack to find the actual subsequence
        result: list[str] = []
        i, j = m, n
        while i > 0 and j > 0:
            if seq_a[i - 1] == seq_b[j - 1]:
                result.append(seq_a[i - 1])
                i -= 1
                j -= 1
            elif dp[i - 1][j] > dp[i][j - 1]:
                i -= 1
            else:
                j -= 1

        result.reverse()
        return result
