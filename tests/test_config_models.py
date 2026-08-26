from __future__ import annotations

import unittest
from pathlib import Path

from src.config import AgentConfig
from src.models import ConstraintSet, IntentResult


class ConfigAndModelsTest(unittest.TestCase):
    def test_config_coerces_paths_and_validates_limits(self) -> None:
        config = AgentConfig(catalog_path="fixture.jsonl", trace_path="trace.jsonl")
        self.assertEqual(config.catalog_path, Path("fixture.jsonl"))
        self.assertEqual(config.trace_path, Path("trace.jsonl"))
        with self.assertRaises(ValueError):
            AgentConfig(max_turns=11)
        with self.assertRaises(ValueError):
            AgentConfig(query_token_limit=0)
        with self.assertRaises(ValueError):
            AgentConfig(cache_entries=0)

    def test_constraint_names_and_intent_validation(self) -> None:
        constraints = ConstraintSet(price_max=100.0, color="black")
        self.assertEqual(constraints.active_names(), ("price_max", "color"))
        self.assertEqual(IntentResult("buying", 0.8).label, "buying")
        with self.assertRaises(ValueError):
            IntentResult("invalid", 0.5)


if __name__ == "__main__":
    unittest.main()
