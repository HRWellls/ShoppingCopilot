from __future__ import annotations

import argparse
import json
from pathlib import Path


VALUES = [
    ("black", "running shoes", 80), ("white", "winter boots", 120),
    ("blue", "casual shirts", 60), ("red", "formal dress", 150),
    ("green", "sneakers", 95), ("brown", "leather bag", 200),
]


INTENT_TEMPLATES = {
    "buying": [
        "I need {color} {product} under ${price}.",
        "Find me {product} in {color}; my budget is ${price}.",
        "I am ready to buy {color} {product}.",
        "Show me specific {product} that cost less than ${price}.",
        "My requirement is {color} {product}, budget ${price}.",
        "I want to purchase {product} in {color} now.",
    ],
    "browsing": [
        "I am still exploring {product} ideas.",
        "What {color} {product} styles could work for me?",
        "I need inspiration and options for {product}.",
        "I am browsing {product} without a fixed target.",
        "Show me different {product} directions to consider.",
        "I want to explore {color} {product} possibilities.",
    ],
    "continue": [
        "{color}",
        "under ${price}",
        "size 9",
        "{color} would be fine",
        "about ${price}",
        "yes, {color}",
    ],
    "confusion_buying": [
        "Show options, but they must be {color} {product} under ${price}.",
        "I need ideas for a specific {product} purchase under ${price}.",
        "Recommend {product}; {color} and ${price} are firm requirements.",
        "What options meet my exact need for {color} {product}?",
        "Help me choose {product} to buy now, maximum ${price}.",
        "Give me suggestions that satisfy {color} {product} requirements.",
    ],
    "confusion_browsing": [
        "I am looking at {product}, but only exploring possibilities.",
        "Show {color} {product} options for inspiration, no fixed target.",
        "I need ideas around {product}, not ready to buy.",
        "Recommend some {product} styles while I browse.",
        "I am considering {product} and want broad inspiration.",
        "What kinds of {color} {product} could I explore?",
    ],
}


EVENT_TEMPLATES = {
    "override": ("Actually, change the color to {color} instead.", "I would rather have {color}; replace the old color."),
    "clear": ("Clear my earlier color preference.", "Please remove the color preference."),
    "negation": ("Anything except {color}.", "I do not want {color}."),
    "no_preference": ("I do not have a preference for color.", "Any color is fine with me."),
    "intent_switch_browsing": ("I am just exploring options now.", "I am only browsing ideas now."),
    "intent_switch_buying": ("I am ready to buy specific shoes.", "I want to buy a specific product now."),
}


def split_for(index: int) -> str:
    return "calibration" if index < 3 else "test"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the versioned shopping intent evaluation set")
    parser.add_argument("--output", default="data/intent_eval_v1.jsonl")
    args = parser.parse_args()
    rows: list[dict[str, object]] = []
    sequence = 0
    for group, templates in INTENT_TEMPLATES.items():
        label = "buying" if group == "confusion_buying" else "browsing" if group == "confusion_browsing" else group
        for template_index, template in enumerate(templates):
            family = f"{group}-{template_index}"
            split = split_for(template_index)
            for repeat in range(50):
                color, product, price = VALUES[repeat % len(VALUES)]
                sequence += 1
                rows.append({
                    "id": f"intent-{sequence:04d}",
                    "split": split,
                    "family": family,
                    "kind": "confusion" if group.startswith("confusion") else label,
                    "expected_intent": label,
                    "message": template.format(color=color, product=product, price=price + repeat),
                    "prior_intent": "buying" if label == "continue" else "unknown",
                    "last_asked_slot": "color" if label == "continue" else None,
                })
    for name, templates in EVENT_TEMPLATES.items():
        kind = "intent_switch" if name.startswith("intent_switch") else name
        target = "browsing" if name.endswith("browsing") else "buying" if name.endswith("buying") else None
        for template_index, template in enumerate(templates):
            split = "calibration" if template_index == 0 else "test"
            for repeat in range(30):
                color, _, _ = VALUES[repeat % len(VALUES)]
                sequence += 1
                rows.append({
                    "id": f"event-{sequence:04d}",
                    "split": split,
                    "family": f"event-{name}-{template_index}",
                    "kind": "event",
                    "expected_event": kind,
                    "expected_target": target,
                    "message": template.format(color=color),
                    "prior_intent": "buying" if target != "buying" else "browsing",
                    "last_asked_slot": "color",
                })
    families: dict[str, str] = {}
    for row in rows:
        family, split = str(row["family"]), str(row["split"])
        if family in families and families[family] != split:
            raise RuntimeError("template family leaked across splits")
        families[family] = split
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"output": str(output), "rows": len(rows), "families": len(families)}, sort_keys=True))


if __name__ == "__main__":
    main()
