from __future__ import annotations

import re
from typing import Iterable

from .contracts import (
    AcousticProfile,
    CognitiveIntent,
    IntentCertainty,
    SemanticIntentResult,
    SemanticSignals,
    SessionState,
)

INTENT_TAXONOMY: tuple[str, ...] = (
    "problem_understanding",
    "parameter_recognition",
    "strategy_selection",
    "execution_start",
    "deviation",
    "verification",
    "silence_reflection",
    "error_correction",
    "solution_summary",
    "conceptual_explanation",
    "comparison_analysis",
    "meta_cognition",
    "working_memory_retrieval",
    "stuck_state",
    "confidence_expression",
    "unknown",
)

RULEBOOK: dict[str, tuple[str, ...]] = {
    "problem_understanding": (
        "the question is asking",
        "this problem is about",
        "this problem deals with",
        "we need to find",
        "we have to find",
        "goal is",
        "we are trying to",
        "it is asking for",
        "the task is",
        "related to",
    ),
    "parameter_recognition": (
        "given",
        "value",
        "values",
        "side",
        "sides",
        "base",
        "height",
        "radius",
        "diameter",
        "distance",
        "time",
        "speed",
        "rate",
        "angle",
        "coefficient",
        "principal",
        "percent",
        "ratio",
        "average",
        "mean",
        "equation",
    ),
    "strategy_selection": (
        "which method",
        "what method",
        "what formula",
        "which formula",
        "best way",
        "cleanest path",
        "cleanest way",
        "should use",
        "lets use",
        "let's use",
        "go with",
        "choose",
        "select",
        "approach",
        "method",
        "formula",
        "strategy",
    ),
    "execution_start": (
        "calculate",
        "compute",
        "plug in",
        "substitute",
        "divide",
        "multiply",
        "simplify",
        "solve",
        "work out",
        "average speed should be",
        "therefore speed is",
        "distance divided by time",
        "hours",
        "kilometer per hour",
    ),
    "deviation": (
        "trigonometry",
        "sine rule",
        "cosine rule",
        "different method",
        "other way",
        "alternate way",
        "instead maybe",
        "maybe another",
        "scratch that",
        "never mind",
    ),
    "verification": (
        "check",
        "verify",
        "double check",
        "confirm",
        "does that make sense",
        "is that right",
    ),
    "error_correction": (
        "mistake",
        "wrong",
        "should be",
        "let me fix",
        "not right",
        "i meant",
    ),
    "solution_summary": (
        "therefore",
        "thus",
        "hence",
        "so the answer is",
        "final answer",
        "answer is",
    ),
    "conceptual_explanation": (
        "because",
        "this works because",
        "reason is",
        "means that",
        "by definition",
        "by formula",
    ),
    "comparison_analysis": (
        "compared to",
        "better than",
        "instead of",
        "more direct",
        "cleaner than",
        "versus",
    ),
    "meta_cognition": (
        "i think",
        "i feel",
        "i believe",
        "i'm thinking",
        "i am thinking",
        "let me think",
        "i wonder",
    ),
    "working_memory_retrieval": (
        "remember",
        "earlier",
        "we already",
        "previously",
        "from before",
    ),
    "stuck_state": (
        "stuck",
        "confused",
        "not sure",
        "don't know",
        "unsure",
        "lost",
    ),
    "confidence_expression": (
        "definitely",
        "certainly",
        "i'm sure",
        "clearly",
        "obviously",
    ),
}

UNCERTAINTY_MARKERS: tuple[str, ...] = (
    "maybe",
    "i think",
    "probably",
    "not sure",
    "perhaps",
    "could be",
    "might",
    "possibly",
    "i guess",
)

DECISION_MARKERS: tuple[str, ...] = (
    "let's use",
    "lets use",
    "i will use",
    "we should use",
    "should use",
    "go with",
    "choose",
    "select",
    "commit to",
)

FORMULA_REFERENCES: tuple[str, ...] = (
    "heron",
    "semiperimeter",
    "base height",
    "quadratic formula",
    "elimination",
    "substitution",
    "distance divided by time",
    "rate formula",
    "probability",
    "percent equation",
    "simple interest formula",
    "area formula",
)

