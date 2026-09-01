"""Validate required local assets and report optional capabilities."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from src.config import AgentConfig


def check(catalog: Path) -> dict:
    result: dict[str, object] = {"catalog": {"path": str(catalog), "required": True}}
    if not catalog.exists():
        result["catalog"] = {"path": str(catalog), "ok": False, "error": "catalog file is missing"}
    else:
        try:
            from src.catalog.store import CatalogStore
            store = CatalogStore(AgentConfig(catalog_path=catalog))
            result["catalog"] = {"path": str(catalog), "ok": True, "count": len(store), "checksum": store.checksum}
        except Exception as exc:
            result["catalog"] = {"path": str(catalog), "ok": False, "error": str(exc)}
    config = AgentConfig(catalog_path=catalog)
    result["config"] = {"ok": True, "version": config.config_version}
    result["optional"] = {
        "numpy": importlib.util.find_spec("numpy") is not None,
        "sentence_transformers": importlib.util.find_spec("sentence_transformers") is not None,
        "deepseek_api_key": bool(__import__("os").getenv(config.api_key_env)),
        "dense_index": config.dense_index_path.exists(),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Shopping Copilot startup self-check")
    parser.add_argument("--catalog", default="data/catalog_sample_100.jsonl")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    report = check(Path(args.catalog))
    required_ok = bool(report.get("config", {}).get("ok")) and bool(report.get("catalog", {}).get("ok"))
    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print("Shopping Copilot self-check")
        for name, value in report.items():
            print(f"- {name}: {json.dumps(value, ensure_ascii=False)}")
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
