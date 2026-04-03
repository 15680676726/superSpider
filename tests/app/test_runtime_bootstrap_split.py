# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from copaw.app import runtime_bootstrap_domains as runtime_bootstrap_domains_module
from copaw.app import runtime_service_graph as runtime_service_graph_module
from copaw.app import runtime_bootstrap_execution as runtime_bootstrap_execution_module
from copaw.app.runtime_service_graph import build_runtime_bootstrap
from copaw.app.runtime_events import RuntimeEventBus
from copaw.compiler import (
    AssignmentPlanningCompiler,
    CyclePlanningCompiler,
    ReportReplanEngine,
    StrategyPlanningCompiler,
)
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.industry.service_context import build_industry_service_runtime_bindings
from copaw.kernel.query_execution_runtime import _QueryExecutionRuntimeMixin
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


def test_task_status_locks_main_brain_chat_performance_regression_guards() -> None:
    status_text = _read("TASK_STATUS.md")

    assert "轻量聊天链回归护栏已锁定（runtime conversations / bootstrap wiring）" in status_text


def test_query_execution_runtime_mixin_inherits_split_runtime_seams() -> None:
    base_modules = {base.__module__ for base in _QueryExecutionRuntimeMixin.__bases__}
    assert "copaw.kernel.query_execution_context_runtime" in base_modules
    assert "copaw.kernel.query_execution_resident_runtime" in base_modules
    assert "copaw.kernel.query_execution_usage_runtime" in base_modules


def test_industry_runtime_bindings_preserve_formal_planning_services() -> None:
    strategy_planning_compiler = StrategyPlanningCompiler()
    cycle_planner = CyclePlanningCompiler()
    assignment_planner = AssignmentPlanningCompiler()
    report_replan_engine = ReportReplanEngine()

    bindings = build_industry_service_runtime_bindings(
        strategy_planning_compiler=strategy_planning_compiler,
        cycle_planner=cycle_planner,
        assignment_planner=assignment_planner,
        report_replan_engine=report_replan_engine,
    )

    assert bindings.strategy_planning_compiler is strategy_planning_compiler
    assert bindings.cycle_planner is cycle_planner
    assert bindings.assignment_planner is assignment_planner
    assert bindings.report_replan_engine is report_replan_engine


