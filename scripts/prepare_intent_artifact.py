from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.nlu.intent.artifact import IntentArtifactManifest, sha256_file, validate_checksums


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or verify a local read-only intent artifact manifest")
    parser.add_argument("model_dir")
    parser.add_argument("--model-file", default="onnx/model_quint8_avx2.onnx")
    parser.add_argument("--tokenizer-file", default="tokenizer.json")
    parser.add_argument("--manifest", default="intent-manifest.json")
    parser.add_argument("--model-id", default="cross-encoder/nli-deberta-v3-xsmall")
    parser.add_argument("--hypothesis-version", choices=("shopping-intent-v1", "shopping-intent-v2"), default="shopping-intent-v1")
    parser.add_argument("--download", action="store_true", help="Fetch the pinned source files during this explicit preparation command")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    root = Path(args.model_dir)
    if args.download:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=args.model_id,
            local_dir=root,
            allow_patterns=[
                args.model_file,
                args.tokenizer_file,
                "config.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "added_tokens.json",
                "spm.model",
            ],
        )
    manifest_path = root / args.manifest
    if args.verify:
        manifest = IntentArtifactManifest.load(manifest_path)
        validate_checksums(root, manifest)
        print(json.dumps({"valid": True, "model_id": manifest.model_id, "variant": manifest.artifact_variant}))
        return
    model_path = root / args.model_file
    tokenizer_path = root / args.tokenizer_file
    manifest = IntentArtifactManifest(
        model_id=args.model_id,
        runtime="onnxruntime-int8",
        artifact_variant=Path(args.model_file).stem,
        labels=("contradiction", "entailment", "neutral"),
        hypothesis_version=args.hypothesis_version,
        resolver_version="intent-resolver-v1",
        model_file=args.model_file,
        tokenizer_file=args.tokenizer_file,
        model_sha256=sha256_file(model_path),
        tokenizer_sha256=sha256_file(tokenizer_path),
    )
    manifest_path.write_text(json.dumps(manifest.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "model_id": manifest.model_id}))


if __name__ == "__main__":
    main()
