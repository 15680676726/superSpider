# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from ..contracts import RetrievalHit
from .index_store import extract_python_symbols


def search_local_repo_symbols(*, workspace_root: Path, query: str, max_hits: int = 20) -> list[RetrievalHit]:
    normalized_query = query.strip()
    if not normalized_query:
        return []
    hits: list[RetrievalHit] = []
    for symbol in extract_python_symbols(Path(workspace_root)):
        if normalized_query not in symbol.symbol_name:
            continue
        hits.append(
            RetrievalHit(
                source_kind="local_repo",
                provider_kind="symbol",
                hit_kind="symbol",
                ref=symbol.file_path,
                normalized_ref=symbol.file_path,
                title=symbol.symbol_name,
                snippet=symbol.signature,
                span={"line": symbol.line},
                score=0.98,
                relevance_score=0.98,
                answerability_score=0.9,
                credibility_score=1.0,
                structural_score=0.95,
                why_matched=f"matched python symbol '{symbol.symbol_name}'",
                metadata={
                    "symbol_kind": symbol.symbol_kind,
                    "container_name": symbol.container_name,
                    "language": symbol.language,
                },
            )
        )
        if len(hits) >= max_hits:
            break
    return hits


__all__ = ["search_local_repo_symbols"]
