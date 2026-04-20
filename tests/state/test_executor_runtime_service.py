# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import SQLiteStateStore
from copaw.state.external_runtime_service import ExternalCapabilityRuntimeService
from copaw.state.repositories import SqliteExternalCapabilityRuntimeRepository
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state.models_executor_runtime import (
    ExecutorProviderRecord,
    ExecutorRuntimeInstanceRecord,
    ModelInvocationPolicyRecord,
    RoleExecutorBindingRecord,
)


def _build_service(tmp_path) -> ExecutorRuntimeService:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteExternalCapabilityRuntimeRepository(store)
    external_runtime_service = ExternalCapabilityRuntimeService(repository=repository)
    return ExecutorRuntimeService(external_runtime_service=external_runtime_service)


def test_executor_runtime_instance_records_executor_kind_and_scope() -> None:
    record = ExecutorRuntimeInstanceRecord(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
    )

    assert record.executor_id == "codex"
    assert record.protocol_kind == "app_server"
    assert record.scope_kind == "assignment"
    assert record.assignment_id == "assign-1"


def test_role_executor_binding_routes_role_to_provider() -> None:
    binding = RoleExecutorBindingRecord(
        role_id="backend-engineer",
        executor_provider_id="codex-app-server",
        selection_mode="role-routed",
    )

    assert binding.executor_provider_id == "codex-app-server"
    assert binding.selection_mode == "role-routed"


def test_model_invocation_policy_supports_runtime_owned_mode() -> None:
    policy = ModelInvocationPolicyRecord(
        policy_id="default",
        ownership_mode="runtime_owned",
        default_model_ref="gpt-5-codex",
    )

    assert policy.ownership_mode == "runtime_owned"
    assert policy.default_model_ref == "gpt-5-codex"


def test_executor_runtime_service_reuses_assignment_runtime(tmp_path) -> None:
    service = _build_service(tmp_path)

    first = service.create_or_reuse_runtime(
        executor_id="codex-app-server",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
        role_id="backend-engineer",
        metadata={"source": "test"},
    )
    second = service.create_or_reuse_runtime(
        executor_id="codex-app-server",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
        role_id="backend-engineer",
    )

    assert second.runtime_id == first.runtime_id
    assert second.assignment_id == "assign-1"
    assert second.role_id == "backend-engineer"
    assert second.protocol_kind == "app_server"
    assert len(service.list_runtimes(executor_id="codex-app-server")) == 1


def test_executor_runtime_service_resolves_provider_binding_and_policy(tmp_path) -> None:
    service = _build_service(tmp_path)
    provider = ExecutorProviderRecord(
        provider_id="codex-app-server",
        provider_kind="external-executor",
        runtime_family="codex",
        control_surface_kind="app_server",
    )
    binding = RoleExecutorBindingRecord(
        role_id="backend-engineer",
        executor_provider_id="codex-app-server",
        selection_mode="role-routed",
    )
    policy = ModelInvocationPolicyRecord(
        policy_id="default",
        ownership_mode="runtime_owned",
        default_model_ref="gpt-5-codex",
    )

    service.upsert_executor_provider(provider)
    service.upsert_role_executor_binding(binding)
    service.upsert_model_invocation_policy(policy)

    assert service.resolve_executor_provider("codex-app-server") == provider
    assert service.resolve_role_executor_binding("backend-engineer") == binding
    assert service.resolve_model_invocation_policy("default") == policy
