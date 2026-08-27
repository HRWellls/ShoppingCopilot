from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from collections import OrderedDict
from collections import defaultdict

from src.catalog.normalize import normalize_key
from src.catalog.store import CatalogStore
from src.models import ConstraintSet, FilterReport, FilterStep, Product


WORD_RE = re.compile(r"[a-z0-9]+")


def _contains_words(value: str, texts: tuple[str, ...]) -> bool:
    required = set(WORD_RE.findall(normalize_key(value)))
    available = set(WORD_RE.findall(normalize_key(" ".join(texts))))
    return bool(required) and required.issubset(available)


class HardFilter:
    def __init__(self, catalog: CatalogStore, cache_entries: int = 64) -> None:
        self._catalog = catalog
        self._cache_entries = cache_entries
        self._cache: OrderedDict[
            tuple[object, ...], tuple[frozenset[str], FilterReport]
        ] = OrderedDict()
        self._all_ids = frozenset(product.parent_asin for product in catalog)
        self._postings: dict[tuple[str, str], set[str]] = defaultdict(set)
        priced: list[tuple[float, str]] = []
        for product in catalog:
            asin = product.parent_asin
            if product.price is not None:
                priced.append((product.price, asin))
            if product.brand_key:
                self._postings[("brand", product.brand_key)].add(asin)
            for field in ("color", "material", "category", "size"):
                for value in product.attributes.get(field, frozenset()):
                    self._postings[(field, normalize_key(value))].add(asin)
            category_text = normalize_key(" ".join(product.categories + (product.title,)))
            for token in set(WORD_RE.findall(category_text)):
                self._postings[("category_token", token)].add(asin)
        priced.sort()
        self._priced = tuple(priced)
        self._price_values = tuple(value for value, _ in priced)

    def apply(self, constraints: ConstraintSet) -> tuple[frozenset[str], FilterReport]:
        cache_key = tuple(constraints.as_dict().values()) + tuple(
            (name, tuple(sorted(values))) for name, values in sorted(constraints.exclusions.items())
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return cached
        current = set(self._all_ids)
        steps: list[FilterStep] = []

        def apply_ids(name: str, eligible: set[str] | frozenset[str]) -> None:
            before = len(current)
            current.intersection_update(eligible)
            steps.append(FilterStep(name=name, before=before, after=len(current)))

        if constraints.price_min is not None:
            index = bisect_left(self._price_values, constraints.price_min)
            apply_ids("price_min", {asin for _, asin in self._priced[index:]})
        if constraints.price_max is not None:
            index = bisect_right(self._price_values, constraints.price_max)
            apply_ids("price_max", {asin for _, asin in self._priced[:index]})
        if constraints.category:
            required = set(WORD_RE.findall(normalize_key(constraints.category)))
            eligible = set(self._all_ids)
            for token in required:
                eligible.intersection_update(self._postings.get(("category_token", token), set()))
            apply_ids("category", eligible if required else set())
        if constraints.brand:
            brand_key = normalize_key(constraints.brand)
            apply_ids("brand", self._postings.get(("brand", brand_key), set()))
        if constraints.color:
            color = "gray" if normalize_key(constraints.color) == "grey" else normalize_key(constraints.color)
            apply_ids("color", self._postings.get(("color", color), set()))
        if constraints.material:
            material = normalize_key(constraints.material)
            apply_ids("material", self._postings.get(("material", material), set()))
        if constraints.size:
            size = normalize_key(constraints.size)
            apply_ids("size", self._postings.get(("size", size), set()))
        for name, values in sorted(constraints.exclusions.items()):
            if name not in {"brand", "color", "material", "category", "size"} or not values:
                continue
            normalized = frozenset(normalize_key(value) for value in values)
            blocked: set[str] = set()
            for value in normalized:
                blocked.update(self._postings.get((name, value), set()))
            before = len(current)
            current.difference_update(blocked)
            steps.append(FilterStep(name=f"exclude_{name}", before=before, after=len(current)))

        report = FilterReport(
            initial_count=self._catalog.record_count,
            steps=tuple(steps),
            final_count=len(current),
        )
        result = frozenset(current)
        self._cache[cache_key] = (result, report)
        if len(self._cache) > self._cache_entries:
            self._cache.popitem(last=False)
        return result, report
