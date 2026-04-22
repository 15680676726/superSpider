# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .external_runtime_service import ExternalCapabilityRuntimeService
from .models_executor_runtime import (
    ExecutionPolicyRecord,
    ExecutorEventRecord,
    ExecutorProviderRecord,
    ExecutorRuntimeInstanceRecord,
    ExecutorThreadBindingRecord,
    ExecutorTurnRecord,
    ModelInvocationPolicyRecord,
    ProjectProfileRecord,
    RoleContractRecord,
    RoleExecutorBindingRecord,
)
from .repositories.base import BaseExecutorRuntimeRepository
from .repositories.sqlite_executor_runtime import SqliteExecutorRuntimeRepository
from .store import SQLiteStateStore

_EXECUTOR_RUNTIME_METADATA_KEY = "executor_runtime"
_ACTIVE_RUNTIME_STATUSES = {"starting", "restarting", "ready", "degraded"}
_TERMINAL_RUNTIME_STATUSES = {"completed", "stopped", "failed", "orphaned"}
_TERMINAL_TURN_STATUS_BY_EVENT = {
    "task_completed": "completed",
    "task_failed": "failed",
}


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
        return (
            "session",
            {
                "session_mount_id": f"assignment:{assignment}",
                "work_context_id": None,
                "environment_ref": None,
            },
        )
    if scope_kind == "role":
        role = _text(role_id)
        if role is None:
            raise ValueError("role scope requires role_id")
        return (
            "work_context",
            {
                "session_mount_id": None,
                "work_context_id": f"role:{role}",
                "environment_ref": None,
            },
        )
    if scope_kind == "project":
        project = _text(project_profile_id)
        if project is None:
            raise ValueError("project scope requires project_profile_id")
        return (
            "work_context",
            {
                "session_mount_id": None,
                "work_context_id": f"project:{project}",
                "environment_ref": None,
            },
        )
    if scope_kind == "session":
        return (
            "session",
            {
                "session_mount_id": f"runtime:{_text(role_id) or 'session'}",
                "work_context_id": None,
                "environment_ref": None,
            },
        )
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
    record: Any,
) -> ExecutorRuntimeInstanceRecord:
    metadata = dict(record.metadata or {})
    compat = dict(metadata.pop(_EXECUTOR_RUNTIME_METADATA_KEY, {}) or {})
    if compat:
        metadata["executor_runtime_managed"] = True
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


def _coerce_state_store(
    external_runtime_service: ExternalCapabilityRuntimeService | None,
    *,
    explicit_store: SQLiteStateStore | None,
) -> SQLiteStateStore | None:
    if explicit_store is not None:
        return explicit_store
    if external_runtime_service is None:
        return None
    repository = getattr(external_runtime_service, "_repository", None)
    store = getattr(repository, "_store", None)
    return store if isinstance(store, SQLiteStateStore) else None


