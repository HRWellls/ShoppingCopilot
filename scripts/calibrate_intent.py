from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from src.config import AgentConfig
from src.models import IntentState, SessionState
from src.nlu.intent.nli import load_intent_classifier
from scripts.evaluate_intent_model import f1_for


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate resolver thresholds from the calibration split only")
    parser.add_argument("--dataset", default="data/intent_eval_v1.jsonl")
    parser.add_argument("--model-dir", default=".runtime/models/nli-deberta-v3-xsmall")
    parser.add_argument("--output", default="docs/baselines/intent-calibration-v2.json")
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line]
    rows = [row for row in rows if row["split"] == "calibration" and row["kind"] != "event"]
    root = Path(args.model_dir)
    config = AgentConfig(
        intent_model_mode="shadow",
        intent_model_path=root,
        intent_manifest_path=root / "intent-manifest.json",
        intent_timeout_ms=1000,
        intent_classifier_strategy="two_stage",
        intent_hypothesis_version="shopping-intent-v2",
        intent_initial_margin=0.0,
    )
    classifier = load_intent_classifier(config)
    observations = []
    for row in rows:
        state = SessionState(
            str(row["id"]),
            turn_count=1,
            intent=str(row.get("prior_intent", "unknown")),
            intent_state=IntentState(str(row.get("prior_intent", "unknown")), 0.9, "fixture", 1),
            last_asked_slot=row.get("last_asked_slot"),
        )
        result = classifier.classify(state, str(row["message"]))
        observations.append((str(row["expected_intent"]), result.label, result.confidence, result.margin))
    best = None
    for threshold in [value / 100 for value in range(0, 51)]:
        expected = [row[0] for row in observations]
        predicted = [row[1] if row[3] >= threshold else "unknown" for row in observations]
        macro = statistics.fmean(f1_for(label, expected, predicted) for label in ("buying", "browsing", "continue"))
        buying_total = sum(label == "buying" for label in expected)
        buying_to_browsing = sum(a == "buying" and b == "browsing" for a, b in zip(expected, predicted)) / buying_total
        candidate = (macro if buying_to_browsing < 0.05 else -1.0, threshold, buying_to_browsing)
        if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] > best[1]):
            best = candidate
    assert best is not None
    selected_margin = best[1]
    accepted_correct_confidences = sorted(
        confidence for expected, predicted, confidence, margin in observations
        if expected == predicted and margin >= selected_margin and expected in {"buying", "browsing"}
    )
    percentile_index = max(0, int(len(accepted_correct_confidences) * 0.05) - 1)
    initial_confidence = accepted_correct_confidences[percentile_index] if accepted_correct_confidences else 1.0
    report = {
        "version": "intent-calibration-v2",
        "dataset": args.dataset,
        "split": "calibration",
        "sample_count": len(rows),
        "hypothesis_version": "shopping-intent-v2",
        "resolver_version": "intent-resolver-v1",
        "strategy": "two_stage",
        "initial_confidence": initial_confidence,
        "initial_margin": selected_margin,
        "switch_confidence": min(1.0, max(initial_confidence, 0.80)),
        "switch_margin": min(1.0, max(selected_margin, 0.10)),
        "calibration_macro_f1": best[0],
        "buying_to_browsing_rate": best[2],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
