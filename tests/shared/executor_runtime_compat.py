# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from copaw.state import ExecutorRuntimeInstanceRecord, ExecutorRuntimeService
from copaw.industry.identity import EXECUTION_CORE_AGENT_ID, EXECUTION_CORE_ROLE_ID


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _merge(*payloads: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        if isinstance(payload, dict):
            merged.update(payload)
    return merged


def _legacy_status_to_executor_status(status: str | None) -> str:
    normalized = _text(status) or "ready"
    if normalized in {"failed", "error"}:
        return "failed"
    if normalized in {"retired", "stopped", "completed"}:
        return "stopped"
    if normalized in {"starting", "restarting", "degraded", "orphaned"}:
        return normalized
    return "ready"


def _executor_status_to_legacy_status(
    runtime_status: str | None,
    metadata: dict[str, Any] | None,
) -> str:
    merged = dict(metadata or {})
    explicit = _text(merged.get("legacy_runtime_status"))
    if explicit is not None:
        return explicit
    assignment_status = _text(merged.get("current_assignment_status"))
    seat_runtime_status = _text(merged.get("seat_runtime_status"))
    current_assignment_id = _text(merged.get("current_assignment_id"))
    current_task_id = _text(merged.get("current_task_id"))
    queue_depth = int(merged.get("queue_depth") or 0)
    normalized_runtime_status = _text(runtime_status) or "ready"

    if assignment_status in {"planned", "created", "pending", "risk-check", "queued"}:
        return "queued"
    if assignment_status == "claimed":
        return "claimed"
    if assignment_status in {"running", "active", "executing", "waiting-report"}:
        return "executing"
    if assignment_status in {"blocked", "waiting-confirm", "needs-confirm"}:
        return "blocked"
    if assignment_status == "waiting":
        return "waiting"
    if normalized_runtime_status in {"failed", "degraded", "orphaned"}:
        return "blocked"
    if normalized_runtime_status in {"starting", "restarting", "hydrating"}:
        return "claimed"
    if normalized_runtime_status == "waiting-input":
        return "waiting"
    if normalized_runtime_status in {"ready", "completed", "stopped"}:
        if current_assignment_id is None and current_task_id is None and queue_depth <= 0:
            return "idle"
        if seat_runtime_status in {
            "assigned",
            "queued",
            "claimed",
            "executing",
            "waiting",
            "blocked",
        }:
            return seat_runtime_status
        if current_assignment_id or current_task_id:
            return "queued"
        return "idle"
    return normalized_runtime_status


def _infer_actor_scope(
    actor_key: str | None,
    *,
    fallback_instance_id: str | None = None,
    fallback_role_id: str | None = None,
) -> tuple[str | None, str | None]:
    normalized_actor_key = _text(actor_key)
    if normalized_actor_key is None or ":" not in normalized_actor_key:
        return fallback_instance_id, fallback_role_id
    instance_id, _, role_id = normalized_actor_key.rpartition(":")
    if not instance_id:
        return fallback_instance_id, fallback_role_id
    return fallback_instance_id or instance_id, fallback_role_id or role_id or None


def _industry_executor_id(instance_id: str | None, agent_id: str) -> str:
    normalized_instance_id = _text(instance_id)
    if normalized_instance_id is None:
        return "legacy-test-compat"
    return f"industry-seat:{normalized_instance_id}:{agent_id}"


def _industry_thread_id(
    instance_id: str | None,
    agent_id: str,
    role_id: str | None,
) -> str | None:
    normalized_instance_id = _text(instance_id)
    normalized_role_id = _text(role_id)
    if normalized_instance_id is None:
        return None
    if agent_id == EXECUTION_CORE_AGENT_ID or normalized_role_id == EXECUTION_CORE_ROLE_ID:
        return f"industry-chat:{normalized_instance_id}:{EXECUTION_CORE_ROLE_ID}"
    return f"agent-chat:{agent_id}"


class AgentRuntimeRecord(BaseModel):
    agent_id: str
    actor_key: str | None = None
    actor_fingerprint: str | None = None
    actor_class: str | None = None
    desired_state: str | None = None
    runtime_status: str = "idle"
    employment_mode: str | None = None
    activation_mode: str | None = None
    persistent: bool | None = None
    industry_instance_id: str | None = None
    industry_role_id: str | None = None
    display_name: str | None = None
    role_name: str | None = None
    current_task_id: str | None = None
    current_mailbox_id: str | None = None
    queue_depth: int = 0
    last_error_summary: str | None = None
    last_checkpoint_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=_utc_now)


