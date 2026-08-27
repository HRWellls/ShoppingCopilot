from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping

from src.catalog.normalize import (
    COLORS,
    MATERIALS,
    STYLES,
    USE_CASES,
    canonical_category,
    clean_text,
    extract_sizes,
    normalize_collection,
    normalize_key,
    parse_price,
    price_bucket,
    token_values,
)
from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import Product


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _product_from_record(record: Mapping[str, Any], order: int, config: AgentConfig) -> Product:
    parent_asin = clean_text(record.get("parent_asin"))
    if not parent_asin:
        raise AgentError(ErrorCode.CATALOG, f"catalog row {order + 1} has no parent_asin")

    title = clean_text(record.get("title"))
    categories = normalize_collection(record.get("categories"))
    brand = clean_text(record.get("store")) or None
    features = normalize_collection(record.get("features"))
    description = clean_text(record.get("description"), config.description_max_chars)
    details = normalize_collection(record.get("details"))
    attribute_source = (title, *categories, *features, description, *details)
    colors = frozenset("gray" if value == "grey" else value for value in token_values(attribute_source, COLORS))
    materials = token_values(attribute_source, MATERIALS)
    sizes = extract_sizes(attribute_source)
    parsed_price = parse_price(record.get("price"))
    attributes = MappingProxyType(
        {
            "color": colors,
            "material": materials,
            "size": sizes,
            "category": frozenset(canonical_category(item) for item in categories if item),
            "brand": frozenset({normalize_key(brand)}) if brand else frozenset(),
            "use_case": token_values(attribute_source, USE_CASES),
            "style": token_values(attribute_source, STYLES),
            "feature": frozenset(normalize_key(item) for item in (*features, *details) if item),
            "price": frozenset({price_bucket(parsed_price)}) if price_bucket(parsed_price) else frozenset(),
        }
    )
    searchable_parts = [title, title, title]
    searchable_parts.extend(categories)
    searchable_parts.extend(categories)
    if brand:
        searchable_parts.extend((brand, brand))
    searchable_parts.extend(features)
    searchable_parts.extend(details)
    if description:
        searchable_parts.append(description)
    searchable_text = clean_text(searchable_parts)

    return Product(
        parent_asin=parent_asin,
        title=title,
        categories=categories,
        brand=brand,
        brand_key=normalize_key(brand) or None,
        price=parsed_price,
        features=features,
        description=description,
        searchable_text=searchable_text,
        metadata=_freeze(dict(record)),
        attributes=attributes,
        catalog_order=order,
    )


def load_catalog(config: AgentConfig) -> tuple[tuple[Product, ...], str]:
    path = Path(config.catalog_path)
    try:
        digest = hashlib.sha256()
        products: list[Product] = []
        seen: set[str] = set()
        with path.open("rb") as handle:
            for order, raw_line in enumerate(handle):
                digest.update(raw_line)
                if not raw_line.strip():
                    continue
                try:
                    record = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise AgentError(ErrorCode.CATALOG, f"invalid catalog JSON at row {order + 1}") from exc
                if not isinstance(record, dict):
                    raise AgentError(ErrorCode.CATALOG, f"catalog row {order + 1} is not an object")
                product = _product_from_record(record, len(products), config)
                if product.parent_asin in seen:
                    raise AgentError(ErrorCode.CATALOG, f"duplicate parent_asin at row {order + 1}")
                seen.add(product.parent_asin)
                products.append(product)
    except OSError as exc:
        raise AgentError(ErrorCode.CATALOG, "catalog could not be read") from exc
    return tuple(products), digest.hexdigest()


def iter_catalog(config: AgentConfig) -> Iterator[Product]:
    products, _ = load_catalog(config)
    yield from products
