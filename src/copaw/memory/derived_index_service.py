# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Iterable

from .models import MemoryRebuildSummary, MemoryScopeSelector, utc_now
from ..state import (
    AgentReportRecord,
    KnowledgeChunkRecord,
    MemoryEntityViewRecord,
    MemoryFactIndexRecord,
    MemoryOpinionViewRecord,
    MemoryReflectionRunRecord,
    ReportRecord,
    RoutineRunRecord,
    StrategyMemoryRecord,
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}")
_MEMORY_DOCUMENT_PREFIX = "memory:"
_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "over",
    "after",
    "before",
    "should",
    "must",
    "need",
    "have",
    "has",
    "only",
    "never",
    "always",
    "task",
    "goal",
    "agent",
    "report",
    "memory",
    "summary",
    "evidence",
    "runtime",
    "status",
    "result",
    "industry",
    "global",
    "scope",
    "record",
}
_OPINION_CUES: tuple[tuple[str, str], ...] = (
    ("do not", "caution"),
    ("don't", "caution"),
    ("must", "requirement"),
    ("need to", "requirement"),
    ("needs to", "requirement"),
    ("requires", "requirement"),
    ("required", "requirement"),
    ("prefer", "preference"),
    ("preferred", "preference"),
    ("avoid", "caution"),
    ("never", "caution"),
    ("only", "requirement"),
    ("should", "recommendation"),
)


def normalize_memory_scope_type(scope_type: str | None) -> str:
    normalized = str(scope_type or "").strip().lower()
    return (
        normalized
        if normalized in {"global", "industry", "agent", "task", "work_context"}
        else "global"
    )


def normalize_scope_id(scope_id: str | None) -> str:
    normalized = str(scope_id or "").strip()
    return normalized or "runtime"


def parse_memory_document_id(document_id: str | None) -> tuple[str, str] | None:
    if not isinstance(document_id, str) or not document_id.startswith(_MEMORY_DOCUMENT_PREFIX):
        return None
    remainder = document_id[len(_MEMORY_DOCUMENT_PREFIX) :]
    scope_type, separator, scope_id = remainder.partition(":")
    if not separator:
        return None
    normalized_scope_type = normalize_memory_scope_type(scope_type)
    normalized_scope_id = normalize_scope_id(scope_id)
    if normalized_scope_type == "global" and normalized_scope_id == "runtime":
        return None
    return normalized_scope_type, normalized_scope_id


def build_scope_candidates(selector: MemoryScopeSelector) -> set[tuple[str, str]]:
    candidates: set[tuple[str, str]] = set()
    if selector.scope_type and selector.scope_id:
        candidates.add(
            (
                normalize_memory_scope_type(selector.scope_type),
                normalize_scope_id(selector.scope_id),
            ),
        )
        if not selector.include_related_scopes:
            return candidates
    if not selector.include_related_scopes:
        return candidates
    for scope_type, scope_id in (
        ("task", selector.task_id),
        ("work_context", selector.work_context_id),
        ("agent", selector.agent_id),
        ("industry", selector.industry_instance_id),
        ("global", selector.global_scope_id),
    ):
        normalized_scope_id = str(scope_id or "").strip()
        if normalized_scope_id:
            candidates.add((scope_type, normalized_scope_id))
    return candidates


def selector_matches_scope(
    *,
    selector: MemoryScopeSelector,
    scope_type: str,
    scope_id: str,
) -> bool:
    candidates = build_scope_candidates(selector)
    if not candidates:
        return True
    return (normalize_memory_scope_type(scope_type), normalize_scope_id(scope_id)) in candidates


def source_route_for_entry(entry: MemoryFactIndexRecord) -> str | None:
    metadata = dict(entry.metadata or {})
    route = metadata.get("source_route")
    if isinstance(route, str) and route.strip():
        return route.strip()
    if entry.source_type == "knowledge_chunk":
        return f"/api/runtime-center/knowledge/{entry.source_ref}"
    if entry.source_type == "strategy_memory":
        return "/api/runtime-center/strategy-memory"
    if entry.source_type == "routine_run":
        return f"/api/routines/runs/{entry.source_ref}"
    if entry.source_type == "evidence":
        return f"/api/runtime-center/evidence/{entry.source_ref}"
    if entry.source_type == "learning_patch":
        return f"/api/runtime-center/learning/patches/{entry.source_ref}"
    if entry.source_type == "learning_growth":
        return f"/api/runtime-center/learning/growth/{entry.source_ref}"
    if entry.source_type == "agent_report" and entry.industry_instance_id:
        return f"/api/runtime-center/industry/{entry.industry_instance_id}"
    return None


