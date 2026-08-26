from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
from starter.agent import Agent

ALLOWED_ATTRIBUTES = {
    "category", "material", "color", "size", "style", "brand",
    "budget", "feature", "use_case", "other", None,
}

class InstrumentedAgent:
    def __init__(self, catalog_path: str | Path) -> None:
        started = time.perf_counter()
        self.agent = Agent(catalog_path)
        self.initialization_seconds = time.perf_counter() - started
        self.turn_latencies_ms: list[float] = []
        self.contract_failures = 0
        self.session_leakage_failures = 0
        self.catalog_ids = self.agent._core.catalog.ids

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.agent.reset(session_id, user_profile)
        state = self.agent._core.sessions.get(session_id)
        if state.turn_count or state.history or state.candidate_ids or state.constraints.active_names():
            self.session_leakage_failures += 1

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        started = time.perf_counter()
        response = self.agent.respond(session_id, user_message, turn, top_k)
        self.turn_latencies_ms.append((time.perf_counter() - started) * 1_000)
        if not self._is_valid_response(response):
            self.contract_failures += 1
        return response

    def _is_valid_response(self, response: Any) -> bool:
        if not isinstance(response, dict) or not isinstance(response.get("message"), str):
            return False
        if response.get("ask_attribute") not in ALLOWED_ATTRIBUTES:
            return False
        recommendations = response.get("recommendations")
        if not isinstance(recommendations, list) or len(recommendations) > 10:
            return False
        seen: set[str] = set()
        for item in recommendations:
            if not isinstance(item, dict):
                return False
            parent_asin = item.get("parent_asin")
            if not isinstance(parent_asin, str) or parent_asin not in self.catalog_ids or parent_asin in seen:
                return False
            seen.add(parent_asin)
        usage = response.get("usage")
        return (
            isinstance(usage, dict)
            and isinstance(usage.get("prompt_tokens"), int)
            and usage["prompt_tokens"] >= 0
            and isinstance(usage.get("completion_tokens"), int)
            and usage["completion_tokens"] >= 0
        )


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the public evaluator with stage 2 engineering metrics")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--output", default=".runtime/phase2-validation.json")
    args = parser.parse_args()

    samples = load_jsonl(args.dataset)
    catalog_ids, categories, products = catalog_index(args.catalog)
    agent = InstrumentedAgent(args.catalog)
    started = time.perf_counter()
    result = evaluate(agent, samples, catalog_ids, categories, products)
    evaluation_seconds = time.perf_counter() - started
    validation = {
        "catalog_count": len(catalog_ids),
        "catalog_checksum": agent.agent._core.catalog.checksum,
        "initialization_seconds": round(agent.initialization_seconds, 6),
        "evaluation_seconds": round(evaluation_seconds, 6),
        "turn_calls": len(agent.turn_latencies_ms),
        "turn_latency_ms": {
            "p50": round(percentile(agent.turn_latencies_ms, 0.50), 3),
            "p95": round(percentile(agent.turn_latencies_ms, 0.95), 3),
            "max": round(max(agent.turn_latencies_ms, default=0.0), 3),
        },
        "contract_failures": agent.contract_failures,
        "session_leakage_failures": agent.session_leakage_failures,
    }
    payload = {**result, "phase2_validation": validation}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "metrics": {key: result[key] for key in ("sample_count", "hit_rate_at_10", "mrr", "mttc", "recommended_technical_score")},
        "phase2_validation": validation,
    }, indent=2))


if __name__ == "__main__":
    main()
