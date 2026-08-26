from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the rule-only B3 release gate")
    parser.add_argument("report")
    parser.add_argument("--baseline", default="docs/baselines/phase3-b0.json")
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    scenarios = report["scenario_metrics"]
    base_scenarios = baseline["scenario_metrics"]
    browsing = scenarios["browsing"]
    passed = {
        "overall_score": report["recommended_technical_score"] > 0.264985,
        "override_hit": scenarios["intent_override"]["hit_rate_at_10"] > 0.20,
        "buying_hit": scenarios["buying"]["hit_rate_at_10"] >= 0.3125,
        "browsing": browsing["hit_rate_at_10"] >= 0.35 or (
            browsing["mrr"] > base_scenarios["browsing"]["mrr"]
            and report["recommended_technical_score"] > baseline["recommended_technical_score"]
        ),
        "boundary": scenarios["boundary"]["hit_rate_at_10"] >= base_scenarios["boundary"]["hit_rate_at_10"],
    }
    payload = {"passed": all(passed.values()), "checks": passed}
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
