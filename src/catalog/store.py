from __future__ import annotations

from collections.abc import Iterator, Sequence
from types import MappingProxyType

from src.catalog.loader import load_catalog
from src.config import AgentConfig
from src.models import Product


class CatalogStore(Sequence[Product]):
    def __init__(self, config: AgentConfig) -> None:
        products, checksum = load_catalog(config)
        self._products = products
        self._by_id = MappingProxyType({product.parent_asin: product for product in products})
        self._ids = frozenset(self._by_id)
        self._checksum = checksum

    @property
    def checksum(self) -> str:
        return self._checksum

    @property
    def ids(self) -> frozenset[str]:
        return self._ids

    @property
    def record_count(self) -> int:
        return len(self._products)

    def get(self, parent_asin: str) -> Product | None:
        return self._by_id.get(parent_asin)

    def require(self, parent_asin: str) -> Product:
        return self._by_id[parent_asin]

    def attribute_values(self, parent_asin: str, name: str) -> frozenset[str]:
        product = self.require(parent_asin)
        return product.attributes.get(name, frozenset())

    def stable_ids(self, subset: set[str] | frozenset[str] | None = None) -> tuple[str, ...]:
        if subset is None:
            return tuple(product.parent_asin for product in self._products)
        return tuple(product.parent_asin for product in self._products if product.parent_asin in subset)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Product):
            return item.parent_asin in self._ids
        return isinstance(item, str) and item in self._ids

    def __getitem__(self, index: int | slice) -> Product | tuple[Product, ...]:
        return self._products[index]

    def __iter__(self) -> Iterator[Product]:
        return iter(self._products)

    def __len__(self) -> int:
        return len(self._products)