class AgentThreadBindingRecord(BaseModel):
    thread_id: str
    agent_id: str | None = None
    session_id: str | None = None
    work_context_id: str | None = None
    industry_instance_id: str | None = None
    industry_role_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SqliteAgentRuntimeRepository:
    def __init__(self, state_store) -> None:
        self._service = ExecutorRuntimeService(state_store=state_store)

    @property
    def service(self) -> ExecutorRuntimeService:
        return self._service

    def _project(self, runtime: ExecutorRuntimeInstanceRecord | None) -> AgentRuntimeRecord | None:
        if runtime is None:
            return None
        metadata = dict(runtime.metadata or {})
        continuity = dict(metadata.get("continuity") or {})
        return AgentRuntimeRecord(
            agent_id=_text(metadata.get("owner_agent_id")) or _text(runtime.role_id) or runtime.runtime_id,
            actor_key=_text(metadata.get("actor_key")) or runtime.runtime_id,
            actor_fingerprint=_text(metadata.get("actor_fingerprint")) or _text(runtime.executor_id),
            actor_class=_text(metadata.get("actor_class")) or "executor-runtime",
            desired_state=_text(metadata.get("desired_state")) or "active",
            runtime_status=_executor_status_to_legacy_status(
                runtime.runtime_status,
                metadata,
            ),
            employment_mode=_text(metadata.get("employment_mode")),
            activation_mode=_text(metadata.get("activation_mode")),
            persistent=metadata.get("persistent"),
            industry_instance_id=_text(metadata.get("industry_instance_id")),
            industry_role_id=_text(metadata.get("industry_role_id")) or _text(runtime.role_id),
            display_name=_text(metadata.get("display_name")),
            role_name=_text(metadata.get("role_name")),
            current_task_id=_text(metadata.get("current_task_id")) or _text(runtime.assignment_id),
            current_mailbox_id=_text(metadata.get("current_mailbox_id")),
            queue_depth=int(metadata.get("queue_depth") or 0),
            last_error_summary=_text(metadata.get("last_error_summary"))
            or _text(metadata.get("last_query_error")),
            last_checkpoint_id=_text(metadata.get("last_checkpoint_id"))
            or _text(metadata.get("last_query_checkpoint_id")),
            metadata=_merge(metadata, {"continuity": continuity} if continuity else None),
            updated_at=runtime.updated_at,
        )

    def _find_runtime(self, agent_id: str) -> ExecutorRuntimeInstanceRecord | None:
        normalized_agent_id = _text(agent_id)
        if normalized_agent_id is None:
            return None
        candidates: list[ExecutorRuntimeInstanceRecord] = []
        for runtime in self._service.list_runtimes():
            metadata = dict(runtime.metadata or {})
            owner_agent_id = _text(metadata.get("owner_agent_id")) or _text(runtime.role_id)
            if owner_agent_id == normalized_agent_id:
                candidates.append(runtime)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item.updated_at, reverse=True)
        return candidates[0]

    def upsert_runtime(self, record: AgentRuntimeRecord) -> AgentRuntimeRecord:
        existing = self._find_runtime(record.agent_id)
        inferred_instance_id, inferred_role_id = _infer_actor_scope(
            record.actor_key,
            fallback_instance_id=_text(record.industry_instance_id),
            fallback_role_id=_text(record.industry_role_id),
        )
        continuity = _merge(
            (existing.metadata or {}).get("continuity") if existing is not None else None,
            (record.metadata or {}).get("continuity"),
        )
        thread_id = (
            _text((record.metadata or {}).get("control_thread_id"))
            or _text((record.metadata or {}).get("session_id"))
            or _text(continuity.get("control_thread_id"))
            or _text(continuity.get("session_id"))
            or _industry_thread_id(inferred_instance_id, record.agent_id, inferred_role_id)
            or (existing.thread_id if existing is not None else None)
        )
        continuity = _merge(
            continuity,
            {
                "control_thread_id": thread_id,
                "session_id": thread_id,
                "work_context_id": _text((record.metadata or {}).get("work_context_id"))
                or _text(continuity.get("work_context_id")),
            },
        )
        metadata = _merge(
            existing.metadata if existing is not None else None,
            record.metadata,
            {
                "owner_agent_id": record.agent_id,
                "actor_key": _text(record.actor_key),
                "actor_fingerprint": _text(record.actor_fingerprint),
                "actor_class": _text(record.actor_class),
                "desired_state": _text(record.desired_state),
                "employment_mode": _text(record.employment_mode),
                "activation_mode": _text(record.activation_mode),
                "persistent": record.persistent,
                "industry_instance_id": inferred_instance_id,
                "industry_role_id": inferred_role_id,
                "display_name": _text(record.display_name),
                "role_name": _text(record.role_name),
                "current_task_id": _text(record.current_task_id),
                "current_mailbox_id": _text(record.current_mailbox_id),
                "queue_depth": int(record.queue_depth or 0),
                "last_error_summary": _text(record.last_error_summary),
                "last_checkpoint_id": _text(record.last_checkpoint_id),
                "legacy_runtime_status": _text(record.runtime_status) or "idle",
                "continuity": continuity,
            },
        )
        metadata["executor_runtime_managed"] = True
        runtime = self._service.create_or_reuse_runtime(
            executor_id=_text(metadata.get("executor_id"))
            or _industry_executor_id(inferred_instance_id, record.agent_id),
            protocol_kind="unknown",
            scope_kind="role",
            assignment_id=_text(record.current_task_id),
            role_id=inferred_role_id or record.agent_id,
            thread_id=thread_id,
            metadata=metadata,
            continuity_metadata=continuity,
        )
        metadata = _merge(runtime.metadata, metadata)
        metadata["executor_runtime_managed"] = True
        runtime = self._service.upsert_runtime(
            runtime.model_copy(
                update={
                    "runtime_status": _legacy_status_to_executor_status(record.runtime_status),
                    "thread_id": thread_id or runtime.thread_id,
                    "metadata": metadata,
                    "updated_at": record.updated_at,
                }
            )
        )
        return self._project(runtime) or record

    def get_runtime(self, agent_id: str) -> AgentRuntimeRecord | None:
        return self._project(self._find_runtime(agent_id))

    def list_runtimes(self, limit: int | None = None):
        projected = [
            item
            for item in (
                self._project(runtime)
                for runtime in self._service.list_runtimes()
            )
            if item is not None
        ]
        if limit is None:
            return projected
        return projected[: max(0, limit)]

    def delete_runtime(self, agent_id: str) -> bool:
        runtime = self._find_runtime(agent_id)
        if runtime is None:
            return False
        return bool(self._service.delete_runtime(runtime.runtime_id))


