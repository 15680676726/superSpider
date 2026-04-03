# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from copaw.app import runtime_bootstrap_domains as runtime_bootstrap_domains_module
from copaw.industry import IndustryService
from copaw.industry.bootstrap_service import IndustryBootstrapService
from copaw.industry.team_service import IndustryTeamService
from copaw.industry.view_service import IndustryViewService
from copaw.industry.service_context import (
    IndustryServiceRuntimeBindings,
    build_industry_service_runtime_bindings,
)
from copaw.state import (
    AgentRuntimeRecord,
    GoalRecord,
    IndustryInstanceRecord,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
)
from copaw.state.repositories import (
    SqliteAgentProfileOverrideRepository,
    SqliteAgentReportRepository,
    SqliteAgentRuntimeRepository,
    SqliteGoalOverrideRepository,
    SqliteIndustryInstanceRepository,
    SqliteTaskRepository,
)
from copaw.industry.models import IndustryRoleBlueprint


class _DummyGoalService:
    def set_industry_service(self, industry_service) -> None:
        self.industry_service = industry_service


class _MemoryRetainSpy:
    def __init__(self) -> None:
        self.reports = []

    def retain_agent_report(self, report) -> None:
        self.reports.append(report)


class _DispatchGoalService(_DummyGoalService):
    def __init__(self) -> None:
        self.dispatched: list[dict[str, object]] = []

    async def compile_goal_dispatch(
        self,
        goal_id: str,
        *,
        context,
        owner_agent_id=None,
        activate=True,
    ):
        self.dispatched.append(
            {
                "goal_id": goal_id,
                "context": context,
                "owner_agent_id": owner_agent_id,
                "execute": False,
                "activate": activate,
            },
        )
        return {
            "goal_id": goal_id,
            "context": context,
        }

    async def dispatch_goal_execute_now(
        self,
        goal_id: str,
        *,
        context,
        owner_agent_id=None,
        activate=True,
    ):
        self.dispatched.append(
            {
                "goal_id": goal_id,
                "context": context,
                "owner_agent_id": owner_agent_id,
                "execute": True,
                "activate": activate,
            },
        )
        return {
            "goal_id": goal_id,
            "context": context,
        }

    async def dispatch_goal_background(
        self,
        goal_id: str,
        *,
        context,
        owner_agent_id=None,
        activate=True,
    ):
        self.dispatched.append(
            {
                "goal_id": goal_id,
                "context": context,
                "owner_agent_id": owner_agent_id,
                "execute": True,
                "background": True,
                "activate": activate,
            },
        )
        return {
            "goal_id": goal_id,
            "context": context,
            "dispatch_results": [{"task_id": "task-1", "scheduled_execution": True}],
        }

    def release_deferred_goal_dispatch(self, *, goal_id: str, dispatch_results):
        self.released = {"goal_id": goal_id, "dispatch_results": list(dispatch_results or [])}


@dataclass
class _MailboxItem:
    id: str


class _MailboxRepositorySpy:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def list_items(
        self,
        *,
        agent_id: str | None = None,
        conversation_thread_id: str | None = None,
        limit=None,
    ) -> list[_MailboxItem]:
        if agent_id == "agent-1":
            return [_MailboxItem(id="mailbox-agent")]
        if conversation_thread_id == "thread-1":
            return [_MailboxItem(id="mailbox-thread")]
        return []

    def delete_item(self, item_id: str) -> bool:
        self.deleted.append(item_id)
        return True


