# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable
import re

from ..state.models_knowledge import KnowledgeChunkRecord

_TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+")
_NON_TEXT_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_DURABLE_TAGS = frozenset(
    {
        "agent-report",
        "follow-up",
        "policy",
        "report",
        "report-outcome",
        "routine-run",
        "shared-memory",
    }
)


def select_canonical_text_anchor(
    chunks: Iterable[KnowledgeChunkRecord],
    *,
    title: str,
    content: str,
    source_ref: str | None = None,
    tags: Iterable[str] | None = None,
) -> KnowledgeChunkRecord | None:
    chunk_list = list(chunks)
    normalized_source_ref = str(source_ref or "").strip()
    if normalized_source_ref:
        source_matches = [
            chunk
            for chunk in chunk_list
            if str(chunk.source_ref or "").strip() == normalized_source_ref
        ]
        if source_matches:
            return _latest_chunk(source_matches)

    normalized_title = _normalize_text(title)
    normalized_content = _normalize_text(content)
    exact_matches = [
        chunk
        for chunk in chunk_list
        if _normalize_text(chunk.title) == normalized_title
        and _normalize_text(chunk.content) == normalized_content
    ]
    if exact_matches:
        return _latest_chunk(exact_matches)

    if not _is_durable_candidate(tags):
        return None

    similar_matches = [
        chunk
        for chunk in chunk_list
        if _normalize_text(chunk.title) == normalized_title
        and _token_overlap(chunk.content, content) >= 0.6
    ]
    if similar_matches:
        return _latest_chunk(similar_matches)
    return None


def merge_canonical_text(*, existing_content: str, incoming_content: str) -> str:
    normalized_existing = _normalize_text(existing_content)
    normalized_incoming = _normalize_text(incoming_content)
    if not normalized_existing:
        return str(incoming_content or "").strip()
    if not normalized_incoming:
        return str(existing_content or "").strip()
    if normalized_existing == normalized_incoming:
        return str(existing_content or "").strip()
    if normalized_existing in normalized_incoming:
        return str(incoming_content or "").strip()
    if normalized_incoming in normalized_existing:
        return str(existing_content or "").strip()

    merged_lines: list[str] = []
    seen: set[str] = set()
    for line in [*str(existing_content or "").splitlines(), *str(incoming_content or "").splitlines()]:
        normalized_line = _normalize_text(line)
        if not normalized_line or normalized_line in seen:
            continue
        seen.add(normalized_line)
        merged_lines.append(line.strip())
    return "\n".join(merged_lines).strip()


def _latest_chunk(chunks: Iterable[KnowledgeChunkRecord]) -> KnowledgeChunkRecord:
    return sorted(
        list(chunks),
        key=lambda item: str(item.updated_at or item.created_at or ""),
        reverse=True,
    )[0]


def _normalize_text(value: object | None) -> str:
    lowered = str(value or "").strip().lower()
    return _NON_TEXT_RE.sub(" ", lowered).strip()


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(_TOKEN_RE.findall(_normalize_text(left)))
    right_tokens = set(_TOKEN_RE.findall(_normalize_text(right)))
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens.union(right_tokens)
    if not union:
        return 0.0
    return len(left_tokens.intersection(right_tokens)) / len(union)


def _is_durable_candidate(tags: Iterable[str] | None) -> bool:
    normalized_tags = {
        str(item or "").strip().lower()
        for item in (tags or [])
        if str(item or "").strip()
    }
    return bool(normalized_tags & _DURABLE_TAGS)
