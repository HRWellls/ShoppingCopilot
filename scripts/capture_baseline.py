"""Capture a redacted, reproducible runtime baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from src.config import AgentConfig
from starter.agent import Agent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="data/catalog_sample_100.jsonl")
    parser.add_argument("--output", default=".runtime/baseline.json")
    args = parser.parse_args()
    catalog = Path(args.catalog)
    started = time.perf_counter()
    agent = Agent(catalog)
    init_seconds = time.perf_counter() - started
    digest = hashlib.sha256(catalog.read_bytes()).hexdigest() if catalog.exists() else None
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        revision = "unknown"
    config = agent.config.public_snapshot()
    report = {
        "schema_version": 1,
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_revision": revision,
        "python": sys.version,
        "platform": platform.platform(),
        "catalog": {"path": str(catalog), "sha256": digest, "count": len(agent._core.catalog)},
        "config": config,
        "routes": {"dense": bool(agent._core.dense), "llm": config.get("llm_enabled", False), "bm25": True},
        "initialization_seconds": round(init_seconds, 6),
        "reproduce": f"python -m scripts.capture_baseline --catalog {args.catalog} --output {args.output}",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
