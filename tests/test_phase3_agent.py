from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.dialogue import ClarificationPolicy
from src.models import Candidate, SessionState
from starter.agent import Agent
from tests.fixtures import profile, write_catalog


class FakeResponse:
    def __init__(self, payload): self.payload = json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self, limit): return self.payload[:limit]


def model_response():
    content = {"intent": "buying", "intent_confidence": .9, "slot_updates": {"color": {"value": "black", "kind": "soft", "confidence": .8}}, "clears": [], "overrides": [], "query_text": "black running shoes", "evidence": []}
    return {"choices": [{"message": {"content": json.dumps(content)}}], "usage": {"prompt_tokens": 4, "completion_tokens": 3}}


class Phase3AgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog = write_catalog(self.root / "catalog.jsonl")

    def tearDown(self) -> None: self.temp.cleanup()

    def test_policy_clarifies_once_and_turn_ten_recommends(self) -> None:
        config = AgentConfig(catalog_path=self.catalog, fused_k=100)
        store = CatalogStore(config)
        policy = ClarificationPolicy(store, config)
        candidates = [Candidate("SHOE_BLACK_9", 1)] * 11
        state = SessionState("s", turn_count=1)
        first = policy.decide(state, candidates)
        self.assertEqual(first.action, "clarify")
        state.asked_slots.add(first.slot or "")
        second = policy.decide(state, candidates)
        self.assertNotEqual(second.slot, first.slot)
        state.turn_count = 10
        self.assertEqual(policy.decide(state, candidates).action, "recommend")
        disabled = ClarificationPolicy(store, AgentConfig(catalog_path=self.catalog, fused_k=100, clarification_enabled=False))
        self.assertEqual(disabled.decide(SessionState("x", turn_count=1), candidates).action, "recommend")

    def test_end_to_end_override_negation_and_llm_off(self) -> None:
        agent = Agent(config=AgentConfig(catalog_path=self.catalog))
        agent.reset("s", profile())
        agent.respond("s", "black running shoes", 1, 10)
        agent.respond("s", "actually white instead", 2, 10)
        self.assertEqual(agent._core.sessions.get("s").constraints.color, "white")
        agent.respond("s", "not red", 3, 10)
        self.assertIn("red", agent._core.sessions.get("s").constraints.exclusions["color"])
        self.assertIsNone(agent._core.parser.model)

    def test_llm_usage_and_trace_fields_are_safe(self) -> None:
        key_path = self.root / "api.env"; key_path.write_text("secret-value", encoding="utf-8"); key_path.chmod(0o600)
        trace = self.root / "trace.jsonl"
        config = AgentConfig(catalog_path=self.catalog, llm_enabled=True, api_key_path=key_path, trace_enabled=True, trace_path=trace)
        agent = Agent(config=config, llm_opener=lambda *a, **k: FakeResponse(model_response()))
        agent.reset("s", profile())
        response = agent.respond("s", "black running shoes", 1, 10)
        self.assertEqual(response["usage"], {"prompt_tokens": 4, "completion_tokens": 3})
        event = json.loads(trace.read_text(encoding="utf-8"))
        self.assertTrue(event["llm_used"])
        self.assertIn("candidate_sources", event)
        self.assertNotIn("secret-value", json.dumps(event))

    def test_dense_enabled_without_model_falls_back(self) -> None:
        agent = Agent(config=AgentConfig(
            catalog_path=self.catalog,
            dense_enabled=True,
            dense_model_path=self.root / "missing-model",
            dense_index_path=self.root / "missing.faiss",
        ))
        self.assertIsNone(agent._core.dense)
        self.assertEqual(agent._core.dense_fallback, "E_MODEL_UNAVAILABLE")
        agent.reset("s", profile())
        self.assertTrue(agent.respond("s", "running shoes", 1, 10)["recommendations"])


if __name__ == "__main__": unittest.main()
