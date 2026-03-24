"""Cognitive Path Engine — Phase 7A.

Manages the evolving cognitive path during a session.  Each incoming
chunk is mapped to a graph node and appended to the path, building
an ordered, time-indexed reasoning trajectory that can be compared
against the formal solution graph.
"""

from __future__ import annotations

import logging

from ..contracts import (
    CognitivePath,
    CognitivePathNode,
    CognitivePathTransition,
    SolutionGraph,
)

logger = logging.getLogger("cognitive_engine.strategy_validation.cognitive_path")


class CognitivePathEngine:
    """Stateless engine that operates on a CognitivePath stored in session state."""

    def add_node(
        self,
        path: CognitivePath,
        node: CognitivePathNode,
        solution_graph: SolutionGraph | None = None,
    ) -> CognitivePath:
        """Append a node to the cognitive path and record the transition.

        The CognitivePath is a Pydantic model; this returns the same
        instance after mutation (session state owns the object).
        """
        # Record the transition from the previous node
        if path.nodes:
            prev = path.nodes[-1]
            is_valid = False
            if (
                solution_graph
                and prev.mapped_graph_node_id
                and node.mapped_graph_node_id
            ):
                is_valid = solution_graph.is_valid_transition(
                    prev.mapped_graph_node_id, node.mapped_graph_node_id
                )

            transition = CognitivePathTransition(
                from_node=prev.node_label,
                to_node=node.node_label,
                from_graph_id=prev.mapped_graph_node_id,
                to_graph_id=node.mapped_graph_node_id,
                time_delta=round(max(node.timestamp - prev.timestamp, 0.0), 3),
                is_valid=is_valid,
            )
            path.transitions.append(transition)

        path.nodes.append(node)

        logger.debug(
            "Path updated | nodes=%d on_graph=%d off_graph=%d latest=%s (graph_id=%s)",
            len(path.nodes),
            path.on_graph_count(),
            path.off_graph_count(),
            node.node_label,
            node.mapped_graph_node_id or "off_graph",
        )
        return path

    def get_on_graph_sequence(self, path: CognitivePath) -> list[str]:
        """Return the ordered list of mapped graph node IDs (skipping off-graph)."""
        return [
            n.mapped_graph_node_id
            for n in path.nodes
            if n.mapped_graph_node_id is not None
        ]

    def get_unique_methods_visited(self, path: CognitivePath) -> set[str]:
        """Extract the set of distinct method branches the student has touched."""
        methods: set[str] = set()
        for node in path.nodes:
            if node.mapped_graph_node_id and node.mapped_graph_node_id.startswith("method:"):
                methods.add(node.mapped_graph_node_id)
            elif node.mapped_graph_node_id and ":step:" in node.mapped_graph_node_id:
                method_part = node.mapped_graph_node_id.rsplit(":step:", 1)[0]
                methods.add(method_part)
        return methods

    def get_last_n_labels(self, path: CognitivePath, n: int = 5) -> list[str]:
        """Return the last N node labels from the path."""
        return [node.node_label for node in path.nodes[-n:]]
