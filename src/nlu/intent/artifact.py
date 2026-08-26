from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.errors import AgentError, ErrorCode


@dataclass(frozen=True)
class IntentArtifactManifest:
    model_id: str
    runtime: str
    artifact_variant: str
    labels: tuple[str, ...]
    hypothesis_version: str
    resolver_version: str
    model_file: str
    tokenizer_file: str
    model_sha256: str
    tokenizer_sha256: str

    @classmethod
    def load(cls, path: Path) -> "IntentArtifactManifest":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or set(payload) != set(cls.__dataclass_fields__):
                raise ValueError
            payload["labels"] = tuple(payload["labels"])
            manifest = cls(**payload)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AgentError(ErrorCode.MODEL_OUTPUT, "intent manifest is invalid") from exc
        if manifest.runtime != "onnxruntime-int8":
            raise AgentError(ErrorCode.MODEL_OUTPUT, "intent runtime is unsupported")
        if set(manifest.labels) != {"contradiction", "entailment", "neutral"}:
            raise AgentError(ErrorCode.MODEL_OUTPUT, "intent label mapping is invalid")
        for relative in (manifest.model_file, manifest.tokenizer_file):
            candidate = Path(relative)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise AgentError(ErrorCode.MODEL_OUTPUT, "intent manifest path is unsafe")
        return manifest

    def as_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "labels": list(self.labels)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise AgentError(ErrorCode.MODEL_UNAVAILABLE, "intent artifact file is unavailable") from exc
    return digest.hexdigest()


def validate_checksums(root: Path, manifest: IntentArtifactManifest) -> tuple[Path, Path]:
    model_path = root / manifest.model_file
    tokenizer_path = root / manifest.tokenizer_file
    if sha256_file(model_path) != manifest.model_sha256:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "intent model checksum mismatch")
    if sha256_file(tokenizer_path) != manifest.tokenizer_sha256:
        raise AgentError(ErrorCode.MODEL_OUTPUT, "intent tokenizer checksum mismatch")
    return model_path, tokenizer_path
