from __future__ import annotations

import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import IntentState, SessionState
from src.nlu.intent.artifact import IntentArtifactManifest, validate_checksums
from src.nlu.intent.hypotheses import build_premise
from src.nlu.intent.nli import NLIIntentClassifier
from src.nlu.intent.schema import IntentModelObservation
from starter.agent import Agent
from tests.fixtures import profile, write_catalog


class InputInfo:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeTokenizer:
    def __init__(self) -> None:
        self.last_premises: list[str] = []

    def __call__(self, premises, hypotheses, **kwargs):
        self.last_premises = list(premises)
        size = len(premises)
        return {
            "input_ids": np.ones((size, 4), dtype=np.int64),
            "attention_mask": np.ones((size, 4), dtype=np.int64),
            "token_type_ids": np.zeros((size, 4), dtype=np.int64),
        }


class FakeSession:
    def __init__(self, logits=None) -> None:
        self.logits = np.asarray(logits if logits is not None else [
            [0.0, 4.0, 0.0],
            [3.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
        ], dtype=np.float32)

    def get_inputs(self):
        return [InputInfo("input_ids"), InputInfo("attention_mask")]

    def run(self, outputs, inputs):
        return [self.logits]


class SlowSession(FakeSession):
    def run(self, outputs, inputs):
        time.sleep(0.01)
        return super().run(outputs, inputs)


class RaisingSession(FakeSession):
    def run(self, outputs, inputs):
        raise RuntimeError("private runtime failure")


class StaticClassifier:
    def __init__(self, observation: IntentModelObservation) -> None:
        self.observation = observation
        self.calls = 0

    def classify(self, state, message):
        self.calls += 1
        return self.observation


class FailingClassifier:
    def classify(self, state, message):
        raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "private failure")


def manifest(**overrides) -> IntentArtifactManifest:
    values = {
        "model_id": "cross-encoder/nli-deberta-v3-xsmall",
        "runtime": "onnxruntime-int8",
        "artifact_variant": "model_quint8_avx2",
        "labels": ("contradiction", "entailment", "neutral"),
        "hypothesis_version": "shopping-intent-v1",
        "resolver_version": "intent-resolver-v1",
        "model_file": "onnx/model.onnx",
        "tokenizer_file": "tokenizer.json",
        "model_sha256": "0" * 64,
        "tokenizer_sha256": "0" * 64,
    }
    values.update(overrides)
    return IntentArtifactManifest(**values)


