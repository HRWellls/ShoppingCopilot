from __future__ import annotations

import unittest
from pathlib import Path

from starter.agent import Agent


CATALOG_PATH = Path("data/catalog.jsonl")


@unittest.skipUnless(CATALOG_PATH.exists(), "full catalog is not available")
class FullCatalogSmokeTest(unittest.TestCase):
    def test_full_catalog_build_and_multi_turn_index_reuse(self) -> None:
        agent = Agent(CATALOG_PATH)
        self.assertEqual(agent._core.catalog.record_count, 50_000)
        self.assertEqual(len(agent._core.catalog.checksum), 64)
        self.assertEqual(agent._core.index.build_count, 1)

        agent.reset("full-smoke", {"summary": "", "preference_tags": []})
        first = agent.respond("full-smoke", "running shoes", 1, 10)
        second = agent.respond("full-smoke", "under $100", 2, 10)
        self.assertLessEqual(len(first["recommendations"]), 10)
        self.assertLessEqual(len(second["recommendations"]), 10)
        self.assertEqual(agent._core.index.build_count, 1)


if __name__ == "__main__":
    unittest.main()
