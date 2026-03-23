from __future__ import annotations

import hashlib
import re
from typing import Any

from ..contracts import MethodDefinition, ProblemPayload, ProblemStructure
from .concept_mapper import detect_concepts_from_text, map_concepts
from .gemini_parser import gemini_problem_parser
from .graph_builder import build_solution_graph
from .method_library import METHOD_LIBRARY
from .symbolic_builder import build_symbolic_representation

NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
EQUATION_PATTERN = re.compile(r"[^\n=]+=[^\n=]+")
RATIO_PATTERN = re.compile(r"(\d+)\s*:\s*(\d+)")
PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
WORD_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]*")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "find", "for", "from", "has", "have", "if", "in", "into", "is", "it", "its", "of", "on", "or", "the", "their", "there", "these", "this", "to", "what", "which", "with", "one", "two", "three",
}


class ProblemStructuringPipeline:
    def __init__(self) -> None:
        self._cache: dict[str, ProblemStructure] = {}

    async def build(self, problem_payload: ProblemPayload) -> ProblemStructure:
        cache_key = self._hash_problem(problem_payload.raw_text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        parsed = await self._parse_problem(problem_payload.raw_text)
        concept_mapping = map_concepts(parsed)
        methods = self._enumerate_methods(concept_mapping.get("concepts", []), parsed)
        optimal_path = self._select_optimal(methods)
        equations, wl_subtrees = build_symbolic_representation(methods)
        representation = build_solution_graph(concept_mapping.get("concepts", []), methods, equations)
        representation.wl_subtrees = wl_subtrees
        keyword_bank = self._build_keyword_bank(parsed, concept_mapping, methods, problem_payload.raw_text)

        structure = ProblemStructure(
            problem_id=problem_payload.problem_id,
            domain=concept_mapping.get("domain"),
            concepts=concept_mapping.get("concepts", []),
            parameters=parsed.get("parameters", {}),
            constraints=parsed.get("constraints", []),
            methods=methods,
            optimal_path=optimal_path,
            representation=representation,
            parsing_summary={
                "entities": parsed.get("entities", []),
                "goal": parsed.get("goal"),
                "hints": parsed.get("hints", []),
                "parser": parsed.get("parser", "rule_based"),
                "allowed_terms": concept_mapping.get("allowed_terms", []),
                "detected_concepts": detect_concepts_from_text(problem_payload.raw_text),
            },
            keyword_bank=keyword_bank,
        )
        self._cache[cache_key] = structure
        return structure

    async def _parse_problem(self, problem_text: str) -> dict[str, Any]:
        llm_result = await gemini_problem_parser.parse(problem_text)
        if llm_result:
            llm_result.setdefault("raw_text", problem_text)
            llm_result.setdefault("parser", "gemini")
            llm_result.setdefault("parameters", self._extract_parameters(problem_text))
            llm_result.setdefault("constraints", self._extract_constraints(problem_text))
            llm_result.setdefault("goal", self._extract_goal(problem_text))
            llm_result.setdefault("entities", self._extract_entities(problem_text))
            llm_result.setdefault("hints", self._extract_hints(problem_text, llm_result.get("parameters", {}), llm_result.get("goal")))
            return llm_result

        parameters = self._extract_parameters(problem_text)
        goal = self._extract_goal(problem_text)
        return {
            "raw_text": problem_text,
            "entities": self._extract_entities(problem_text),
            "goal": goal,
            "hints": self._extract_hints(problem_text, parameters, goal),
            "parameters": parameters,
            "constraints": self._extract_constraints(problem_text),
            "keyword_bank": [],
            "parser": "rule_based",
        }

    def _extract_entities(self, text: str) -> list[str]:
        entities = NUMBER_PATTERN.findall(text)
        entities.extend(detect_concepts_from_text(text))
        entities.extend(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
        return list(dict.fromkeys(entities))

    def _extract_goal(self, text: str) -> str:
        lowered = text.lower()
        goal_patterns = [
            ("find its area", "find area"),
            ("find the area", "find area"),
            ("find the perimeter", "find perimeter"),
            ("find the probability", "find probability"),
            ("find the mean", "find mean"),
            ("find the average", "find mean"),
            ("find the simple interest", "find simple interest"),
            ("what is its average speed", "find speed"),
            ("what is its speed", "find speed"),
            ("how many", "find quantity"),
            ("solve for", "solve variable"),
            ("solve the system", "solve system"),
            ("solve the quadratic", "solve quadratic"),
            ("what is", "evaluate expression"),
        ]
        for pattern, goal in goal_patterns:
            if pattern in lowered:
                return goal
        if "=" in lowered and any(symbol in lowered for symbol in ["x", "y"]):
            return "solve variable"
        return "unknown_goal"

    def _extract_parameters(self, text: str) -> dict[str, Any]:
        lowered = text.lower()
        numbers = [float(value) if "." in value else int(value) for value in NUMBER_PATTERN.findall(text)]
        parameters: dict[str, Any] = {"numbers": numbers}

        if "triangle" in lowered and len(numbers) >= 3 and "side" in lowered:
            parameters["sides"] = numbers[:3]
        if "base" in lowered and numbers:
            parameters["base"] = numbers[0]
        if "height" in lowered and len(numbers) >= 2:
            parameters["height"] = numbers[-1]
        if "radius" in lowered and numbers:
            parameters["radius"] = numbers[0]
        if "diameter" in lowered and numbers:
            parameters["diameter"] = numbers[0]
        if "circumference" in lowered and numbers:
            parameters["circumference"] = numbers[0]
        if "length" in lowered and numbers:
            parameters["length"] = numbers[0]
        if "width" in lowered and len(numbers) >= 2:
            parameters["width"] = numbers[1]
        if PERCENT_PATTERN.search(lowered):
            parameters["percent"] = float(PERCENT_PATTERN.search(lowered).group(1))
        if RATIO_PATTERN.search(lowered):
            match = RATIO_PATTERN.search(lowered)
            parameters["ratio"] = [int(match.group(1)), int(match.group(2))]
        if any(token in lowered for token in ["km", "miles", "hours", "minutes", "speed", "distance", "time"]):
            if len(numbers) >= 2:
                parameters["distance_time_values"] = numbers[:2]
        if any(token in lowered for token in ["principal", "interest", "per annum"]):
            if numbers:
                parameters["principal"] = numbers[0]
            if len(numbers) >= 2:
                parameters["rate"] = numbers[1]
            if len(numbers) >= 3:
                parameters["time"] = numbers[2]
        equations = [match.strip() for match in EQUATION_PATTERN.findall(text)]
        if equations:
            parameters["equations"] = equations
        parameters["variables"] = sorted(set(re.findall(r"\b[a-z]\b", lowered)))
        return parameters

    def _extract_hints(self, text: str, parameters: dict[str, Any], goal: str | None) -> list[str]:
        lowered = text.lower()
        hints: set[str] = set()

        if len(parameters.get("sides", [])) == 3:
            hints.update(["all_sides_known", "three_sides_known"])
        if "base" in lowered:
            hints.add("base_known")
        if "height" in lowered:
            hints.update(["height_known", "base_and_height_known"])
        if "angle" in lowered or any(token in lowered for token in ["sin", "cos", "tan"]):
            hints.add("included_angle_known")
        if len(parameters.get("sides", [])) >= 2:
            hints.add("two_sides_known")
        if "radius" in lowered:
            hints.add("radius_known")
        if "diameter" in lowered:
            hints.add("diameter_known")
        if "circumference" in lowered:
            hints.add("circumference_known")
        if "length" in lowered:
            hints.add("length_known")
        if "width" in lowered:
            hints.add("width_known")
        if "length_known" in hints and "width_known" in hints:
            hints.add("length_and_width_known")
        if goal == "find area":
            hints.add("goal_is_area")
        if goal == "find perimeter":
            hints.add("goal_is_perimeter")
        if parameters.get("equations") and any(var in parameters.get("variables", []) for var in ["x", "y", "z"]):
            hints.add("single_variable_equation")
        if len(parameters.get("equations", [])) >= 2:
            hints.add("system_two_equations")
        if any("x^2" in equation or "quadratic" in lowered for equation in parameters.get("equations", [])) or "quadratic" in lowered:
            hints.add("quadratic_equation_present")
        if any(token in lowered for token in ["x^2", "factor", "roots"]):
            hints.add("factorable_quadratic")
        if PERCENT_PATTERN.search(lowered):
            hints.add("percent_problem")
        if RATIO_PATTERN.search(lowered) or "ratio" in lowered or "proportion" in lowered:
            hints.add("ratio_problem")
        if any(token in lowered for token in ["speed", "distance", "time", "journey", "average speed"]):
            hints.add("speed_distance_time_problem")
        if "minutes" in lowered and "hours" in lowered:
            hints.add("unit_conversion_needed")
        if any(token in lowered for token in ["probability", "bag", "coin", "dice", "cards"]):
            hints.add("probability_problem")
        if any(token in lowered for token in ["at least", "not", "complement"]):
            hints.add("complement_language")
        if any(token in lowered for token in ["average", "mean"]):
            hints.add("average_problem")
        if any(token in lowered for token in ["simple interest", "per annum", "principal"]):
            hints.update(["simple_interest_problem", "principal_known"])
            if "rate" in lowered or PERCENT_PATTERN.search(lowered):
                hints.add("rate_known")
            if "year" in lowered or "years" in lowered:
                hints.add("time_known")
        return sorted(hints)

    def _extract_constraints(self, text: str) -> list[str]:
        lowered = text.lower()
        constraints: list[str] = []
        if "integer" in lowered:
            constraints.append("integer_solution")
        if "in terms of pi" in lowered:
            constraints.append("exact_pi_form")
        if "nearest" in lowered or "round" in lowered:
            constraints.append("rounding_required")
        return constraints

    def _enumerate_methods(self, concepts: list[str], parsed: dict[str, Any]) -> list[MethodDefinition]:
        methods: list[MethodDefinition] = []
        seen: set[str] = set()
        for concept in concepts:
            for candidate in METHOD_LIBRARY.get(concept, []):
                if not self._conditions_met(candidate.get("conditions", []), parsed):
                    continue
                name = str(candidate.get("name"))
                if name in seen:
                    continue
                methods.append(
                    MethodDefinition(
                        name=name,
                        requirements=list(candidate.get("requirements", [])),
                        steps=list(candidate.get("steps", [])),
                        equations=list(candidate.get("equations", [])),
                        keywords=list(candidate.get("keywords", [])),
                        score=self._score_method(candidate, parsed),
                    )
                )
                seen.add(name)
        return methods

    def _conditions_met(self, conditions: list[str], parsed: dict[str, Any]) -> bool:
        hints = set(parsed.get("hints", []))
        for condition in conditions:
            if condition not in hints:
                return False
        return True

    def _score_method(self, candidate: dict[str, Any], parsed: dict[str, Any]) -> float:
        score = float(candidate.get("base_score", 5.0))
        equations = list(candidate.get("equations", []))
        keywords = list(candidate.get("keywords", []))
        hints = set(parsed.get("hints", []))
        goal = str(parsed.get("goal") or "")

        score += max(0.0, 1.5 - (0.25 * max(0, len(equations) - 1)))
        if "unit_conversion_needed" in hints and "convert" in " ".join(keywords).lower():
            score += 0.4
        if goal == "find area" and any("area" in equation.lower() for equation in equations):
            score += 0.6
        if goal == "solve variable" and any(token in " ".join(keywords).lower() for token in ["isolate", "balance"]):
            score += 0.6
        if "three_sides_known" in hints and str(candidate.get("name")) == "Heron":
            score += 1.2
        if "included_angle_known" not in hints and str(candidate.get("name")) == "Trigonometric Area":
            score -= 3.0
        if "factorable_quadratic" in hints and str(candidate.get("name")) == "Factoring":
            score += 1.0
        if len(parsed.get("parameters", {}).get("equations", [])) >= 2 and str(candidate.get("name")) == "Elimination":
            score += 0.5
        return round(score, 3)

    def _select_optimal(self, methods: list[MethodDefinition]) -> list[str]:
        if not methods:
            return []
        ordered = sorted(methods, key=lambda method: (-method.score, len(method.steps), method.name))
        return [ordered[0].name]

    def _build_keyword_bank(self, parsed: dict[str, Any], concept_mapping: dict[str, Any], methods: list[MethodDefinition], raw_text: str) -> list[str]:
        bank: list[str] = []

        for keyword in parsed.get("keyword_bank", []) or []:
            if isinstance(keyword, str):
                cleaned = keyword.strip().lower()
                if cleaned:
                    bank.append(cleaned)

        bank.extend(str(term).lower() for term in concept_mapping.get("allowed_terms", []))
        bank.extend(str(concept).replace("_", " ") for concept in concept_mapping.get("concepts", []))
        for method in methods:
            bank.append(method.name.lower())
            bank.extend(keyword.lower() for keyword in method.keywords)
            bank.extend(step.replace("_", " ").lower() for step in method.steps)
            bank.extend(eq.lower() for eq in method.equations)

        entities = parsed.get("entities", []) or []
        bank.extend(str(entity).lower() for entity in entities if isinstance(entity, (str, int, float)))
        numbers = parsed.get("parameters", {}).get("numbers", []) or []
        bank.extend(str(number).lower() for number in numbers)
        bank.extend(token.lower() for token in WORD_PATTERN.findall(raw_text.lower()) if token.lower() not in STOPWORDS)

        unique: list[str] = []
        seen: set[str] = set()
        for item in bank:
            cleaned = re.sub(r"\s+", " ", str(item).strip().lower())
            if len(cleaned) < 2 or cleaned in STOPWORDS:
                continue
            if cleaned not in seen:
                unique.append(cleaned)
                seen.add(cleaned)
            if len(unique) >= 40:
                break
        return unique

    def _hash_problem(self, raw_text: str) -> str:
        return hashlib.sha1(raw_text.strip().lower().encode("utf-8")).hexdigest()


problem_structuring_pipeline = ProblemStructuringPipeline()