CONFIDENCE_MARKERS: tuple[str, ...] = (
    "definitely",
    "certainly",
    "absolutely",
    "confident",
    "sure",
    "clearly",
)

HESITATION_MARKERS: tuple[str, ...] = (
    "um",
    "uh",
    "er",
    "hmm",
    "so so",
    "like",
)

QUANTITATIVE_MARKERS: tuple[str, ...] = (
    "equals",
    "plus",
    "minus",
    "times",
    "divided by",
    "percent",
    "ratio",
    "average",
    "mean",
    "speed",
    "hour",
    "kilometer",
)

TEMPORAL_MARKERS: tuple[str, ...] = (
    "first",
    "then",
    "next",
    "finally",
    "now",
)

FILLER_WORDS: set[str] = {
    "a", "ah", "an", "and", "eh", "er", "hey", "hmm", "i", "just", "like", "oh", "okay", "so", "uh", "um", "well", "yeah", "yes",
}

TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]*")


def get_intent_taxonomy() -> tuple[str, ...]:
    return INTENT_TAXONOMY


def build_default_rulebook() -> dict[str, tuple[str, ...]]:
    return RULEBOOK


def _find_markers(transcript: str, markers: Iterable[str]) -> list[str]:
    lowered = transcript.lower()
    return [marker for marker in markers if marker in lowered]


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text.lower())]


def _normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _problem_keyword_bank(session_state: SessionState) -> list[str]:
    if session_state.problem_structure and session_state.problem_structure.keyword_bank:
        return [keyword.lower() for keyword in session_state.problem_structure.keyword_bank]
    return []


def _problem_alignment(text: str, session_state: SessionState) -> tuple[list[str], list[str], float]:
    keyword_bank = _problem_keyword_bank(session_state)
    if not text or not keyword_bank:
        return [], [], 0.0
    tokens = _tokenize(text)
    token_set = set(tokens)
    hits: list[str] = []
    for keyword in keyword_bank:
        parts = set(_tokenize(keyword))
        if not parts:
            continue
        if parts.issubset(token_set) or keyword in text:
            hits.append(keyword)
    off_topic: list[str] = []
    if session_state.problem_structure:
        allowed = set(session_state.problem_structure.concepts)
        mentioned_concepts = set()
        if any(token in token_set for token in {"triangle", "radius", "diameter", "base", "height", "area"}):
            mentioned_concepts.add("triangle_area")
        if any(token in token_set for token in {"speed", "distance", "time", "hour", "velocity", "rate"}):
            mentioned_concepts.add("speed_distance_time")
        if any(token in token_set for token in {"probability", "coin", "dice", "bag", "card"}):
            mentioned_concepts.add("probability_basic")
        if any(token in token_set for token in {"ratio", "proportion", "share"}):
            mentioned_concepts.add("ratio_proportion")
        if any(token in token_set for token in {"average", "mean"}):
            mentioned_concepts.add("mean_average")
        if any(token in token_set for token in {"equation", "solve", "x", "y"}):
            mentioned_concepts.add("linear_equation")
        for concept in mentioned_concepts:
            if concept not in allowed:
                off_topic.append(concept)
    score = 0.0
    if keyword_bank:
        lexical = len(set(hits)) / max(min(len(keyword_bank), 20), 1)
        weighted = min(1.0, lexical * 2.8)
        if len(set(hits)) >= 3:
            weighted += 0.08
        if len(set(hits)) >= 5:
            weighted += 0.08
        if off_topic:
            weighted -= min(0.3, 0.12 * len(off_topic))
        score = max(0.0, min(weighted, 1.0))
    return sorted(set(hits)), sorted(set(off_topic)), round(score, 3)


def _is_filler_only(text: str) -> bool:
    tokens = _tokenize(text)
    if not tokens:
        return True
    meaningful = [token for token in tokens if token not in FILLER_WORDS]
    return len(meaningful) <= 1


