# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import SQLiteStateStore
from copaw.state.external_runtime_service import ExternalCapabilityRuntimeService
from copaw.state.repositories import SqliteExternalCapabilityRuntimeRepository
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state import models_executor_runtime as executor_models
from copaw.state.models_executor_runtime import (
    ExecutionPolicyRecord,
    ExecutorProviderRecord,
    ExecutorRuntimeInstanceRecord,
    ModelInvocationPolicyRecord,
    ProjectProfileRecord,
    RoleContractRecord,
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


def test_executor_runtime_service_resolves_role_contract_project_profile_and_policy(
    tmp_path,
) -> None:
    service = _build_service(tmp_path)
    role_contract = RoleContractRecord(
        role_id="backend-engineer",
        display_name="Backend Engineer",
        summary="Owns implementation slices.",
        responsibilities=["deliver runtime changes"],
        planning_contract="plan-before-apply",
        reporting_contract="result-first",
        escalation_rules=["raise blockers immediately"],
        default_skill_set=["copaw-worker-core"],
        default_project_profile="carrier-main",
        status="active",
    )
    project_profile = ProjectProfileRecord(
        project_profile_id="carrier-main",
        root_path="D:/word/copaw",
        agents_md_path="D:/word/copaw/AGENTS.md",
        role_md_path="D:/word/copaw/ROLE.md",
        project_md_path="D:/word/copaw/PROJECT.md",
        skill_root="D:/word/copaw/.codex/skills",
        runtime_root="D:/word/copaw/runtime",
        status="active",
    )
    execution_policy = ExecutionPolicyRecord(
        policy_id="open-default",
        policy_name="open_default",
        sandbox_mode="danger-full-access",
        approval_mode="never",
        network_mode="enabled",
        notes="High-trust executor baseline.",
        status="active",
    )

    service.upsert_role_contract(role_contract)
    service.upsert_project_profile(project_profile)
    service.upsert_execution_policy(execution_policy)

    assert service.resolve_role_contract("backend-engineer") == role_contract
    assert service.resolve_project_profile("carrier-main") == project_profile
    assert service.resolve_execution_policy("open-default") == execution_policy


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


def test_executor_runtime_service_supports_canonical_runtime_truth_without_external_runtime_service(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    service = ExecutorRuntimeService(state_store=store)

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
    stored = service.get_runtime(first.runtime_id)

    assert second.runtime_id == first.runtime_id
    assert stored is not None
    assert stored.assignment_id == "assign-1"
    assert stored.executor_id == "codex-app-server"
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


def test_executor_runtime_service_marks_sidecar_install_status(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "sidecar-state.db")
    service = ExecutorRuntimeService(state_store=store)
    install_record_type = getattr(
        executor_models,
        "ExecutorSidecarInstallRecord",
        None,
    )
    assert install_record_type is not None

    service.upsert_sidecar_install(
        install_record_type(
            install_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            install_root="D:/word/copaw/runtime/codex/0.10.0",
            executable_path="D:/word/copaw/runtime/codex/0.10.0/codex.exe",
            install_status="ready",
            metadata={"managed_by": "copaw"},
        )
    )

    degraded = service.mark_sidecar_install_status(
        "codex-stable-0.10.0",
        status="degraded",
        metadata={"reason": "healthcheck_failed"},
    )
    active = service.get_active_sidecar_install(runtime_family="codex")

    assert degraded.install_status == "degraded"
    assert active is not None
    assert active.install_status == "degraded"
    assert active.metadata["reason"] == "healthcheck_failed"


def test_mark_runtime_ready_persists_thread_binding_and_turn_record(tmp_path) -> None:
    service = _build_service(tmp_path)

    runtime = service.create_or_reuse_runtime(
        executor_id="codex-app-server",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
        role_id="backend-engineer",
        project_profile_id="carrier-main",
    )
    ready = service.mark_runtime_ready(
        runtime.runtime_id,
        thread_id="thread-1",
        turn_id="turn-1",
    )

    bindings = service.list_thread_bindings(thread_id="thread-1")
    turns = service.list_turn_records(thread_id="thread-1")

    assert ready.thread_id == "thread-1"
    assert len(bindings) == 1
    assert bindings[0].runtime_id == runtime.runtime_id
    assert bindings[0].executor_provider_id == "codex-app-server"
    assert bindings[0].role_id == "backend-engineer"
    assert bindings[0].project_profile_id == "carrier-main"
    assert bindings[0].runtime_status == "ready"
    assert bindings[0].last_turn_id == "turn-1"
    assert bindings[0].last_seen_at is not None
    assert len(turns) == 1
    assert turns[0].runtime_id == runtime.runtime_id
    assert turns[0].assignment_id == "assign-1"
    assert turns[0].turn_id == "turn-1"
    assert turns[0].turn_status == "running"
    assert turns[0].started_at is not None
    assert turns[0].completed_at is None


def test_executor_runtime_service_persists_parent_linkage_continuity_and_recovery_contract(
    tmp_path,
) -> None:
    service = _build_service(tmp_path)

    runtime = service.create_or_reuse_runtime(
        executor_id="codex-app-server",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-child-1",
        role_id="backend-engineer",
        parent_runtime_id="runtime-parent-1",
        continuity_metadata={
            "control_thread_id": "control-thread-1",
            "session_id": "industry-chat:industry-1:execution-core",
            "work_context_id": "ctx-1",
        },
        recovery_metadata={
            "strategy": "restart-once",
            "status": "ready",
        },
    )
    ready = service.mark_runtime_ready(
        runtime.runtime_id,
        thread_id="thread-child-1",
        turn_id="turn-child-1",
    )

    bindings = service.list_thread_bindings(thread_id="thread-child-1")
    turns = service.list_turn_records(thread_id="thread-child-1")

    assert ready.metadata["parent_runtime_id"] == "runtime-parent-1"
    assert ready.metadata["continuity"]["control_thread_id"] == "control-thread-1"
    assert ready.metadata["continuity"]["work_context_id"] == "ctx-1"
    assert ready.metadata["recovery"]["strategy"] == "restart-once"
    assert bindings[0].metadata["parent_runtime_id"] == "runtime-parent-1"
    assert bindings[0].metadata["continuity"]["session_id"] == (
        "industry-chat:industry-1:execution-core"
    )
    assert turns[0].metadata["continuity"]["work_context_id"] == "ctx-1"
    assert turns[0].metadata["recovery"]["status"] == "ready"


def test_record_event_persists_formal_executor_event_and_updates_turn_terminal_state(
    tmp_path,
) -> None:
    service = _build_service(tmp_path)

    runtime = service.create_or_reuse_runtime(
        executor_id="codex-app-server",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
        role_id="backend-engineer",
    )
    service.mark_runtime_ready(
        runtime.runtime_id,
        thread_id="thread-1",
        turn_id="turn-1",
    )

    stored = service.record_event(
        runtime_id=runtime.runtime_id,
        assignment_id="assign-1",
        thread_id="thread-1",
        turn_id="turn-1",
        event_type="task_completed",
        source_type="turn",
        payload={"summary": "Executor finished assignment successfully."},
        summary="Executor finished assignment successfully.",
    )

    events = service.list_event_records(thread_id="thread-1")
    turns = service.list_turn_records(thread_id="thread-1")
    bindings = service.list_thread_bindings(thread_id="thread-1")

    assert stored.turn_id == "turn-1"
    assert stored.event_type == "task_completed"
    assert stored.source_type == "turn"
    assert stored.assignment_id == "assign-1"
    assert stored.runtime_id == runtime.runtime_id
    assert stored.payload["summary"] == "Executor finished assignment successfully."
    assert len(events) == 1
    assert events[0].event_id == stored.event_id
    assert turns[0].turn_status == "completed"
    assert turns[0].summary == "Executor finished assignment successfully."
    assert turns[0].completed_at is not None
    assert bindings[0].runtime_status == "completed"
