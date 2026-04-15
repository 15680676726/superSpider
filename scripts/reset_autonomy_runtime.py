#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _runtime_targets(root: Path) -> list[Path]:
    return [root / "memory" / "qmd"]


def _destructive_runtime_targets(root: Path) -> list[Path]:
    return [
        root / "state" / "phase1.sqlite3",
        root / "evidence" / "phase1.sqlite3",
        root / "learning" / "phase1.sqlite3",
    ]


def reset_autonomy_runtime(
    *,
    root: Path,
    dry_run: bool = False,
    allow_destructive: bool = False,
) -> dict[str, object]:
    resolved_root = root.resolve()
    candidate_targets = _runtime_targets(resolved_root)
    if allow_destructive:
        candidate_targets = _destructive_runtime_targets(resolved_root) + candidate_targets
    existing_targets = [path for path in candidate_targets if path.exists()]
    removed_paths = [str(path) for path in existing_targets]

    if not dry_run:
        for path in existing_targets:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    return {
        "root": str(resolved_root),
        "dry_run": dry_run,
        "allow_destructive": allow_destructive,
        "removed_paths": removed_paths,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove CoPaw autonomy runtime state so the hard-cut kernel can boot cleanly.",
    )
    parser.add_argument(
        "--root",
        default=str(_default_root()),
        help="Workspace root. Defaults to the repository root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List removable runtime artifacts without deleting them.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Also remove primary runtime databases under state/evidence/learning.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = reset_autonomy_runtime(
        root=Path(args.root),
        dry_run=bool(args.dry_run),
        allow_destructive=bool(args.force),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
