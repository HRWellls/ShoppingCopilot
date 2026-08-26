from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.retrieval.dense import DenseIndex, SentenceTransformerProvider
from tests.fixtures import write_catalog


class MockProvider:
    model_id = "mock"
    model_version = "1"
    dimension = 3

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        result = []
        for text in texts:
            value = text.casefold()
            result.append([value.count("shoe") + value.count("running"), value.count("shirt"), value.count("boot")])
        return np.asarray(result, dtype=np.float32) + 0.01


class FailingProvider(MockProvider):
    def embed(self, texts):
        raise RuntimeError("offline")


class DenseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        catalog_path = write_catalog(root / "catalog.jsonl")
        self.config = AgentConfig(catalog_path=catalog_path, dense_enabled=True, dense_build_allowed=True, dense_index_path=root / "dense.faiss", dense_k=3)
        self.catalog = CatalogStore(self.config)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_search_subset_cache_and_manifest_reuse(self) -> None:
        provider = MockProvider()
        index = DenseIndex(self.catalog, self.config, provider)
        first = index.search("running shoe", 2, {"SHOE_BLACK_9", "SHIRT_BLUE_M"})
        self.assertEqual(first[0].parent_asin, "SHOE_BLACK_9")
        calls = provider.calls
        self.assertEqual(index.search("running shoe", 2, {"SHOE_BLACK_9", "SHIRT_BLUE_M"}), first)
        self.assertEqual(provider.calls, calls)
        loaded_provider = MockProvider()
        loaded = DenseIndex(self.catalog, self.config, loaded_provider)
        self.assertTrue(loaded.loaded_from_disk)
        self.assertEqual(loaded_provider.calls, 0, "persisted index must not re-embed catalog products")
        if loaded.index is not None:
            self.assertEqual(loaded.index.ntotal, self.catalog.record_count)
        else:
            self.assertTrue(np.array_equal(index.matrix, loaded.matrix))

    def test_manifest_mismatch_rebuilds(self) -> None:
        DenseIndex(self.catalog, self.config, MockProvider())
        changed = MockProvider()
        changed.model_version = "2"
        DenseIndex(self.catalog, self.config, changed)
        self.assertGreater(changed.calls, 0)

    def test_runtime_manifest_mismatch_never_rebuilds(self) -> None:
        protected_path = Path(self.temp.name) / "protected.faiss"
        protected_path.write_bytes(b"do-not-overwrite")
        runtime = AgentConfig(
            catalog_path=self.config.catalog_path,
            dense_enabled=True,
            dense_build_allowed=False,
            dense_index_path=protected_path,
            dense_k=3,
        )
        provider = MockProvider()
        with self.assertRaises(AgentError) as context:
            DenseIndex(self.catalog, runtime, provider)
        self.assertEqual(context.exception.code, ErrorCode.INDEX_NOT_READY)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(protected_path.read_bytes(), b"do-not-overwrite")

    def test_provider_failure_is_controlled(self) -> None:
        with self.assertRaises(AgentError):
            DenseIndex(self.catalog, self.config, FailingProvider())

    def test_missing_local_model_is_controlled(self) -> None:
        with self.assertRaises(AgentError) as context:
            SentenceTransformerProvider(Path("/missing"), "missing")
        self.assertEqual(context.exception.code, ErrorCode.MODEL_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
