from __future__ import annotations

import time
from typing import Any

from src.catalog.store import CatalogStore
from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import FilterReport, ModelUsage, SessionState, TraceEvent
from src.nlu import DeepSeekStructuredParser, FallbackStructuredParser, IntentResolver, RuleConstraintExtractor, RuleEventDetector
from src.nlu.intent.schema import RuleIntentObservation, TurnObservation
from src.nlu.intent.nli import load_intent_classifier
from src.observability import TraceRecorder
from src.output import make_response, sanitize_candidates
from src.retrieval import BM25Index, DenseIndex, HardFilter, HybridRetriever, SentenceTransformerProvider
from src.state import OverrideResolver, SessionStateStore, TurnStateReducer
from src.dialogue import ClarificationPolicy, render_question


SUCCESS_MESSAGE = "Here are the closest matches I found."
EMPTY_MESSAGE = "I couldn't find a catalog item that satisfies the current constraints."
FALLBACK_MESSAGE = "I couldn't process that request safely."
PREVIOUS_MESSAGE = "I couldn't process that update, so here are the previous matches."


class ShoppingAgentCore:
    def __init__(self, config: AgentConfig, embedding_provider: object | None = None, llm_opener: object | None = None) -> None:
        self.config = config
        self.catalog = CatalogStore(config)
        self.sessions = SessionStateStore(config)
        self.extractor = RuleConstraintExtractor()
        model_parser = None
        if config.llm_enabled:
            kwargs = {"opener": llm_opener} if llm_opener is not None else {}
            model_parser = DeepSeekStructuredParser(config, **kwargs)
        self.parser = FallbackStructuredParser(self.extractor, model_parser, config.soft_slot_ttl)
        self.override_resolver = OverrideResolver()
        self.event_detector = RuleEventDetector()
        self.intent_resolver = IntentResolver(config)
        self.state_reducer = TurnStateReducer(config.override_invalidation_enabled)
        self.intent_classifier = None
        self.intent_startup_fallback: str | None = None
        if config.intent_model_mode != "off":
            try:
                self.intent_classifier = load_intent_classifier(config)
            except AgentError as exc:
                self.intent_startup_fallback = exc.code.value
        self.hard_filter = HardFilter(self.catalog, config.cache_entries)
        self.index = BM25Index(self.catalog, config)
        self.dense_fallback: str | None = None
        self.dense = None
        if config.dense_enabled:
            try:
                provider = embedding_provider
                if provider is None:
                    if config.dense_model_path is None:
                        raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "dense model path is not configured")
                    provider = SentenceTransformerProvider(config.dense_model_path, config.dense_model_id)
                self.dense = DenseIndex(self.catalog, config, provider)  # type: ignore[arg-type]
            except AgentError as exc:
                self.dense_fallback = exc.code.value
        self.hybrid = HybridRetriever(self.catalog, config, self.index, self.hard_filter, self.dense)
        self.policy = ClarificationPolicy(self.catalog, config)
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
        asked_slot = None
        fallback_reason = self.dense_fallback
        model_usage = ModelUsage()
        try:
            self._validate_top_k(top_k)
            transactional = self.config.multiturn_state_enabled
            state = (
                self.sessions.begin_transaction(session_id, turn, user_message)
                if transactional else self.sessions.begin_turn(session_id, turn, user_message)
            )
            parsed, model_usage, parser_fallback = self.parser.parse(user_message, state)
            fallback_reason = parser_fallback or fallback_reason
            if transactional:
                events = self.event_detector.detect(user_message, state, parsed)
                valid_answer = bool(state.last_asked_slot and state.last_asked_slot in parsed.slot_updates)
                rule = RuleIntentObservation(
                    parsed.intent,
                    parsed.intent_confidence,
                    parsed.evidence,
                    parsed.intent != "unknown" and parsed.intent_confidence >= 0.6,
                )
                stable_before = state.intent_state.label
                state.stable_intent_before = stable_before
                model_observation = None
                state.intent_fallback_reason = self.intent_startup_fallback
                if self.intent_classifier is not None:
                    intent_started = time.perf_counter()
                    try:
                        model_observation = self.intent_classifier.classify(state, user_message)
                    except AgentError as exc:
                        state.intent_fallback_reason = exc.code.value
                        self.intent_classifier = None
                    finally:
                        state.intent_latency_ms = (time.perf_counter() - intent_started) * 1_000
                state.rule_intent = rule.label
                state.rule_confidence = rule.confidence
                state.model_intent = model_observation.label if model_observation else None
                state.model_confidence = model_observation.confidence if model_observation else None
                state.model_margin = model_observation.margin if model_observation else None
                resolved = self.intent_resolver.resolve(
                    state, TurnObservation(rule, events, model_observation, valid_answer)
                )
                self.state_reducer.reduce(state, parsed, events, resolved)
            else:
                if parsed.intent != "unknown" or state.intent == "unknown":
                    state.intent = parsed.intent
                    state.intent_confidence = parsed.intent_confidence
                self.override_resolver.apply(state, parsed)
            state.last_query = parsed.query_text or user_message
            self.hybrid.bm25 = self.index
            retrieval = self.hybrid.retrieve(state) if not state.conflict_reason else None
            candidates = list(retrieval.candidates) if retrieval else []
            if retrieval:
                report = retrieval.filter_report
                state.relaxation_level = retrieval.relaxation.level
                fallback_reason = retrieval.dense_fallback or fallback_reason
                state.last_route_plan = retrieval.plan.as_dict() if retrieval.plan is not None else {}
                state.last_retrieval_stages = retrieval.stages or {}
                state.last_retrieval_timings = retrieval.timings or {}
            candidate_count = len(candidates)
            state.candidate_pool = candidates
            top_ids = sanitize_candidates(candidates, self.catalog, top_k)
            state.candidate_ids = list(top_ids)
            state.model_usage = ModelUsage(
                state.model_usage.prompt_tokens + model_usage.prompt_tokens,
                state.model_usage.completion_tokens + model_usage.completion_tokens,
            )
            decision = self.policy.decide(state, candidates)
            if decision.action == "clarify" and decision.slot:
                asked_slot = decision.slot
                if transactional:
                    self.state_reducer.record_question(state, decision.slot)
                else:
                    state.asked_slots.add(decision.slot)
                state.last_action = "clarify"
                response = make_response(
                    render_question(decision.slot), top_ids,
                    self.policy.attribute_for(decision.slot), model_usage,
                )
            elif top_ids:
                state.last_action = "recommend"
                response = make_response(SUCCESS_MESSAGE, top_ids, usage=model_usage)
            else:
                state.last_action = "empty"
                error_code = ErrorCode.EMPTY_RESULT
                response = make_response(EMPTY_MESSAGE, (), usage=model_usage)
            if transactional:
                self.sessions.commit(state)
            else:
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
            fallback_reason=fallback_reason,
            asked_slot=asked_slot,
            model_usage=model_usage,
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
        fallback_reason: str | None,
        asked_slot: str | None,
        model_usage: ModelUsage,
    ) -> None:
        event = TraceEvent(
            session_id=session_id if isinstance(session_id, str) else "invalid",
            turn=turn if isinstance(turn, int) and not isinstance(turn, bool) else 0,
            intent=state.intent if state is not None else "unknown",
            intent_confidence=state.intent_confidence if state is not None else 0.0,
            constraint_names=state.active_constraints().active_names() if state is not None else (),
            route=state.intent if state is not None else "unknown",
            filter_report=report.as_dict(),
            candidate_count=candidate_count,
            top10=tuple(top_ids[:10]),
            latency_ms=latency_ms,
            fallback=fallback,
            error_code=error_code.value if error_code is not None else None,
            config_version=self.config.config_version,
            dense_enabled=self.dense is not None,
            llm_used=model_usage.total_tokens > 0,
            fallback_reason=fallback_reason,
            relaxation_level=state.relaxation_level if state else 0,
            candidate_sources=tuple(sorted({source for candidate in state.candidate_pool for source in candidate.sources})) if state else (),
            asked_slot=asked_slot,
            model_usage=model_usage,
            route_plan=state.last_route_plan if state else {},
            policy_reason=state.last_policy_reason if state else None,
            detected_events=state.last_event_kinds if state else (),
            rule_intent=state.rule_intent if state else "unknown",
            rule_confidence=state.rule_confidence if state else 0.0,
            model_intent=state.model_intent if state else None,
            model_confidence=state.model_confidence if state else None,
            model_margin=state.model_margin if state else None,
            stable_intent_before=state.stable_intent_before if state else "unknown",
            intent_switched=bool(state and state.intent_state.last_switch_turn == state.turn_count),
            switch_reason=state.intent_state.switch_reason if state else None,
            slot_answer_status=(state.slot_answers[state.last_asked_slot].status if state and state.last_asked_slot in state.slot_answers else None),
            intent_model_mode=self.config.intent_model_mode,
            intent_fallback_reason=state.intent_fallback_reason if state else self.intent_startup_fallback,
            intent_latency_ms=state.intent_latency_ms if state else 0.0,
        )
        self.trace.record(event)
