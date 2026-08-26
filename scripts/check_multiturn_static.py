from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _function_source(relative: str, name: str) -> str:
    source = _read(relative)
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise ValueError(f"missing function {name} in {relative}")


def _class_method_source(relative: str, class_name: str, method_name: str) -> str:
    source = _read(relative)
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                    return "\n".join(lines[child.lineno - 1 : child.end_lineno])
    raise ValueError(f"missing method {class_name}.{method_name} in {relative}")


def main() -> None:
    route_plan = _function_source("src/retrieval/hybrid.py", "build_route_plan")
    premise_v1 = _function_source("src/nlu/intent/hypotheses.py", "build_premise")
    premise_v2 = _function_source("src/nlu/intent/hypotheses.py", "build_premise_v2")
    score = _function_source("src/nlu/intent/nli.py", "_score")
    trace_dict = _class_method_source("src/models.py", "TraceEvent", "as_dict")

    intent_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src/nlu/intent").glob("*.py"))
    ).casefold()
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src").rglob("*.py"))
    ).casefold()

    download_markers = (
        "snapshot_download",
        "hf_hub_download",
        "requests.get(",
        "urllib.request",
        "urlretrieve(",
    )
    trace_forbidden = (
        '"premise"',
        '"embedding"',
        '"secret"',
        '"api_key"',
        '"model_path"',
        '"manifest_path"',
        '"ground_truth"',
        '"target_asin"',
    )
    public_branch_markers = (
        "public_set.jsonl",
        "public_sample",
        "public_session",
        "sample_id in",
    )
    checks = {
        "active_query_uses_no_historical_slots": "state.slots" not in route_plan,
        "premise_v1_is_bounded": "[:max_chars]" in premise_v1,
        "premise_v2_is_bounded": "[:max_chars]" in premise_v2,
        "tokenizer_input_is_bounded": "truncation=True" in score and "max_length=" in score,
        "trace_has_no_sensitive_fields": not any(marker in trace_dict.casefold() for marker in trace_forbidden),
        "intent_runtime_has_no_download_code": (
            not any(marker in intent_runtime for marker in download_markers)
            and intent_runtime.count("from_pretrained(") == intent_runtime.count("local_files_only=true")
        ),
        "production_has_no_public_sample_branch": not any(marker in production for marker in public_branch_markers),
    }
    payload = {"passed": all(checks.values()), "checks": checks}
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
