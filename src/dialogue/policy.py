from __future__ import annotations

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.models import Candidate, PolicyDecision, SessionState


SLOT_PRIORITY = ("category", "price_max", "size", "color", "brand", "material")
BUYING_PRIORITY = ("category", "price_max", "size", "brand", "color", "material")
BROWSING_PRIORITY = ("use_case", "occasion", "style", "category", "price_max")
UNKNOWN_PRIORITY = ("category", "use_case", "price_max")
D3_PRIORITY = {
    "buying": ("feature", "material", "color", "size", "brand", "category", "price_max", "use_case"),
    "browsing": ("feature", "material", "color", "use_case", "style", "category", "brand", "size", "price_max"),
    "unknown": ("feature", "material", "color", "category", "use_case", "brand", "size", "price_max"),
}
SUPPORTED_ATTRIBUTES = frozenset({"category", "material", "color", "size", "style", "brand", "price_max", "feature", "use_case"})
ASK_ATTRIBUTE = {"price_max": "budget"}
QUESTIONS = {
    "category": "Which type of product are you looking for?",
    "price_max": "Do you have a maximum budget?",
    "size": "Which size do you need?",
    "color": "Which color would you prefer?",
    "brand": "Do you have a preferred brand, or is any brand fine?",
    "material": "Do you have a material preference?",
    "use_case": "What will you use it for?",
    "occasion": "Is there a particular occasion?",
    "style": "Which style direction would you like to explore?",
    "feature": "Which product feature matters most to you?",
}


def render_question(slot: str) -> str:
    return QUESTIONS.get(slot, "Which detail matters most to you?")


class ClarificationPolicy:
    def __init__(self, catalog: CatalogStore, config: AgentConfig) -> None:
        self.catalog = catalog
        self.config = config

    def decide(self, state: SessionState, candidates: list[Candidate]) -> PolicyDecision:
        if self.config.intent_policy_enabled:
            return self._decide_intent_aware(state, candidates)
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

    def _decide_intent_aware(self, state: SessionState, candidates: list[Candidate]) -> PolicyDecision:
        fingerprint = tuple(candidate.parent_asin for candidate in candidates[:10])
        previous_fingerprint = state.last_top10_fingerprint
        previous_count = state.previous_candidate_count
        if set(state.last_event_kinds) & {"override", "clear", "negation", "intent_switch"}:
            previous_fingerprint = ()
            previous_count = None
            state.consecutive_stable_top10 = 0
            state.consecutive_no_shrink = 0
            state.consecutive_non_improving_clarifications = 0
            state.last_evaluated_question_turn = None
            state.last_question_candidate_count = None
            state.last_question_top10_fingerprint = ()
        if previous_fingerprint and fingerprint == previous_fingerprint:
            state.consecutive_stable_top10 += 1
        else:
            state.consecutive_stable_top10 = 0
        if previous_count is not None and len(candidates) >= previous_count:
            state.consecutive_no_shrink += 1
        else:
            state.consecutive_no_shrink = 0
        state.last_top10_fingerprint = fingerprint
        state.previous_candidate_count = len(candidates)

        if self.config.recommendation_with_clarification_enabled:
            self._record_clarification_outcome(state, candidates, fingerprint)

        if state.turn_count >= self.config.max_turns:
            return self._decision(state, "recommend", reason="turn_limit")
        if not self.config.clarification_enabled:
            return self._decision(state, "recommend", reason="clarification_disabled")
        if state.conflict_reason:
            return self._decision(state, "clarify", self._conflict_slot(state.conflict_reason), state.conflict_reason)
        if len(candidates) <= 10:
            return self._decision(state, "recommend", reason="small_candidate_set")
        if self.config.recommendation_with_clarification_enabled and state.turn_count >= 4:
            return self._decision(state, "recommend", reason="recommendation_first")
        if state.turn_count >= self.config.late_turn:
            return self._decision(state, "recommend", reason="late_turn_protection")
        if state.consecutive_stable_top10 >= self.config.clarification_stability_turns:
            return self._decision(state, "recommend", reason="stable_top10")
        if len(candidates) >= 2 and candidates[0].score - candidates[1].score >= self.config.clarification_margin_threshold:
            return self._decision(state, "recommend", reason="score_margin")
        if state.consecutive_no_shrink >= self.config.clarification_no_shrink_limit:
            return self._decision(state, "recommend", reason="no_candidate_shrink")

        if (
            self.config.recommendation_with_clarification_enabled
            and state.consecutive_non_improving_clarifications >= 2
        ):
            return self._decision(state, "recommend", reason="non_improving_clarifications")

        priority = (
            D3_PRIORITY[state.intent]
            if self.config.recommendation_with_clarification_enabled
            else {
                "buying": BUYING_PRIORITY,
                "browsing": BROWSING_PRIORITY,
                "unknown": UNKNOWN_PRIORITY,
            }[state.intent]
        )
        active = state.active_slots()
        missing = []
        for slot in priority:
            if slot in active:
                continue
            answer = state.slot_answers.get(slot)
            if answer is not None and answer.status in {"answered", "declined"}:
                continue
            if answer is not None and answer.status == "asked" and answer.route == state.intent:
                continue
            missing.append(slot)
        if not missing:
            return self._decision(state, "recommend", reason="no_high_value_slot")
        if self.config.recommendation_with_clarification_enabled:
            slot = self._best_supported_slot(missing, candidates)
            if slot is None:
                return self._decision(state, "recommend", reason="no_supported_information_gain")
            state.last_question_candidate_count = len(candidates)
            state.last_question_top10_fingerprint = fingerprint
        else:
            slot = self._best_slot(missing, candidates)
        return self._decision(state, "clarify", slot, "route_information_gain", 0.7)

    @staticmethod
    def _record_clarification_outcome(
        state: SessionState,
        candidates: list[Candidate],
        fingerprint: tuple[str, ...],
    ) -> None:
        if not state.last_asked_slot:
            return
        answer = state.slot_answers.get(state.last_asked_slot)
        if answer is None or answer.turn >= state.turn_count or answer.turn == state.last_evaluated_question_turn:
            return
        improved = (
            state.last_question_candidate_count is not None
            and len(candidates) < state.last_question_candidate_count
        ) or (
            bool(state.last_question_top10_fingerprint)
            and fingerprint != state.last_question_top10_fingerprint
        )
        if improved:
            state.consecutive_non_improving_clarifications = 0
        else:
            state.consecutive_non_improving_clarifications += 1
        state.last_evaluated_question_turn = answer.turn

    def _best_supported_slot(self, missing: list[str], candidates: list[Candidate]) -> str | None:
        for slot in missing:
            if slot not in SUPPORTED_ATTRIBUTES:
                continue
            partitions: set[tuple[object, ...]] = set()
            for candidate in candidates[: self.config.fused_k]:
                product = self.catalog.get(candidate.parent_asin)
                if product is None:
                    continue
                if slot == "price_max" and product.price is not None:
                    values: tuple[object, ...] = (int(product.price // 25),)
                elif slot == "brand" and product.brand_key:
                    values = (product.brand_key,)
                else:
                    values = tuple(sorted(product.attributes.get(slot, frozenset())))
                if values:
                    partitions.add(values)
            if len(partitions) > 1:
                return slot
        return None

    @staticmethod
    def _decision(
        state: SessionState,
        action: str,
        slot: str | None = None,
        reason: str = "",
        confidence: float = 1.0,
    ) -> PolicyDecision:
        state.last_policy_reason = reason
        return PolicyDecision(action, slot, reason, confidence)

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
        if missing[0] in {"use_case", "occasion", "style"}:
            return missing[0]
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
