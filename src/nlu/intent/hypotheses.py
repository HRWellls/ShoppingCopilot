from __future__ import annotations

from src.models import SessionState


HYPOTHESIS_VERSION = "shopping-intent-v1"
HYPOTHESES = {
    "buying": "The customer has a specific purchase goal and wants products satisfying concrete requirements.",
    "browsing": "The customer is exploring ideas, styles, occasions, or options without a fixed target.",
    "continue": "The customer is answering the previous shopping question or adding a preference without changing shopping mode.",
}
HYPOTHESES_V2 = {
    "buying": "The customer wants to buy a product.",
    "browsing": "The customer is exploring ideas.",
    "continue": "The customer answered the previous question.",
}
HYPOTHESIS_SETS = {
    HYPOTHESIS_VERSION: HYPOTHESES,
    "shopping-intent-v2": HYPOTHESES_V2,
}


def build_premise(state: SessionState, message: str, max_chars: int) -> str:
    parts = [f"Previous stable intent: {state.intent_state.label}."]
    if state.last_asked_slot:
        parts.append(f"The assistant asked about {state.last_asked_slot}.")
    active_names = ", ".join(sorted(state.active_slots())) or "none"
    parts.append(f"Known active preference names: {active_names}.")
    if state.previous_user_message and len(message.split()) <= 3:
        previous = state.previous_user_message[: max(0, max_chars // 4)]
        parts.append(f"Previous customer message: {previous}.")
    parts.append(f"The customer now says: {message}.")
    premise = " ".join(parts)
    return premise[:max_chars]


def build_premise_v2(state: SessionState, message: str, max_chars: int, continuation: bool = False) -> str:
    if continuation and state.last_asked_slot:
        premise = f"The assistant asked the customer about {state.last_asked_slot}. The customer answered: {message}."
    else:
        premise = f"The customer says: {message}."
    return premise[:max_chars]
