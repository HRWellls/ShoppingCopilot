from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.retrieval.dense import DenseIndex, SentenceTransformerProvider


def ensure_model(model_id: str, model_path: Path) -> None:
    if model_path.exists() and any(model_path.iterdir()):
        return
    from sentence_transformers import SentenceTransformer

    model_path.parent.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(model_id)
    model.save(str(model_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the persistent 50,000-product FAISS index")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--model-id", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--model-path", default=".runtime/models/all-MiniLM-L6-v2")
    parser.add_argument("--index", default=".runtime/indexes/catalog-all-MiniLM-L6-v2.faiss")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    model_path, index_path = Path(args.model_path), Path(args.index)
    ensure_model(args.model_id, model_path)
    if args.force:
        index_path.unlink(missing_ok=True)
        DenseIndex.manifest_path(index_path).unlink(missing_ok=True)
    config = AgentConfig(
        catalog_path=Path(args.catalog), dense_enabled=True,
        dense_model_id=args.model_id, dense_model_path=model_path,
        dense_index_path=index_path, dense_batch_size=args.batch_size,
        dense_build_allowed=True,
    )
    started = time.perf_counter()
    catalog = CatalogStore(config)
    provider = SentenceTransformerProvider(model_path, args.model_id)
    dense = DenseIndex(catalog, config, provider)
    summary = {
        "catalog_records": catalog.record_count,
        "catalog_checksum": catalog.checksum,
        "index_path": str(index_path),
        "manifest_path": str(DenseIndex.manifest_path(index_path)),
        "model_id": provider.model_id,
        "dimension": provider.dimension,
        "backend": dense.backend,
        "loaded_from_disk": dense.loaded_from_disk,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
