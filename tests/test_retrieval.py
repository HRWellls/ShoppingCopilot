from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.models import ConstraintSet
from src.retrieval import BM25Index, HardFilter
from tests.fixtures import write_catalog


class RetrievalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        path = write_catalog(Path(self.temp.name) / "catalog.jsonl")
        self.config = AgentConfig(catalog_path=path, retrieval_limit=3)
        self.catalog = CatalogStore(self.config)
        self.hard_filter = HardFilter(self.catalog)
        self.index = BM25Index(self.catalog, self.config)

    def tearDown(self) -> None:
        self.index.close()
        self.temp.cleanup()

    def test_budget_and_attributes_intersect_with_report(self) -> None:
        subset, report = self.hard_filter.apply(
            ConstraintSet(price_max=100, category="running shoes", color="black", size="9")
        )
        self.assertEqual(subset, frozenset({"SHOE_BLACK_9"}))
        self.assertEqual([step.name for step in report.steps], ["price_max", "category", "color", "size"])
        self.assertEqual(report.steps[0].before, 4)
        self.assertEqual(report.final_count, 1)
        self.assertNotIn("UNKNOWN_PRICE_BOOT", subset)

    def test_empty_filter_does_not_relax(self) -> None:
        subset, report = self.hard_filter.apply(ConstraintSet(size="99"))
        self.assertEqual(subset, frozenset())
        self.assertEqual(report.final_count, 0)
        self.assertEqual(self.index.search("shoes", 10, subset), [])

    def test_search_is_bounded_stable_and_reuses_index(self) -> None:
        first = self.index.search("trail running shoes", 10)
        second = self.index.search("trail running shoes", 10)
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 3)
        self.assertEqual(self.index.build_count, 1)
        self.assertEqual(first[0].parent_asin, "SHOE_BLACK_9")

    def test_caches_are_bounded(self) -> None:
        config = AgentConfig(catalog_path=self.config.catalog_path, cache_entries=1)
        hard_filter = HardFilter(self.catalog, config.cache_entries)
        index = BM25Index(self.catalog, config)
        try:
            hard_filter.apply(ConstraintSet(color="black"))
            hard_filter.apply(ConstraintSet(color="white"))
            index.search("black shoes", 2)
            index.search("white shoes", 2)
            self.assertEqual(len(hard_filter._cache), 1)
            self.assertEqual(len(index._cache), 1)
        finally:
            index.close()

    def test_search_enforces_subset(self) -> None:
        result = self.index.search("running shoes", 10, {"SHOE_WHITE_9"})
        self.assertEqual([candidate.parent_asin for candidate in result], ["SHOE_WHITE_9"])

    def test_empty_query_uses_catalog_order(self) -> None:
        result = self.index.search("the and please", 2, {"SHIRT_BLUE_M", "SHOE_WHITE_9"})
        self.assertEqual(
            [candidate.parent_asin for candidate in result],
            ["SHOE_WHITE_9", "SHIRT_BLUE_M"],
        )


if __name__ == "__main__":
    unittest.main()
