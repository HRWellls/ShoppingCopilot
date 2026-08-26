from __future__ import annotations

import json
import os
import socket
import stat
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Protocol

from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import ModelUsage, ParsedTurn, SessionState, SlotKind, SlotValue
from src.nlu.rules import RuleConstraintExtractor


ALLOWED_TOP_LEVEL = frozenset({"intent", "intent_confidence", "slot_updates", "clears", "overrides", "query_text", "evidence"})
ALLOWED_SLOTS = frozenset({"price_min", "price_max", "brand", "color", "material", "category", "size", "occasion", "style", "use_case"})


class StructuredParser(Protocol):
    def parse(self, message: str, state: SessionState) -> tuple[ParsedTurn, ModelUsage]: ...


def load_api_key(config: AgentConfig, environ: dict[str, str] | None = None) -> str | None:
    environment = os.environ if environ is None else environ
    value = environment.get(config.api_key_env, "").strip()
    if value:
        return value
    path = Path(config.api_key_path)
    if not path.exists():
        return None
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        # Windows exposes synthetic POSIX mode bits, so they cannot reliably
        # represent the file ACL that protects this local secret.
        if os.name != "nt" and mode & 0o077:
            raise AgentError(ErrorCode.PROTOCOL, "api.env permissions must be 0600")
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise AgentError(ErrorCode.PROTOCOL, "API key file cannot be read") from exc
    if not raw:
        return None
    if "=" in raw:
        name, raw_value = raw.split("=", 1)
        if name.strip() not in {config.api_key_env, "API_KEY", "DEEPSEEK_API_KEY"}:
            return None
        return raw_value.strip().strip('"\'') or None
    return raw


def _slot_from_json(name: str, payload: Any, turn: int) -> SlotValue:
    if name not in ALLOWED_SLOTS:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model returned an unknown slot")
    if not isinstance(payload, dict) or set(payload) - {"value", "kind", "confidence", "negated", "explicit"}:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model slot schema is invalid")
    if "value" not in payload:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model slot has no value")
    try:
        kind = SlotKind(str(payload.get("kind", "soft")))
        confidence = float(payload.get("confidence", 0.5))
    except (ValueError, TypeError) as exc:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model slot metadata is invalid") from exc
    return SlotValue(
        value=payload["value"],
        kind=kind,
        confidence=confidence,
        source="model",
        turn_seen=turn,
        ttl=None if kind == SlotKind.HARD else 3,
        negated=bool(payload.get("negated", False)),
        explicit=bool(payload.get("explicit", False)),
    )


def validate_model_turn(payload: Any, state: SessionState) -> ParsedTurn:
    if not isinstance(payload, dict) or set(payload) - ALLOWED_TOP_LEVEL:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model turn schema is invalid")
    intent = payload.get("intent")
    if intent not in {"buying", "browsing", "unknown"}:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model intent is invalid")
    updates_payload = payload.get("slot_updates", {})
    if not isinstance(updates_payload, dict):
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model slot_updates is invalid")
    updates = {name: _slot_from_json(name, value, state.turn_count) for name, value in updates_payload.items()}
    clears = payload.get("clears", [])
    overrides = payload.get("overrides", [])
    evidence = payload.get("evidence", [])
    if not all(isinstance(value, list) for value in (clears, overrides, evidence)):
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model collection field is invalid")
    if any(name not in ALLOWED_SLOTS for name in clears + overrides):
        raise AgentError(ErrorCode.MODEL_OUTPUT, "model clear or override is invalid")
    return ParsedTurn(
        intent=intent,
        intent_confidence=float(payload.get("intent_confidence", 0.5)),
        slot_updates=updates,
        clears=frozenset(clears),
        overrides=frozenset(overrides),
        query_text=str(payload.get("query_text", ""))[:2_000],
        evidence=tuple(str(value)[:200] for value in evidence[:10]),
        parser_source="model",
    )


class DeepSeekStructuredParser:
    def __init__(
        self,
        config: AgentConfig,
        opener: Callable[..., Any] = urllib.request.urlopen,
        api_key: str | None = None,
    ) -> None:
        self.config = config
        self._opener = opener
        self._api_key = api_key if api_key is not None else load_api_key(config)
        self.calls = 0

    def __repr__(self) -> str:
        return f"DeepSeekStructuredParser(model={self.config.llm_model!r}, enabled={self.config.llm_enabled})"

    def parse(self, message: str, state: SessionState) -> tuple[ParsedTurn, ModelUsage]:
        if not self.config.llm_enabled or not self._api_key:
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "structured model is unavailable")
        self.calls += 1
        body = json.dumps({
            "model": self.config.llm_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Return JSON only with intent, intent_confidence, slot_updates, clears, overrides, query_text, evidence. Never return product IDs or tools."},
                {"role": "user", "content": json.dumps({"message": message[:2_000], "known_slots": sorted(state.slots), "turn": state.turn_count})},
            ],
        }).encode("utf-8")
        request = urllib.request.Request(
            self.config.llm_endpoint,
            data=body,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.config.llm_timeout_ms / 1000) as response:
                raw = response.read(self.config.llm_max_response_bytes + 1)
            if len(raw) > self.config.llm_max_response_bytes:
                raise AgentError(ErrorCode.MODEL_OUTPUT, "model response is too large")
            outer = json.loads(raw)
            content = outer["choices"][0]["message"]["content"]
            parsed = validate_model_turn(json.loads(content), state)
            usage = outer.get("usage")
            if not isinstance(usage, dict):
                raise AgentError(ErrorCode.MODEL_OUTPUT, "model usage is missing")
            model_usage = ModelUsage(int(usage["prompt_tokens"]), int(usage["completion_tokens"]))
            if model_usage.prompt_tokens < 0 or model_usage.completion_tokens < 0:
                raise ValueError
            return parsed, model_usage
        except AgentError:
            raise
        except (TimeoutError, socket.timeout) as exc:
            raise AgentError(ErrorCode.MODEL_TIMEOUT, "structured model timed out") from exc
        except urllib.error.HTTPError as exc:
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, f"structured model HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "structured model network is unavailable") from exc
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AgentError(ErrorCode.MODEL_OUTPUT, "structured model response is invalid") from exc


class FallbackStructuredParser:
    def __init__(self, rules: RuleConstraintExtractor, model: DeepSeekStructuredParser | None, soft_ttl: int) -> None:
        self.rules = rules
        self.model = model
        self.soft_ttl = soft_ttl

    def parse(self, message: str, state: SessionState) -> tuple[ParsedTurn, ModelUsage, str | None]:
        if self.model is not None:
            try:
                parsed, usage = self.model.parse(message, state)
                return parsed, usage, None
            except AgentError as exc:
                fallback = exc.code.value
        else:
            fallback = None
        return self.rules.parse(message, state, self.soft_ttl), ModelUsage(), fallback
