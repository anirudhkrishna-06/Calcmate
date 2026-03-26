from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from cognitive_engine.app.report_tutoring import ReportTutoringService


@pytest.mark.anyio
async def test_tutoring_moves_question_by_question() -> None:
    service = ReportTutoringService()
    report = {
        "rounds": [
            {
                "questionNumber": 1,
                "report": {
                    "wrong_step_analysis": {
                        "available": True,
                        "thinking_mistakes": [
                            {
                                "title": "Wrong formula choice",
                                "guided_question": "Why was the formula wrong?",
                                "hint": "Match the givens to the formula.",
                                "correction": "Use the area relation that matches the givens.",
                                "why_it_failed": "The chosen formula did not use the known values directly.",
                            }
                        ],
                        "solving_mistakes": [
                            {
                                "title": "Arithmetic slip",
                                "guided_question": "Where did the arithmetic break?",
                                "hint": "Recheck the multiplication.",
                                "correction": "Multiply carefully before simplifying.",
                                "why_it_failed": "The intermediate product was incorrect.",
                            }
                        ],
                    }
                },
            },
            {
                "questionNumber": 2,
                "report": {
                    "wrong_step_analysis": {
                        "available": True,
                        "thinking_mistakes": [
                            {
                                "title": "Missed variable isolation",
                                "guided_question": "What should have been isolated first?",
                                "hint": "Undo the constant before dividing.",
                                "correction": "Isolate x before the final division.",
                                "why_it_failed": "The variable was not isolated in the correct order.",
                            }
                        ],
                        "solving_mistakes": [],
                    }
                },
            },
        ]
    }

    start = await service.start_session(report)
    tutoring_session_id = start.tutoring_session_id

    response1 = await service.send_message(
        tutoring_session_id,
        "The formula was wrong because it did not match the givens, and I should have used the area relation that fits the known values.",
    )
    assert "Question 1" in response1.assistant_message

    response2 = await service.send_message(
        tutoring_session_id,
        "The arithmetic broke in the multiplication step, so I need to recompute that product carefully before simplifying.",
    )
    assert "Moving to Question 2" in response2.assistant_message
