# Deterministic Retrieval D4

The promoted offline candidate configuration is:

```text
attribute_retrieval_enabled=true
attribute_reranking_enabled=true
recommendation_with_clarification_enabled=true
override_invalidation_enabled=true
optimized_single_pass_enabled=true
dense_enabled=false
llm_enabled=false
intent_model_mode=off
```

Run the matched B3/D4 promotion gate with:

```powershell
python -m scripts.check_retrieval_gate
```

The command exits nonzero unless candidate recall@150 is at least 0.95, overall
Hit@10 is at least 0.65, Intent Override Hit@10 is at least 0.80,
TechnicalScore is above 0.331459, every scenario protects its B3 Hit@10, and
response p95 is no more than 25 ms above the matched B3 control.

## Rollback

The application defaults remain the B3 values. Set all five retrieval D4 switches
above to `false`; keep Dense, LLM, and active NLI disabled. The legacy FTS path,
response protocol, transactional state store, and offline fallback remain available.

Do not promote a failed report. A failure leaves the default configuration unchanged.

## Optional Dense Ablation

The existing local `all-MiniLM-L6-v2` FAISS index was evaluated on the 20-session
stratified smoke set as a low-weight (`0.25`) candidate supplement. Hard-filter
eligibility remained authoritative and the model loaded without fallback.

Dense did not change Hit@10 (`0.95`), reduced MRR from `0.555476` to `0.555119`,
and increased response p95 from `58.295 ms` to `196.984 ms`. Browsing and Buying
MRR each fell by `0.01`. Dense therefore remains disabled and does not change the
deterministic D4 release switch. LLM and active NLI were not initialized or called.