def extract_semantic_signals(transcript: str | None, session_state: SessionState) -> SemanticSignals:
    text = _normalize_phrase(transcript or "")
    if not text:
        return SemanticSignals(filler_only=True)

    concepts = _find_markers(text, FORMULA_REFERENCES)
    uncertainty_markers = _find_markers(text, UNCERTAINTY_MARKERS)
    decision_markers = _find_markers(text, DECISION_MARKERS)
    deviation_markers = _find_markers(text, RULEBOOK["deviation"])
    verification_markers = _find_markers(text, RULEBOOK["verification"])
    parameter_markers = _find_markers(text, RULEBOOK["parameter_recognition"])
    strategy_markers = _find_markers(text, RULEBOOK["strategy_selection"])
    error_markers = _find_markers(text, RULEBOOK["error_correction"])
    summary_markers = _find_markers(text, RULEBOOK["solution_summary"])
    conceptual_markers = _find_markers(text, RULEBOOK["conceptual_explanation"])
    confidence_markers = _find_markers(text, CONFIDENCE_MARKERS)
    hesitation_markers = _find_markers(text, HESITATION_MARKERS)
    quantitative_markers = _find_markers(text, QUANTITATIVE_MARKERS)
    temporal_markers = _find_markers(text, TEMPORAL_MARKERS)
    problem_keyword_hits, off_topic_markers, problem_alignment_score = _problem_alignment(text, session_state)
    filler_only = _is_filler_only(text)

    for hit in problem_keyword_hits:
        if hit in FORMULA_REFERENCES and hit not in concepts:
            concepts.append(hit)
        if hit in RULEBOOK["strategy_selection"] and hit not in strategy_markers:
            strategy_markers.append(hit)
        if hit in RULEBOOK["parameter_recognition"] and hit not in parameter_markers:
            parameter_markers.append(hit)

    return SemanticSignals(
        concepts=sorted(set(concepts)),
        uncertainty=bool(uncertainty_markers),
        decision=bool(decision_markers),
        formula_references=sorted(set(concepts)),
        uncertainty_markers=sorted(set(uncertainty_markers)),
        decision_markers=sorted(set(decision_markers)),
        deviation_markers=sorted(set(deviation_markers)),
        verification_markers=sorted(set(verification_markers)),
        parameter_markers=sorted(set(parameter_markers)),
        strategy_markers=sorted(set(strategy_markers)),
        error_markers=sorted(set(error_markers)),
        summary_markers=sorted(set(summary_markers)),
        conceptual_markers=sorted(set(conceptual_markers)),
        confidence_markers=sorted(set(confidence_markers)),
        hesitation_markers=sorted(set(hesitation_markers)),
        quantitative_markers=sorted(set(quantitative_markers)),
        temporal_markers=sorted(set(temporal_markers)),
        problem_keyword_hits=problem_keyword_hits,
        off_topic_markers=off_topic_markers,
        problem_alignment_score=problem_alignment_score,
        filler_only=filler_only,
    )


def _certainty_from(confidence: float, alignment_score: float, filler_only: bool) -> IntentCertainty:
    if filler_only:
        return IntentCertainty.AMBIGUOUS
    if confidence >= 0.82 and alignment_score >= 0.35:
        return IntentCertainty.STRONG
    if confidence >= 0.6:
        return IntentCertainty.WEAK
    return IntentCertainty.AMBIGUOUS


