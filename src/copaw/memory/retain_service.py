# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any

from .derived_index_service import normalize_scope_id, parse_memory_document_id


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _chunk_token(value: object | None, *, fallback: str) -> str:
    normalized = _NON_ALNUM_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return normalized or fallback


class MemoryRetainService:
    """Retain high-value execution outcomes into canonical facts plus derived index."""

    def __init__(
        self,
        *,
        knowledge_service: object | None,
        derived_index_service,
        reflection_service: object | None = None,
    ) -> None:
        self._knowledge_service = knowledge_service
        self._derived_index_service = derived_index_service
        self._reflection_service = reflection_service

    def set_reflection_service(self, reflection_service: object | None) -> None:
        self._reflection_service = reflection_service

    def retain_agent_report(self, report: object) -> object | None:
        industry_instance_id = str(getattr(report, "industry_instance_id", "") or "").strip()
        work_context_id = str(getattr(report, "work_context_id", "") or "").strip()
        scope_type = "work_context" if work_context_id else "industry"
        scope_id = work_context_id or industry_instance_id
        if scope_id:
            self._upsert_memory_chunk(
                chunk_id=f"retain:agent-report:{getattr(report, 'id', 'unknown')}",
                document_id=f"memory:{scope_type}:{scope_id}",
                title=str(getattr(report, "headline", "") or "Agent report"),
                content="\n".join(
                    part
                    for part in (
                        f"Result: {getattr(report, 'result', '')}" if getattr(report, "result", None) else "",
                        f"Risk: {getattr(report, 'risk_level', '')}" if getattr(report, "risk_level", None) else "",
                        str(getattr(report, "summary", "") or ""),
                    )
                    if part
                ).strip(),
                source_ref=f"agent-report:{getattr(report, 'id', '')}",
                role_bindings=[
                    str(getattr(report, "owner_role_id", "") or "").strip(),
                ],
                tags=[
                    "retain",
                    "agent-report",
                    str(getattr(report, "status", "") or "recorded"),
                    str(getattr(report, "result", "") or "unknown"),
                ],
            )
        self._derived_index_service.upsert_agent_report(report)
        self._reflect_scope(
            scope_type=scope_type,
            scope_id=scope_id or "runtime",
            owner_agent_id=str(getattr(report, "owner_agent_id", "") or "").strip() or None,
            industry_instance_id=industry_instance_id or None,
            trigger_kind="retain-agent-report",
        )
        return report

    def retain_routine_run(self, run: object, *, routine: object | None = None) -> object | None:
        scope_type, scope_id, industry_instance_id = self._derived_index_service._resolve_routine_scope(  # noqa: SLF001
            run=run,
            routine=routine,
        )
        self._upsert_memory_chunk(
            chunk_id=f"retain:routine-run:{getattr(run, 'id', 'unknown')}",
            document_id=f"memory:{scope_type}:{scope_id}",
            title=str(getattr(routine, "name", "") or "Routine run"),
            content="\n".join(
                part
                for part in (
                    f"Status: {getattr(run, 'status', '')}" if getattr(run, "status", None) else "",
                    f"Failure: {getattr(run, 'failure_class', '')}" if getattr(run, "failure_class", None) else "",
                    f"Fallback: {getattr(run, 'fallback_mode', '')}" if getattr(run, "fallback_mode", None) else "",
                    str(getattr(run, "output_summary", "") or ""),
                )
                if part
            ).strip(),
            source_ref=f"routine-run:{getattr(run, 'id', '')}",
            role_bindings=[],
            tags=[
                "retain",
                "routine-run",
                str(getattr(run, "status", "") or "unknown"),
            ],
        )
        self._derived_index_service.upsert_routine_run(run, routine=routine)
        self._reflect_scope(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=str(getattr(run, "owner_agent_id", "") or "").strip() or None,
            industry_instance_id=industry_instance_id,
            trigger_kind="retain-routine-run",
        )
        return run

    def retain_chat_writeback(
        self,
        *,
        industry_instance_id: str,
        work_context_id: str | None = None,
        title: str,
        content: str,
        source_ref: str,
        role_bindings: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> object | None:
        normalized_industry_instance_id = str(industry_instance_id or "").strip()
        normalized_work_context_id = str(work_context_id or "").strip() or None
        scope_type = "work_context" if normalized_work_context_id else "industry"
        scope_id = normalized_work_context_id or normalized_industry_instance_id
        if not scope_id:
            return None
        normalized_source_ref = str(source_ref or "").strip()
        chunk_id = ":".join(
            [
                "retain",
                "chat-writeback",
                _chunk_token(scope_type, fallback="scope"),
                _chunk_token(scope_id, fallback="runtime"),
                _chunk_token(normalized_source_ref, fallback="source"),
            ],
        )
        self._upsert_memory_chunk(
            chunk_id=chunk_id,
            document_id=f"memory:{scope_type}:{scope_id}",
            title=title,
            content=content,
            source_ref=normalized_source_ref or None,
            role_bindings=role_bindings,
            tags=[
                "retain",
                "chat-writeback",
                f"scope:{scope_type}",
                f"scope-id:{normalize_scope_id(scope_id)}",
                *(tags or []),
            ],
        )
        self._reflect_scope(
            scope_type=scope_type,
            scope_id=scope_id,
            industry_instance_id=normalized_industry_instance_id or None,
            trigger_kind="retain-chat-writeback",
        )
        return {
            "industry_instance_id": normalized_industry_instance_id,
            "work_context_id": normalized_work_context_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "source_ref": normalized_source_ref,
        }

    def retain_report_snapshot(self, report: object) -> object | None:
        self._derived_index_service.upsert_report_snapshot(report)
        return report

    def retain_evidence(self, evidence: object) -> object | None:
        self._derived_index_service.upsert_evidence(evidence)
        return evidence

    def _upsert_memory_chunk(
        self,
        *,
        chunk_id: str,
        document_id: str,
        title: str,
        content: str,
        source_ref: str | None,
        role_bindings: list[str] | None,
        tags: list[str] | None,
    ) -> object | None:
        service = self._knowledge_service
        upsert_chunk = getattr(service, "upsert_chunk", None)
        get_chunk = getattr(service, "get_chunk", None)
        list_chunks = getattr(service, "list_chunks", None)
        if not callable(upsert_chunk):
            return None
        existing = get_chunk(chunk_id) if callable(get_chunk) else None
        if existing is not None:
            chunk_index = int(getattr(existing, "chunk_index", 0) or 0)
        elif callable(list_chunks):
            related_chunks = list_chunks(document_id=document_id, limit=None)
            chunk_index = max((int(getattr(item, "chunk_index", 0) or 0) for item in related_chunks), default=-1) + 1
        else:
            chunk_index = 0
        return upsert_chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            title=title,
            content=content,
            source_ref=source_ref,
            chunk_index=chunk_index,
            role_bindings=[item for item in (role_bindings or []) if item],
            tags=[item for item in (tags or []) if item],
        )

    def _reflect_scope(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        trigger_kind: str,
    ) -> None:
        service = self._reflection_service
        reflect = getattr(service, "reflect", None)
        if not callable(reflect):
            return
        if scope_type == "global" and parse_memory_document_id(f"memory:{scope_type}:{scope_id}") is None:
            scope_id = "runtime"
        try:
            reflect(
                scope_type=scope_type,
                scope_id=scope_id,
                owner_agent_id=owner_agent_id,
                industry_instance_id=industry_instance_id,
                trigger_kind=trigger_kind,
                create_learning_proposals=False,
            )
        except Exception:
            return
