#!/usr/bin/env python3
"""Validate the repository surface before publishing it.

The default mode is strict and rejects unresolved submission placeholders. During
draft preparation, pass ``--allow-placeholders`` to validate everything else.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"TODO_SUBMISSION_[A-Z0-9_]+")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SECRET_PATTERNS = {
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "assigned API secret": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token)\b\s*[:=]\s*['\"]?(?!TODO|YOUR_|<)[A-Za-z0-9_./+\-=]{16,}"
    ),
}
PROHIBITED_PREFIXES = ("Owndocs/", "runresult/", "video/", "demo/video-assets/")
PROHIBITED_PARTS = {".DS_Store", ".env", "api.env", ".runtime", ".venv", "__pycache__"}
PROHIBITED_NAMES = {
    "tiktok-techjam-2026-demo-script-bilingual-v8-2026-09-01.md",
    "tiktok-techjam-2026-narration-bilingual-2026-09-01.md",
}
MAX_TRACKED_FILE_BYTES = 2 * 1024 * 1024
REQUIRED_README_HEADINGS = (
    "# Shopping Copilot",
    "## Setup and Installation",
    "## Reproduce the Results",
    "## Limitations",
    "## Future Improvements",
    "## Team Contributions",
)


def repository_files() -> list[Path]:
    """Return tracked and intended untracked files, excluding ignored files."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def readable_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def check_surface(files: list[Path], errors: list[str]) -> None:
    for path in files:
        rel = relative(path)
        parts = set(path.relative_to(ROOT).parts)
        if rel in PROHIBITED_NAMES or rel.startswith(PROHIBITED_PREFIXES):
            errors.append(f"prohibited publication artifact: {rel}")
        if parts & PROHIBITED_PARTS:
            errors.append(f"generated or secret-bearing path is publishable: {rel}")
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            continue
        if size > MAX_TRACKED_FILE_BYTES:
            errors.append(f"oversized publishable file ({size} bytes): {rel}")


def check_secrets(files: list[Path], errors: list[str]) -> None:
    for path in files:
        text = readable_text(path)
        if text is None:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible {label} in {relative(path)}")


def check_markdown_links(files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix.lower() not in {".md", ".markdown"}:
            continue
        text = readable_text(path)
        if text is None:
            continue
        for target in MARKDOWN_LINK.findall(text):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            target = target.split(" ", 1)[0]
            if not (path.parent / target).resolve().exists():
                errors.append(f"broken link in {relative(path)}: {target}")


def check_readme(errors: list[str]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for heading in REQUIRED_README_HEADINGS:
        if heading not in readme:
            errors.append(f"README is missing required heading: {heading}")


def check_metrics(errors: list[str]) -> None:
    canonical_path = ROOT / "docs/results/final-public.json"
    baseline_path = ROOT / "docs/baseline_results.json"
    if not canonical_path.exists() or not baseline_path.exists():
        errors.append("canonical or official baseline metric file is missing")
        return
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    official = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = canonical["metrics"]
    for key in ("hit_rate_at_10", "mrr", "mttc", "efficiency", "technical_score"):
        if abs(float(canonical["official_baseline"][key]) - float(official[key])) > 1e-9:
            errors.append(f"baseline mismatch for {key}")
    expected = {
        "hit_rate_at_10": f"{current['hit_rate_at_10']:.4f}",
        "mrr": f"{current['mrr']:.6f}",
        "mttc": f"{current['mttc']:.3f}",
        "efficiency": f"{current['efficiency']:.4f}",
        "technical_score": f"{current['technical_score']:.6f}",
    }
    for document in (ROOT / "README.md", ROOT / "docs/devpost-project-description.md"):
        text = document.read_text(encoding="utf-8")
        for key, value in expected.items():
            if value not in text:
                errors.append(f"{relative(document)} does not contain canonical {key}={value}")


def check_placeholders(files: list[Path], errors: list[str], warnings: list[str], allow: bool) -> None:
    found: dict[str, set[str]] = {}
    for path in files:
        text = readable_text(path)
        if text is not None and (matches := set(PLACEHOLDER.findall(text))):
            found[relative(path)] = matches
    if found:
        detail = "; ".join(f"{path}: {', '.join(sorted(values))}" for path, values in sorted(found.items()))
        message = f"unresolved submission placeholders: {detail}"
        (warnings if allow else errors).append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    files = repository_files()
    check_surface(files, errors)
    check_secrets(files, errors)
    check_markdown_links(files, errors)
    check_readme(errors)
    check_metrics(errors)
    check_placeholders(files, errors, warnings, args.allow_placeholders)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"Public-submission check failed with {len(errors)} error(s).")
        return 1
    print(f"Public-submission check passed for {len(files)} publishable file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
