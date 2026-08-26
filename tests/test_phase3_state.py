from __future__ import annotations

import unittest

from src.config import AgentConfig
from src.models import ParsedTurn, SlotKind, SlotValue
from src.nlu import RuleConstraintExtractor
from src.state import OverrideResolver, SessionStateStore, make_slot
from tests.fixtures import profile


class Phase3StateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SessionStateStore(AgentConfig())
        self.state = self.store.reset("s", profile())
        self.parser = RuleConstraintExtractor()
        self.resolver = OverrideResolver()

    def apply(self, turn: int, message: str) -> None:
        self.store.begin_turn("s", turn, message)
        parsed = self.parser.parse(message, self.state)
        self.resolver.apply(self.state, parsed)

    def test_override_clear_negation_and_history(self) -> None:
        self.apply(1, "black shoes from SwiftStep")
        self.apply(2, "actually white instead")
        self.assertEqual(self.state.constraints.color, "white")
        self.apply(3, "any brand is fine")
        self.assertIsNone(self.state.constraints.brand)
        self.apply(4, "not red")
        self.assertIn("red", self.state.constraints.exclusions["color"])
        self.assertGreaterEqual(len(self.state.slot_history), 4)

    def test_model_cannot_override_confirmed_hard_slot(self) -> None:
        self.state.turn_count = 1
        confirmed = make_slot(100.0, name="price_max", turn=1)
        self.resolver.apply(self.state, ParsedTurn("buying", 1.0, {"price_max": confirmed}))
        model = SlotValue(200.0, SlotKind.HARD, 0.99, "model", 2)
        self.state.turn_count = 2
        self.resolver.apply(self.state, ParsedTurn("buying", 0.8, {"price_max": model}))
        self.assertEqual(self.state.constraints.price_max, 100.0)

    def test_explicit_budget_override_and_conflict(self) -> None:
        self.apply(1, "under $100 shoes")
        self.apply(2, "actually between $150 and $200")
        self.assertEqual(self.state.constraints.price_min, 150.0)
        self.assertEqual(self.state.constraints.price_max, 200.0)
        self.state.slots["price_min"] = make_slot(300.0, name="price_min", turn=3)
        self.resolver._sync_constraints(self.state)
        self.assertEqual(self.resolver.detect_conflict(self.state), "price_range_conflict")

    def test_soft_slot_weight_decays_without_deletion(self) -> None:
        slot = make_slot("black", name="color", turn=1, source="model", soft_ttl=3)
        self.assertEqual(slot.active_weight(1), 1.0)
        self.assertEqual(slot.active_weight(4), 0.0)
        self.assertEqual(slot.value, "black")


if __name__ == "__main__":
    unittest.main()
