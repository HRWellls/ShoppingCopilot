from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.errors import AgentError
from src.models import Candidate, ConstraintSet, FilterReport, RelaxationReport, SessionState
from src.retrieval.bm25 import BM25Index
from src.retrieval.dense import DenseIndex
from src.retrieval.filters import HardFilter


CATEGORY_SYNONYMS = {
    "running shoes": "shoes",
    "sneakers": "shoes",
    "winter boots": "boots",
    "casual shirts": "shirts",
}


def build_route_queries(state: SessionState) -> tuple[str, str]:
    c = state.constraints
    structured = [str(value) for value in (c.category, c.brand, c.color, c.size, c.material) if value]
    lexical = " ".join(structured + ([state.last_query] if state.last_query else []))
    if state.intent == "browsing":
        dense = state.last_query or " ".join(state.history[-2:])
    else:
        dense = " ".join(structured + ([state.last_query] if state.last_query else []))
    return lexical.strip(), dense.strip()


def fuse_rankings(
    rankings: dict[str, list[Candidate]],
    weights: dict[str, float],
    k_rrf: int,
    limit: int,
) -> list[Candidate]:
    active = {name: weight for name, weight in weights.items() if weight > 0 and rankings.get(name)}
    total = sum(active.values())
    if not total:
        return []
    normalized_weights = {name: value / total for name, value in active.items()}
    scores: defaultdict[str, float] = defaultdict(float)
    source_scores: defaultdict[str, dict[str, float]] = defaultdict(dict)
    source_ranks: defaultdict[str, dict[str, int]] = defaultdict(dict)
    first_seen: dict[str, int] = {}
    sequence = 0
    for source, candidates in rankings.items():
        if source not in normalized_weights:
            continue
        for rank, candidate in enumerate(candidates, 1):
            first_seen.setdefault(candidate.parent_asin, sequence)
            sequence += 1
            contribution = normalized_weights[source] / (k_rrf + rank)
            scores[candidate.parent_asin] += contribution
            source_scores[candidate.parent_asin][source] = candidate.score
            source_ranks[candidate.parent_asin][source] = rank
    ordered = sorted(scores, key=lambda asin: (-scores[asin], first_seen[asin], asin))[:limit]
    return [
        Candidate(
            parent_asin=asin,
            score=scores[asin],
            source_scores=source_scores[asin],
            source_ranks=source_ranks[asin],
            sources=tuple(sorted(source_scores[asin])),
        )
        for asin in ordered
    ]


def relaxed_constraints(constraints: ConstraintSet, level: str) -> ConstraintSet:
    result = constraints.copy()
    if level == "brand":
        result.brand = None
    elif level == "color_material":
        result.color = None
        result.material = None
    elif level == "category_synonym" and result.category:
        result.category = CATEGORY_SYNONYMS.get(result.category.casefold(), result.category)
    return result


@dataclass(frozen=True)
class RetrievalResult:
    candidates: tuple[Candidate, ...]
    filter_report: FilterReport
    relaxation: RelaxationReport
    dense_fallback: str | None = None


class HybridRetriever:
    def __init__(
        self,
        catalog: CatalogStore,
        config: AgentConfig,
        bm25: BM25Index,
        hard_filter: HardFilter,
        dense: DenseIndex | None = None,
    ) -> None:
        self.catalog = catalog
        self.config = config
        self.bm25 = bm25
        self.hard_filter = hard_filter
        self.dense = dense

    def retrieve(self, state: SessionState) -> RetrievalResult:
        subset, report = self.hard_filter.apply(state.constraints)
        relaxation = RelaxationReport()
        if not subset and self.config.relaxation_enabled:
            for index, level in enumerate(("brand", "color_material", "category_synonym"), 1):
                changed = relaxed_constraints(state.constraints, level)
                if changed.as_dict() == state.constraints.as_dict():
                    continue
                relaxed_subset, relaxed_report = self.hard_filter.apply(changed)
                if relaxed_subset:
                    subset, report = relaxed_subset, relaxed_report
                    relaxation = RelaxationReport(index, level, "empty_hard_filter")
                    break
        lexical_query, dense_query = build_route_queries(state)
        lexical = self.bm25.search(lexical_query, self.config.lexical_k, subset) if self.config.lexical_enabled else []
        lexical = [Candidate(c.parent_asin, c.score, {"lexical": c.score}, {"lexical": i}, ("lexical",)) for i, c in enumerate(lexical, 1)]
        dense_candidates: list[Candidate] = []
        dense_fallback = None
        if self.config.dense_enabled and self.dense is not None:
            try:
                dense_subset = subset if state.intent == "buying" else None
                dense_candidates = self.dense.search(dense_query, self.config.dense_k, dense_subset)
            except AgentError as exc:
                dense_fallback = exc.code.value
        weights_tuple = self.config.browsing_weights if state.intent == "browsing" else self.config.buying_weights
        # Category and profile sources are introduced as explicit inputs in later ranking; Stage 3
        # fusion renormalizes the active lexical/dense paths.
        weights = {"lexical": weights_tuple[0], "dense": weights_tuple[1]}
        fused = fuse_rankings(
            {"lexical": lexical, "dense": dense_candidates},
            weights,
            self.config.k_rrf,
            self.config.fused_k,
        )
        return RetrievalResult(tuple(fused), report, relaxation, dense_fallback)
