"""Metric Calculators — Phase 7A.

Computes the five quantitative cognitive metrics from the CognitivePath
and SolutionGraph.  Every metric is deterministic and explainable.
No LLM calls are involved.

Metrics:
  1. deviation_score    — how far the user path diverges from valid graph nodes
  2. delay_score        — latency in reaching critical nodes
  3. inefficiency_score — unnecessary exploration
  4. oscillation_index  — instability in thinking
  5. path_alignment_score — overall alignment with optimal path
"""

from __future__ import annotations

import logging
from collections import Counter

from ..contracts import (
    CognitivePath,
    CognitivePathNode,
    SolutionGraph,
    ValidationState,
)
from .graph_alignment import AlignmentResult, GraphAlignmentEngine

logger = logging.getLogger("cognitive_engine.strategy_validation.metrics")

_alignment_engine = GraphAlignmentEngine()


class MetricsEngine:
    """Computes all five cognitive metrics plus a composite ValidationState."""

    def compute_validation_state(
        self,
        path: CognitivePath,
        graph: SolutionGraph,
        session_start_time: float = 0.0,
    ) -> ValidationState:
        """Compute the full ValidationState from the current path and graph."""
        alignment = _alignment_engine.compute(path, graph)

        deviation = self.compute_deviation_score(path, graph, alignment)
        delay = self.compute_delay_score(path, graph, session_start_time)
        inefficiency = self.compute_inefficiency_score(path, graph)
        oscillation = self.compute_oscillation_index(path)
        path_alignment = self.compute_path_alignment_score(alignment)

        active_deviations = self._collect_active_deviations(
            deviation, delay, inefficiency, oscillation, path, graph
        )

        state = ValidationState(
            path_alignment_score=round(path_alignment, 4),
            deviation_score=round(deviation, 4),
            delay_score=round(delay, 4),
            inefficiency_score=round(inefficiency, 4),
            oscillation_index=round(oscillation, 4),
            nodes_visited=len(path.nodes),
            on_graph_nodes=path.on_graph_count(),
            off_graph_nodes=path.off_graph_count(),
            progress_ratio=round(alignment.progress_ratio, 4),
            active_deviations=active_deviations,
        )

        logger.info(
            "ValidationState computed | alignment=%.3f deviation=%.3f delay=%.3f "
            "inefficiency=%.3f oscillation=%.3f progress=%.3f deviations=%s",
            state.path_alignment_score,
            state.deviation_score,
            state.delay_score,
            state.inefficiency_score,
            state.oscillation_index,
            state.progress_ratio,
            ",".join(state.active_deviations) if state.active_deviations else "none",
        )
        return state

    # -----------------------------------------------------------------------
    # Individual metric calculators
    # -----------------------------------------------------------------------

    def compute_deviation_score(
        self,
        path: CognitivePath,
        graph: SolutionGraph,
        alignment: AlignmentResult | None = None,
    ) -> float:
        """Measure how far the user path diverges from valid graph nodes.

        Factors:
          - Ratio of off-graph nodes (weighted by confidence)
          - Number of invalid transitions
          - Inverse of alignment score
        """
        if not path.nodes:
            return 0.0

        if alignment is None:
            alignment = _alignment_engine.compute(path, graph)

        total = len(path.nodes)

        # Weighted off-graph ratio
        off_graph_weight = sum(
            1.0 - n.confidence_weight
            for n in path.nodes
            if not n.is_on_graph
        )
        off_graph_ratio = off_graph_weight / total if total > 0 else 0.0

        # Invalid transition penalty
        invalid_ratio = (
            alignment.invalid_transitions_count
            / max(alignment.valid_transitions_count + alignment.invalid_transitions_count, 1)
        )

        # Inverse alignment (low alignment → high deviation)
        alignment_penalty = max(0.0, 1.0 - alignment.overall_alignment)

        score = (
            off_graph_ratio * 0.40
            + invalid_ratio * 0.30
            + alignment_penalty * 0.30
        )
        if len(path.nodes) <= 3:
            score *= 0.55
        elif len(path.nodes) <= 5:
            score *= 0.75
        return min(max(score, 0.0), 1.0)

    def compute_delay_score(
        self,
        path: CognitivePath,
        graph: SolutionGraph,
        session_start_time: float = 0.0,
    ) -> float:
        """Measure latency in reaching critical nodes.

        Factors:
          - Time to first valid strategy/method node
          - Time spent in understanding/silence before key transitions
          - Proportion of path spent before first on-graph step node
        """
        if not path.nodes:
            return 0.0

        first_strategy_time: float | None = None
        first_step_time: float | None = None
        total_time = path.nodes[-1].timestamp - session_start_time if path.nodes else 0.0

        for node in path.nodes:
            if node.is_on_graph and node.node_type == "method" and first_strategy_time is None:
                first_strategy_time = node.timestamp - session_start_time
            if node.is_on_graph and node.node_type == "step" and first_step_time is None:
                first_step_time = node.timestamp - session_start_time

        if total_time <= 0:
            return 0.0

        # Strategy delay: fraction of total time before first method node
        strategy_delay_ratio = 0.0
        if first_strategy_time is not None:
            strategy_delay_ratio = first_strategy_time / total_time
        elif total_time > 0:
            strategy_delay_ratio = 1.0  # never reached a strategy

        # Execution delay: fraction of total time before first step node
        step_delay_ratio = 0.0
        if first_step_time is not None:
            step_delay_ratio = first_step_time / total_time
        elif total_time > 0:
            step_delay_ratio = 1.0

        # Silence / understanding heavy segments early on
        early_nodes = path.nodes[:max(len(path.nodes) // 3, 1)]
        silence_heavy = sum(
            1 for n in early_nodes
            if n.intent.value in {"silence_reflection", "unknown"}
        )
        silence_ratio = silence_heavy / len(early_nodes) if early_nodes else 0.0

        score = (
            strategy_delay_ratio * 0.40
            + step_delay_ratio * 0.35
            + silence_ratio * 0.25
        )
        if len(path.nodes) <= 3:
            score *= 0.7
        return min(max(score, 0.0), 1.0)

    def compute_inefficiency_score(
        self,
        path: CognitivePath,
        graph: SolutionGraph,
    ) -> float:
        """Measure unnecessary exploration.

        Factors:
          - Number of distinct method branches attempted
          - Repeated visits to the same node
          - Redundant reasoning (visiting a node after it was already completed)
        """
        if not path.nodes:
            return 0.0

        # Distinct methods tried
        methods_touched: set[str] = set()
        for node in path.nodes:
            gid = node.mapped_graph_node_id
            if gid:
                if gid.startswith("method:"):
                    methods_touched.add(gid)
                elif ":step:" in gid:
                    methods_touched.add(gid.rsplit(":step:", 1)[0])

        # Optimal should be 1 method
        optimal_count = len(graph.optimal_paths)
        extra_methods = max(0, len(methods_touched) - max(optimal_count, 1))
        method_penalty = min(extra_methods * 0.20, 0.50)

        # Repeated node visits
        label_counts = Counter(n.node_label for n in path.nodes if n.is_on_graph)
        repeated_visits = sum(c - 1 for c in label_counts.values() if c > 1)
        repeated_ratio = repeated_visits / max(len(path.nodes), 1)
        repeated_penalty = min(repeated_ratio, 0.30)

        # Redundant off-graph detours between valid nodes
        total = len(path.nodes)
        off_graph_between_valid = 0
        in_valid_sequence = False
        for node in path.nodes:
            if node.is_on_graph:
                in_valid_sequence = True
            elif in_valid_sequence:
                off_graph_between_valid += 1

        detour_ratio = off_graph_between_valid / max(total, 1)
        detour_penalty = min(detour_ratio, 0.30)

        score = method_penalty + repeated_penalty + detour_penalty
        if len(path.nodes) <= 4:
            score *= 0.7
        return min(max(score, 0.0), 1.0)

    def compute_oscillation_index(self, path: CognitivePath) -> float:
        """Measure instability in thinking.

        Counts switches between different method branches.  Repeated
        switching (A→B→A→B) scores higher than a single switch (A→B).
        """
        if len(path.nodes) < 3:
            return 0.0

        method_sequence: list[str] = []
        for node in path.nodes:
            gid = node.mapped_graph_node_id
            if not gid:
                continue
            if gid.startswith("method:"):
                branch = gid
            elif ":step:" in gid:
                branch = gid.rsplit(":step:", 1)[0]
            else:
                continue
            method_sequence.append(branch)

        if len(method_sequence) < 2:
            return 0.0

        # Count direction changes
        switches = 0
        for i in range(1, len(method_sequence)):
            if method_sequence[i] != method_sequence[i - 1]:
                switches += 1

        # Normalize: max_switches = len - 1
        max_switches = len(method_sequence) - 1
        raw_ratio = switches / max_switches if max_switches > 0 else 0.0

        # Penalize rapid back-and-forth oscillation more heavily
        back_and_forths = 0
        for i in range(2, len(method_sequence)):
            if (
                method_sequence[i] == method_sequence[i - 2]
                and method_sequence[i] != method_sequence[i - 1]
            ):
                back_and_forths += 1

        bf_penalty = min(back_and_forths * 0.15, 0.40)

        score = raw_ratio * 0.60 + bf_penalty
        if len(method_sequence) <= 3:
            score *= 0.65
        return min(max(score, 0.0), 1.0)

    def compute_path_alignment_score(self, alignment: AlignmentResult) -> float:
        """Return the overall alignment score (0.0 — 1.0)."""
        return min(max(alignment.overall_alignment, 0.0), 1.0)

    # -----------------------------------------------------------------------
    # Deviation classification
    # -----------------------------------------------------------------------

    def _collect_active_deviations(
        self,
        deviation: float,
        delay: float,
        inefficiency: float,
        oscillation: float,
        path: CognitivePath,
        graph: SolutionGraph,
    ) -> list[str]:
        """Build a list of human-readable deviation reasons."""
        reasons: list[str] = []

        if deviation >= 0.45:
            # Determine if hard or soft
            off_graph = path.off_graph_count()
            if off_graph > 0 and (off_graph / max(len(path.nodes), 1)) > 0.40:
                reasons.append("hard_deviation:off_graph_reasoning")
            else:
                reasons.append("soft_deviation:low_alignment")

        if delay >= 0.50:
            reasons.append("temporal_deviation:delayed_strategy_selection")

        if inefficiency >= 0.40:
            reasons.append("inefficiency:excessive_method_switching")

        if oscillation >= 0.35:
            reasons.append("oscillation:unstable_thinking")

        return reasons
