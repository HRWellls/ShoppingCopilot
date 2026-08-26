from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import Candidate
from src.output import sanitize_candidates
from starter.agent import Agent
from tests.fixtures import profile, write_catalog


class RaisingIndex:
    def search(self, query: str, k: int, subset: object = None) -> list[Candidate]:
        raise AgentError(ErrorCode.RETRIEVAL, "injected failure")


class AgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog_path = write_catalog(self.root / "catalog.jsonl")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_agent(self, *, trace_enabled: bool = False, trace_path: Path | None = None) -> Agent:
        config = AgentConfig(
            catalog_path=self.catalog_path,
            trace_enabled=trace_enabled,
            trace_path=trace_path or self.root / "turns.jsonl",
        )
        return Agent(config=config)

    def assert_contract(self, response: dict) -> None:
        self.assertIsInstance(response["message"], str)
        self.assertIsNone(response["ask_attribute"])
        self.assertIsInstance(response["recommendations"], list)
        self.assertLessEqual(len(response["recommendations"]), 10)
        self.assertEqual(response["usage"], {"prompt_tokens": 0, "completion_tokens": 0})

    def test_successful_response_and_turn_ten_are_legal(self) -> None:
        agent = self.make_agent()
        agent.reset("session", profile())
        response = agent.respond("session", "black running shoes under $100 size 9", 1, 10)
        self.assert_contract(response)
        self.assertEqual(response["recommendations"][0]["parent_asin"], "SHOE_BLACK_9")
        for turn in range(2, 11):
            response = agent.respond("session", "black running shoes", turn, 10)
        self.assert_contract(response)

    def test_sanitizer_preserves_first_valid_unique_order(self) -> None:
        agent = self.make_agent()
        values = ["SHOE_BLACK_9", "bad", "SHOE_BLACK_9", "SHIRT_BLUE_M", "SHOE_WHITE_9"]
        result = sanitize_candidates(values, agent._core.catalog, 2)
        self.assertEqual(result, ["SHOE_BLACK_9", "SHIRT_BLUE_M"])

    def test_unknown_session_and_invalid_input_fall_back(self) -> None:
        agent = self.make_agent()
        response = agent.respond("missing", "shoes", 1, 10)
        self.assert_contract(response)
        self.assertEqual(response["recommendations"], [])
        agent.reset("session", profile())
        response = agent.respond("session", None, 1, 10)  # type: ignore[arg-type]
        self.assert_contract(response)

    def test_retrieval_failure_returns_previous_candidates(self) -> None:
        agent = self.make_agent()
        agent.reset("session", profile())
        initial = agent.respond("session", "running shoes", 1, 10)
        expected = initial["recommendations"]
        agent._core.index = RaisingIndex()  # type: ignore[assignment]
        response = agent.respond("session", "under $100", 2, 10)
        self.assert_contract(response)
        self.assertEqual(response["recommendations"], expected)

    def test_trace_matches_output_and_excludes_sensitive_values(self) -> None:
        trace_path = self.root / "trace" / "turns.jsonl"
        agent = self.make_agent(trace_enabled=True, trace_path=trace_path)
        secret_profile = profile("TOP_SECRET_PROFILE")
        agent.reset("session", secret_profile)
        response = agent.respond("session", "TOP_SECRET_MESSAGE black running shoes", 1, 10)
        event = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(
            event["top10"],
            [item["parent_asin"] for item in response["recommendations"]],
        )
        serialized = json.dumps(event)
        self.assertNotIn("TOP_SECRET_PROFILE", serialized)
        self.assertNotIn("TOP_SECRET_MESSAGE", serialized)
        self.assertNotIn("ground_truth", serialized)
        self.assertFalse(event["fallback"])

    def test_trace_can_be_disabled_or_fail_without_changing_response(self) -> None:
        disabled_path = self.root / "disabled.jsonl"
        disabled = self.make_agent(trace_enabled=False, trace_path=disabled_path)
        disabled.reset("session", profile())
        expected = disabled.respond("session", "running shoes", 1, 10)
        self.assertFalse(disabled_path.exists())

        parent_file = self.root / "not-a-directory"
        parent_file.write_text("x", encoding="utf-8")
        failing = self.make_agent(trace_enabled=True, trace_path=parent_file / "turns.jsonl")
        failing.reset("session", profile())
        actual = failing.respond("session", "running shoes", 1, 10)
        self.assertEqual(actual, expected)
        self.assertTrue(failing._core.trace.degraded)

    def test_public_contract_is_stable_and_invalid_turn_does_not_advance(self) -> None:
        agent = self.make_agent()
        agent.reset("session", profile())
        first = agent.respond("session", "running shoes", 1, 10)
        self.assertEqual(set(first), {"message", "ask_attribute", "recommendations", "usage"})
        ids = [item["parent_asin"] for item in first["recommendations"]]
        self.assertEqual(ids, list(dict.fromkeys(ids)))
        state = agent._core.sessions.get("session")
        self.assertEqual(state.turn_count, 1)
        agent.respond("session", "skip a turn", 3, 10)
        self.assertEqual(agent._core.sessions.get("session").turn_count, 1)
        second = agent.respond("session", "under $100", 2, 10)
        self.assert_contract(second)


if __name__ == "__main__":
    unittest.main()
