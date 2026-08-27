from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.errors import AgentError
from src.models import Candidate, ConstraintSet, FilterReport, RelaxationReport, SessionState, StructuredRetrievalRequest
from src.catalog.normalize import canonical_category
from src.retrieval.attributes import ExactAttributeIndex
from src.retrieval.rerank import RouteReranker
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
    request: StructuredRetrievalRequest | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "route": self.route,
            "dense_uses_subset": self.dense_uses_subset,
            "diversity": self.diversity,
            "lexical_query_chars": len(self.lexical_query),
            "dense_query_chars": len(self.dense_query),
            "hard_filter_count": len(self.request.hard_filters) if self.request else 0,
            "lexical_field_count": len(self.request.lexical_fields) if self.request else 0,
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
    state_changed = bool(set(state.last_event_kinds) & {"override", "clear", "negation", "intent_switch"})
    retained_history = state.history[state.retrieval_context_start:]
    history_context = [current] if state_changed else retained_history[-4:]
    semantic.extend(message for message in history_context if message and message != current)
    if config.override_invalidation_enabled:
        semantic.extend(state.query_evidence[slot] for slot in sorted(state.query_evidence))
    hard_filters: list[tuple[str, str | float]] = []
    for name in ("price_min", "price_max", "size", "brand", "color", "material", "category"):
        value = getattr(active, name)
        if value is not None:
            hard_filters.append((name, value))
    for name, values in sorted(active.exclusions.items()):
        hard_filters.extend((f"exclude_{name}", value) for value in sorted(values))
    lexical_values = {
        "category": (canonical_category(active.category),) if active.category else (),
        "brand": (str(active.brand),) if active.brand else (),
        "color": (str(active.color),) if active.color else (),
        "material": (str(active.material),) if active.material else (),
        "size": (str(active.size),) if active.size else (),
        "use_case": tuple(str(slots[name].value) for name in ("use_case",) if name in slots),
        "style": tuple(str(slots[name].value) for name in ("style",) if name in slots),
    }
    request = StructuredRetrievalRequest(
        route=route,
        hard_filters=tuple(hard_filters),
        lexical_fields=tuple((name, values) for name, values in lexical_values.items() if values),
        semantic_terms=tuple(semantic),
        residual_query=current,
        confidence=state.intent_confidence,
    )
    if route == "buying":
        lexical = " ".join(dict.fromkeys([*structured, current])).strip()
        dense = lexical
        return RouteRetrievalPlan(route, lexical, dense, active, True, config.buying_weights[:2], request=request)
    boundary = ConstraintSet(
        price_min=active.price_min,
        price_max=active.price_max,
        exclusions=dict(active.exclusions),
    )
    if route == "browsing":
        lexical = " ".join(dict.fromkeys([*semantic, active.category or "", current])).strip()
        dense = " ".join(dict.fromkeys([*semantic, current])).strip()
        return RouteRetrievalPlan(route, lexical, dense, boundary, False, config.browsing_weights[:2], True, request)
    lexical = " ".join(dict.fromkeys([*semantic, active.category or "", current])).strip()
    dense = " ".join(dict.fromkeys([*semantic, current])).strip()
    return RouteRetrievalPlan("unknown", lexical, dense, active, False, (0.5, 0.5), False, request)


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
    stages: dict[str, tuple[str, ...]] | None = None
    timings: dict[str, float] | None = None


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
        self.attributes = ExactAttributeIndex(catalog) if config.attribute_retrieval_enabled else None
        self.reranker = RouteReranker(catalog, config.cache_entries) if config.attribute_reranking_enabled else None

    def retrieve(self, state: SessionState) -> RetrievalResult:
        timings: dict[str, float] = {}
        started = perf_counter()
        plan = build_route_plan(state, self.config) if self.config.intent_routing_enabled else None
        applied_constraints = plan.filter_constraints if plan is not None else state.constraints
        subset, report = self.hard_filter.apply(applied_constraints)
        timings["filter_ms"] = (perf_counter() - started) * 1_000
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
        stage_started = perf_counter()
        lexical = (
            self.bm25.search(lexical_query, self.config.lexical_k, subset)
            if self.config.lexical_enabled and not self.config.optimized_single_pass_enabled
            else []
        )
        timings["lexical_ms"] = (perf_counter() - stage_started) * 1_000
        stage_started = perf_counter()
        structured_lexical = (
            self.bm25.search_structured(plan.request, self.config.lexical_k, subset)
            if self.config.lexical_enabled
            and not self.config.optimized_single_pass_enabled
            and plan is not None and plan.request is not None and self.config.attribute_retrieval_enabled
            else []
        )
        timings["structured_ms"] = (perf_counter() - stage_started) * 1_000
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
        b3_fused = list(fused)
        attribute_candidates: list[Candidate] = []
        raw_union: list[Candidate] = list(b3_fused)
        reranked_all: list[Candidate] = []
        if self.attributes is not None and plan is not None and plan.request is not None:
            stage_started = perf_counter()
            attribute_subset = subset if plan.route == "buying" else None
            attribute_candidates = self.attributes.search(plan.request, self.config.lexical_k, attribute_subset)
            timings["attribute_ms"] = (perf_counter() - stage_started) * 1_000
            ordered_sources = [*b3_fused, *structured_lexical, *attribute_candidates]
            expanded: list[Candidate] = []
            existing: set[str] = set()
            for candidate in ordered_sources:
                if candidate.parent_asin not in existing:
                    expanded.append(candidate)
                    existing.add(candidate.parent_asin)
            raw_union = expanded
            if self.reranker is not None:
                stage_started = perf_counter()
                reranked_all = self.reranker.rank(
                    plan.request,
                    {
                        "lexical": lexical,
                        "structured": structured_lexical,
                        "attribute": attribute_candidates,
                        "dense": dense_candidates,
                    },
                    subset,
                    len(raw_union),
                )
                timings["rerank_ms"] = (perf_counter() - stage_started) * 1_000
                fused = reranked_all[: self.config.fused_k]
        stages = {
            "lexical": tuple(item.parent_asin for item in lexical),
            "structured_lexical": tuple(item.parent_asin for item in structured_lexical),
            "dense": tuple(item.parent_asin for item in dense_candidates),
            "attribute": tuple(item.parent_asin for item in attribute_candidates),
            "raw_channel_union": tuple(item.parent_asin for item in raw_union),
            "b3_fused": tuple(item.parent_asin for item in b3_fused),
            "reranked": tuple(item.parent_asin for item in reranked_all),
            "fused": tuple(item.parent_asin for item in fused),
        }
        timings["total_ms"] = (perf_counter() - started) * 1_000
        return RetrievalResult(tuple(fused), report, relaxation, dense_fallback, plan, stages, timings)
