from __future__ import annotations

from dataclasses import dataclass

from src.models import AskedSlotState, IntentState, STABLE_INTENTS


MODEL_INTENTS = STABLE_INTENTS | {"continue"}
EVENT_KINDS = frozenset({"override", "clear", "negation", "no_preference", "intent_switch"})


def _validate_confidence(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class RuleIntentObservation:
    label: str
    confidence: float
    evidence: tuple[str, ...] = ()
    strong: bool = False

    def __post_init__(self) -> None:
        if self.label not in STABLE_INTENTS:
            raise ValueError("unsupported rule intent")
        _validate_confidence(self.confidence, "rule confidence")


@dataclass(frozen=True)
class IntentModelObservation:
    label: str
    confidence: float
    margin: float
    source: str = "nli"

    def __post_init__(self) -> None:
        if self.label not in MODEL_INTENTS:
            raise ValueError("unsupported model intent")
        _validate_confidence(self.confidence, "model confidence")
        _validate_confidence(self.margin, "model margin")


@dataclass(frozen=True)
class TurnEvent:
    kind: str
    slots: frozenset[str] = frozenset()
    confidence: float = 1.0
    explicit: bool = True
    evidence: tuple[str, ...] = ()
    target_intent: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError("unsupported turn event")
        _validate_confidence(self.confidence, "event confidence")
        if self.kind == "intent_switch":
            if self.target_intent not in {"buying", "browsing"}:
                raise ValueError("intent switch requires a target")
        elif self.target_intent is not None:
            raise ValueError("only intent switch can have a target")
        if self.kind in {"override", "clear", "negation", "no_preference"} and self.explicit and not self.slots:
            raise ValueError("explicit destructive events require scoped slots")


@dataclass(frozen=True)
class ResolvedIntent:
    label: str
    confidence: float
    source: str
    switched: bool
    reason: str

    def __post_init__(self) -> None:
        if self.label not in STABLE_INTENTS:
            raise ValueError("unsupported resolved intent")
        _validate_confidence(self.confidence, "resolved confidence")


@dataclass(frozen=True)
class TurnObservation:
    rule: RuleIntentObservation
    events: tuple[TurnEvent, ...] = ()
    model: IntentModelObservation | None = None
    valid_answer: bool = False


__all__ = [
    "AskedSlotState", "IntentModelObservation", "IntentState", "ResolvedIntent",
    "RuleIntentObservation", "TurnEvent", "TurnObservation",
]
