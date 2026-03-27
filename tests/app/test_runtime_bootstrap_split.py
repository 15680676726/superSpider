# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from copaw.app import runtime_service_graph as runtime_service_graph_module
from copaw.app.runtime_service_graph import build_runtime_bootstrap
from copaw.app.runtime_events import RuntimeEventBus
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.state import SQLiteStateStore


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_documentation_runtime_first_alignment_docs_do_not_define_a_second_main_chain() -> None:
    spec_text = _read(
        "docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md",
    )
    status_text = _read("TASK_STATUS.md")
    data_model_text = _read("DATA_MODEL_DRAFT.md")
    api_map_text = _read("API_TRANSITION_MAP.md")

    assert (
        "StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan"
        in spec_text
    )
    assert "不能替代现有 7 层" in spec_text
    assert "runtime-first 补充视角" in status_text
    assert "runtime-first 补充视角" in data_model_text
    assert "runtime-first 补充视角" in api_map_text


def test_build_runtime_bootstrap_assembles_domain_services_via_domain_builder(
    monkeypatch,
    tmp_path,
) -> None:
    calls: dict[str, object] = {}
    repositories = SimpleNamespace(
        work_context_repository=object(),
        industry_instance_repository=SimpleNamespace(list_instances=lambda limit=None: []),
    )
    capability_service = SimpleNamespace(
        set_turn_executor=lambda value: calls.setdefault("turn_executor", value),
    )
    domain_services = SimpleNamespace(
        goal_service="goal-service",
        agent_profile_service="agent-profile-service",
        reporting_service="reporting-service",
        operating_lane_service="operating-lane-service",
        backlog_service="backlog-service",
        operating_cycle_service="operating-cycle-service",
        assignment_service="assignment-service",
        agent_report_service="agent-report-service",
        media_service="media-service",
        industry_service="industry-service",
        workflow_template_service="workflow-template-service",
        fixed_sop_service="fixed-sop-service",
        routine_service="routine-service",
        prediction_service="prediction-service",
        delegation_service="delegation-service",
        query_execution_service="query-execution-service",
        main_brain_chat_service="main-brain-chat-service",
        main_brain_orchestrator="main-brain-orchestrator",
    )

    monkeypatch.setattr(runtime_service_graph_module, "WORKING_DIR", tmp_path)
    monkeypatch.setattr(
        runtime_service_graph_module,
        "SessionRuntimeThreadHistoryReader",
        lambda session_backend: "thread-history-reader",
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "build_runtime_repositories",
        lambda state_store: repositories,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_build_runtime_observability",
        lambda **kwargs: ("evidence-ledger", "environment-registry", "environment-service", "runtime-event-bus"),
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_build_query_services",
        lambda **kwargs: (
            SimpleNamespace(),
            "evidence-query-service",
            "strategy-memory-service",
            "knowledge-service",
            SimpleNamespace(rebuild_all=lambda: calls.setdefault("rebuild_all", True)),
            SimpleNamespace(reflect=lambda **reflect_kwargs: calls.setdefault("reflect_calls", []).append(reflect_kwargs)),
            SimpleNamespace(
                list_backends=lambda: [SimpleNamespace(backend_id="hybrid-local", is_default=True)],
                prepare_sidecar_backends=lambda prewarm_backend_ids: calls.setdefault("prewarm_backends", list(prewarm_backend_ids)),
            ),
            "memory-retain-service",
            "agent-experience-service",
        ),
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "WorkContextService",
        lambda repository: "work-context-service",
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_build_kernel_runtime",
        lambda **kwargs: (
            "learning-service",
            "governance-service",
            "kernel-task-store",
            "kernel-tool-bridge",
            capability_service,
            "kernel-dispatcher",
            "actor-mailbox-service",
            "actor-worker",
            "actor-supervisor",
        ),
    )

    def _fake_domain_builder(**kwargs):
        calls["domain_builder_kwargs"] = kwargs
        return domain_services

    monkeypatch.setattr(
        runtime_service_graph_module,
        "build_runtime_domain_services",
        _fake_domain_builder,
    )
    monkeypatch.setattr(
        runtime_service_graph_module.ProviderManager,
        "get_instance",
        staticmethod(lambda: "provider-manager"),
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "KernelTurnExecutor",
        lambda **kwargs: "turn-executor",
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "RuntimeHealthService",
        lambda **kwargs: "runtime-health-service",
    )

    bootstrap = build_runtime_bootstrap(
        session_backend="session-backend",
        memory_manager="memory-manager",
        mcp_manager="mcp-manager",
    )

    assert calls["domain_builder_kwargs"]["work_context_service"] == "work-context-service"
    assert calls["domain_builder_kwargs"]["capability_service"] is capability_service
    assert bootstrap.goal_service == "goal-service"
    assert bootstrap.main_brain_orchestrator == "main-brain-orchestrator"
    assert bootstrap.turn_executor == "turn-executor"


def test_environment_service_rebinds_cooperative_facade_after_late_bootstrap_injection(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    environment_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_repository,
        host_id="windows-host",
        process_id=5050,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    runtime_event_bus = RuntimeEventBus(max_events=20)

    environment_service.set_session_repository(session_repository)
    environment_service.set_runtime_event_bus(runtime_event_bus)

    lease = environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-1",
        user_id="alice",
        owner="worker-5",
        ttl_seconds=60,
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
        },
    )

    browser_snapshot = environment_service.register_browser_companion(
        session_mount_id=lease.id,
        transport_ref="transport:browser-companion:localhost",
        status="ready",
        available=True,
    )
    environment_service.register_host_watchers(
        lease.id,
        downloads={
            "status": "healthy",
            "download_policy": "download-bucket:workspace-main",
        },
    )
    environment_service.register_windows_app_adapter(
        session_mount_id=lease.id,
        adapter_refs=["app-adapter:excel"],
        app_identity="excel",
        control_channel="accessibility-tree",
    )

    browser_projection = environment_service.browser_companion_snapshot(
        session_mount_id=lease.id,
    )
    watcher_projection = environment_service.host_watchers_snapshot(lease.id)
    environment_detail = environment_service.get_session_detail(lease.id, limit=5)

    assert browser_snapshot["browser_companion"]["available"] is True
    assert browser_projection["browser_companion"]["transport_ref"] == (
        "transport:browser-companion:localhost"
    )
    assert watcher_projection["watchers"]["downloads"]["available"] is True
    assert environment_detail is not None
    assert (
        environment_detail["cooperative_adapter_availability"]["windows_app_adapters"][
            "app_identity"
        ]
        == "excel"
    )
    event_names = [event.event_name for event in runtime_event_bus.list_events(limit=10)]
    assert "cooperative_adapter.browser_companion_updated" in event_names
