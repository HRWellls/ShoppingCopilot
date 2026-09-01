# Shopping Copilot

Shopping Copilot is a headless conversational product-search Agent for the TikTok TechJam 2026 Shopping Copilot challenge. It turns a one-shot keyword query into a stateful shopping process: users can add constraints, change their mind, browse broadly, answer one useful clarification question, and receive catalog-valid recommendations within the ten-turn limit.

On the organizer-released 200-session public development set, the frozen deterministic configuration achieved:

| Metric | Official weak BM25 baseline | Shopping Copilot | Improvement |
|---|---:|---:|---:|
| HitRate@10 | 0.1250 | **0.9600** | +83.50 pp |
| MRR | 0.068034 | **0.606629** | +53.86 pp |
| MTTC | 9.810 | **2.585** | 7.225 fewer turns |
| Efficiency | 0.1190 | **0.8415** | +72.25 pp |
| TechnicalScore | 0.106710 | **0.830289** | +72.36 pp |

The frozen run used local deterministic rules and retrieval: `dense=false`, `llm=false`, `intent model=off`, with zero external model calls and zero contract-compatible fallbacks in that run.

## Problem

Static e-commerce search loses context when a shopper starts vague, adds a budget, changes a brand preference, switches between buying and browsing, or asks for an impossible combination. A useful shopping Agent must update only what changed, preserve every still-valid constraint, and avoid silently inventing or relaxing requirements.

## Solution

Shopping Copilot combines:

- **Buying/Browsing routing**: Buying prioritizes hard eligibility and precision; Browsing keeps scene context and result diversity.
- **Transactional multi-turn state**: every turn updates isolated session state atomically.
- **Slot-level override handling**: clear or replace only the conflicting preference instead of restarting the conversation.
- **Hard eligibility before ranking**: budget, explicit exclusions and catalog facts cannot be overridden by semantic similarity.
- **Useful clarification**: ask at most one high-value question when the candidate space is too broad, with late-turn protection.
- **Controlled relaxation**: when no result remains, relax only eligible preferences; never silently relax budget or explicit exclusions.
- **Protocol-safe output**: return at most ten unique `parent_asin` values that exist in the read-only catalog.

## Architecture

```text
message + user profile
  → rule parsing and event detection
  → transactional session-state reducer
  → Buying / Browsing route plan
  → hard eligibility filter
  → local retrieval and route-aware reranking
  → clarify / safely relax / recommend
  → catalog-valid Top 10 response
```

The official adapter remains small:

```python
from starter.agent import Agent

agent = Agent("data/catalog.jsonl")
agent.reset(session_id, user_profile)
response = agent.respond(session_id, user_message, turn, top_k=10)
```

See [Architecture](docs/architecture.md) for component and safety details.

## Repository Structure

```text
starter/                    official reset/respond adapter
src/                        state, NLU, retrieval, policy and output core
evaluator/                  deterministic public-set evaluator
scripts/                    supported setup, evaluation and validation commands
tests/                      unit, integration, protocol and retrieval tests
data/                       public sessions and small demo fixtures
demo/                       optional local browser walkthrough
docs/                       architecture, results, contract and attribution
```

Local catalogs, model/index caches, API secrets, traces and generated results are intentionally excluded from Git.

## Requirements

- Python 3.10 or newer; development and the frozen run used Python 3.12.
- The organizer catalog is required only for the full 200-session reproduction.
- The deterministic offline route uses no paid API.
- `requirements.txt` contains optional dense-retrieval dependencies (`NumPy`, `FAISS`, `sentence-transformers`) and is needed for the complete optional-module test surface.

## Setup and Installation

```bash
git clone https://github.com/HRWellls/Hamburgerr.git
cd Hamburgerr

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The repository includes `data/catalog_sample_100.jsonl`, so the self-check, browser demo and unit tests do not require the full catalog:

```bash
python -m scripts.delivery_self_check --json
```

## Data Preparation

The full evaluation catalog is not committed. Obtain the participant-kit `catalog.jsonl.gz` from the organizer release, decompress it, and place it at:

```text
data/catalog.jsonl
```

Verify the prepared files:

```bash
shasum -a 256 data/catalog.jsonl data/public_set.jsonl
```

Expected SHA-256 values:

```text
da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67  data/catalog.jsonl
857259f7a438e6188ac63e18995b6ff4489bfcfc4a716a798b9a2aa0ee8f7579  data/public_set.jsonl
```

Source and redistribution boundaries are documented in [Data and Asset Attribution](docs/data-attribution.md).

## Run the Browser Demo

The local browser walkthrough uses the retained 100-product sample by default:

```bash
python -m demo.app
```

Open  http://127.0.0.1:8765 . To use the full catalog:

```bash
HAMBURGERR_DEMO_CATALOG=data/catalog.jsonl python -m demo.app
```

## Reproduce the Results

Run the frozen D4 configuration on the full public set:

```bash
python -m scripts.run_public_set_local \
  --profile d4 \
  --output .runtime/final-public.json
