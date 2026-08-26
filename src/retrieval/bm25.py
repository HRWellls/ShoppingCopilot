from __future__ import annotations

import re
import sqlite3
from collections import OrderedDict
from collections.abc import Collection

from src.catalog.normalize import clean_text
from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import Candidate


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "i", "in", "is", "it", "me", "my", "of", "on", "or", "please", "some", "that", "the", "this", "to", "want", "with", "would", "you", "looking"}
)


def query_terms(query: str, limit: int) -> tuple[str, ...]:
    tokens = (
        token.casefold()
        for token in TOKEN_RE.findall(query)
        if len(token) > 1 and token.casefold() not in STOPWORDS
    )
    return tuple(dict.fromkeys(tokens))[:limit]


class BM25Index:
    def __init__(self, catalog: CatalogStore, config: AgentConfig) -> None:
        self._catalog = catalog
        self._config = config
        self.connection = sqlite3.connect(":memory:")
        self.build_count = 0
        self._cache: OrderedDict[
            tuple[str, int, frozenset[str] | None], tuple[Candidate, ...]
        ] = OrderedDict()
        self._build()

    def _build(self) -> None:
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "CREATE VIRTUAL TABLE products USING fts5("
                "parent_asin UNINDEXED, catalog_order UNINDEXED, title, categories, features, "
                "details, store, description, tokenize='unicode61 remove_diacritics 2')"
            )
            batch: list[tuple[str, int, str, str, str, str, str, str]] = []
            for product in self._catalog:
                raw_details = product.metadata.get("details") or {}
                details = clean_text(dict(raw_details) if hasattr(raw_details, "items") else raw_details)
                batch.append(
                    (
                        product.parent_asin,
                        product.catalog_order,
                        product.title,
                        " ".join(product.categories),
                        " ".join(product.features),
                        details,
                        product.brand or "",
                        product.description,
                    )
                )
                if len(batch) >= 1_000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
            if batch:
                cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch)
            self.connection.commit()
            self.build_count += 1
        except sqlite3.Error as exc:
            self.connection.close()
            raise AgentError(ErrorCode.INDEX_NOT_READY, "SQLite FTS5 index could not be built") from exc

    def search(
        self,
        query: str,
        k: int,
        subset: Collection[str] | None = None,
    ) -> list[Candidate]:
        if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
            raise AgentError(ErrorCode.RETRIEVAL, "k must be a positive integer")
        bounded_k = min(k, self._config.retrieval_limit)
        valid_subset = None if subset is None else frozenset(value for value in subset if value in self._catalog)
        if valid_subset is not None and not valid_subset:
            return []
        terms = query_terms(query, self._config.query_token_limit)
        normalized_query = " ".join(terms)
        cache_key = (normalized_query, bounded_k, valid_subset)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return list(cached)
        if not terms:
            result = tuple(
                Candidate(parent_asin=value, score=0.0)
                for value in self._catalog.stable_ids(valid_subset)[:bounded_k]
            )
            self._remember(cache_key, result)
            return list(result)
        expression = " OR ".join(f'"{term}"' for term in terms)
        try:
            if valid_subset is None:
                rows = self.connection.execute(
                    "SELECT parent_asin, bm25(products, 0.0, 0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0) AS score "
                    "FROM products WHERE products MATCH ? ORDER BY score ASC, catalog_order ASC LIMIT ?",
                    (expression, bounded_k),
                ).fetchall()
                result = tuple(Candidate(parent_asin=str(row[0]), score=-float(row[1])) for row in rows)
            else:
                cursor = self.connection.cursor()
                rows = cursor.execute(
                    "SELECT parent_asin, "
                    "bm25(products, 0.0, 0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0) AS score "
                    "FROM products WHERE products MATCH ? ORDER BY score ASC, catalog_order ASC",
                    (expression,),
                )
                selected: list[Candidate] = []
                for row in rows:
                    parent_asin = str(row[0])
                    if parent_asin not in valid_subset:
                        continue
                    selected.append(Candidate(parent_asin=parent_asin, score=-float(row[1])))
                    if len(selected) >= bounded_k:
                        break
                result = tuple(selected)
            self._remember(cache_key, result)
            return list(result)
        except sqlite3.Error as exc:
            raise AgentError(ErrorCode.RETRIEVAL, "BM25 query failed") from exc

    def close(self) -> None:
        self.connection.close()

    def _remember(
        self,
        key: tuple[str, int, frozenset[str] | None],
        value: tuple[Candidate, ...],
    ) -> None:
        self._cache[key] = value
        if len(self._cache) > self._config.cache_entries:
            self._cache.popitem(last=False)
