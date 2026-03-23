from __future__ import annotations

import asyncio
from typing import Dict

from .contracts import SessionState


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def create(self, state: SessionState) -> SessionState:
        self._sessions[state.session_id] = state
        self._locks.setdefault(state.session_id, asyncio.Lock())
        return state

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def save(self, state: SessionState) -> SessionState:
        self._sessions[state.session_id] = state
        self._locks.setdefault(state.session_id, asyncio.Lock())
        return state

    def get_lock(self, session_id: str) -> asyncio.Lock:
        return self._locks.setdefault(session_id, asyncio.Lock())


store = InMemorySessionStore()
