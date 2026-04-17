# -*- coding: utf-8 -*-
"""Formal knowledge chunk service for V2 knowledge retrieval."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..memory.canonical_compaction import merge_canonical_text, select_canonical_text_anchor
from ..industry.identity import normalize_industry_role_id
from .models_knowledge import KnowledgeChunkRecord
from .repositories import BaseKnowledgeChunkRepository

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_-]+")
_MEMORY_PREFIX = "memory:"
_MEMORY_SCOPE_TYPES = frozenset({"global", "industry", "agent", "task", "work_context"})


class StateKnowledgeService:
    """Manage formal knowledge chunks in the unified state layer."""

    def __init__(
        self,
        *,
        repository: BaseKnowledgeChunkRepository,
        derived_index_service: object | None = None,
        reflection_service: object | None = None,
    ) -> None:
        self._repository = repository
        self._derived_index_service = derived_index_service
        self._reflection_service = reflection_service
        self._memory_sleep_service: object | None = None

    def set_derived_index_service(self, derived_index_service: object | None) -> None:
        self._derived_index_service = derived_index_service

    def set_reflection_service(self, reflection_service: object | None) -> None:
        self._reflection_service = reflection_service

    def set_memory_sleep_service(self, memory_sleep_service: object | None) -> None:
        self._memory_sleep_service = memory_sleep_service

    def list_chunks(
        self,
        *,
        query: str | None = None,
        role: str | None = None,
        document_id: str | None = None,
        limit: int | None = 50,
    ) -> list[KnowledgeChunkRecord]:
        chunks = self._repository.list_chunks(document_id=document_id)
        ranked = self._filter_and_rank(chunks, query=query, role=role)
        return ranked if limit is None else ranked[:limit]

    def list_documents(
        self,
        *,
        query: str | None = None,
        role: str | None = None,
        limit: int | None = 50,
    ) -> list[dict[str, Any]]:
        all_chunks = self._repository.list_chunks()
        matched_chunks = self._filter_and_rank(
            all_chunks,
            query=query,
            role=role,
        )
        matched_document_ids = {chunk.document_id for chunk in matched_chunks}
        documents: dict[str, list[KnowledgeChunkRecord]] = defaultdict(list)
        for chunk in all_chunks:
            if matched_document_ids and chunk.document_id not in matched_document_ids:
                continue
            if not matched_document_ids and (query or role):
                continue
            documents[chunk.document_id].append(chunk)

        payload: list[dict[str, Any]] = []
        for document_id, document_chunks in documents.items():
            ordered = sorted(document_chunks, key=lambda item: item.chunk_index)
            latest = max(ordered, key=lambda item: item.updated_at or item.created_at)
            payload.append(
                {
                    "document_id": document_id,
                    "title": ordered[0].title,
                    "summary": ordered[0].summary,
                    "source_ref": ordered[0].source_ref,
                    "chunk_count": len(ordered),
                    "tags": _merge_strings(item.tags for item in ordered),
                    "role_bindings": _merge_strings(item.role_bindings for item in ordered),
                    "updated_at": latest.updated_at,
                    "route": f"/api/runtime-center/knowledge?document_id={document_id}",
                },
            )
        payload.sort(
            key=lambda item: str(item.get("updated_at") or ""),
            reverse=True,
        )
        return payload if limit is None else payload[:limit]

    def retrieve(
        self,
        *,
        query: str,
        role: str | None = None,
        limit: int = 5,
    ) -> list[KnowledgeChunkRecord]:
        return self.list_chunks(query=query, role=role, limit=limit)

    def remember_fact(
        self,
        *,
        title: str,
        content: str,
        scope_type: str,
        scope_id: str,
        source_ref: str | None = None,
        role_bindings: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> KnowledgeChunkRecord:
        normalized_scope_type = _normalize_memory_scope_type(scope_type)
        normalized_scope_id = str(scope_id).strip()
        if not normalized_scope_id:
            raise ValueError("Memory scope_id is required")

        document_id = _memory_document_id(
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
        )
        existing_chunks = self._repository.list_chunks(document_id=document_id)
        merged_tags = _normalize_strings(["memory", "fact", *(tags or [])])
        stable_anchor = _select_memory_anchor(
            existing_chunks,
            title=title,
            content=content,
            source_ref=source_ref,
            tags=merged_tags,
        )
        if stable_anchor is not None:
            return self.upsert_chunk(
                chunk_id=stable_anchor.id,
                document_id=document_id,
                title=title,
                content=merge_canonical_text(
                    existing_content=stable_anchor.content,
                    incoming_content=content,
                ),
                source_ref=source_ref,
                chunk_index=stable_anchor.chunk_index,
                role_bindings=role_bindings,
                tags=merged_tags,
            )
        next_chunk_index = (
            max((chunk.chunk_index for chunk in existing_chunks), default=-1) + 1
        )
        return self.upsert_chunk(
            document_id=document_id,
            title=title,
            content=content,
            source_ref=source_ref,
            chunk_index=next_chunk_index,
            role_bindings=role_bindings,
            tags=merged_tags,
        )

    def list_memory(
        self,
        *,
        query: str | None = None,
        role: str | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        global_scope_id: str | None = None,
        include_related_scopes: bool = True,
        limit: int | None = 50,
    ) -> list[KnowledgeChunkRecord]:
        normalized_scope_type = (
            _normalize_memory_scope_type(scope_type)
            if isinstance(scope_type, str) and scope_type.strip()
            else None
        )
        normalized_scope_id = str(scope_id).strip() if isinstance(scope_id, str) else None
        candidate_documents = _candidate_memory_document_ids(
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
            task_id=task_id,
            work_context_id=work_context_id,
            agent_id=agent_id,
            industry_instance_id=industry_instance_id,
            global_scope_id=global_scope_id,
            include_related_scopes=include_related_scopes,
        )
        candidate_document_set = set(candidate_documents)
        scope_priority = {
            document_id: len(candidate_documents) - index
            for index, document_id in enumerate(candidate_documents)
        }
        chunks = [
            chunk
            for chunk in self._repository.list_chunks()
            if _is_memory_document_id(chunk.document_id)
            and (
                not candidate_document_set
                or chunk.document_id in candidate_document_set
            )
        ]
        ranked = self._filter_and_rank(
            chunks,
            query=query,
            role=role,
            scope_priority=scope_priority,
        )
        return ranked if limit is None else ranked[:limit]

    def retrieve_memory(
        self,
        *,
        query: str,
        role: str | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        global_scope_id: str | None = None,
        include_related_scopes: bool = True,
        limit: int = 5,
    ) -> list[KnowledgeChunkRecord]:
        return self.list_memory(
            query=query,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            task_id=task_id,
            work_context_id=work_context_id,
            agent_id=agent_id,
            industry_instance_id=industry_instance_id,
            global_scope_id=global_scope_id,
            include_related_scopes=include_related_scopes,
            limit=limit,
        )

    def describe_memory_document(
        self,
        document_id: str,
    ) -> dict[str, str] | None:
        return _parse_memory_document_id(document_id)

    def get_chunk(self, chunk_id: str) -> KnowledgeChunkRecord | None:
        return self._repository.get_chunk(chunk_id)

    def upsert_chunk(
        self,
        *,
        chunk_id: str | None = None,
        document_id: str,
        title: str,
        content: str,
        source_ref: str | None = None,
        chunk_index: int = 0,
        role_bindings: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> KnowledgeChunkRecord:
        now = datetime.now(timezone.utc)
        existing = self._repository.get_chunk(chunk_id) if chunk_id else None
        if (
            existing is not None
            and existing.document_id != document_id
            and _is_memory_document_id(existing.document_id)
        ):
            raise ValueError("Formal memory scope drift is not allowed for existing chunk")
        record = KnowledgeChunkRecord(
            id=chunk_id or (existing.id if existing is not None else str(uuid4())),
            document_id=document_id,
            title=title.strip(),
            content=content.strip(),
            summary=_summarize_content(content),
            source_ref=source_ref.strip() if source_ref else None,
            chunk_index=chunk_index,
            role_bindings=_normalize_strings(role_bindings),
            tags=_normalize_strings(tags),
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        stored = self._repository.upsert_chunk(record)
        indexer = getattr(self._derived_index_service, "upsert_knowledge_chunk", None)
        if callable(indexer):
            try:
                indexer(stored)
            except Exception:
                pass
        self._mark_memory_sleep_dirty(stored.document_id, source_ref=stored.source_ref or stored.id)
        self._reflect_memory_scope(stored.document_id)
        self._refresh_memory_sleep_projection(stored.document_id)
        return stored

    def delete_chunk(self, chunk_id: str) -> bool:
        chunk = self._repository.get_chunk(chunk_id)
        deleted = self._repository.delete_chunk(chunk_id)
        if deleted:
            remover = getattr(self._derived_index_service, "delete_source", None)
            if callable(remover):
                try:
                    remover(source_type="knowledge_chunk", source_ref=chunk_id)
                except Exception:
                    pass
            if chunk is not None:
                self._mark_memory_sleep_dirty(chunk.document_id, source_ref=chunk.source_ref or chunk.id)
                self._reflect_memory_scope(chunk.document_id)
                self._refresh_memory_sleep_projection(chunk.document_id)
        return deleted

    def import_document(
        self,
        *,
        title: str,
        content: str,
        source_ref: str | None = None,
        role_bindings: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized_title = title.strip()
        normalized_content = content.strip()
        if not normalized_title:
            raise ValueError("Knowledge document title is required")
        if not normalized_content:
            raise ValueError("Knowledge document content is required")

        document_id = f"knowledge-doc:{uuid4()}"
        chunks = _split_markdown_chunks(normalized_title, normalized_content)
        stored_chunks = [
            self.upsert_chunk(
                document_id=document_id,
                title=chunk_title,
                content=chunk_content,
                source_ref=source_ref,
                chunk_index=index,
                role_bindings=role_bindings,
                tags=tags,
            )
            for index, (chunk_title, chunk_content) in enumerate(chunks)
        ]
        return {
            "document_id": document_id,
            "title": normalized_title,
            "source_ref": source_ref,
            "chunk_count": len(stored_chunks),
            "chunks": [chunk.model_dump(mode="json") for chunk in stored_chunks],
        }

    def ingest_research_session(
        self,
        *,
        session: object,
        rounds: list[object] | None = None,
    ) -> dict[str, Any]:
        rounds = list(rounds or [])
        session_id = str(getattr(session, "id", "") or "").strip()
        goal = str(getattr(session, "goal", "") or "").strip()
        brief = _research_mapping(getattr(session, "brief", None))
        stable_findings = _research_text_lines(getattr(session, "stable_findings", None))
        stable_lookup = {item.casefold() for item in stable_findings}
        working_findings = _normalize_strings(
            [
                finding
                for round_record in rounds
                for finding in _research_text_lines(getattr(round_record, "new_findings", None))
                if finding.casefold() not in stable_lookup
            ],
        )
        sources = _dedupe_source_rows(
            [
                source
                for round_record in rounds
                for source in _research_mapping_list(getattr(round_record, "sources", None))
            ],
        )
        content = _build_research_memory_content(
            goal=goal,
            brief=brief,
            stable_findings=stable_findings,
            working_findings=working_findings,
            sources=sources,
        )
        if not content:
            return {
                "research_session_id": session_id or None,
                "work_context_chunk_ids": [],
                "industry_document_id": None,
                "source_refs": [],
            }

        source_ref = f"research-session:{session_id}" if session_id else None
        tags = _normalize_strings(
            [
                "research",
                "research-session",
                "summary",
                "source-collection" if sources else "",
            ],
        )
        result = {
            "research_session_id": session_id or None,
            "work_context_chunk_ids": [],
            "industry_document_id": None,
            "source_refs": _normalize_strings(
                [
                    source.get("source_ref")
                    or source.get("normalized_ref")
                    or source.get("source_id")
                    for source in sources
                ],
            ),
        }

        work_context_id = str(getattr(session, "work_context_id", "") or "").strip()
        if work_context_id:
            chunk = self.remember_fact(
                title=goal or f"Research session {session_id or 'summary'}",
                content=content,
                scope_type="work_context",
                scope_id=work_context_id,
                source_ref=source_ref,
                tags=tags,
            )
            result["work_context_chunk_ids"] = [chunk.id]

        industry_instance_id = str(
            getattr(session, "industry_instance_id", "") or "",
        ).strip()
        if industry_instance_id:
            chunk = self.remember_fact(
                title=goal or f"Research session {session_id or 'summary'}",
                content=content,
                scope_type="industry",
                scope_id=industry_instance_id,
                source_ref=source_ref,
                tags=tags,
            )
            result["industry_document_id"] = chunk.document_id
        return result

    def _filter_and_rank(
        self,
        chunks: list[KnowledgeChunkRecord],
        *,
        query: str | None,
        role: str | None,
        scope_priority: dict[str, int] | None = None,
    ) -> list[KnowledgeChunkRecord]:
        normalized_role = role.strip().lower() if isinstance(role, str) and role.strip() else None
        query_terms = _tokenize(query)
        ranked: list[tuple[int, float, str, KnowledgeChunkRecord]] = []
        for chunk in chunks:
            if normalized_role and not _matches_role(chunk, normalized_role):
                continue
            if query_terms:
                score = _chunk_score(chunk, query_terms, normalized_role)
                if score <= 0:
                    continue
            else:
                score = 1
            priority = float((scope_priority or {}).get(chunk.document_id, 0))
            ranked.append((priority, score, str(chunk.updated_at), chunk))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [item[3] for item in ranked]

    def _reflect_memory_scope(self, document_id: str) -> None:
        scope = _parse_memory_document_id(document_id)
        if scope is None:
            return
        reflector = getattr(self._reflection_service, "reflect", None)
        if not callable(reflector):
            return
        try:
            reflector(
                scope_type=scope["scope_type"],
                scope_id=scope["scope_id"],
                trigger_kind="knowledge-upsert",
                create_learning_proposals=False,
            )
        except Exception:
            return

    def _mark_memory_sleep_dirty(self, document_id: str, *, source_ref: str | None) -> None:
        scope = _parse_memory_document_id(document_id)
        marker = getattr(self._memory_sleep_service, "mark_scope_dirty", None)
        if scope is None or not callable(marker):
            return
        industry_instance_id = None
        if scope["scope_type"] == "industry":
            industry_instance_id = scope["scope_id"]
        elif scope["scope_type"] == "work_context":
            industry_instance_id = _parse_industry_instance_id_from_source_ref(source_ref)
        try:
            marker(
                scope_type=scope["scope_type"],
                scope_id=scope["scope_id"],
                industry_instance_id=industry_instance_id,
                reason="knowledge-upsert",
                source_ref=source_ref,
            )
        except Exception:
            return

    def _refresh_memory_sleep_projection(self, document_id: str) -> None:
        scope = _parse_memory_document_id(document_id)
        refresher = getattr(self._memory_sleep_service, "refresh_scope_projection", None)
        if scope is None or not callable(refresher):
            return
        try:
            refresher(
                scope_type=scope["scope_type"],
                scope_id=scope["scope_id"],
                trigger_kind="knowledge-upsert",
            )
        except Exception:
            return


def _split_markdown_chunks(title: str, content: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = title
    current_lines: list[str] = []
    saw_heading = False
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        heading = _heading_text(line)
        if heading is not None:
            saw_heading = True
            if any(part.strip() for part in current_lines):
                sections.append((current_title, "\n".join(current_lines).strip()))
                current_lines = []
            current_title = heading
            continue
        current_lines.append(raw_line)
    if any(part.strip() for part in current_lines):
        sections.append((current_title, "\n".join(current_lines).strip()))
    if saw_heading and sections:
        return sections
    return _split_by_paragraph_window(title, content)


def _split_by_paragraph_window(
    title: str,
    content: str,
    *,
    max_chars: int = 1200,
) -> list[tuple[str, str]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs:
        return [(title, content.strip())]
    chunks: list[tuple[str, str]] = []
    current_parts: list[str] = []
    current_size = 0
    for paragraph in paragraphs:
        projected = current_size + len(paragraph) + (2 if current_parts else 0)
        if current_parts and projected > max_chars:
            chunks.append((title, "\n\n".join(current_parts).strip()))
            current_parts = [paragraph]
            current_size = len(paragraph)
            continue
        current_parts.append(paragraph)
        current_size = projected
    if current_parts:
        chunks.append((title, "\n\n".join(current_parts).strip()))
    return chunks


def _heading_text(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    heading = stripped.lstrip("#").strip()
    return heading or None


def _summarize_content(content: str, *, limit: int = 180) -> str:
    collapsed = " ".join(content.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3].rstrip()}..."


def _tokenize(query: str | None) -> list[str]:
    if not isinstance(query, str) or not query.strip():
        return []
    return [token.lower() for token in _TOKEN_RE.findall(query) if token]


def _matches_role(chunk: KnowledgeChunkRecord, role: str) -> bool:
    if not chunk.role_bindings:
        return True
    normalized_role = normalize_industry_role_id(role) or role.lower()
    role_bindings = {
        normalize_industry_role_id(item) or item.lower()
        for item in chunk.role_bindings
    }
    return normalized_role in role_bindings


def _chunk_score(
    chunk: KnowledgeChunkRecord,
    query_terms: list[str],
    role: str | None,
) -> int:
    title = chunk.title.lower()
    content = chunk.content.lower()
    tags = " ".join(chunk.tags).lower()
    roles = " ".join(chunk.role_bindings).lower()
    score = 0
    for term in query_terms:
        if term in title:
            score += 5
        if term in tags:
            score += 4
        if term in roles:
            score += 3
        if term in content:
            score += 1 + min(content.count(term), 3)
    if score > 0 and role and role in roles:
        score += 2
    return score


def _normalize_strings(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


def _merge_strings(groups: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(item)
    return merged


def _research_mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _research_mapping_list(value: object | None) -> list[dict[str, Any]]:
    if isinstance(value, list):
        items = value
    elif value is None:
        items = []
    else:
        items = [value]
    normalized: list[dict[str, Any]] = []
    for item in items:
        mapping = _research_mapping(item)
        if mapping:
            normalized.append(mapping)
    return normalized


def _research_text_lines(value: object) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
    else:
        items = []
    return _normalize_strings([str(item or "").strip() for item in items])


def _dedupe_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(
            row.get("normalized_ref")
            or row.get("source_ref")
            or row.get("source_id")
            or row.get("title")
            or "",
        ).strip()
        if not key:
            key = str(row)
        lowered = key.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(dict(row))
    return deduped


def _source_display_text(source: dict[str, Any]) -> str | None:
    title = str(source.get("title") or "").strip()
    ref = str(
        source.get("source_ref")
        or source.get("normalized_ref")
        or source.get("source_id")
        or "",
    ).strip()
    snippet = str(source.get("snippet") or "").strip()
    parts = [part for part in (title, ref, snippet) if part]
    if not parts:
        return None
    return " | ".join(parts)


def _build_research_memory_content(
    *,
    goal: str,
    brief: dict[str, Any],
    stable_findings: list[str],
    working_findings: list[str],
    sources: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    if goal:
        lines.append(f"Goal: {goal}")
    question = str(brief.get("question") or "").strip()
    why_needed = str(brief.get("why_needed") or "").strip()
    done_when = str(brief.get("done_when") or "").strip()
    if question:
        lines.append(f"Question: {question}")
    if why_needed:
        lines.append(f"Why needed: {why_needed}")
    if done_when:
        lines.append(f"Done when: {done_when}")
    if stable_findings:
        lines.append("Stable findings:")
        lines.extend(f"- {item}" for item in stable_findings)
    if working_findings:
        lines.append("Working findings:")
        lines.extend(f"- {item}" for item in working_findings)
    rendered_sources = [
        rendered
        for rendered in (_source_display_text(source) for source in sources)
        if rendered is not None
    ]
    if rendered_sources:
        lines.append("Sources:")
        lines.extend(f"- {item}" for item in rendered_sources)
    return "\n".join(lines).strip()


def _normalize_memory_scope_type(scope_type: str) -> str:
    normalized = str(scope_type).strip().lower()
    if normalized not in _MEMORY_SCOPE_TYPES:
        raise ValueError(
            "Memory scope_type must be one of: global, industry, agent, task, work_context",
        )
    return normalized


def _memory_document_id(*, scope_type: str, scope_id: str) -> str:
    return f"{_MEMORY_PREFIX}{scope_type}:{scope_id}"


def _is_memory_document_id(document_id: str) -> bool:
    return _parse_memory_document_id(document_id) is not None


def _parse_memory_document_id(document_id: str) -> dict[str, str] | None:
    if not isinstance(document_id, str) or not document_id.startswith(_MEMORY_PREFIX):
        return None
    remainder = document_id[len(_MEMORY_PREFIX) :]
    scope_type, separator, scope_id = remainder.partition(":")
    if not separator or not scope_type or not scope_id:
        return None
    normalized_scope_type = scope_type.strip().lower()
    if normalized_scope_type not in _MEMORY_SCOPE_TYPES:
        return None
    normalized_scope_id = scope_id.strip()
    if not normalized_scope_id:
        return None
    return {
        "scope_type": normalized_scope_type,
        "scope_id": normalized_scope_id,
        "document_id": document_id,
    }


def _parse_industry_instance_id_from_source_ref(source_ref: str | None) -> str | None:
    text = str(source_ref or "").strip()
    if not text.startswith("industry:"):
        return None
    remainder = text.split(":", 1)[1].strip()
    if not remainder:
        return None
    industry_instance_id = remainder.split(":", 1)[0].strip()
    return industry_instance_id or None


def _select_memory_anchor(
    chunks: list[KnowledgeChunkRecord],
    *,
    title: str,
    content: str,
    source_ref: str | None,
    tags: list[str] | None,
) -> KnowledgeChunkRecord | None:
    return select_canonical_text_anchor(
        chunks,
        title=title,
        content=content,
        source_ref=source_ref,
        tags=tags,
    )


def _candidate_memory_document_ids(
    *,
    scope_type: str | None,
    scope_id: str | None,
    task_id: str | None,
    work_context_id: str | None,
    agent_id: str | None,
    industry_instance_id: str | None,
    global_scope_id: str | None,
    include_related_scopes: bool,
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _add_candidate(candidate_scope_type: str, candidate_scope_id: str | None) -> None:
        normalized_scope_id = (
            str(candidate_scope_id).strip()
            if isinstance(candidate_scope_id, str)
            else ""
        )
        if not normalized_scope_id:
            return
        document_id = _memory_document_id(
            scope_type=candidate_scope_type,
            scope_id=normalized_scope_id,
        )
        if document_id in seen:
            return
        seen.add(document_id)
        candidates.append(document_id)

    if scope_type and scope_id:
        _add_candidate(scope_type, scope_id)
        if not include_related_scopes:
            return candidates
    if not include_related_scopes:
        return candidates
    for candidate_scope_type, candidate_scope_id in (
        ("work_context", work_context_id),
        ("task", task_id),
        ("agent", agent_id),
        ("industry", industry_instance_id),
        ("global", global_scope_id),
    ):
        _add_candidate(candidate_scope_type, candidate_scope_id)
    return candidates