```

This command uses `data/public_set.jsonl` and `data/catalog.jsonl`. It prints the aggregate and per-scenario metrics and writes detailed output under the ignored `.runtime/` directory.

For a quick execution smoke test:

```bash
python -m scripts.run_public_set_local \
  --profile d4 \
  --catalog data/catalog_sample_100.jsonl \
  --dataset data/sample_smoke.jsonl \
  --output .runtime/smoke.json
```

The sample-catalog smoke checks execution only; it does not reproduce the published quality score. See [Evaluation and Results](docs/results.md) and [machine-readable frozen evidence](docs/results/final-public.json).

## Run the Tests

```bash
python -m unittest discover -s tests -v
```

`tests/test_full_catalog_smoke.py` automatically skips when `data/catalog.jsonl` is unavailable. The remaining suite covers the Agent contract, session isolation, state updates, overrides, negation, filters, retrieval, clarification, dense fallback and evaluator behavior.

While the final team and public URLs are still pending, run:

```bash
python -m scripts.check_public_submission --allow-placeholders
```

Run the same command without `--allow-placeholders` for the final publication gate.

## Tools, APIs, Libraries and Data

- **Development tools**: Python 3.12, VS Code, Git/GitHub, terminal tooling and browser developer tools.
- **Core runtime**: Python standard library and in-memory/local indexes.
- **Optional libraries**: NumPy 2.5.2, FAISS CPU 1.12.0 and sentence-transformers 5.7.0 for the opt-in dense path.
- **Optional API**: a schema-bounded DeepSeek/OpenAI-compatible chat-completions parser is supported. It is disabled by default and was not called in the frozen run.
- **Dataset**: organizer competition package derived from Amazon Reviews 2023, `Clothing_Shoes_and_Jewelry`; 50,000 read-only products and 200 public development sessions.
- **Assets**: original text/UI demo assets; no third-party product images or logos are required.

### Model and API Cost

The reported D4 evaluation used no dense model, intent model or external LLM call. External API cost for that run was USD 0. Local CPU time and memory are still real runtime costs. API keys must be supplied through environment variables or a local ignored `api.env`; they are never committed or included in traces.

## Limitations

- The catalog is static and read-only; there is no live inventory, price or availability feed.
- Evaluation targets exact `parent_asin` matches, which is narrower than real user satisfaction.
- The system is text-only and single-process; it does not provide multimodal search or production concurrency guarantees.
- Rules remain weaker on spelling noise, implicit long-tail preferences and complex comparative language.
- Local latency measurements are not production SLAs.
- Business impact such as conversion or abandonment reduction still requires online experimentation.

## Future Improvements

- Connect a live catalog with inventory and price freshness.
- Add guarded semantic understanding only when it passes end-to-end quality, latency and cost gates.
- Calibrate clarification using real interaction feedback and candidate uncertainty.
- Add typo tolerance, multilingual queries and richer comparative reasoning.
- Validate conversion, satisfaction and hand-off hypotheses through controlled online experiments.


## Public Links

- Devpost: `TODO_SUBMISSION_DEVPOST_URL`
- Demo video: `TODO_SUBMISSION_VIDEO_URL`
- GitHub repository: `https://github.com/HRWellls/Hamburgerr.git`

## Security and Submission Notes

- Never commit `api.env`, `.env`, API keys, the full catalog, private evaluation data, model weights, FAISS indexes, runtime traces or generated evaluator output.
- The catalog is treated as read-only.
- Reported metrics come from the unmodified local evaluator and the canonical evidence under `docs/results/`.
- See [Agent API contract](docs/agent_api_contract.json), [evaluation configuration](docs/evaluation_config.json), [submission rules](docs/submission_rules.md), and [data attribution](docs/data-attribution.md).
