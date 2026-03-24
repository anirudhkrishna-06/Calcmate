from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import get_settings
from .contracts import CognitiveChunk, CognitiveIntent, SessionState
from .state import build_timeline_metrics

try:
    import joblib
    import numpy as np
    import pandas as pd
except ImportError:  # pragma: no cover - handled gracefully at runtime
    joblib = None
    np = None
    pd = None


logger = logging.getLogger("cognitive_engine.predictive_analytics")


@dataclass
class LoadedArtifacts:
    regression: dict[str, Any]
    classification: dict[str, Any]


class PredictiveAnalyticsService:
    """Lazy, failure-safe wrapper around the saved ML artifacts."""

    def __init__(self) -> None:
        self._artifacts: LoadedArtifacts | None = None
        self._load_error: str | None = None

    def build_report_payload(self, session_state: SessionState) -> dict[str, Any]:
        settings = get_settings().predictive_analytics
        base_payload: dict[str, Any] = {
            "enabled": settings.enabled,
            "available": False,
            "model_status": "disabled" if not settings.enabled else "unavailable",
            "summary": "",
            "highlights": [],
            "recommendations": [],
        }

        if not settings.enabled:
            base_payload["summary"] = "Predictive analytics is disabled for this runtime."
            return base_payload

        if joblib is None or np is None or pd is None:
            base_payload["model_status"] = "dependency_missing"
            base_payload["summary"] = (
                "Predictive analytics could not run because runtime ML dependencies are missing."
            )
            return base_payload

        artifacts = self._load_artifacts()
        if artifacts is None:
            base_payload["model_status"] = "load_failed"
            base_payload["summary"] = (
                self._load_error
                or "Predictive analytics models could not be loaded."
            )
            return base_payload

        try:
            regression_artifact = artifacts.regression
            classification_artifact = artifacts.classification
            early_chunk_count = int(
                regression_artifact.get(
                    "early_chunk_count",
                    settings.early_chunk_count,
                )
            )
            features, observed_total_time = self._extract_session_features(
                session_state,
                early_chunk_count=early_chunk_count,
            )
            regression_input = self._align_features_to_artifact(
                features,
                regression_artifact,
            )
            classification_input = self._align_features_to_artifact(
                features,
                classification_artifact,
            )

            predicted_total_time = float(
                regression_artifact["model"].predict(regression_input)[0]
            )
            prob_final_correct = float(
                classification_artifact["model"].predict_proba(classification_input)[0][1]
            )
            confusion_probability = max(0.0, min(1.0, 1.0 - prob_final_correct))
            payload = self._build_prediction_payload(
                session_state=session_state,
                features=features,
                observed_total_time=observed_total_time,
                predicted_total_time=predicted_total_time,
                confusion_probability=confusion_probability,
                regression_artifact=regression_artifact,
                classification_artifact=classification_artifact,
            )
            return payload
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            logger.warning("Predictive analytics failed | session=%s error=%s", session_state.session_id, exc)
            base_payload["model_status"] = "prediction_failed"
            base_payload["summary"] = f"Predictive analytics failed during report generation: {exc}"
            return base_payload

    def _load_artifacts(self) -> LoadedArtifacts | None:
        if self._artifacts is not None:
            return self._artifacts
        if self._load_error is not None:
            return None

        settings = get_settings().predictive_analytics
        model_dir = settings.models_dir
        regression_path = model_dir / settings.regression_model_filename
        classification_path = model_dir / settings.classification_model_filename

        try:
            regression_artifact = joblib.load(regression_path)
            classification_artifact = joblib.load(classification_path)
            self._artifacts = LoadedArtifacts(
                regression=regression_artifact,
                classification=classification_artifact,
            )
            logger.info(
                "Predictive analytics artifacts loaded | regression=%s classification=%s",
                regression_path,
                classification_path,
            )
            return self._artifacts
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            self._load_error = (
                f"Could not load predictive artifacts from {model_dir}: {exc}"
            )
            logger.warning(self._load_error)
            return None

    def _extract_session_features(
        self,
        session_state: SessionState,
        *,
        early_chunk_count: int,
    ) -> tuple[dict[str, Any], float]:
        chunks = list(session_state.chunks)
        metrics = build_timeline_metrics(session_state)
        validation_state = session_state.validation_state
        observed_total_time = self._get_observed_total_time(session_state, chunks)
        normalized_chunks = [self._normalize_chunk(chunk) for chunk in chunks]

        deviation_time = sum(
            chunk["time"] for chunk in normalized_chunks if not chunk["correct_path"]
        )
        silence_time = sum(
            chunk["time"]
            for chunk in normalized_chunks
            if chunk["intent"] == CognitiveIntent.SILENCE_REFLECTION.value
        )
        strategy_delay = float(metrics.strategy_delay_seconds)

        features: dict[str, Any] = {
            "student_id": session_state.session_id,
            "problem_id": (
                session_state.problem_payload.problem_id
                if session_state.problem_payload
                else session_state.session_id
            ),
            "domain": self._resolve_domain(session_state),
            "difficulty": self._resolve_difficulty(session_state),
            "student_type": self._resolve_student_type(session_state, observed_total_time),
            "strategy_delay": strategy_delay,
            "deviation_time": deviation_time,
            "deviation_ratio": self._safe_divide(deviation_time, observed_total_time),
            "strategy_delay_ratio": self._safe_divide(
                strategy_delay,
                observed_total_time,
            ),
            "avg_alignment_score": self._compute_weighted_alignment(normalized_chunks),
            "silence_ratio": self._safe_divide(silence_time, observed_total_time),
            "number_of_chunks": len(normalized_chunks),
            "number_of_strategy_switches": self._compute_strategy_switches(
                normalized_chunks
            ),
            "avg_confidence": float(
                np.nanmean([chunk["confidence"] for chunk in normalized_chunks])
            )
            if normalized_chunks
            else 0.0,
            "inefficiency_score": float(validation_state.inefficiency_score),
        }

        features.update(
            self._compute_intent_distribution(normalized_chunks, observed_total_time)
        )
        features.update(
            self._compute_early_features(
                normalized_chunks,
                early_chunk_count=early_chunk_count,
            )
        )

        return features, observed_total_time

    def _normalize_chunk(self, chunk: CognitiveChunk) -> dict[str, Any]:
        duration = max(
            float(chunk.timestamp.end_time) - float(chunk.timestamp.start_time),
            0.0,
        )
        normalized_intent = self._normalize_intent_name(chunk.intent_refined)
        return {
            "intent": normalized_intent,
            "time": duration,
            "correct_path": not bool(chunk.deviation_flag),
            "confidence": float(chunk.refined_confidence),
            "alignment_score": float(chunk.semantic_signals.problem_alignment_score),
        }

    def _normalize_intent_name(self, intent: CognitiveIntent) -> str:
        if intent in {
            CognitiveIntent.PROBLEM_UNDERSTANDING,
            CognitiveIntent.CONCEPTUAL_EXPLANATION,
            CognitiveIntent.WORKING_MEMORY_RETRIEVAL,
        }:
            return CognitiveIntent.PROBLEM_UNDERSTANDING.value
        if intent in {
            CognitiveIntent.STRATEGY_SELECTION,
            CognitiveIntent.COMPARISON_ANALYSIS,
            CognitiveIntent.META_COGNITION,
        }:
            return CognitiveIntent.STRATEGY_SELECTION.value
        if intent in {
            CognitiveIntent.EXECUTION_START,
            CognitiveIntent.SOLUTION_SUMMARY,
            CognitiveIntent.ERROR_CORRECTION,
            CognitiveIntent.CONFIDENCE_EXPRESSION,
        }:
            return "execution"
        if intent == CognitiveIntent.STUCK_STATE:
            return CognitiveIntent.DEVIATION.value
        return intent.value

    def _get_observed_total_time(
        self,
        session_state: SessionState,
        chunks: list[CognitiveChunk],
    ) -> float:
        timeline_end = max(
            (
                float(item.at_seconds)
                for item in session_state.timeline
                if item.event_type == "SESSION_ENDED"
            ),
            default=0.0,
        )
        chunk_end = max(
            (float(chunk.timestamp.end_time) for chunk in chunks),
            default=0.0,
        )
        return max(timeline_end, chunk_end)

    def _compute_weighted_alignment(self, chunks: list[dict[str, Any]]) -> float:
        total_chunk_time = sum(chunk["time"] for chunk in chunks)
        if total_chunk_time <= 0:
            valid_scores = [
                chunk["alignment_score"]
                for chunk in chunks
                if not pd.isna(chunk["alignment_score"])
            ]
            return float(np.mean(valid_scores)) if valid_scores else 0.0

        weighted_sum = sum(
            (0.0 if pd.isna(chunk["alignment_score"]) else chunk["alignment_score"])
            * chunk["time"]
            for chunk in chunks
        )
        return float(weighted_sum / total_chunk_time)

    def _compute_strategy_switches(self, chunks: list[dict[str, Any]]) -> int:
        if len(chunks) <= 1:
            return 0

        switches = 0
        previous_intent = chunks[0]["intent"]
        for chunk in chunks[1:]:
            current_intent = chunk["intent"]
            if current_intent != previous_intent:
                switches += 1
            previous_intent = current_intent
        return switches

    def _compute_intent_distribution(
        self,
        chunks: list[dict[str, Any]],
        session_total_time: float,
    ) -> dict[str, float]:
        if not chunks:
            return {}

        intent_time: dict[str, float] = {}
        for chunk in chunks:
            intent_time[chunk["intent"]] = (
                intent_time.get(chunk["intent"], 0.0) + chunk["time"]
            )

        if session_total_time <= 0:
            total_chunks = len(chunks)
            return {
                f"intent_pct__{intent}": count / total_chunks
                for intent, count in {
                    intent: sum(1 for chunk in chunks if chunk["intent"] == intent)
                    for intent in intent_time
                }.items()
            }

        return {
            f"intent_pct__{intent}": intent_seconds / session_total_time
            for intent, intent_seconds in intent_time.items()
        }

    def _compute_early_features(
        self,
        chunks: list[dict[str, Any]],
        *,
        early_chunk_count: int,
    ) -> dict[str, float]:
        early_chunks = chunks[:early_chunk_count]
        early_total_time = sum(chunk["time"] for chunk in early_chunks)
        early_deviation_time = sum(
            chunk["time"] for chunk in early_chunks if not chunk["correct_path"]
        )
        early_silence_time = sum(
            chunk["time"]
            for chunk in early_chunks
            if chunk["intent"] == CognitiveIntent.SILENCE_REFLECTION.value
        )

        return {
            "early_avg_alignment": self._compute_weighted_alignment(early_chunks),
            "early_deviation_ratio": self._safe_divide(
                early_deviation_time,
                early_total_time,
            ),
            "early_silence_ratio": self._safe_divide(
                early_silence_time,
                early_total_time,
            ),
        }

    def _align_features_to_artifact(
        self,
        features: dict[str, Any],
        artifact: dict[str, Any],
    ):
        inference_row = pd.DataFrame([features])
        return inference_row.reindex(columns=artifact["feature_columns"], fill_value=np.nan)

    def _resolve_domain(self, session_state: SessionState) -> str:
        if session_state.problem_structure and session_state.problem_structure.domain:
            return str(session_state.problem_structure.domain)
        structured = (
            session_state.problem_payload.structured_representation
            if session_state.problem_payload
            else {}
        )
        return str(structured.get("domain") or "unknown")

    def _resolve_difficulty(self, session_state: SessionState) -> str:
        structured = (
            session_state.problem_payload.structured_representation
            if session_state.problem_payload
            else {}
        )
        parsing_summary = (
            session_state.problem_structure.parsing_summary
            if session_state.problem_structure
            else {}
        )
        return str(
            structured.get("difficulty")
            or parsing_summary.get("difficulty")
            or "unknown"
        )

    def _resolve_student_type(
        self,
        session_state: SessionState,
        observed_total_time: float,
    ) -> str:
        vs = session_state.validation_state
        if observed_total_time <= 35 and vs.path_alignment_score >= 0.75:
            return "fast_accurate"
        if observed_total_time >= 90 and vs.path_alignment_score >= 0.7:
            return "slow_correct"
        if vs.deviation_score >= 0.35 or vs.delay_score >= 0.4:
            return "confused_explorer"
        return "unknown"

    def _build_prediction_payload(
        self,
        *,
        session_state: SessionState,
        features: dict[str, Any],
        observed_total_time: float,
        predicted_total_time: float,
        confusion_probability: float,
        regression_artifact: dict[str, Any],
        classification_artifact: dict[str, Any],
    ) -> dict[str, Any]:
        delta_seconds = observed_total_time - predicted_total_time
        delta_ratio = self._safe_divide(delta_seconds, predicted_total_time)
        confusion_risk = self._confusion_risk_label(confusion_probability)
        pace_label = self._pace_label(delta_ratio)
        summary = self._build_summary(
            observed_total_time=observed_total_time,
            predicted_total_time=predicted_total_time,
            confusion_risk=confusion_risk,
            pace_label=pace_label,
        )
        highlights = self._build_highlights(
            session_state=session_state,
            features=features,
            confusion_probability=confusion_probability,
            pace_label=pace_label,
        )
        recommendations = self._build_recommendations(
            session_state=session_state,
            features=features,
            confusion_probability=confusion_probability,
            pace_label=pace_label,
        )

        return {
            "enabled": True,
            "available": True,
            "model_status": "ready",
            "summary": summary,
            "predicted_total_time_seconds": round(predicted_total_time, 2),
            "observed_total_time_seconds": round(observed_total_time, 2),
            "time_delta_seconds": round(delta_seconds, 2),
            "time_delta_ratio": round(delta_ratio, 4),
            "pace_label": pace_label,
            "confusion_probability": round(confusion_probability, 4),
            "confusion_risk_level": confusion_risk,
            "feature_snapshot": {
                "domain": features.get("domain"),
                "difficulty": features.get("difficulty"),
                "student_type": features.get("student_type"),
                "strategy_delay_seconds": round(float(features.get("strategy_delay", 0.0)), 2),
                "strategy_delay_ratio": round(
                    float(features.get("strategy_delay_ratio", 0.0)),
                    4,
                ),
                "deviation_ratio": round(float(features.get("deviation_ratio", 0.0)), 4),
                "silence_ratio": round(float(features.get("silence_ratio", 0.0)), 4),
                "avg_alignment_score": round(
                    float(features.get("avg_alignment_score", 0.0)),
                    4,
                ),
                "avg_confidence": round(float(features.get("avg_confidence", 0.0)), 4),
                "number_of_chunks": int(features.get("number_of_chunks", 0) or 0),
                "number_of_strategy_switches": int(
                    features.get("number_of_strategy_switches", 0) or 0
                ),
                "early_avg_alignment": round(
                    float(features.get("early_avg_alignment", 0.0)),
                    4,
                ),
                "early_deviation_ratio": round(
                    float(features.get("early_deviation_ratio", 0.0)),
                    4,
                ),
            },
            "highlights": highlights,
            "recommendations": recommendations,
            "model_artifacts": {
                "regression_features": len(regression_artifact.get("feature_columns", [])),
                "classification_features": len(
                    classification_artifact.get("feature_columns", [])
                ),
                "early_chunk_count": int(
                    regression_artifact.get("early_chunk_count", 0) or 0
                ),
            },
        }

    def _build_summary(
        self,
        *,
        observed_total_time: float,
        predicted_total_time: float,
        confusion_risk: str,
        pace_label: str,
    ) -> str:
        return (
            f"The predictive layer estimates an expected solving time of "
            f"{predicted_total_time:.1f}s versus an observed {observed_total_time:.1f}s. "
            f"Overall pace was {pace_label.replace('_', ' ')}, and the modeled confusion risk is {confusion_risk}."
        )

    def _build_highlights(
        self,
        *,
        session_state: SessionState,
        features: dict[str, Any],
        confusion_probability: float,
        pace_label: str,
    ) -> list[str]:
        vs = session_state.validation_state
        highlights: list[str] = [
            f"Modeled confusion probability: {confusion_probability:.1%}.",
            f"Observed strategy delay consumed {float(features.get('strategy_delay_ratio', 0.0)):.1%} of the thinking window.",
        ]
        if vs.path_alignment_score >= 0.75:
            highlights.append(
                f"Path alignment stayed strong at {vs.path_alignment_score:.1%}, which supports reliable reasoning."
            )
        if float(features.get("early_deviation_ratio", 0.0)) > 0.2:
            highlights.append(
                "Early chunks showed noticeable off-path behavior, which likely increased cognitive load."
            )
        if pace_label == "slower_than_expected":
            highlights.append(
                "The student spent longer than the model expected, suggesting hesitation or over-analysis."
            )
        elif pace_label == "faster_than_expected":
            highlights.append(
                "The student reached a solution faster than expected, indicating confident progression."
            )
        return highlights[:4]

    def _build_recommendations(
        self,
        *,
        session_state: SessionState,
        features: dict[str, Any],
        confusion_probability: float,
        pace_label: str,
    ) -> list[str]:
        vs = session_state.validation_state
        recommendations: list[str] = []
        if confusion_probability >= 0.35:
            recommendations.append(
                "Add a stronger note in the report around confusion risk and suggest a brief verification checklist."
            )
        if float(features.get("strategy_delay_ratio", 0.0)) >= 0.4:
            recommendations.append(
                "Call out the long strategy-selection window and recommend choosing the governing formula earlier."
            )
        if vs.oscillation_index >= 0.35:
            recommendations.append(
                "Mention method switching explicitly and encourage committing to one path before restarting."
            )
        if pace_label == "faster_than_expected" and vs.path_alignment_score >= 0.75:
            recommendations.append(
                "Reinforce the student's efficient reasoning pattern as a strength to keep repeating."
            )
        if not recommendations:
            recommendations.append(
                "Use the prediction as supporting context, but keep the report focused on alignment, pacing, and verification habits."
            )
        return recommendations[:4]

    def _confusion_risk_label(self, confusion_probability: float) -> str:
        if confusion_probability >= 0.45:
            return "high"
        if confusion_probability >= 0.2:
            return "moderate"
        return "low"

    def _pace_label(self, delta_ratio: float) -> str:
        if delta_ratio >= 0.15:
            return "slower_than_expected"
        if delta_ratio <= -0.15:
            return "faster_than_expected"
        return "on_expected_pace"

    def _safe_divide(self, numerator: float, denominator: float) -> float:
        if denominator in (0, 0.0):
            return 0.0
        return float(numerator) / float(denominator)


predictive_analytics_service = PredictiveAnalyticsService()
