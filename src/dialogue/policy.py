from __future__ import annotations

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.models import Candidate, PolicyDecision, SessionState


SLOT_PRIORITY = ("category", "price_max", "size", "color", "brand", "material")
ASK_ATTRIBUTE = {"price_max": "budget"}
QUESTIONS = {
    "category": "Which type of product are you looking for?",
    "price_max": "Do you have a maximum budget?",
    "size": "Which size do you need?",
    "color": "Which color would you prefer?",
    "brand": "Do you have a preferred brand, or is any brand fine?",
    "material": "Do you have a material preference?",
}


def render_question(slot: str) -> str:
    return QUESTIONS.get(slot, "Which detail matters most to you?")


class ClarificationPolicy:
    def __init__(self, catalog: CatalogStore, config: AgentConfig) -> None:
        self.catalog = catalog
        self.config = config

    def decide(self, state: SessionState, candidates: list[Candidate]) -> PolicyDecision:
        if state.turn_count >= self.config.max_turns:
            return PolicyDecision("recommend", reason="turn_limit")
        if not self.config.clarification_enabled:
            return PolicyDecision("recommend", reason="clarification_disabled")
        if state.conflict_reason:
            return PolicyDecision("clarify", self._conflict_slot(state.conflict_reason), state.conflict_reason)
        if len(candidates) <= 10:
            return PolicyDecision("recommend", reason="small_candidate_set")
        missing = [slot for slot in SLOT_PRIORITY if slot not in state.slots and slot not in state.asked_slots]
        if not missing:
            return PolicyDecision("recommend", reason="no_unasked_slot")
        if state.turn_count >= self.config.late_turn:
            return PolicyDecision("recommend", reason="late_turn_protection")
        slot = self._best_slot(missing, candidates)
        return PolicyDecision("clarify", slot, "large_candidate_set", 0.7)

    @staticmethod
    def attribute_for(slot: str | None) -> str | None:
        if slot is None:
            return None
        return ASK_ATTRIBUTE.get(slot, slot)

    @staticmethod
    def _conflict_slot(reason: str) -> str:
        return "price_max" if reason.startswith("price") else reason.split("_", 1)[0]

    def _best_slot(self, missing: list[str], candidates: list[Candidate]) -> str:
        # Prefer fields that actually vary in the current pool, then stable priority.
        best = missing[0]
        best_count = -1
        for slot in missing:
            values = set()
            for candidate in candidates[: self.config.fused_k]:
                product = self.catalog.get(candidate.parent_asin)
                if product is None:
                    continue
                if slot == "price_max" and product.price is not None:
                    values.add(int(product.price // 25))
                elif slot == "brand" and product.brand_key:
                    values.add(product.brand_key)
                else:
                    values.update(product.attributes.get(slot, frozenset()))
            if len(values) > best_count:
                best, best_count = slot, len(values)
        return best
