from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.config import AgentConfig
from src.models import ConstraintSet, IntentResult, StructuredRetrievalRequest


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
        with self.assertRaises(ValueError):
            AgentConfig(optimized_single_pass_enabled=True)

    def test_constraint_names_and_intent_validation(self) -> None:
        constraints = ConstraintSet(price_max=100.0, color="black")
        self.assertEqual(constraints.active_names(), ("price_max", "color"))
        self.assertEqual(IntentResult("buying", 0.8).label, "buying")
        with self.assertRaises(ValueError):
            IntentResult("invalid", 0.5)

    def test_structured_retrieval_request_separates_boundaries(self) -> None:
        request = StructuredRetrievalRequest(
            "buying", (("price_max", 100.0),), (("category", ("shoes",)),), ("running",), "trail shoes", 0.9
        )
        self.assertEqual(request.hard_filters, (("price_max", 100.0),))
        with self.assertRaises(ValueError):
            StructuredRetrievalRequest(
                "buying", (), (("price_max", ("100",)),), (), "shoes", 0.9
            )

    def test_intent_features_are_disabled_and_private_paths_are_hidden(self) -> None:
        config = AgentConfig(
            intent_model_path="private/model.onnx",
            intent_manifest_path="private/manifest.json",
        )
        self.assertFalse(config.multiturn_state_enabled)
        self.assertFalse(config.intent_routing_enabled)
        self.assertFalse(config.intent_policy_enabled)
        self.assertEqual(config.intent_model_mode, "off")
        snapshot = json.dumps(config.public_snapshot())
        self.assertNotIn("private/model.onnx", snapshot)
        self.assertNotIn("private/manifest.json", snapshot)

    def test_intent_config_rejects_invalid_modes_and_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            AgentConfig(intent_model_mode="invalid")
        with self.assertRaises(ValueError):
            AgentConfig(intent_classifier_strategy="invalid")
        with self.assertRaises(ValueError):
            AgentConfig(intent_switch_confidence=1.1)
        with self.assertRaises(ValueError):
            AgentConfig(intent_initial_margin=-0.1)
        with self.assertRaises(ValueError):
            AgentConfig(intent_p95_budget_ms=0)

    def test_frozen_b0_score_matches_formula(self) -> None:
        fixture = json.loads(Path("docs/baselines/phase3-b0.json").read_text(encoding="utf-8"))
        efficiency = max(0.0, min(1.0, (11.0 - fixture["mttc"]) / 10.0))
        score = 0.5 * fixture["hit_rate_at_10"] + 0.3 * fixture["mrr"] + 0.2 * efficiency
        self.assertAlmostEqual(score, fixture["recommended_technical_score"], places=6)


if __name__ == "__main__":
    unittest.main()
