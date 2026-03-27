#!/usr/bin/env python3
"""Guardrails for repository source-file shape."""
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOTS = (
    ROOT / "src",
    ROOT / "tests",
    ROOT / "console" / "src",
)
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
BLOCKED_PARTS = {
    "dist",
    "build",
    "node_modules",
    ".vite",
    "coverage",
    "__pycache__",
}
MAX_SOURCE_LINES = 2000
BANNED_SUFFIXES = (".broken", ".bak", ".orig", ".rej")


def _iter_candidate_files() -> list[Path]:
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in BLOCKED_PARTS for part in path.parts):
                continue
            files.append(path)
    return files


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def main() -> int:
    violations: list[str] = []
    for path in sorted(_iter_candidate_files()):
        rel = path.relative_to(ROOT).as_posix()
        lower_name = path.name.casefold()
        if lower_name.endswith(BANNED_SUFFIXES):
            violations.append(
                f"backup-or-broken file is not allowed in maintained source paths: {rel}",
            )
            continue
        if path.suffix.casefold() not in SOURCE_EXTENSIONS:
            continue
        line_count = _line_count(path)
        if line_count > MAX_SOURCE_LINES:
            violations.append(
                f"source file exceeds {MAX_SOURCE_LINES} lines: {rel} ({line_count})",
            )
    if not violations:
        print("repo-shape: ok")
        return 0
    print("repo-shape: violations found", file=sys.stderr)
    for item in violations:
        print(f" - {item}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
