# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .external_runtime_service import ExternalCapabilityRuntimeService
from .models_executor_runtime import (
    ExecutorProviderRecord,
    ExecutorRuntimeInstanceRecord,
    ModelInvocationPolicyRecord,
    RoleExecutorBindingRecord,
)
from .models_external_runtime import ExternalCapabilityRuntimeInstanceRecord

_EXECUTOR_RUNTIME_METADATA_KEY = "executor_runtime"
_ACTIVE_RUNTIME_STATUSES = {"starting", "restarting", "ready", "degraded"}


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


def _executor_capability_id(executor_id: str) -> str:
    normalized = str(executor_id).strip()
    if normalized.startswith("executor:"):
        return normalized
    return f"executor:{normalized}"


def _executor_id_from_capability_id(capability_id: str) -> str:
    normalized = str(capability_id).strip()
    if normalized.startswith("executor:"):
        return normalized.split(":", 1)[1] or normalized
    return normalized


def _compat_scope(
    *,
    scope_kind: str,
    assignment_id: str | None,
    role_id: str | None,
    project_profile_id: str | None,
) -> tuple[str, dict[str, str | None]]:
    if scope_kind == "assignment":
        assignment = _text(assignment_id)
        if assignment is None:
            raise ValueError("assignment scope requires assignment_id")
        return ("session", {"session_mount_id": f"assignment:{assignment}", "work_context_id": None, "environment_ref": None})
    if scope_kind == "role":
        role = _text(role_id)
        if role is None:
            raise ValueError("role scope requires role_id")
        return ("work_context", {"session_mount_id": None, "work_context_id": f"role:{role}", "environment_ref": None})
    if scope_kind == "project":
        project = _text(project_profile_id)
        if project is None:
            raise ValueError("project scope requires project_profile_id")
        return ("work_context", {"session_mount_id": None, "work_context_id": f"project:{project}", "environment_ref": None})
    if scope_kind == "session":
        return ("session", {"session_mount_id": f"runtime:{_text(role_id) or 'session'}", "work_context_id": None, "environment_ref": None})
    raise ValueError(f"Unsupported executor scope_kind: {scope_kind}")


