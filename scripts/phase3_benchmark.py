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
        self.fallback_count = 0

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
            self.fallback_count += 1
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
    parser.add_argument("--state-events", action="store_true", help="Enable transactional multi-turn state and events")
    parser.add_argument("--route", action="store_true", help="Enable intent-aware retrieval")
    parser.add_argument("--policy", action="store_true", help="Enable intent-aware dialogue policy")
    parser.add_argument("--intent-mode", choices=("off", "shadow", "active"), default="off")
    parser.add_argument("--intent-model-dir", default=".runtime/models/nli-deberta-v3-xsmall")
    parser.add_argument("--intent-strategy", choices=("single", "two_stage"), default="two_stage")
    parser.add_argument("--intent-hypothesis-version", choices=("shopping-intent-v1", "shopping-intent-v2"), default="shopping-intent-v2")
    parser.add_argument("--intent-calibration", default="docs/baselines/intent-calibration-v2.json")
    parser.add_argument("--disable-model-switch", action="store_true")
    args = parser.parse_args()
    calibration = json.loads(Path(args.intent_calibration).read_text(encoding="utf-8")) if args.intent_mode != "off" else {}
    intent_root = Path(args.intent_model_dir)
    config = AgentConfig(
        catalog_path=Path(args.catalog),
        clarification_enabled=args.variant != "no-clarification",
        relaxation_enabled=args.variant != "no-relaxation",
        dense_enabled=args.dense,
        multiturn_state_enabled=args.state_events,
        intent_routing_enabled=args.route,
        intent_policy_enabled=args.policy,
        intent_model_mode=args.intent_mode,
        intent_model_path=intent_root if args.intent_mode != "off" else None,
        intent_manifest_path=intent_root / "intent-manifest.json" if args.intent_mode != "off" else None,
        intent_classifier_strategy=args.intent_strategy,
        intent_hypothesis_version=args.intent_hypothesis_version,
        intent_model_switch_enabled=not args.disable_model_switch,
        intent_initial_confidence=float(calibration.get("initial_confidence", 0.80)),
        intent_initial_margin=float(calibration.get("initial_margin", 0.15)),
        intent_switch_confidence=float(calibration.get("switch_confidence", 0.90)),
        intent_switch_margin=float(calibration.get("switch_margin", 0.20)),
        intent_timeout_ms=1000 if args.intent_mode != "off" else 100,
        config_version=(
            f"multiturn-{args.intent_mode}{'-no-switch' if args.disable_model_switch else ''}" if args.intent_mode != "off" else
            "multiturn-b3" if args.policy else
            "multiturn-b2" if args.route else
            "multiturn-b1" if args.state_events else
            "phase3-b0"
        ),
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
        "fallback_count": agent.fallback_count,
    }
    payload = {**result, "phase3_ablation": summary}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"variant": args.variant, "hit_rate_at_10": result["hit_rate_at_10"], "mrr": result["mrr"], "mttc": result["mttc"], "score": result["recommended_technical_score"], "p50_ms": summary["p50_ms"], "p95_ms": summary["p95_ms"]}, indent=2))


if __name__ == "__main__":
    main()
