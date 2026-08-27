from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from evaluator.local_evaluator import catalog_index, load_jsonl
from evaluator.retrieval_diagnostics import evaluate_with_diagnostics, file_sha256, stable_quality_sha256
from src.config import AgentConfig
from starter.agent import Agent


class TimedAgent:
    def __init__(self, config: AgentConfig) -> None:
        started = time.perf_counter()
        self.agent = Agent(config=config)
        self.initialization_seconds = time.perf_counter() - started
        self.latencies: list[float] = []
        self.fallback_count = 0

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.agent.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        started = time.perf_counter()
        response = self.agent.respond(session_id, user_message, turn, top_k)
        self.latencies.append((time.perf_counter() - started) * 1000)
        if response.get("message", "").startswith("I couldn't process"):
            self.fallback_count += 1
        return response


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))]


def build_comparison(result: dict, baseline: dict) -> dict:
    scenario_deltas = {}
    scenario_protection = {}
    for name, metrics in result["scenario_metrics"].items():
        control = baseline.get("scenario_metrics", {}).get(name, {})
        baseline_hit = float(control.get("hit_rate_at_10", 0.0))
        scenario_deltas[name] = {
            "hit_rate_at_10": round(float(metrics["hit_rate_at_10"]) - baseline_hit, 6),
            "mrr": round(float(metrics["mrr"]) - float(control.get("mrr", 0.0)), 6),
            "mttc": round(float(metrics["mttc"]) - float(control.get("mttc", 0.0)), 6),
        }
        scenario_protection[name] = float(metrics["hit_rate_at_10"]) >= baseline_hit
    recall = float(result["retrieval_diagnostics"]["overall"]["candidate_recall_at_pool"])
    p95_overhead = round(
        float(result["benchmark"]["p95_ms"]) - float(baseline.get("benchmark", {}).get("p95_ms", 0.0)),
        3,
    )
    gates = {
        "candidate_recall_at_150": recall >= 0.95,
        "overall_hit_at_10": float(result["hit_rate_at_10"]) >= 0.65,
        "technical_score": float(result["recommended_technical_score"]) > 0.331459,
        "intent_override_hit_at_10": float(
            result["scenario_metrics"].get("intent_override", {}).get("hit_rate_at_10", 0.0)
        ) >= 0.80,
        "scenario_non_regression": all(scenario_protection.values()),
        "p95_overhead_ms": p95_overhead <= 25.0,
    }
    return {
        "baseline_quality_sha256": baseline.get("benchmark", {}).get("quality_sha256"),
        "deltas": {
            "hit_rate_at_10": round(float(result["hit_rate_at_10"]) - float(baseline["hit_rate_at_10"]), 6),
            "mrr": round(float(result["mrr"]) - float(baseline["mrr"]), 6),
            "technical_score": round(
                float(result["recommended_technical_score"]) - float(baseline["recommended_technical_score"]), 6
            ),
            "p95_ms": p95_overhead,
        },
        "scenario_deltas": scenario_deltas,
        "scenario_protection": scenario_protection,
        "gates": gates,
        "all_promotion_gates_pass": all(gates.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval-stage diagnostic benchmark")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--output", default=".runtime/retrieval-d0-b3.json")
    parser.add_argument("--baseline", default=None, help="Matched B3 diagnostic JSON for gate comparison")
    parser.add_argument("--verify-repeat", action="store_true")
    parser.add_argument("--attribute-retrieval", action="store_true")
    parser.add_argument("--attribute-reranking", action="store_true")
    parser.add_argument("--recommend-with-clarification", action="store_true")
    parser.add_argument("--override-invalidation", action="store_true")
    parser.add_argument("--single-pass", action="store_true")
    parser.add_argument("--dense", action="store_true")
    args = parser.parse_args()
    config = AgentConfig(
        catalog_path=Path(args.catalog),
        multiturn_state_enabled=True,
        intent_routing_enabled=True,
        intent_policy_enabled=True,
        intent_model_mode="off",
        dense_enabled=args.dense,
        llm_enabled=False,
        attribute_retrieval_enabled=args.attribute_retrieval,
        attribute_reranking_enabled=args.attribute_reranking,
        recommendation_with_clarification_enabled=args.recommend_with_clarification,
        override_invalidation_enabled=args.override_invalidation,
        optimized_single_pass_enabled=args.single_pass,
        config_version=(
            "phase3-hybrid-v1" if args.dense else
            "retrieval-d4" if args.override_invalidation else
            "retrieval-d3" if args.recommend_with_clarification else
            "retrieval-d2" if args.attribute_reranking else
            "retrieval-d1" if args.attribute_retrieval else
            "retrieval-d0-b3"
        ),
    )
    samples = load_jsonl(args.dataset)
    ids, categories, products = catalog_index(args.catalog)

    def run() -> tuple[dict, TimedAgent]:
        measured = TimedAgent(config)
        return evaluate_with_diagnostics(measured, samples, ids, categories, products), measured

    result, measured = run()
    quality_hash = stable_quality_sha256(result)
    repeat_hash = None
    if args.verify_repeat:
        repeated, _ = run()
        repeat_hash = stable_quality_sha256(repeated)
        if repeat_hash != quality_hash:
            raise SystemExit("non-timing diagnostic metrics are not reproducible")
    component_values: dict[str, list[float]] = {}
    for session in result["sessions"]:
        for turn in session["turns"]:
            for name, value in turn.get("retrieval_timings", {}).items():
                component_values.setdefault(name, []).append(float(value))
    result["benchmark"] = {
        "dataset": str(Path(args.dataset)),
        "dataset_sha256": file_sha256(args.dataset),
        "catalog": str(Path(args.catalog)),
        "catalog_sha256": file_sha256(args.catalog),
        "config": config.public_snapshot(),
        "quality_sha256": quality_hash,
        "repeat_quality_sha256": repeat_hash,
        "initialization_seconds": round(measured.initialization_seconds, 6),
        "p50_ms": round(percentile(measured.latencies, 0.5), 3),
        "p95_ms": round(percentile(measured.latencies, 0.95), 3),
        "fallback_count": measured.fallback_count,
        "dense_available": measured.agent._core.dense is not None,
        "dense_startup_fallback": measured.agent._core.dense_fallback,
        "retrieval_component_ms": {
            name: {
                "p50": round(percentile(values, 0.5), 3),
                "p95": round(percentile(values, 0.95), 3),
            }
            for name, values in sorted(component_values.items())
        },
    }
    if args.baseline:
        baseline_path = Path(args.baseline)
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        result["comparison"] = {
            "baseline": str(baseline_path),
            **build_comparison(result, baseline),
        }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "hit_rate_at_10": result["hit_rate_at_10"],
        "mrr": result["mrr"],
        "candidate_recall_at_pool": result["retrieval_diagnostics"]["overall"]["candidate_recall_at_pool"],
        "raw_channel_union_coverage": result["retrieval_diagnostics"]["overall"]["raw_channel_union_coverage"],
        "quality_sha256": quality_hash,
        "repeat_verified": repeat_hash == quality_hash if repeat_hash else False,
        "gates": result.get("comparison", {}).get("gates"),
    }, indent=2))


if __name__ == "__main__":
    main()
