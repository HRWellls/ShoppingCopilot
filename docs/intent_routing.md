# Multi-turn Intent Routing Operations

The intent-aware shopping path is controlled by independent feature flags. All flags default to disabled, so a clean installation runs the existing rule and BM25 path without ONNX Runtime, Transformers, or an intent artifact.

## Modes and release default

- `off`: does not import or load the NLI runtime. Rule evidence alone resolves intent.
- `shadow`: runs the local classifier and emits sanitized telemetry, but cannot change state, routing, retrieval, policy, or candidates.
- `active`: permits qualified model observations to participate in the resolver after explicit rules and valid continuations. Model output can never create events or mutate slots directly.

The selected release default is `off`. The B3 rule-only route passed its quality gate with TechnicalScore `0.331459`. Active D scored `0.309576`, regressed Intent Override Hit@10, and exceeded the approved p95 overhead, so the automated gate rejected it. Shadow remains suitable for measurement because it is behaviorally identical to off.

Enable the complete B3 path explicitly:

```python
from pathlib import Path

from src.config import AgentConfig

config = AgentConfig(
    catalog_path=Path("data/catalog.jsonl"),
    multiturn_state_enabled=True,
    intent_routing_enabled=True,
    intent_policy_enabled=True,
    intent_model_mode="off",
)
```

## Offline artifact setup

Artifact acquisition is an explicit preparation action. Agent startup and inference never download, train, convert, or overwrite model files.

```bash
python -m scripts.prepare_intent_artifact .runtime/models/nli-deberta-v3-xsmall \
  --download \
  --hypothesis-version shopping-intent-v2

python -m scripts.prepare_intent_artifact .runtime/models/nli-deberta-v3-xsmall --verify
```

For shadow evaluation, configure `intent_model_mode="shadow"`, set `intent_model_path` to that directory, select `intent_classifier_strategy="two_stage"` and `intent_hypothesis_version="shopping-intent-v2"`, and apply the thresholds from `docs/baselines/intent-calibration-v2.json`. A missing file, checksum mismatch, unsupported provider, invalid ONNX interface, timeout, or inference error falls back to the frozen B3 behavior.

## Reproduce the reports

```bash
python -m scripts.phase3_benchmark --state-events --route --policy --intent-mode off --output .runtime/multiturn-b3.json
python -m scripts.phase3_benchmark --state-events --route --policy --intent-mode shadow --output .runtime/multiturn-c-shadow.json
python -m scripts.phase3_benchmark --state-events --route --policy --intent-mode active --output .runtime/multiturn-d-active.json
python -m scripts.phase3_benchmark --state-events --route --policy --intent-mode active --disable-model-switch --output .runtime/multiturn-e-no-switch.json
python -m scripts.check_multiturn_gate .runtime/multiturn-b3.json
python -m scripts.check_active_gate
python -m scripts.check_multiturn_static
```

Frozen release reports are under `docs/baselines/`: `multiturn-b3.json`, `intent-calibration-v2.json`, `intent-v2-test.json`, `multiturn-model-ablation.json`, and `release-evidence.json`.

## Rollback

Set `intent_model_mode="off"` to disable the model immediately. If the route or policy itself must be rolled back, also set `intent_routing_enabled=False`, `intent_policy_enabled=False`, and `multiturn_state_enabled=False`. Existing sessions require no migration: model observations are not persisted as events or slot values, and the transactional reducer preserves the same session contract.
