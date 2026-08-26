from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    INPUT_TYPE = "E_INPUT_TYPE"
    PROTOCOL = "E_PROTOCOL"
    CATALOG = "E_CATALOG"
    INDEX_NOT_READY = "E_INDEX_NOT_READY"
    EMPTY_RESULT = "E_EMPTY_RESULT"
    RETRIEVAL = "E_RETRIEVAL"
    MODEL_UNAVAILABLE = "E_MODEL_UNAVAILABLE"
    MODEL_TIMEOUT = "E_MODEL_TIMEOUT"
    MODEL_OUTPUT = "E_MODEL_OUTPUT"
    SLOT_CONFLICT = "E_SLOT_CONFLICT"
    INTERNAL = "E_INTERNAL"


class AgentError(RuntimeError):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