def slugify(value: object, *, fallback: str = "memory") -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-"
        for character in str(value or "").strip()
    ).strip("-")
    return normalized or fallback


def truncate_text(value: object, *, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def tokenize(text: str | None) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def hashed_vector(text: str | None, *, dimensions: int = 192) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        index = hash(token) % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return float(sum(lhs * rhs for lhs, rhs in zip(left, right)))


def extract_entity_candidates(
    *,
    title: str,
    summary: str,
    content_text: str,
    explicit: Iterable[str] = (),
) -> tuple[list[str], dict[str, str]]:
    entity_labels: dict[str, str] = {}
    ordered_keys: list[str] = []

    def add(value: object, *, label: str | None = None) -> None:
        text = str(value or "").strip()
        if not text:
            return
        key = slugify(text, fallback="entity")
        if key in entity_labels:
            return
        entity_labels[key] = truncate_text(label or text, max_length=80) or key
        ordered_keys.append(key)

    for item in explicit:
        add(item)

    token_counts = Counter(
        token
        for token in tokenize("\n".join(part for part in (title, summary, content_text) if part))
        if token not in _STOP_WORDS
    )
    for token, _count in token_counts.most_common(8):
        add(token, label=token.replace("-", " "))
    return ordered_keys[:12], entity_labels


def extract_opinion_keys(text: str | None, *, entity_keys: list[str]) -> list[str]:
    normalized_text = str(text or "").strip().lower()
    if not normalized_text:
        return []
    collected: list[str] = []
    for cue, stance in _OPINION_CUES:
        if cue not in normalized_text:
            continue
        subject = entity_keys[0] if entity_keys else "general"
        collected.append(f"{subject}:{stance}:{slugify(cue, fallback=stance)}")
    return list(dict.fromkeys(collected))[:8]


def derive_quality_score(
    *,
    content_text: str,
    summary: str,
    evidence_refs: list[str],
    entity_keys: list[str],
) -> float:
    score = 0.25
    if summary:
        score += 0.15
    score += min(len(content_text), 640) / 1280.0
    score += min(len(evidence_refs), 3) * 0.07
    score += min(len(entity_keys), 5) * 0.03
    return max(0.05, min(1.0, score))


def derive_confidence(
    *,
    source_type: str,
    status: str | None = None,
    processed: bool | None = None,
    evidence_refs: list[str] | None = None,
) -> float:
    base = {
        "strategy_memory": 0.9,
        "knowledge_chunk": 0.72,
        "agent_report": 0.8,
        "routine_run": 0.78,
        "report_snapshot": 0.76,
        "evidence": 0.68,
        "learning_patch": 0.78,
        "learning_growth": 0.8,
    }.get(source_type, 0.65)
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"failed", "rejected", "rolled_back"}:
        base -= 0.12
    elif normalized_status in {"completed", "approved", "applied", "processed", "active"}:
        base += 0.05
    if processed:
        base += 0.04
    if evidence_refs:
        base += min(len(evidence_refs), 3) * 0.02
    return max(0.05, min(0.99, base))


def _safe_getattr(target: object | None, name: str) -> Any:
    if target is None:
        return None
    return getattr(target, name, None)


