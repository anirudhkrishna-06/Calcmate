from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

import httpx

from .config import get_settings
from .contracts import (
    StartTutoringSessionResponse,
    TutoringChatResponse,
    TutoringProgress,
)
from .llm_budget import llm_budget_controller

logger = logging.getLogger("cognitive_engine.report_tutoring")


def _extract_json(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


class ReportTutoringService:
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._active_session_id: str | None = None

    def _flatten_items(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        def add_analysis(analysis: dict[str, Any] | None, question_number: int | None) -> None:
            if not analysis or not analysis.get("available"):
                return
            for stage_key, stage_name in (("thinking_mistakes", "thinking"), ("solving_mistakes", "solving")):
                for raw_item in analysis.get(stage_key, []) or []:
                    if not isinstance(raw_item, dict):
                        continue
                    items.append(
                        {
                            "id": raw_item.get("finding_id") or f"item_{uuid4().hex[:10]}",
                            "question_number": raw_item.get("question_number") or question_number,
                            "stage": raw_item.get("stage") or stage_name,
                            "title": str(raw_item.get("title", "")).strip(),
                            "observed_issue": str(raw_item.get("observed_issue", "")).strip(),
                            "evidence": str(raw_item.get("evidence", "")).strip(),
                            "why_it_failed": str(raw_item.get("why_it_failed", "")).strip(),
                            "correction": str(raw_item.get("correction", "")).strip(),
                            "guided_question": str(raw_item.get("guided_question", "")).strip(),
                            "hint": str(raw_item.get("hint", "")).strip(),
                            "attempts": 0,
                            "question_label": f"Question {raw_item.get('question_number') or question_number or 1}",
                        }
                    )

        rounds = report.get("rounds") or []
        if rounds:
            for index, round_item in enumerate(rounds, start=1):
                round_report = (round_item or {}).get("report") or {}
                add_analysis(round_report.get("wrong_step_analysis"), (round_item or {}).get("questionNumber") or index)
        else:
            add_analysis(report.get("wrong_step_analysis"), None)

        return [item for item in items if item["guided_question"] or item["title"]]

    def _build_ability_profile(self, report: dict[str, Any]) -> dict[str, Any]:
        timeline = report.get("timeline_metrics") or {}
        validation = report.get("validation_state") or {}
        predictive = report.get("predictive_analytics") or {}
        understanding = float(timeline.get("understanding_time_seconds", 0.0) or 0.0)
        strategy = float(timeline.get("strategy_delay_seconds", 0.0) or 0.0)
        execution = float(timeline.get("execution_time_seconds", 0.0) or 0.0)
        confusion = float(predictive.get("confusion_probability", 0.0) or 0.0)
        alignment = float(validation.get("path_alignment_score", 0.0) or 0.0)

        if confusion >= 0.45 or alignment < 0.35:
            tone = "gentle"
        elif understanding + strategy > execution + 12:
            tone = "supportive"
        else:
            tone = "direct"

        return {
            "tone": tone,
            "understanding_time_seconds": understanding,
            "strategy_time_seconds": strategy,
            "execution_time_seconds": execution,
            "confusion_probability": confusion,
            "alignment_score": alignment,
        }

    def _progress(self, session: dict[str, Any]) -> TutoringProgress:
        items = session["items"]
        current = items[session["current_index"]] if items and session["current_index"] < len(items) else {}
        completed = session["current_index"] >= len(items)
        return TutoringProgress(
            total_questions=len(items),
            completed_questions=min(session["current_index"], len(items)),
            current_question_index=min(session["current_index"] + 1, len(items)) if items else 0,
            current_title=str(current.get("title", "")),
            current_stage=str(current.get("stage", "")),
            ready_for_next=bool(session.get("ready_for_next", False)),
            completed=completed,
        )

    def _compose_question(self, item: dict[str, Any]) -> str:
        question_label = f"Question {item['question_number']}" if item.get("question_number") else "This question"
        stage_label = str(item.get("stage", "thinking")).capitalize()
        prompt = item.get("guided_question") or f"What should be corrected in the {item.get('stage', 'thinking')} here?"
        hint = item.get("hint") or "Use the problem's givens and the target unknown to rebuild the step."
        return (
            f"{question_label}. {stage_label} focus: {item.get('title', 'Wrong step')}.\n"
            f"{prompt}\n"
            f"Clue: {hint}"
        )

    async def _call_fast_gemini(self, prompt: str) -> tuple[dict[str, Any], str]:
        settings = get_settings()
        candidates = [
            ("GEMINI4", settings.gemini4.api_key, settings.gemini4.model, settings.gemini4.timeout_seconds),
            ("GEMINI3", settings.gemini3.api_key, settings.gemini3.model, settings.gemini3.timeout_seconds),
            ("GEMINI2", settings.gemini2.api_key, settings.gemini2.model, settings.gemini2.timeout_seconds),
        ]

        last_error = "No Gemini tutoring provider configured."
        for label, api_key, model, timeout_seconds in candidates:
            if not api_key:
                continue
            if not llm_budget_controller.consume(self._active_session_id, reason=f"tutoring_{label.lower()}"):
                return {}, "Session LLM budget exhausted."
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                logger.info("Tutoring model request | session=%s provider=%s prompt_chars=%d", self._active_session_id, label, len(prompt))
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.post(
                        url,
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "temperature": 0.25,
                                "maxOutputTokens": 700,
                                "responseMimeType": "application/json",
                            },
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                raw_text = "".join(
                    part.get("text", "")
                    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                )
                parsed = _extract_json(raw_text)
                if parsed:
                    logger.info("Tutoring model response parsed | session=%s provider=%s", self._active_session_id, label)
                    return parsed, label
                last_error = f"{label} returned invalid JSON."
            except Exception as exc:
                last_error = f"{label}: {exc}"
                logger.warning("Tutoring model call failed | provider=%s error=%s", label, exc)

        return {}, last_error

    def _fallback_feedback(self, item: dict[str, Any], student_message: str) -> dict[str, Any]:
        lower_message = student_message.lower()
        correction = str(item.get("correction", "")).lower()
        why_failed = str(item.get("why_it_failed", "")).lower()
        overlap = 0
        for token in {word for word in re_split_words(correction + " " + why_failed) if len(word) > 4}:
            if token in lower_message:
                overlap += 1

        if overlap >= 3 or len(student_message.split()) >= 25:
            return {
                "understanding_status": "solid",
                "should_advance": True,
                "assistant_message": "That explains both the mistake and the fix clearly.",
            }
        return {
            "understanding_status": "partial" if len(student_message.split()) >= 10 else "not_yet",
            "should_advance": False,
            "assistant_message": (
                f"You're close, but pin down the exact break in the step. "
                f"Focus on this clue: {item.get('hint') or item.get('correction')}"
            ),
        }

    async def start_session(self, report: dict[str, Any]) -> StartTutoringSessionResponse:
        items = self._flatten_items(report or {})
        tutoring_session_id = f"tutor_{uuid4().hex}"
        llm_budget_controller.reset(tutoring_session_id)

        session = {
            "report": report or {},
            "items": items,
            "current_index": 0,
            "history": [],
            "ready_for_next": False,
            "ability_profile": self._build_ability_profile(report or {}),
            "completed_questions": set(),
        }
        self._sessions[tutoring_session_id] = session
        logger.info(
            "Tutoring session started | session=%s items=%d tone=%s",
            tutoring_session_id,
            len(items),
            session["ability_profile"]["tone"],
        )

        if not items:
            progress = self._progress(session)
            return StartTutoringSessionResponse(
                tutoring_session_id=tutoring_session_id,
                available=False,
                intro_message="No wrong-step tutoring targets were found in this report.",
                assistant_message="The report does not contain question-level mistakes that need guided follow-up right now.",
                progress=progress,
            )

        first_question = self._compose_question(items[0])
        progress = self._progress(session)
        return StartTutoringSessionResponse(
            tutoring_session_id=tutoring_session_id,
            available=True,
            intro_message=(
                f"I found {len(items)} wrong-step target{'s' if len(items) != 1 else ''} in your report. "
                "We'll clear them question by question. We only move on after your explanation is convincing."
            ),
            assistant_message=first_question,
            progress=progress,
        )

    async def send_message(self, tutoring_session_id: str, message: str) -> TutoringChatResponse:
        session = self._sessions.get(tutoring_session_id)
        if session is None:
            raise KeyError("Tutoring session not found.")
        self._active_session_id = tutoring_session_id

        items = session["items"]
        if session["current_index"] >= len(items):
            progress = self._progress(session)
            return TutoringChatResponse(
                tutoring_session_id=tutoring_session_id,
                assistant_message="All tutoring questions are complete for this report.",
                progress=progress,
                understanding_status="solid",
                completed=True,
            )

        item = items[session["current_index"]]
        item["attempts"] = int(item.get("attempts", 0)) + 1
        logger.info(
            "Tutoring turn received | session=%s index=%d question=%s stage=%s attempts=%d chars=%d",
            tutoring_session_id,
            session["current_index"],
            item.get("question_number"),
            item.get("stage"),
            item["attempts"],
            len(message),
        )
        ability_profile = session.get("ability_profile", {})
        recent_history = session["history"][-3:]

        prompt = (
            "You are a post-report math tutor. The learner must explain why their wrong step was wrong and how to do it right. "
            "Use short clues and short coaching, ideally 1 to 3 sentences. Do not move to the next mistake unless the learner clearly shows understanding. "
            "If attempts are low, stay Socratic. If attempts are 2 or more, be a bit more explicit, but still keep the learner engaged. "
            "Match the tone to the learner profile: direct means concise and efficient, supportive means calm and encouraging, gentle means extra patience and lower cognitive load.\n\n"
            f"Learner profile: {json.dumps(ability_profile, ensure_ascii=True)}\n"
            f"Current wrong-step item: {json.dumps(item, ensure_ascii=True)}\n"
            f"Recent tutoring history: {json.dumps(recent_history, ensure_ascii=True)}\n"
            f"Student reply: {message}\n\n"
            "Return valid JSON only with keys "
            "\"understanding_status\", \"should_advance\", and \"assistant_message\". "
            "understanding_status must be one of \"not_yet\", \"partial\", or \"solid\"."
        )

        parsed, provider = await self._call_fast_gemini(prompt)
        if not parsed:
            parsed = self._fallback_feedback(item, message)
            provider = "fallback"

        understanding_status = str(parsed.get("understanding_status", "not_yet")).strip().lower()
        if understanding_status not in {"not_yet", "partial", "solid"}:
            understanding_status = "not_yet"
        should_advance = bool(parsed.get("should_advance")) and understanding_status == "solid"
        assistant_message = str(parsed.get("assistant_message", "")).strip() or (
            "Try again, but this time explain both the mistake and the corrected step."
        )

        session["history"].append(
            {
                "item_id": item["id"],
                "question_number": item.get("question_number"),
                "user": message,
                "assistant": assistant_message,
                "understanding_status": understanding_status,
                "provider": provider,
            }
        )

        if should_advance:
            current_question = item.get("question_number")
            session["current_index"] += 1
            session["ready_for_next"] = True
            if session["current_index"] < len(items):
                next_item = items[session["current_index"]]
                if current_question != next_item.get("question_number"):
                    session["completed_questions"].add(current_question)
                    assistant_message = (
                        f"{assistant_message}\n\nMoving to Question {next_item.get('question_number')}. "
                        f"Here is the next step to fix.\n{self._compose_question(next_item)}"
                    )
                else:
                    assistant_message = (
                        f"{assistant_message}\n\nGood. Stay on Question {current_question}. "
                        f"Now fix the next step.\n{self._compose_question(next_item)}"
                    )
            else:
                session["completed_questions"].add(current_question)
                assistant_message = (
                    f"{assistant_message}\n\nYou worked through every wrong-step target across all questions. "
                    "This tutoring session is now complete."
                )
        else:
            session["ready_for_next"] = False

        logger.info(
            "Tutoring turn resolved | session=%s understanding=%s advance=%s next_index=%d completed_questions=%d",
            tutoring_session_id,
            understanding_status,
            should_advance,
            session["current_index"],
            len(session["completed_questions"]),
        )
        progress = self._progress(session)
        return TutoringChatResponse(
            tutoring_session_id=tutoring_session_id,
            assistant_message=assistant_message,
            progress=progress,
            understanding_status=understanding_status,
            completed=progress.completed,
        )


def re_split_words(text: str) -> list[str]:
    import re

    return re.findall(r"[a-zA-Z]+", text.lower())


tutoring_service = ReportTutoringService()
