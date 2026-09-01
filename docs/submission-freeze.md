# Public Submission Freeze

This document records the repository-cleanup decisions and the evidence boundary for the public submission.

## Tracked-file inventory and retention matrix

| Area | Approximate tracked contents before cleanup | Reverse-reference finding | Decision |
|---|---:|---|---|
| `starter/`, `src/`, `evaluator/` | Agent adapter, runtime pipeline, evaluator | Imported by the official entry point, tests, demo and reproduction command | **KEEP** |
| `tests/` | 20 test modules plus fixtures | Covers protocol, state, retrieval, dense fallback, routing and evaluator behavior | **KEEP** |
| `scripts/` | 21 development/evaluation helpers | Final workflow needs `run_public_set_local`, demo/self-check helpers and scripts imported by retained tests; phase/report-only helpers have no final consumer | **KEEP selectively / REMOVE obsolete** |
| `data/public_set.jsonl` | 200 organizer-released development sessions, 88 KB | Required by evaluator and final score reproduction | **KEEP** |
| `data/catalog_sample_100.jsonl` | 100-product sample, 126 KB | Required by the dependency-light browser demo and self-check | **KEEP** |
| `data/public_smoke.jsonl` | 8 stratified sessions, 3 KB | Used for fast evaluation smoke | **KEEP** |
| `data/catalog.jsonl` | 50,000 products, about 58 MB | Required for full evaluation; already ignored | **LOCAL-ONLY**, document placement/checksum |
| `data/catalog_sample_500.jsonl`, `intent_eval_v1.jsonl`, `owntest*.jsonl` | Self-built/sample experiment data, about 1.1 MB | Used only by development experiments or non-public generalization claims | **REMOVE** |
| `docs/` and root internal Markdown | 17 technical/history files plus 9 root planning files | Final facts overlap; many links point to phase-specific commands and reports | **CONSOLIDATE** into architecture, results, attribution and submission docs |
| `docs/baselines/` | 9 phase/model reports | Some are referenced only by optional experimental scripts/tests | **REMOVE obsolete**, retain only fixtures required by retained tests or final evidence |
| `runresult/` | 9 timestamped raw evaluator JSON files, about 600 KB | Source for frozen metrics but unsuitable as the canonical public surface | **CONSOLIDATE** one summary, then **REMOVE** |
| `Owndocs/` | 12 internal analysis/process documents, including an 847 KB trace report | No runtime imports; attribution and final facts can be moved | **CONSOLIDATE**, then **REMOVE** |
| `demo/` | Runnable browser demo, 7 internal docs, 54 rendered PNGs | `demo/app.py` and `demo/index.html` are runnable; docs/assets are recording support | **KEEP app/UI**, **REMOVE docs/assets** |
| `video/` | 54 rendered PNGs, recording workbench, backups, logs and one-off JS/PowerShell scripts | Not imported by the product; final deliverable is an external YouTube video | **REMOVE from public tree** after local recording backup |
| `.runtime/`, `.venv/`, `api.env`, caches, `autoresearch-results/` | Local-only data, models, secrets and generated output | Already ignored; must not be deleted by cleanup | **LOCAL-ONLY** |

Tracked sizes and references were checked with `git ls-files`, `stat`, and `rg` before deletion. The cleanup keeps any script directly imported by a retained test or referenced by a final public command.

## Redistribution boundary

- `data/public_set.jsonl` is the organizer-released public development set and remains for reproducibility.
- `data/catalog_sample_100.jsonl` remains as the minimal, text-only demo fixture already shipped in the participant workspace.
- The full `data/catalog.jsonl` remains ignored. Reviewers must obtain the organizer-provided 50,000-product catalog and verify its SHA-256 checksum.
- Self-built session sets, generated intent-evaluation data, raw result directories, model weights, indexes, traces and private evaluation data are not published.
- Underlying catalog metadata is derived from Amazon Reviews 2023 and remains subject to the source dataset terms described in `docs/data-attribution.md`.

## Frozen result

- Profile: `d4` / config version `retrieval-d4`
- Dataset: `data/public_set.jsonl`, 200 sessions
- Catalog: `data/catalog.jsonl`, 50,000 products
- Dense retrieval: disabled
- External LLM: disabled
- Intent model: off
- Trace: disabled
- Reproduction: `python -m scripts.run_public_set_local --profile d4 --output .runtime/final-public.json`
- Canonical evidence: `docs/results/final-public.json`

## Finalization placeholders

These values are intentionally unresolved until the submission accounts and final team details are available:

- Team member names and contribution mapping: `TODO_SUBMISSION_TEAM`
- Public GitHub repository: `TODO_SUBMISSION_REPOSITORY_URL`
- Public YouTube demo: `TODO_SUBMISSION_VIDEO_URL`
- Devpost project URL: `TODO_SUBMISSION_DEVPOST_URL`

The frozen run used no external model/API calls, so reported external API cost is **USD 0 for that run**. Local compute still has a runtime cost.
