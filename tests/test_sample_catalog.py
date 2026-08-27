from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.sample_catalog import sample_catalog


class SampleCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "catalog.jsonl"
        self.rows = [{"parent_asin": f"ASIN-{index}"} for index in range(10)]
        self.source.write_text(
            "".join(json.dumps(row) + "\n" for row in self.rows),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def read_rows(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_samples_requested_number_of_unique_catalog_rows(self) -> None:
        output = self.root / "sample.jsonl"

        source_count = sample_catalog(self.source, output, 4, seed=7)
        sampled = self.read_rows(output)

        self.assertEqual(source_count, 10)
        self.assertEqual(len(sampled), 4)
        self.assertEqual(len({row["parent_asin"] for row in sampled}), 4)
        self.assertTrue(all(row in self.rows for row in sampled))

    def test_same_seed_produces_same_sample(self) -> None:
        first = self.root / "first.jsonl"
        second = self.root / "second.jsonl"

        sample_catalog(self.source, first, 5, seed=123)
        sample_catalog(self.source, second, 5, seed=123)

        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_rejects_invalid_size_and_existing_output(self) -> None:
        output = self.root / "sample.jsonl"
        output.write_text("do not overwrite\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "greater than zero"):
            sample_catalog(self.source, self.root / "zero.jsonl", 0, seed=1)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            sample_catalog(self.source, self.root / "large.jsonl", 11, seed=1)
        with self.assertRaises(FileExistsError):
            sample_catalog(self.source, output, 2, seed=1)
        self.assertEqual(output.read_text(encoding="utf-8"), "do not overwrite\n")

    def test_force_replaces_existing_output(self) -> None:
        output = self.root / "sample.jsonl"
        output.write_text("old content\n", encoding="utf-8")

        sample_catalog(self.source, output, 2, seed=1, overwrite=True)

        self.assertEqual(len(self.read_rows(output)), 2)


if __name__ == "__main__":
    unittest.main()
