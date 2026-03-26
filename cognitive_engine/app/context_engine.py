from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .contracts import (
    CognitiveChunk,
    CognitiveIntent,
    CognitiveTrajectory,
    ContextRefinementResult,
    IntentCertainty,
    SessionPhase,
    SessionState,
)

WINDOW_SIZE = 5
TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]*")


class ContextWindowEngine:
    def __init__(self) -> None:
        self._problem_profiles: dict[str, dict[str, Any]] = {}

    def refine(self, *, current_chunk: CognitiveChunk, session_state: SessionState) -> ContextRefinementResult:
        history = session_state.chunks[-(WINDOW_SIZE - 1):]
        window = [*history, current_chunk]
        intents = [chunk.intent_refined for chunk in window]
        notes: list[str] = []
        profile = self._problem_profile(session_state)

        strategy_like = {CognitiveIntent.STRATEGY_SELECTION, CognitiveIntent.COMPARISON_ANALYSIS}
        deviation_like = {CognitiveIntent.DEVIATION, CognitiveIntent.STUCK_STATE}
        correction_like = {CognitiveIntent.ERROR_CORRECTION, CognitiveIntent.STRATEGY_SELECTION, CognitiveIntent.COMPARISON_ANALYSIS}

        strategy_count = sum(1 for intent in intents if intent in strategy_like)
        deviation_count = sum(1 for intent in intents if intent in deviation_like)
        correction_count = sum(1 for intent in intents if intent in correction_like)
        unknown_count = sum(1 for intent in intents if intent == CognitiveIntent.UNKNOWN)

        refined_intent = current_chunk.intent_raw
        confidence = current_chunk.raw_confidence
        trajectory = CognitiveTrajectory.ISOLATED_SIGNAL
        deviation_flag = False
        exploration_valid = False
        ambiguity_score = 0.0

        lexical_alignment = self._lexical_alignment(current_chunk, profile)
        graph_alignment = self._graph_alignment(current_chunk, profile)
        temporal_consensus = self._temporal_consensus(current_chunk, history)
        phase_prior = self._phase_prior(current_chunk, session_state)
        deviation_signal = self._deviation_signal(current_chunk, session_state, profile)
        confidence = max(confidence, lexical_alignment["confidence_floor"])
        confidence = max(confidence, graph_alignment["confidence_floor"])
        confidence = max(confidence, phase_prior["confidence_floor"])
        notes.extend(lexical_alignment["notes"])
        notes.extend(graph_alignment["notes"])
        notes.extend(temporal_consensus["notes"])
        notes.extend(phase_prior["notes"])
        notes.extend(deviation_signal["notes"])

        if lexical_alignment["best_intent"] is not None and lexical_alignment["score"] >= 0.48:
            if refined_intent == CognitiveIntent.UNKNOWN or confidence < 0.72:
                refined_intent = lexical_alignment["best_intent"]
                confidence = max(confidence, lexical_alignment["confidence_floor"])
                ambiguity_score = max(0.0, ambiguity_score - 0.06)
                notes.append("Lexical similarity to the problem graph stabilized the intent without an LLM call.")

        if graph_alignment["best_intent"] is not None and graph_alignment["score"] >= 0.45:
            if refined_intent in {CognitiveIntent.UNKNOWN, CognitiveIntent.PARAMETER_RECOGNITION} or confidence < 0.76:
                refined_intent = graph_alignment["best_intent"]
                confidence = max(confidence, graph_alignment["confidence_floor"])
                ambiguity_score = max(0.0, ambiguity_score - 0.08)
                notes.append("Graph-node alignment promoted the chunk toward the most compatible solution step.")

        if phase_prior["best_intent"] is not None and refined_intent == CognitiveIntent.UNKNOWN:
            refined_intent = phase_prior["best_intent"]
            confidence = max(confidence, phase_prior["confidence_floor"])
            notes.append("Phase prior stabilized an otherwise unknown chunk.")

        if strategy_count >= 2 and correction_count >= 2:
            trajectory = CognitiveTrajectory.EXPLORATION_CONVERGING
            exploration_valid = True
            refined_intent = CognitiveIntent.STRATEGY_SELECTION
            confidence = max(confidence, 0.84)
            notes.append("Multiple recent chunks explored methods and converged on a strategy.")
        elif strategy_count >= 2 and deviation_count >= 1:
            trajectory = CognitiveTrajectory.EXPLORATION_ACTIVE
            exploration_valid = True
            if current_chunk.intent_raw == CognitiveIntent.DEVIATION:
                refined_intent = CognitiveIntent.COMPARISON_ANALYSIS
                confidence = max(confidence, 0.71)
                notes.append("Potential deviation appears inside an active comparison window, so it is treated as exploration.")
            else:
                refined_intent = current_chunk.intent_raw if current_chunk.intent_raw != CognitiveIntent.UNKNOWN else CognitiveIntent.STRATEGY_SELECTION
                confidence = max(confidence, 0.76)
                notes.append("The recent window shows active strategy exploration rather than isolated drift.")
        elif deviation_count >= 2 and correction_count <= 1:
            trajectory = CognitiveTrajectory.DEVIATION_PERSISTENT
            deviation_flag = True
            refined_intent = CognitiveIntent.DEVIATION
            confidence = max(confidence, 0.84)
            notes.append("Deviation persisted across the recent context window without corrective reasoning.")
        elif current_chunk.intent_raw == CognitiveIntent.SILENCE_REFLECTION:
            if strategy_count >= 1 or correction_count >= 1:
                trajectory = CognitiveTrajectory.DEEP_REFLECTION
                confidence = max(confidence, 0.74)
                notes.append("Silence followed structured reasoning, so it is treated as deep reflection.")
            else:
                trajectory = CognitiveTrajectory.CONFUSION_BUILDING
                ambiguity_score += 0.2
                notes.append("Silence lacks recent semantic progress and may indicate confusion.")
        elif current_chunk.intent_raw == CognitiveIntent.EXECUTION_START and strategy_count >= 2:
            trajectory = CognitiveTrajectory.EXECUTION_COMMITMENT
            confidence = max(confidence, 0.82)
            notes.append("The recent window shows planning that now resolves into execution.")
        elif current_chunk.intent_raw == CognitiveIntent.UNKNOWN and strategy_count >= 2:
            trajectory = CognitiveTrajectory.EXPLORATION_CONVERGING
            exploration_valid = True
            refined_intent = CognitiveIntent.STRATEGY_SELECTION
            confidence = max(confidence, 0.7)
            ambiguity_score += 0.12
            notes.append("The current chunk is locally ambiguous, but the recent context strongly indicates strategy formation.")
        elif unknown_count >= 2 and current_chunk.acoustic_profile.hesitation_score >= 0.6:
            trajectory = CognitiveTrajectory.CONFUSION_BUILDING
            ambiguity_score += 0.28
            notes.append("Repeated ambiguity with hesitation suggests unresolved confusion.")
        else:
            trajectory = CognitiveTrajectory.STABLE_PROGRESS
            confidence = max(confidence, current_chunk.raw_confidence)
            notes.append("The current chunk is consistent with the recent reasoning trajectory.")

        if deviation_signal["is_deviation"]:
            if strategy_count >= 1 and session_state.phase == SessionPhase.STRATEGY:
                refined_intent = CognitiveIntent.COMPARISON_ANALYSIS
                exploration_valid = True
                confidence = max(confidence, deviation_signal["confidence_floor"])
                notes.append("Alternative-method evidence was kept on-graph as comparison rather than premature deviation.")
            else:
                refined_intent = CognitiveIntent.DEVIATION
                deviation_flag = True
                confidence = max(confidence, deviation_signal["confidence_floor"])
                ambiguity_score += 0.08
                notes.append("The chunk conflicted with the selected graph path strongly enough to count as deviation.")

        if graph_alignment["node_type"] == "step" and graph_alignment["score"] >= 0.42 and refined_intent != CognitiveIntent.VERIFICATION:
            refined_intent = CognitiveIntent.EXECUTION_START
            confidence = max(confidence, 0.74)
            ambiguity_score = max(0.0, ambiguity_score - 0.05)
            notes.append("Direct step alignment upgraded the chunk into execution.")
        elif graph_alignment["node_type"] == "method" and refined_intent == CognitiveIntent.UNKNOWN:
            refined_intent = CognitiveIntent.STRATEGY_SELECTION
            confidence = max(confidence, 0.72)
            notes.append("Method-node alignment upgraded the chunk into strategy selection.")
        elif graph_alignment["node_type"] == "equation" and refined_intent != CognitiveIntent.VERIFICATION:
            refined_intent = CognitiveIntent.EXECUTION_START
            confidence = max(confidence, 0.73)
            notes.append("Equation alignment indicates active solving rather than idle reasoning.")

        if temporal_consensus["best_intent"] is not None:
            if refined_intent == CognitiveIntent.UNKNOWN and temporal_consensus["support"] >= 2:
                refined_intent = temporal_consensus["best_intent"]
                confidence = max(confidence, temporal_consensus["confidence_floor"])
                ambiguity_score = max(0.0, ambiguity_score - 0.08)
                notes.append("Temporal smoothing promoted the dominant recent intent.")
            elif refined_intent != temporal_consensus["best_intent"] and temporal_consensus["support"] >= 3:
                ambiguity_score += 0.06
                notes.append("The current chunk conflicts with the recent temporal consensus, so confidence stayed conservative.")

        if current_chunk.semantic_signals.uncertainty and not exploration_valid:
            ambiguity_score += 0.14
        if current_chunk.intent_raw == CognitiveIntent.UNKNOWN:
            ambiguity_score += 0.18
        if current_chunk.transcript_confidence < 0.65:
            ambiguity_score += 0.12
        if current_chunk.acoustic_profile.hesitation_score >= 0.7:
            ambiguity_score += 0.1
        if deviation_flag and exploration_valid:
            ambiguity_score += 0.2
        if lexical_alignment["score"] >= 0.52:
            ambiguity_score = max(0.0, ambiguity_score - 0.08)
        if graph_alignment["score"] >= 0.5:
            ambiguity_score = max(0.0, ambiguity_score - 0.1)
        if temporal_consensus["support"] >= 2:
            ambiguity_score = max(0.0, ambiguity_score - 0.05)
        if phase_prior["score"] >= 0.5:
            ambiguity_score = max(0.0, ambiguity_score - 0.04)

        ambiguity_score = min(max(ambiguity_score, 0.0), 0.95)
        certainty = self._certainty_from(confidence=confidence, ambiguity_score=ambiguity_score)
        llm_recommended = False

        return ContextRefinementResult(
            refined_intent=refined_intent,
            confidence=round(min(max(confidence, 0.0), 0.98), 3),
            certainty=certainty,
            trajectory=trajectory,
            deviation_flag=deviation_flag,
            exploration_valid=exploration_valid,
            ambiguity_score=round(ambiguity_score, 3),
            llm_recommended=llm_recommended,
            notes=notes,
        )

    def _problem_profile(self, session_state: SessionState) -> dict[str, Any]:
        if not session_state.problem_structure:
            return {}
        problem_id = session_state.problem_structure.problem_id
        if problem_id in self._problem_profiles:
            return self._problem_profiles[problem_id]

        profile: dict[str, Any] = {
            "problem_id": problem_id,
            "keyword_bank_bag": Counter(self._tokenize(" ".join(session_state.problem_structure.keyword_bank[:30]))),
            "method_bags": [],
            "node_bags": [],
            "optimal_method_tokens": set(),
        }
        optimal_method_name = session_state.problem_structure.optimal_path[0].lower() if session_state.problem_structure.optimal_path else ""
        for method in session_state.problem_structure.methods[:10]:
            method_text = " ".join([method.name, *method.keywords[:8], *method.steps[:4], *method.equations[:2]])
            bag = Counter(self._tokenize(method_text))
            profile["method_bags"].append((method.name, bag))
            if method.name.lower() == optimal_method_name:
                profile["optimal_method_tokens"] = set(bag.keys())

        if session_state.solution_graph:
            for node in session_state.solution_graph.nodes:
                node_text = " ".join([node.label, *node.keywords[:8]])
                profile["node_bags"].append(
                    {
                        "node_id": node.node_id,
                        "node_type": node.node_type,
                        "bag": Counter(self._tokenize(node_text)),
                    }
                )

        self._problem_profiles[problem_id] = profile
        return profile

    def _lexical_alignment(self, current_chunk: CognitiveChunk, profile: dict[str, Any]) -> dict[str, object]:
        transcript = (current_chunk.transcript or "").lower().strip()
        if not transcript or not profile:
            return {
                "best_intent": None,
                "score": 0.0,
                "confidence_floor": current_chunk.raw_confidence,
                "notes": [],
            }

        transcript_tokens = self._tokenize(transcript)
        transcript_counter = Counter(transcript_tokens)
        if not transcript_counter:
            return {
                "best_intent": None,
                "score": 0.0,
                "confidence_floor": current_chunk.raw_confidence,
                "notes": [],
            }

        candidate_bags: list[tuple[CognitiveIntent, Counter[str]]] = []
        if profile.get("keyword_bank_bag"):
            candidate_bags.append((CognitiveIntent.PARAMETER_RECOGNITION, profile["keyword_bank_bag"]))
        for method_name, bag in profile.get("method_bags", []):
            if bag:
                candidate_bags.append((CognitiveIntent.STRATEGY_SELECTION, bag))
        candidate_bags.extend(
            [
                (CognitiveIntent.EXECUTION_START, Counter(self._tokenize(" ".join(current_chunk.semantic_signals.quantitative_markers + current_chunk.semantic_signals.temporal_markers)))),
                (CognitiveIntent.VERIFICATION, Counter(self._tokenize(" ".join(current_chunk.semantic_signals.verification_markers)))),
                (CognitiveIntent.ERROR_CORRECTION, Counter(self._tokenize(" ".join(current_chunk.semantic_signals.error_markers)))),
                (CognitiveIntent.PROBLEM_UNDERSTANDING, Counter(self._tokenize(" ".join(current_chunk.semantic_signals.problem_keyword_hits[:8])))),
            ]
        )

        best_intent = None
        best_score = 0.0
        for intent, bag in candidate_bags:
            if not bag:
                continue
            score = self._cosine_similarity(transcript_counter, bag)
            if score > best_score:
                best_score = score
                best_intent = intent

        notes: list[str] = []
        if best_intent is not None and best_score >= 0.32:
            notes.append(
                f"Local lexical alignment matched {best_intent.value} with score={best_score:.2f}."
            )
        return {
            "best_intent": best_intent,
            "score": best_score,
            "confidence_floor": max(current_chunk.raw_confidence, min(0.86, 0.5 + (best_score * 0.45))),
            "notes": notes,
        }

    def _graph_alignment(self, current_chunk: CognitiveChunk, profile: dict[str, Any]) -> dict[str, object]:
        transcript = (current_chunk.transcript or "").lower().strip()
        if not transcript or not profile.get("node_bags"):
            return {
                "best_intent": None,
                "score": 0.0,
                "node_type": None,
                "confidence_floor": current_chunk.raw_confidence,
                "notes": [],
            }

        transcript_counter = Counter(self._tokenize(transcript))
        best_score = 0.0
        best_node_type = None
        for node in profile["node_bags"]:
            bag = node["bag"]
            if not bag:
                continue
            score = self._cosine_similarity(transcript_counter, bag)
            if score > best_score:
                best_score = score
                best_node_type = node["node_type"]

        intent_for_type = {
            "concept": CognitiveIntent.PARAMETER_RECOGNITION,
            "method": CognitiveIntent.STRATEGY_SELECTION,
            "step": CognitiveIntent.EXECUTION_START,
            "equation": CognitiveIntent.EXECUTION_START,
        }
        notes: list[str] = []
        if best_node_type and best_score >= 0.28:
            notes.append(f"Solution-graph alignment matched a {best_node_type} node with score={best_score:.2f}.")
        return {
            "best_intent": intent_for_type.get(best_node_type),
            "score": best_score,
            "node_type": best_node_type,
            "confidence_floor": max(current_chunk.raw_confidence, min(0.88, 0.52 + (best_score * 0.48))),
            "notes": notes,
        }

    def _temporal_consensus(self, current_chunk: CognitiveChunk, history: list[CognitiveChunk]) -> dict[str, object]:
        recent = [chunk.intent_refined for chunk in history[-3:] if chunk.intent_refined != CognitiveIntent.UNKNOWN]
        if not recent:
            return {"best_intent": None, "support": 0, "confidence_floor": current_chunk.raw_confidence, "notes": []}
        counts = Counter(recent)
        best_intent, support = counts.most_common(1)[0]
        notes: list[str] = []
        if support >= 2:
            notes.append(
                f"Temporal smoothing found recent majority intent={best_intent.value} across {support} chunks."
            )
        return {
            "best_intent": best_intent,
            "support": support,
            "confidence_floor": max(current_chunk.raw_confidence, min(0.84, 0.58 + (support * 0.08))),
            "notes": notes,
        }

    def _phase_prior(self, current_chunk: CognitiveChunk, session_state: SessionState) -> dict[str, object]:
        phase_to_intents = {
            SessionPhase.UNDERSTANDING: [CognitiveIntent.PROBLEM_UNDERSTANDING, CognitiveIntent.PARAMETER_RECOGNITION, CognitiveIntent.CONCEPTUAL_EXPLANATION],
            SessionPhase.STRATEGY: [CognitiveIntent.STRATEGY_SELECTION, CognitiveIntent.COMPARISON_ANALYSIS, CognitiveIntent.DEVIATION],
            SessionPhase.EXECUTION: [CognitiveIntent.EXECUTION_START, CognitiveIntent.VERIFICATION, CognitiveIntent.ERROR_CORRECTION],
            SessionPhase.REFLECTION: [CognitiveIntent.SILENCE_REFLECTION, CognitiveIntent.META_COGNITION, CognitiveIntent.ERROR_CORRECTION],
        }
        expected = phase_to_intents.get(session_state.phase, [])
        if current_chunk.intent_raw in expected:
            return {
                "best_intent": current_chunk.intent_raw,
                "score": 0.6,
                "confidence_floor": max(current_chunk.raw_confidence, 0.64),
                "notes": [f"Current session phase {session_state.phase.value} supports the raw intent directly."],
            }
        if current_chunk.intent_raw == CognitiveIntent.UNKNOWN and expected:
            promoted = expected[0]
            return {
                "best_intent": promoted,
                "score": 0.35,
                "confidence_floor": current_chunk.raw_confidence,
                "notes": [f"Phase prior kept the chunk within the expected {session_state.phase.value} intent family."],
            }
        return {"best_intent": None, "score": 0.0, "confidence_floor": current_chunk.raw_confidence, "notes": []}

    def _deviation_signal(self, current_chunk: CognitiveChunk, session_state: SessionState, profile: dict[str, Any]) -> dict[str, object]:
        transcript = (current_chunk.transcript or "").lower().strip()
        if not transcript or not profile.get("method_bags"):
            return {"is_deviation": False, "confidence_floor": current_chunk.raw_confidence, "notes": []}

        transcript_tokens = set(self._tokenize(transcript))
        optimal_tokens = profile.get("optimal_method_tokens", set())
        if not optimal_tokens:
            return {"is_deviation": False, "confidence_floor": current_chunk.raw_confidence, "notes": []}

        best_non_optimal_score = 0.0
        best_non_optimal_name = None
        transcript_counter = Counter(transcript_tokens)
        for method_name, bag in profile["method_bags"]:
            if method_name.lower() in {path.lower() for path in (session_state.problem_structure.optimal_path if session_state.problem_structure else [])}:
                continue
            score = self._cosine_similarity(transcript_counter, bag)
            if score > best_non_optimal_score:
                best_non_optimal_score = score
                best_non_optimal_name = method_name

        optimal_overlap = len(transcript_tokens & optimal_tokens)
        off_topic_hits = len(current_chunk.semantic_signals.off_topic_markers)
        is_deviation = (
            best_non_optimal_score >= 0.42
            and optimal_overlap == 0
            and (off_topic_hits > 0 or current_chunk.intent_raw in {CognitiveIntent.DEVIATION, CognitiveIntent.UNKNOWN})
        )
        notes: list[str] = []
        if is_deviation and best_non_optimal_name:
            notes.append(
                f"Transcript aligned with alternative method '{best_non_optimal_name}' while missing optimal-path tokens."
            )
        return {
            "is_deviation": is_deviation,
            "confidence_floor": max(current_chunk.raw_confidence, min(0.87, 0.58 + (best_non_optimal_score * 0.4))),
            "notes": notes,
        }

    def _tokenize(self, text: str) -> list[str]:
        return [token.lower() for token in TOKEN_PATTERN.findall(text)]

    def _cosine_similarity(self, left: Counter[str], right: Counter[str]) -> float:
        dot = sum(left[token] * right.get(token, 0) for token in left)
        if dot <= 0:
            return 0.0
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _certainty_from(self, *, confidence: float, ambiguity_score: float) -> IntentCertainty:
        if confidence >= 0.8 and ambiguity_score <= 0.3:
            return IntentCertainty.STRONG
        if confidence >= 0.6 and ambiguity_score <= 0.58:
            return IntentCertainty.WEAK
        return IntentCertainty.AMBIGUOUS


context_window_engine = ContextWindowEngine()
