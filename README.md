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

Python 3.10 or later is recommended. The BM25 fallback uses only the standard library; persistent dense retrieval uses the dependencies in `requirements.txt`.

Create the project environment and install the dense-retrieval dependencies:

```bash
/opt/anaconda3/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

```bash
python3 -m evaluator.local_evaluator
```

Edit `starter/agent.py` to implement your system. Do not edit the evaluator or public labels when reporting your local score.
The command writes per-session results and aggregate metrics to `results.json`.

The included weak BM25 starter scores Hit Rate@10 `0.125`, MRR `0.068034`, and
MTTC `9.81` on the released public set. See `docs/baseline_results.json`.

## Stage 2 MVP and Stage 3 Hybrid State

The editable Agent now uses the deterministic Stage 2 framework described in `技术文档.md`:

```text
starter.Agent (official adapter)
  -> SessionStateStore
  -> rule or optional DeepSeek structured parsing
  -> typed slots, override, negation, and TTL
  -> read-only CatalogStore, hard filters, and safe relaxation
  -> Buying/Browsing BM25 + optional dense retrieval
  -> weighted RRF and a wide candidate pool
  -> clarification policy and late-turn protection
  -> Top 10 sanitization
  -> optional JSONL trace
```

The default implementation remains single-process and offline. Dense and LLM routes are disabled by default, so the Agent always has a rule + BM25 path. The catalog is normalized and the FTS5 index is built once when `Agent` starts. Session state is keyed by the official `session_id`; `reset` replaces all prior state for that identifier. Explicit budget, brand, color, material, category, size, and exclusions are applied before final ranking. Missing prices do not satisfy an explicit budget.

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

### Developer delivery and visual demo

Run the startup self-check and capture a redacted reproducible baseline:

```bash
python -m scripts.delivery_self_check --json
python -m scripts.capture_baseline --output .runtime/baseline.json
```

Launch the dependency-light conversation demo (sample catalog, offline BM25 fallback):

```bash
python -m demo.app
# open http://127.0.0.1:8765
```

See `开发者交付总结与操作指南.md` for the complete delivery checklist and rollback notes.

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

Run the Stage 3 default state/clarification configuration with the same wrapper:

```bash
python3 -m scripts.phase2_benchmark --output .runtime/phase3-bm25-state-validation.json
```

The Stage 3 run completed with Hit Rate@10 `0.31`, MRR `0.212282`, MTTC `8.685`, 0 contract failures, and 0 session-leakage failures. See `docs/phase3_results.md` for scenario metrics and experiment boundaries.

Run the Stage 3 ablations when comparing dialogue contributions:

```bash
python3 -m scripts.phase3_benchmark --variant full --output .runtime/phase3-full.json
python3 -m scripts.phase3_benchmark --variant no-clarification --output .runtime/phase3-no-clarification.json
python3 -m scripts.phase3_benchmark --variant no-relaxation --output .runtime/phase3-no-relaxation.json
```

On the released public set, `no-clarification` returned to the Stage 2 score (`0.119633`), `no-relaxation` scored `0.255585`, and the full variant scored `0.264985`. These runs use dense and LLM disabled, so they are deterministic and do not require an API key.

`no-clarification` disables follow-up questions: the Agent returns its current Top 10 without asking for a missing category, budget, size, color, brand, or material. `no-relaxation` keeps clarification but disables safe empty-result recovery: if all hard filters produce no candidates, the Agent does not retry after removing brand, color/material, or expanding a category synonym. Budget and explicit exclusions are never silently relaxed in either mode.

### Multi-turn intent routing

The optional multi-turn path adds transactional event reduction, Buying/Browsing-specific retrieval, and route-aware clarification. The local NLI classifier supports `off`, observational `shadow`, and gated `active` modes; its release default is `off` because the active end-to-end ablation did not beat the B3 rule-only gate. Model-off needs no optional NLI dependencies or artifact, and runtime code never downloads model files.

See `docs/intent_routing.md` for feature flags, offline artifact preparation and verification, benchmark commands, frozen report locations, failure fallback, and rollback steps.

### Persistent dense retrieval

Dense retrieval requires NumPy plus a locally available sentence-transformers model. The Agent never downloads a model during startup. Configure a local path explicitly:

On macOS, the FAISS and PyTorch wheels may ship separate OpenMP runtimes; the dense module sets `KMP_DUPLICATE_LIB_OK=TRUE` before loading them to avoid a process abort. Dense inference remains single-process.

```python
config = AgentConfig(
    catalog_path=Path("data/catalog.jsonl"),
    dense_enabled=True,
    dense_model_id="your-local-model-id",
    dense_model_path=Path("/path/to/cached/model"),
    dense_index_path=Path(".runtime/indexes/catalog-all-MiniLM-L6-v2.faiss"),
)
```

The generated FAISS file contains normalized product vectors plus a JSON manifest keyed by catalog checksum, model/version, dimension, normalization, backend, and config version. It remains under `.runtime/` and must not be committed. When the default catalog and matching files exist, `Agent("data/catalog.jsonl")` loads this index directly; it does not re-embed products. If the index/model is unavailable or its manifest mismatches, the Agent records a controlled fallback and continues with BM25.

Normal Agent startup has `dense_build_allowed=False`: it will never rebuild or overwrite FAISS. Only the explicit build command enables writes.

Build the persistent index once with:

```bash
.venv/bin/python -m scripts.build_dense_index
```

The command embeds exactly the 50,000 records from `data/catalog.jsonl`. Use `--force` only after changing the catalog or embedding model.

For routine testing, use the fixed 8-session stratified set instead of all 200 sessions:

```bash
.venv/bin/python -m scripts.phase3_benchmark \
  --dataset data/public_smoke.jsonl \
  --dense \
  --output .runtime/phase3-dense-smoke.json
