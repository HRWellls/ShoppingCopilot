from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.dialogue import ClarificationPolicy
from src.models import AskedSlotState, Candidate, ConstraintSet, IntentState, SessionState
from src.nlu import RuleConstraintExtractor
from src.retrieval import BM25Index, HardFilter, HybridRetriever, build_route_plan, diversify_candidates
from src.state import make_slot
from starter.agent import Agent
from tests.fixtures import profile, write_catalog


class IntentRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog_path = write_catalog(self.root / "catalog.jsonl")
        self.config = AgentConfig(
            catalog_path=self.catalog_path,
            fused_k=100,
            lexical_k=100,
            intent_routing_enabled=True,
            intent_policy_enabled=True,
            multiturn_state_enabled=True,
        )
        self.catalog = CatalogStore(self.config)
        self.index = BM25Index(self.catalog, self.config)
        self.filter = HardFilter(self.catalog)

    def tearDown(self) -> None:
        self.index.close()
        self.temp.cleanup()

    @staticmethod
    def state(route: str, message: str = "") -> SessionState:
        return SessionState(
            "s",
            turn_count=1,
            intent=route,
            intent_state=IntentState(route, 0.9, "rule", 1),
            last_user_message=message,
            last_query=message,
        )

    def test_semantic_slots_are_soft_query_inputs_not_hard_filters(self) -> None:
        state = self.state("browsing", "casual outfit for a wedding")
        parsed = RuleConstraintExtractor().parse(state.last_user_message, state)
        self.assertEqual(parsed.slot_updates["style"].value, "casual")
        self.assertEqual(parsed.slot_updates["occasion"].value, "wedding")
        state.slots.update(parsed.slot_updates)
        plan = build_route_plan(state, self.config)
        self.assertIn("casual", plan.lexical_query)
        self.assertIn("wedding", plan.dense_query)
        self.assertFalse(hasattr(plan.filter_constraints, "occasion"))

    def test_route_plans_are_distinct_without_dense(self) -> None:
        buying = self.state("buying", "running shoes")
        buying.slots["category"] = make_slot("running shoes", name="category", turn=1)
        browsing = self.state("browsing", "running shoes for outdoor travel")
        browsing.slots.update({
            "category": make_slot("running shoes", name="category", turn=1),
            "use_case": make_slot("outdoor travel", name="use_case", turn=1),
        })
        unknown = self.state("unknown", "show options")
        plans = [build_route_plan(state, self.config) for state in (buying, browsing, unknown)]
        self.assertEqual([plan.route for plan in plans], ["buying", "browsing", "unknown"])
        self.assertTrue(plans[0].dense_uses_subset)
        self.assertFalse(plans[1].dense_uses_subset)
        self.assertNotEqual(plans[0].weights, plans[2].weights)
        self.assertIn("outdoor", plans[1].lexical_query)

    def test_buying_protects_boundaries_and_browsing_relaxes_category(self) -> None:
        buying = self.state("buying", "black running shoes")
        buying.slots.update({
            "category": make_slot("running shoes", name="category", turn=1),
            "color": make_slot("black", name="color", turn=1),
            "price_max": make_slot(100.0, name="price_max", turn=1),
        })
        buying.constraints.exclusions["color"] = frozenset({"red"})
        result = HybridRetriever(self.catalog, self.config, self.index, self.filter).retrieve(buying)
        self.assertTrue(all(self.catalog.require(item.parent_asin).price <= 100 for item in result.candidates))
        self.assertTrue(result.plan and result.plan.dense_uses_subset)

        browsing = self.state("browsing", "winter outfit ideas")
        browsing.slots.update(buying.slots)
        browsing.constraints.exclusions["color"] = frozenset({"red"})
        plan = build_route_plan(browsing, self.config)
        self.assertIsNone(plan.filter_constraints.category)
        self.assertEqual(plan.filter_constraints.price_max, 100.0)
        self.assertIn("red", plan.filter_constraints.exclusions["color"])

    def test_cleared_preference_is_not_reintroduced_from_history(self) -> None:
        state = self.state("buying", "white shoes")
        state.history = ["black shoes", "white shoes"]
        state.slots["category"] = make_slot("shoes", name="category", turn=1)
        plan = build_route_plan(state, self.config)
        self.assertNotIn("black", plan.lexical_query)
        self.assertIn("white", plan.lexical_query)

    def test_diversity_is_deterministic_and_penalizes_repetition(self) -> None:
        candidates = [
            Candidate("SHOE_BLACK_9", 1.0),
            Candidate("SHOE_WHITE_9", 0.99),
            Candidate("SHIRT_BLUE_M", 0.98),
        ]
        first = diversify_candidates(candidates, self.catalog)
        second = diversify_candidates(candidates, self.catalog)
        self.assertEqual(first, second)
        self.assertEqual(first[0].parent_asin, "SHOE_BLACK_9")
        self.assertEqual(first[1].parent_asin, "SHIRT_BLUE_M")

    def test_policy_priorities_declines_and_stop_conditions(self) -> None:
        policy = ClarificationPolicy(self.catalog, self.config)
        candidates = [Candidate(item.parent_asin, 1.0 - index / 1000) for index, item in enumerate(self.catalog)] * 4
        browsing = self.state("browsing")
        browsing.slots["category"] = make_slot("shoes", name="category", turn=1)
        self.assertEqual(policy.decide(browsing, candidates).slot, "use_case")
        browsing.slot_answers["use_case"] = AskedSlotState("use_case", 1, "declined", "browsing")
        browsing.last_top10_fingerprint = ()
        self.assertEqual(policy.decide(browsing, candidates).slot, "occasion")
        browsing.turn_count = 8
        self.assertEqual(policy.decide(browsing, candidates).reason, "late_turn_protection")

        buying = self.state("buying")
        buying.last_top10_fingerprint = tuple(item.parent_asin for item in candidates[:10])
        buying.consecutive_stable_top10 = self.config.clarification_stability_turns - 1
        self.assertEqual(policy.decide(buying, candidates).reason, "stable_top10")

        buying.last_event_kinds = ("override",)
        buying.last_top10_fingerprint = tuple(item.parent_asin for item in candidates[:10])
        buying.consecutive_stable_top10 = self.config.clarification_stability_turns
        self.assertNotEqual(policy.decide(buying, candidates).reason, "stable_top10")

    def test_gate_script_rejects_baseline_equal_report(self) -> None:
        baseline = json.loads(Path("docs/baselines/phase3-b0.json").read_text(encoding="utf-8"))
        report = self.root / "report.json"
        report.write_text(json.dumps(baseline), encoding="utf-8")
        result = subprocess.run(
            ["python", "-m", "scripts.check_multiturn_gate", str(report)],
            cwd=Path.cwd(), capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["passed"])

    def test_route_and_policy_trace_is_sanitized(self) -> None:
        trace = self.root / "route-trace.jsonl"
        agent = Agent(config=AgentConfig(
            catalog_path=self.catalog_path,
            fused_k=100,
            multiturn_state_enabled=True,
            intent_routing_enabled=True,
            intent_policy_enabled=True,
            trace_enabled=True,
            trace_path=trace,
        ))
        agent.reset("s", profile("PRIVATE_PROFILE_VALUE"))
        agent.respond("s", "PRIVATE_MESSAGE looking for black running shoes", 1, 10)
        event = json.loads(trace.read_text(encoding="utf-8"))
        self.assertEqual(event["route_plan"]["route"], "buying")
        self.assertTrue(event["policy_reason"])
        serialized = json.dumps(event)
        self.assertNotIn("PRIVATE_PROFILE_VALUE", serialized)
        self.assertNotIn("PRIVATE_MESSAGE", serialized)
        self.assertNotIn(str(self.root.resolve()), serialized)


if __name__ == "__main__":
    unittest.main()
