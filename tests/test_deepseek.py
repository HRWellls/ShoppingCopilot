from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
from pathlib import Path

from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import SessionState
from src.nlu.structured import DeepSeekStructuredParser, FallbackStructuredParser, load_api_key
from src.nlu.rules import RuleConstraintExtractor


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self, limit): return self.payload[:limit]


def valid_outer():
    content = {
        "intent": "buying", "intent_confidence": .9,
        "slot_updates": {"color": {"value": "black", "kind": "soft", "confidence": .8}},
        "clears": [], "overrides": [], "query_text": "black shoes", "evidence": ["black"],
    }
    return {"choices": [{"message": {"content": json.dumps(content)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


class DeepSeekTest(unittest.TestCase):
    def test_environment_precedes_file_and_repr_hides_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api.env"
            path.write_text("file-secret", encoding="utf-8")
            path.chmod(0o600)
            config = AgentConfig(api_key_path=path, llm_enabled=True)
            self.assertEqual(load_api_key(config, {"DEEPSEEK_API_KEY": "env-secret"}), "env-secret")
            parser = DeepSeekStructuredParser(config, opener=lambda *a, **k: FakeResponse(valid_outer()), api_key="env-secret")
            self.assertNotIn("env-secret", repr(parser))

    def test_raw_and_key_value_secret_and_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api.env"
            config = AgentConfig(api_key_path=path)
            path.write_text("raw-secret", encoding="utf-8"); path.chmod(0o600)
            self.assertEqual(load_api_key(config, {}), "raw-secret")
            path.write_text("DEEPSEEK_API_KEY=value-secret", encoding="utf-8")
            self.assertEqual(load_api_key(config, {}), "value-secret")
            path.chmod(0o644)
            if os.name != "nt":
                with self.assertRaises(AgentError): load_api_key(config, {})

    def test_valid_parse_usage_and_schema_rejection(self) -> None:
        config = AgentConfig(llm_enabled=True)
        parser = DeepSeekStructuredParser(config, opener=lambda *a, **k: FakeResponse(valid_outer()), api_key="secret")
        parsed, usage = parser.parse("black shoes", SessionState("s", turn_count=1))
        self.assertEqual(parsed.slot_updates["color"].value, "black")
        self.assertEqual(usage.total_tokens, 15)
        invalid = valid_outer(); content = json.loads(invalid["choices"][0]["message"]["content"]); content["asin"] = "BAD"; invalid["choices"][0]["message"]["content"] = json.dumps(content)
        broken = DeepSeekStructuredParser(config, opener=lambda *a, **k: FakeResponse(invalid), api_key="secret")
        with self.assertRaises(AgentError): broken.parse("x", SessionState("s", turn_count=1))

    def test_timeout_and_malformed_fall_back_to_rules(self) -> None:
        config = AgentConfig(llm_enabled=True)
        def timeout(*args, **kwargs): raise socket.timeout()
        model = DeepSeekStructuredParser(config, opener=timeout, api_key="secret")
        fallback = FallbackStructuredParser(RuleConstraintExtractor(), model, 3)
        parsed, usage, reason = fallback.parse("black shoes", SessionState("s", turn_count=1))
        self.assertEqual(parsed.slot_updates["color"].value, "black")
        self.assertEqual(usage.total_tokens, 0)
        self.assertEqual(reason, ErrorCode.MODEL_TIMEOUT.value)
        malformed = DeepSeekStructuredParser(config, opener=lambda *a, **k: FakeResponse({"bad": True}), api_key="secret")
        with self.assertRaises(AgentError): malformed.parse("x", SessionState("s", turn_count=1))

    def test_disabled_model_never_calls_http(self) -> None:
        called = []
        parser = DeepSeekStructuredParser(AgentConfig(llm_enabled=False), opener=lambda *a, **k: called.append(1), api_key="secret")
        with self.assertRaises(AgentError): parser.parse("x", SessionState("s"))
        self.assertEqual(called, [])


if __name__ == "__main__": unittest.main()
