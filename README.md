# TechJam Conversational E-Commerce Search Challenge

Build an AI shopping agent that asks useful follow-up questions and recommends the customer's hidden target product within at most 10 turns.

## What You Receive

- A frozen catalog of 50,000 products from the `Clothing_Shoes_and_Jewelry` category of Amazon Reviews 2023.
- 200 labeled public sessions for local development.
- A weak BM25 starter agent and deterministic local evaluator.
- The Agent API contract and scoring rules.

The organizer keeps 800 additional sessions private for final evaluation.

## Task

For each session, your agent receives an anonymized preference profile and a short customer message. Raw user IDs, review text, timestamps, and purchase history are never disclosed. On every turn the agent may:

- ask a natural clarification question in `message` and identify one requested field in `ask_attribute`;
- return a ranked list of up to 10 catalog `parent_asin` values;
- do both in the same response.

The session ends when the target product appears in the scored Top 10 or after turn 10. Sessions cover Buying, Browsing, Intent Override, and Boundary behavior.

## Download the Catalog

Download `catalog.jsonl.gz` from the GitHub Release attached to this repository, then run:

```bash
gzip -dk catalog.jsonl.gz
mv catalog.jsonl data/catalog.jsonl
```

Verify the downloaded file using the published `SHA256SUMS` file.

## Run the Starter

Python 3.10 or later is recommended. The starter uses only the Python standard library.

```bash
python3 -m evaluator.local_evaluator
```

Edit `starter/agent.py` to implement your system. Do not edit the evaluator or public labels when reporting your local score.
The command writes per-session results and aggregate metrics to `results.json`.

The included weak BM25 starter scores Hit Rate@10 `0.125`, MRR `0.068034`, and
MTTC `9.81` on the released public set. See `docs/baseline_results.json`.

## Stage 2 MVP

The editable Agent now uses the deterministic Stage 2 framework described in `技术文档.md`:

```text
starter.Agent (official adapter)
  -> SessionStateStore
  -> rule intent and constraint parsing
  -> read-only CatalogStore and hard filters
  -> in-memory SQLite FTS5 BM25
  -> Top 10 sanitization
  -> optional JSONL trace
```

The implementation remains single-process, offline, and standard-library only. The catalog is normalized and the FTS5 index is built once when `Agent` starts. Session state is keyed by the official `session_id`; `reset` replaces all prior state for that identifier. Explicit budget, brand, color, material, category, and size constraints are applied before final ranking. Missing prices do not satisfy an explicit budget.

The official entry point remains unchanged:

```python
from starter.agent import Agent

agent = Agent("data/catalog.jsonl")
agent.reset(session_id, user_profile)
response = agent.respond(session_id, user_message, turn, top_k=10)
```

Every response is sanitized to at most 10 unique catalog-valid `parent_asin` values. Invalid input, unknown sessions, index errors, and unexpected component failures return a contract-compatible deterministic fallback without exposing a stack trace. Controlled errors use codes such as `E_INPUT_TYPE`, `E_PROTOCOL`, `E_INDEX_NOT_READY`, `E_EMPTY_RESULT`, and `E_RETRIEVAL` in local traces.

### Tests

Run all unit, integration, evaluator, and catalog smoke tests:

```bash
python3 -m unittest discover -s tests -v
```

`tests/test_full_catalog_smoke.py` loads all 50,000 products when `data/catalog.jsonl` is present. It is skipped when the release catalog has not been downloaded.

### Evaluation and engineering metrics

Run the unmodified official evaluator and keep its generated result local:

```bash
mkdir -p .runtime
python3 -m evaluator.local_evaluator --output .runtime/phase2-public-results.json
```

Run the instrumentation wrapper for initialization time, per-turn latency, contract validation, and session-isolation checks. It calls the same public evaluator functions and does not alter labels or scoring:

```bash
python3 -m scripts.phase2_benchmark --output .runtime/phase2-validation.json
```

