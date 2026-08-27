from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.models import Candidate, ConstraintSet, SessionState
from src.retrieval import BM25Index, HardFilter, HybridRetriever, build_route_plan, build_route_queries, fuse_rankings
from tests.fixtures import write_catalog
from src.state import make_slot


class StaticDense:
    def search(self, query, k, subset=None):
        values = ["SHIRT_BLUE_M", "SHOE_BLACK_9", "SHOE_WHITE_9"]
        if subset is not None:
            values = [value for value in values if value in subset]
        return [Candidate(value, 1.0 - i / 10, {"dense": 1.0 - i / 10}, {"dense": i + 1}, ("dense",)) for i, value in enumerate(values)]


class HybridTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        path = write_catalog(Path(self.temp.name) / "catalog.jsonl")
        self.config = AgentConfig(catalog_path=path, fused_k=100, lexical_k=100, dense_k=100)
        self.catalog = CatalogStore(self.config)
        self.bm25 = BM25Index(self.catalog, self.config)
        self.filter = HardFilter(self.catalog)

    def tearDown(self) -> None:
        self.bm25.close()
        self.temp.cleanup()

    def test_rrf_deduplicates_and_records_sources(self) -> None:
        result = fuse_rankings(
            {"lexical": [Candidate("A", 1), Candidate("B", .5)], "dense": [Candidate("B", 1), Candidate("C", .5)]},
            {"lexical": .5, "dense": .5}, 60, 100,
        )
        self.assertEqual(result[0].parent_asin, "B")
        self.assertEqual(result[0].sources, ("dense", "lexical"))

    def test_buying_filters_both_routes_and_dense_off_works(self) -> None:
        state = SessionState("s", intent="buying", constraints=ConstraintSet(price_max=100, color="black", category="running shoes"), last_query="running shoes")
        enabled = AgentConfig(catalog_path=self.config.catalog_path, dense_enabled=True, fused_k=100)
        result = HybridRetriever(self.catalog, enabled, self.bm25, self.filter, StaticDense()).retrieve(state)
        self.assertEqual([item.parent_asin for item in result.candidates], ["SHOE_BLACK_9"])
        disabled = HybridRetriever(self.catalog, self.config, self.bm25, self.filter).retrieve(state)
        self.assertTrue(disabled.candidates)
        self.assertEqual(disabled.candidates[0].sources, ("lexical",))

    def test_browsing_query_preserves_context(self) -> None:
        state = SessionState("s", intent="browsing", last_query="summer wedding outfit")
        lexical, dense = build_route_queries(state)
        self.assertIn("summer wedding", dense)
        self.assertIn("summer wedding", lexical)

    def test_structured_request_uses_bounded_history_as_soft_context(self) -> None:
        state = SessionState(
            "s",
            intent="browsing",
            last_user_message="I do not have another preference",
            history=["looking for basketball clothing", "I do not have another preference"],
        )
        request = build_route_plan(state, self.config).request
        self.assertIn("looking for basketball clothing", request.semantic_terms)
        self.assertNotIn(("category", "basketball"), request.hard_filters)

    def test_override_turn_drops_prior_history_context(self) -> None:
        state = SessionState(
            "s",
            intent="buying",
            last_user_message="actually white instead",
            history=["black shoes", "actually white instead"],
            last_event_kinds=("override",),
        )
        request = build_route_plan(state, self.config).request
        self.assertNotIn("black shoes", request.semantic_terms)

    def test_d4_context_start_prevents_old_history_from_returning(self) -> None:
        config = AgentConfig(catalog_path=self.config.catalog_path, override_invalidation_enabled=True)
        state = SessionState(
            "s",
            intent="buying",
            last_user_message="no additional preference",
            history=["black shoes", "actually white instead", "no additional preference"],
            retrieval_context_start=1,
            query_evidence={"feature": "water resistant"},
        )
        request = build_route_plan(state, config).request
        self.assertNotIn("black shoes", request.semantic_terms)
        self.assertIn("actually white instead", request.semantic_terms)
        self.assertIn("water resistant", request.semantic_terms)

    def test_semantic_evidence_reaches_structured_candidate_channels(self) -> None:
        state = SessionState(
            "s",
            intent="buying",
            last_user_message="actually prioritize mesh",
            history=["actually prioritize mesh"],
            query_evidence={"feature": "black trail running"},
        )
        config = AgentConfig(
            catalog_path=self.config.catalog_path,
            fused_k=100,
            lexical_k=100,
            intent_routing_enabled=True,
            attribute_retrieval_enabled=True,
            attribute_reranking_enabled=True,
            override_invalidation_enabled=True,
        )
        bm25 = BM25Index(self.catalog, config)
        self.addCleanup(bm25.close)
        result = HybridRetriever(self.catalog, config, bm25, self.filter).retrieve(state)
        self.assertIn("SHOE_BLACK_9", result.stages["structured_lexical"])
        self.assertIn("SHOE_BLACK_9", result.stages["attribute"])

    def test_single_pass_uses_attribute_candidates_without_fts_queries(self) -> None:
        state = SessionState(
            "s", intent="buying", last_user_message="black mesh running shoes",
            history=["black mesh running shoes"],
        )
        config = AgentConfig(
            catalog_path=self.config.catalog_path,
            fused_k=100,
            lexical_k=100,
            intent_routing_enabled=True,
            attribute_retrieval_enabled=True,
            attribute_reranking_enabled=True,
            optimized_single_pass_enabled=True,
        )
        bm25 = BM25Index(self.catalog, config)
        self.addCleanup(bm25.close)
        result = HybridRetriever(self.catalog, config, bm25, self.filter).retrieve(state)
        self.assertEqual(result.stages["lexical"], ())
        self.assertEqual(result.stages["structured_lexical"], ())
        self.assertTrue(result.stages["attribute"])

    def test_single_pass_dense_cannot_bypass_reranker_eligibility(self) -> None:
        state = SessionState("s", intent="buying", last_user_message="black running shoes")
        state.slots = {"color": make_slot("black", name="color", turn=1)}
        config = AgentConfig(
            catalog_path=self.config.catalog_path,
            fused_k=100,
            lexical_k=100,
            dense_enabled=True,
            intent_routing_enabled=True,
            attribute_retrieval_enabled=True,
            attribute_reranking_enabled=True,
            optimized_single_pass_enabled=True,
        )
        bm25 = BM25Index(self.catalog, config)
        self.addCleanup(bm25.close)
        result = HybridRetriever(self.catalog, config, bm25, self.filter, StaticDense()).retrieve(state)
        self.assertTrue(all(self.catalog.require(item.parent_asin).attributes["color"] == {"black"} for item in result.candidates))

    def test_safe_relaxation_does_not_remove_budget(self) -> None:
        state = SessionState("s", intent="buying", constraints=ConstraintSet(price_max=100, brand="Missing", category="running shoes"), last_query="running shoes")
        result = HybridRetriever(self.catalog, self.config, self.bm25, self.filter).retrieve(state)
        self.assertEqual(result.relaxation.relaxed, "brand")
        self.assertTrue(all(self.catalog.require(item.parent_asin).price <= 100 for item in result.candidates))

    def test_structured_request_and_attribute_channel_preserve_top_result(self) -> None:
        state = SessionState(
            "s", intent="buying", intent_confidence=0.9,
            last_query="black trail running sneakers", last_user_message="black trail running sneakers",
        )
        state.slots = {
            "price_max": make_slot(100, name="price_max", turn=1),
            "color": make_slot("black", name="color", turn=1),
            "category": make_slot("sneakers", name="category", turn=1),
        }
        plan = build_route_plan(state, self.config)
        self.assertIn(("price_max", 100), plan.request.hard_filters)
        self.assertIn(("category", ("shoes",)), plan.request.lexical_fields)
        enabled = AgentConfig(
            catalog_path=self.config.catalog_path, fused_k=100, lexical_k=100,
            attribute_retrieval_enabled=True, intent_routing_enabled=True,
        )
        baseline_config = AgentConfig(
            catalog_path=self.config.catalog_path, fused_k=100, lexical_k=100,
            intent_routing_enabled=True,
        )
        baseline = HybridRetriever(self.catalog, baseline_config, self.bm25, self.filter).retrieve(state)
        structured_bm25 = BM25Index(self.catalog, enabled)
        self.addCleanup(structured_bm25.close)
        result = HybridRetriever(self.catalog, enabled, structured_bm25, self.filter).retrieve(state)
        self.assertEqual(
            [item.parent_asin for item in result.candidates],
            [item.parent_asin for item in baseline.candidates],
        )
        self.assertIn("SHOE_BLACK_9", result.stages["attribute"])
        self.assertGreaterEqual(len(result.stages["raw_channel_union"]), len(result.stages["fused"]))
        self.assertEqual(structured_bm25.schema_version, "attribute-fields-v1")

    def test_attribute_reranking_records_explainable_features(self) -> None:
        state = SessionState("s", intent="buying", intent_confidence=0.9, last_query="black mesh running shoes", last_user_message="black mesh running shoes")
        state.slots = {
            "color": make_slot("black", name="color", turn=1),
            "material": make_slot("mesh", name="material", turn=1),
            "category": make_slot("shoes", name="category", turn=1),
        }
        config = AgentConfig(
            catalog_path=self.config.catalog_path, fused_k=100, lexical_k=100,
            intent_routing_enabled=True, attribute_retrieval_enabled=True,
            attribute_reranking_enabled=True,
        )
        bm25 = BM25Index(self.catalog, config)
        self.addCleanup(bm25.close)
        result = HybridRetriever(self.catalog, config, bm25, self.filter).retrieve(state)
        self.assertEqual(result.candidates[0].parent_asin, "SHOE_BLACK_9")
        self.assertIn("field_material", result.candidates[0].source_scores)
        self.assertEqual(result.stages["reranked"][0], "SHOE_BLACK_9")


if __name__ == "__main__":
    unittest.main()
