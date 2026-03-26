from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import get_settings

logger = logging.getLogger("cognitive_engine.llm_budget")


@dataclass
class BudgetState:
    used: int = 0
    max_calls: int = 4

    @property
    def remaining(self) -> int:
        return max(self.max_calls - self.used, 0)


class LLMBudgetController:
    def __init__(self) -> None:
        self._states: dict[str, BudgetState] = {}

    def reset(self, session_id: str) -> None:
        max_calls = get_settings().llm_budget_max_calls_per_session
        self._states[session_id] = BudgetState(used=0, max_calls=max_calls)
        logger.info("LLM budget reset | session=%s max_calls=%d", session_id, max_calls)

    def snapshot(self, session_id: str) -> BudgetState:
        if session_id not in self._states:
            self.reset(session_id)
        return self._states[session_id]

    def allow(self, session_id: str, *, cost: int = 1) -> bool:
        state = self.snapshot(session_id)
        allowed = state.used + cost <= state.max_calls
        if not allowed:
            logger.warning(
                "LLM budget exhausted | session=%s used=%d max_calls=%d requested_cost=%d",
                session_id,
                state.used,
                state.max_calls,
                cost,
            )
        return allowed

    def consume(self, session_id: str, *, cost: int = 1, reason: str = "") -> bool:
        if not self.allow(session_id, cost=cost):
            return False
        state = self.snapshot(session_id)
        state.used += cost
        logger.info(
            "LLM budget consumed | session=%s used=%d remaining=%d reason=%s",
            session_id,
            state.used,
            state.remaining,
            reason or "<unspecified>",
        )
        return True


llm_budget_controller = LLMBudgetController()
