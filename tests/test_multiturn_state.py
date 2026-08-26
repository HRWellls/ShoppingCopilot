from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import AskedSlotState, Candidate, IntentState, ParsedTurn, SessionState, SlotKind, SlotValue
from src.nlu import IntentResolver, RuleConstraintExtractor, RuleEventDetector
from src.nlu.intent.schema import IntentModelObservation, ResolvedIntent, RuleIntentObservation, TurnEvent, TurnObservation
from src.state import SessionStateStore, TurnStateReducer, make_slot
from starter.agent import Agent
from tests.fixtures import profile, write_catalog


class RaisingIndex:
    def search(self, query: str, k: int, subset: object = None) -> list[Candidate]:
        raise AgentError(ErrorCode.RETRIEVAL, "injected transaction failure")


class MultiturnStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AgentConfig(multiturn_state_enabled=True)
        self.store = SessionStateStore(self.config)
        self.state = self.store.reset("s", profile())
        self.extractor = RuleConstraintExtractor()
        self.detector = RuleEventDetector()
        self.resolver = IntentResolver(self.config)
        self.reducer = TurnStateReducer()

    def apply(self, turn: int, message: str) -> SessionState:
        state = self.store.begin_transaction("s", turn, message)
        parsed = self.extractor.parse(message, state)
        events = self.detector.detect(message, state, parsed)
        rule = RuleIntentObservation(parsed.intent, parsed.intent_confidence, parsed.evidence, parsed.intent != "unknown" and parsed.intent_confidence >= 0.6)
        valid_answer = bool(state.last_asked_slot and state.last_asked_slot in parsed.slot_updates)
        resolved = self.resolver.resolve(state, TurnObservation(rule, events, valid_answer=valid_answer))
        self.reducer.reduce(state, parsed, events, resolved)
        self.store.commit(state)
        self.state = state
        return state

    def test_schema_validation_and_continue_is_not_stable(self) -> None:
        self.assertEqual(IntentState("buying", 0.8, "rule", 1).label, "buying")
        self.assertEqual(AskedSlotState("color", 1, "asked", "buying").status, "asked")
        with self.assertRaises(ValueError):
            IntentState("continue", 0.8, "model", 1)
        with self.assertRaises(ValueError):
            AskedSlotState("color", 1, "missing", "buying")
        with self.assertRaises(ValueError):
            TurnEvent("clear", explicit=True)
        with self.assertRaises(ValueError):
            IntentModelObservation("bad", 0.8, 0.2)

    def test_short_answers_and_declines_follow_last_question(self) -> None:
        self.state.intent_state = IntentState("buying", 0.9, "rule", 1)
        self.state.intent = "buying"
        self.state.turn_count = 1
        self.state.history.append("looking for shoes")
        self.reducer.record_question(self.state, "color")
        self.apply(2, "black")
        self.assertEqual(self.state.constraints.color, "black")
        self.assertEqual(self.state.slot_answers["color"].status, "answered")
        self.reducer.record_question(self.state, "brand")
        self.apply(3, "any brand is fine")
        self.assertEqual(self.state.slot_answers["brand"].status, "declined")
        self.assertIsNone(self.state.constraints.brand)
        self.reducer.record_question(self.state, "size")
        self.apply(4, "not sure yet")
        self.assertEqual(self.state.slot_answers["size"].status, "asked")
        self.apply(5, "9")
        self.assertEqual(self.state.constraints.size, "9")
        self.assertEqual(self.state.slot_answers["size"].status, "answered")

    def test_scoped_events_preserve_unrelated_state(self) -> None:
        self.apply(1, "looking for black shoes under $100 size 9")
        self.apply(2, "actually white instead")
        self.assertEqual(self.state.constraints.color, "white")
        self.assertEqual(self.state.constraints.price_max, 100.0)
        self.assertEqual(self.state.constraints.size, "9")
        self.apply(3, "anything except red")
        self.assertEqual(self.state.constraints.color, "white")
        self.assertIn("red", self.state.constraints.exclusions["color"])
        self.apply(4, "ignore my earlier preference")
        self.assertIsNone(self.state.constraints.color)
        self.assertEqual(self.state.constraints.price_max, 100.0)

    def test_explicit_switch_beats_strong_rule_and_weak_input_is_stable(self) -> None:
        self.apply(1, "looking for black shoes")
        self.assertEqual(self.state.intent_state.label, "buying")
        self.apply(2, "I am just exploring options now, looking for shoes")
        self.assertEqual(self.state.intent_state.label, "browsing")
        self.assertEqual(self.state.intent_state.last_switch_turn, 2)
        self.apply(3, "maybe")
        self.assertEqual(self.state.intent_state.label, "browsing")
        self.apply(4, "I am ready to buy specific shoes")
        self.assertEqual(self.state.intent_state.label, "buying")
        self.assertEqual(self.state.intent_state.last_switch_turn, 4)

    def test_active_view_expires_only_inferred_soft_slots(self) -> None:
        self.state.turn_count = 4
        self.state.slots["color"] = make_slot("black", name="color", turn=1)
        self.state.slots["style"] = SlotValue("sporty", SlotKind.SOFT, 0.8, "model", 1, ttl=3)
        active = self.state.active_slots()
        self.assertIn("color", active)
        self.assertNotIn("style", active)
        self.assertEqual(self.state.slots["style"].value, "sporty")

    def test_transaction_failure_keeps_committed_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = write_catalog(Path(directory) / "catalog.jsonl")
            agent = Agent(config=AgentConfig(catalog_path=catalog, multiturn_state_enabled=True))
            agent.reset("s", profile())
            first = agent.respond("s", "looking for black running shoes", 1, 10)
            committed = agent._core.sessions.get("s")
            self.assertEqual(committed.turn_count, 1)
            agent._core.index = RaisingIndex()  # type: ignore[assignment]
            second = agent.respond("s", "under $100", 2, 10)
            after = agent._core.sessions.get("s")
            self.assertEqual(after.turn_count, 1)
            self.assertEqual(after.history, ["looking for black running shoes"])
            self.assertEqual(second["recommendations"], first["recommendations"])

    def test_sessions_and_invalid_turns_are_isolated(self) -> None:
        self.store.reset("other", profile("durable"))
        self.apply(1, "looking for black shoes")
        other = self.store.begin_transaction("other", 1, "just exploring options now")
        self.assertEqual(other.slots, {})
        with self.assertRaises(AgentError):
            self.store.begin_transaction("s", 3, "skip")
        self.assertEqual(self.store.get("s").turn_count, 1)


if __name__ == "__main__":
    unittest.main()
