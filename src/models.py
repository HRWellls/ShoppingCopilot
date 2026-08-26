from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from enum import Enum
from typing import Any, Mapping


def immutable_mapping(values: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return MappingProxyType(dict(values or {}))


@dataclass(frozen=True)
class Product:
    parent_asin: str
    title: str
    categories: tuple[str, ...]
    brand: str | None
    brand_key: str | None
    price: float | None
    features: tuple[str, ...]
    description: str
    searchable_text: str
    metadata: Mapping[str, Any]
    attributes: Mapping[str, frozenset[str]]
    catalog_order: int


@dataclass(frozen=True)
class IntentResult:
    label: str
    confidence: float
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.label not in {"buying", "browsing", "unknown"}:
            raise ValueError("unsupported intent label")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("intent confidence must be between 0 and 1")


@dataclass
class ConstraintSet:
    price_min: float | None = None
    price_max: float | None = None
    brand: str | None = None
    color: str | None = None
    material: str | None = None
    category: str | None = None
    size: str | None = None
    exclusions: dict[str, frozenset[str]] = field(default_factory=dict)

    def active_names(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in (
                "price_min", "price_max", "brand", "color", "material", "category", "size"
            )
            if getattr(self, name) is not None
        )

    def copy(self) -> "ConstraintSet":
        return ConstraintSet(**self.as_dict(), exclusions=dict(self.exclusions))

    def as_dict(self) -> dict[str, str | float | None]:
        return {
            "price_min": self.price_min,
            "price_max": self.price_max,
            "brand": self.brand,
            "color": self.color,
            "material": self.material,
            "category": self.category,
            "size": self.size,
        }


class SlotKind(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    CONTEXT = "context"


@dataclass(frozen=True)
class SlotValue:
    value: Any
    kind: SlotKind
    confidence: float
    source: str
    turn_seen: int
    ttl: int | None = None
    negated: bool = False
    explicit: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("slot confidence must be between 0 and 1")
        if self.kind == SlotKind.HARD and self.ttl is not None:
            raise ValueError("hard slots cannot expire")

    def active_weight(self, turn: int) -> float:
        if self.ttl is None:
            return 1.0
        age = max(0, turn - self.turn_seen)
        return max(0.0, 1.0 - age / max(self.ttl, 1))


@dataclass(frozen=True)
class ParsedTurn:
    intent: str
    intent_confidence: float
    slot_updates: Mapping[str, SlotValue] = field(default_factory=immutable_mapping)
    clears: frozenset[str] = frozenset()
    overrides: frozenset[str] = frozenset()
    query_text: str = ""
    evidence: tuple[str, ...] = ()
    parser_source: str = "rule"

    def __post_init__(self) -> None:
        if self.intent not in {"buying", "browsing", "unknown"}:
            raise ValueError("unsupported parsed intent")
        if not 0 <= self.intent_confidence <= 1:
            raise ValueError("parsed intent confidence must be between 0 and 1")


@dataclass(frozen=True)
class SlotChange:
    name: str
    old_value: Any
    new_value: Any
    turn: int
    reason: str


@dataclass(frozen=True)
class Candidate:
    parent_asin: str
    score: float
    source_scores: Mapping[str, float] = field(default_factory=immutable_mapping)
    source_ranks: Mapping[str, int] = field(default_factory=immutable_mapping)
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class FilterStep:
    name: str
    before: int
    after: int


@dataclass(frozen=True)
class FilterReport:
    initial_count: int
    steps: tuple[FilterStep, ...]
    final_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "initial_count": self.initial_count,
            "steps": [
                {"name": step.name, "before": step.before, "after": step.after}
                for step in self.steps
            ],
            "final_count": self.final_count,
        }


@dataclass(frozen=True)
class RelaxationReport:
    level: int = 0
    relaxed: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    slot: str | None = None
    reason: str = ""
    confidence: float = 1.0


@dataclass(frozen=True)
class ModelUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class SessionState:
    session_id: str
    user_profile: Mapping[str, Any] = field(default_factory=immutable_mapping)
    turn_count: int = 0
    intent: str = "unknown"
    intent_confidence: float = 0.0
    constraints: ConstraintSet = field(default_factory=ConstraintSet)
    slots: dict[str, SlotValue] = field(default_factory=dict)
    slot_history: list[SlotChange] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    last_query: str = ""
    candidate_ids: list[str] = field(default_factory=list)
    candidate_pool: list[Candidate] = field(default_factory=list)
    asked_slots: set[str] = field(default_factory=set)
    relaxation_level: int = 0
    conflict_reason: str | None = None
    model_usage: ModelUsage = field(default_factory=ModelUsage)
    last_action: str | None = None


@dataclass(frozen=True)
class TraceEvent:
    session_id: str
    turn: int
    intent: str
    intent_confidence: float
    constraint_names: tuple[str, ...]
    route: str
    filter_report: Mapping[str, Any]
    candidate_count: int
    top10: tuple[str, ...]
    latency_ms: float
    fallback: bool
    error_code: str | None
    config_version: str
    dense_enabled: bool = False
    llm_used: bool = False
    fallback_reason: str | None = None
    relaxation_level: int = 0
    candidate_sources: tuple[str, ...] = ()
    asked_slot: str | None = None
    model_usage: ModelUsage = field(default_factory=ModelUsage)

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn": self.turn,
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "constraint_names": list(self.constraint_names),
            "route": self.route,
            "filter_report": dict(self.filter_report),
            "candidate_count": self.candidate_count,
            "top10": list(self.top10),
            "latency_ms": round(self.latency_ms, 3),
            "fallback": self.fallback,
            "error_code": self.error_code,
            "config_version": self.config_version,
            "dense_enabled": self.dense_enabled,
            "llm_used": self.llm_used,
            "fallback_reason": self.fallback_reason,
            "relaxation_level": self.relaxation_level,
            "candidate_sources": list(self.candidate_sources),
            "asked_slot": self.asked_slot,
            "model_usage": {
                "prompt_tokens": self.model_usage.prompt_tokens,
                "completion_tokens": self.model_usage.completion_tokens,
            },
        }
