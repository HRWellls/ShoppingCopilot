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
    lexical_enabled: bool = True
    attribute_retrieval_enabled: bool = False
    attribute_reranking_enabled: bool = False
    recommendation_with_clarification_enabled: bool = False
    override_invalidation_enabled: bool = False
    optimized_single_pass_enabled: bool = False
    dense_enabled: bool = False
    dense_build_allowed: bool = False
    dense_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    dense_model_path: Path | None = Path(".runtime/models/all-MiniLM-L6-v2")
    dense_index_path: Path = Path(".runtime/indexes/catalog-all-MiniLM-L6-v2.faiss")
    dense_batch_size: int = 128
    lexical_k: int = 300
    dense_k: int = 300
    fused_k: int = 150
    k_rrf: int = 60
    buying_weights: tuple[float, float, float, float] = (0.45, 0.25, 0.20, 0.10)
    browsing_weights: tuple[float, float, float, float] = (0.30, 0.45, 0.15, 0.10)
    soft_slot_ttl: int = 3
    relaxation_enabled: bool = True
    clarification_enabled: bool = True
    clarify_count_threshold: int = 100
    late_turn: int = 8
    clarification_margin_threshold: float = 0.01
    clarification_no_shrink_limit: int = 4
    clarification_stability_turns: int = 3
    llm_enabled: bool = False
    llm_model: str = "deepseek-v4-flash"
    llm_endpoint: str = "https://api.deepseek.com/chat/completions"
    llm_timeout_ms: int = 600
    llm_max_response_bytes: int = 64_000
    multiturn_state_enabled: bool = False
    intent_routing_enabled: bool = False
    intent_policy_enabled: bool = False
    intent_model_mode: str = "off"
    intent_model_id: str = "cross-encoder/nli-deberta-v3-xsmall"
    intent_classifier_strategy: str = "single"
    intent_hypothesis_version: str = "shopping-intent-v1"
    intent_model_switch_enabled: bool = True
    intent_model_path: Path | None = None
    intent_manifest_path: Path | None = None
    intent_input_max_chars: int = 800
    intent_initial_confidence: float = 0.80
    intent_initial_margin: float = 0.15
    intent_switch_confidence: float = 0.90
    intent_switch_margin: float = 0.20
    intent_timeout_ms: int = 100
    intent_p95_budget_ms: float = 25.0
    api_key_env: str = "DEEPSEEK_API_KEY"
    api_key_path: Path = Path("api.env")
    max_turns: int = 10
    config_version: str = "phase3-hybrid-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "catalog_path", Path(self.catalog_path))
        object.__setattr__(self, "trace_path", Path(self.trace_path))
        object.__setattr__(self, "dense_index_path", Path(self.dense_index_path))
        object.__setattr__(self, "api_key_path", Path(self.api_key_path))
        if self.dense_model_path is not None:
            object.__setattr__(self, "dense_model_path", Path(self.dense_model_path))
        if self.intent_model_path is not None:
            object.__setattr__(self, "intent_model_path", Path(self.intent_model_path))
        if self.intent_manifest_path is not None:
            object.__setattr__(self, "intent_manifest_path", Path(self.intent_manifest_path))
        positive = {
            "description_max_chars": self.description_max_chars,
            "query_token_limit": self.query_token_limit,
            "retrieval_limit": self.retrieval_limit,
            "cache_entries": self.cache_entries,
            "dense_batch_size": self.dense_batch_size,
            "lexical_k": self.lexical_k,
            "dense_k": self.dense_k,
            "fused_k": self.fused_k,
            "k_rrf": self.k_rrf,
            "soft_slot_ttl": self.soft_slot_ttl,
            "clarify_count_threshold": self.clarify_count_threshold,
            "late_turn": self.late_turn,
            "clarification_no_shrink_limit": self.clarification_no_shrink_limit,
            "clarification_stability_turns": self.clarification_stability_turns,
            "llm_timeout_ms": self.llm_timeout_ms,
            "llm_max_response_bytes": self.llm_max_response_bytes,
            "intent_input_max_chars": self.intent_input_max_chars,
            "intent_timeout_ms": self.intent_timeout_ms,
            "max_turns": self.max_turns,
        }
        for name, value in positive.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_turns > 10:
            raise ValueError("max_turns must be at most 10")
        if self.attribute_reranking_enabled and not self.attribute_retrieval_enabled:
            raise ValueError("attribute reranking requires attribute retrieval")
        if self.optimized_single_pass_enabled and not self.attribute_reranking_enabled:
            raise ValueError("single-pass ranking requires attribute reranking")
        if not 100 <= self.fused_k <= 200:
            raise ValueError("fused_k must be between 100 and 200")
        if self.late_turn > self.max_turns:
            raise ValueError("late_turn must not exceed max_turns")
        for weights in (self.buying_weights, self.browsing_weights):
            if len(weights) != 4 or any(value < 0 for value in weights) or not any(weights):
                raise ValueError("retrieval weights must contain four non-negative values")
        if not self.config_version.strip():
            raise ValueError("config_version must not be empty")
        if self.intent_model_mode not in {"off", "shadow", "active"}:
            raise ValueError("intent_model_mode must be off, shadow, or active")
        if self.intent_classifier_strategy not in {"single", "two_stage"}:
            raise ValueError("intent_classifier_strategy must be single or two_stage")
        if self.intent_hypothesis_version not in {"shopping-intent-v1", "shopping-intent-v2"}:
            raise ValueError("intent_hypothesis_version is unsupported")
        for name, value in {
            "intent_initial_confidence": self.intent_initial_confidence,
            "intent_initial_margin": self.intent_initial_margin,
            "intent_switch_confidence": self.intent_switch_confidence,
            "intent_switch_margin": self.intent_switch_margin,
        }.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if isinstance(self.intent_p95_budget_ms, bool) or self.intent_p95_budget_ms <= 0:
            raise ValueError("intent_p95_budget_ms must be positive")
        if isinstance(self.clarification_margin_threshold, bool) or self.clarification_margin_threshold < 0:
            raise ValueError("clarification_margin_threshold must be non-negative")

    def public_snapshot(self) -> dict[str, object]:
        return {
            name: str(value) if isinstance(value, Path) else value
            for name, value in self.__dict__.items()
            if name not in {
                "api_key_env", "api_key_path", "intent_model_path", "intent_manifest_path"
            }
        }