class ExecutorRuntimeService:
    def __init__(
        self,
        *,
        external_runtime_service: ExternalCapabilityRuntimeService | None = None,
        state_store: SQLiteStateStore | None = None,
        repository: BaseExecutorRuntimeRepository | None = None,
    ) -> None:
        self._external_runtime_service = external_runtime_service
        resolved_store = _coerce_state_store(
            external_runtime_service,
            explicit_store=state_store,
        )
        self._repository = repository or (
            SqliteExecutorRuntimeRepository(resolved_store)
            if resolved_store is not None
            else None
        )
        self._role_contracts: dict[str, RoleContractRecord] = {}
        self._project_profiles: dict[str, ProjectProfileRecord] = {}
        self._execution_policies: dict[str, ExecutionPolicyRecord] = {}
        self._providers: dict[str, ExecutorProviderRecord] = {}
        self._role_bindings: dict[str, RoleExecutorBindingRecord] = {}
        self._model_policies: dict[str, ModelInvocationPolicyRecord] = {}
        self._runtime_instances: dict[str, ExecutorRuntimeInstanceRecord] = {}
        self._thread_bindings: dict[str, ExecutorThreadBindingRecord] = {}
        self._turn_records: dict[str, ExecutorTurnRecord] = {}
        self._event_records: dict[str, ExecutorEventRecord] = {}

    def upsert_role_contract(self, record: RoleContractRecord) -> RoleContractRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_role_contract(record)
        self._role_contracts[record.role_id] = record
        return record

    def resolve_role_contract(self, role_id: str) -> RoleContractRecord | None:
        repository = self._repository
        if repository is not None:
            return repository.get_role_contract(role_id)
        return self._role_contracts.get(role_id)

    def upsert_project_profile(self, record: ProjectProfileRecord) -> ProjectProfileRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_project_profile(record)
        self._project_profiles[record.project_profile_id] = record
        return record

    def resolve_project_profile(self, project_profile_id: str) -> ProjectProfileRecord | None:
        repository = self._repository
        if repository is not None:
            return repository.get_project_profile(project_profile_id)
        return self._project_profiles.get(project_profile_id)

    def upsert_execution_policy(self, record: ExecutionPolicyRecord) -> ExecutionPolicyRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_execution_policy(record)
        self._execution_policies[record.policy_id] = record
        return record

    def resolve_execution_policy(self, policy_id: str) -> ExecutionPolicyRecord | None:
        repository = self._repository
        if repository is not None:
            return repository.get_execution_policy(policy_id)
        return self._execution_policies.get(policy_id)

    def upsert_executor_provider(
        self,
        provider: ExecutorProviderRecord,
    ) -> ExecutorProviderRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_executor_provider(provider)
        self._providers[provider.provider_id] = provider
        return provider

    def upsert_role_executor_binding(
        self,
        binding: RoleExecutorBindingRecord,
    ) -> RoleExecutorBindingRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_role_executor_binding(binding)
        self._role_bindings[binding.role_id] = binding
        return binding

    def upsert_model_invocation_policy(
        self,
        policy: ModelInvocationPolicyRecord,
    ) -> ModelInvocationPolicyRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_model_invocation_policy(policy)
        self._model_policies[policy.policy_id] = policy
        return policy

    def resolve_executor_provider(self, provider_id: str) -> ExecutorProviderRecord | None:
        repository = self._repository
        if repository is not None:
            return repository.get_executor_provider(provider_id)
        return self._providers.get(provider_id)

    def list_executor_providers(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorProviderRecord]:
        repository = self._repository
        if repository is not None:
            return repository.list_executor_providers(
                status=status,
                limit=limit,
            )
        items = list(self._providers.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        items.sort(
            key=lambda item: (
                item.updated_at or item.created_at,
                item.created_at,
            ),
            reverse=True,
        )
        if isinstance(limit, int) and limit > 0:
            return items[:limit]
        return items

    def resolve_role_executor_binding(self, role_id: str) -> RoleExecutorBindingRecord | None:
        repository = self._repository
        if repository is not None:
            return repository.get_role_executor_binding(role_id)
        return self._role_bindings.get(role_id)

    def resolve_model_invocation_policy(
        self,
        policy_id: str,
    ) -> ModelInvocationPolicyRecord | None:
        repository = self._repository
        if repository is not None:
            return repository.get_model_invocation_policy(policy_id)
        return self._model_policies.get(policy_id)

    def get_runtime(
        self,
        runtime_id: str,
        *,
        formal_only: bool = False,
    ) -> ExecutorRuntimeInstanceRecord | None:
        repository = self._repository
        if repository is not None:
            runtime = repository.get_runtime(runtime_id)
        else:
            runtime = self._runtime_instances.get(runtime_id)
        if runtime is not None:
            if formal_only and not self.is_formal_runtime(runtime):
                return None
            return runtime
        service = self._external_runtime_service
        if service is None:
            return None
        record = service.get_runtime(runtime_id)
        if record is None:
            return None
        runtime = _executor_runtime_from_external(record)
        if formal_only and not self.is_formal_runtime(runtime):
            return None
        return runtime

    def list_runtimes(
        self,
        *,
        executor_id: str | None = None,
        assignment_id: str | None = None,
        role_id: str | None = None,
        runtime_status: str | None = None,
        formal_only: bool = False,
    ) -> list[ExecutorRuntimeInstanceRecord]:
        repository = self._repository
        if repository is not None:
            items = repository.list_runtimes(
                executor_id=executor_id,
                assignment_id=assignment_id,
                role_id=role_id,
                runtime_status=runtime_status,
                limit=None,
            )
        else:
            items = list(self._runtime_instances.values())
        filtered: list[ExecutorRuntimeInstanceRecord] = []
        for item in items:
            if formal_only and not self.is_formal_runtime(item):
                continue
            if executor_id is not None and item.executor_id != executor_id:
                continue
            if assignment_id is not None and item.assignment_id != assignment_id:
                continue
            if role_id is not None and item.role_id != role_id:
                continue
            if runtime_status is not None and item.runtime_status != runtime_status:
                continue
            filtered.append(item)
        if filtered:
            return filtered
        service = self._external_runtime_service
        if service is None:
            return []
        records = service.list_runtimes(
            capability_id=_executor_capability_id(executor_id) if executor_id else None,
        )
        fallback = [_executor_runtime_from_external(item) for item in records]
        output: list[ExecutorRuntimeInstanceRecord] = []
        for item in fallback:
            if formal_only and not self.is_formal_runtime(item):
                continue
            if assignment_id is not None and item.assignment_id != assignment_id:
                continue
            if role_id is not None and item.role_id != role_id:
                continue
            if runtime_status is not None and item.runtime_status != runtime_status:
                continue
            output.append(item)
        return output

    @staticmethod
    def is_formal_runtime(runtime: ExecutorRuntimeInstanceRecord) -> bool:
        metadata = dict(runtime.metadata or {})
        return bool(metadata.get("executor_runtime_managed"))

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
        runtime_metadata = _merge_metadata(metadata, {"executor_runtime_managed": True})
        existing = self._resolve_active_runtime(
            executor_id=executor_id,
            scope_kind=scope_kind,
            assignment_id=assignment_id,
            role_id=role_id,
            project_profile_id=project_profile_id,
        )
        now = _utc_now()
        if existing is None:
            runtime = ExecutorRuntimeInstanceRecord(
                executor_id=executor_id,
                protocol_kind=protocol_kind,
                scope_kind=scope_kind,
                assignment_id=_text(assignment_id),
                role_id=_text(role_id),
                project_profile_id=_text(project_profile_id),
                thread_id=_text(thread_id),
                runtime_status="starting",
                metadata=runtime_metadata,
            )
        else:
            runtime = existing.model_copy(
                update={
                    "executor_id": executor_id,
                    "protocol_kind": protocol_kind or existing.protocol_kind,
                    "scope_kind": scope_kind or existing.scope_kind,
                    "assignment_id": _text(assignment_id) or existing.assignment_id,
                    "role_id": _text(role_id) or existing.role_id,
                    "project_profile_id": _text(project_profile_id) or existing.project_profile_id,
                    "thread_id": _text(thread_id) or existing.thread_id,
                    "metadata": _merge_metadata(existing.metadata, runtime_metadata),
                    "updated_at": now,
                }
            )
        runtime = self._store_runtime_instance(runtime)
        if thread_id is not None:
            self._sync_thread_binding(
                runtime=runtime,
                thread_id=thread_id,
                last_turn_id=None,
                metadata=metadata,
            )
        return runtime

    def mark_runtime_ready(
        self,
        runtime_id: str,
        *,
        thread_id: str | None = None,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutorRuntimeInstanceRecord:
        current = self.get_runtime(runtime_id)
        if current is None:
            raise KeyError(f"Runtime '{runtime_id}' not found")
        runtime = self._store_runtime_instance(
            current.model_copy(
                update={
                    "thread_id": _text(thread_id) or current.thread_id,
                    "runtime_status": "ready",
                    "metadata": _merge_metadata(
                        current.metadata,
                        _merge_metadata(metadata, {"executor_runtime_managed": True}),
                    ),
                    "updated_at": _utc_now(),
                }
            )
        )
        binding = self._sync_thread_binding(
            runtime=runtime,
            thread_id=_text(thread_id) or runtime.thread_id,
            last_turn_id=turn_id,
            metadata=metadata,
        )
        if binding is not None and turn_id is not None:
            self._sync_turn_record(
                binding=binding,
                runtime=runtime,
                turn_id=turn_id,
                turn_status="running",
                summary=None,
                metadata=metadata,
            )
        return runtime

    def mark_runtime_stopped(
        self,
        runtime_id: str,
        *,
        status: str = "stopped",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutorRuntimeInstanceRecord:
        current = self.get_runtime(runtime_id)
        if current is None:
            raise KeyError(f"Runtime '{runtime_id}' not found")
        normalized_status = (
            status
            if status in _ACTIVE_RUNTIME_STATUSES | _TERMINAL_RUNTIME_STATUSES
            else "stopped"
        )
        runtime = self._store_runtime_instance(
            current.model_copy(
                update={
                    "runtime_status": normalized_status,
                    "metadata": _merge_metadata(
                        current.metadata,
                        _merge_metadata(metadata, {"executor_runtime_managed": True}),
                    ),
                    "updated_at": _utc_now(),
                }
            )
        )
        for binding in self.list_thread_bindings(runtime_id=runtime_id):
            updated_binding = binding.model_copy(
                update={
                    "runtime_status": normalized_status,
                    "last_seen_at": _utc_now(),
                    "metadata": _merge_metadata(binding.metadata, metadata),
                    "updated_at": _utc_now(),
                }
            )
            self._store_thread_binding(updated_binding)
        return runtime

    def _store_runtime_instance(
        self,
        record: ExecutorRuntimeInstanceRecord,
    ) -> ExecutorRuntimeInstanceRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_runtime(record)
        self._runtime_instances[record.runtime_id] = record
        return record

    def _resolve_active_runtime(
        self,
        *,
        executor_id: str,
        scope_kind: str,
        assignment_id: str | None,
        role_id: str | None,
        project_profile_id: str | None,
    ) -> ExecutorRuntimeInstanceRecord | None:
        candidates = self.list_runtimes(
            executor_id=executor_id,
            assignment_id=assignment_id if scope_kind == "assignment" else None,
            role_id=role_id if scope_kind == "role" else None,
            runtime_status=None,
            formal_only=True,
        )
        for item in candidates:
            if item.scope_kind != scope_kind:
                continue
            if scope_kind == "assignment" and item.assignment_id != _text(assignment_id):
                continue
            if scope_kind == "role" and item.role_id != _text(role_id):
                continue
            if scope_kind == "project" and item.project_profile_id != _text(project_profile_id):
                continue
            if scope_kind == "session" and item.role_id != _text(role_id):
                continue
            if item.runtime_status in _ACTIVE_RUNTIME_STATUSES:
                return item
        return None

    def list_thread_bindings(
        self,
        *,
        runtime_id: str | None = None,
        thread_id: str | None = None,
        role_id: str | None = None,
        assignment_id: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorThreadBindingRecord]:
        repository = self._repository
        if repository is not None:
            return repository.list_thread_bindings(
                runtime_id=runtime_id,
                thread_id=thread_id,
                role_id=role_id,
                assignment_id=assignment_id,
                limit=limit,
            )
        items = list(self._thread_bindings.values())
        filtered = [
            item
            for item in items
            if (runtime_id is None or item.runtime_id == runtime_id)
            and (thread_id is None or item.thread_id == thread_id)
            and (role_id is None or item.role_id == role_id)
            and (assignment_id is None or item.assignment_id == assignment_id)
        ]
        filtered.sort(
            key=lambda item: (
                item.updated_at or item.created_at,
                item.created_at,
            ),
            reverse=True,
        )
        if isinstance(limit, int) and limit > 0:
            return filtered[:limit]
        return filtered

    def list_turn_records(
        self,
        *,
        runtime_id: str | None = None,
        thread_id: str | None = None,
        assignment_id: str | None = None,
        turn_id: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorTurnRecord]:
        repository = self._repository
        if repository is not None:
            return repository.list_turn_records(
                runtime_id=runtime_id,
                thread_id=thread_id,
                assignment_id=assignment_id,
                turn_id=turn_id,
                limit=limit,
            )
        items = list(self._turn_records.values())
        filtered = [
            item
            for item in items
            if (runtime_id is None or item.runtime_id == runtime_id)
            and (thread_id is None or item.thread_id == thread_id)
            and (assignment_id is None or item.assignment_id == assignment_id)
            and (turn_id is None or item.turn_id == turn_id)
        ]
        filtered.sort(
            key=lambda item: (
                item.updated_at or item.created_at,
                item.created_at,
            ),
            reverse=True,
        )
        if isinstance(limit, int) and limit > 0:
            return filtered[:limit]
        return filtered

    def list_event_records(
        self,
        *,
        runtime_id: str | None = None,
        thread_id: str | None = None,
        assignment_id: str | None = None,
        turn_id: str | None = None,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorEventRecord]:
        repository = self._repository
        if repository is not None:
            return repository.list_event_records(
                runtime_id=runtime_id,
                thread_id=thread_id,
                assignment_id=assignment_id,
                turn_id=turn_id,
                event_type=event_type,
                limit=limit,
            )
        items = list(self._event_records.values())
        filtered = [
            item
            for item in items
            if (runtime_id is None or item.runtime_id == runtime_id)
            and (thread_id is None or item.thread_id == thread_id)
            and (assignment_id is None or item.assignment_id == assignment_id)
            and (turn_id is None or item.turn_id == turn_id)
            and (event_type is None or item.event_type == event_type)
        ]
        filtered.sort(key=lambda item: item.created_at, reverse=True)
        if isinstance(limit, int) and limit > 0:
            return filtered[:limit]
        return filtered

    def record_event(
        self,
        *,
        runtime_id: str,
        assignment_id: str | None,
        thread_id: str | None,
        turn_id: str | None,
        event_type: str,
        source_type: str,
        payload: dict[str, Any] | None,
        summary: str,
        raw_method: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutorEventRecord:
        runtime = self.get_runtime(runtime_id)
        if runtime is None:
            raise KeyError(f"Runtime '{runtime_id}' not found")
        resolved_thread_id = _text(thread_id) or runtime.thread_id
        binding = self._sync_thread_binding(
            runtime=runtime,
            thread_id=resolved_thread_id,
            last_turn_id=turn_id,
            metadata=metadata,
        )
        turn_record = None
        if binding is not None and turn_id is not None:
            turn_status = _TERMINAL_TURN_STATUS_BY_EVENT.get(event_type, "running")
            turn_record = self._sync_turn_record(
                binding=binding,
                runtime=runtime,
                turn_id=turn_id,
                turn_status=turn_status,
                summary=summary if turn_status in {"completed", "failed"} else None,
                metadata=metadata,
            )
        event_record = ExecutorEventRecord(
            runtime_id=runtime_id,
            turn_record_id=turn_record.turn_record_id if turn_record is not None else None,
            assignment_id=_text(assignment_id) or runtime.assignment_id,
            thread_id=resolved_thread_id,
            turn_id=_text(turn_id),
            event_type=event_type,
            source_type=source_type,
            summary=str(summary or "").strip(),
            payload=dict(payload or {}),
            raw_method=_text(raw_method),
            metadata=dict(metadata or {}),
        )
        stored = self._store_event_record(event_record)
        terminal_runtime_status = _TERMINAL_TURN_STATUS_BY_EVENT.get(event_type)
        if terminal_runtime_status is not None:
            runtime = self.mark_runtime_stopped(
                runtime_id,
                status=terminal_runtime_status,
                metadata={"last_event_type": event_type, **dict(metadata or {})},
            )
            if binding is not None:
                self._sync_thread_binding(
                    runtime=runtime,
                    thread_id=resolved_thread_id,
                    last_turn_id=turn_id,
                    metadata=metadata,
                )
        return stored

    def _store_thread_binding(
        self,
        record: ExecutorThreadBindingRecord,
    ) -> ExecutorThreadBindingRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_thread_binding(record)
        self._thread_bindings[record.binding_id] = record
        return record

    def _store_turn_record(self, record: ExecutorTurnRecord) -> ExecutorTurnRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_turn_record(record)
        self._turn_records[record.turn_record_id] = record
        return record

    def _store_event_record(self, record: ExecutorEventRecord) -> ExecutorEventRecord:
        repository = self._repository
        if repository is not None:
            return repository.upsert_event_record(record)
        self._event_records[record.event_id] = record
        return record

    def _sync_thread_binding(
        self,
        *,
        runtime: ExecutorRuntimeInstanceRecord,
        thread_id: str | None,
        last_turn_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> ExecutorThreadBindingRecord | None:
        resolved_thread_id = _text(thread_id)
        if resolved_thread_id is None:
            return None
        existing = next(
            iter(
                self.list_thread_bindings(
                    runtime_id=runtime.runtime_id,
                    thread_id=resolved_thread_id,
                    limit=1,
                )
            ),
            None,
        )
        now = _utc_now()
        if existing is None:
            record = ExecutorThreadBindingRecord(
                runtime_id=runtime.runtime_id,
                role_id=runtime.role_id,
                executor_provider_id=runtime.executor_id,
                project_profile_id=runtime.project_profile_id,
                assignment_id=runtime.assignment_id,
                thread_id=resolved_thread_id,
                runtime_status=runtime.runtime_status,
                last_turn_id=_text(last_turn_id),
                last_seen_at=now,
                metadata=dict(metadata or {}),
            )
        else:
            record = existing.model_copy(
                update={
                    "role_id": runtime.role_id or existing.role_id,
                    "executor_provider_id": runtime.executor_id,
                    "project_profile_id": runtime.project_profile_id or existing.project_profile_id,
                    "assignment_id": runtime.assignment_id or existing.assignment_id,
                    "thread_id": resolved_thread_id,
                    "runtime_status": runtime.runtime_status,
                    "last_turn_id": _text(last_turn_id) or existing.last_turn_id,
                    "last_seen_at": now,
                    "metadata": _merge_metadata(existing.metadata, metadata),
                    "updated_at": now,
                }
            )
        return self._store_thread_binding(record)

    def _sync_turn_record(
        self,
        *,
        binding: ExecutorThreadBindingRecord,
        runtime: ExecutorRuntimeInstanceRecord,
        turn_id: str,
        turn_status: str,
        summary: str | None,
        metadata: dict[str, Any] | None,
    ) -> ExecutorTurnRecord:
        existing = next(
            iter(
                self.list_turn_records(
                    runtime_id=runtime.runtime_id,
                    turn_id=turn_id,
                    limit=1,
                )
            ),
            None,
        )
        now = _utc_now()
        started_at = (
            existing.started_at
            if existing is not None and existing.started_at is not None
            else now
        )
        completed_at = (
            now
            if turn_status in {"completed", "failed", "stopped"}
            else (existing.completed_at if existing is not None else None)
        )
        if existing is None:
            record = ExecutorTurnRecord(
                runtime_id=runtime.runtime_id,
                thread_binding_id=binding.binding_id,
                assignment_id=runtime.assignment_id,
                thread_id=binding.thread_id,
                turn_id=turn_id,
                turn_status=turn_status,
                started_at=started_at,
                completed_at=completed_at,
                summary=_text(summary),
                metadata=dict(metadata or {}),
            )
        else:
            record = existing.model_copy(
                update={
                    "thread_binding_id": binding.binding_id,
                    "assignment_id": runtime.assignment_id or existing.assignment_id,
                    "thread_id": binding.thread_id,
                    "turn_status": turn_status,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "summary": _text(summary) or existing.summary,
                    "metadata": _merge_metadata(existing.metadata, metadata),
                    "updated_at": now,
                }
            )
        return self._store_turn_record(record)
