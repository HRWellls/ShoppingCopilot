# Shopping Copilot Architecture

Shopping Copilot is a headless conversational retrieval Agent that maintains the shopper's current valid intent across at most ten turns. The official integration surface remains `starter.Agent.reset()` and `starter.Agent.respond()`.

## Runtime flow

```text
User message + session profile
        │
        ▼
Rule parsing and event detection
        │  override · clear · negation · no preference · route switch
        ▼
Transactional session-state reduction
        │  retain valid slots, invalidate only conflicting state
        ▼
Buying / Browsing route plan
        │
        ▼
Hard eligibility filter
        │  budget, exclusions, category, brand, colour, material, size
        ▼
Local candidate retrieval and route-aware reranking
        │
        ▼
Clarify / safely relax / recommend
        │
        ▼
Catalog-valid, unique Top 10 response
```

## Components

- `starter/agent.py` preserves the challenge API and delegates to the product core.
- `src/core.py` orchestrates parsing, event detection, intent resolution, transactional state, retrieval, policy, output sanitation and optional trace recording.
- `src/state/` owns isolated session state, turn transactions, overrides and slot reduction.
- `src/nlu/` provides deterministic rules and optional bounded model adapters. The frozen result uses rules only.
- `src/retrieval/` performs hard filtering, lexical/attribute retrieval, route-aware ranking, optional dense retrieval and controlled relaxation.
- `src/dialogue/` selects a recommendation or one useful clarification while enforcing late-turn protection.
- `evaluator/local_evaluator.py` is the deterministic public-set simulator and scorer.

## State and constraint safety

State is keyed by the evaluator-provided `session_id`. `reset()` replaces prior state for that identifier, and each `respond()` call uses a transaction so malformed updates do not partially corrupt the session. Explicit budget bounds and exclusions are never silently relaxed. Candidate IDs are sanitized against the read-only catalog, deduplicated and limited to the requested Top K.

## Buying and Browsing

- **Buying** prioritizes eligibility and precise constraint matching. Empty hard-filter results can trigger controlled relaxation of eligible preferences, never the budget or explicit exclusions.
- **Browsing** keeps scene and style information as ranking context and preserves diversity instead of over-filtering the catalog.

Both routes share the same parser, state model, eligibility boundary, response contract and trace schema.

## Optional capabilities versus the frozen run

The code supports persistent dense retrieval, a local intent classifier, a schema-bounded DeepSeek-compatible parser and JSONL tracing. These are opt-in and fail back to deterministic behavior. In the frozen public result:

```text
dense_enabled=false
llm_enabled=false
intent_model_mode=off
trace_enabled=false
attribute_retrieval_enabled=true
attribute_reranking_enabled=true
recommendation_with_clarification_enabled=true
override_invalidation_enabled=true
optimized_single_pass_enabled=true
```

This distinction matters: optional modules demonstrate extension boundaries, but the reported score and external API cost correspond to the deterministic offline configuration above.