The Stage 2 validation run on the included 200 sessions completed with 0 contract failures and 0 session-leakage failures. Local metrics were Hit Rate@10 `0.14`, MRR `0.076442`, and MTTC `9.665`; the official weak-baseline record in `docs/baseline_results.json` is intentionally unchanged.

### Optional trace

Tracing is disabled by default. Enable it explicitly when constructing the Agent:

```python
from pathlib import Path

from src.config import AgentConfig
from starter.agent import Agent

config = AgentConfig(
    catalog_path=Path("data/catalog.jsonl"),
    trace_enabled=True,
    trace_path=Path(".runtime/turns.jsonl"),
)
agent = Agent(config=config)
```

Each JSONL event contains routing, constraint names, filter counts, candidate count, returned Top 10, latency, fallback status, error code, and config version. It excludes raw messages, full profiles, credentials, ground truth, and private evaluator state. Trace I/O failure degrades logging only and never retries or changes retrieval.

### Later phases

Stage 2 intentionally does not include dense retrieval, RRF fusion, complete override/negation/TTL handling, progressive relaxation, reranking, Verifier, or adaptive clarification. Those remain Stage 3 and Stage 4 work so the current baseline stays deterministic and independently testable.

## Agent Interface

```python
class Agent:
    def reset(self, session_id: str, user_profile: dict) -> None:
        ...

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        return {
            "message": "Do you have a material preference?",
            "ask_attribute": "material",
            "recommendations": [
                {"parent_asin": "B000..."},
                {"parent_asin": "B001..."}
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30}
        }
```

`ask_attribute` is one of `category`, `material`, `color`, `size`, `style`, `brand`, `budget`, `feature`, `use_case`, `other`, or `null`. See `docs/agent_api_contract.json`.

## Technical Metrics

- **Hit Rate@10:** fraction of sessions that find the target within 10 turns.
- **MRR:** mean reciprocal rank of the target; a miss contributes zero.
- **MTTC:** mean first-hit turn; a miss is assigned turn 11.
- **Reported token usage:** prompt and completion tokens returned by the team's model client.

```text
TechnicalScore = 0.50 × HitRate@10 + 0.30 × MRR + 0.20 × Efficiency
Efficiency = clip((11 - MTTC) / 10, 0, 1)
```

Only exact `parent_asin` equality produces a hit. Core metrics are also reported by scenario.

## Model Choice and Cost

Teams may use any legally accessible LLM API or local model. Teams manage their own credentials and must never commit API keys. Model choice, estimated cost, token usage, and latency must be disclosed. Token usage is a feasibility metric, not part of the core technical score. The organizer does not provide or reimburse model API credits; teams are responsible for any costs incurred through optional external services.

## Files

```text
data/public_set.jsonl             200 labeled development sessions
docs/competition_specification.md participant rules and evaluation protocol
docs/agent_api_contract.json      machine-readable Agent contract
docs/evaluation_config.json       scoring configuration
docs/baseline_results.json        reproducible weak-starter reference score
starter/agent.py                  editable weak starter
evaluator/local_evaluator.py      public-set simulator and scorer
src/                              Stage 2 typed Agent core
scripts/phase2_benchmark.py       local engineering-metric wrapper
```

## Judging and Submission Policy

- Participant submission requirements: `docs/submission_rules.md`
- Participant release checklist: `docs/participant_release_checklist.md`
- Organizer-only final judging controls: `organizer/JUDGING_RUNBOOK.md`
- Organizer private release checklist: `organizer/private_release_checklist.md`
- Judging day operations SOP: `organizer/JUDGING_DAY_SOP.md`

## Data Source

The catalog and sessions are derived from Amazon Reviews 2023 by McAuley Lab, UCSD. See `DATA_ATTRIBUTION.md` before using or redistributing the data.
Sessions are sampled deterministically from the official Clothing 5-core leave-last-out split and joined to the frozen catalog.
