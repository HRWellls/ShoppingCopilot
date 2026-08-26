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


@dataclass(frozen=True)
class RouteRetrievalPlan:
    route: str
    lexical_query: str
    dense_query: str
    filter_constraints: ConstraintSet
    dense_uses_subset: bool
    weights: tuple[float, float]
    diversity: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "route": self.route,
            "dense_uses_subset": self.dense_uses_subset,
            "diversity": self.diversity,
            "lexical_query_chars": len(self.lexical_query),
            "dense_query_chars": len(self.dense_query),
        }


def build_route_plan(state: SessionState, config: AgentConfig) -> RouteRetrievalPlan:
    route = state.intent
    active = state.active_constraints()
    slots = state.active_slots()
    structured = [
        str(value) for value in (
            active.category, active.brand, active.color, active.size, active.material
        ) if value
    ]
    semantic = [str(slots[name].value) for name in ("occasion", "use_case", "style") if name in slots]
    current = state.last_user_message or state.last_query
    if route == "buying":
        lexical = " ".join(dict.fromkeys([*structured, current])).strip()
        dense = lexical
        return RouteRetrievalPlan(route, lexical, dense, active, True, config.buying_weights[:2])
    boundary = ConstraintSet(
        price_min=active.price_min,
        price_max=active.price_max,
        exclusions=dict(active.exclusions),
    )
    if route == "browsing":
        lexical = " ".join(dict.fromkeys([*semantic, active.category or "", current])).strip()
        dense = " ".join(dict.fromkeys([*semantic, current])).strip()
        return RouteRetrievalPlan(route, lexical, dense, boundary, False, config.browsing_weights[:2], True)
    lexical = " ".join(dict.fromkeys([*semantic, active.category or "", current])).strip()
    dense = " ".join(dict.fromkeys([*semantic, current])).strip()
    return RouteRetrievalPlan("unknown", lexical, dense, active, False, (0.5, 0.5))


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
    plan: RouteRetrievalPlan | None = None


def diversify_candidates(candidates: list[Candidate], catalog: CatalogStore) -> list[Candidate]:
    remaining = list(candidates)
    result: list[Candidate] = []
    brand_counts: defaultdict[str, int] = defaultdict(int)
    category_counts: defaultdict[str, int] = defaultdict(int)
    title_counts: defaultdict[str, int] = defaultdict(int)
    while remaining:
        best_index = 0
        best_key: tuple[float, int, str] | None = None
        for index, candidate in enumerate(remaining):
            product = catalog.require(candidate.parent_asin)
            brand = product.brand_key or ""
            category = product.categories[-1].casefold() if product.categories else ""
            title = product.title.casefold()
            penalty = 0.08 * brand_counts[brand] + 0.05 * category_counts[category] + 0.15 * title_counts[title]
            key = (candidate.score * max(0.5, 1.0 - penalty), -index, candidate.parent_asin)
            if best_key is None or key > best_key:
                best_key = key
                best_index = index
        selected = remaining.pop(best_index)
        product = catalog.require(selected.parent_asin)
        brand_counts[product.brand_key or ""] += 1
        category_counts[product.categories[-1].casefold() if product.categories else ""] += 1
        title_counts[product.title.casefold()] += 1
        result.append(selected)
    return result


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
        plan = build_route_plan(state, self.config) if self.config.intent_routing_enabled else None
        applied_constraints = plan.filter_constraints if plan is not None else state.constraints
        subset, report = self.hard_filter.apply(applied_constraints)
        relaxation = RelaxationReport()
        if not subset and self.config.relaxation_enabled and (plan is None or plan.route == "buying"):
            for index, level in enumerate(("brand", "color_material", "category_synonym"), 1):
                changed = relaxed_constraints(applied_constraints, level)
                if changed.as_dict() == applied_constraints.as_dict():
                    continue
                relaxed_subset, relaxed_report = self.hard_filter.apply(changed)
                if relaxed_subset:
                    subset, report = relaxed_subset, relaxed_report
                    relaxation = RelaxationReport(index, level, "empty_hard_filter")
                    break
        lexical_query, dense_query = (
            (plan.lexical_query, plan.dense_query) if plan is not None else build_route_queries(state)
        )
        lexical = self.bm25.search(lexical_query, self.config.lexical_k, subset) if self.config.lexical_enabled else []
        lexical = [Candidate(c.parent_asin, c.score, {"lexical": c.score}, {"lexical": i}, ("lexical",)) for i, c in enumerate(lexical, 1)]
        dense_candidates: list[Candidate] = []
        dense_fallback = None
        if self.config.dense_enabled and self.dense is not None:
            try:
                dense_subset = subset if (plan.dense_uses_subset if plan is not None else state.intent == "buying") else None
                dense_candidates = self.dense.search(dense_query, self.config.dense_k, dense_subset)
            except AgentError as exc:
                dense_fallback = exc.code.value
        weights_tuple = plan.weights if plan is not None else (self.config.browsing_weights if state.intent == "browsing" else self.config.buying_weights)
        # Category and profile sources are introduced as explicit inputs in later ranking; Stage 3
        # fusion renormalizes the active lexical/dense paths.
        weights = {"lexical": weights_tuple[0], "dense": weights_tuple[1]}
        fused = fuse_rankings(
            {"lexical": lexical, "dense": dense_candidates},
            weights,
            self.config.k_rrf,
            self.config.fused_k,
        )
        if plan is not None and plan.diversity:
            fused = diversify_candidates(fused, self.catalog)
        return RetrievalResult(tuple(fused), report, relaxation, dense_fallback, plan)