```

`data/public_smoke.jsonl` contains 2 sessions from each of Buying, Browsing, Intent Override, and Boundary. Regenerate it deterministically with `python -m scripts.make_smoke_dataset`.

### Optional DeepSeek parser

`deepseek-v4-flash` is configured as a schema-bounded parser, not as an ASIN selector or tool-running agent. Keep the API key in the environment or in local `api.env` with mode 0600:

```bash
export DEEPSEEK_API_KEY="..."
# or: chmod 600 api.env
```

Enable it explicitly:

```python
config = AgentConfig(
    catalog_path=Path("data/catalog.jsonl"),
    llm_enabled=True,
    llm_model="deepseek-v4-flash",
    llm_endpoint="https://api.deepseek.com/chat/completions",
    llm_timeout_ms=600,
)
agent = Agent(config=config)
```

Environment variables take precedence over `api.env`. Missing keys, unsafe file permissions, HTTP/auth failures, timeouts, malformed JSON, unknown fields, and missing usage all fall back to deterministic rules. Secrets and raw model responses are excluded from trace and config snapshots.

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

Stage 3 provides dense/RRF boundaries, structured state, override/negation, safe relaxation, and basic clarification. Cross-Encoder/LLM reranking, Verifier, entropy/margin policy, and information-gain calibration remain Stage 4 work.

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
data/public_smoke.jsonl           8-session stratified smoke set
docs/competition_specification.md participant rules and evaluation protocol
docs/agent_api_contract.json      machine-readable Agent contract
docs/evaluation_config.json       scoring configuration
docs/baseline_results.json        reproducible weak-starter reference score
starter/agent.py                  editable weak starter
evaluator/local_evaluator.py      public-set simulator and scorer
src/                              Stage 2/3 typed Agent core
scripts/phase2_benchmark.py       local engineering-metric wrapper
scripts/phase3_benchmark.py       Stage 3 ablation wrapper
scripts/build_dense_index.py      one-time 50k product FAISS builder
scripts/make_smoke_dataset.py     stratified smoke-set generator
docs/phase3_results.md            Phase 3 experiment record
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