def test_industry_service_explicit_runtime_bindings_wire_memory_retain_service(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(state_store)
    memory_retain = _MemoryRetainSpy()
    industry_instance_repository = SqliteIndustryInstanceRepository(state_store)
    agent_report_repository = SqliteAgentReportRepository(state_store)
    runtime_bindings = build_industry_service_runtime_bindings(
        agent_report_repository=agent_report_repository,
        memory_retain_service=memory_retain,
    )
    industry_service = IndustryService(
        goal_service=_DummyGoalService(),
        industry_instance_repository=industry_instance_repository,
        goal_override_repository=SqliteGoalOverrideRepository(state_store),
        agent_profile_override_repository=SqliteAgentProfileOverrideRepository(
            state_store,
        ),
        state_store=state_store,
        memory_retain_service=memory_retain,
        runtime_bindings=runtime_bindings,
    )

    assert industry_service._agent_report_service is not None

    industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-acme",
            label="Acme Industry",
            owner_scope="industry-v1-acme",
        ),
    )

    task = task_repository.upsert_task(
        TaskRecord(
            id="task-terminal-1",
            title="Close task",
            summary="Finish the operating loop.",
            task_type="agent",
            status="completed",
            owner_agent_id="industry-solution-lead",
            industry_instance_id="industry-v1-acme",
        ),
    )

    report = industry_service._agent_report_service.record_task_terminal_report(
        task=task,
        runtime=TaskRuntimeRecord(
            task_id="task-terminal-1",
            current_phase="completed",
            last_result_summary="Task completed successfully.",
        ),
        assignment=None,
        evidence_ids=["evidence-1"],
        decision_ids=["decision-1"],
        owner_role_id="solution-lead",
    )

    assert report is not None
    assert [item.id for item in memory_retain.reports] == [report.id]


