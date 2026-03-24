"""Solution Graph Builder — Phase 7A.

Transforms a Phase 6 ProblemStructure into an enriched SolutionGraph
with node metadata (priority, expected order, prerequisites, keywords)
and adjacency list edges.  The output provides the formal target
against which a student's cognitive path is compared.
"""

from __future__ import annotations

import logging
from typing import Any

from ..contracts import (
    MethodDefinition,
    ProblemStructure,
    SolutionGraph,
    SolutionGraphNode,
)

logger = logging.getLogger("cognitive_engine.strategy_validation.solution_graph")

# ---------------------------------------------------------------------------
# Node type constants
# ---------------------------------------------------------------------------
NT_CONCEPT = "concept"
NT_METHOD = "method"
NT_STEP = "step"
NT_EQUATION = "equation"

# ---------------------------------------------------------------------------
# Priority constants
# ---------------------------------------------------------------------------
PR_CRITICAL = "critical"
PR_OPTIONAL = "optional"


def build_enriched_solution_graph(problem_structure: ProblemStructure) -> SolutionGraph:
    """Build a SolutionGraph from an existing ProblemStructure.

    This enriches the flat Phase 6 output into a formal graph with:
      - concept nodes
      - method nodes (one per valid method)
      - step nodes (ordered within each method)
      - equation nodes
      - adjacency list capturing valid transitions
      - optimal_paths and alternative_paths as ordered node-ID sequences
    """
    nodes: list[SolutionGraphNode] = []
    edges: dict[str, list[str]] = {}
    optimal_paths: list[list[str]] = []
    alternative_paths: list[list[str]] = []

    # ---- Sort methods by score to identify optimal vs alternative ----------
    sorted_methods = sorted(problem_structure.methods, key=lambda m: -m.score)
    optimal_method_name = problem_structure.optimal_path[0] if problem_structure.optimal_path else (sorted_methods[0].name if sorted_methods else None)

    # ---- Concept nodes -----------------------------------------------------
    for concept in problem_structure.concepts:
        cid = f"concept:{concept}"
        nodes.append(SolutionGraphNode(
            node_id=cid,
            label=concept.replace("_", " ").title(),
            node_type=NT_CONCEPT,
            priority=PR_CRITICAL,
            expected_order=0,
            keywords=[concept.replace("_", " ")],
        ))
        edges.setdefault(cid, [])

    # ---- Method + step + equation nodes ------------------------------------
    global_order = 1  # running counter for expected_order within the optimal path

    for method in sorted_methods:
        is_optimal = method.name == optimal_method_name
        method_id = _method_id(method.name)

        nodes.append(SolutionGraphNode(
            node_id=method_id,
            label=method.name,
            node_type=NT_METHOD,
            priority=PR_CRITICAL if is_optimal else PR_OPTIONAL,
            expected_order=global_order if is_optimal else 0,
            method_name=method.name,
            keywords=[kw.lower() for kw in method.keywords],
            metadata={"score": method.score, "requirements": method.requirements},
        ))
        edges.setdefault(method_id, [])

        # Link concepts → method
        for concept in problem_structure.concepts:
            cid = f"concept:{concept}"
            edges.setdefault(cid, [])
            if method_id not in edges[cid]:
                edges[cid].append(method_id)

        # Step nodes
        step_path: list[str] = [method_id]
        prev_step_id: str | None = None
        time_weight_per_step = 1.0 / max(len(method.steps), 1)

        for idx, step_label in enumerate(method.steps):
            step_id = f"{method_id}:step:{idx}"
            prereqs = [prev_step_id] if prev_step_id else [method_id]
            step_order = (global_order + idx + 1) if is_optimal else 0

            nodes.append(SolutionGraphNode(
                node_id=step_id,
                label=step_label.replace("_", " ").title(),
                node_type=NT_STEP,
                priority=PR_CRITICAL if is_optimal else PR_OPTIONAL,
                expected_order=step_order,
                expected_time_weight=round(time_weight_per_step, 3),
                prerequisites=prereqs,
                method_name=method.name,
                keywords=_step_keywords(step_label, method),
            ))
            edges.setdefault(step_id, [])

            # Edge from previous step (or method) to this step
            source = prev_step_id if prev_step_id else method_id
            edges.setdefault(source, [])
            if step_id not in edges[source]:
                edges[source].append(step_id)

            step_path.append(step_id)
            prev_step_id = step_id

        # Equation nodes
        for eq_idx, equation in enumerate(method.equations):
            eq_id = f"{method_id}:eq:{eq_idx}"
            nodes.append(SolutionGraphNode(
                node_id=eq_id,
                label=equation,
                node_type=NT_EQUATION,
                priority=PR_OPTIONAL,
                method_name=method.name,
                keywords=_equation_keywords(equation),
            ))
            edges.setdefault(eq_id, [])
            edges.setdefault(method_id, [])
            if eq_id not in edges[method_id]:
                edges[method_id].append(eq_id)

        # Collect path
        if is_optimal:
            optimal_paths.append(step_path)
            global_order += len(method.steps) + 1
        else:
            alternative_paths.append(step_path)

    all_node_ids = {n.node_id for n in nodes}

    graph = SolutionGraph(
        nodes=nodes,
        edges=edges,
        optimal_paths=optimal_paths,
        alternative_paths=alternative_paths,
        all_node_ids=all_node_ids,
    )

    logger.info(
        "Solution graph built | nodes=%d edges=%d optimal_paths=%d alternative_paths=%d",
        len(nodes),
        sum(len(v) for v in edges.values()),
        len(optimal_paths),
        len(alternative_paths),
    )
    return graph


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _method_id(name: str) -> str:
    return f"method:{name.lower().replace(' ', '_')}"


def _step_keywords(step_label: str, method: MethodDefinition) -> list[str]:
    """Generate keywords for a step node from column label and parent method."""
    keywords: list[str] = []
    words = step_label.replace("_", " ").lower().split()
    keywords.extend(words)
    # Add any method keyword that is a substring of the step label
    for kw in method.keywords:
        if kw.lower() in step_label.lower().replace("_", " "):
            keywords.append(kw.lower())
    return list(dict.fromkeys(keywords))


def _equation_keywords(equation: str) -> list[str]:
    """Extract searchable tokens from an equation string."""
    import re
    tokens = re.findall(r"[a-zA-Z_]+", equation.lower())
    return list(dict.fromkeys(tokens))
