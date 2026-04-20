# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import os
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path

from .index_models import CodeSymbolRecord, RepositoryIndexSnapshot

_BLOCKED_DIR_NAMES = {
    "dist",
    "build",
    "node_modules",
    ".vite",
    "coverage",
    "__pycache__",
    ".git",
    ".github",
    ".idea",
    ".pytest_cache",
    ".worktrees",
    "logs",
}
_TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".md"}
_UNTRACKED_CODE_ROOTS = ("src/", "tests/", "console/src/", "docs/")


def iter_local_repo_files(workspace_root: Path, *, suffixes: set[str] | None = None) -> Iterator[Path]:
    root = Path(workspace_root)
    allowed_suffixes = suffixes or _TEXT_SUFFIXES
    yielded: set[Path] = set()
    for relative_path in _iter_git_known_relative_paths(root):
        path = root / relative_path
        if not path.is_file():
            continue
        if _should_skip_relative_path(relative_path):
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        resolved = path.resolve()
        if resolved in yielded:
            continue
        yielded.add(resolved)
        yield path


def _iter_git_known_relative_paths(workspace_root: Path) -> Iterator[Path]:
    git_relative_paths = _run_git_ls_files(workspace_root)
    if git_relative_paths:
        for relative_path in git_relative_paths:
            yield relative_path
        return
    yield from _iter_fallback_relative_paths(workspace_root)


def _run_git_ls_files(workspace_root: Path) -> list[Path]:
    commands = [
        ["git", "ls-files", "--cached", "--modified"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    relative_paths: list[Path] = []
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=workspace_root,
                capture_output=True,
                check=True,
                text=True,
                encoding="utf-8",
            )
        except (OSError, subprocess.CalledProcessError):
            return []
        for line in completed.stdout.splitlines():
            normalized = line.strip().replace("\\", "/")
            if not normalized:
                continue
            if command[2] == "--others" and not normalized.startswith(_UNTRACKED_CODE_ROOTS):
                continue
            relative_paths.append(Path(normalized))
    return relative_paths


def _iter_fallback_relative_paths(workspace_root: Path) -> Iterator[Path]:
    for current_root, dir_names, file_names in os.walk(workspace_root):
        dir_names[:] = [name for name in dir_names if name not in _BLOCKED_DIR_NAMES and not name.startswith(".") and not name.startswith("tmp") and not name.startswith("workflow_")]
        current_root_path = Path(current_root)
        for file_name in file_names:
            relative_path = (current_root_path / file_name).relative_to(workspace_root)
            yield relative_path


def _should_skip_relative_path(relative_path: Path) -> bool:
    relative_parts = relative_path.parts
    for part in relative_parts:
        if part in _BLOCKED_DIR_NAMES:
            return True
        if part.startswith("."):
            return True
        if part.startswith("tmp"):
            return True
        if part.startswith("workflow_"):
            return True
    return False


def build_repository_index_snapshot(workspace_root: Path, *, symbols: Iterable[CodeSymbolRecord] = ()) -> RepositoryIndexSnapshot:
    root = Path(workspace_root)
    files = list(iter_local_repo_files(root))
    symbol_list = list(symbols)
    return RepositoryIndexSnapshot(
        workspace_root=str(root),
        file_count=len(files),
        chunk_count=len(files),
        symbol_count=len(symbol_list),
    )


def extract_python_symbols(workspace_root: Path) -> list[CodeSymbolRecord]:
    root = Path(workspace_root)
    records: list[CodeSymbolRecord] = []
    for path in iter_local_repo_files(root, suffixes={".py"}):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        relative_path = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                records.append(
                    CodeSymbolRecord(
                        symbol_name=node.name,
                        symbol_kind="function",
                        file_path=relative_path,
                        line=getattr(node, "lineno", 1),
                        container_name="module",
                        language="python",
                        signature=f"{node.name}(...)",
                    )
                )
            elif isinstance(node, ast.ClassDef):
                records.append(
                    CodeSymbolRecord(
                        symbol_name=node.name,
                        symbol_kind="class",
                        file_path=relative_path,
                        line=getattr(node, "lineno", 1),
                        container_name="module",
                        language="python",
                        signature=node.name,
                    )
                )
    return records


__all__ = [
    "build_repository_index_snapshot",
    "extract_python_symbols",
    "iter_local_repo_files",
]
