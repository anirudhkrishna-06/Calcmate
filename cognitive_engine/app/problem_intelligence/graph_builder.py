from __future__ import annotations

from ..contracts import GraphEdge, GraphNode, MethodDefinition, SymbolicRepresentation


def build_solution_graph(concepts: list[str], methods: list[MethodDefinition], equations: list[str]) -> SymbolicRepresentation:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    for concept in concepts:
        concept_id = f"concept:{concept}"
        nodes.append(GraphNode(node_id=concept_id, label=concept, node_type="concept"))

    for method in methods:
        method_node_id = f"method:{method.name.lower().replace(' ', '_')}"
        nodes.append(
            GraphNode(
                node_id=method_node_id,
                label=method.name,
                node_type="method",
                metadata={"requirements": method.requirements, "score": method.score, "keywords": method.keywords},
            )
        )
        for concept in concepts:
            edges.append(GraphEdge(source=f"concept:{concept}", target=method_node_id, relation="solvable_by"))

        previous_step_id = None
        for index, step in enumerate(method.steps):
            step_id = f"{method_node_id}:step:{index}"
            nodes.append(GraphNode(node_id=step_id, label=step, node_type="step", metadata={"method": method.name}))
            edges.append(GraphEdge(source=method_node_id, target=step_id, relation="contains"))
            if previous_step_id is not None:
                edges.append(GraphEdge(source=previous_step_id, target=step_id, relation="depends_on"))
            previous_step_id = step_id

        for equation in method.equations:
            equation_id = f"equation:{abs(hash((method.name, equation)))}"
            nodes.append(GraphNode(node_id=equation_id, label=equation, node_type="equation", metadata={"method": method.name}))
            edges.append(GraphEdge(source=method_node_id, target=equation_id, relation="uses_equation"))

    seen_equations: set[str] = set()
    previous_equation_id: str | None = None
    for equation in equations:
        equation_id = f"equation:global:{abs(hash(equation))}"
        if equation_id not in seen_equations:
            nodes.append(GraphNode(node_id=equation_id, label=equation, node_type="equation_global"))
            seen_equations.add(equation_id)
        if previous_equation_id is not None:
            edges.append(GraphEdge(source=previous_equation_id, target=equation_id, relation="derives"))
        previous_equation_id = equation_id

    return SymbolicRepresentation(type="graph", equations=equations, wl_subtrees=[], nodes=nodes, edges=edges)
