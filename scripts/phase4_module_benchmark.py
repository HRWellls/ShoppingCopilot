from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
from src.config import AgentConfig
from src.errors import AgentError
from starter.agent import Agent


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


class MeasuredAgent:
    def __init__(self, config: AgentConfig) -> None:
        started = time.perf_counter()
        self.agent = Agent(config=config)
        self.initialization_seconds = time.perf_counter() - started
        self.latencies: list[float] = []
        self.response_fallbacks = 0
        self.llm_attempts = 0
        self.llm_successes = 0
        self.llm_failures: Counter[str] = Counter()
        self.dense_queries = 0
        self.dense_failures: Counter[str] = Counter()
        self._instrument_modules()

    def _instrument_modules(self) -> None:
        model = self.agent._core.parser.model
        if model is not None:
            original_model_parse: Callable[..., Any] = model.parse

            def measured_model_parse(*args: Any, **kwargs: Any) -> Any:
                self.llm_attempts += 1
                try:
                    result = original_model_parse(*args, **kwargs)
                    self.llm_successes += 1
                    return result
                except AgentError as exc:
                    self.llm_failures[exc.code.value] += 1
                    raise

            model.parse = measured_model_parse  # type: ignore[method-assign]

        dense = self.agent._core.dense
        if dense is not None:
            original_dense_search: Callable[..., Any] = dense.search

            def measured_dense_search(*args: Any, **kwargs: Any) -> Any:
                self.dense_queries += 1
                try:
                    return original_dense_search(*args, **kwargs)
                except AgentError as exc:
                    self.dense_failures[exc.code.value] += 1
                    raise

            dense.search = measured_dense_search  # type: ignore[method-assign]

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.agent.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        started = time.perf_counter()
        response = self.agent.respond(session_id, user_message, turn, top_k)
        self.latencies.append((time.perf_counter() - started) * 1_000)
        if response.get("message") in {
            "I couldn't process that request safely.",
            "I couldn't process that update, so here are the previous matches.",
        }:
            self.response_fallbacks += 1
        return response

    def metrics(self, dense_requested: bool, llm_requested: bool) -> dict[str, object]:
        core = self.agent._core
        dense = core.dense
        model = core.parser.model
        return {
            "initialization_seconds": round(self.initialization_seconds, 6),
            "respond_calls": len(self.latencies),
            "p50_ms": round(percentile(self.latencies, 0.50), 3),
            "p95_ms": round(percentile(self.latencies, 0.95), 3),
            "response_fallbacks": self.response_fallbacks,
            "dense": {
                "requested": dense_requested,
                "active": dense is not None,
                "loaded_from_disk": bool(dense is not None and dense.loaded_from_disk),
                "startup_fallback": core.dense_fallback,
                "queries": self.dense_queries,
                "cache_hits": int(dense.cache_hits) if dense is not None else 0,
                "failures": dict(sorted(self.dense_failures.items())),
            },
            "llm": {
                "requested": llm_requested,
                "parser_configured": model is not None,
                "credentials_available": bool(model is not None and model._api_key),
                "attempts": self.llm_attempts,
                "successes": self.llm_successes,
                "failures": dict(sorted(self.llm_failures.items())),
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate B3 with optional Dense and DeepSeek modules")
    parser.add_argument("--name", required=True)
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dense", action="store_true")
    parser.add_argument("--dense-weight", type=float)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--llm-timeout-ms", type=int, default=600)
    args = parser.parse_args()
    if args.dense_weight is not None and not 0.0 <= args.dense_weight <= 1.0:
        parser.error("--dense-weight must be between 0 and 1")

    weight_overrides = {}
    if args.dense_weight is not None:
        weight_overrides = {
            "buying_weights": (1.0 - args.dense_weight, args.dense_weight, 0.0, 0.0),
            "browsing_weights": (1.0 - args.dense_weight, args.dense_weight, 0.0, 0.0),
        }

    config = AgentConfig(
        catalog_path=Path(args.catalog),
        multiturn_state_enabled=True,
        intent_routing_enabled=True,
        intent_policy_enabled=True,
        intent_model_mode="off",
        dense_enabled=args.dense,
        llm_enabled=args.llm,
        llm_timeout_ms=args.llm_timeout_ms,
        # The persisted dense manifest was built with this compatibility version.
        config_version="phase3-hybrid-v1",
        **weight_overrides,
    )
    samples = load_jsonl(args.dataset)
    catalog_ids, categories, products = catalog_index(args.catalog)
    started = time.perf_counter()
    agent = MeasuredAgent(config)
    result = evaluate(agent, samples, catalog_ids, categories, products)
    experiment = {
        "name": args.name,
        "behavior_version": "multiturn-b3",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
        "wall_seconds": round(time.perf_counter() - started, 3),
        "config": config.public_snapshot(),
        **agent.metrics(args.dense, args.llm),
    }
    payload = {**result, "experiment": experiment}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "name": args.name,
        "hit_rate_at_10": result["hit_rate_at_10"],
        "mrr": result["mrr"],
        "mttc": result["mttc"],
        "technical_score": result["recommended_technical_score"],
        "token_usage": result["reported_token_usage"],
        **agent.metrics(args.dense, args.llm),
    }, indent=2))


if __name__ == "__main__":
    main()
