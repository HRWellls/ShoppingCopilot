# Evaluation and Results

## Protocol

The deterministic local evaluator runs each session for at most ten turns. A hit occurs only when the exact target `parent_asin` appears in the first ten unique, catalog-valid recommendations. The reported score is:

```text
Efficiency = clip((11 - MTTC) / 10, 0, 1)
TechnicalScore = 0.50 × HitRate@10 + 0.30 × MRR + 0.20 × Efficiency
```

The frozen result uses the organizer-released 200-session public development set and the read-only 50,000-product catalog. Dense retrieval, the external LLM parser and the intent model were disabled.

## Headline result

| Metric | Official weak BM25 baseline | Shopping Copilot D4 | Change |
|---|---:|---:|---:|
| HitRate@10 | 0.1250 | **0.9600** | +83.50 pp |
| MRR | 0.068034 | **0.606629** | +53.86 pp |
| MTTC | 9.810 | **2.585** | 7.225 fewer turns |
| Efficiency | 0.1190 | **0.8415** | +72.25 pp |
| TechnicalScore | 0.106710 | **0.830289** | +72.36 pp |

MTTC is a turn count, so its improvement is not expressed in percentage points.

## Scenario breakdown

| Scenario | Sessions | HitRate@10 | MRR | MTTC |
|---|---:|---:|---:|---:|
| Buying | 80 | 0.9625 | 0.577540 | 2.1375 |
| Browsing | 80 | 0.9750 | 0.556741 | 2.2875 |
| Intent Override | 30 | 1.0000 | 0.876667 | 3.8000 |
| Boundary | 10 | 0.7000 | 0.428333 | 4.9000 |

## Engineering measurements

- Initialization: 53.338836 seconds
- Response p50: 27.248 ms
- Response p95: 48.044 ms
- Contract-compatible fallbacks in this run: 0
- External model/API calls in this run: 0

Latency values are local measurements from one frozen run, not a production SLA. Initialization includes loading and indexing the 50,000-product local catalog.

## Reproduce

After placing the organizer catalog at `data/catalog.jsonl`:

```bash
python -m scripts.run_public_set_local \
  --profile d4 \
  --output .runtime/final-public.json
```

For a quick functional check using the retained stratified smoke set:

```bash
python -m scripts.run_public_set_local \
  --profile d4 \
  --catalog data/catalog_sample_100.jsonl \
  --dataset data/public_smoke.jsonl \
  --output .runtime/smoke.json
```

The small catalog smoke validates execution, not the published quality score. Machine-readable frozen evidence is stored in `docs/results/final-public.json`.

## Evidence boundary

Self-built 100-session and 500-session generalization fixtures are not part of the cleaned public repository, so their historical metrics are intentionally omitted from README and Devpost. This prevents an unverifiable secondary claim from being presented alongside the reproducible public score.
