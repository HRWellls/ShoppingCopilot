from __future__ import annotations

import json
import os
from collections import OrderedDict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import Candidate

# macOS wheels for FAISS and PyTorch can load separate OpenMP runtimes.
# Allow the process to continue while keeping dense inference single-process.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]

try:
    import faiss
    faiss.omp_set_num_threads(1)
except ImportError:  # pragma: no cover
    faiss = None  # type: ignore[assignment]


class EmbeddingProvider(Protocol):
    model_id: str
    model_version: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> "np.ndarray": ...


class SentenceTransformerProvider:
    def __init__(self, model_path: Path, model_id: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(str(model_path), local_files_only=True)
        except Exception as exc:
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "local embedding model is unavailable") from exc
        self.model_id = model_id
        self.model_version = str(model_path.resolve())
        dimension_getter = getattr(self._model, "get_embedding_dimension", None)
        self.dimension = int(dimension_getter() if dimension_getter else self._model.get_sentence_embedding_dimension())

    def embed(self, texts: Sequence[str]) -> "np.ndarray":
        try:
            return self._model.encode(
                list(texts),
                batch_size=min(128, max(1, len(texts))),
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "embedding inference failed") from exc


@dataclass(frozen=True)
class DenseManifest:
    catalog_checksum: str
    model_id: str
    model_version: str
    dimension: int
    dtype: str
    normalization_version: str
    config_version: str
    record_count: int
    backend: str

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


def _normalize(matrix: "np.ndarray") -> "np.ndarray":
    values = np.ascontiguousarray(np.asarray(matrix, dtype=np.float32))
    if values.ndim != 2:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "embedding output must be a matrix")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms == 0) or not np.all(np.isfinite(values)):
        raise AgentError(ErrorCode.MODEL_OUTPUT, "embedding output contains invalid vectors")
    return np.ascontiguousarray(values / norms, dtype=np.float32)


