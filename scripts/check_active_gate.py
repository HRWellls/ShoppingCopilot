from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Check active intent model release gates")
    parser.add_argument("--baseline", default=".runtime/multiturn-b3.json")
    parser.add_argument("--active", default=".runtime/multiturn-d-active.json")
    parser.add_argument("--intent", default=".runtime/intent-v2-test.json")
    parser.add_argument("--p95-budget-ms", type=float, default=25.0)
    args = parser.parse_args()
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    active = json.loads(Path(args.active).read_text(encoding="utf-8"))
    intent = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    scenario_regression = all(
        active["scenario_metrics"][name]["hit_rate_at_10"] >= values["hit_rate_at_10"]
        for name, values in baseline["scenario_metrics"].items()
    )
    event_metrics = all(value >= 0.90 for value in intent["event_recall"].values())
    p95_overhead = active["phase3_ablation"]["p95_ms"] - baseline["phase3_ablation"]["p95_ms"]
    checks = {
        "active_above_b3": active["recommended_technical_score"] > baseline["recommended_technical_score"],
        "scenario_protection": scenario_regression,
        "event_metrics": event_metrics,
        "p95_budget": p95_overhead <= args.p95_budget_ms,
    }
    payload = {
        "passed": all(checks.values()),
        "checks": checks,
        "p95_overhead_ms": round(p95_overhead, 3),
        "selected_default_mode": "active" if all(checks.values()) else "off",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