class SqliteAgentThreadBindingRepository:
    def __init__(self, state_store) -> None:
        self._service = ExecutorRuntimeService(state_store=state_store)

    @property
    def service(self) -> ExecutorRuntimeService:
        return self._service

    def _project(self, binding: object) -> AgentThreadBindingRecord:
        metadata = dict(getattr(binding, "metadata", None) or {})
        continuity = _merge(metadata.get("continuity"))
        return AgentThreadBindingRecord(
            thread_id=str(getattr(binding, "thread_id")),
            agent_id=_text(metadata.get("owner_agent_id")) or _text(getattr(binding, "role_id", None)),
            session_id=_text(continuity.get("session_id")) or _text(getattr(binding, "thread_id", None)),
            work_context_id=_text(continuity.get("work_context_id")) or _text(metadata.get("work_context_id")),
            industry_instance_id=_text(metadata.get("industry_instance_id")),
            industry_role_id=_text(metadata.get("industry_role_id")) or _text(getattr(binding, "role_id", None)),
            metadata=metadata,
        )

    def get_binding(self, thread_id: str) -> AgentThreadBindingRecord | None:
        for binding in self._service.list_thread_bindings(thread_id=thread_id):
            return self._project(binding)
        return None

    def list_bindings(
        self,
        *,
        industry_instance_id: str | None = None,
        agent_id: str | None = None,
        active_only: bool = True,
        limit: int | None = None,
    ):
        items: list[AgentThreadBindingRecord] = []
        for binding in self._service.list_thread_bindings(limit=limit):
            projected = self._project(binding)
            if industry_instance_id is not None and projected.industry_instance_id != industry_instance_id:
                continue
            if agent_id is not None and projected.agent_id != agent_id:
                continue
            if active_only and _text((projected.metadata or {}).get("binding_status")) == "retired":
                continue
            items.append(projected)
        return items
