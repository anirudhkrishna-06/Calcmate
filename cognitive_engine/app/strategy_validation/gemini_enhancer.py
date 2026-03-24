"""Gemini Graph Enhancer — Phase 7B.

Uses the Gemini LLM to enrich the SolutionGraph at session start.
This is a controlled, non-fragile use of LLM power:
  - Input: problem text, concepts, methods, equations
  - Output: refined solution steps, alternative valid paths,
            node relationships, edge justifications
  - All output is validated and normalized before entering the graph

Important: Gemini output is NEVER trusted blindly. Every enrichment
is validated against the existing rule-based graph before merging.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..config import get_settings
from ..contracts import (
    ProblemStructure,
    SolutionGraph,
    SolutionGraphNode,
)

logger = logging.getLogger("cognitive_engine.strategy_validation.gemini_enhancer")

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------
GRAPH_ENHANCEMENT_PROMPT = """You are a math education expert. Given a math problem and its structural analysis, enhance the solution graph with:

1. **additional_steps**: Any missing intermediate reasoning steps that a student would need (max 5). Each step must have: label, node_type (one of: concept, step, operation, inference), method_name, keywords (list of 3-6 words a student might say).

2. **alternative_paths**: Up to 2 valid alternative solution approaches not already listed. Each has: method_name, steps (list of step labels), keywords.

3. **edge_justifications**: For the optimal method, explain WHY each step follows from the previous (max 5). Each has: from_step, to_step, justification.

4. **common_misconceptions**: Up to 3 common wrong approaches students try. Each has: description, keywords_that_indicate_it.

5. **critical_keywords**: Up to 10 additional keywords/phrases a student might say that map to valid steps.

Problem: {problem_text}
Domain: {domain}
Concepts: {concepts}
Methods: {methods}
Optimal method: {optimal_method}
Equations: {equations}

