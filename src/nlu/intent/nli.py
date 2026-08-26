from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Any, Protocol, Sequence

from src.config import AgentConfig
from src.errors import AgentError, ErrorCode
from src.models import SessionState
from src.nlu.intent.artifact import IntentArtifactManifest, validate_checksums
from src.nlu.intent.hypotheses import HYPOTHESIS_SETS, build_premise, build_premise_v2
from src.nlu.intent.schema import IntentModelObservation


class IntentClassifier(Protocol):
    def classify(self, state: SessionState, message: str) -> IntentModelObservation: ...


def _softmax(values: Sequence[float]) -> list[float]:
    maximum = max(values)
    exponents = [math.exp(value - maximum) for value in values]
    total = sum(exponents)
    return [value / total for value in exponents]


class NLIIntentClassifier:
    def __init__(
        self,
        config: AgentConfig,
        manifest: IntentArtifactManifest,
        session: Any,
        tokenizer: Any,
    ) -> None:
        self.config = config
        self.manifest = manifest
        self.session = session
        self.tokenizer = tokenizer
        try:
            self.entailment_index = manifest.labels.index("entailment")
        except ValueError as exc:
            raise AgentError(ErrorCode.MODEL_OUTPUT, "intent entailment label is missing") from exc

    def classify(self, state: SessionState, message: str) -> IntentModelObservation:
        hypotheses = HYPOTHESIS_SETS[self.manifest.hypothesis_version]
        if self.config.intent_classifier_strategy == "two_stage":
            if state.last_asked_slot and len(message.split()) <= 6:
                premise = build_premise_v2(state, message, self.config.intent_input_max_chars, continuation=True)
                continue_score = self._score(premise, (hypotheses["continue"],))[0]
                if continue_score >= 0.5:
                    return IntentModelObservation("continue", continue_score, min(1.0, continue_score - 0.5), self.manifest.model_id)
            normalized = message.casefold()
            buying_signal = re.search(
                r"\b(?:ready to buy|buy now|purchase|exact need|requirements?|must be|maximum budget|budget|find me|specific product)\b",
                normalized,
            )
            browsing_signal = re.search(
                r"\b(?:explor(?:e|ing)|brows(?:e|ing)|inspiration|not ready to buy|possibilities|directions to consider|broad ideas)\b",
                normalized,
            )
            if buying_signal:
                return IntentModelObservation("buying", 0.99, 0.90, "two-stage-explicit")
            if browsing_signal:
                return IntentModelObservation("browsing", 0.99, 0.90, "two-stage-explicit")
            premise = build_premise_v2(state, message, self.config.intent_input_max_chars)
            labels = ("buying", "browsing")
        else:
            premise = build_premise(state, message, self.config.intent_input_max_chars)
            labels = tuple(hypotheses)
        scores = self._score(premise, tuple(hypotheses[label] for label in labels))
        order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
        best, runner_up = order[0], order[1]
        confidence = max(0.0, min(1.0, scores[best]))
        margin = max(0.0, min(1.0, confidence - scores[runner_up]))
        if self.config.intent_classifier_strategy == "two_stage":
            label = labels[best] if margin >= self.config.intent_initial_margin else "unknown"
        else:
            label = labels[best] if confidence >= 0.5 else "unknown"
        return IntentModelObservation(label, confidence, margin, self.manifest.model_id)

    def _score(self, premise: str, hypotheses: tuple[str, ...]) -> list[float]:
        pairs = [(premise, hypothesis) for hypothesis in hypotheses]
        started = time.perf_counter()
        try:
            encoded = self.tokenizer(
                [pair[0] for pair in pairs],
                [pair[1] for pair in pairs],
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="np",
            )
            input_names = {item.name for item in self.session.get_inputs()}
            inputs = {name: value for name, value in encoded.items() if name in input_names}
            if not {"input_ids", "attention_mask"}.issubset(inputs):
                raise AgentError(ErrorCode.MODEL_OUTPUT, "intent ONNX inputs are incompatible")
            outputs = self.session.run(None, inputs)
            logits = outputs[0]
            if getattr(logits, "shape", None) != (len(hypotheses), len(self.manifest.labels)):
                raise AgentError(ErrorCode.MODEL_OUTPUT, "intent logits shape is invalid")
            scores = [_softmax([float(value) for value in row])[self.entailment_index] for row in logits]
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "intent inference failed") from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms > self.config.intent_timeout_ms:
            raise AgentError(ErrorCode.MODEL_TIMEOUT, "intent inference exceeded its budget")
        return scores


def load_intent_classifier(config: AgentConfig) -> NLIIntentClassifier:
    if config.intent_model_mode == "off":
        raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "intent model is off")
    if config.intent_model_path is None or config.intent_manifest_path is None:
        raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "intent artifact is not configured")
    root = Path(config.intent_model_path)
    manifest = IntentArtifactManifest.load(Path(config.intent_manifest_path))
    if manifest.model_id != config.intent_model_id or manifest.hypothesis_version != config.intent_hypothesis_version:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "intent manifest version does not match configuration")
    model_path, _ = validate_checksums(root, manifest)
    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        inputs = {item.name for item in session.get_inputs()}
        if not {"input_ids", "attention_mask"}.issubset(inputs) or not session.get_outputs():
            raise AgentError(ErrorCode.MODEL_OUTPUT, "intent ONNX I/O is incompatible")
        if "CPUExecutionProvider" not in session.get_providers():
            raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "intent execution provider is unavailable")
        tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True)
        classifier = NLIIntentClassifier(config, manifest, session, tokenizer)
        health = SessionState("intent-health", last_user_message="show me options")
        classifier.classify(health, "show me options")
        return classifier
    except AgentError:
        raise
    except Exception as exc:
        raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "local intent artifact cannot be loaded") from exc
