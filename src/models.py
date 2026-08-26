from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
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

    def active_names(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in (
                "price_min", "price_max", "brand", "color", "material", "category", "size"
            )
            if getattr(self, name) is not None
        )

    def copy(self) -> "ConstraintSet":
        return ConstraintSet(**self.as_dict())

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


@dataclass(frozen=True)
class Candidate:
    parent_asin: str
    score: float


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


@dataclass
class SessionState:
    session_id: str
    user_profile: Mapping[str, Any] = field(default_factory=immutable_mapping)
    turn_count: int = 0
    intent: str = "unknown"
    intent_confidence: float = 0.0
    constraints: ConstraintSet = field(default_factory=ConstraintSet)
    history: list[str] = field(default_factory=list)
    last_query: str = ""
    candidate_ids: list[str] = field(default_factory=list)
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
        }
