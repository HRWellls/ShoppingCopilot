from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.catalog.normalize import canonical_category, clean_text, normalize_collection, normalize_key, parse_price
from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from tests.fixtures import CATALOG_ROWS, write_catalog


class CatalogTest(unittest.TestCase):
    def test_normalization_is_deterministic_and_safe(self) -> None:
        self.assertEqual(clean_text("  Caf\u00e9\t<b>shoe</b>\x00 "), "Caf\u00e9 shoe")
        self.assertEqual(normalize_key("  NIKE  "), "nike")
        self.assertEqual(normalize_collection([" one ", None, "two"]), ("one", "two"))
        self.assertEqual(parse_price("USD $1,299.50"), 1299.5)
        self.assertIsNone(parse_price("not available"))
        self.assertIsNone(parse_price(-1))
        self.assertEqual(canonical_category("Sneakers"), "shoes")

    def test_store_loads_products_and_preserves_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_catalog(Path(directory) / "catalog.jsonl")
            store = CatalogStore(AgentConfig(catalog_path=path, description_max_chars=24))
            self.assertEqual(store.record_count, 4)
            self.assertEqual(store.stable_ids()[0], "SHOE_BLACK_9")
            self.assertEqual(store.require("SHOE_BLACK_9").brand_key, "swiftstep")
            self.assertIsNone(store.require("UNKNOWN_PRICE_BOOT").price)
            self.assertIn("black", store.attribute_values("SHOE_BLACK_9", "color"))
            self.assertIn("running", store.attribute_values("SHOE_BLACK_9", "use_case"))
            self.assertIn("cotton", " ".join(store.attribute_values("SHIRT_BLUE_M", "feature")))
            self.assertEqual(store.attribute_values("UNKNOWN_PRICE_BOOT", "price"), frozenset())
            self.assertEqual(len(store.checksum), 64)

    def test_checksum_is_stable_and_products_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_catalog(Path(directory) / "catalog.jsonl")
            first = CatalogStore(AgentConfig(catalog_path=path))
            second = CatalogStore(AgentConfig(catalog_path=path))
            self.assertEqual(first.checksum, second.checksum)
            before = first.require("SHOE_BLACK_9")
            with self.assertRaises(TypeError):
                before.metadata["title"] = "changed"  # type: ignore[index]
            self.assertEqual(first.require("SHOE_BLACK_9"), before)

    def test_duplicate_and_malformed_rows_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = write_catalog(root / "duplicate.jsonl", (CATALOG_ROWS[0], CATALOG_ROWS[0]))
            with self.assertRaises(AgentError) as context:
                CatalogStore(AgentConfig(catalog_path=duplicate))
            self.assertEqual(context.exception.code, ErrorCode.CATALOG)

            malformed = root / "malformed.jsonl"
            malformed.write_text(json.dumps(CATALOG_ROWS[0]) + "\n{bad}\n", encoding="utf-8")
            with self.assertRaises(AgentError):
                CatalogStore(AgentConfig(catalog_path=malformed))

    def test_optional_fields_can_be_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_catalog(Path(directory) / "catalog.jsonl", ({"parent_asin": "ONLY_ID"},))
            product = CatalogStore(AgentConfig(catalog_path=path))[0]
            self.assertEqual(product.title, "")
            self.assertEqual(product.categories, ())
            self.assertIsNone(product.brand)
            self.assertIsNone(product.price)


if __name__ == "__main__":
    unittest.main()
