from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.models import Candidate, ConstraintSet, SessionState
from src.retrieval import BM25Index, HardFilter, HybridRetriever, build_route_queries, fuse_rankings
from tests.fixtures import write_catalog


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

    def test_safe_relaxation_does_not_remove_budget(self) -> None:
        state = SessionState("s", intent="buying", constraints=ConstraintSet(price_max=100, brand="Missing", category="running shoes"), last_query="running shoes")
        result = HybridRetriever(self.catalog, self.config, self.bm25, self.filter).retrieve(state)
        self.assertEqual(result.relaxation.relaxed, "brand")
        self.assertTrue(all(self.catalog.require(item.parent_asin).price <= 100 for item in result.candidates))


if __name__ == "__main__":
    unittest.main()
