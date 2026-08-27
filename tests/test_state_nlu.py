from __future__ import annotations

import unittest

from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.nlu import RuleConstraintExtractor, RuleIntentRouter, apply_rule_turn
from src.state import SessionStateStore
from tests.fixtures import profile


class SessionStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SessionStateStore(AgentConfig())

    def test_reset_replaces_state_and_copies_profile(self) -> None:
        source = profile("fit")
        state = self.store.reset("A", source)
        source["summary"] = "changed"
        self.assertNotEqual(state.user_profile["summary"], "changed")
        self.store.begin_turn("A", 1, "black shoes")
        replacement = self.store.reset("A", profile())
        self.assertEqual(replacement.turn_count, 0)
        self.assertEqual(replacement.history, [])
        self.assertEqual(replacement.constraints.active_names(), ())

    def test_sessions_are_isolated(self) -> None:
        first = self.store.reset("A", profile())
        second = self.store.reset("B", profile())
        self.store.begin_turn("A", 1, "black shoes under $100")
        apply_rule_turn(first, first.history[-1], RuleConstraintExtractor())
        self.assertEqual(second.constraints.active_names(), ())
        self.assertNotIn("black", second.last_query)

    def test_turn_validation_leaves_state_unchanged(self) -> None:
        state = self.store.reset("A", profile())
        self.store.begin_turn("A", 1, "shoes")
        for invalid in (1, 3, 0, 11):
            with self.assertRaises(AgentError) as context:
                self.store.begin_turn("A", invalid, "bad turn")
            self.assertEqual(context.exception.code, ErrorCode.PROTOCOL)
        self.assertEqual(state.turn_count, 1)
        self.assertEqual(state.history, ["shoes"])
        with self.assertRaises(AgentError):
            self.store.get("missing")


class RuleNluTest(unittest.TestCase):
    def setUp(self) -> None:
        self.router = RuleIntentRouter()
        self.extractor = RuleConstraintExtractor()

    def test_intent_routing(self) -> None:
        buying = self.router.route("I'm looking for black running shoes under $100")
        self.assertEqual(buying.label, "buying")
        self.assertGreater(buying.confidence, 0.5)
        browsing = self.router.route("What should I wear to a summer wedding?")
        self.assertEqual(browsing.label, "browsing")
        self.assertEqual(self.router.route("the and please").label, "unknown")
        self.assertEqual(self.router.route("hello").label, "unknown")

    def test_constraint_extraction(self) -> None:
        result = self.extractor.extract("Nike brand shoes in black leather, size 9, between $50 and $100")
        self.assertEqual(result.category, "shoes")
        self.assertEqual(result.color, "black")
        self.assertEqual(result.material, "leather")
        self.assertEqual(result.size, "9")
        self.assertEqual(result.price_min, 50.0)
        self.assertEqual(result.price_max, 100.0)
        brand = self.extractor.extract("shoes from Nike under $80")
        self.assertEqual(brand.brand, "Nike")
        underwear = self.extractor.extract("looking for women panties; machine wash with laundry bag")
        self.assertEqual(underwear.category, "panties")

    def test_constraints_accumulate_and_replace_same_field(self) -> None:
        store = SessionStateStore(AgentConfig())
        state = store.reset("A", profile())
        for turn, message in enumerate(("running shoes", "under $100", "size 9"), 1):
            store.begin_turn("A", turn, message)
            apply_rule_turn(state, message, self.extractor)
        self.assertEqual(state.constraints.category, "running shoes")
        self.assertEqual(state.constraints.price_max, 100.0)
        self.assertEqual(state.constraints.size, "9")
        apply_rule_turn(state, "I prefer black", self.extractor)
        apply_rule_turn(state, "white would be better", self.extractor)
        self.assertEqual(state.constraints.color, "white")
        self.assertNotIn("black", state.last_query)

    def test_non_category_answer_does_not_replace_category_from_incidental_word(self) -> None:
        store = SessionStateStore(AgentConfig())
        state = store.reset("A", profile())
        state.last_asked_slot = "feature"
        parsed = self.extractor.parse("machine wash with a laundry bag", state)
        self.assertIsNone(parsed.slot_updates.get("category"))


if __name__ == "__main__":
    unittest.main()
