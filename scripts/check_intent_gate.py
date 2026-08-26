from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Check offline intent and event activation gates")
    parser.add_argument("report")
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    events = report["event_recall"]
    checks = {
        "macro_f1": report["macro_f1"] >= 0.90,
        "buying_to_browsing": report["buying_to_browsing_rate"] < 0.05,
        "continue_recall": report["continue_recall"] >= 0.90,
        "explicit_switch_recall": events.get("intent_switch", 0.0) >= 0.90,
        "event_recall": all(events.get(name, 0.0) >= 0.90 for name in ("override", "clear", "negation", "no_preference", "intent_switch")),
    }
    payload = {"passed": all(checks.values()), "checks": checks}
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
