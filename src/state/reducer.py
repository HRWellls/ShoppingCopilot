from __future__ import annotations

from src.models import AskedSlotState, IntentState, ParsedTurn, SessionState, SlotChange, SlotKind, SlotValue
from src.nlu.intent.schema import ResolvedIntent, TurnEvent
from src.state.overrides import ALLOWED_SLOTS, slot_priority


class TurnStateReducer:
    def reduce(
        self,
        state: SessionState,
        parsed: ParsedTurn,
        events: tuple[TurnEvent, ...],
        resolved: ResolvedIntent,
    ) -> list[SlotChange]:
        changes: list[SlotChange] = []
        protected = {"price_min", "price_max", "size"}

        clear_slots: set[str] = set()
        for event in events:
            if event.kind in {"clear", "no_preference"}:
                if event.slots:
                    clear_slots.update(event.slots)
                elif not event.explicit:
                    recent = self._recent_soft_slot(state)
                    if recent:
                        clear_slots.add(recent)
        for name in clear_slots:
            if name not in ALLOWED_SLOTS:
                continue
            old = state.slots.get(name)
            event_is_explicit = any(name in event.slots and event.explicit for event in events if event.kind in {"clear", "no_preference"})
            if old is not None and (name not in protected or event_is_explicit):
                state.slots.pop(name, None)
                changes.append(SlotChange(name, old.value, None, state.turn_count, "explicit_clear"))

        override_slots = set().union(*(event.slots for event in events if event.kind == "override")) if events else set()
        for name in override_slots:
            if name in state.slots:
                old = state.slots.pop(name)
                changes.append(SlotChange(name, old.value, None, state.turn_count, "override_clear"))
        if "category" in override_slots:
            for semantic_name in ("style", "use_case", "occasion"):
                if semantic_name in parsed.slot_updates:
                    continue
                old = state.slots.pop(semantic_name, None)
                if old is not None:
                    changes.append(SlotChange(semantic_name, old.value, None, state.turn_count, "category_context_reset"))
                answer = state.slot_answers.get(semantic_name)
                if answer is not None and answer.status != "declined":
                    state.slot_answers.pop(semantic_name, None)

        exclusions = dict(state.constraints.exclusions)
        for event in events:
            if event.kind != "negation":
                continue
            for name in event.slots:
                current = set(exclusions.get(name, frozenset()))
                current.update(value.casefold() for value in event.evidence if value)
                exclusions[name] = frozenset(current)
        state.constraints.exclusions = exclusions

        for name, new in parsed.slot_updates.items():
            if name not in ALLOWED_SLOTS:
                continue
            if new.negated:
                current = set(state.constraints.exclusions.get(name, frozenset()))
                values = new.value if isinstance(new.value, (list, tuple, set, frozenset)) else (new.value,)
                current.update(str(value).casefold() for value in values)
                state.constraints.exclusions[name] = frozenset(current)
                continue
            old = state.slots.get(name)
            explicit_override = name in override_slots
            if old is not None and old.kind == SlotKind.HARD and old.source == "user-confirmed" and not explicit_override and slot_priority(new) < slot_priority(old):
                continue
            if old is None or explicit_override or slot_priority(new) >= slot_priority(old) or new.confidence >= old.confidence:
                state.slots[name] = new
                changes.append(SlotChange(name, old.value if old else None, new.value, state.turn_count, "explicit_override" if explicit_override else "slot_update"))

        self._update_answer_state(state, parsed, events)
        state.slot_history.extend(changes)
        state.constraints = state.active_constraints()
        state.conflict_reason = self._detect_conflict(state)
        state.last_event_kinds = tuple(event.kind for event in events)
        self._commit_intent(state, resolved)
        return changes

    @staticmethod
    def record_question(state: SessionState, slot: str) -> None:
        asked = AskedSlotState(slot, state.turn_count, "asked", state.intent_state.label)
        state.last_asked_slot = slot
        state.slot_answers[slot] = asked
        state.asked_slots = set(state.slot_answers)

    @staticmethod
    def _update_answer_state(state: SessionState, parsed: ParsedTurn, events: tuple[TurnEvent, ...]) -> None:
        slot = state.last_asked_slot
        if not slot or slot not in state.slot_answers:
            return
        previous = state.slot_answers[slot]
        if any(event.kind == "no_preference" and slot in event.slots for event in events):
            state.slot_answers[slot] = AskedSlotState(slot, previous.turn, "declined", previous.route)
        elif slot in parsed.slot_updates and not parsed.slot_updates[slot].negated:
            state.slot_answers[slot] = AskedSlotState(slot, previous.turn, "answered", previous.route)

    @staticmethod
    def _recent_soft_slot(state: SessionState) -> str | None:
        for change in reversed(state.slot_history):
            slot = state.slots.get(change.name)
            if slot is not None and slot.kind != SlotKind.HARD:
                return change.name
        return None

    @staticmethod
    def _detect_conflict(state: SessionState) -> str | None:
        constraints = state.constraints
        if constraints.price_min is not None and constraints.price_max is not None and constraints.price_min > constraints.price_max:
            return "price_range_conflict"
        for name in ("brand", "color", "material", "category", "size"):
            value = getattr(constraints, name)
            excluded = constraints.exclusions.get(name, frozenset())
            if value is not None and str(value).casefold() in excluded:
                return f"{name}_allow_exclusion_conflict"
        return None

    @staticmethod
    def _commit_intent(state: SessionState, resolved: ResolvedIntent) -> None:
        previous = state.intent_state
        switched = resolved.label != previous.label
        stable_since = state.turn_count if switched or previous.stable_since_turn == 0 else previous.stable_since_turn
        state.intent_state = IntentState(
            label=resolved.label,
            confidence=resolved.confidence,
            source=resolved.source,
            stable_since_turn=stable_since,
            last_switch_turn=state.turn_count if switched else previous.last_switch_turn,
            switch_reason=resolved.reason if switched else previous.switch_reason,
        )
        state.intent = state.intent_state.label
        state.intent_confidence = state.intent_state.confidence
