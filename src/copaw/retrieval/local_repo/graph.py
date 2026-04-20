# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from .index_store import iter_local_repo_files


def build_local_repo_import_graph(workspace_root: Path) -> dict[str, list[str]]:
    root = Path(workspace_root)
    graph: dict[str, list[str]] = {}
    for path in iter_local_repo_files(root, suffixes={".py"}):
        graph[path.relative_to(root).as_posix()] = []
    return graph


__all__ = ["build_local_repo_import_graph"]
