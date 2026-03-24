"""Validation Logger — Phase 7B.

Structured logging layer for the strategy validation engine.
Logs every decision point with enough detail for tuning:
  - Node mapping decisions
  - Alignment scores per chunk
  - Deviation triggers with full context
  - Metric breakdowns
  - Gemini enrichment decisions
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from ..contracts import (
    CognitiveChunk,
    CognitivePath,
    CognitivePathNode,
    SolutionGraph,
    ValidationState,
)

logger = logging.getLogger("cognitive_engine.strategy_validation.validation_log")


class ValidationLogger:
    """Structured logger for strategy validation decisions."""

    def log_node_mapping(
        self,
        chunk: CognitiveChunk,
        path_node: CognitivePathNode,
        graph: SolutionGraph,
    ) -> None:
        """Log the node mapping decision for a chunk."""
        logger.info(
            "NODE_MAP | chunk=%s intent=%s transcript=%s -> node=%s graph_id=%s "
            "on_graph=%s confidence=%.3f type=%s",
            chunk.chunk_id,
            chunk.intent_refined.value,
            _truncate(chunk.transcript, 60),
            path_node.node_label,
            path_node.mapped_graph_node_id or "off_graph",
            path_node.is_on_graph,
            path_node.confidence_weight,
            path_node.node_type,
        )

    def log_alignment_update(
        self,
        chunk_id: str,
        validation_state: ValidationState,
    ) -> None:
        """Log the alignment and metric update after processing a chunk."""
        logger.info(
            "METRICS | chunk=%s alignment=%.3f deviation=%.3f delay=%.3f "
            "inefficiency=%.3f oscillation=%.3f progress=%.1f%% "
            "on_graph=%d off_graph=%d deviations=[%s]",
            chunk_id,
            validation_state.path_alignment_score,
            validation_state.deviation_score,
            validation_state.delay_score,
            validation_state.inefficiency_score,
            validation_state.oscillation_index,
            validation_state.progress_ratio * 100,
            validation_state.on_graph_nodes,
            validation_state.off_graph_nodes,
            ", ".join(validation_state.active_deviations) if validation_state.active_deviations else "none",
        )

    def log_deviation_trigger(
        self,
        chunk_id: str,
        reason: str,
        deviation_score: float,
        alignment_score: float,
        transcript: str | None = None,
    ) -> None:
        """Log when a deviation event is triggered."""
        logger.warning(
            "DEVIATION_TRIGGERED | chunk=%s reason=%s deviation=%.3f alignment=%.3f transcript=%s",
            chunk_id,
            reason,
            deviation_score,
            alignment_score,
            _truncate(transcript, 80),
        )

    def log_delay_trigger(
        self,
        chunk_id: str,
        delay_score: float,
    ) -> None:
        """Log when a delay event is triggered."""
        logger.warning(
            "DELAY_TRIGGERED | chunk=%s delay_score=%.3f",
            chunk_id,
            delay_score,
        )

    def log_inefficiency_trigger(
        self,
        chunk_id: str,
        inefficiency_score: float,
        oscillation_index: float,
    ) -> None:
        """Log when an inefficiency event is triggered."""
        logger.warning(
            "INEFFICIENCY_TRIGGERED | chunk=%s inefficiency=%.3f oscillation=%.3f",
            chunk_id,
            inefficiency_score,
            oscillation_index,
        )

    def log_path_progress(
        self,
        chunk_id: str,
        node_label: str,
        progress_ratio: float,
    ) -> None:
        """Log valid path progress."""
        logger.info(
            "PATH_PROGRESS | chunk=%s node=%s progress=%.1f%%",
            chunk_id,
            node_label,
            progress_ratio * 100,
        )

    def log_gemini_enhancement(
        self,
        added_steps: int,
        added_keywords: int,
        misconceptions: int,
        total_nodes_after: int,
    ) -> None:
        """Log Gemini graph enhancement results."""
        logger.info(
            "GEMINI_ENHANCE | added_steps=%d added_keywords=%d "
            "misconceptions=%d total_nodes=%d",
            added_steps,
            added_keywords,
            misconceptions,
            total_nodes_after,
        )

    def log_session_graph_summary(
        self,
        session_id: str,
        graph: SolutionGraph,
    ) -> None:
        """Log a summary of the solution graph at session start."""
        method_nodes = [n for n in graph.nodes if n.node_type == "method"]
        step_nodes = [n for n in graph.nodes if n.node_type == "step"]
        gemini_nodes = [n for n in graph.nodes if n.metadata.get("source") == "gemini"]
        logger.info(
            "GRAPH_SUMMARY | session=%s total_nodes=%d methods=%d steps=%d "
            "equations=%d gemini_enriched=%d optimal_paths=%d alt_paths=%d edges=%d",
            session_id,
            len(graph.nodes),
            len(method_nodes),
            len(step_nodes),
            sum(1 for n in graph.nodes if n.node_type == "equation"),
            len(gemini_nodes),
            len(graph.optimal_paths),
            len(graph.alternative_paths),
            sum(len(v) for v in graph.edges.values()),
        )

    def log_path_snapshot(
        self,
        session_id: str,
        path: CognitivePath,
    ) -> None:
        """Log a snapshot of the current cognitive path."""
        recent = path.nodes[-5:] if path.nodes else []
        labels = [f"{n.node_label}({'✓' if n.is_on_graph else '✗'})" for n in recent]
        logger.info(
            "PATH_SNAPSHOT | session=%s total=%d on=%d off=%d recent=[%s]",
            session_id,
            len(path.nodes),
            path.on_graph_count(),
            path.off_graph_count(),
            " → ".join(labels),
        )


def _truncate(text: str | None, max_len: int = 60) -> str:
    if not text:
        return "<none>"
    text = text.replace("\n", " ").strip()
    return text[:max_len] + "…" if len(text) > max_len else text


validation_logger = ValidationLogger()
