from __future__ import annotations

import json
from pathlib import Path


CATALOG_ROWS = (
    {
        "parent_asin": "SHOE_BLACK_9",
        "title": "Black Trail Running Shoes Size 9",
        "features": ["breathable mesh", "size 9", "rubber sole"],
        "description": ["Lightweight running shoe for trails."],
        "price": 79.99,
        "categories": ["Clothing, Shoes & Jewelry", "Men", "Shoes", "Running"],
        "details": {"Color": "Black", "Size": "9", "Material": "Mesh"},
        "store": "SwiftStep",
    },
    {
        "parent_asin": "SHOE_WHITE_9",
        "title": "White Road Running Shoes Size 9",
        "features": ["size 9", "foam sole"],
        "description": ["Everyday road runner."],
        "price": 119.0,
        "categories": ["Clothing, Shoes & Jewelry", "Women", "Shoes", "Running"],
        "details": {"Color": "White", "Size": "9", "Material": "Synthetic"},
        "store": "RoadWorks",
    },
    {
        "parent_asin": "SHIRT_BLUE_M",
        "title": "Blue Cotton Casual Shirt Medium",
        "features": ["100% cotton", "machine washable"],
        "description": ["A casual shirt for daily wear."],
        "price": 35.0,
        "categories": ["Clothing, Shoes & Jewelry", "Men", "Clothing", "Shirts"],
        "details": {"Color": "Blue", "Size": "M", "Material": "Cotton"},
        "store": "DailyThreads",
    },
    {
        "parent_asin": "UNKNOWN_PRICE_BOOT",
        "title": "Black Leather Winter Boot Size 9",
        "features": ["leather", "size 9"],
        "description": [],
        "price": None,
        "categories": ["Clothing, Shoes & Jewelry", "Shoes", "Boots"],
        "details": {"Color": "Black", "Material": "Leather"},
        "store": "NorthBoot",
    },
)


def write_catalog(path: Path, rows: tuple[dict, ...] = CATALOG_ROWS) -> Path:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def profile(tag: str = "comfort") -> dict:
    return {
        "purchase_frequency": "1-2 prior purchases",
        "average_prior_rating": 4.0,
        "rating_style": "usually positive",
        "preference_tags": [tag],
        "summary": f"Prefers {tag}.",
    }


PHASE3_TURNS = {
    "buying": "black running shoes under $100 size 9",
    "browsing": "what should I wear to a summer wedding",
    "override": ("black shoes", "actually white instead"),
    "clear": ("shoes from SwiftStep", "any brand is fine"),
    "negation": ("red shoes", "not red"),
    "empty": "purple leather boots under $5",
    "clarify": "recommend something",
}
