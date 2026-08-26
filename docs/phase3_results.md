# Phase 3 Validation Record

Date: 2026-08-26

## Environment

- Catalog rows: 50,000
- Catalog checksum: `da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67`
- Public sessions: 200
- Dense libraries: NumPy available; sentence-transformers and FAISS unavailable
- Secrets: local `api.env`, ignored by Git, mode 0600; value never recorded

## Public evaluator comparison

| Variant | Hit@10 | MRR | MTTC | TechnicalScore | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| Phase 2 rules + BM25 | 0.1400 | 0.076442 | 9.665 | 0.119633 | 9.832 ms | 46.351 ms |
| Phase 3 state + BM25 | 0.3100 | 0.212282 | 8.685 | 0.264985 | 17.335 ms | 79.883 ms |

Phase 3 scenario metrics:

| Scenario | Hit@10 | MRR | MTTC |
|---|---:|---:|---:|
| Buying | 0.3125 | 0.188676 | 8.0125 |
| Browsing | 0.3500 | 0.237862 | 8.9000 |
| Intent Override | 0.2000 | 0.177778 | 9.633333 |
| Boundary | 0.3000 | 0.300000 | 9.5000 |

The Phase 3 run completed 1,599 turn calls with 0 contract failures and 0 session-leakage failures. Output is stored locally at `.runtime/phase3-bm25-state-validation.json`.

## Dense experiment

The initial Phase 3 run skipped dense because no model or FAISS environment was installed. A subsequent persistent-index setup used Python 3.12, `faiss-cpu==1.12.0`, and `sentence-transformers/all-MiniLM-L6-v2`:

- Product source: `data/catalog.jsonl` (50,000 rows)
- Index: `.runtime/indexes/catalog-all-MiniLM-L6-v2.faiss`
- Manifest: `.runtime/indexes/catalog-all-MiniLM-L6-v2.faiss.manifest.json`
- Backend: FAISS `IndexFlatIP`
- Dimension: 384
- Index records: 50,000
- Index size: approximately 73 MB
- First build time: approximately 250 seconds

Normal Agent startup loads the persisted index and has no permission to rebuild it. An 8-session stratified smoke run completed successfully with dense enabled; that sample is only a chain-health check and is not used as a quality estimate.

## DeepSeek connectivity experiment

- Model: `deepseek-v4-flash`
- Mode: explicit one-turn opt-in
- Outcome: controlled `E_MODEL_TIMEOUT`
- Observed latency: approximately 759 ms
- Token usage: 0 reported
- Estimated API cost: 0 from the failed request
- Fallback rate: 100% for this one connectivity attempt

The request did not expose the API key or response body. A full 200-session LLM run was not performed because connectivity did not satisfy the configured 600 ms budget; deterministic rule parsing remained available.

## Ablation

- Full Stage 3 state, relaxation, and clarification: TechnicalScore `0.264985`
- Clarification disabled: TechnicalScore `0.119633`
- Relaxation disabled: TechnicalScore `0.255585`

All ablations used dense and LLM disabled. The no-clarification run matched the Phase 2 baseline, while safe relaxation provided a smaller additional gain.
