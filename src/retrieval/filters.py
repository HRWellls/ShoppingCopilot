from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable

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

    def apply(self, constraints: ConstraintSet) -> tuple[frozenset[str], FilterReport]:
        cache_key = tuple(constraints.as_dict().values())
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return cached
        current_products = list(self._catalog)
        steps: list[FilterStep] = []

        def apply_step(name: str, predicate: Callable[[Product], bool]) -> None:
            nonlocal current_products
            before = len(current_products)
            current_products = [product for product in current_products if predicate(product)]
            steps.append(FilterStep(name=name, before=before, after=len(current_products)))

        if constraints.price_min is not None:
            apply_step("price_min", lambda product: product.price is not None and product.price >= constraints.price_min)
        if constraints.price_max is not None:
            apply_step("price_max", lambda product: product.price is not None and product.price <= constraints.price_max)
        if constraints.category:
            apply_step(
                "category",
                lambda product: _contains_words(constraints.category or "", product.categories + (product.title,)),
            )
        if constraints.brand:
            brand_key = normalize_key(constraints.brand)
            apply_step("brand", lambda product: product.brand_key == brand_key)
        if constraints.color:
            color = "gray" if normalize_key(constraints.color) == "grey" else normalize_key(constraints.color)
            apply_step("color", lambda product: color in product.attributes["color"])
        if constraints.material:
            material = normalize_key(constraints.material)
            apply_step("material", lambda product: material in product.attributes["material"])
        if constraints.size:
            size = normalize_key(constraints.size)
            apply_step("size", lambda product: size in product.attributes["size"])

        report = FilterReport(
            initial_count=self._catalog.record_count,
            steps=tuple(steps),
            final_count=len(current_products),
        )
        result = frozenset(product.parent_asin for product in current_products)
        self._cache[cache_key] = (result, report)
        if len(self._cache) > self._cache_entries:
            self._cache.popitem(last=False)
        return result, report