def test_industry_service_runtime_bindings_wire_memory_activation_service(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    memory_activation_service = object()

    runtime_bindings = build_industry_service_runtime_bindings(
        memory_activation_service=memory_activation_service,
    )
    industry_service = IndustryService(
        goal_service=_DummyGoalService(),
        industry_instance_repository=SqliteIndustryInstanceRepository(state_store),
        goal_override_repository=SqliteGoalOverrideRepository(state_store),
        agent_profile_override_repository=SqliteAgentProfileOverrideRepository(
            state_store,
        ),
        runtime_bindings=runtime_bindings,
    )

    assert runtime_bindings.memory_activation_service is memory_activation_service
    assert industry_service._memory_activation_service is memory_activation_service


def test_runtime_domain_builder_passes_memory_activation_service_to_industry_service(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    memory_activation_service = object()

    class _EnvironmentService(SimpleNamespace):
        def set_kernel_dispatcher(self, value) -> None:
            captured["environment_kernel_dispatcher"] = value

    class _ProviderManager(SimpleNamespace):
        @property
        def get_active_chat_model(self):
            return lambda *args, **kwargs: None

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

    class _DerivedMemoryIndexService(SimpleNamespace):
        def set_reporting_service(self, value) -> None:
            captured["derived_reporting_service"] = value

        def set_learning_service(self, value) -> None:
            captured["derived_learning_service"] = value

    class _MemoryReflectionService(SimpleNamespace):
        def set_learning_service(self, value) -> None:
            captured["reflection_learning_service"] = value

    class _IndustryService(SimpleNamespace):
        def __init__(self, **kwargs) -> None:
            super().__init__()
            captured["industry_service_init_kwargs"] = kwargs
            self._memory_activation_service = kwargs.get("memory_activation_service")

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

    monkeypatch.setattr(
        runtime_bootstrap_domains_module,
        "GoalService",
        lambda **kwargs: _GoalService(),
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
        _IndustryService,
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

    domain_services = runtime_bootstrap_domains_module.build_runtime_domain_services(
        session_backend=object(),
        conversation_compaction_service=object(),
        mcp_manager=object(),
        state_store=SQLiteStateStore(":memory:"),
        repositories=_RepoBag(),
        evidence_ledger=object(),
        environment_service=_EnvironmentService(),
        runtime_event_bus=object(),
        provider_manager=_ProviderManager(),
        state_query_service=_StateQueryService(),
        strategy_memory_service=object(),
        knowledge_service=object(),
        derived_memory_index_service=_DerivedMemoryIndexService(),
        memory_reflection_service=_MemoryReflectionService(),
        memory_recall_service=object(),
        memory_retain_service=object(),
        memory_activation_service=memory_activation_service,
        agent_experience_service=None,
        work_context_service=object(),
        learning_service=_LearningService(),
        capability_service=_CapabilityService(),
        kernel_dispatcher=object(),
        kernel_tool_bridge=object(),
        actor_mailbox_service=object(),
        actor_supervisor=object(),
    )

    assert (
        captured["industry_runtime_bindings_kwargs"]["memory_activation_service"]
        is memory_activation_service
    )
    assert (
        captured["industry_service_init_kwargs"]["memory_activation_service"]
        is memory_activation_service
    )
    assert domain_services.industry_service._memory_activation_service is memory_activation_service


def test_industry_service_does_not_fabricate_runtime_bindings_from_state_store(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    memory_retain = _MemoryRetainSpy()
    industry_service = IndustryService(
        goal_service=_DummyGoalService(),
        industry_instance_repository=SqliteIndustryInstanceRepository(state_store),
        goal_override_repository=SqliteGoalOverrideRepository(state_store),
        agent_profile_override_repository=SqliteAgentProfileOverrideRepository(
            state_store,
        ),
        state_store=state_store,
        memory_retain_service=memory_retain,
    )

    assert industry_service._operating_lane_repository is None
    assert industry_service._backlog_item_repository is None
    assert industry_service._operating_cycle_repository is None
    assert industry_service._assignment_repository is None
    assert industry_service._agent_report_repository is None
    assert industry_service._agent_report_service is None
    assert industry_service._get_browser_runtime_service() is None


def test_runtime_bindings_builder_does_not_fabricate_from_state_store(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")

    runtime_bindings = build_industry_service_runtime_bindings(
        state_store=state_store,
    )

    assert runtime_bindings.operating_lane_repository is None
    assert runtime_bindings.backlog_item_repository is None
    assert runtime_bindings.operating_cycle_repository is None
    assert runtime_bindings.assignment_repository is None
    assert runtime_bindings.agent_report_repository is None
    assert runtime_bindings.agent_runtime_repository is None
    assert runtime_bindings.agent_thread_binding_repository is None
    assert runtime_bindings.schedule_repository is None
    assert runtime_bindings.agent_mailbox_repository is None
    assert runtime_bindings.agent_checkpoint_repository is None
    assert runtime_bindings.agent_lease_repository is None
    assert runtime_bindings.strategy_memory_repository is None
    assert runtime_bindings.workflow_run_repository is None
    assert runtime_bindings.prediction_case_repository is None
    assert runtime_bindings.prediction_scenario_repository is None
    assert runtime_bindings.prediction_signal_repository is None
    assert runtime_bindings.prediction_recommendation_repository is None
    assert runtime_bindings.prediction_review_repository is None
    assert runtime_bindings.operating_lane_service is None
    assert runtime_bindings.backlog_service is None
    assert runtime_bindings.operating_cycle_service is None
    assert runtime_bindings.assignment_service is None
    assert runtime_bindings.agent_report_service is None
    assert runtime_bindings.browser_runtime_service is None


def test_industry_service_does_not_recreate_missing_view_delegate(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    industry_service = IndustryService(
        goal_service=_DummyGoalService(),
        industry_instance_repository=SqliteIndustryInstanceRepository(state_store),
        goal_override_repository=SqliteGoalOverrideRepository(state_store),
        agent_profile_override_repository=SqliteAgentProfileOverrideRepository(
            state_store,
        ),
    )
    industry_service._view_service = None

    with pytest.raises(AttributeError):
        industry_service.list_instances()


def test_industry_view_service_owns_read_model_logic_without_lifecycle_mixin(
    monkeypatch,
) -> None:
    record = SimpleNamespace(instance_id="industry-1", status="active")
    updated_at = datetime(2026, 3, 26, 8, 0, tzinfo=timezone.utc)
    summary = SimpleNamespace(
        instance_id="industry-1",
        status="active",
        updated_at=updated_at,
        stats={
            "agent_count": 3,
            "lane_count": 5,
            "backlog_count": 6,
            "cycle_count": 1,
            "assignment_count": 7,
            "report_count": 2,
            "schedule_count": 4,
        },
    )
    detail = {"instance_id": "industry-1", "stats": {"lane_count": 5}}
    facade = SimpleNamespace(
        _industry_instance_repository=SimpleNamespace(
            list_instances=lambda status=None, limit=None: [record],
            get_instance=lambda instance_id: record if instance_id == "industry-1" else None,
        ),
        _reconcile_kickoff_autonomy_status=lambda value: value,
        _derive_instance_status=lambda value: "active",
        _build_instance_summary=lambda value: summary if value is record else None,
        _build_instance_detail=lambda value: detail if value is record else None,
    )
    view_service = IndustryViewService(facade)

    monkeypatch.setattr(
        "copaw.industry.view_service._IndustryLifecycleMixin.list_instances",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("view service should own list logic"),
        ),
    )
    monkeypatch.setattr(
        "copaw.industry.view_service._IndustryLifecycleMixin.get_instance_detail",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("view service should own detail logic"),
        ),
    )
    monkeypatch.setattr(
        "copaw.industry.view_service.IndustryViewService.reconcile_instance_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("public read surfaces must not invoke reconcile"),
        ),
    )

    summaries = view_service.list_instances(status="active", limit=None)

    assert summaries == [summary]
    assert view_service.get_instance_detail("industry-1") is detail


def test_industry_service_cleanup_uses_injected_mailbox_repository_without_state_store(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    mailbox_repository = _MailboxRepositorySpy()
    industry_service = IndustryService(
        goal_service=_DummyGoalService(),
        industry_instance_repository=SqliteIndustryInstanceRepository(state_store),
        goal_override_repository=SqliteGoalOverrideRepository(state_store),
        agent_profile_override_repository=SqliteAgentProfileOverrideRepository(
            state_store,
        ),
        runtime_bindings=IndustryServiceRuntimeBindings(
            agent_mailbox_repository=mailbox_repository,
        ),
    )

    deleted = industry_service._delete_instance_mailbox_items(
        agent_ids=["agent-1"],
        thread_ids=["thread-1"],
    )

    assert deleted == 2
    assert sorted(mailbox_repository.deleted) == ["mailbox-agent", "mailbox-thread"]


def test_reconcile_instance_status_for_goal_uses_targeted_goal_lookup(
    tmp_path,
    monkeypatch,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteIndustryInstanceRepository(state_store)
    industry_service = IndustryService(
        goal_service=_DummyGoalService(),
        industry_instance_repository=repository,
        goal_override_repository=SqliteGoalOverrideRepository(state_store),
        agent_profile_override_repository=SqliteAgentProfileOverrideRepository(
            state_store,
        ),
    )
    record = repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-demo",
            label="Demo Industry",
            owner_scope="industry-demo",
            goal_ids=["goal-demo"],
        ),
    )

    monkeypatch.setattr(
        repository,
        "list_instances",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("global instance scan is not allowed"),
        ),
    )
    monkeypatch.setattr(
        repository,
        "list_instances_for_goal",
        lambda goal_id: [record] if goal_id == "goal-demo" else [],
        raising=False,
    )
    monkeypatch.setattr(
        industry_service,
        "_current_operating_cycle_record",
        lambda instance_id: None,
    )
    monkeypatch.setattr(
        industry_service,
        "_ensure_terminal_agent_reports",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        industry_service,
        "_process_pending_agent_reports",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        industry_service,
        "_retire_completed_temporary_roles",
        lambda record: record,
    )
    monkeypatch.setattr(
        industry_service,
        "reconcile_instance_status",
        lambda instance_id: record if instance_id == record.instance_id else None,
    )
    monkeypatch.setattr(
        industry_service,
        "_sync_role_runtime_surfaces_for_record",
        lambda record: None,
    )
    monkeypatch.setattr(
        industry_service,
        "_sync_strategy_memory_for_instance",
        lambda record: None,
    )

    industry_service.reconcile_instance_status_for_goal("goal-demo")


def test_kickoff_execution_from_chat_records_trigger_message_context(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    goal_service = _DispatchGoalService()
    industry_instance_repository = SqliteIndustryInstanceRepository(state_store)
    industry_service = IndustryService(
        goal_service=goal_service,
        industry_instance_repository=industry_instance_repository,
        goal_override_repository=SqliteGoalOverrideRepository(state_store),
        agent_profile_override_repository=SqliteAgentProfileOverrideRepository(
            state_store,
        ),
    )
    industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-demo",
            label="Demo Industry",
            owner_scope="industry-demo",
            status="active",
        ),
    )
    goal = GoalRecord(
        id="goal-demo",
        title="Launch execution",
        summary="Kick off the execution stage.",
        status="active",
        priority=3,
        owner_scope="industry-demo",
    )

    industry_service._list_pending_chat_kickoff_goals = lambda record, team=None: [
        (goal, None)
    ]
    industry_service._list_pending_chat_kickoff_schedule_ids = (
        lambda instance_id, schedule_ids: []
    )
    industry_service._resolve_goal_kickoff_stage = (
        lambda goal, override, record, team=None: "execution"
    )
    industry_service._resolve_goal_runtime_context = (
        lambda goal, override, record, team=None: {}
    )
    industry_service._current_operating_cycle_record = lambda instance_id: None
    industry_service._list_assignment_records = lambda *args, **kwargs: []

    async def _resume_schedules(**kwargs):
        return []

    industry_service._resume_instance_schedules = _resume_schedules

    result = asyncio.run(
        industry_service.kickoff_execution_from_chat(
            industry_instance_id="industry-demo",
            message_text="继续推进这个目标",
            owner_agent_id="operator-1",
            session_id="session-1",
            channel="copaw-chat",
        ),
    )

    assert result is not None
    assert goal_service.dispatched[0]["context"]["trigger_message_text"] == "继续推进这个目标"
    assert goal_service.dispatched[0]["context"]["trigger_session_id"] == "session-1"
    assert goal_service.dispatched[0]["context"]["trigger_channel"] == "copaw-chat"


@pytest.mark.asyncio
async def test_bootstrap_service_preview_does_not_delegate_back_to_lifecycle(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "copaw.industry.service_lifecycle._IndustryLifecycleMixin.preview_v1",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("bootstrap preview should not call lifecycle mixin"),
        ),
    )
    monkeypatch.setattr(
        "copaw.industry.bootstrap_service.IndustryPreviewResponse",
        lambda **kwargs: {"preview_payload": kwargs},
        raising=False,
    )

    plan = SimpleNamespace(
        profile={"industry": "demo"},
        draft={"team": "draft"},
        recommendation_pack={"pack": "r1"},
        readiness_checks=[
            SimpleNamespace(required=True, status="ready"),
            SimpleNamespace(required=False, status="missing"),
        ],
        media_analyses=[{"id": "m1"}],
        media_warnings=["warn"],
    )

    async def _prepare_preview(_request):
        return plan

    facade = SimpleNamespace(_prepare_preview=_prepare_preview)
    service = IndustryBootstrapService(facade)

    response = await service.preview_v1(SimpleNamespace())

    assert response["preview_payload"]["profile"] == plan.profile
    assert response["preview_payload"]["can_activate"] is True
    assert response["preview_payload"]["media_warnings"] == ["warn"]


