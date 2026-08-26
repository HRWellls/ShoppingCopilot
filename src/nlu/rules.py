from __future__ import annotations

import re

from src.catalog.normalize import COLORS, MATERIALS, clean_text, normalize_key
from src.models import ConstraintSet, SessionState


NUMBER = r"(?:\d+(?:\.\d+)?)"
RANGE_RE = re.compile(rf"\bbetween\s*\$?({NUMBER})\s*(?:and|to|-)\s*\$?({NUMBER})\b", re.I)
UNDER_RE = re.compile(rf"(?:\bunder\b|\bbelow\b|\bless than\b|\bup to\b|\bno more than\b)\s*\$?({NUMBER})", re.I)
OVER_RE = re.compile(rf"(?:\bover\b|\babove\b|\bat least\b|\bmore than\b)\s*\$?({NUMBER})", re.I)
BUDGET_RE = re.compile(rf"\bbudget(?:\s+(?:is|of|around))?\s*\$?({NUMBER})", re.I)
SIZE_RE = re.compile(r"\bsize\s*[:#-]?\s*(xxs|xs|s|m|l|xl|xxl|\d{1,2}(?:\.5)?)\b", re.I)
BRAND_RE = re.compile(r"\b(?:brand|by|from)\s*[:=-]?\s*([a-z0-9][a-z0-9&' -]{0,30}?)(?=\s+(?:under|below|over|above|size|in|for|with)\b|[,.!?;]|$)", re.I)

CATEGORY_PHRASES = (
    "running shoes", "winter boots", "casual shirts", "formal dress", "hoop earrings",
    "shoes", "shoe", "boots", "boot", "shirts", "shirt", "dresses", "dress",
    "jackets", "jacket", "pants", "jeans", "earrings", "rings", "ring", "watches",
    "watch", "bags", "bag", "sneakers", "sneaker", "sandals", "sandal", "jewelry",
)


class RuleConstraintExtractor:
    def extract(self, message: str) -> ConstraintSet:
        normalized = normalize_key(message)
        updates = ConstraintSet()

        range_match = RANGE_RE.search(normalized)
        if range_match:
            first, second = float(range_match.group(1)), float(range_match.group(2))
            updates.price_min, updates.price_max = min(first, second), max(first, second)
        else:
            under = UNDER_RE.search(normalized) or BUDGET_RE.search(normalized)
            over = OVER_RE.search(normalized)
            if under:
                updates.price_max = float(under.group(1))
            if over:
                updates.price_min = float(over.group(1))

        size = SIZE_RE.search(normalized)
        if size:
            updates.size = size.group(1).casefold()

        for color in sorted(COLORS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(color)}\b", normalized):
                updates.color = "gray" if color == "grey" else color
                break
        for material in sorted(MATERIALS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(material)}\b", normalized):
                updates.material = material
                break
        for category in CATEGORY_PHRASES:
            if re.search(rf"\b{re.escape(category)}\b", normalized):
                updates.category = category
                break

        brand = BRAND_RE.search(clean_text(message))
        if brand:
            value = clean_text(brand.group(1))
            if value:
                updates.brand = value
        return updates


def merge_constraints(current: ConstraintSet, updates: ConstraintSet) -> ConstraintSet:
    merged = current.copy()
    for name, value in updates.as_dict().items():
        if value is not None:
            setattr(merged, name, value)
    return merged


def build_query(state: SessionState, current_message: str) -> str:
    parts: list[str] = []
    constraints = state.constraints
    for name in ("category", "brand", "color", "size", "material"):
        value = getattr(constraints, name)
        if value is not None:
            parts.append(str(value))
    if constraints.price_min is not None:
        parts.append(f"at least {constraints.price_min:g}")
    if constraints.price_max is not None:
        parts.append(f"under {constraints.price_max:g}")
    parts.append(clean_text(current_message))
    return " ".join(dict.fromkeys(part for part in parts if part)).strip()


def apply_rule_turn(
    state: SessionState,
    message: str,
    extractor: RuleConstraintExtractor,
) -> ConstraintSet:
    updates = extractor.extract(message)
    state.constraints = merge_constraints(state.constraints, updates)
    state.last_query = build_query(state, message)
    return updates
