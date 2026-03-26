from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_engine.app.llm_budget import LLMBudgetController


def test_budget_blocks_after_limit() -> None:
    controller = LLMBudgetController()
    controller.reset("session_test")
    state = controller.snapshot("session_test")
    state.max_calls = 2

    assert controller.consume("session_test", reason="first")
    assert controller.consume("session_test", reason="second")
    assert not controller.consume("session_test", reason="third")