@pytest.mark.asyncio
async def test_bootstrap_service_bootstrap_does_not_delegate_back_to_lifecycle(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "copaw.industry.service_lifecycle._IndustryLifecycleMixin.bootstrap_v1",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("bootstrap activate should not call lifecycle mixin"),
        ),
    )

    captured: dict[str, object] = {}

    async def _prepare_bootstrap(_request):
        return "prepared-plan"

    def _public_bootstrap_activation_flags(_request):
        return (
            {
                "auto_activate": True,
                "auto_dispatch": True,
                "execute": False,
            },
            True,
        )

    async def _activate_plan(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    request = SimpleNamespace(
        auto_activate=True,
        goal_priority=5,
        install_plan=["pkg-1"],
    )
    facade = SimpleNamespace(
        _prepare_bootstrap=_prepare_bootstrap,
        _public_bootstrap_activation_flags=_public_bootstrap_activation_flags,
        _activate_plan=_activate_plan,
    )
    service = IndustryBootstrapService(facade)

    result = await service.bootstrap_v1(request)

    assert result == {"ok": True}
    assert captured["plan"] == "prepared-plan"
    assert captured["auto_activate"] is True
    assert captured["auto_dispatch"] is True
    assert captured["execute"] is False
    assert captured["goal_priority"] == 5
    assert captured["install_plan"] == ["pkg-1"]
    assert captured["auto_start_learning"] is True


@pytest.mark.asyncio
async def test_team_service_update_does_not_delegate_back_to_lifecycle(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "copaw.industry.service_lifecycle._IndustryLifecycleMixin.update_instance_team",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("team update should not call lifecycle mixin"),
        ),
    )

    captured: dict[str, object] = {}

    async def _prepare_team_update(*, instance_id, request):
        captured["prepared"] = (instance_id, request)
        return "team-plan"

    async def _activate_plan(**kwargs):
        captured.update(kwargs)
        return {"updated": True}

    request = SimpleNamespace(
        auto_activate=False,
        auto_dispatch=False,
        execute=True,
        goal_priority=7,
        install_plan=["pkg-a"],
    )
    facade = SimpleNamespace(
        get_instance_detail=lambda _instance_id: {"detail": True},
        _default_team_update_flags=lambda _detail: {
            "auto_activate": True,
            "auto_dispatch": False,
            "execute": True,
        },
        _prepare_team_update=_prepare_team_update,
        _activate_plan=_activate_plan,
    )
    service = IndustryTeamService(facade)

    result = await service.update_instance_team(
        "industry-demo",
        request,
        public_contract=True,
    )

    assert result == {"updated": True}
    assert captured["prepared"] == ("industry-demo", request)
    assert captured["plan"] == "team-plan"
    assert captured["auto_activate"] is True
    assert captured["auto_dispatch"] is False
    assert captured["execute"] is True
    assert captured["goal_priority"] == 7
    assert captured["install_plan"] == ["pkg-a"]