def classify_semantic_intent(
    transcript: str | None,
    acoustic_profile: AcousticProfile,
    session_state: SessionState,
) -> SemanticIntentResult:
    text = _normalize_phrase(transcript or "")
    signals = extract_semantic_signals(transcript, session_state)

    if not text:
        if acoustic_profile.silence_ratio >= 0.92:
            return SemanticIntentResult(
                intent=CognitiveIntent.SILENCE_REFLECTION,
                confidence=0.72,
                certainty=IntentCertainty.WEAK,
                semantic_signals=signals,
                rationale="No transcript was produced and the chunk is acoustically dominated by silence.",
            )
        return SemanticIntentResult(
            intent=CognitiveIntent.UNKNOWN,
            confidence=0.22,
            certainty=IntentCertainty.AMBIGUOUS,
            semantic_signals=signals,
            rationale="No transcript was available.",
        )

    if signals.filler_only:
        return SemanticIntentResult(
            intent=CognitiveIntent.UNKNOWN,
            confidence=0.18,
            certainty=IntentCertainty.AMBIGUOUS,
            semantic_signals=signals,
            rationale="Transcript is too short or filler-heavy to support semantic intent.",
        )

    alignment = signals.problem_alignment_score
    has_problem_context = alignment >= 0.22 or len(signals.problem_keyword_hits) >= 2

    if signals.error_markers and len(signals.error_markers) >= 1:
        confidence = 0.82 + min(0.08, alignment * 0.1)
        return SemanticIntentResult(
            intent=CognitiveIntent.ERROR_CORRECTION,
            confidence=round(min(confidence, 0.94), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="Error-correction language detected.",
        )

    if signals.verification_markers and has_problem_context:
        confidence = 0.79 + min(0.12, alignment * 0.15)
        return SemanticIntentResult(
            intent=CognitiveIntent.VERIFICATION,
            confidence=round(min(confidence, 0.93), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="Verification language aligns with the current problem.",
        )

    if signals.summary_markers and has_problem_context:
        confidence = 0.8 + min(0.1, alignment * 0.12)
        return SemanticIntentResult(
            intent=CognitiveIntent.SOLUTION_SUMMARY,
            confidence=round(min(confidence, 0.92), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="Summary language appeared with strong problem alignment.",
        )

    if signals.off_topic_markers and alignment < 0.12 and len(signals.problem_keyword_hits) <= 1:
        confidence = 0.72 + min(0.12, acoustic_profile.hesitation_score * 0.15)
        return SemanticIntentResult(
            intent=CognitiveIntent.DEVIATION,
            confidence=round(min(confidence, 0.9), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="Transcript introduced concepts outside the current problem structure.",
        )

    if signals.decision_markers or len(signals.strategy_markers) >= 2:
        confidence = 0.78 + min(0.16, alignment * 0.22) + (0.04 if signals.formula_references else 0.0)
        return SemanticIntentResult(
            intent=CognitiveIntent.STRATEGY_SELECTION,
            confidence=round(min(confidence, 0.96), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="Strategy language matched the current problem's keyword bank.",
        )

    if any(marker in text for marker in RULEBOOK["execution_start"]) and has_problem_context:
        confidence = 0.77 + min(0.17, alignment * 0.25)
        return SemanticIntentResult(
            intent=CognitiveIntent.EXECUTION_START,
            confidence=round(min(confidence, 0.95), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="Computation-oriented language matched the current problem context.",
        )

    if signals.parameter_markers and has_problem_context:
        confidence = 0.7 + min(0.18, alignment * 0.28)
        return SemanticIntentResult(
            intent=CognitiveIntent.PARAMETER_RECOGNITION,
            confidence=round(min(confidence, 0.92), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="The transcript references givens and quantities from the active problem.",
        )

    if any(marker in text for marker in RULEBOOK["problem_understanding"]) or (signals.uncertainty and has_problem_context):
        confidence = 0.64 + min(0.16, alignment * 0.22)
        return SemanticIntentResult(
            intent=CognitiveIntent.PROBLEM_UNDERSTANDING,
            confidence=round(min(confidence, 0.88), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="The learner appears to be framing or understanding the problem.",
        )

    if acoustic_profile.hesitation_score >= 0.82 and signals.uncertainty and alignment < 0.16:
        confidence = 0.58
        return SemanticIntentResult(
            intent=CognitiveIntent.STUCK_STATE,
            confidence=confidence,
            certainty=IntentCertainty.WEAK,
            semantic_signals=signals,
            rationale="High hesitation with low problem alignment suggests a stuck state.",
        )

    if alignment >= 0.35 and any(token in text for token in ["answer", "hour", "kilometer", "speed", "distance", "time", "mean", "probability", "percent"]):
        confidence = 0.68 + min(0.18, alignment * 0.22)
        return SemanticIntentResult(
            intent=CognitiveIntent.EXECUTION_START,
            confidence=round(min(confidence, 0.9), 3),
            certainty=_certainty_from(confidence, alignment, False),
            semantic_signals=signals,
            rationale="Domain-specific quantitative language strongly matches the current problem.",
        )

    return SemanticIntentResult(
        intent=CognitiveIntent.UNKNOWN,
        confidence=0.28 + min(0.16, alignment * 0.2),
        certainty=IntentCertainty.AMBIGUOUS,
        semantic_signals=signals,
        rationale="The transcript was captured, but evidence is still too weak for a stable intent.",
    )
