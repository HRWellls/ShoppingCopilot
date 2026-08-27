from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a small stratified public-session test set")
    parser.add_argument("--source", default="data/public_set.jsonl")
    parser.add_argument("--output", default=".runtime/public_smoke.jsonl")
    parser.add_argument("--per-scenario", type=int, default=2)
    parser.add_argument("--scenario", choices=("boundary", "browsing", "buying", "intent_override"))
    args = parser.parse_args()
    selected, counts = [], defaultdict(int)
    with Path(args.source).open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            scenario = str(row["scenario_type"])
            if args.scenario and scenario != args.scenario:
                continue
            if counts[scenario] >= args.per_scenario:
                continue
            selected.append(row); counts[scenario] += 1
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=True) + "\n" for row in selected), encoding="utf-8")
    print(json.dumps({"output": str(output), "rows": len(selected), "scenario_counts": dict(sorted(counts.items()))}, indent=2))


if __name__ == "__main__":
    main()
