from __future__ import annotations

import math
from collections import OrderedDict, defaultdict

from src.catalog.normalize import normalize_key
from src.catalog.store import CatalogStore
from src.models import Candidate, StructuredRetrievalRequest
from src.retrieval.attributes import tokens


SOURCE_WEIGHTS = {"lexical": 1.0, "structured": 1.1, "attribute": 1.2, "dense": 0.25}
ROUTE_FIELD_WEIGHTS = {
    "buying": {"category": 8.0, "brand": 8.0, "color": 7.0, "material": 7.0, "size": 8.0, "use_case": 3.0, "style": 2.0},
    "browsing": {"category": 8.0, "brand": 2.0, "color": 2.0, "material": 3.0, "size": 1.0, "use_case": 8.0, "style": 8.0},
    "unknown": {"category": 8.0, "brand": 3.0, "color": 2.0, "material": 2.0, "size": 2.0, "use_case": 3.0, "style": 3.0},
}


class RouteReranker:
    def __init__(self, catalog: CatalogStore, cache_entries: int = 64) -> None:
        self.catalog = catalog
        self.cache_entries = cache_entries
        self._cache: OrderedDict[tuple[object, ...], tuple[Candidate, ...]] = OrderedDict()
        self._fields: dict[str, dict[str, frozenset[str]]] = {}
        self._feature_text: dict[str, tuple[str, ...]] = {}
        document_frequency: defaultdict[str, int] = defaultdict(int)
        for product in catalog:
            self._feature_text[product.parent_asin] = tuple(
                normalize_key(value) for value in product.features if normalize_key(value)
            )
            self._fields[product.parent_asin] = {
                "title": tokens(product.title),
                "category": tokens(" ".join(product.attributes.get("category", ()))),
                "brand": tokens(" ".join(product.attributes.get("brand", ()))),
                "color": tokens(" ".join(product.attributes.get("color", ()))),
                "material": tokens(" ".join(product.attributes.get("material", ()))),
                "size": frozenset(normalize_key(value) for value in product.attributes.get("size", ())),
                "use_case": tokens(" ".join(product.attributes.get("use_case", ()))),
                "style": tokens(" ".join(product.attributes.get("style", ()))),
                "feature": tokens(" ".join(product.attributes.get("feature", ()))),
                "all": tokens(product.searchable_text),
            }
            for token in self._fields[product.parent_asin]["all"]:
                document_frequency[token] += 1
        size = max(catalog.record_count, 1)
        self._idf = {
            token: math.log((size + 1) / (frequency + 1)) + 1.0
            for token, frequency in document_frequency.items()
        }

    def rank(
        self,
        request: StructuredRetrievalRequest,
        rankings: dict[str, list[Candidate]],
        eligible: frozenset[str],
        limit: int,
    ) -> list[Candidate]:
        ranking_key = tuple((name, tuple(item.parent_asin for item in values)) for name, values in sorted(rankings.items()))
        cache_key = (request, ranking_key, eligible, limit)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return list(cached)

        source_ranks: defaultdict[str, dict[str, int]] = defaultdict(dict)
        source_scores: defaultdict[str, dict[str, float]] = defaultdict(dict)
        first_seen: dict[str, int] = {}
        sequence = 0
        for source, candidates in rankings.items():
            for rank, candidate in enumerate(candidates, 1):
                if candidate.parent_asin not in eligible:
                    continue
                first_seen.setdefault(candidate.parent_asin, sequence)
                sequence += 1
                source_ranks[candidate.parent_asin][source] = rank
                source_scores[candidate.parent_asin][source] = candidate.score

        request_fields = request.field_terms()
        residual = tokens(request.residual_query)
        semantic = tokens(" ".join(request.semantic_terms))
        scored: list[tuple[float, int, str, Candidate]] = []
        for asin, ranks in source_ranks.items():
            fields = self._fields[asin]
            contributions: dict[str, float] = {"eligible": 1.0}
            score = 100.0

            source_rank_score = sum(
                SOURCE_WEIGHTS.get(source, 0.5)
                * (1.8 if request.route == "buying" and source == "attribute" else 1.0)
                * (1.0 - (rank - 1) / 300.0)
                for source, rank in ranks.items()
            )
            contributions["source_rank"] = source_rank_score
            score += source_rank_score

            attribute_rank = ranks.get("attribute")
            if request.route == "buying" and attribute_rank is not None and attribute_rank <= 5:
                attribute_top_rank = 0.9 * (6 - attribute_rank) / 5
                contributions["attribute_top_rank"] = attribute_top_rank
                score += attribute_top_rank

            exact_total = 0.0
            exact_matched = 0.0
            for field, values in request_fields.items():
                weight = ROUTE_FIELD_WEIGHTS[request.route].get(field, 1.0)
                expected = (
                    frozenset(normalize_key(value) for value in values)
                    if field == "size"
                    else tokens(" ".join(values))
                )
                if not expected:
                    continue
                exact_total += weight
                overlap = expected & fields.get(field, frozenset())
                ratio = len(overlap) / len(expected)
                if ratio:
                    contribution = weight * ratio
                    contributions[f"field_{field}"] = contribution
                    exact_matched += contribution
                    score += contribution
            if exact_total:
                completeness = exact_matched / exact_total
                bonus = completeness * (12.0 if request.route == "buying" else 5.0)
                contributions["field_completeness"] = bonus
                score += bonus

            title_overlap = self._weighted_overlap(residual, fields["title"])
            category_overlap = self._weighted_overlap(residual | semantic, fields["category"])
            feature_overlap = self._weighted_overlap(residual | semantic, fields["feature"])
            context_overlap = self._weighted_overlap(residual | semantic, fields["all"])
            title_weight = 8.0 if request.route in {"buying", "unknown"} else 4.0
            category_weight = 18.0
            feature_weight = 9.0 if request.route == "buying" else 6.0
            context_weight = 4.0 if request.route == "buying" else 9.0
            for name, contribution in (
                ("title_overlap", title_overlap * title_weight),
                ("category_overlap", category_overlap * category_weight),
                ("feature_overlap", feature_overlap * feature_weight),
                ("context_overlap", context_overlap * context_weight),
            ):
                if contribution:
                    contributions[name] = contribution
                    score += contribution

            exact_phrase = self._exact_phrase_score(asin, (request.residual_query, *request.semantic_terms))
            if exact_phrase:
                contributions["exact_phrase"] = exact_phrase
                score += exact_phrase

            product = self.catalog.require(asin)
            candidate = Candidate(
                asin,
                score,
                {**source_scores[asin], **contributions},
                dict(ranks),
                tuple(sorted(ranks)),
            )
            scored.append((score, -first_seen[asin], asin, candidate))

        scored.sort(key=lambda item: (-item[0], -item[1], self.catalog.require(item[2]).catalog_order, item[2]))
        candidates = [item[3] for item in scored]
        if request.route == "browsing":
            candidates = self._diversify_within_relevance_band(candidates)
        result = tuple(
            Candidate(
                candidate.parent_asin,
                candidate.score / 10_000.0,
                {**candidate.source_scores, "rerank_total": candidate.score},
                candidate.source_ranks,
                candidate.sources,
            )
            for candidate in candidates[:limit]
        )
        self._cache[cache_key] = result
        if len(self._cache) > self.cache_entries:
            self._cache.popitem(last=False)
        return list(result)

    def _weighted_overlap(self, query: frozenset[str], field: frozenset[str]) -> float:
        if not query:
            return 0.0
        denominator = sum(self._idf.get(token, 1.0) for token in query)
        matched = sum(self._idf.get(token, 1.0) for token in query & field)
        return matched / max(denominator, 1.0)

    def _exact_phrase_score(self, asin: str, evidence: tuple[str, ...]) -> float:
        phrases: set[str] = set()
        for value in evidence:
            for part in value.split(";"):
                normalized = normalize_key(part)
                if normalized.startswith("for that") and ":" in normalized:
                    normalized = normalized.split(":", 1)[1].strip()
                phrase_tokens = tokens(normalized)
                if len(phrase_tokens) >= 2:
                    phrases.add(normalized)
        score = 0.0
        for phrase in phrases:
            if any(phrase in feature or feature in phrase for feature in self._feature_text[asin]):
                phrase_tokens = tokens(phrase)
                information = sum(self._idf.get(token, 1.0) for token in phrase_tokens)
                score += min(20.0, 5.0 + information / 2.0)
        return score

    def _diversify_within_relevance_band(self, candidates: list[Candidate]) -> list[Candidate]:
        output: list[Candidate] = []
        brand_counts: defaultdict[str, int] = defaultdict(int)
        index = 0
        while index < len(candidates):
            band = round(candidates[index].score, 1)
            end = index + 1
            while end < len(candidates) and round(candidates[end].score, 1) == band:
                end += 1
            group = candidates[index:end]
            group.sort(
                key=lambda candidate: (
                    brand_counts[self.catalog.require(candidate.parent_asin).brand_key or ""],
                    self.catalog.require(candidate.parent_asin).catalog_order,
                    candidate.parent_asin,
                )
            )
            for candidate in group:
                brand_counts[self.catalog.require(candidate.parent_asin).brand_key or ""] += 1
                output.append(candidate)
            index = end
        return output
