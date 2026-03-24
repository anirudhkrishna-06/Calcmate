"""Phase 7 — Strategy Validation Engine.

Provides trajectory evaluation against a formal solution graph,
including node mapping, cognitive path tracking, graph alignment,
quantitative metric computation, Gemini-powered graph enhancement,
and structured validation logging.
"""

from .solution_graph import build_enriched_solution_graph
from .node_mapper import NodeMapper
from .cognitive_path import CognitivePathEngine
from .graph_alignment import GraphAlignmentEngine
from .metrics import MetricsEngine
from .gemini_enhancer import gemini_graph_enhancer
from .validation_logger import validation_logger

__all__ = [
    "build_enriched_solution_graph",
    "NodeMapper",
    "CognitivePathEngine",
    "GraphAlignmentEngine",
    "MetricsEngine",
    "gemini_graph_enhancer",
    "validation_logger",
]