def test_industry_service_syncs_formal_capability_layers_into_actor_runtime(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "industry-runtime-capability-layers.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-support",
            actor_key="industry-1:support-specialist",
            actor_fingerprint="fingerprint-old",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            metadata={
                "capability_layers": {
                    "schema_version": "industry-seat-capability-layers-v1",
                    "role_prototype_capability_ids": ["tool:read_file"],
                    "seat_instance_capability_ids": ["skill:crm-seat-playbook"],
                    "cycle_delta_capability_ids": ["mcp:campaign-dashboard"],
                    "session_overlay_capability_ids": ["mcp:browser-temp"],
                    "effective_capability_ids": [
                        "tool:read_file",
                        "skill:crm-seat-playbook",
                        "mcp:campaign-dashboard",
                        "mcp:browser-temp",
                    ],
                },
            },
        ),
    )
    runtime_bindings = build_industry_service_runtime_bindings(
        agent_runtime_repository=runtime_repository,
    )
    industry_service = IndustryService(
        goal_service=_DummyGoalService(),
        industry_instance_repository=SqliteIndustryInstanceRepository(state_store),
        goal_override_repository=SqliteGoalOverrideRepository(state_store),
        agent_profile_override_repository=SqliteAgentProfileOverrideRepository(
            state_store,
        ),
        runtime_bindings=runtime_bindings,
    )
    role = IndustryRoleBlueprint(
        role_id="support-specialist",
        agent_id="agent-support",
        name="Support Specialist",
        role_name="Support Specialist",
        role_summary="Handle support and follow-up work.",
        mission="Close support work with the correct capability pack.",
        goal_kind="support-specialist",
        allowed_capabilities=["tool:read_file", "mcp:salesforce"],
    )

    industry_service._sync_actor_runtime_surface(  # pylint: disable=protected-access
        agent=role,
        instance_id="industry-1",
        owner_scope="industry:industry-1",
        goal_id=None,
        goal_title=None,
        status="waiting",
        assignment_id="assignment-1",
        assignment_title="Handle support follow-up",
        assignment_summary="Review the support queue and prepare the next action.",
        assignment_status="queued",
    )

    runtime = runtime_repository.get_runtime("agent-support")
    assert runtime is not None
    assert runtime.metadata["capability_layers"] == {
        "schema_version": "industry-seat-capability-layers-v1",
        "role_prototype_capability_ids": ["tool:read_file", "mcp:salesforce"],
        "seat_instance_capability_ids": ["skill:crm-seat-playbook"],
        "cycle_delta_capability_ids": ["mcp:campaign-dashboard"],
        "session_overlay_capability_ids": ["mcp:browser-temp"],
        "effective_capability_ids": [
            "tool:read_file",
            "mcp:salesforce",
            "skill:crm-seat-playbook",
            "mcp:campaign-dashboard",
            "mcp:browser-temp",
        ],
    }
