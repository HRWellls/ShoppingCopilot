from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
from src.config import AgentConfig
from starter.agent import Agent


class TimedAgent:
    def __init__(self, config: AgentConfig) -> None:
        started = time.perf_counter()
        self.agent = Agent(config=config)
        self.initialization_seconds = time.perf_counter() - started
        self.latencies: list[float] = []

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.agent.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        started = time.perf_counter()
        response = self.agent.respond(session_id, user_message, turn, top_k)
        self.latencies.append((time.perf_counter() - started) * 1_000)
        return response


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))] if ordered else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3 ablation benchmark")
    parser.add_argument("--variant", choices=("full", "no-clarification", "no-relaxation"), default="full")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--output", default=".runtime/phase3-ablation.json")
    parser.add_argument("--dense", action="store_true", help="Load the persisted FAISS index and local model")
    args = parser.parse_args()
    config = AgentConfig(
        catalog_path=Path(args.catalog),
        clarification_enabled=args.variant != "no-clarification",
        relaxation_enabled=args.variant != "no-relaxation",
        dense_enabled=args.dense,
    )
    samples = load_jsonl(args.dataset)
    ids, categories, products = catalog_index(args.catalog)
    agent = TimedAgent(config)
    result = evaluate(agent, samples, ids, categories, products)
    summary = {
        "variant": args.variant,
        "config": config.public_snapshot(),
        "initialization_seconds": round(agent.initialization_seconds, 6),
        "p50_ms": round(percentile(agent.latencies, .5), 3),
        "p95_ms": round(percentile(agent.latencies, .95), 3),
    }
    payload = {**result, "phase3_ablation": summary}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"variant": args.variant, "hit_rate_at_10": result["hit_rate_at_10"], "mrr": result["mrr"], "mttc": result["mttc"], "score": result["recommended_technical_score"], "p50_ms": summary["p50_ms"], "p95_ms": summary["p95_ms"]}, indent=2))


if __name__ == "__main__":
    main()
