from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from enum import Enum
from typing import Any, Mapping


STABLE_INTENTS = frozenset({"buying", "browsing", "unknown"})


@dataclass(frozen=True)
class AskedSlotState:
    slot: str
    turn: int
    status: str
    route: str

    def __post_init__(self) -> None:
        if not self.slot:
            raise ValueError("asked slot must not be empty")
        if self.turn < 1 or self.turn > 10:
            raise ValueError("asked slot turn must be between 1 and 10")
        if self.status not in {"asked", "answered", "declined"}:
            raise ValueError("unsupported asked slot status")
        if self.route not in STABLE_INTENTS:
            raise ValueError("unsupported asked slot route")


@dataclass(frozen=True)
class IntentState:
    label: str = "unknown"
    confidence: float = 0.0
    source: str = "default"
    stable_since_turn: int = 0
    last_switch_turn: int | None = None
    switch_reason: str | None = None

    def __post_init__(self) -> None:
        if self.label not in STABLE_INTENTS:
            raise ValueError("unsupported stable intent")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("intent confidence must be between 0 and 1")
        if self.stable_since_turn < 0 or self.stable_since_turn > 10:
            raise ValueError("stable intent turn must be between 0 and 10")
        if self.last_switch_turn is not None and not 1 <= self.last_switch_turn <= 10:
            raise ValueError("intent switch turn must be between 1 and 10")


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
        if self.label not in STABLE_INTENTS:
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
    intent_state: IntentState = field(default_factory=IntentState)
    last_asked_slot: str | None = None
    slot_answers: dict[str, AskedSlotState] = field(default_factory=dict)
    last_user_message: str = ""
    previous_user_message: str | None = None
    last_event_kinds: tuple[str, ...] = ()
    last_route_plan: Mapping[str, Any] = field(default_factory=immutable_mapping)
    last_policy_reason: str | None = None
    last_top10_fingerprint: tuple[str, ...] = ()
    previous_candidate_count: int | None = None
    consecutive_no_shrink: int = 0
    consecutive_stable_top10: int = 0
    rule_intent: str = "unknown"
    rule_confidence: float = 0.0
    model_intent: str | None = None
    model_confidence: float | None = None
    model_margin: float | None = None
    intent_fallback_reason: str | None = None
    intent_latency_ms: float = 0.0
    stable_intent_before: str = "unknown"

    def active_slots(self, turn: int | None = None) -> dict[str, SlotValue]:
        current_turn = self.turn_count if turn is None else turn
        return {
            name: value
            for name, value in self.slots.items()
            if value.active_weight(current_turn) > 0.0
        }

    def active_constraints(self, turn: int | None = None) -> ConstraintSet:
        constraints = ConstraintSet(exclusions=dict(self.constraints.exclusions))
        for name, slot in self.active_slots(turn).items():
            if slot.negated:
                values = slot.value if isinstance(slot.value, (list, tuple, set, frozenset)) else (slot.value,)
                current = set(constraints.exclusions.get(name, frozenset()))
                current.update(str(value).casefold() for value in values)
                constraints.exclusions[name] = frozenset(current)
            elif hasattr(constraints, name):
                setattr(constraints, name, slot.value)
        return constraints


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
    route_plan: Mapping[str, Any] = field(default_factory=immutable_mapping)
    policy_reason: str | None = None
    detected_events: tuple[str, ...] = ()
    rule_intent: str = "unknown"
    rule_confidence: float = 0.0
    model_intent: str | None = None
    model_confidence: float | None = None
    model_margin: float | None = None
    stable_intent_before: str = "unknown"
    intent_switched: bool = False
    switch_reason: str | None = None
    slot_answer_status: str | None = None
    intent_model_mode: str = "off"
    intent_fallback_reason: str | None = None
    intent_latency_ms: float = 0.0

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
            "route_plan": dict(self.route_plan),
            "policy_reason": self.policy_reason,
            "detected_events": list(self.detected_events),
            "rule_intent": self.rule_intent,
            "rule_confidence": self.rule_confidence,
            "model_intent": self.model_intent,
            "model_confidence": self.model_confidence,
            "model_margin": self.model_margin,
            "stable_intent_before": self.stable_intent_before,
            "intent_switched": self.intent_switched,
            "switch_reason": self.switch_reason,
            "slot_answer_status": self.slot_answer_status,
            "intent_model_mode": self.intent_model_mode,
            "intent_fallback_reason": self.intent_fallback_reason,
            "intent_latency_ms": round(self.intent_latency_ms, 3),
            "model_usage": {
                "prompt_tokens": self.model_usage.prompt_tokens,
                "completion_tokens": self.model_usage.completion_tokens,
            },
        }
