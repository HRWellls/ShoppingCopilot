from __future__ import annotations

import argparse
import json
import statistics
import time
import tracemalloc
from collections import Counter
from pathlib import Path

from src.config import AgentConfig
from src.models import IntentState, SessionState
from src.nlu import RuleConstraintExtractor, RuleEventDetector
from src.nlu.intent.nli import load_intent_classifier


def f1_for(label: str, expected: list[str], predicted: list[str]) -> float:
    true_positive = sum(a == label and b == label for a, b in zip(expected, predicted))
    false_positive = sum(a != label and b == label for a, b in zip(expected, predicted))
    false_negative = sum(a == label and b != label for a, b in zip(expected, predicted))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the local shopping intent classifier and rule events")
    parser.add_argument("--dataset", default="data/intent_eval_v1.jsonl")
    parser.add_argument("--split", choices=("calibration", "test"), default="test")
    parser.add_argument("--model-dir", default=".runtime/models/nli-deberta-v3-xsmall")
    parser.add_argument("--output", default=".runtime/intent-shadow-test.json")
    parser.add_argument("--strategy", choices=("single", "two_stage"), default="single")
    parser.add_argument("--hypothesis-version", choices=("shopping-intent-v1", "shopping-intent-v2"), default="shopping-intent-v1")
    parser.add_argument("--calibration", help="Optional calibration JSON; only thresholds are read")
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line]
    selected = [row for row in rows if row["split"] == args.split]
    root = Path(args.model_dir)
    calibration = json.loads(Path(args.calibration).read_text(encoding="utf-8")) if args.calibration else {}
    config = AgentConfig(
        intent_model_mode="shadow",
        intent_model_path=root,
        intent_manifest_path=root / "intent-manifest.json",
        intent_timeout_ms=1000,
        intent_classifier_strategy=args.strategy,
        intent_hypothesis_version=args.hypothesis_version,
        intent_initial_confidence=float(calibration.get("initial_confidence", 0.80)),
        intent_initial_margin=float(calibration.get("initial_margin", 0.15)),
        intent_switch_confidence=float(calibration.get("switch_confidence", 0.90)),
        intent_switch_margin=float(calibration.get("switch_margin", 0.20)),
    )
    tracemalloc.start()
    initialized = time.perf_counter()
    classifier = load_intent_classifier(config)
    initialization_ms = (time.perf_counter() - initialized) * 1000
    extractor, detector = RuleConstraintExtractor(), RuleEventDetector()
    expected: list[str] = []
    predicted: list[str] = []
    latencies: list[float] = []
    event_totals: Counter[str] = Counter()
    event_hits: Counter[str] = Counter()
    for row in selected:
        state = SessionState(
            str(row["id"]),
            turn_count=1,
            intent=str(row.get("prior_intent", "unknown")),
            intent_state=IntentState(str(row.get("prior_intent", "unknown")), 0.9, "fixture", 1),
            last_asked_slot=row.get("last_asked_slot"),
        )
        message = str(row["message"])
        if row["kind"] == "event":
            parsed = extractor.parse(message, state)
            events = detector.detect(message, state, parsed)
            expected_event = str(row["expected_event"])
            event_totals[expected_event] += 1
            if any(event.kind == expected_event and (row.get("expected_target") is None or event.target_intent == row["expected_target"]) for event in events):
                event_hits[expected_event] += 1
            continue
        started = time.perf_counter()
        observation = classifier.classify(state, message)
        latencies.append((time.perf_counter() - started) * 1000)
        expected.append(str(row["expected_intent"]))
        predicted.append(observation.label)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    labels = ("buying", "browsing", "continue")
    per_label_f1 = {label: f1_for(label, expected, predicted) for label in labels}
    continue_total = sum(value == "continue" for value in expected)
    continue_hits = sum(a == "continue" and b == "continue" for a, b in zip(expected, predicted))
    buying_total = sum(value == "buying" for value in expected)
    buying_to_browsing = sum(a == "buying" and b == "browsing" for a, b in zip(expected, predicted))
    event_recall = {name: event_hits[name] / total for name, total in event_totals.items()}
    report = {
        "dataset": args.dataset,
        "split": args.split,
        "sample_count": len(selected),
        "intent_sample_count": len(expected),
        "macro_f1": statistics.fmean(per_label_f1.values()),
        "per_label_f1": per_label_f1,
        "buying_to_browsing_rate": buying_to_browsing / buying_total if buying_total else 0.0,
        "continue_recall": continue_hits / continue_total if continue_total else 0.0,
        "event_recall": event_recall,
        "initialization_ms": initialization_ms,
        "p50_ms": statistics.median(latencies) if latencies else 0.0,
        "p95_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0.0,
        "peak_python_bytes": peak,
        "prediction_counts": dict(Counter(predicted)),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