class IntentNLITest(unittest.TestCase):
    def test_bounded_premise_uses_only_allowed_state(self) -> None:
        state = SessionState(
            "s",
            intent_state=IntentState("browsing", 0.9, "rule", 1),
            last_asked_slot="color",
            previous_user_message="earlier message",
            history=["SECRET FULL HISTORY"],
            candidate_ids=["PRIVATE_PRODUCT"],
        )
        premise = build_premise(state, "black", 180)
        self.assertIn("browsing", premise)
        self.assertIn("color", premise)
        self.assertIn("black", premise)
        self.assertLessEqual(len(premise), 180)
        self.assertNotIn("PRIVATE_PRODUCT", premise)
        self.assertNotIn("SECRET FULL HISTORY", premise)

    def test_classifier_normalizes_logits_confidence_and_margin(self) -> None:
        tokenizer = FakeTokenizer()
        classifier = NLIIntentClassifier(AgentConfig(intent_timeout_ms=1000), manifest(), FakeSession(), tokenizer)
        result = classifier.classify(SessionState("s"), "I need specific shoes")
        self.assertEqual(result.label, "buying")
        self.assertGreater(result.confidence, 0.9)
        self.assertGreater(result.margin, 0.8)
        self.assertEqual(len(tokenizer.last_premises), 3)

    def test_classifier_rejects_malformed_output(self) -> None:
        classifier = NLIIntentClassifier(
            AgentConfig(intent_timeout_ms=1000), manifest(), FakeSession([[1.0, 2.0, 3.0]]), FakeTokenizer()
        )
        with self.assertRaises(AgentError):
            classifier.classify(SessionState("s"), "options")

    def test_classifier_handles_ties_timeout_and_runtime_failure(self) -> None:
        tied = NLIIntentClassifier(
            AgentConfig(intent_timeout_ms=1000), manifest(),
            FakeSession([[0.0, 2.0, 0.0]] * 3), FakeTokenizer(),
        ).classify(SessionState("s"), "options")
        self.assertEqual(tied.label, "buying")
        self.assertEqual(tied.margin, 0.0)
        with self.assertRaises(AgentError):
            NLIIntentClassifier(
                AgentConfig(intent_timeout_ms=1), manifest(), SlowSession(), FakeTokenizer()
            ).classify(SessionState("s"), "options")
        with self.assertRaises(AgentError):
            NLIIntentClassifier(
                AgentConfig(intent_timeout_ms=1000), manifest(), RaisingSession(), FakeTokenizer()
            ).classify(SessionState("s"), "options")

    def test_manifest_checksums_and_paths_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "onnx").mkdir()
            model = root / "onnx/model.onnx"
            tokenizer = root / "tokenizer.json"
            model.write_bytes(b"model")
            tokenizer.write_bytes(b"tokenizer")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            value = manifest(model_sha256=digest(model), tokenizer_sha256=digest(tokenizer))
            self.assertEqual(validate_checksums(root, value), (model, tokenizer))
            with self.assertRaises(AgentError):
                validate_checksums(root, manifest(tokenizer_sha256=digest(tokenizer)))
            unsafe = {**value.as_dict(), "model_file": "../outside.onnx"}
            path = root / "unsafe.json"
            path.write_text(json.dumps(unsafe), encoding="utf-8")
            with self.assertRaises(AgentError):
                IntentArtifactManifest.load(path)

    def test_off_and_shadow_have_identical_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = write_catalog(root / "catalog.jsonl")
            common = dict(
                catalog_path=catalog,
                fused_k=100,
                multiturn_state_enabled=True,
                intent_routing_enabled=True,
                intent_policy_enabled=True,
            )
            off = Agent(config=AgentConfig(**common, intent_model_mode="off"))
            shadow = Agent(config=AgentConfig(**common, intent_model_mode="shadow"))
            fake = StaticClassifier(IntentModelObservation("browsing", 0.99, 0.9))
            shadow._core.intent_classifier = fake
            for agent in (off, shadow):
                agent.reset("s", profile())
            off_response = off.respond("s", "looking for black running shoes", 1, 10)
            shadow_response = shadow.respond("s", "looking for black running shoes", 1, 10)
            self.assertEqual(off_response, shadow_response)
            self.assertEqual(off._core.sessions.get("s").intent, shadow._core.sessions.get("s").intent)
            self.assertEqual(fake.calls, 1)

    def test_active_resolver_uses_model_thresholds_without_mutating_slots(self) -> None:
        from src.nlu.intent.resolver import IntentResolver
        from src.nlu.intent.schema import RuleIntentObservation, TurnObservation

        config = AgentConfig(
            intent_model_mode="active",
            intent_initial_confidence=0.7,
            intent_initial_margin=0.1,
            intent_switch_confidence=0.8,
            intent_switch_margin=0.2,
        )
        resolver = IntentResolver(config)
        state = SessionState("s", intent_state=IntentState("buying", 0.9, "rule", 1))
        weak = RuleIntentObservation("unknown", 0.2)
        low = resolver.resolve(state, TurnObservation(weak, model=IntentModelObservation("browsing", 0.79, 0.5)))
        self.assertEqual(low.label, "buying")
        switched = resolver.resolve(state, TurnObservation(weak, model=IntentModelObservation("browsing", 0.9, 0.4)))
        self.assertEqual(switched.label, "browsing")
        self.assertEqual(state.slots, {})
        no_switch = IntentResolver(AgentConfig(
            intent_model_mode="active", intent_model_switch_enabled=False,
        )).resolve(state, TurnObservation(weak, model=IntentModelObservation("browsing", 1.0, 1.0)))
        self.assertEqual(no_switch.label, "buying")

    def test_missing_shadow_artifact_falls_back_and_trace_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = write_catalog(root / "catalog.jsonl")
            trace = root / "trace.jsonl"
            agent = Agent(config=AgentConfig(
                catalog_path=catalog,
                fused_k=100,
                multiturn_state_enabled=True,
                intent_routing_enabled=True,
                intent_policy_enabled=True,
                intent_model_mode="shadow",
                intent_model_path=root / "PRIVATE_MODEL_PATH",
                intent_manifest_path=root / "PRIVATE_MANIFEST_PATH",
                trace_enabled=True,
                trace_path=trace,
            ))
            agent.reset("s", profile())
            response = agent.respond("s", "looking for shoes", 1, 10)
            self.assertTrue(response["recommendations"])
            event = json.loads(trace.read_text(encoding="utf-8"))
            self.assertEqual(event["intent_model_mode"], "shadow")
            self.assertEqual(event["intent_fallback_reason"], "E_MODEL_OUTPUT")
            serialized = json.dumps(event)
            self.assertNotIn("PRIVATE_MODEL_PATH", serialized)
            self.assertNotIn("PRIVATE_MANIFEST_PATH", serialized)

    def test_active_startup_and_mid_session_failures_match_b3_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = write_catalog(root / "catalog.jsonl")
            common = dict(
                catalog_path=catalog,
                fused_k=100,
                multiturn_state_enabled=True,
                intent_routing_enabled=True,
                intent_policy_enabled=True,
            )
            off = Agent(config=AgentConfig(**common, intent_model_mode="off"))
            missing = Agent(config=AgentConfig(
                **common,
                intent_model_mode="active",
                intent_model_path=root / "missing",
                intent_manifest_path=root / "missing/manifest.json",
            ))
            runtime_failure = Agent(config=AgentConfig(**common, intent_model_mode="active"))
            runtime_failure._core.intent_classifier = FailingClassifier()
            for agent in (off, missing, runtime_failure):
                agent.reset("s", profile())
            message = "looking for black running shoes"
            expected = off.respond("s", message, 1, 10)
            self.assertEqual(missing.respond("s", message, 1, 10), expected)
            self.assertEqual(runtime_failure.respond("s", message, 1, 10), expected)
            self.assertEqual(runtime_failure._core.sessions.get("s").intent, off._core.sessions.get("s").intent)

    def test_invalid_onnx_provider_artifact_falls_back_without_initialization_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "onnx").mkdir()
            model = root / "onnx/model.onnx"
            tokenizer = root / "tokenizer.json"
            model.write_bytes(b"not-an-onnx-model")
            tokenizer.write_text("{}", encoding="utf-8")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            value = manifest(model_sha256=digest(model), tokenizer_sha256=digest(tokenizer))
            manifest_path = root / "intent-manifest.json"
            manifest_path.write_text(json.dumps(value.as_dict()), encoding="utf-8")
            catalog = write_catalog(root / "catalog.jsonl")
            agent = Agent(config=AgentConfig(
                catalog_path=catalog,
                fused_k=100,
                multiturn_state_enabled=True,
                intent_routing_enabled=True,
                intent_policy_enabled=True,
                intent_model_mode="active",
                intent_model_path=root,
                intent_manifest_path=manifest_path,
            ))
            agent.reset("s", profile())
            self.assertTrue(agent.respond("s", "looking for shoes", 1, 10)["recommendations"])


if __name__ == "__main__":
    unittest.main()
