from __future__ import annotations

import re

from src.catalog.normalize import COLORS, MATERIALS, clean_text, normalize_key
from src.models import ConstraintSet, ParsedTurn, SessionState
from src.nlu.router import RuleIntentRouter
from src.state.overrides import make_slot


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
    "watch", "panties", "underwear", "undershirts", "socks", "loafers", "bags", "bag",
    "sneakers", "sneaker", "sandals", "sandal", "jewelry",
    "wrist watches", "camisoles", "camisole", "camis", "tanks", "tops", "tees",
    "tunics", "shorts", "slippers", "necklaces", "bracelets",
)
STYLE_WORDS = ("casual", "formal", "sporty", "classic", "vintage", "minimalist", "elegant", "streetwear", "relaxed")
USE_CASE_WORDS = ("hiking", "running", "gym", "winter", "outdoor", "work", "travel", "wedding", "party", "office")


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

    def parse(self, message: str, state: SessionState, soft_ttl: int = 3) -> ParsedTurn:
        intent = RuleIntentRouter().route(message)
        updates = self.extract(message)
        normalized = normalize_key(message)
        if (
            updates.category is not None
            and state.last_asked_slot
            and state.last_asked_slot != "category"
            and not re.search(r"\b(?:looking for|category|type of product)\b", normalized)
        ):
            updates.category = None
        self._bind_short_answer(updates, normalized, state)
        clears: set[str] = set()
        overrides: set[str] = set()
        slots = {}
        if re.search(r"\b(any brand|brand does not matter|no brand preference)\b", normalized):
            clears.add("brand")
            updates.brand = None
        explicit_override = bool(re.search(r"\b(actually|instead|change|rather)\b", normalized))
        for name, value in updates.as_dict().items():
            if value is None:
                continue
            slots[name] = make_slot(value, name=name, turn=state.turn_count, soft_ttl=soft_ttl)
            if explicit_override or name in state.slots:
                overrides.add(name)
        for name, value in self._semantic_slots(normalized).items():
            slots[name] = make_slot(value, name=name, turn=state.turn_count, soft_ttl=soft_ttl)
            if explicit_override or name in state.slots:
                overrides.add(name)
        negated = re.search(
            r"\b(?:anything\s+except|except|not|no|without|don't want|do not want)\s+(black|white|blue|red|pink|green|brown|gray|grey|purple|yellow|orange)\b",
            normalized,
        )
        if negated:
            color = "gray" if negated.group(1) == "grey" else negated.group(1)
            slots["color"] = make_slot(color, name="color", turn=state.turn_count, negated=True, soft_ttl=soft_ttl)
            overrides.add("color")
        return ParsedTurn(
            intent=intent.label,
            intent_confidence=intent.confidence,
            slot_updates=slots,
            clears=frozenset(clears),
            overrides=frozenset(overrides),
            query_text=clean_text(message),
            evidence=intent.evidence,
            parser_source="rule",
        )

    @staticmethod
    def _semantic_slots(normalized: str) -> dict[str, str]:
        result: dict[str, str] = {}
        styles = [word for word in STYLE_WORDS if re.search(rf"\b{re.escape(word)}\b", normalized)]
        uses = [word for word in USE_CASE_WORDS if re.search(rf"\b{re.escape(word)}\b", normalized)]
        if styles:
            result["style"] = " ".join(styles)
        if uses:
            result["use_case"] = " ".join(uses)
        occasion = re.search(r"\b(?:for|to)\s+(?:a|an|the)?\s*(wedding|party|office|vacation|trip|event|date night)\b", normalized)
        if occasion:
            result["occasion"] = occasion.group(1)
        return result

    @staticmethod
    def _bind_short_answer(updates: ConstraintSet, normalized: str, state: SessionState) -> None:
        slot = state.last_asked_slot
        if not slot or len(normalized.split()) > 5 or not normalized:
            return
        if slot == "size" and updates.size is None:
            match = re.fullmatch(r"(?:size\s*)?(xxs|xs|s|m|l|xl|xxl|\d{1,2}(?:\.5)?)", normalized)
            if match:
                updates.size = match.group(1).casefold()
        elif slot == "brand" and updates.brand is None and not re.search(r"\b(?:any|none|no preference|doesn't matter|do not care)\b", normalized):
            updates.brand = clean_text(normalized)
        elif slot == "price_max" and updates.price_max is None:
            match = re.fullmatch(r"\$?([0-9]+(?:\.[0-9]+)?)", normalized)
            if match:
                updates.price_max = float(match.group(1))


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
