# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from copaw.app.runtime_events import RuntimeEventBus
from copaw.app.startup_recovery import (
    StartupRecoverySummary,
    _detect_requested_surfaces,
    run_startup_recovery,
)
from copaw.environments import EnvironmentRegistry, EnvironmentRepository, EnvironmentService, SessionMountRepository
from copaw.evidence import EvidenceLedger
from copaw.kernel import AbsorptionAction, AbsorptionCase, AbsorptionSummary, KernelConfig, KernelDispatcher, KernelTask, KernelTaskStore
from copaw.state import (
    AssignmentRecord,
    BacklogItemRecord,
    DecisionRequestRecord,
    GoalRecord,
    GoalOverrideRecord,
    HumanAssistTaskRecord,
    IndustryInstanceRecord,
    OperatingCycleRecord,
    SQLiteStateStore,
    ScheduleRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from copaw.state.human_assist_task_service import HumanAssistTaskService
from copaw.state.repositories import (
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteHumanAssistTaskRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingCycleRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


class _RecordingAbsorptionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def scan(self, *, runtimes, mailbox_items, human_assist_tasks, now):
        self.calls.append(
            {
                "runtime_count": len(list(runtimes)),
                "mailbox_count": len(list(mailbox_items)),
                "human_assist_count": len(list(human_assist_tasks)),
                "now": now,
            },
        )
        return AbsorptionSummary(
            active_cases=[
                AbsorptionCase(
                    case_kind="stale-lease",
                    owner_agent_id="ops-agent",
                    scope_ref="session:console:desktop-1",
                    recovery_rung="cleanup",
                ),
            ],
            case_counts={"stale-lease": 1},
            recovery_counts={"cleanup": 1},
            human_required_case_count=0,
            main_brain_summary="Main brain is absorbing internal execution pressure.",
        )


class _AbsorbingRecoveryService(_RecordingAbsorptionService):
    def __init__(self, action) -> None:
        super().__init__()
        self.action = action
        self.absorb_calls: list[dict[str, object]] = []

    def absorb(self, *, runtimes, mailbox_items, human_assist_tasks, now, **kwargs):
        self.absorb_calls.append(
            {
                "runtime_count": len(list(runtimes)),
                "mailbox_count": len(list(mailbox_items)),
                "human_assist_count": len(list(human_assist_tasks)),
                "now": now,
                "kwargs": dict(kwargs),
            },
        )
        return self.action


class _RuntimeRepository:
    def __init__(self, runtimes: list[object]) -> None:
        self._runtimes = list(runtimes)

    def list_runtimes(self, **_: object):
        return list(self._runtimes)


def _build_human_assist_service(tmp_path) -> HumanAssistTaskService:
    state_store = SQLiteStateStore(tmp_path / "human-assist-state.sqlite3")
    return HumanAssistTaskService(
        repository=SqliteHumanAssistTaskRepository(state_store),
        evidence_ledger=EvidenceLedger(database_path=tmp_path / "human-assist-evidence.sqlite3"),
    )


def test_startup_recovery_surface_detection_prefers_capability_layers() -> None:
    surfaces = _detect_requested_surfaces(
        "整理本地文件并处理桌面操作",
        metadata={
            "capability_layers": {
                "schema_version": "industry-seat-capability-layers-v1",
                "role_prototype_capability_ids": ["tool:read_file"],
                "seat_instance_capability_ids": ["tool:write_file"],
                "cycle_delta_capability_ids": ["tool:edit_file"],
                "session_overlay_capability_ids": ["mcp:desktop_windows"],
            },
            "environment_constraints": ["desktop", "workspace", "file-view"],
            "role_summary": "Handles local desktop work and governed file organization.",
        },
    )

    assert surfaces == ["file", "desktop"]


def test_startup_recovery_surface_detection_fails_closed_when_layers_are_malformed() -> None:
    surfaces = _detect_requested_surfaces(
        "打开浏览器并改本地文件",
        metadata={
            "capability_layers": {
                "schema_version": "industry-seat-capability-layers-v1",
                "role_prototype_capability_ids": "not-a-list",
            },
            "allowed_capabilities": ["mcp:browser", "tool:write_file"],
            "environment_constraints": ["browser", "desktop", "file-view"],
        },
    )

    assert surfaces == []


def test_startup_recovery_surface_detection_does_not_treat_legacy_allowed_capabilities_as_live_projection() -> None:
    surfaces = _detect_requested_surfaces(
        "打开桌面客户端并更新本地文件",
        metadata={
            "allowed_capabilities": [
                "mcp:desktop_windows",
                "tool:read_file",
                "tool:write_file",
                "tool:edit_file",
            ],
            "environment_constraints": ["desktop", "workspace", "file-view"],
            "role_summary": "Handles local desktop work and governed file organization.",
        },
    )

    assert surfaces == []


def test_startup_recovery_signature_and_summary_drop_retired_actor_recovery_fields() -> None:
    field_names = set(StartupRecoverySummary.model_fields)
    signature = inspect.signature(run_startup_recovery)

    assert "actor_mailbox_service" not in signature.parameters
    assert "reaped_expired_actor_leases" not in field_names
    assert "recovered_orphaned_actor_leases" not in field_names
    assert "recovered_orphaned_mailbox_items" not in field_names
    assert "requeued_orphaned_mailbox_items" not in field_names
    assert "blocked_orphaned_mailbox_items" not in field_names
    assert "resolved_orphaned_mailbox_items" not in field_names


def test_startup_recovery_recovers_session_orphans_and_expires_decisions(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_repository = SqliteDecisionRequestRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)

    session_repository = SessionMountRepository(state_store)
    environment_repository = EnvironmentRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=environment_repository,
            session_repository=session_repository,
        ),
        lease_ttl_seconds=120,
    )
    environment_service.set_session_repository(session_repository)

    lease = environment_service.acquire_session_lease(
        channel="console",
        session_id="sess-1",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=60,
        handle={"browser": "tab-1"},
    )

    recovered_environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=environment_repository,
            session_repository=session_repository,
        ),
        lease_ttl_seconds=120,
    )
    recovered_environment_service.set_session_repository(session_repository)

    event_bus = RuntimeEventBus()
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_repository,
        runtime_event_bus=event_bus,
    )
    dispatcher = KernelDispatcher(
        config=KernelConfig(decision_expiry_hours=72),
        task_store=task_store,
    )

    expired_task = KernelTask(
        id="task-expired",
        title="Expired approval",
        owner_agent_id="ops-agent",
        capability_ref="system:dispatch_goal",
        risk_level="confirm",
        phase="waiting-confirm",
    )
    pending_task = KernelTask(
        id="task-pending",
        title="Pending approval",
        owner_agent_id="ops-agent",
        capability_ref="system:dispatch_goal",
        risk_level="confirm",
        phase="waiting-confirm",
    )
    task_store.upsert(expired_task)
    task_store.upsert(pending_task)
    decision_repository.upsert_decision_request(
        DecisionRequestRecord(
            id="decision-expired",
            task_id=expired_task.id,
            decision_type="kernel-confirmation",
            risk_level="confirm",
            summary="Expired decision",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ),
    )
    decision_repository.upsert_decision_request(
        DecisionRequestRecord(
            id="decision-pending",
            task_id=pending_task.id,
            decision_type="kernel-confirmation",
            risk_level="confirm",
            summary="Pending decision",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
    )
    schedule_repository.upsert_schedule(
        ScheduleRecord(
            id="schedule-1",
            title="Morning review",
            cron="0 9 * * *",
            status="scheduled",
        ),
    )

    summary = run_startup_recovery(
        environment_service=recovered_environment_service,
        decision_request_repository=decision_repository,
        kernel_dispatcher=dispatcher,
        kernel_task_store=task_store,
        schedule_repository=schedule_repository,
        runtime_event_bus=event_bus,
        reason="startup",
    )

    assert summary.recovered_orphaned_leases == 1
    assert summary.expired_decisions == 1
    assert summary.pending_decisions == 1
    assert summary.hydrated_waiting_confirm_tasks == 1
    assert summary.active_schedules == 1

    recovered_session = session_repository.get_session(lease.id)
    assert recovered_session is not None
    assert recovered_session.lease_status == "expired"

    expired_decision = decision_repository.get_decision_request("decision-expired")
    assert expired_decision is not None
    assert expired_decision.status == "expired"

    events = event_bus.list_events(after_id=0, limit=20)
    assert any(event.event_name == "system.recovery" for event in events)


def test_startup_recovery_projects_absorption_summary_into_result(tmp_path) -> None:
    runtime_repository = _RuntimeRepository(
        [
            SimpleNamespace(
                agent_id="ops-agent",
                task_id="task-1",
                metadata={"environment_ref": "session:console:desktop-1"},
            ),
        ],
    )
    absorption_service = _RecordingAbsorptionService()

    summary = run_startup_recovery(
        environment_service=None,
        decision_request_repository=None,
        kernel_dispatcher=None,
        kernel_task_store=None,
        schedule_repository=None,
        runtime_repository=runtime_repository,
        exception_absorption_service=absorption_service,
        human_assist_task_service=None,
        reason="startup",
    )

    assert summary.absorption_case_count == 1
    assert summary.absorption_human_required_case_count == 0
    assert summary.absorption_case_counts == {"stale-lease": 1}
    assert summary.absorption_recovery_counts == {"cleanup": 1}
    assert "absorbing internal execution pressure" in summary.absorption_summary
    assert len(absorption_service.calls) == 1


def test_startup_recovery_materializes_exception_absorption_human_assist_when_continuity_anchor_exists(
    tmp_path,
) -> None:
    runtime_repository = _RuntimeRepository(
        [
            {
                "agent_id": "ops-agent",
                "task_id": "task-1",
                "assignment_id": "assignment-1",
                "industry_instance_id": "industry-1",
                "conversation_thread_id": "industry-chat:industry-1:execution-core",
                "work_context_id": "ctx-1",
                "metadata": {
                    "environment_ref": "session:console:desktop-1",
                    "profile_id": "profile-1",
                },
            },
        ],
    )
    action = AbsorptionAction(
        kind="human-assist",
        summary="Need a human to upload the receipt.",
        human_action_summary="Upload the receipt in chat.",
        human_action_contract={
            "title": "Upload receipt",
            "summary": "Receipt proof is still missing.",
            "required_action": "Upload the receipt in chat and confirm when done.",
            "resume_checkpoint_ref": "checkpoint:receipt-upload",
        },
        owner_agent_id="ops-agent",
        case_kind="stale-lease",
        scope_ref="task-1",
        recovery_rung="human",
    )
    absorption_service = _AbsorbingRecoveryService(action)
    human_assist_service = _build_human_assist_service(tmp_path)

    summary = run_startup_recovery(
        environment_service=None,
        decision_request_repository=None,
        kernel_dispatcher=None,
        kernel_task_store=None,
        schedule_repository=None,
        runtime_repository=runtime_repository,
        exception_absorption_service=absorption_service,
        human_assist_task_service=human_assist_service,
        reason="startup",
    )

    assert summary.absorption_action_kind == "human-assist"
    assert summary.absorption_action_materialized is True
    assert summary.absorption_human_task_id is not None
    task = human_assist_service.get_task(summary.absorption_human_task_id)
    assert task is not None
    assert task.chat_thread_id == "industry-chat:industry-1:execution-core"
    assert task.resume_checkpoint_ref == "checkpoint:receipt-upload"


def test_startup_recovery_does_not_requeue_legacy_execution_core_chat_writeback_gap_without_layers(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_repository = SqliteDecisionRequestRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    backlog_repository = SqliteBacklogItemRepository(state_store)
    assignment_repository = SqliteAssignmentRepository(state_store)
    goal_repository = SqliteGoalRepository(state_store)
    goal_override_repository = SqliteGoalOverrideRepository(state_store)
    operating_cycle_repository = SqliteOperatingCycleRepository(state_store)
    industry_repository = SqliteIndustryInstanceRepository(state_store)

    industry_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-1",
            label="测试行业",
            summary="测试恢复旧误路由任务",
            owner_scope="owner-1",
            current_cycle_id="cycle-legacy-gap",
        ),
    )
    goal_repository.upsert_goal(
        GoalRecord(
            id="goal-legacy-gap",
            title="整理桌面文件",
            summary="旧误路由执行目标",
            status="active",
            priority=3,
            owner_scope="owner-1",
            industry_instance_id="industry-1",
            cycle_id="cycle-legacy-gap",
            goal_class="cycle-goal",
        ),
    )
    operating_cycle_repository.upsert_cycle(
        OperatingCycleRecord(
            id="cycle-legacy-gap",
            industry_instance_id="industry-1",
            cycle_kind="daily",
            title="Legacy cycle",
            status="active",
            source_ref="industry-chat-writeback",
            backlog_item_ids=["backlog-legacy-gap"],
            assignment_ids=["assignment-legacy-gap"],
        ),
    )

    backlog_item = BacklogItemRecord(
        id="backlog-legacy-gap",
        industry_instance_id="industry-1",
        cycle_id="cycle-legacy-gap",
        goal_id="goal-legacy-gap",
        title="整理桌面文件",
        summary="把桌面的 text 文件整理到一个文件夹",
        status="materialized",
        priority=3,
        source_kind="operator",
        source_ref="chat-writeback:legacy-gap",
        metadata={
            "source": "chat-writeback",
            "industry_role_id": "execution-core",
            "owner_agent_id": "copaw-agent-runner",
            "goal_kind": "execution-core",
            "task_mode": "chat-writeback-followup",
            "chat_writeback_instruction": "请把电脑桌面的 text 文件整理到一个文件夹",
            "chat_writeback_classes": ["strategy", "backlog", "lane"],
            "chat_writeback_target_match_signals": [],
        },
    )
    backlog_repository.upsert_item(backlog_item)
    assignment_repository.upsert_assignment(
        AssignmentRecord(
            id="assignment-legacy-gap",
            industry_instance_id="industry-1",
            cycle_id="cycle-legacy-gap",
            backlog_item_id=backlog_item.id,
            goal_id="goal-legacy-gap",
            task_id="task-legacy-gap",
            owner_agent_id="copaw-agent-runner",
            owner_role_id="execution-core",
            title="整理桌面文件",
            summary="执行中枢误接了叶子执行任务",
            status="running",
            metadata={
                "source_kind": "operator",
                "source_ref": "chat-writeback:legacy-gap",
            },
        ),
    )
    backlog_repository.upsert_item(
        backlog_item.model_copy(update={"assignment_id": "assignment-legacy-gap"}),
    )
    goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id="goal-legacy-gap",
            status="active",
            reason="legacy chat writeback goal",
            compiler_context={
                "source": "chat-writeback",
                "backlog_item_id": backlog_item.id,
                "industry_role_id": "execution-core",
            },
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-legacy-gap",
            goal_id="goal-legacy-gap",
            title="整理桌面文件",
            summary="旧 execution-core 叶子执行任务",
            task_type="agent",
            status="running",
            priority=3,
            owner_agent_id="copaw-agent-runner",
            industry_instance_id="industry-1",
            cycle_id="cycle-legacy-gap",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-legacy-gap",
            runtime_status="active",
            current_phase="executing",
            risk_level="guarded",
            last_owner_agent_id="copaw-agent-runner",
        ),
    )

    summary = run_startup_recovery(
        environment_service=None,
        decision_request_repository=decision_repository,
        kernel_dispatcher=None,
        kernel_task_store=None,
        schedule_repository=schedule_repository,
        backlog_item_repository=backlog_repository,
        assignment_repository=assignment_repository,
        goal_repository=goal_repository,
        goal_override_repository=goal_override_repository,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        reason="startup",
    )

    assert summary.recovered_legacy_chat_writebacks == 0
    refreshed_backlog = backlog_repository.get_item(backlog_item.id)
    assert refreshed_backlog is not None
    assert refreshed_backlog.status == "materialized"
    assert "chat_writeback_requested_surfaces" not in refreshed_backlog.metadata