def _executor_metadata(
    *,
    executor_id: str,
    protocol_kind: str,
    scope_kind: str,
    assignment_id: str | None,
    role_id: str | None,
    project_profile_id: str | None,
    thread_id: str | None = None,
    runtime_status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _merge_metadata(
        metadata,
        {
            _EXECUTOR_RUNTIME_METADATA_KEY: {
                "executor_id": executor_id,
                "protocol_kind": protocol_kind,
                "scope_kind": scope_kind,
                "assignment_id": _text(assignment_id),
                "role_id": _text(role_id),
                "project_profile_id": _text(project_profile_id),
                "thread_id": _text(thread_id),
                "runtime_status": _text(runtime_status),
            }
        },
    )


def _executor_runtime_from_external(
    record: ExternalCapabilityRuntimeInstanceRecord,
) -> ExecutorRuntimeInstanceRecord:
    metadata = dict(record.metadata or {})
    compat = dict(metadata.pop(_EXECUTOR_RUNTIME_METADATA_KEY, {}) or {})
    return ExecutorRuntimeInstanceRecord(
        runtime_id=record.runtime_id,
        executor_id=str(
            compat.get("executor_id")
            or _executor_id_from_capability_id(record.capability_id)
        ),
        protocol_kind=str(
            compat.get("protocol_kind")
            or ("cli_runtime" if record.runtime_kind == "cli" else "unknown")
        ),
        scope_kind=str(compat.get("scope_kind") or "assignment"),
        assignment_id=_text(compat.get("assignment_id")),
        role_id=_text(compat.get("role_id")) or record.owner_agent_id,
        project_profile_id=_text(compat.get("project_profile_id")),
        thread_id=_text(compat.get("thread_id")),
        runtime_status=str(compat.get("runtime_status") or record.status),
        metadata=metadata,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class ExecutorRuntimeService:
    def __init__(
        self,
        *,
        external_runtime_service: ExternalCapabilityRuntimeService,
    ) -> None:
        self._external_runtime_service = external_runtime_service
        self._providers: dict[str, ExecutorProviderRecord] = {}
        self._role_bindings: dict[str, RoleExecutorBindingRecord] = {}
        self._model_policies: dict[str, ModelInvocationPolicyRecord] = {}

    def upsert_executor_provider(
        self,
        provider: ExecutorProviderRecord,
    ) -> ExecutorProviderRecord:
        self._providers[provider.provider_id] = provider
        return provider

    def upsert_role_executor_binding(
        self,
        binding: RoleExecutorBindingRecord,
    ) -> RoleExecutorBindingRecord:
        self._role_bindings[binding.role_id] = binding
        return binding

    def upsert_model_invocation_policy(
        self,
        policy: ModelInvocationPolicyRecord,
    ) -> ModelInvocationPolicyRecord:
        self._model_policies[policy.policy_id] = policy
        return policy

    def resolve_executor_provider(self, provider_id: str) -> ExecutorProviderRecord | None:
        return self._providers.get(provider_id)

    def resolve_role_executor_binding(self, role_id: str) -> RoleExecutorBindingRecord | None:
        return self._role_bindings.get(role_id)

    def resolve_model_invocation_policy(
        self,
        policy_id: str,
    ) -> ModelInvocationPolicyRecord | None:
        return self._model_policies.get(policy_id)

    def get_runtime(self, runtime_id: str) -> ExecutorRuntimeInstanceRecord | None:
        record = self._external_runtime_service.get_runtime(runtime_id)
        if record is None:
            return None
        return _executor_runtime_from_external(record)

    def list_runtimes(
        self,
        *,
        executor_id: str | None = None,
        assignment_id: str | None = None,
        role_id: str | None = None,
        runtime_status: str | None = None,
    ) -> list[ExecutorRuntimeInstanceRecord]:
        records = self._external_runtime_service.list_runtimes(
            capability_id=_executor_capability_id(executor_id) if executor_id else None,
        )
        items = [_executor_runtime_from_external(item) for item in records]
        filtered: list[ExecutorRuntimeInstanceRecord] = []
        for item in items:
            if assignment_id is not None and item.assignment_id != assignment_id:
                continue
            if role_id is not None and item.role_id != role_id:
                continue
            if runtime_status is not None and item.runtime_status != runtime_status:
                continue
            filtered.append(item)
        return filtered

    def create_or_reuse_runtime(
        self,
        *,
        executor_id: str,
        protocol_kind: str,
        scope_kind: str,
        assignment_id: str | None = None,
        role_id: str | None = None,
        project_profile_id: str | None = None,
        thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutorRuntimeInstanceRecord:
        compat_scope_kind, compat_refs = _compat_scope(
            scope_kind=scope_kind,
            assignment_id=assignment_id,
            role_id=role_id,
            project_profile_id=project_profile_id,
        )
        record = self._external_runtime_service.create_or_reuse_service_runtime(
            capability_id=_executor_capability_id(executor_id),
            scope_kind=compat_scope_kind,
            session_mount_id=compat_refs["session_mount_id"],
            work_context_id=compat_refs["work_context_id"],
            environment_ref=compat_refs["environment_ref"],
            owner_agent_id=role_id,
            command="",
            metadata=_executor_metadata(
                executor_id=executor_id,
                protocol_kind=protocol_kind,
                scope_kind=scope_kind,
                assignment_id=assignment_id,
                role_id=role_id,
                project_profile_id=project_profile_id,
                thread_id=thread_id,
                runtime_status="starting",
                metadata=metadata,
            ),
        )
        return _executor_runtime_from_external(record)

    def mark_runtime_ready(
        self,
        runtime_id: str,
        *,
        thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutorRuntimeInstanceRecord:
        current = self._external_runtime_service.get_runtime(runtime_id)
        if current is None:
            raise KeyError(f"Runtime '{runtime_id}' not found")
        compat = dict(current.metadata.get(_EXECUTOR_RUNTIME_METADATA_KEY, {}) or {})
        updated = self._external_runtime_service.mark_runtime_ready(
            runtime_id,
            metadata=_executor_metadata(
                executor_id=str(compat.get("executor_id") or _executor_id_from_capability_id(current.capability_id)),
                protocol_kind=str(compat.get("protocol_kind") or "unknown"),
                scope_kind=str(compat.get("scope_kind") or "assignment"),
                assignment_id=_text(compat.get("assignment_id")),
                role_id=_text(compat.get("role_id")) or current.owner_agent_id,
                project_profile_id=_text(compat.get("project_profile_id")),
                thread_id=_text(thread_id) or _text(compat.get("thread_id")),
                runtime_status="ready",
                metadata=metadata,
            ),
        )
        return _executor_runtime_from_external(updated)

    def mark_runtime_stopped(
        self,
        runtime_id: str,
        *,
        status: str = "stopped",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutorRuntimeInstanceRecord:
        current = self._external_runtime_service.get_runtime(runtime_id)
        if current is None:
            raise KeyError(f"Runtime '{runtime_id}' not found")
        compat = dict(current.metadata.get(_EXECUTOR_RUNTIME_METADATA_KEY, {}) or {})
        normalized_status = status if status in _ACTIVE_RUNTIME_STATUSES | {"completed", "stopped", "failed", "orphaned"} else "stopped"
        updated = self._external_runtime_service.mark_runtime_stopped(
            runtime_id,
            status=normalized_status,
            metadata=_executor_metadata(
                executor_id=str(compat.get("executor_id") or _executor_id_from_capability_id(current.capability_id)),
                protocol_kind=str(compat.get("protocol_kind") or "unknown"),
                scope_kind=str(compat.get("scope_kind") or "assignment"),
                assignment_id=_text(compat.get("assignment_id")),
                role_id=_text(compat.get("role_id")) or current.owner_agent_id,
                project_profile_id=_text(compat.get("project_profile_id")),
                thread_id=_text(compat.get("thread_id")),
                runtime_status=normalized_status,
                metadata=metadata,
            ),
        )
        return _executor_runtime_from_external(updated)
