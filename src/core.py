from __future__ import annotations

import time
from typing import Any

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import FilterReport, SessionState, TraceEvent
from src.nlu import RuleConstraintExtractor, RuleIntentRouter, apply_rule_turn
from src.observability import TraceRecorder
from src.output import make_response, sanitize_candidates
from src.retrieval import BM25Index, HardFilter
from src.state import SessionStateStore


SUCCESS_MESSAGE = "Here are the closest matches I found."
EMPTY_MESSAGE = "I couldn't find a catalog item that satisfies the current constraints."
FALLBACK_MESSAGE = "I couldn't process that request safely."
PREVIOUS_MESSAGE = "I couldn't process that update, so here are the previous matches."


class ShoppingAgentCore:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.catalog = CatalogStore(config)
        self.sessions = SessionStateStore(config)
        self.router = RuleIntentRouter()
        self.extractor = RuleConstraintExtractor()
        self.hard_filter = HardFilter(self.catalog, config.cache_entries)
        self.index = BM25Index(self.catalog, config)
        self.trace = TraceRecorder(config.trace_enabled, config.trace_path)

    def reset(self, session_id: str, user_profile: dict[str, Any]) -> None:
        self.sessions.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict[str, Any]:
        started = time.perf_counter()
        state: SessionState | None = None
        report = FilterReport(initial_count=self.catalog.record_count, steps=(), final_count=self.catalog.record_count)
        fallback = False
        error_code: ErrorCode | None = None
        top_ids: list[str] = []
        candidate_count = 0
        try:
            self._validate_top_k(top_k)
            state = self.sessions.begin_turn(session_id, turn, user_message)
            intent = self.router.route(user_message)
            state.intent = intent.label
            state.intent_confidence = intent.confidence
            apply_rule_turn(state, user_message, self.extractor)
            subset, report = self.hard_filter.apply(state.constraints)
            candidates = self.index.search(state.last_query, self.config.retrieval_limit, subset)
            candidate_count = len(candidates)
            top_ids = sanitize_candidates(candidates, self.catalog, top_k)
            state.candidate_ids = list(top_ids)
            if top_ids:
                state.last_action = "recommend"
                response = make_response(SUCCESS_MESSAGE, top_ids)
            else:
                state.last_action = "empty"
                error_code = ErrorCode.EMPTY_RESULT
                response = make_response(EMPTY_MESSAGE, ())
            self.sessions.save(state)
        except AgentError as exc:
            fallback = True
            error_code = exc.code
            state = self._safe_state(session_id)
            previous = state.candidate_ids if state is not None else []
            top_ids = sanitize_candidates(previous, self.catalog, top_k if isinstance(top_k, int) else 0)
            response = make_response(PREVIOUS_MESSAGE if top_ids else FALLBACK_MESSAGE, top_ids)
        except Exception:
            fallback = True
            error_code = ErrorCode.INTERNAL
            state = self._safe_state(session_id)
            previous = state.candidate_ids if state is not None else []
            top_ids = sanitize_candidates(previous, self.catalog, top_k if isinstance(top_k, int) else 0)
            response = make_response(PREVIOUS_MESSAGE if top_ids else FALLBACK_MESSAGE, top_ids)

        self._record_trace(
            session_id=session_id,
            turn=turn,
            state=state,
            report=report,
            candidate_count=candidate_count,
            top_ids=top_ids,
            latency_ms=(time.perf_counter() - started) * 1_000,
            fallback=fallback,
            error_code=error_code,
        )
        return response

    @staticmethod
    def _validate_top_k(top_k: int) -> None:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise AgentError(ErrorCode.PROTOCOL, "top_k must be a positive integer")

    def _safe_state(self, session_id: object) -> SessionState | None:
        if not isinstance(session_id, str) or session_id not in self.sessions:
            return None
        try:
            return self.sessions.get(session_id)
        except AgentError:
            return None

    def _record_trace(
        self,
        *,
        session_id: object,
        turn: object,
        state: SessionState | None,
        report: FilterReport,
        candidate_count: int,
        top_ids: list[str],
        latency_ms: float,
        fallback: bool,
        error_code: ErrorCode | None,
    ) -> None:
        event = TraceEvent(
            session_id=session_id if isinstance(session_id, str) else "invalid",
            turn=turn if isinstance(turn, int) and not isinstance(turn, bool) else 0,
            intent=state.intent if state is not None else "unknown",
            intent_confidence=state.intent_confidence if state is not None else 0.0,
            constraint_names=state.constraints.active_names() if state is not None else (),
            route=state.intent if state is not None else "unknown",
            filter_report=report.as_dict(),
            candidate_count=candidate_count,
            top10=tuple(top_ids[:10]),
            latency_ms=latency_ms,
            fallback=fallback,
            error_code=error_code.value if error_code is not None else None,
            config_version=self.config.config_version,
        )
        self.trace.record(event)
