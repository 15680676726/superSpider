# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from ..contracts import RetrievalHit
from .chunker import tokenize_text
from .index_store import iter_local_repo_files


def _source_area_weight(file_path: str) -> float:
    normalized = file_path.replace("\\", "/")
    if normalized.startswith("src/"):
        return 0.25
    if normalized.startswith("tests/"):
        return -0.15
    if normalized.startswith("docs/"):
        return -0.25
    return 0.0


def search_local_repo_exact(*, workspace_root: Path, query: str, max_hits: int = 20) -> list[RetrievalHit]:
    root = Path(workspace_root)
    normalized_query = query.strip()
    query_tokens = tokenize_text(normalized_query)
    if not normalized_query:
        return []
    hits: list[RetrievalHit] = []
    for path in iter_local_repo_files(root):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match_index = content.find(normalized_query)
        if match_index < 0:
            continue
        line_number = content[:match_index].count("\n") + 1
        line = content.splitlines()[line_number - 1] if content.splitlines() else ""
        relative_path = path.relative_to(root).as_posix()
        content_tokens = tokenize_text(content)
        token_coverage = len(query_tokens & content_tokens) / max(1, len(query_tokens))
        path_overlap = len(query_tokens & tokenize_text(relative_path.replace("/", " "))) / max(1, len(query_tokens))
        source_area_weight = _source_area_weight(relative_path)
        score = round(0.45 + (token_coverage * 0.25) + (path_overlap * 0.1) + source_area_weight, 4)
        answerability = round(
            min(0.9, 0.35 + (token_coverage * 0.35) + (path_overlap * 0.15) + max(source_area_weight, 0.0)),
            4,
        )
        hits.append(
            RetrievalHit(
                source_kind="local_repo",
                provider_kind="exact",
                hit_kind="file",
                ref=relative_path,
                normalized_ref=relative_path,
                title=path.name,
                snippet=line.strip(),
                span={"line": line_number},
                score=score,
                relevance_score=round(token_coverage, 4),
                answerability_score=answerability,
                credibility_score=1.0,
                structural_score=round(min(0.85, 0.45 + path_overlap + max(source_area_weight, 0.0)), 4),
                why_matched=f"exact text match for '{normalized_query}'",
            )
        )
        if len(hits) >= max_hits:
            break
    return hits


__all__ = ["search_local_repo_exact"]
