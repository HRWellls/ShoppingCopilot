from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.models import Candidate, StructuredRetrievalRequest
from src.retrieval.attributes import tokens
from src.retrieval.rerank import RouteReranker
from tests.fixtures import CATALOG_ROWS, write_catalog


class RouteRerankerTest(unittest.TestCase):
    def test_dialogue_control_words_are_not_product_evidence(self) -> None:
        self.assertEqual(tokens("Actually ignore my earlier preference: water resistant"), {"water", "resistant"})

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        catalog_path = write_catalog(Path(self.temp.name) / "catalog.jsonl")
        self.catalog = CatalogStore(AgentConfig(catalog_path=catalog_path))
        self.reranker = RouteReranker(self.catalog)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_buying_exact_match_outranks_lexical_near_match(self) -> None:
        request = StructuredRetrievalRequest(
            "buying",
            (("price_max", 100.0), ("color", "black"), ("material", "mesh")),
            (("category", ("shoes",)), ("color", ("black",)), ("material", ("mesh",))),
            ("running",),
            "black mesh running shoes",
            0.9,
        )
        result = self.reranker.rank(
            request,
            {"lexical": [Candidate("SHOE_WHITE_9", 2.0), Candidate("SHOE_BLACK_9", 1.0)]},
            frozenset({"SHOE_BLACK_9"}),
            10,
        )
        self.assertEqual([item.parent_asin for item in result], ["SHOE_BLACK_9"])
        self.assertIn("field_material", result[0].source_scores)
        self.assertLess(result[0].score, 0.1)
        self.assertGreater(result[0].source_scores["rerank_total"], 100)
        self.assertEqual(result, self.reranker.rank(
            request,
            {"lexical": [Candidate("SHOE_WHITE_9", 2.0), Candidate("SHOE_BLACK_9", 1.0)]},
            frozenset({"SHOE_BLACK_9"}),
            10,
        ))

    def test_browsing_diversity_does_not_cross_relevance_band(self) -> None:
        candidates = [
            Candidate("SHOE_BLACK_9", 10.0),
            Candidate("SHOE_WHITE_9", 9.8),
            Candidate("SHIRT_BLUE_M", 9.8),
        ]
        result = self.reranker._diversify_within_relevance_band(candidates)
        self.assertEqual(result[0].parent_asin, "SHOE_BLACK_9")
        self.assertEqual({item.parent_asin for item in result[1:]}, {"SHOE_WHITE_9", "SHIRT_BLUE_M"})

    def test_unknown_route_prefers_category_evidence(self) -> None:
        request = StructuredRetrievalRequest(
            "unknown", (), (("category", ("shirts",)),), (), "something to wear", 0.2
        )
        result = self.reranker.rank(
            request,
            {"lexical": [Candidate("SHOE_BLACK_9", 2.0), Candidate("SHIRT_BLUE_M", 1.0)]},
            frozenset({"SHOE_BLACK_9", "SHIRT_BLUE_M"}),
            10,
        )
        self.assertEqual(result[0].parent_asin, "SHIRT_BLUE_M")

    def test_rare_query_terms_outweigh_common_context(self) -> None:
        rows = CATALOG_ROWS + (
            {
                "parent_asin": "RARE_ALLOY",
                "title": "Men Jewelry Alloy Pentagram",
                "features": ["alloy pendant"],
                "description": [],
                "price": 20,
                "categories": ["Clothing, Shoes & Jewelry", "Men", "Jewelry"],
                "details": {"Material": "Alloy"},
                "store": "RareWorks",
            },
            {
                "parent_asin": "COMMON_JEWELRY",
                "title": "Men Jewelry Everyday Item",
                "features": ["daily accessory"],
                "description": [],
                "price": 20,
                "categories": ["Clothing, Shoes & Jewelry", "Men", "Jewelry"],
                "details": {},
                "store": "CommonWorks",
            },
        )
        path = write_catalog(Path(self.temp.name) / "rare-catalog.jsonl", rows)
        reranker = RouteReranker(CatalogStore(AgentConfig(catalog_path=path)))
        request = StructuredRetrievalRequest(
            "buying",
            (),
            (),
            (),
            "looking for men jewelry with alloy",
            0.9,
        )
        result = reranker.rank(
            request,
            {"lexical": [Candidate("COMMON_JEWELRY", 2.0), Candidate("RARE_ALLOY", 1.0)]},
            frozenset({"COMMON_JEWELRY", "RARE_ALLOY"}),
            2,
        )
        self.assertEqual(result[0].parent_asin, "RARE_ALLOY")
        self.assertGreater(
            result[0].source_scores["title_overlap"],
            result[1].source_scores["title_overlap"],
        )

    def test_semantic_history_contributes_to_category_evidence(self) -> None:
        request = StructuredRetrievalRequest(
            "browsing",
            (),
            (),
            ("running",),
            "no additional material preference",
            0.8,
        )
        result = self.reranker.rank(
            request,
            {"lexical": [Candidate("SHIRT_BLUE_M", 2.0), Candidate("SHOE_BLACK_9", 1.0)]},
            frozenset({"SHIRT_BLUE_M", "SHOE_BLACK_9"}),
            2,
        )
        shoe = next(candidate for candidate in result if candidate.parent_asin == "SHOE_BLACK_9")
        self.assertIn("category_overlap", shoe.source_scores)

    def test_exact_feature_phrase_is_explainable(self) -> None:
        request = StructuredRetrievalRequest(
            "buying", (), (), ("For that, what matters is: breathable mesh; rubber sole",), "", 0.9
        )
        result = self.reranker.rank(
            request,
            {"lexical": [Candidate("SHOE_WHITE_9", 2.0), Candidate("SHOE_BLACK_9", 1.0)]},
            frozenset({"SHOE_BLACK_9", "SHOE_WHITE_9"}),
            2,
        )
        self.assertEqual(result[0].parent_asin, "SHOE_BLACK_9")
        self.assertIn("exact_phrase", result[0].source_scores)


if __name__ == "__main__":
    unittest.main()
