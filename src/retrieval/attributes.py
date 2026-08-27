from __future__ import annotations

import re
from collections import OrderedDict, defaultdict

from src.catalog.store import CatalogStore
from src.models import Candidate, StructuredRetrievalRequest


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
QUERY_STOPWORDS = frozenset({
    "a", "about", "actually", "additional", "an", "and", "are", "as", "ask", "at",
    "attribute", "be", "but", "by", "do", "earlier", "for", "from", "have", "i",
    "ignore", "in", "is", "it", "looking", "matters", "me", "my", "need", "not",
    "of", "on", "one", "options", "or", "please", "preference", "preferences", "quite",
    "right", "some", "specific", "that", "the", "this", "those", "to", "want", "what",
    "with", "would", "yet", "you",
})
FIELD_WEIGHTS = {"category": 6.0, "brand": 5.0, "color": 4.0, "material": 4.0, "size": 4.0, "use_case": 3.0, "style": 3.0, "feature": 2.0, "title": 2.5}


def tokens(value: str) -> frozenset[str]:
    return frozenset(
        token.casefold()
        for token in TOKEN_RE.findall(value)
        if len(token) > 1 and token.casefold() not in QUERY_STOPWORDS
    )


class ExactAttributeIndex:
    def __init__(self, catalog: CatalogStore) -> None:
        self.catalog = catalog
        self._postings: dict[str, set[str]] = defaultdict(set)
        self._field_tokens: dict[str, dict[str, frozenset[str]]] = {}
        self._cache: OrderedDict[tuple[object, ...], tuple[Candidate, ...]] = OrderedDict()
        for product in catalog:
            fields = {
                "title": tokens(product.title),
                **{name: tokens(" ".join(product.attributes.get(name, ()))) for name in ("category", "brand", "color", "material", "size", "use_case", "style", "feature")},
            }
            self._field_tokens[product.parent_asin] = fields
            for value in set().union(*fields.values()):
                self._postings[value].add(product.parent_asin)

    def search(self, request: StructuredRetrievalRequest, k: int, subset: frozenset[str] | None) -> list[Candidate]:
        query_fields = request.field_terms()
        residual = tokens(" ".join((request.residual_query, *request.semantic_terms)))
        query_tokens = set(residual)
        for values in query_fields.values():
            query_tokens.update(tokens(" ".join(values)))
        cache_key = (request, min(k, 300), subset)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return list(cached)
        available = sorted(
            ((len(self._postings[token]), token) for token in query_tokens if token in self._postings),
            key=lambda item: (item[0], item[1]),
        )
        selective = [(count, token) for count, token in available if count <= 5_000][:12]
        if not selective:
            selective = available[:3]
        preliminary: defaultdict[str, float] = defaultdict(float)
        catalog_size = max(self.catalog.record_count, 1)
        for count, token in selective:
            rarity = 1.0 + (catalog_size / max(count, 1)) ** 0.25
            for asin in self._postings[token]:
                if subset is None or asin in subset:
                    preliminary[asin] += rarity
        candidate_ids = {
            asin for asin, _ in sorted(
                preliminary.items(),
                key=lambda item: (-item[1], self.catalog.require(item[0]).catalog_order, item[0]),
            )[:2_000]
        }
        scored: list[tuple[float, int, str, dict[str, float]]] = []
        for asin in candidate_ids:
            product = self.catalog.require(asin)
            fields = self._field_tokens[asin]
            evidence: dict[str, float] = {}
            score = 0.0
            for field, values in query_fields.items():
                expected = tokens(" ".join(values))
                matched = expected & fields.get(field, frozenset())
                if matched:
                    contribution = FIELD_WEIGHTS.get(field, 1.0) * len(matched) / max(len(expected), 1)
                    evidence[field] = contribution
                    score += contribution
            broad = residual & set().union(*fields.values())
            if broad:
                contribution = sum(
                    1.0 + (self.catalog.record_count / max(len(self._postings[token]), 1)) ** 0.25
                    for token in broad
                ) / max(len(residual), 1)
                evidence["residual"] = contribution
                score += contribution
            if score > 0:
                scored.append((score, -product.catalog_order, asin, evidence))
        scored.sort(reverse=True)
        result = tuple(Candidate(asin, score, {"attribute": score, **evidence}, {"attribute": rank}, ("attribute",)) for rank, (score, _, asin, evidence) in enumerate(scored[:k], 1))
        self._cache[cache_key] = result
        if len(self._cache) > 64:
            self._cache.popitem(last=False)
        return list(result)