class DenseIndex:
    NORMALIZATION_VERSION = "l2-v1"

    def __init__(self, catalog: CatalogStore, config: AgentConfig, provider: EmbeddingProvider) -> None:
        if np is None:
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "NumPy is required for dense retrieval")
        self.catalog = catalog
        self.config = config
        self.provider = provider
        self.ids = catalog.stable_ids()
        self.cache_hits = 0
        self._cache: OrderedDict[tuple[str, int, frozenset[str] | None], tuple[Candidate, ...]] = OrderedDict()
        self.backend = "faiss-flat-ip" if faiss is not None else "numpy-flat-ip"
        self.manifest = self._expected_manifest()
        self.index = None
        self.matrix = None
        self.loaded_from_disk = self._load(config.dense_index_path)
        if not self.loaded_from_disk:
            if not config.dense_build_allowed:
                raise AgentError(
                    ErrorCode.INDEX_NOT_READY,
                    "dense index is missing or its manifest does not match; run scripts.build_dense_index",
                )
            self._build()
            self._save(config.dense_index_path)

    @staticmethod
    def manifest_path(index_path: Path) -> Path:
        return index_path.with_suffix(index_path.suffix + ".manifest.json")

    def _expected_manifest(self) -> DenseManifest:
        return DenseManifest(
            catalog_checksum=self.catalog.checksum,
            model_id=self.provider.model_id,
            model_version=self.provider.model_version,
            dimension=self.provider.dimension,
            dtype="float32",
            normalization_version=self.NORMALIZATION_VERSION,
            config_version=self.config.config_version,
            record_count=self.catalog.record_count,
            backend=self.backend,
        )

    def _build(self) -> None:
        products = list(self.catalog)
        chunks = []
        if self.backend == "faiss-flat-ip":
            self.index = faiss.IndexFlatIP(self.provider.dimension)
        for start in range(0, len(products), self.config.dense_batch_size):
            texts = [product.searchable_text for product in products[start:start + self.config.dense_batch_size]]
            try:
                vectors = _normalize(self.provider.embed(texts))
            except AgentError:
                raise
            except Exception as exc:
                raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "catalog embedding failed") from exc
            if vectors.shape[1] != self.provider.dimension:
                raise AgentError(ErrorCode.MODEL_OUTPUT, "embedding dimensions do not match provider")
            if self.index is not None:
                self.index.add(vectors)
            else:
                chunks.append(vectors)
        if self.index is not None:
            if self.index.ntotal != self.catalog.record_count:
                raise AgentError(ErrorCode.MODEL_OUTPUT, "FAISS record count does not match catalog")
        else:
            self.matrix = np.vstack(chunks) if chunks else np.empty((0, self.provider.dimension), dtype=np.float32)
            if self.matrix.shape != (self.catalog.record_count, self.provider.dimension):
                raise AgentError(ErrorCode.MODEL_OUTPUT, "embedding dimensions do not match manifest")

    def search(self, query: str, k: int, subset: Collection[str] | None = None) -> list[Candidate]:
        if k <= 0:
            return []
        valid_subset = None if subset is None else frozenset(value for value in subset if value in self.catalog)
        key = (query.casefold().strip(), min(k, self.config.dense_k), valid_subset)
        if key in self._cache:
            self.cache_hits += 1
            self._cache.move_to_end(key)
            return list(self._cache[key])
        try:
            vector = _normalize(self.provider.embed([query]))
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "dense query embedding failed") from exc
        selected = self._faiss_search(vector, key[1], valid_subset) if self.index is not None else self._numpy_search(vector[0], key[1], valid_subset)
        result = tuple(selected)
        self._cache[key] = result
        if len(self._cache) > self.config.cache_entries:
            self._cache.popitem(last=False)
        return list(result)

    def _faiss_search(self, vector: "np.ndarray", k: int, subset: frozenset[str] | None) -> list[Candidate]:
        fetch = min(self.catalog.record_count, max(k, 1024 if subset is not None else k))
        while True:
            scores, indices = self.index.search(vector, fetch)
            selected = self._select(scores[0], indices[0], k, subset)
            if len(selected) >= k or fetch >= self.catalog.record_count:
                return selected
            fetch = min(self.catalog.record_count, fetch * 2)

    def _numpy_search(self, vector: "np.ndarray", k: int, subset: frozenset[str] | None) -> list[Candidate]:
        scores = self.matrix @ vector
        indices = np.argsort(-scores, kind="stable")
        return self._select(scores[indices], indices, k, subset)

    def _select(self, scores: Sequence[float], indices: Sequence[int], k: int, subset: frozenset[str] | None) -> list[Candidate]:
        selected = []
        for raw_score, raw_index in zip(scores, indices):
            index = int(raw_index)
            if index < 0:
                continue
            parent_asin = self.ids[index]
            if subset is not None and parent_asin not in subset:
                continue
            score = float(raw_score)
            selected.append(Candidate(parent_asin, score, {"dense": score}, {"dense": len(selected) + 1}, ("dense",)))
            if len(selected) >= k:
                break
        return selected

    def _load(self, path: Path) -> bool:
        manifest_path = self.manifest_path(path)
        if not path.exists() or not manifest_path.exists():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest != self.manifest.as_dict():
                return False
            if self.backend == "faiss-flat-ip":
                self.index = faiss.read_index(str(path))
                return self.index.d == self.provider.dimension and self.index.ntotal == self.catalog.record_count
            with np.load(path, allow_pickle=False) as payload:
                self.matrix = np.asarray(payload["matrix"], dtype=np.float32)
            return self.matrix.shape == (self.catalog.record_count, self.provider.dimension)
        except Exception:
            self.index = None
            self.matrix = None
            return False

    def _save(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if self.index is not None:
                temp = path.with_suffix(path.suffix + ".tmp")
                faiss.write_index(self.index, str(temp))
                temp.replace(path)
            else:
                with path.open("wb") as handle:
                    np.savez_compressed(handle, matrix=self.matrix)
            self.manifest_path(path).write_text(
                json.dumps(self.manifest.as_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise AgentError(ErrorCode.INDEX_NOT_READY, "dense index could not be persisted") from exc
