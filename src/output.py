from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.catalog.store import CatalogStore
from src.models import Candidate


def candidate_id(value: Any) -> str:
    if isinstance(value, Candidate):
        return value.parent_asin.strip()
    if isinstance(value, dict):
        return str(value.get("parent_asin", "")).strip()
    return str(value).strip() if isinstance(value, str) else ""


def sanitize_candidates(
    values: Iterable[Any],
    catalog: CatalogStore,
    top_k: int,
) -> list[str]:
    limit = min(max(top_k, 0), 10)
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        parent_asin = candidate_id(value)
        if not parent_asin or parent_asin in seen or parent_asin not in catalog:
            continue
        seen.add(parent_asin)
        result.append(parent_asin)
        if len(result) >= limit:
            break
    return result


def make_response(message: str, parent_asins: Iterable[str]) -> dict[str, Any]:
    return {
        "message": message,
        "ask_attribute": None,
        "recommendations": [{"parent_asin": parent_asin} for parent_asin in parent_asins],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    }
