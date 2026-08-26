from __future__ import annotations

from pathlib import Path

from src.config import AgentConfig
from src.core import ShoppingAgentCore


class Agent:
    """Official reset/respond adapter for the deterministic stage 2 core."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        config: AgentConfig | None = None,
    ) -> None:
        self.config = config or AgentConfig(catalog_path=Path(catalog_path))
        self._core = ShoppingAgentCore(self.config)

    def reset(self, session_id: str, user_profile: dict) -> None:
        self._core.reset(session_id, user_profile)

    def respond(
        self,
        session_id: str,
        user_message: str,
        turn: int,
        top_k: int,
    ) -> dict:
        return self._core.respond(session_id, user_message, turn, top_k)
