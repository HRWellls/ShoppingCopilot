from __future__ import annotations

import html
import math
import re
import unicodedata
from collections.abc import Iterable
from typing import Any


HTML_RE = re.compile(r"<[^>]*>")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPACE_RE = re.compile(r"\s+")
PRICE_RE = re.compile(r"-?\d+(?:\.\d+)?")

COLORS = frozenset(
    {"black", "white", "blue", "red", "pink", "green", "brown", "gray", "grey", "purple", "yellow", "orange"}
)
MATERIALS = frozenset(
    {"cotton", "polyester", "nylon", "leather", "wool", "spandex", "silk", "rayon", "mesh", "synthetic", "fabric"}
)


def flatten_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [
            f"{key} {item}"
            for key, item in value.items()
            if item is not None and clean_text(item)
        ]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [clean_text(item) for item in value if clean_text(item)]
    cleaned = clean_text(value)
    return [cleaned] if cleaned else []


def clean_text(value: Any, max_chars: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        text = " ".join(flatten_text(value))
    else:
        text = str(value)
    text = unicodedata.normalize("NFKC", html.unescape(text))
    text = HTML_RE.sub(" ", text)
    text = CONTROL_RE.sub(" ", text)
    text = SPACE_RE.sub(" ", text).strip()
    if max_chars is not None:
        text = text[:max_chars].rstrip()
    return text


def normalize_key(value: Any) -> str:
    return clean_text(value).casefold()


def normalize_collection(value: Any) -> tuple[str, ...]:
    return tuple(item for item in flatten_text(value) if item)


def parse_price(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        match = PRICE_RE.search(clean_text(value).replace(",", ""))
        if match is None:
            return None
        try:
            number = float(match.group(0))
        except ValueError:
            return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def token_values(texts: Iterable[str], vocabulary: frozenset[str]) -> frozenset[str]:
    corpus = f" {' '.join(texts).casefold()} "
    return frozenset(value for value in vocabulary if re.search(rf"\b{re.escape(value)}\b", corpus))


def extract_sizes(texts: Iterable[str]) -> frozenset[str]:
    corpus = " ".join(texts).casefold()
    values: set[str] = set()
    for match in re.finditer(r"\bsize\s*[:#-]?\s*(xxs|xs|s|m|l|xl|xxl|\d{1,2}(?:\.5)?)\b", corpus):
        values.add(match.group(1))
    return frozenset(values)
