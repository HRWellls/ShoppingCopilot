from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Any

from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import SessionState


class SessionStateStore:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._sessions: dict[str, SessionState] = {}

    def reset(self, session_id: str, user_profile: dict[str, Any]) -> SessionState:
        if not isinstance(session_id, str) or not session_id.strip():
            raise AgentError(ErrorCode.PROTOCOL, "session_id must be a non-empty string")
        if not isinstance(user_profile, dict):
            raise AgentError(ErrorCode.PROTOCOL, "user_profile must be an object")
        profile_copy = MappingProxyType(deepcopy(user_profile))
        state = SessionState(session_id=session_id, user_profile=profile_copy)
        self._sessions[session_id] = state
        return state

    def get(self, session_id: str) -> SessionState:
        if not isinstance(session_id, str) or not session_id.strip():
            raise AgentError(ErrorCode.PROTOCOL, "session_id must be a non-empty string")
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise AgentError(ErrorCode.PROTOCOL, "reset must be called before respond") from exc

    def begin_turn(self, session_id: str, turn: int, message: str) -> SessionState:
        state = self.get(session_id)
        if isinstance(turn, bool) or not isinstance(turn, int):
            raise AgentError(ErrorCode.PROTOCOL, "turn must be an integer")
        if turn < 1 or turn > self._config.max_turns:
            raise AgentError(ErrorCode.PROTOCOL, "turn is outside the configured range")
        expected = state.turn_count + 1
        if turn != expected:
            raise AgentError(ErrorCode.PROTOCOL, f"expected turn {expected}")
        if not isinstance(message, str):
            raise AgentError(ErrorCode.INPUT_TYPE, "user_message must be a string")
        state.turn_count = turn
        state.history.append(message)
        return state

    def save(self, state: SessionState) -> None:
        current = self.get(state.session_id)
        if current is not state:
            raise AgentError(ErrorCode.PROTOCOL, "cannot save stale session state")

    def __contains__(self, session_id: object) -> bool:
        return isinstance(session_id, str) and session_id in self._sessions
