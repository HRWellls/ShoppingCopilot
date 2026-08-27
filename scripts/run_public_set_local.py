"""Run the public-set evaluator with an explicit deterministic Agent profile.

Examples:
    python -m scripts.run_public_set_local --profile d4
    python -m scripts.run_public_set_local --profile b3 --output .runtime/public-b3.json
    python -m scripts.run_public_set_local --dataset data/public_smoke.jsonl
"""

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
        self.latencies_ms: list[float] = []
        self.fallback_count = 0

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.agent.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        started = time.perf_counter()
        response = self.agent.respond(session_id, user_message, turn, top_k)
        self.latencies_ms.append((time.perf_counter() - started) * 1_000)
        if response.get("message", "").startswith("I couldn't process"):
            self.fallback_count += 1
        return response


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def make_config(profile: str, catalog_path: Path) -> AgentConfig:
    if profile == "b3":
        return AgentConfig(
            catalog_path=catalog_path,
            multiturn_state_enabled=True,
            intent_routing_enabled=True,
            intent_policy_enabled=True,
            intent_model_mode="off",
            dense_enabled=False,
            llm_enabled=False,
            config_version="public-b3",
        )
    if profile == "d4":
        return AgentConfig(
            catalog_path=catalog_path,
            multiturn_state_enabled=True,
            intent_routing_enabled=True,
            intent_policy_enabled=True,
            intent_model_mode="off",
            dense_enabled=False,
            llm_enabled=False,
            attribute_retrieval_enabled=True,
            attribute_reranking_enabled=True,
            recommendation_with_clarification_enabled=True,
            override_invalidation_enabled=True,
            optimized_single_pass_enabled=True,
            config_version="retrieval-d4",
        )
    raise ValueError(f"unsupported profile: {profile}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate an Agent on data/public_set.jsonl")
    parser.add_argument("--profile", choices=("b3", "d4"), default="d4")
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    parser.add_argument("--dataset", type=Path, default=Path("data/public_set.jsonl"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    config = make_config(args.profile, args.catalog)
    samples = load_jsonl(args.dataset)
    catalog_ids, categories, products = catalog_index(args.catalog)
    measured = TimedAgent(config)
    result = evaluate(measured, samples, catalog_ids, categories, products)
    summary = {
        "profile": args.profile,
        "dataset": str(args.dataset),
        "catalog": str(args.catalog),
        "config": config.public_snapshot(),
        "initialization_seconds": round(measured.initialization_seconds, 6),
        "response_p50_ms": round(percentile(measured.latencies_ms, 0.50), 3),
        "response_p95_ms": round(percentile(measured.latencies_ms, 0.95), 3),
        "fallback_count": measured.fallback_count,
    }
    payload = {**result, "benchmark": summary}
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({**summary, "metrics": {
        "sample_count": result["sample_count"],
        "hit_rate_at_10": result["hit_rate_at_10"],
        "mrr": result["mrr"],
        "mttc": result["mttc"],
        "technical_score": result["recommended_technical_score"],
        "scenario_metrics": result["scenario_metrics"],
    }}, indent=2))


if __name__ == "__main__":
    main()
