from __future__ import annotations

import re

from src.catalog.normalize import normalize_key
from src.models import ParsedTurn, SessionState
from src.nlu.intent.schema import TurnEvent


SLOT_WORDS = {
    "brand": "brand", "color": "color", "colour": "color", "size": "size",
    "budget": "price_max", "price": "price_max", "material": "material",
    "category": "category", "style": "style", "occasion": "occasion",
    "use case": "use_case", "use-case": "use_case",
}
COLOR_WORDS = "black|white|blue|red|pink|green|brown|gray|grey|purple|yellow|orange"


def _named_slots(message: str) -> frozenset[str]:
    return frozenset(value for key, value in SLOT_WORDS.items() if re.search(rf"\b{re.escape(key)}\b", message))


class RuleEventDetector:
    def detect(self, message: str, state: SessionState, parsed: ParsedTurn) -> tuple[TurnEvent, ...]:
        normalized = normalize_key(message)
        events: list[TurnEvent] = []
        named = _named_slots(normalized)

        no_preference = bool(re.search(r"\b(?:no|don't have|do not have|without)\s+(?:a\s+)?(?:\w+\s+)?preference\b|\bany\s+(?:brand|color|size|material)\b.*\bfine\b|\b(?:brand|color|size|material)\s+does(?:n't| not)\s+matter\b", normalized))
        if no_preference:
            slots = named or (frozenset({state.last_asked_slot}) if state.last_asked_slot else frozenset())
            if slots:
                events.append(TurnEvent("no_preference", slots, 0.99, True, ("no_preference",)))

        clear_signal = bool(re.search(r"\b(?:clear|remove|forget|ignore)\b", normalized))
        if clear_signal and not no_preference:
            if named:
                events.append(TurnEvent("clear", named, 0.98, True, ("scoped_clear",)))
            else:
                events.append(TurnEvent("clear", frozenset(), 0.60, False, ("ambiguous_clear",)))

        negated = re.search(rf"\b(?:anything\s+except|except|not|without|don't want|do not want)\s+({COLOR_WORDS})\b", normalized)
        if negated:
            events.append(TurnEvent("negation", frozenset({"color"}), 0.99, True, (negated.group(1),)))

        positive_overrides = frozenset(
            name for name in parsed.overrides
            if name not in parsed.slot_updates or not parsed.slot_updates[name].negated
        )
        if positive_overrides:
            events.append(TurnEvent("override", positive_overrides, 0.98, True, ("explicit_override",)))

        browse_switch = re.search(r"\b(?:just|only|still)\s+(?:exploring|browsing)\b|\bexploring options now\b|\bneed ideas now\b", normalized)
        buy_switch = re.search(r"\b(?:ready to buy|want to buy|decided on|specific purchase)\b", normalized)
        if browse_switch:
            events.append(TurnEvent("intent_switch", confidence=0.99, explicit=True, evidence=(browse_switch.group(0),), target_intent="browsing"))
        elif buy_switch:
            events.append(TurnEvent("intent_switch", confidence=0.99, explicit=True, evidence=(buy_switch.group(0),), target_intent="buying"))
        return tuple(events)
