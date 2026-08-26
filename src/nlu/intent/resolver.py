from __future__ import annotations

from src.config import AgentConfig
from src.models import SessionState
from src.nlu.intent.schema import ResolvedIntent, TurnObservation


class IntentResolver:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def resolve(self, state: SessionState, observation: TurnObservation) -> ResolvedIntent:
        current = state.intent_state
        switch = next((event for event in observation.events if event.kind == "intent_switch"), None)
        if switch is not None and switch.target_intent is not None:
            return ResolvedIntent(
                switch.target_intent, switch.confidence, "event", switch.target_intent != current.label,
                switch.evidence[0] if switch.evidence else "explicit_intent_switch",
            )
        rule = observation.rule
        if rule.strong and rule.label != "unknown":
            return ResolvedIntent(rule.label, rule.confidence, "rule", rule.label != current.label, "strong_rule")
        if observation.model is not None and self.config.intent_model_mode == "active":
            model = observation.model
            if model.label == "continue" and current.label != "unknown":
                return ResolvedIntent(current.label, current.confidence, "model_continue", False, "continue")
            if current.label == "unknown":
                if model.label != "unknown" and model.confidence >= self.config.intent_initial_confidence and model.margin >= self.config.intent_initial_margin:
                    return ResolvedIntent(model.label, model.confidence, "model", True, "model_initial")
            elif model.label in {"buying", "browsing"} and model.label != current.label:
                if self.config.intent_model_switch_enabled and model.confidence >= self.config.intent_switch_confidence and model.margin >= self.config.intent_switch_margin:
                    return ResolvedIntent(model.label, model.confidence, "model", True, "model_switch")
        if observation.valid_answer and current.label != "unknown":
            return ResolvedIntent(current.label, current.confidence, "continue", False, "valid_answer")
        if current.label != "unknown":
            return ResolvedIntent(current.label, current.confidence, "stable", False, "stable_intent")
        return ResolvedIntent("unknown", rule.confidence, "rule", False, "insufficient_evidence")
