from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluator.local_evaluator import catalog_index, evaluate
from evaluator.retrieval_diagnostics import evaluate_with_diagnostics, stable_quality_sha256
from scripts.retrieval_diagnostic_benchmark import build_comparison
from src.config import AgentConfig
from starter.agent import Agent
from tests.fixtures import profile, write_catalog


class RetrievalDiagnosticsTest(unittest.TestCase):
    def test_comparison_emits_each_promotion_gate(self) -> None:
        baseline = {
            "hit_rate_at_10": 0.38,
            "mrr": 0.26,
            "recommended_technical_score": 0.331459,
            "scenario_metrics": {"buying": {"hit_rate_at_10": 0.3, "mrr": 0.2, "mttc": 8.0}},
            "benchmark": {"p95_ms": 100.0, "quality_sha256": "b3"},
        }
        result = {
            "hit_rate_at_10": 0.65,
            "mrr": 0.4,
            "recommended_technical_score": 0.5,
            "scenario_metrics": {
                "buying": {"hit_rate_at_10": 0.4, "mrr": 0.3, "mttc": 7.0},
                "intent_override": {"hit_rate_at_10": 0.8, "mrr": 0.5, "mttc": 7.0},
            },
            "retrieval_diagnostics": {"overall": {"candidate_recall_at_pool": 0.95}},
            "benchmark": {"p95_ms": 125.0},
        }
        comparison = build_comparison(result, baseline)
        self.assertEqual(
            set(comparison["gates"]),
            {
                "candidate_recall_at_150", "overall_hit_at_10", "technical_score",
                "intent_override_hit_at_10", "scenario_non_regression", "p95_overhead_ms",
            },
        )
        self.assertTrue(comparison["all_promotion_gates_pass"])

    def test_diagnostics_preserve_scores_and_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = write_catalog(Path(directory) / "catalog.jsonl")
            ids, categories, products = catalog_index(catalog)
            samples = [{
                "sample_id": "diag_1",
                "scenario_type": "buying",
                "user_profile": profile(),
                "ground_truth": {"parent_asin": "SHOE_BLACK_9"},
                "intent_card": {
                    "target_category": "running shoes",
                    "hard_constraints": ["black", "size 9"],
                    "soft_preferences": ["mesh"],
                },
                "behavior": {"scenario_type": "buying"},
            }]
            config = AgentConfig(catalog_path=catalog, fused_k=100)
            plain = evaluate(Agent(config=config), samples, ids, categories, products)
            first = evaluate_with_diagnostics(Agent(config=config), samples, ids, categories, products)
            second = evaluate_with_diagnostics(Agent(config=config), samples, ids, categories, products)
            for key in ("hit_rate_at_10", "mrr", "mttc", "recommended_technical_score"):
                self.assertEqual(first[key], plain[key])
            self.assertEqual(stable_quality_sha256(first), stable_quality_sha256(second))
            self.assertIn("buying", first["retrieval_diagnostics"]["scenarios"])
            self.assertIn("target_ranks", first["sessions"][0]["turns"][0])
            self.assertIn("query_evidence", first["sessions"][0]["turns"][0])

            ranked_config = AgentConfig(
                catalog_path=catalog, fused_k=100,
                multiturn_state_enabled=True, intent_routing_enabled=True, intent_policy_enabled=True,
                attribute_retrieval_enabled=True, attribute_reranking_enabled=True,
            )
            ranked = evaluate_with_diagnostics(Agent(config=ranked_config), samples, ids, categories, products)
            explanations = ranked["sessions"][0]["turns"][0]["reranker_explanations"]
            self.assertTrue(explanations)
            self.assertIn("contributions", explanations[0])


if __name__ == "__main__":
    unittest.main()
