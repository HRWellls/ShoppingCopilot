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
        *,
        embedding_provider: object | None = None,
        llm_opener: object | None = None,
    ) -> None:
        if config is None:
            path = Path(catalog_path)
            default_config = AgentConfig(catalog_path=path)
            use_persisted_dense = (
                path == Path("data/catalog.jsonl")
                and default_config.dense_index_path.exists()
                and default_config.dense_model_path is not None
                and default_config.dense_model_path.exists()
            )
            self.config = AgentConfig(catalog_path=path, dense_enabled=use_persisted_dense)
        else:
            self.config = config
        self._core = ShoppingAgentCore(self.config, embedding_provider, llm_opener)

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