Return ONLY valid JSON with keys: additional_steps, alternative_paths, edge_justifications, common_misconceptions, critical_keywords.
"""


class GeminiGraphEnhancer:
    """Calls Gemini to enrich a SolutionGraph with LLM-derived insights."""

    def __init__(self) -> None:
        self.settings = get_settings().gemini

    def enabled(self) -> bool:
        return self.settings.graph_enhancement_enabled and bool(self.settings.api_key)

    async def enhance(
        self,
        problem_structure: ProblemStructure,
        solution_graph: SolutionGraph,
    ) -> SolutionGraph:
        """Enhance the solution graph with Gemini-derived enrichments.

        Returns the same graph (mutated) with additions merged in.
        If Gemini is disabled or fails, returns the graph unchanged.
        """
        if not self.enabled():
            logger.info("Gemini graph enhancement skipped (disabled)")
            return solution_graph

        prompt = self._build_prompt(problem_structure)
        raw_output = await self._call_gemini(prompt)
        if raw_output is None:
            return solution_graph

        parsed = self._parse_response(raw_output)
        if parsed is None:
            return solution_graph

        # Validate and merge enrichments
        self._merge_additional_steps(parsed, solution_graph, problem_structure)
        self._merge_critical_keywords(parsed, solution_graph)
        self._merge_alternative_paths(parsed, solution_graph)
        self._store_misconceptions(parsed, solution_graph)
        self._store_edge_justifications(parsed, solution_graph)

        logger.info(
            "Gemini graph enhancement completed | nodes=%d edges=%d",
            len(solution_graph.nodes),
            sum(len(v) for v in solution_graph.edges.values()),
        )
        return solution_graph

    # -----------------------------------------------------------------------
    # Prompt building
    # -----------------------------------------------------------------------

    def _build_prompt(self, ps: ProblemStructure) -> str:
        methods_info = []
        all_equations = []
        for m in ps.methods:
            methods_info.append(f"{m.name} (score={m.score}, steps={m.steps})")
            all_equations.extend(m.equations)

        return GRAPH_ENHANCEMENT_PROMPT.format(
            problem_text=ps.parsing_summary.get("raw_text", "")
            or ", ".join(ps.concepts),
            domain=ps.domain or "general_math",
            concepts=", ".join(ps.concepts),
            methods="; ".join(methods_info),
            optimal_method=ps.optimal_path[0] if ps.optimal_path else "undetermined",
            equations="; ".join(all_equations) if all_equations else "none",
        )

    # -----------------------------------------------------------------------
    # Gemini API call
    # -----------------------------------------------------------------------

    async def _call_gemini(self, prompt: str) -> str | None:
        url = self.settings.base_url_template.format(model=self.settings.model)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        try:
            timeout = max(self.settings.timeout_seconds, 5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url, params={"key": self.settings.api_key}, json=body
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException:
            logger.warning("Gemini graph enhancement timed out")
            return None
        except Exception as exc:
            logger.exception("Gemini graph enhancement failed | error=%s", exc)
            return None

        # Extract text
        for candidate in payload.get("candidates", []):
            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                text = part.get("text")
                if text:
                    return text
        return None

    # -----------------------------------------------------------------------
    # Response parsing
    # -----------------------------------------------------------------------

    def _parse_response(self, raw: str) -> dict[str, Any] | None:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    pass
        logger.warning("Failed to parse Gemini graph enhancement response")
        return None

    # -----------------------------------------------------------------------
    # Merge logic (with validation)
    # -----------------------------------------------------------------------

    def _merge_additional_steps(
        self,
        parsed: dict[str, Any],
        graph: SolutionGraph,
        ps: ProblemStructure,
    ) -> None:
        """Add valid additional steps from Gemini to the graph."""
        steps = parsed.get("additional_steps", [])
        if not isinstance(steps, list):
            return

        valid_methods = {m.name.lower() for m in ps.methods}
        added = 0

        for step in steps[:5]:  # cap at 5
            if not isinstance(step, dict):
                continue
            label = str(step.get("label", "")).strip()
            method_name = str(step.get("method_name", "")).strip()
            node_type = str(step.get("node_type", "step")).strip()
            keywords = step.get("keywords", [])

            if not label or not method_name:
                continue
            # Validate: method must exist in our graph
            if method_name.lower() not in valid_methods:
                logger.debug("Rejected Gemini step '%s' — method '%s' not in valid set", label, method_name)
                continue
            # Check for duplicate
            if any(n.label.lower() == label.lower() for n in graph.nodes):
                continue
            # Validate node_type
            if node_type not in {"concept", "step", "operation", "inference"}:
                node_type = "step"

            node_id = f"gemini:{method_name.lower().replace(' ', '_')}:{label.lower().replace(' ', '_')}"
            new_node = SolutionGraphNode(
                node_id=node_id,
                label=label,
                node_type=node_type,
                priority="optional",
                method_name=method_name,
                keywords=[str(k).lower() for k in keywords if isinstance(k, str)][:6],
                metadata={"source": "gemini"},
            )
            graph.nodes.append(new_node)
            graph.all_node_ids.add(node_id)
            graph.edges.setdefault(node_id, [])

            # Link to parent method
            method_id = f"method:{method_name.lower().replace(' ', '_')}"
            if method_id in graph.edges:
                graph.edges[method_id].append(node_id)
            added += 1

        if added:
            logger.info("Merged %d additional steps from Gemini", added)

    def _merge_critical_keywords(
        self,
        parsed: dict[str, Any],
        graph: SolutionGraph,
    ) -> None:
        """Add new keywords to existing nodes."""
        keywords = parsed.get("critical_keywords", [])
        if not isinstance(keywords, list):
            return

        for kw in keywords[:10]:
            kw_str = str(kw).lower().strip()
            if not kw_str or len(kw_str) < 2:
                continue
            # Add to nodes that have the most keyword overlap
            best_node = None
            best_overlap = 0
            for node in graph.nodes:
                overlap = sum(1 for existing in node.keywords if existing in kw_str or kw_str in existing)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_node = node
            if best_node and kw_str not in best_node.keywords:
                best_node.keywords.append(kw_str)

    def _merge_alternative_paths(
        self,
        parsed: dict[str, Any],
        graph: SolutionGraph,
    ) -> None:
        """Record alternative paths from Gemini (without adding nodes for unknown methods)."""
        alt_paths = parsed.get("alternative_paths", [])
        if not isinstance(alt_paths, list):
            return

        for alt in alt_paths[:2]:
            if not isinstance(alt, dict):
                continue
            method_name = str(alt.get("method_name", "")).strip()
            if not method_name:
                continue
            # Only record if the method already exists in our graph
            method_id = f"method:{method_name.lower().replace(' ', '_')}"
            if graph.is_on_graph(method_id):
                step_ids = [
                    n.node_id for n in graph.nodes
                    if n.method_name and n.method_name.lower() == method_name.lower()
                       and n.node_type == "step"
                ]
                if step_ids:
                    path = [method_id] + step_ids
                    if path not in graph.alternative_paths:
                        graph.alternative_paths.append(path)

    def _store_misconceptions(
        self,
        parsed: dict[str, Any],
        graph: SolutionGraph,
    ) -> None:
        """Store common misconceptions as off-graph metadata on the graph."""
        misconceptions = parsed.get("common_misconceptions", [])
        if not isinstance(misconceptions, list):
            return

        validated = []
        for m in misconceptions[:3]:
            if not isinstance(m, dict):
                continue
            desc = str(m.get("description", "")).strip()
            keywords = m.get("keywords_that_indicate_it", [])
            if desc:
                validated.append({
                    "description": desc,
                    "keywords": [str(k).lower() for k in keywords if isinstance(k, str)][:5],
                })

        if validated:
            # Store as metadata on a virtual node
            misconception_node = SolutionGraphNode(
                node_id="meta:common_misconceptions",
                label="Common Misconceptions",
                node_type="inference",
                priority="optional",
                keywords=[],
                metadata={"source": "gemini", "misconceptions": validated},
            )
            # Only add if not already present
            if not graph.is_on_graph("meta:common_misconceptions"):
                graph.nodes.append(misconception_node)
                graph.all_node_ids.add("meta:common_misconceptions")

    def _store_edge_justifications(
        self,
        parsed: dict[str, Any],
        graph: SolutionGraph,
    ) -> None:
        """Store edge justifications as metadata on existing step nodes."""
        justifications = parsed.get("edge_justifications", [])
        if not isinstance(justifications, list):
            return

        for j in justifications[:5]:
            if not isinstance(j, dict):
                continue
            to_step = str(j.get("to_step", "")).strip().lower()
            justification = str(j.get("justification", "")).strip()
            if not to_step or not justification:
                continue
            # Find matching node
            for node in graph.nodes:
                if node.label.lower().replace(" ", "_") == to_step.replace(" ", "_"):
                    node.metadata["edge_justification"] = justification
                    break


gemini_graph_enhancer = GeminiGraphEnhancer()
