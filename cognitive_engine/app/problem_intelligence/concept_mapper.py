from __future__ import annotations

from typing import Any

CONCEPT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "concept": "triangle_area",
        "domain": "geometry",
        "patterns": ["triangle", "area"],
        "keywords": ["triangle", "area", "side", "sides", "heron", "height", "base", "angle", "semiperimeter"],
    },
    {
        "concept": "circle_area",
        "domain": "geometry",
        "patterns": ["circle", "area"],
        "keywords": ["circle", "area", "radius", "diameter", "circumference", "pi"],
    },
    {
        "concept": "rectangle_measurement",
        "domain": "geometry",
        "patterns": ["rectangle"],
        "keywords": ["rectangle", "length", "width", "perimeter", "area"],
    },
    {
        "concept": "linear_equation",
        "domain": "algebra",
        "patterns": ["solve for", "equation"],
        "keywords": ["equation", "solve", "x", "variable", "linear", "balance", "isolate"],
    },
    {
        "concept": "quadratic_equation",
        "domain": "algebra",
        "patterns": ["quadratic"],
        "keywords": ["quadratic", "factor", "roots", "zeros", "parabola", "discriminant"],
    },
    {
        "concept": "system_of_linear_equations",
        "domain": "algebra",
        "patterns": ["system of equations"],
        "keywords": ["system", "equations", "substitution", "elimination", "simultaneous", "x", "y"],
    },
    {
        "concept": "percentage",
        "domain": "arithmetic",
        "patterns": ["percent"],
        "keywords": ["percent", "percentage", "%", "discount", "increase", "decrease", "markup"],
    },
    {
        "concept": "ratio_proportion",
        "domain": "arithmetic",
        "patterns": ["ratio", "proportion"],
        "keywords": ["ratio", "proportion", "share", "mixture", "part", "total"],
    },
    {
        "concept": "speed_distance_time",
        "domain": "applied_math",
        "patterns": ["speed", "distance", "time"],
        "keywords": ["speed", "distance", "time", "rate", "velocity", "journey", "km", "hours"],
    },
    {
        "concept": "probability_basic",
        "domain": "statistics",
        "patterns": ["probability"],
        "keywords": ["probability", "chance", "coin", "dice", "cards", "bag", "favorable", "outcomes"],
    },
    {
        "concept": "mean_average",
        "domain": "statistics",
        "patterns": ["average", "mean"],
        "keywords": ["average", "mean", "sum", "data", "scores", "count"],
    },
    {
        "concept": "simple_interest",
        "domain": "commercial_math",
        "patterns": ["simple interest", "interest"],
        "keywords": ["interest", "principal", "rate", "time", "amount", "simple interest"],
    },
]


def detect_concepts_from_text(text: str) -> list[str]:
    lowered = (text or "").lower()
    detected: list[str] = []
    for definition in CONCEPT_DEFINITIONS:
        patterns = definition.get("patterns", [])
        keywords = definition.get("keywords", [])
        pattern_hit = all(str(pattern).lower() in lowered for pattern in patterns) if patterns else False
        keyword_hits = sum(1 for keyword in keywords if str(keyword).lower() in lowered)
        if pattern_hit or keyword_hits >= 2:
            detected.append(str(definition["concept"]))
    if "solve for" in lowered and "=" in lowered:
        detected.append("linear_equation")
    if lowered.count("=") >= 2 and any(token in lowered for token in ["x", "y"]):
        detected.append("system_of_linear_equations")
    if "x^2" in lowered or "quadratic" in lowered:
        detected.append("quadratic_equation")
    if "%" in lowered or "percent" in lowered or "percentage" in lowered:
        detected.append("percentage")
    if ":" in lowered and any(char.isdigit() for char in lowered):
        detected.append("ratio_proportion")
    if "average speed" in lowered:
        detected.append("speed_distance_time")
    if any(token in lowered for token in ["sin", "cos", "tan"]) and "triangle" in lowered:
        detected.append("triangle_area")
    return list(dict.fromkeys(detected))


def map_concepts(parsed: dict[str, Any]) -> dict[str, Any]:
    text = (parsed.get("raw_text") or "").lower()
    hints = [str(hint).lower() for hint in parsed.get("hints", [])]
    parameters = parsed.get("parameters", {})

    concepts = detect_concepts_from_text(text)
    applicable_methods: list[str] = []
    domains: list[str] = []
    allowed_terms: set[str] = set()

    for definition in CONCEPT_DEFINITIONS:
        concept = str(definition["concept"])
        if concept not in concepts:
            continue
        domains.append(str(definition.get("domain") or "general_math"))
        allowed_terms.update(str(keyword).lower() for keyword in definition.get("keywords", []))
        if concept == "triangle_area":
            applicable_methods.extend(["Heron", "Base-Height", "Trigonometric Area"])
            if len(parameters.get("sides", [])) == 3:
                allowed_terms.update(["side", "sides", "semiperimeter"])
            if "included_angle_known" in hints:
                allowed_terms.update(["sin", "angle", "included angle"])
        elif concept == "circle_area":
            applicable_methods.extend(["Radius Formula", "Diameter Conversion", "Circumference Backsolve"])
        elif concept == "rectangle_measurement":
            applicable_methods.extend(["Area Formula", "Perimeter Formula"])
        elif concept == "linear_equation":
            applicable_methods.extend(["Isolation", "Balance Method"])
        elif concept == "quadratic_equation":
            applicable_methods.extend(["Factoring", "Quadratic Formula", "Completing the Square"])
        elif concept == "system_of_linear_equations":
            applicable_methods.extend(["Substitution", "Elimination"])
        elif concept == "percentage":
            applicable_methods.extend(["Percent Equation", "Decimal Conversion"])
        elif concept == "ratio_proportion":
            applicable_methods.extend(["Scaling", "Unit Rate"])
        elif concept == "speed_distance_time":
            applicable_methods.extend(["Rate Formula", "Unit Conversion + Rate Formula"])
        elif concept == "probability_basic":
            applicable_methods.extend(["Favorable Over Total", "Complement Rule"])
        elif concept == "mean_average":
            applicable_methods.extend(["Sum Over Count"])
        elif concept == "simple_interest":
            applicable_methods.extend(["Simple Interest Formula"])

    return {
        "domain": domains[0] if domains else "general_math",
        "concepts": concepts,
        "applicable_methods": sorted(set(applicable_methods)),
        "allowed_terms": sorted(allowed_terms),
    }

