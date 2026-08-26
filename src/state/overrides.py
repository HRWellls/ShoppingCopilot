from __future__ import annotations

from typing import Any

from src.models import ConstraintSet, ParsedTurn, SessionState, SlotChange, SlotKind, SlotValue


ALLOWED_SLOTS = frozenset(
    {"price_min", "price_max", "brand", "color", "material", "category", "size", "occasion", "style"}
)


def slot_priority(value: SlotValue) -> int:
    if value.source == "user-confirmed" and value.explicit:
        return 5
    if value.explicit:
        return 4
    if value.source == "rule":
        return 3
    if value.source == "model":
        return 2
    return 1


class OverrideResolver:
    def apply(self, state: SessionState, parsed: ParsedTurn) -> list[SlotChange]:
        changes: list[SlotChange] = []
        for name in parsed.clears:
            if name not in ALLOWED_SLOTS:
                continue
            old = state.slots.pop(name, None)
            if old is not None:
                changes.append(SlotChange(name, old.value, None, state.turn_count, "explicit_clear"))

        for name, new in parsed.slot_updates.items():
            if name not in ALLOWED_SLOTS:
                continue
            old = state.slots.get(name)
            explicit_override = name in parsed.overrides
            if (
                old is not None
                and old.kind == SlotKind.HARD
                and old.source == "user-confirmed"
                and not explicit_override
                and slot_priority(new) < slot_priority(old)
            ):
                continue
            if old is None or explicit_override or slot_priority(new) >= slot_priority(old) or new.confidence >= old.confidence:
                state.slots[name] = new
                changes.append(
                    SlotChange(name, old.value if old else None, new.value, state.turn_count,
                               "explicit_override" if explicit_override else "slot_update")
                )

        state.slot_history.extend(changes)
        self._sync_constraints(state)
        state.conflict_reason = self.detect_conflict(state)
        return changes

    def decay(self, state: SessionState) -> None:
        # Values remain auditable; active_weight controls ranking influence.
        for value in state.slots.values():
            value.active_weight(state.turn_count)

    @staticmethod
    def detect_conflict(state: SessionState) -> str | None:
        c = state.constraints
        if c.price_min is not None and c.price_max is not None and c.price_min > c.price_max:
            return "price_range_conflict"
        for name in ("brand", "color", "material", "category", "size"):
            value = getattr(c, name)
            excluded = c.exclusions.get(name, frozenset())
            allowed = set(value) if isinstance(value, (set, frozenset, tuple, list)) else {value} if value else set()
            if allowed and allowed.issubset(excluded):
                return f"{name}_allow_exclusion_conflict"
        return None

    @staticmethod
    def _sync_constraints(state: SessionState) -> None:
        constraints = ConstraintSet(exclusions=dict(state.constraints.exclusions))
        for name, slot in state.slots.items():
            if slot.negated:
                values = slot.value if isinstance(slot.value, (list, tuple, set, frozenset)) else (slot.value,)
                current = set(constraints.exclusions.get(name, frozenset()))
                current.update(str(value).casefold() for value in values)
                constraints.exclusions[name] = frozenset(current)
            elif hasattr(constraints, name):
                setattr(constraints, name, slot.value)
        state.constraints = constraints


def make_slot(
    value: Any,
    *,
    name: str,
    turn: int,
    source: str = "user-confirmed",
    confidence: float = 0.95,
    explicit: bool = True,
    negated: bool = False,
    soft_ttl: int = 3,
) -> SlotValue:
    kind = SlotKind.HARD if name in {"price_min", "price_max", "size"} or negated else SlotKind.SOFT
    return SlotValue(
        value=value,
        kind=kind,
        confidence=confidence,
        source=source,
        turn_seen=turn,
        ttl=None if kind == SlotKind.HARD else soft_ttl,
        negated=negated,
        explicit=explicit,
    )
