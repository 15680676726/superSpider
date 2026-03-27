# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .models_work_context import WorkContextRecord
from .repositories.base import BaseWorkContextRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class WorkContextService:
    """Resolve and persist formal continuous work boundaries."""

    def __init__(self, *, repository: BaseWorkContextRepository) -> None:
        self._repository = repository

    def get_context(self, context_id: str) -> WorkContextRecord | None:
        return self._repository.get_context(context_id)

    def get_by_context_key(self, context_key: str) -> WorkContextRecord | None:
        return self._repository.get_by_context_key(context_key)

    def list_contexts(self, **kwargs: Any) -> list[WorkContextRecord]:
        return self._repository.list_contexts(**kwargs)

    def ensure_context(
        self,
        *,
        context_id: str | None = None,
        context_key: str | None = None,
        title: str,
        summary: str = "",
        context_type: str = "generic",
        status: str = "active",
        owner_scope: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        primary_thread_id: str | None = None,
        source_kind: str | None = None,
        source_ref: str | None = None,
        parent_work_context_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkContextRecord:
        existing = None
        normalized_context_id = _text(context_id)
        normalized_context_key = _text(context_key)
        if normalized_context_id is not None:
            existing = self._repository.get_context(normalized_context_id)
        if existing is None and normalized_context_key is not None:
            existing = self._repository.get_by_context_key(normalized_context_key)
        now = _utc_now()
        if existing is None:
            record = WorkContextRecord(
                id=normalized_context_id or str(uuid4()),
                title=title.strip(),
                summary=summary.strip(),
                context_type=_text(context_type) or "generic",
                status=status if status in {"active", "paused", "completed", "archived"} else "active",
                context_key=normalized_context_key,
                owner_scope=_text(owner_scope),
                owner_agent_id=_text(owner_agent_id),
                industry_instance_id=_text(industry_instance_id),
                primary_thread_id=_text(primary_thread_id),
                source_kind=_text(source_kind),
                source_ref=_text(source_ref),
                parent_work_context_id=_text(parent_work_context_id),
                metadata=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
            return self._repository.upsert_context(record)
        merged_metadata = {
            **dict(existing.metadata or {}),
            **dict(metadata or {}),
        }
        updated = existing.model_copy(
            update={
                "title": title.strip() or existing.title,
                "summary": summary.strip() or existing.summary,
                "context_type": _text(context_type) or existing.context_type,
                "status": (
                    status
                    if status in {"active", "paused", "completed", "archived"}
                    else existing.status
                ),
                "context_key": normalized_context_key or existing.context_key,
                "owner_scope": _text(owner_scope) or existing.owner_scope,
                "owner_agent_id": _text(owner_agent_id) or existing.owner_agent_id,
                "industry_instance_id": _text(industry_instance_id) or existing.industry_instance_id,
                "primary_thread_id": _text(primary_thread_id) or existing.primary_thread_id,
                "source_kind": _text(source_kind) or existing.source_kind,
                "source_ref": _text(source_ref) or existing.source_ref,
                "parent_work_context_id": _text(parent_work_context_id) or existing.parent_work_context_id,
                "metadata": merged_metadata,
                "updated_at": now,
            },
        )
        return self._repository.upsert_context(updated)
