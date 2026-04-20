# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from ..contracts import RetrievalHit
from .chunker import chunk_file, tokenize_text
from .index_store import iter_local_repo_files

_QUERY_EXPANSIONS = {
    "fields": {"field", "payload", "payloads", "sources", "findings", "conflicts", "gaps"},
    "reads": {"read", "reads", "serialize", "serialized", "exposes"},
    "truth": {"truth", "formal", "writeback", "brief", "payload"},
    "surface": {"surface", "summary", "payload", "projection"},
}

_GENERIC_QUERY_TOKEN_WEIGHTS = {
    "brief": 0.35,
    "field": 0.3,
    "fields": 0.3,
    "findings": 0.35,
    "formal": 0.3,
    "gaps": 0.35,
    "payload": 0.35,
    "payloads": 0.35,
    "projection": 0.35,
    "read": 0.3,
    "reads": 0.3,
    "sources": 0.35,
    "summary": 0.35,
    "surface": 0.3,
    "truth": 0.3,
    "which": 0.0,
}

_ANSWER_SURFACE_BONUS = {
    "brief": 0.01,
    "conflicts": 0.05,
    "findings": 0.04,
    "gaps": 0.05,
    "payload": 0.03,
    "payloads": 0.03,
    "projection": 0.03,
    "read": 0.06,
    "reads": 0.06,
    "serialize": 0.06,
    "serialized": 0.06,
    "sources": 0.05,
    "summary": 0.02,
    "writeback": 0.03,
}

def _expand_query_tokens(query_tokens: set[str]) -> set[str]:
    expanded = set(query_tokens)
    for token in list(query_tokens):
        expanded.update(_QUERY_EXPANSIONS.get(token, set()))
    return expanded


def _token_weight(token: str) -> float:
    return _GENERIC_QUERY_TOKEN_WEIGHTS.get(token, 1.0)


def _weighted_overlap_ratio(query_tokens: set[str], matched_tokens: set[str]) -> float:
    total_weight = sum(_token_weight(token) for token in query_tokens)
    if total_weight <= 0:
        return 0.0
    matched_weight = sum(_token_weight(token) for token in matched_tokens)
    return matched_weight / total_weight


def _answer_surface_bonus(tokens: set[str]) -> float:
    return min(0.2, sum(_ANSWER_SURFACE_BONUS.get(token, 0.0) for token in tokens))


def _source_area_weight(file_path: str) -> float:
    normalized = file_path.replace("\\", "/")
    if normalized.startswith("src/"):
        return 0.35
    if normalized.startswith("tests/"):
        return -0.1
    if normalized.startswith("docs/"):
        return -0.2
    return 0.0


def _semantic_score(
    *,
    original_query_tokens: set[str],
    expanded_query_tokens: set[str],
    chunk_tokens: set[str],
    file_path: str,
) -> tuple[float, float]:
    if not original_query_tokens or not chunk_tokens:
        return 0.0, 0.0
    original_overlap = original_query_tokens & chunk_tokens
    expansion_overlap = (expanded_query_tokens - original_query_tokens) & chunk_tokens
    if not original_overlap and not expansion_overlap:
        return 0.0, 0.0
    overlap_score = _weighted_overlap_ratio(original_query_tokens, original_overlap)
    expansion_score = min(0.18, len(expansion_overlap) * 0.015)
    path_tokens = tokenize_text(file_path.replace("/", " "))
    path_overlap = _weighted_overlap_ratio(original_query_tokens, original_query_tokens & path_tokens)
    expanded_path_overlap = min(
        0.3,
        len(((expanded_query_tokens - original_query_tokens) & path_tokens)) * 0.1,
    )
    answer_bonus = _answer_surface_bonus(expansion_overlap | original_overlap)
    final_score = (
        overlap_score
        + expansion_score
        + (path_overlap * 0.35)
        + expanded_path_overlap
        + answer_bonus
        + _source_area_weight(file_path)
    )
    return final_score, overlap_score


def search_local_repo_semantic(
    *,
    workspace_root: Path,
    query: str,
    max_hits: int = 20,
) -> list[RetrievalHit]:
    root = Path(workspace_root)
    original_query_tokens = tokenize_text(query)
    query_tokens = _expand_query_tokens(original_query_tokens)
    if not original_query_tokens:
        return []
    hits: list[RetrievalHit] = []
    for path in iter_local_repo_files(root):
        for chunk in chunk_file(path, workspace_root=root):
            score, relevance = _semantic_score(
                original_query_tokens=original_query_tokens,
                expanded_query_tokens=query_tokens,
                chunk_tokens=chunk.tokens,
                file_path=chunk.file_path,
            )
            if score <= 0:
                continue
            snippet_line = next(
                (line.strip() for line in chunk.text.splitlines() if line.strip()),
                "",
            )
            hits.append(
                RetrievalHit(
                    source_kind="local_repo",
                    provider_kind="semantic",
                    hit_kind="chunk",
                    ref=chunk.file_path,
                    normalized_ref=chunk.file_path,
                    title=Path(chunk.file_path).name,
                    snippet=snippet_line,
                    span={"line": chunk.start_line},
                    score=round(score, 4),
                    relevance_score=round(relevance, 4),
                    answerability_score=round(min(0.95, relevance + 0.15), 4),
                    freshness_score=0.0,
                    credibility_score=1.0,
                    structural_score=round(min(0.9, score), 4),
                    why_matched="semantic token overlap with repository chunk",
                    metadata={
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "matched_terms": sorted(query_tokens & chunk.tokens),
                    },
                )
            )
    hits.sort(
        key=lambda hit: (
            hit.score,
            hit.answerability_score,
            -int(hit.metadata.get("start_line", 0) or 0),
        ),
        reverse=True,
    )
    return hits[:max_hits]


__all__ = ["search_local_repo_semantic"]
