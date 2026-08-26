from __future__ import annotations

import re

from src.catalog.normalize import normalize_key
from src.models import IntentResult


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "i", "in", "is", "it", "me", "my", "of", "on", "or", "please", "some", "that", "the", "this", "to", "want", "with", "would", "you"}
)
BUY_ACTIONS = ("looking for", "need", "want to buy", "buy", "shopping for", "find me")
BROWSE_SIGNALS = ("recommend", "ideas", "what should i wear", "what to wear", "options", "still exploring", "something for", "use your judgment")
PRODUCT_TERMS = frozenset(
    {"shoe", "shoes", "boot", "boots", "shirt", "shirts", "dress", "dresses", "jacket", "jackets", "pants", "jeans", "jewelry", "earrings", "ring", "rings", "watch", "watches", "bag", "bags", "clothing", "sneaker", "sneakers", "sandal", "sandals"}
)


class RuleIntentRouter:
    def route(self, message: str) -> IntentResult:
        normalized = normalize_key(message)
        tokens = tuple(token.casefold() for token in TOKEN_RE.findall(normalized))
        meaningful = tuple(token for token in tokens if token not in STOPWORDS)
        if not meaningful:
            return IntentResult("unknown", 0.0, ())

        buying_evidence: list[str] = []
        browsing_evidence: list[str] = []
        for phrase in BUY_ACTIONS:
            if phrase in normalized:
                buying_evidence.append(f"buy_action:{phrase}")
        if any(token in PRODUCT_TERMS for token in tokens):
            buying_evidence.append("product_term")
        if re.search(r"(?:\$\s*\d|\b(?:under|below|between|budget|size)\b)", normalized):
            buying_evidence.append("explicit_constraint")
        for phrase in BROWSE_SIGNALS:
            if phrase in normalized:
                browsing_evidence.append(f"browse_signal:{phrase}")

        if browsing_evidence and len(buying_evidence) < 2:
            confidence = min(0.95, 0.6 + 0.1 * len(browsing_evidence))
            return IntentResult("browsing", confidence, tuple(browsing_evidence))
        if len(buying_evidence) >= 2:
            confidence = min(0.95, 0.55 + 0.1 * len(buying_evidence))
            return IntentResult("buying", confidence, tuple(buying_evidence))
        if browsing_evidence:
            return IntentResult("browsing", 0.6, tuple(browsing_evidence))
        return IntentResult("unknown", 0.25, tuple(buying_evidence))
