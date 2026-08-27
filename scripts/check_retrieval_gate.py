from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts.retrieval_diagnostic_benchmark import build_comparison


def run_benchmark(output: Path, optimized: bool, baseline: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "scripts.retrieval_diagnostic_benchmark",
        "--output",
        str(output),
    ]
    if optimized:
        command.extend([
            "--attribute-retrieval",
            "--attribute-reranking",
            "--recommend-with-clarification",
            "--override-invalidation",
            "--single-pass",
            "--baseline",
            str(baseline),
        ])
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic retrieval promotion gate")
    parser.add_argument("--baseline-report", default=".runtime/retrieval-gate-b3.json")
    parser.add_argument("--optimized-report", default=".runtime/retrieval-gate-d4.json")
    parser.add_argument("--reuse-existing", action="store_true")
    args = parser.parse_args()
    baseline_path = Path(args.baseline_report)
    optimized_path = Path(args.optimized_report)
    if not args.reuse_existing:
        run_benchmark(baseline_path, False, baseline_path)
        run_benchmark(optimized_path, True, baseline_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    optimized = json.loads(optimized_path.read_text(encoding="utf-8"))
    comparison = build_comparison(optimized, baseline)
    optimized["comparison"] = {"baseline": str(baseline_path), **comparison}
    optimized_path.write_text(json.dumps(optimized, indent=2) + "\n", encoding="utf-8")
    payload = {
        "passed": comparison["all_promotion_gates_pass"],
        "checks": comparison["gates"],
        "baseline_quality_sha256": comparison["baseline_quality_sha256"],
        "optimized_quality_sha256": optimized.get("benchmark", {}).get("quality_sha256"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