class DerivedMemoryIndexService:
    """Maintain rebuildable fact index entries derived from canonical sources."""

    def __init__(
        self,
        *,
        fact_index_repository,
        entity_view_repository=None,
        opinion_view_repository=None,
        reflection_run_repository=None,
        knowledge_repository=None,
        strategy_repository=None,
        agent_report_repository=None,
        routine_repository=None,
        routine_run_repository=None,
        industry_instance_repository=None,
        evidence_ledger=None,
        reporting_service: object | None = None,
        learning_service: object | None = None,
        sidecar_backends: list[object] | None = None,
    ) -> None:
        self._fact_index_repository = fact_index_repository
        self._entity_view_repository = entity_view_repository
        self._opinion_view_repository = opinion_view_repository
        self._reflection_run_repository = reflection_run_repository
        self._knowledge_repository = knowledge_repository
        self._strategy_repository = strategy_repository
        self._agent_report_repository = agent_report_repository
        self._routine_repository = routine_repository
        self._routine_run_repository = routine_run_repository
        self._industry_instance_repository = industry_instance_repository
        self._evidence_ledger = evidence_ledger
        self._reporting_service = reporting_service
        self._learning_service = learning_service
        self._sidecar_backends = list(sidecar_backends or [])

    def set_reporting_service(self, reporting_service: object | None) -> None:
        self._reporting_service = reporting_service

    def set_learning_service(self, learning_service: object | None) -> None:
        self._learning_service = learning_service

    def set_sidecar_backends(self, sidecar_backends: list[object] | None) -> None:
        self._sidecar_backends = list(sidecar_backends or [])

    def list_fact_entries(self, **kwargs: Any) -> list[MemoryFactIndexRecord]:
        return self._fact_index_repository.list_entries(**kwargs)

    def list_entity_views(self, **kwargs: Any) -> list[MemoryEntityViewRecord]:
        if self._entity_view_repository is None:
            return []
        return self._entity_view_repository.list_views(**kwargs)

    def list_opinion_views(self, **kwargs: Any) -> list[MemoryOpinionViewRecord]:
        if self._opinion_view_repository is None:
            return []
        return self._opinion_view_repository.list_views(**kwargs)

    def list_reflection_runs(self, **kwargs: Any) -> list[MemoryReflectionRunRecord]:
        if self._reflection_run_repository is None:
            return []
        return self._reflection_run_repository.list_runs(**kwargs)

    def clear_compiled_views(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> None:
        if self._entity_view_repository is not None:
            self._entity_view_repository.clear(scope_type=scope_type, scope_id=scope_id)
        if self._opinion_view_repository is not None:
            self._opinion_view_repository.clear(scope_type=scope_type, scope_id=scope_id)

    def delete_source(self, *, source_type: str, source_ref: str) -> int:
        existing_entries = self._fact_index_repository.list_entries(
            source_type=source_type,
            source_ref=source_ref,
            limit=None,
        )
        deleted = self._fact_index_repository.delete_by_source(
            source_type=source_type,
            source_ref=source_ref,
        )
        if deleted > 0:
            self._notify_sidecar_delete_entries(entry_ids=[entry.id for entry in existing_entries])
        return deleted

    def rebuild_all(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        include_reporting: bool = True,
        include_learning: bool = True,
        evidence_limit: int = 200,
    ) -> MemoryRebuildSummary:
        started_at = utc_now()
        normalized_scope_type = (
            normalize_memory_scope_type(scope_type)
            if isinstance(scope_type, str) and scope_type.strip()
            else None
        )
        normalized_scope_id = (
            normalize_scope_id(scope_id)
            if isinstance(scope_id, str) and scope_id.strip()
            else None
        )
        self._fact_index_repository.clear(
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
        )
        source_counts: Counter[str] = Counter()

        if self._strategy_repository is not None:
            for strategy in self._strategy_repository.list_strategies(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
                limit=None,
            ):
                self.upsert_strategy_memory(strategy)
                source_counts["strategy_memory"] += 1

        if self._knowledge_repository is not None:
            for chunk in self._knowledge_repository.list_chunks():
                if not self._matches_chunk_scope(
                    chunk,
                    scope_type=normalized_scope_type,
                    scope_id=normalized_scope_id,
                ):
                    continue
                self.upsert_knowledge_chunk(chunk)
                source_counts["knowledge_chunk"] += 1

        if self._agent_report_repository is not None:
            report_filters: dict[str, Any] = {"limit": None}
            if normalized_scope_type == "work_context" and normalized_scope_id:
                report_filters["work_context_id"] = normalized_scope_id
            if normalized_scope_type == "industry" and normalized_scope_id:
                report_filters["industry_instance_id"] = normalized_scope_id
            for report in self._agent_report_repository.list_reports(**report_filters):
                if not self._matches_record_scope(
                    record_scope_type=(
                        "work_context"
                        if report.work_context_id
                        else "industry"
                    ),
                    record_scope_id=report.work_context_id or report.industry_instance_id,
                    scope_type=normalized_scope_type,
                    scope_id=normalized_scope_id,
                ):
                    continue
                self.upsert_agent_report(report)
                source_counts["agent_report"] += 1

        routine_by_id: dict[str, Any] = {}
        if self._routine_repository is not None:
            routine_by_id = {
                routine.id: routine
                for routine in self._routine_repository.list_routines(limit=None)
            }
        if self._routine_run_repository is not None:
            for run in self._routine_run_repository.list_runs(limit=None):
                routine = routine_by_id.get(run.routine_id)
                if not self._matches_routine_scope(
                    run=run,
                    routine=routine,
                    scope_type=normalized_scope_type,
                    scope_id=normalized_scope_id,
                ):
                    continue
                self.upsert_routine_run(run, routine=routine)
                source_counts["routine_run"] += 1

        if include_reporting:
            for report in self._iter_report_snapshots(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
            ):
                self.upsert_report_snapshot(report)
                source_counts["report_snapshot"] += 1

        if include_learning:
            for patch in self._iter_learning_patches(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
            ):
                self.upsert_learning_patch(patch)
                source_counts["learning_patch"] += 1
            for growth in self._iter_learning_growth(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
            ):
                self.upsert_learning_growth(growth)
                source_counts["learning_growth"] += 1

        if self._evidence_ledger is not None:
            for evidence in self._iter_evidence_records(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
                limit=evidence_limit,
            ):
                self.upsert_evidence(evidence)
                source_counts["evidence"] += 1

        completed_at = utc_now()
        all_entries = self._fact_index_repository.list_entries(limit=None)
        fact_index_count = len(
            [
                entry
                for entry in all_entries
                if self._matches_record_scope(
                    record_scope_type=entry.scope_type,
                    record_scope_id=entry.scope_id,
                    scope_type=normalized_scope_type,
                    scope_id=normalized_scope_id,
                )
            ]
        )
        self._notify_sidecar_replace(entries=all_entries)
        metadata = {
            "include_reporting": include_reporting,
            "include_learning": include_learning,
            "evidence_limit": evidence_limit,
        }
        return MemoryRebuildSummary(
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
            fact_index_count=fact_index_count,
            source_counts=dict(source_counts),
            started_at=started_at,
            completed_at=completed_at,
            metadata=metadata,
        )

    def upsert_knowledge_chunk(self, chunk: KnowledgeChunkRecord) -> MemoryFactIndexRecord:
        parsed_scope = parse_memory_document_id(chunk.document_id)
        scope_type, scope_id = (
            parsed_scope
            if parsed_scope is not None
            else ("global", normalize_scope_id(chunk.document_id))
        )
        title = truncate_text(chunk.title or chunk.document_id, max_length=160) or "Knowledge Chunk"
        summary = truncate_text(chunk.summary or chunk.content, max_length=320)
        content_excerpt = truncate_text(chunk.content, max_length=320)
        content_text = "\n".join(part for part in (chunk.title, chunk.summary, chunk.content) if part).strip()
        explicit_entities = [
            scope_id,
            *(chunk.role_bindings or []),
            *(chunk.tags or []),
            *(chunk.source_ref.split(":") if isinstance(chunk.source_ref, str) else []),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        opinion_keys = extract_opinion_keys(content_text, entity_keys=entity_keys)
        evidence_refs = [chunk.source_ref] if chunk.source_ref else []
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("knowledge_chunk", chunk.id),
            source_type="knowledge_chunk",
            source_ref=chunk.id,
            scope_type=scope_type,
            scope_id=scope_id,
            title=title,
            summary=summary,
            content_excerpt=content_excerpt,
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=opinion_keys,
            tags=list(dict.fromkeys(["knowledge", *(chunk.tags or [])])),
            role_bindings=list(chunk.role_bindings or []),
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="knowledge_chunk",
                status="active" if parsed_scope is not None else None,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=chunk.updated_at or chunk.created_at,
            metadata={
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "source_ref": chunk.source_ref,
                "entity_labels": entity_labels,
                "source_route": f"/api/runtime-center/knowledge/{chunk.id}",
            },
            created_at=chunk.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_strategy_memory(self, strategy: StrategyMemoryRecord) -> MemoryFactIndexRecord:
        content_text = "\n".join(
            part
            for part in (
                strategy.summary,
                strategy.mission,
                strategy.north_star,
                *strategy.priority_order,
                *strategy.delegation_policy,
                *strategy.direct_execution_policy,
                *strategy.execution_constraints,
                *strategy.evidence_requirements,
                *strategy.current_focuses,
            )
            if part
        ).strip()
        explicit_entities = [
            strategy.scope_id,
            strategy.owner_agent_id,
            strategy.industry_instance_id,
            *(strategy.active_goal_ids or []),
            *(strategy.active_goal_titles or []),
            *(strategy.paused_lane_ids or []),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=strategy.title,
            summary=strategy.summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = [strategy.source_ref] if strategy.source_ref else []
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("strategy_memory", strategy.strategy_id),
            source_type="strategy_memory",
            source_ref=strategy.strategy_id,
            scope_type=normalize_memory_scope_type(strategy.scope_type),
            scope_id=normalize_scope_id(strategy.scope_id),
            owner_agent_id=strategy.owner_agent_id,
            owner_scope=strategy.owner_scope,
            industry_instance_id=strategy.industry_instance_id,
            title=truncate_text(strategy.title, max_length=160) or "Strategy Memory",
            summary=truncate_text(strategy.summary or strategy.north_star, max_length=320),
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=["strategy", strategy.status],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="strategy_memory",
                status=strategy.status,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=strategy.summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=strategy.updated_at or strategy.created_at,
            metadata={
                "entity_labels": entity_labels,
                "strategy_id": strategy.strategy_id,
                "source_ref": strategy.source_ref,
                "source_route": "/api/runtime-center/strategy-memory",
                "status": strategy.status,
            },
            created_at=strategy.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_agent_report(self, report: AgentReportRecord) -> MemoryFactIndexRecord:
        content_text = "\n".join(
            part
            for part in (
                report.headline,
                report.summary,
                str(report.metadata or ""),
            )
            if part
        ).strip()
        explicit_entities = [
            report.industry_instance_id,
            report.owner_agent_id,
            report.owner_role_id,
            report.goal_id,
            report.task_id,
            report.lane_id,
            *(report.evidence_ids or []),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=report.headline,
            summary=report.summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = list(report.evidence_ids or [])
        scope_type = "work_context" if report.work_context_id else "industry"
        scope_id = normalize_scope_id(report.work_context_id or report.industry_instance_id)
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("agent_report", report.id),
            source_type="agent_report",
            source_ref=report.id,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=report.owner_agent_id,
            industry_instance_id=report.industry_instance_id,
            title=truncate_text(report.headline, max_length=160) or "Agent Report",
            summary=truncate_text(report.summary or report.headline, max_length=320),
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "agent-report",
                str(report.report_kind or "task-terminal"),
                str(report.status or "recorded"),
                str(report.result or "unknown"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="agent_report",
                status=report.result or report.status,
                processed=report.processed,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=report.summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=report.updated_at or report.created_at,
            metadata={
                "entity_labels": entity_labels,
                "goal_id": report.goal_id,
                "task_id": report.task_id,
                "work_context_id": report.work_context_id,
                "assignment_id": report.assignment_id,
                "lane_id": report.lane_id,
                "result": report.result,
                "status": report.status,
                "source_route": (
                    f"/api/runtime-center/industry/{report.industry_instance_id}"
                    if report.industry_instance_id
                    else None
                ),
            },
            created_at=report.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def _resolve_routine_scope(
        self,
        *,
        run: RoutineRunRecord,
        routine: object | None = None,
    ) -> tuple[str, str, str | None]:
        routine_owner_scope = _safe_getattr(routine, "owner_scope")
        routine_owner_agent_id = _safe_getattr(routine, "owner_agent_id")
        industry_instance_id = (
            str(run.metadata.get("industry_instance_id") or "").strip()
            if isinstance(run.metadata, dict)
            else ""
        ) or None
        if industry_instance_id:
            return "industry", industry_instance_id, industry_instance_id
        if run.owner_agent_id or routine_owner_agent_id:
            return "agent", normalize_scope_id(run.owner_agent_id or routine_owner_agent_id), None
        if run.source_ref:
            prefix = str(run.source_ref).split(":", 1)[0].strip().lower()
            if prefix == "task":
                return "task", normalize_scope_id(run.source_ref.split(":", 1)[-1]), None
        return "global", normalize_scope_id(run.owner_scope or routine_owner_scope), None

    def upsert_routine_run(
        self,
        run: RoutineRunRecord,
        *,
        routine: object | None = None,
    ) -> MemoryFactIndexRecord:
        routine_owner_scope = _safe_getattr(routine, "owner_scope")
        routine_owner_agent_id = _safe_getattr(routine, "owner_agent_id")
        routine_summary = _safe_getattr(routine, "summary")
        routine_name = _safe_getattr(routine, "name")
        scope_type, scope_id, industry_instance_id = self._resolve_routine_scope(
            run=run,
            routine=routine,
        )
        title = truncate_text(
            f"{routine_name or 'Routine'} {run.status}",
            max_length=160,
        ) or "Routine Run"
        summary = truncate_text(
            run.output_summary or routine_summary or title,
            max_length=320,
        )
        content_text = "\n".join(
            part
            for part in (
                routine_name,
                routine_summary,
                run.output_summary,
                run.failure_class,
                run.fallback_mode,
                run.deterministic_result,
                str(run.metadata or ""),
            )
            if part
        ).strip()
        explicit_entities = [
            scope_id,
            run.owner_agent_id,
            run.routine_id,
            run.session_id,
            run.environment_id,
            run.failure_class,
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = list(run.evidence_ids or [])
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("routine_run", run.id),
            source_type="routine_run",
            source_ref=run.id,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=run.owner_agent_id or routine_owner_agent_id,
            owner_scope=run.owner_scope or routine_owner_scope,
            industry_instance_id=industry_instance_id,
            title=title,
            summary=summary,
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "routine-run",
                str(run.status or "unknown"),
                str(run.source_type or "manual"),
                str(_safe_getattr(routine, "engine_kind") or "engine"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="routine_run",
                status=run.status,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=run.completed_at or run.updated_at or run.created_at,
            metadata={
                "entity_labels": entity_labels,
                "routine_id": run.routine_id,
                "failure_class": run.failure_class,
                "fallback_mode": run.fallback_mode,
                "deterministic_result": run.deterministic_result,
                "source_route": f"/api/routines/runs/{run.id}",
            },
            created_at=run.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_report_snapshot(self, report: ReportRecord) -> MemoryFactIndexRecord:
        scope_type = normalize_memory_scope_type(report.scope_type)
        scope_id = normalize_scope_id(report.scope_id)
        content_text = "\n".join(
            [
                report.summary,
                *list(report.highlights or []),
                *[
                    f"{metric.label}: {metric.display_value or metric.value}"
                    for metric in list(report.metrics or [])[:8]
                ],
            ]
        ).strip()
        explicit_entities = [
            scope_id,
            *(report.goal_ids or []),
            *(report.task_ids or []),
            *(report.agent_ids or []),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=report.title,
            summary=report.summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = list(report.evidence_ids or [])
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("report_snapshot", report.id),
            source_type="report_snapshot",
            source_ref=report.id,
            scope_type=scope_type,
            scope_id=scope_id,
            title=truncate_text(report.title, max_length=160) or "Report Snapshot",
            summary=truncate_text(report.summary, max_length=320),
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=["report", report.window, report.scope_type],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="report_snapshot",
                status=report.status,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=report.summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=report.until or report.created_at,
            metadata={
                "entity_labels": entity_labels,
                "window": report.window,
                "routes": dict(report.routes or {}),
                "source_route": (
                    f"/api/runtime-center/reports?window={report.window}"
                    f"&scope_type={report.scope_type}&scope_id={scope_id}"
                ),
            },
            created_at=report.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_evidence(self, evidence: object) -> MemoryFactIndexRecord:
        task_id = _safe_getattr(evidence, "task_id")
        evidence_id = str(_safe_getattr(evidence, "id") or "").strip()
        title = truncate_text(
            _safe_getattr(evidence, "action_summary") or evidence_id or "Evidence",
            max_length=160,
        ) or "Evidence"
        summary = truncate_text(_safe_getattr(evidence, "result_summary") or title, max_length=320)
        metadata = _safe_getattr(evidence, "metadata") or {}
        work_context_id = (
            str(metadata.get("work_context_id") or "").strip()
            if isinstance(metadata, dict)
            else ""
        ) or None
        scope_type = (
            "work_context"
            if work_context_id
            else "task"
            if task_id
            else "global"
        )
        scope_id = normalize_scope_id(work_context_id or task_id)
        content_text = "\n".join(
            part
            for part in (
                _safe_getattr(evidence, "action_summary"),
                _safe_getattr(evidence, "result_summary"),
                _safe_getattr(evidence, "capability_ref"),
                _safe_getattr(evidence, "actor_ref"),
                str(metadata),
            )
            if part
        ).strip()
        explicit_entities = [
            task_id,
            work_context_id,
            _safe_getattr(evidence, "actor_ref"),
            _safe_getattr(evidence, "capability_ref"),
            _safe_getattr(evidence, "environment_ref"),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = [evidence_id] if evidence_id else []
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("evidence", evidence_id),
            source_type="evidence",
            source_ref=evidence_id,
            scope_type=scope_type,
            scope_id=scope_id,
            title=title,
            summary=summary,
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "evidence",
                str(_safe_getattr(evidence, "status") or "recorded"),
                str(_safe_getattr(evidence, "risk_level") or "auto"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="evidence",
                status=_safe_getattr(evidence, "status"),
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=_safe_getattr(evidence, "created_at"),
            metadata={
                "entity_labels": entity_labels,
                "actor_ref": _safe_getattr(evidence, "actor_ref"),
                "capability_ref": _safe_getattr(evidence, "capability_ref"),
                "environment_ref": _safe_getattr(evidence, "environment_ref"),
                "work_context_id": work_context_id,
                "source_route": (
                    f"/api/runtime-center/evidence/{evidence_id}"
                    if evidence_id
                    else None
                ),
            },
            created_at=_safe_getattr(evidence, "created_at") or utc_now(),
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def _scope_from_learning_object(self, item: object) -> tuple[str, str]:
        task_id = _safe_getattr(item, "task_id")
        agent_id = _safe_getattr(item, "agent_id")
        goal_id = _safe_getattr(item, "goal_id")
        if task_id:
            return "task", normalize_scope_id(task_id)
        if agent_id:
            return "agent", normalize_scope_id(agent_id)
        if goal_id:
            return "global", normalize_scope_id(goal_id)
        return "global", "runtime"

    def upsert_learning_patch(self, patch: object) -> MemoryFactIndexRecord:
        source_ref = str(_safe_getattr(patch, "id") or "").strip()
        title = truncate_text(_safe_getattr(patch, "title") or "Learning Patch", max_length=160)
        summary = truncate_text(
            _safe_getattr(patch, "description") or _safe_getattr(patch, "diff_summary") or title,
            max_length=320,
        )
        content_text = "\n".join(
            part
            for part in (
                _safe_getattr(patch, "description"),
                _safe_getattr(patch, "diff_summary"),
                _safe_getattr(patch, "kind"),
                _safe_getattr(patch, "status"),
            )
            if part
        ).strip()
        scope_type, scope_id = self._scope_from_learning_object(patch)
        explicit_entities = [
            scope_id,
            _safe_getattr(patch, "agent_id"),
            _safe_getattr(patch, "goal_id"),
            _safe_getattr(patch, "task_id"),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = list(_safe_getattr(patch, "evidence_refs") or [])
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("learning_patch", source_ref),
            source_type="learning_patch",
            source_ref=source_ref,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=_safe_getattr(patch, "agent_id"),
            title=title or "Learning Patch",
            summary=summary,
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "learning",
                "patch",
                str(_safe_getattr(patch, "kind") or "patch"),
                str(_safe_getattr(patch, "status") or "proposed"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="learning_patch",
                status=_safe_getattr(patch, "status"),
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=_safe_getattr(patch, "applied_at") or _safe_getattr(patch, "created_at"),
            metadata={
                "entity_labels": entity_labels,
                "kind": _safe_getattr(patch, "kind"),
                "status": _safe_getattr(patch, "status"),
                "source_route": f"/api/runtime-center/learning/patches/{source_ref}",
            },
            created_at=_safe_getattr(patch, "created_at") or utc_now(),
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_learning_growth(self, growth: object) -> MemoryFactIndexRecord:
        source_ref = str(_safe_getattr(growth, "id") or "").strip()
        title = truncate_text(_safe_getattr(growth, "description") or "Growth Event", max_length=160)
        summary = truncate_text(
            _safe_getattr(growth, "result") or _safe_getattr(growth, "description") or title,
            max_length=320,
        )
        content_text = "\n".join(
            part
            for part in (
                _safe_getattr(growth, "description"),
                _safe_getattr(growth, "result"),
                _safe_getattr(growth, "change_type"),
            )
            if part
        ).strip()
        scope_type, scope_id = self._scope_from_learning_object(growth)
        explicit_entities = [
            scope_id,
            _safe_getattr(growth, "agent_id"),
            _safe_getattr(growth, "goal_id"),
            _safe_getattr(growth, "task_id"),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = [
            ref
            for ref in [_safe_getattr(growth, "source_evidence_id")]
            if isinstance(ref, str) and ref.strip()
        ]
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("learning_growth", source_ref),
            source_type="learning_growth",
            source_ref=source_ref,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=_safe_getattr(growth, "agent_id"),
            title=title or "Growth Event",
            summary=summary,
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "learning",
                "growth",
                str(_safe_getattr(growth, "change_type") or "growth"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="learning_growth",
                status="recorded",
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=_safe_getattr(growth, "created_at"),
            metadata={
                "entity_labels": entity_labels,
                "change_type": _safe_getattr(growth, "change_type"),
                "source_patch_id": _safe_getattr(growth, "source_patch_id"),
                "source_route": f"/api/runtime-center/learning/growth/{source_ref}",
            },
            created_at=_safe_getattr(growth, "created_at") or utc_now(),
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def _notify_sidecar_replace(self, *, entries: list[MemoryFactIndexRecord]) -> None:
        for backend in self._sidecar_backends:
            replacer = getattr(backend, "replace_entries", None)
            if not callable(replacer):
                continue
            try:
                replacer(entries)
            except Exception:
                continue

    def _notify_sidecar_upsert(self, entry: MemoryFactIndexRecord) -> None:
        for backend in self._sidecar_backends:
            upsert = getattr(backend, "upsert_entry", None)
            if not callable(upsert):
                continue
            try:
                upsert(entry)
            except Exception:
                continue

    def _notify_sidecar_delete_entries(self, *, entry_ids: list[str]) -> None:
        if not entry_ids:
            return
        for backend in self._sidecar_backends:
            delete = getattr(backend, "delete_entries", None)
            if not callable(delete):
                continue
            try:
                delete(entry_ids)
            except Exception:
                continue

    def _iter_report_snapshots(
        self,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> Iterable[ReportRecord]:
        service = self._reporting_service
        getter = getattr(service, "get_report", None)
        if not callable(getter):
            return []
        windows = ("daily", "weekly", "monthly")
        reports: list[ReportRecord] = []
        if scope_type is not None and scope_id is not None:
            for window in windows:
                try:
                    report = getter(window=window, scope_type=scope_type, scope_id=scope_id)
                except Exception:
                    continue
                if report is not None:
                    reports.append(report)
            return reports

        for window in windows:
            try:
                report = getter(window=window, scope_type="global", scope_id=None)
            except Exception:
                continue
            if report is not None:
                reports.append(report)
        if self._industry_instance_repository is not None:
            for instance in self._industry_instance_repository.list_instances(limit=None):
                try:
                    report = getter(
                        window="weekly",
                        scope_type="industry",
                        scope_id=instance.instance_id,
                    )
                except Exception:
                    continue
                if report is not None:
                    reports.append(report)
        return reports

    def _iter_learning_patches(
        self,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> Iterable[object]:
        service = self._learning_service
        lister = getattr(service, "list_patches", None)
        if not callable(lister):
            return []
        try:
            patches = lister(limit=None)
        except Exception:
            return []
        return [
            patch
            for patch in patches
            if self._matches_learning_object_scope(
                patch,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        ]

    def _iter_learning_growth(
        self,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> Iterable[object]:
        service = self._learning_service
        lister = getattr(service, "list_growth", None)
        if not callable(lister):
            return []
        try:
            growth_events = lister(limit=None)
        except Exception:
            return []
        return [
            growth
            for growth in growth_events
            if self._matches_learning_object_scope(
                growth,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        ]

    def _iter_evidence_records(
        self,
        *,
        scope_type: str | None,
        scope_id: str | None,
        limit: int,
    ) -> Iterable[object]:
        if self._evidence_ledger is None:
            return []
        try:
            if scope_type == "task" and scope_id:
                return list(self._evidence_ledger.query_by_task(scope_id))
            records = self._evidence_ledger.list_records(limit=limit)
        except Exception:
            return []
        if scope_type is None or scope_id is None:
            return records
        if scope_type == "global":
            return records
        if scope_type == "agent":
            return [
                record
                for record in records
                if scope_id in str(_safe_getattr(record, "actor_ref") or "")
            ]
        return []

    def _matches_learning_object_scope(
        self,
        item: object,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> bool:
        if scope_type is None or scope_id is None:
            return True
        derived_scope_type, derived_scope_id = self._scope_from_learning_object(item)
        return self._matches_record_scope(
            record_scope_type=derived_scope_type,
            record_scope_id=derived_scope_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def _matches_chunk_scope(
        self,
        chunk: KnowledgeChunkRecord,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> bool:
        if scope_type is None or scope_id is None:
            return True
        parsed_scope = parse_memory_document_id(chunk.document_id)
        if parsed_scope is None:
            return scope_type == "global"
        return self._matches_record_scope(
            record_scope_type=parsed_scope[0],
            record_scope_id=parsed_scope[1],
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def _matches_routine_scope(
        self,
        *,
        run: RoutineRunRecord,
        routine: object | None,
        scope_type: str | None,
        scope_id: str | None,
    ) -> bool:
        if scope_type is None or scope_id is None:
            return True
        derived_scope_type, derived_scope_id, _industry_instance_id = self._resolve_routine_scope(
            run=run,
            routine=routine,
        )
        return self._matches_record_scope(
            record_scope_type=derived_scope_type,
            record_scope_id=derived_scope_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def _matches_record_scope(
        self,
        *,
        record_scope_type: str | None,
        record_scope_id: str | None,
        scope_type: str | None,
        scope_id: str | None,
    ) -> bool:
        if scope_type is None or scope_id is None:
            return True
        return (
            normalize_memory_scope_type(record_scope_type) == normalize_memory_scope_type(scope_type)
            and normalize_scope_id(record_scope_id) == normalize_scope_id(scope_id)
        )

    def _stable_entry_id(self, source_type: str, source_ref: object) -> str:
        return f"memory-index:{source_type}:{slugify(source_ref, fallback='entry')}"