def test_build_runtime_bootstrap_assembles_domain_services_via_domain_builder(
    monkeypatch,
    tmp_path,
) -> None:
    calls: dict[str, object] = {}
    repositories = SimpleNamespace(
        work_context_repository=object(),
        industry_instance_repository=SimpleNamespace(list_instances=lambda limit=None: []),
        human_assist_task_repository=object(),
    )
    capability_service = SimpleNamespace(
        set_turn_executor=lambda value: calls.setdefault("turn_executor", value),
    )
    governance_service = SimpleNamespace(
        set_environment_service=lambda value: calls.setdefault("governance_environment_service", value),
        set_human_assist_task_service=lambda value: calls.setdefault(
            "governance_human_assist_task_service",
            value,
        ),
        set_industry_service=lambda value: calls.setdefault("governance_industry_service", value),
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
            "memory-activation-service",
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
            governance_service,
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
    def _fake_turn_executor(**kwargs):
        calls["turn_executor_kwargs"] = kwargs
        return "turn-executor"

    monkeypatch.setattr(runtime_service_graph_module, "KernelTurnExecutor", _fake_turn_executor)
    monkeypatch.setattr(
        runtime_service_graph_module,
        "RuntimeHealthService",
        lambda **kwargs: "runtime-health-service",
    )

    bootstrap = build_runtime_bootstrap(
        session_backend="session-backend",
        conversation_compaction_service="conversation-compaction-service",
        mcp_manager="mcp-manager",
    )

    assert calls["domain_builder_kwargs"]["work_context_service"] == "work-context-service"
    assert calls["domain_builder_kwargs"]["capability_service"] is capability_service
    assert calls["governance_environment_service"] == "environment-service"
    assert calls["governance_industry_service"] == "industry-service"
    assert (
        calls["domain_builder_kwargs"]["conversation_compaction_service"]
        == "conversation-compaction-service"
    )
    assert calls["turn_executor_kwargs"]["main_brain_chat_service"] == "main-brain-chat-service"
    assert calls["turn_executor_kwargs"]["main_brain_orchestrator"] == "main-brain-orchestrator"
    assert calls["turn_executor_kwargs"]["query_execution_service"] == "query-execution-service"
    assert (
        calls["turn_executor_kwargs"]["conversation_compaction_service"]
        == "conversation-compaction-service"
    )
    assert bootstrap.goal_service == "goal-service"
    assert bootstrap.memory_activation_service == "memory-activation-service"
    assert bootstrap.main_brain_orchestrator == "main-brain-orchestrator"
    assert bootstrap.turn_executor == "turn-executor"


def test_runtime_execution_contract_tracks_compaction_sidecar_instead_of_experience_memory() -> None:
    degraded = runtime_bootstrap_execution_module._build_runtime_contract(
        conversation_compaction_service=None,
    )
    available = runtime_bootstrap_execution_module._build_runtime_contract(
        conversation_compaction_service=object(),
    )

    assert degraded["sidecar_memory"]["status"] == "degraded"
    assert available["sidecar_memory"]["status"] == "available"
    assert degraded["runtime_entropy"]["status"] == "degraded"
    assert available["runtime_entropy"]["status"] == "available"
    assert degraded["runtime_entropy"]["sidecar_memory_status"] == "degraded"
    assert available["runtime_entropy"]["sidecar_memory_status"] == "available"
    assert degraded["runtime_entropy"]["carry_forward_contract"] == "canonical-state-only"
    assert available["runtime_entropy"]["carry_forward_contract"] == "private-compaction-sidecar"
    assert degraded["runtime_entropy"]["max_input_length"] > 0


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


def test_domain_builder_wires_environment_service_into_fixed_sop_service(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class _EnvironmentService(SimpleNamespace):
        def set_kernel_dispatcher(self, value) -> None:
            captured["environment_kernel_dispatcher"] = value

    class _ProviderManager(SimpleNamespace):
        @property
        def get_active_chat_model(self):
            return lambda *args, **kwargs: None

    environment_service = _EnvironmentService()
    provider_manager = _ProviderManager()

    class _RepoBag(SimpleNamespace):
        def __getattr__(self, name: str):
            value = object()
            setattr(self, name, value)
            return value

    class _CapabilityService:
        def __init__(self) -> None:
            self.discovery = SimpleNamespace(set_fixed_sop_service=lambda service: None)

        def set_goal_service(self, value) -> None:
            captured["goal_service"] = value

        def set_agent_profile_service(self, value) -> None:
            captured["agent_profile_service"] = value

        def set_industry_service(self, value) -> None:
            captured["industry_service"] = value

        def set_routine_service(self, value) -> None:
            captured["routine_service"] = value

        def set_fixed_sop_service(self, value) -> None:
            captured["fixed_sop_service"] = value

        def set_delegation_service(self, value) -> None:
            captured["delegation_service"] = value

        def set_actor_mailbox_service(self, value) -> None:
            captured["actor_mailbox_service"] = value

        def set_actor_supervisor(self, value) -> None:
            captured["actor_supervisor"] = value

        def get_discovery_service(self):
            return self.discovery

    class _StateQueryService:
        def set_goal_service(self, value) -> None:
            captured["state_query_goal_service"] = value

        def set_learning_service(self, value) -> None:
            captured["state_query_learning_service"] = value

        def set_agent_profile_service(self, value) -> None:
            captured["state_query_agent_profile_service"] = value

    class _AgentProfileService(SimpleNamespace):
        def backfill_industry_baseline_capabilities(self) -> None:
            captured["baseline_backfill"] = True

    class _GoalService(SimpleNamespace):
        def set_agent_profile_service(self, value) -> None:
            captured["goal_agent_profile_service"] = value

        def set_industry_service(self, value) -> None:
            captured["goal_industry_service"] = value

    class _DerivedMemoryIndexService(SimpleNamespace):
        def set_reporting_service(self, value) -> None:
            captured["derived_reporting_service"] = value

        def set_learning_service(self, value) -> None:
            captured["derived_learning_service"] = value

    class _MemoryReflectionService(SimpleNamespace):
        def set_learning_service(self, value) -> None:
            captured["reflection_learning_service"] = value

    class _IndustryService(SimpleNamespace):
        def set_prediction_service(self, value) -> None:
            captured["prediction_service"] = value

    class _LearningService(SimpleNamespace):
        def configure_bindings(self, value) -> None:
            captured["learning_bindings"] = value

    class _FixedSopService(SimpleNamespace):
        def __init__(self, **kwargs) -> None:
            super().__init__()
            captured["fixed_sop_init_kwargs"] = kwargs

        def set_routine_service(self, value) -> None:
            captured["fixed_sop_routine_service"] = value

    def _fake_goal_service(**kwargs):
        captured["goal_service_kwargs"] = kwargs
        return _GoalService()

    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "GoalService",
        _fake_goal_service,
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "AgentProfileService",
        lambda **kwargs: _AgentProfileService(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "StateReportingService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "OperatingLaneService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "BacklogService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "OperatingCycleService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "AssignmentService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "AgentReportService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "MediaService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "IndustryDraftGenerator",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "build_industry_service_runtime_bindings",
        lambda **kwargs: captured.setdefault("industry_runtime_bindings_kwargs", kwargs)
        or SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "IndustryService",
        lambda **kwargs: _IndustryService(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "WorkflowTemplateService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "FixedSopService",
        _FixedSopService,
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "RoutineService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "PredictionService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "TaskDelegationService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "KernelQueryExecutionService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "MainBrainChatService",
        lambda **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "MainBrainOrchestrator",
        lambda **kwargs: SimpleNamespace(),
    )

    runtime_bootstrap_domains_module.build_runtime_domain_services(
        session_backend=object(),
        conversation_compaction_service=object(),
        mcp_manager=object(),
        state_store=SQLiteStateStore(":memory:"),
        repositories=_RepoBag(),
        evidence_ledger=object(),
        environment_service=environment_service,
        runtime_event_bus=object(),
        provider_manager=provider_manager,
        state_query_service=_StateQueryService(),
        strategy_memory_service=object(),
        knowledge_service=object(),
        derived_memory_index_service=_DerivedMemoryIndexService(),
        memory_reflection_service=_MemoryReflectionService(),
        memory_recall_service=object(),
        memory_retain_service=object(),
        agent_experience_service=None,
        work_context_service=object(),
        learning_service=_LearningService(),
        capability_service=_CapabilityService(),
        kernel_dispatcher=object(),
        kernel_tool_bridge=object(),
        actor_mailbox_service=object(),
        actor_supervisor=object(),
    )

    assert captured["fixed_sop_init_kwargs"]["environment_service"] is environment_service
    assert captured["environment_kernel_dispatcher"] is not None
    assert "assignment_planner" in captured["goal_service_kwargs"]
    assert captured["goal_service_kwargs"]["assignment_planner"] is not None
    assert "strategy_planning_compiler" in captured["industry_runtime_bindings_kwargs"]
    assert captured["industry_runtime_bindings_kwargs"]["strategy_planning_compiler"] is not None
    assert "cycle_planner" in captured["industry_runtime_bindings_kwargs"]
    assert captured["industry_runtime_bindings_kwargs"]["cycle_planner"] is not None
    assert "assignment_planner" in captured["industry_runtime_bindings_kwargs"]
    assert captured["industry_runtime_bindings_kwargs"]["assignment_planner"] is not None
    assert "report_replan_engine" in captured["industry_runtime_bindings_kwargs"]
    assert captured["industry_runtime_bindings_kwargs"]["report_replan_engine"] is not None
