from __future__ import annotations

import hashlib
import json
import random
import statistics
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluator.local_evaluator import (
    MAX_TURNS,
    TOP_K,
    coarse_category,
    customer_reply,
    initial_message,
    materialize_hidden_fields,
    metric_summary,
    normalize_recommendations,
)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rank(values: list[str] | tuple[str, ...], target: str) -> int | None:
    try:
        return values.index(target) + 1
    except ValueError:
        return None


def _state(agent: Any, session_id: str) -> Any | None:
    wrapped = getattr(agent, "agent", agent)
    core = getattr(wrapped, "_core", None)
    return core.sessions.get(session_id) if core is not None else None


def _active_values(state: Any) -> set[str]:
    if state is None:
        return set()
    values: set[str] = set()
    for slot in state.active_slots().values():
        raw = slot.value
        items = raw if isinstance(raw, (list, tuple, set, frozenset)) else (raw,)
        values.update(str(item).casefold() for item in items if item is not None)
    return values


def _aggregate(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    if not sessions:
        return {
            "sample_count": 0,
            "candidate_recall_at_10": 0.0,
            "candidate_recall_at_50": 0.0,
            "candidate_recall_at_pool": 0.0,
            "candidate_generation_failures": 0,
            "ranking_failures": 0,
            "unproductive_clarifications": 0,
            "override_state_failures": 0,
            "raw_channel_union_coverage": 0.0,
        }
    count = len(sessions)
    ranks = [item["best_pool_rank"] for item in sessions]
    raw_union_ranks = [item["best_raw_union_rank"] for item in sessions]
    return {
        "sample_count": count,
        "candidate_recall_at_10": round(sum(rank is not None and rank <= 10 for rank in ranks) / count, 6),
        "candidate_recall_at_50": round(sum(rank is not None and rank <= 50 for rank in ranks) / count, 6),
        "candidate_recall_at_pool": round(sum(rank is not None for rank in ranks) / count, 6),
        "candidate_generation_failures": sum(rank is None for rank in ranks),
        "ranking_failures": sum(rank is not None and rank > 10 and not item["hit"] for rank, item in zip(ranks, sessions)),
        "unproductive_clarifications": sum(item["unproductive_clarifications"] for item in sessions),
        "override_state_failures": sum(bool(item["override_state_failure"]) for item in sessions),
        "raw_channel_union_coverage": round(sum(rank is not None for rank in raw_union_ranks) / count, 6),
        "mean_first_recall_turn": round(
            statistics.fmean(item["first_recall_turn"] for item in sessions if item["first_recall_turn"] is not None), 6
        ) if any(item["first_recall_turn"] is not None for item in sessions) else None,
    }


def evaluate_with_diagnostics(
    agent: Any,
    samples: list[dict[str, Any]],
    catalog_ids: set[str],
    categories: dict[str, list[str]],
    products: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sessions: list[dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    for sample in samples:
        session_id = f"diagnostic_{uuid.uuid4().hex}"
        agent.reset(session_id, sample["user_profile"])
        target = str(sample["ground_truth"]["parent_asin"])
        intent_card, behavior = materialize_hidden_fields(sample, products)
        effective = {**sample, "intent_card": intent_card, "behavior": behavior}
        disclosed: set[str] = set()
        boundary_used = False
        override_applied = sample["scenario_type"] != "intent_override"
        override = behavior.get("override") or {}
        old_override_value = str(override.get("old_value", "")).casefold()
        user_message = initial_message(effective, coarse_category(categories.get(target, [])), disclosed)
        hit_turn: int | None = None
        best_rank: int | None = None
        best_pool_rank: int | None = None
        best_raw_union_rank: int | None = None
        first_recall_turn: int | None = None
        turns: list[dict[str, Any]] = []
        pending_clarification: dict[str, Any] | None = None
        unproductive = 0
        override_state_failure = False
        for turn in range(1, MAX_TURNS + 1):
            try:
                response = agent.respond(session_id, user_message, turn, TOP_K)
            except Exception:
                response = {"message": "", "ask_attribute": None, "recommendations": []}
            if not isinstance(response, dict) or not isinstance(response.get("message"), str):
                response = {"message": "", "ask_attribute": None, "recommendations": []}
            usage = response.get("usage")
            if isinstance(usage, dict):
                total_prompt_tokens += usage.get("prompt_tokens", 0) if isinstance(usage.get("prompt_tokens"), int) else 0
                total_completion_tokens += usage.get("completion_tokens", 0) if isinstance(usage.get("completion_tokens"), int) else 0
            state = _state(agent, session_id)
            stages = dict(getattr(state, "last_retrieval_stages", {}) or {})
            pool = list(stages.get("fused", ()))
            ranked = normalize_recommendations(response.get("recommendations"), catalog_ids)
            pool_rank = _rank(pool, target)
            raw_union_rank = _rank(list(stages.get("raw_channel_union", ())), target)
            if pool_rank is not None and (best_pool_rank is None or pool_rank < best_pool_rank):
                best_pool_rank = pool_rank
                first_recall_turn = first_recall_turn or turn
            if raw_union_rank is not None and (best_raw_union_rank is None or raw_union_rank < best_raw_union_rank):
                best_raw_union_rank = raw_union_rank
            if pending_clarification is not None:
                answered = not user_message.casefold().startswith("i don't have an additional preference")
                shrank = len(pool) < pending_clarification["candidate_count"]
                prior_rank = pending_clarification["target_rank"]
                improved = pool_rank is not None and (prior_rank is None or pool_rank < prior_rank)
                pending_clarification.update({"answered": answered, "pool_shrank": shrank, "target_rank_improved": improved})
                if not answered and not shrank and not improved:
                    pending_clarification["unproductive"] = True
                    unproductive += 1
                pending_clarification = None
            retained_evidence = " ".join(
                str(value).casefold()
                for value in (getattr(state, "query_evidence", {}) or {}).values()
            ) if state is not None else ""
            if override_applied and old_override_value and (
                old_override_value in _active_values(state) or old_override_value in retained_evidence
            ):
                override_state_failure = True
            turn_record = {
                "turn": turn,
                "route": getattr(state, "intent", "unknown"),
                "active_constraints": state.active_constraints().as_dict() if state is not None else {},
                "query_evidence": dict(getattr(state, "query_evidence", {}) or {}),
                "retrieval_timings": dict(getattr(state, "last_retrieval_timings", {}) or {}),
                "candidate_count": len(pool),
                "target_ranks": {name: _rank(list(values), target) for name, values in stages.items()},
                "top10": ranked,
                "asked_attribute": response.get("ask_attribute"),
                "policy_reason": getattr(state, "last_policy_reason", None),
                "events": list(getattr(state, "last_event_kinds", ())),
                "override_applied": override_applied,
                "reranker_explanations": [
                    {
                        "parent_asin": candidate.parent_asin,
                        "score": round(candidate.score, 6),
                        "contributions": dict(candidate.source_scores),
                        "source_ranks": dict(candidate.source_ranks),
                    }
                    for candidate in (list(getattr(state, "candidate_pool", ()))[:10] if state is not None else [])
                ] if state is not None and getattr(agent, "agent", agent)._core.config.attribute_reranking_enabled else [],
            }
            turns.append(turn_record)
            if response.get("ask_attribute"):
                pending_clarification = turn_record | {
                    "target_rank": pool_rank,
                    "answered": None,
                    "pool_shrank": None,
                    "target_rank_improved": None,
                    "unproductive": False,
                }
            if override_applied and target in ranked:
                best_rank = ranked.index(target) + 1
                hit_turn = turn
                break
            if turn == MAX_TURNS:
                break
            if not override_applied and turn + 1 == int(override.get("turn", 3)):
                override_applied = True
                new_value = str(override.get("new_value", ""))
                if new_value:
                    disclosed.add(new_value)
                user_message = str(override.get("message", "Actually, please ignore my earlier preference."))
            else:
                user_message, boundary_used = customer_reply(
                    effective, response.get("ask_attribute"), disclosed, boundary_used
                )
        sessions.append({
            "sample_id": sample["sample_id"],
            "scenario_type": sample["scenario_type"],
            "hit": hit_turn is not None,
            "first_hit_turn": hit_turn,
            "best_rank": best_rank,
            "reciprocal_rank": 0.0 if best_rank is None else 1.0 / best_rank,
            "best_pool_rank": best_pool_rank,
            "best_raw_union_rank": best_raw_union_rank,
            "first_recall_turn": first_recall_turn,
            "unproductive_clarifications": unproductive,
            "override_state_failure": override_state_failure,
            "turns": turns,
        })
    overall = metric_summary(sessions)
    efficiency = max(0.0, min(1.0, (11.0 - float(overall["mttc"])) / 10.0))
    technical_score = 0.50 * overall["hit_rate_at_10"] + 0.30 * overall["mrr"] + 0.20 * efficiency
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        grouped[session["scenario_type"]].append(session)
    return {
        **overall,
        "efficiency": round(efficiency, 6),
        "recommended_technical_score": round(technical_score, 6),
        "reported_token_usage": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
        },
        "scenario_metrics": {name: metric_summary(grouped[name]) for name in sorted(grouped)},
        "retrieval_diagnostics": {
            "overall": _aggregate(sessions),
            "scenarios": {name: _aggregate(grouped[name]) for name in sorted(grouped)},
        },
        "sessions": sessions,
    }


def stable_quality_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in result.items()
        if key not in {"benchmark", "comparison", "timing"}
    }
    if "sessions" in payload:
        payload["sessions"] = [
            {
                **session,
                "turns": [
                    {key: value for key, value in turn.items() if key != "retrieval_timings"}
                    for turn in session["turns"]
                ],
            }
            for session in payload["sessions"]
        ]
    return payload


def stable_quality_sha256(result: dict[str, Any]) -> str:
    encoded = json.dumps(stable_quality_payload(result), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
