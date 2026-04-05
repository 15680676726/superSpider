# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models_external_runtime import ExternalCapabilityRuntimeInstanceRecord
from .repositories.base import BaseExternalCapabilityRuntimeRepository

_ACTIVE_SERVICE_STATUSES = {"starting", "restarting", "ready", "degraded"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _merge_metadata(
    base: dict[str, Any] | None,
    patch: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _merge_metadata(existing, value)
            continue
        merged[key] = value
    return merged


def _require_scope_ref(
    *,
    scope_kind: str,
    session_mount_id: str | None,
    work_context_id: str | None,
    environment_ref: str | None,
) -> dict[str, str | None]:
    normalized = {
        "session_mount_id": _text(session_mount_id),
        "work_context_id": _text(work_context_id),
        "environment_ref": _text(environment_ref),
    }
    if scope_kind == "session" and normalized["session_mount_id"] is None:
        raise ValueError("session scope requires session_mount_id")
    if scope_kind == "work_context" and normalized["work_context_id"] is None:
        raise ValueError("work_context scope requires work_context_id")
    if scope_kind == "seat" and normalized["environment_ref"] is None:
        raise ValueError("seat scope requires environment_ref")
    return normalized


class ExternalCapabilityRuntimeService:
    def __init__(self, *, repository: BaseExternalCapabilityRuntimeRepository) -> None:
        self._repository = repository

    def get_runtime(self, runtime_id: str) -> ExternalCapabilityRuntimeInstanceRecord | None:
        return self._repository.get_runtime(runtime_id)

    def list_runtimes(self, **kwargs: Any) -> list[ExternalCapabilityRuntimeInstanceRecord]:
        return self._repository.list_runtimes(**kwargs)

    def update_runtime(
        self,
        runtime_id: str,
        *,
        metadata: dict[str, Any] | None = None,
        **updates: Any,
    ) -> ExternalCapabilityRuntimeInstanceRecord:
        record = self._repository.get_runtime(runtime_id)
        if record is None:
            raise KeyError(f"Runtime '{runtime_id}' not found")
        payload = dict(updates)
        if metadata is not None:
            payload["metadata"] = _merge_metadata(record.metadata, metadata)
        payload["updated_at"] = _utc_now()
        updated = record.model_copy(update=payload)
        return self._repository.upsert_runtime(updated)

    def resolve_active_service_instance(
        self,
        *,
        capability_id: str,
        scope_kind: str,
        session_mount_id: str | None = None,
        work_context_id: str | None = None,
        environment_ref: str | None = None,
    ) -> ExternalCapabilityRuntimeInstanceRecord | None:
        normalized_scope = _require_scope_ref(
            scope_kind=scope_kind,
            session_mount_id=session_mount_id,
            work_context_id=work_context_id,
            environment_ref=environment_ref,
        )
        items = self._repository.list_runtimes(
            capability_id=capability_id,
            runtime_kind="service",
            scope_kind=scope_kind,
            session_mount_id=normalized_scope["session_mount_id"],
            work_context_id=normalized_scope["work_context_id"],
            environment_ref=normalized_scope["environment_ref"],
        )
        for item in items:
            if item.status in _ACTIVE_SERVICE_STATUSES:
                return item
        return None

    def create_or_reuse_service_runtime(
        self,
        *,
        capability_id: str,
        scope_kind: str,
        session_mount_id: str | None = None,
        work_context_id: str | None = None,
        environment_ref: str | None = None,
        owner_agent_id: str | None = None,
        command: str = "",
        cwd: str | None = None,
        continuity_policy: str = "scoped",
        retention_policy: str = "until-stop",
        latest_start_evidence_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExternalCapabilityRuntimeInstanceRecord:
        normalized_scope = _require_scope_ref(
            scope_kind=scope_kind,
            session_mount_id=session_mount_id,
            work_context_id=work_context_id,
            environment_ref=environment_ref,
        )
        now = _utc_now()
        existing = self.resolve_active_service_instance(
            capability_id=capability_id,
            scope_kind=scope_kind,
            session_mount_id=normalized_scope["session_mount_id"],
            work_context_id=normalized_scope["work_context_id"],
            environment_ref=normalized_scope["environment_ref"],
        )
        if existing is not None:
            updated = existing.model_copy(
                update={
                    "owner_agent_id": _text(owner_agent_id) or existing.owner_agent_id,
                    "command": str(command or existing.command or ""),
                    "cwd": _text(cwd) or existing.cwd,
                    "continuity_policy": continuity_policy or existing.continuity_policy,
                    "retention_policy": retention_policy or existing.retention_policy,
                    "latest_start_evidence_id": (
                        _text(latest_start_evidence_id) or existing.latest_start_evidence_id
                    ),
                    "metadata": _merge_metadata(existing.metadata, metadata),
                    "updated_at": now,
                },
            )
            return self._repository.upsert_runtime(updated)
        record = ExternalCapabilityRuntimeInstanceRecord(
            capability_id=capability_id,
            runtime_kind="service",
            scope_kind=scope_kind,
            session_mount_id=normalized_scope["session_mount_id"],
            work_context_id=normalized_scope["work_context_id"],
            environment_ref=normalized_scope["environment_ref"],
            owner_agent_id=_text(owner_agent_id),
            status="starting",
            command=str(command or ""),
            cwd=_text(cwd),
            continuity_policy=continuity_policy or "scoped",
            retention_policy=retention_policy or "until-stop",
            last_started_at=now,
            latest_start_evidence_id=_text(latest_start_evidence_id),
            metadata=_merge_metadata(None, metadata),
        )
        return self._repository.upsert_runtime(record)

    def record_cli_run(
        self,
        *,
        capability_id: str,
        scope_kind: str,
        session_mount_id: str | None = None,
        work_context_id: str | None = None,
        environment_ref: str | None = None,
        owner_agent_id: str | None = None,
        command: str,
        cwd: str | None = None,
        success: bool,
        exit_code: int | None = None,
        last_error: str | None = None,
        latest_start_evidence_id: str | None = None,
        latest_stop_evidence_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExternalCapabilityRuntimeInstanceRecord:
        normalized_scope = _require_scope_ref(
            scope_kind=scope_kind,
            session_mount_id=session_mount_id,
            work_context_id=work_context_id,
            environment_ref=environment_ref,
        )
        now = _utc_now()
        record = ExternalCapabilityRuntimeInstanceRecord(
            capability_id=capability_id,
            runtime_kind="cli",
            scope_kind=scope_kind,
            session_mount_id=normalized_scope["session_mount_id"],
            work_context_id=normalized_scope["work_context_id"],
            environment_ref=normalized_scope["environment_ref"],
            owner_agent_id=_text(owner_agent_id),
            status="completed" if success else "failed",
            command=str(command or ""),
            cwd=_text(cwd),
            continuity_policy="ephemeral",
            retention_policy="history",
            last_started_at=now,
            last_stopped_at=now,
            last_exit_code=exit_code,
            last_error=_text(last_error),
            latest_start_evidence_id=_text(latest_start_evidence_id),
            latest_stop_evidence_id=_text(latest_stop_evidence_id),
            metadata=_merge_metadata(None, metadata),
        )
        return self._repository.upsert_runtime(record)

    def mark_runtime_ready(
        self,
        runtime_id: str,
        *,
        process_id: int | None = None,
        port: int | None = None,
        health_url: str | None = None,
        latest_healthcheck_evidence_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExternalCapabilityRuntimeInstanceRecord:
        now = _utc_now()
        return self.update_runtime(
            runtime_id,
            status="ready",
            process_id=process_id,
            port=port,
            health_url=_text(health_url),
            last_ready_at=now,
            latest_healthcheck_evidence_id=_text(latest_healthcheck_evidence_id),
            metadata=metadata,
        )

    def mark_runtime_stopped(
        self,
        runtime_id: str,
        *,
        status: str = "stopped",
        exit_code: int | None = None,
        last_error: str | None = None,
        latest_stop_evidence_id: str | None = None,
        latest_recovery_evidence_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExternalCapabilityRuntimeInstanceRecord:
        normalized_status = (
            status if status in {"completed", "stopped", "failed", "orphaned"} else "stopped"
        )
        now = _utc_now()
        return self.update_runtime(
            runtime_id,
            status=normalized_status,
            last_exit_code=exit_code,
            last_error=_text(last_error),
            last_stopped_at=now,
            latest_stop_evidence_id=_text(latest_stop_evidence_id),
            latest_recovery_evidence_id=_text(latest_recovery_evidence_id),
            metadata=metadata,
        )
