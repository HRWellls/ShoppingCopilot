from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentConfig:
    catalog_path: Path = Path("data/catalog.jsonl")
    trace_enabled: bool = False
    trace_path: Path = Path(".runtime/turns.jsonl")
    description_max_chars: int = 2_000
    query_token_limit: int = 40
    retrieval_limit: int = 300
    cache_entries: int = 64
    max_turns: int = 10
    config_version: str = "phase2-mvp-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "catalog_path", Path(self.catalog_path))
        object.__setattr__(self, "trace_path", Path(self.trace_path))
        positive = {
            "description_max_chars": self.description_max_chars,
            "query_token_limit": self.query_token_limit,
            "retrieval_limit": self.retrieval_limit,
            "cache_entries": self.cache_entries,
            "max_turns": self.max_turns,
        }
        for name, value in positive.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_turns > 10:
            raise ValueError("max_turns must be at most 10")
        if not self.config_version.strip():
            raise ValueError("config_version must not be empty")
