from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

import copaw.app._app as app_module
from copaw.app import runtime_lifecycle as runtime_lifecycle_module
from copaw.app.crons.heartbeat import run_heartbeat_once
from copaw.app.runtime_bootstrap_repositories import build_runtime_repositories
from copaw.app.runtime_lifecycle import (
    RuntimeRestartCoordinator,
    _reap_stale_kernel_tasks,
    _should_run_host_recovery,
    _should_run_operating_cycle,
    _should_run_learning_strategy,
    automation_interval_seconds,
    start_automation_tasks,
    stop_automation_tasks,
    submit_kernel_automation_task,
)
from copaw.state import AutomationLoopRuntimeRecord, SQLiteStateStore


def test_automation_interval_seconds_uses_default_for_invalid_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COPAW_TEST_INTERVAL", "bad")

    value = automation_interval_seconds("COPAW_TEST_INTERVAL", 123)

    assert value == 123


def test_automation_interval_seconds_enforces_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COPAW_TEST_INTERVAL", "5")

    value = automation_interval_seconds("COPAW_TEST_INTERVAL", 123)

    assert value == 30


def test_automation_loop_state_persists_formal_result_anchors(tmp_path) -> None:
    repositories = build_runtime_repositories(SQLiteStateStore(tmp_path / "state.db"))
    loop_state = runtime_lifecycle_module._AutomationLoopState(
        task_name="operating-cycle",
        capability_ref="system:run_operating_cycle",
        owner_agent_id="copaw-main-brain",
        interval_seconds=180,
        automation_task_id="copaw-main-brain:operating-cycle:system:run_operating_cycle",
        automation_loop_runtime_repository=repositories.automation_loop_runtime_repository,
    )
    loop_state.persist()

    loop_state.record_result(
        SimpleNamespace(
            phase="completed",
            summary="Operating cycle completed with fresh evidence.",
            task_id="task-auto-1",
            evidence_id="evidence-auto-1",
        ),
    )

    record = repositories.automation_loop_runtime_repository.get_loop(
        "copaw-main-brain:operating-cycle:system:run_operating_cycle",
    )

    assert record is not None
    assert record.last_task_id == "task-auto-1"
    assert record.last_evidence_id == "evidence-auto-1"
    assert (
        record.last_result_summary
        == "Operating cycle completed with fresh evidence."
    )


@pytest.mark.asyncio
async def test_start_automation_tasks_creates_named_tasks() -> None:
    tasks = start_automation_tasks(
        kernel_dispatcher=SimpleNamespace(),
        capability_service=SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        logger=logging.getLogger(__name__),
    )

    assert {task.get_name() for task in tasks} == {
        "copaw-automation-host-recovery",
        "copaw-automation-operating-cycle",
        "copaw-automation-learning-strategy",
    }

    await stop_automation_tasks(tasks)

    assert all(task.done() for task in tasks)


@pytest.mark.asyncio
async def test_start_automation_tasks_exposes_durable_loop_contract_snapshots() -> None:
    tasks = start_automation_tasks(
        kernel_dispatcher=SimpleNamespace(),
        capability_service=SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        logger=logging.getLogger(__name__),
    )

    try:
        snapshots = tasks.loop_snapshots()
    finally:
        await stop_automation_tasks(tasks)

    assert set(snapshots) == {
        "host-recovery",
        "operating-cycle",
        "learning-strategy",
    }
    assert snapshots["operating-cycle"] == {
        "task_name": "operating-cycle",
        "capability_ref": "system:run_operating_cycle",
        "owner_agent_id": "copaw-main-brain",
        "interval_seconds": 180,
        "automation_task_id": (
            "copaw-main-brain:operating-cycle:system:run_operating_cycle"
        ),
        "coordinator_contract": "automation-coordinator/v1",
        "loop_phase": "idle",
        "health_status": "idle",
        "last_gate_reason": "not-yet-evaluated",
        "last_result_phase": None,
        "last_result_summary": None,
        "last_error_summary": None,
        "last_task_id": None,
        "last_evidence_id": None,
        "submit_count": 0,
        "consecutive_failures": 0,
    }


@pytest.mark.asyncio
async def test_start_automation_tasks_rehydrates_persisted_loop_state(
    tmp_path,
) -> None:
    repositories = build_runtime_repositories(SQLiteStateStore(tmp_path / "state.db"))
    repositories.automation_loop_runtime_repository.upsert_loop(
        AutomationLoopRuntimeRecord(
            automation_task_id=(
                "copaw-main-brain:operating-cycle:system:run_operating_cycle"
            ),
            task_name="operating-cycle",
            capability_ref="system:run_operating_cycle",
            owner_agent_id="copaw-main-brain",
            interval_seconds=180,
            coordinator_contract="automation-coordinator/v1",
            loop_phase="failed",
            health_status="degraded",
            last_gate_reason="active-industry",
            last_result_phase="failed",
            last_error_summary="planner timeout",
            submit_count=3,
            consecutive_failures=2,
        ),
    )

    tasks = start_automation_tasks(
        kernel_dispatcher=SimpleNamespace(),
        capability_service=SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        automation_loop_runtime_repository=repositories.automation_loop_runtime_repository,
        logger=logging.getLogger(__name__),
    )

    try:
        snapshots = tasks.loop_snapshots()
    finally:
        await stop_automation_tasks(tasks)

    assert snapshots["operating-cycle"]["loop_phase"] == "failed"
    assert snapshots["operating-cycle"]["health_status"] == "degraded"
    assert snapshots["operating-cycle"]["last_error_summary"] == "planner timeout"
    assert snapshots["operating-cycle"]["submit_count"] == 3
    assert snapshots["operating-cycle"]["consecutive_failures"] == 2


@pytest.mark.asyncio
async def test_start_automation_tasks_tracks_blocked_and_submitting_loop_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submissions: list[dict[str, object]] = []
    submitted = asyncio.Event()

    async def _record_submit(
        dispatcher,
        capability_service,
        *,
        capability_ref,
        title,
        owner_agent_id,
        payload,
    ):
        _ = dispatcher
        _ = capability_service
        submissions.append(
            {
                "capability_ref": capability_ref,
                "title": title,
                "owner_agent_id": owner_agent_id,
                "payload": dict(payload),
            },
        )
        submitted.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        runtime_lifecycle_module,
        "automation_interval_seconds",
        lambda *_args, **_kwargs: 0,
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "submit_kernel_automation_task",
        _record_submit,
    )

    tasks = start_automation_tasks(
        kernel_dispatcher=SimpleNamespace(),
        capability_service=SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        environment_service=SimpleNamespace(
            should_run_host_recovery=lambda **_kwargs: (
                False,
                "no-actionable-host-events",
            ),
        ),
        industry_service=SimpleNamespace(
            should_run_operating_cycle=lambda: (True, "active-industry"),
        ),
        learning_service=SimpleNamespace(
            should_run_strategy_cycle=lambda **_kwargs: (
                False,
                "no-actionable-failure-pattern",
            ),
        ),
        logger=logging.getLogger(__name__),
    )

    try:
        await asyncio.wait_for(submitted.wait(), timeout=0.2)
        snapshots = tasks.loop_snapshots()
    finally:
        await stop_automation_tasks(tasks)

    assert submissions == [
        {
            "capability_ref": "system:run_operating_cycle",
            "title": "Automation: operating-cycle",
            "owner_agent_id": "copaw-main-brain",
            "payload": {
                "actor": "system:automation",
                "source": "automation:operating_cycle",
                "force": False,
                "entry_source": "automation-loop",
                "automation_task_id": (
                    "copaw-main-brain:operating-cycle:system:run_operating_cycle"
                ),
                "coordinator_contract": "automation-coordinator/v1",
                "automation_loop_name": "operating-cycle",
                "durable_coordinator_contract": "durable-runtime-coordinator/v1",
                "durable_coordinator_entrypoint": "automation-loop",
                "durable_coordinator_id": (
                    "copaw-main-brain:operating-cycle:system:run_operating_cycle"
                ),
            },
        },
    ]
    assert snapshots["host-recovery"]["loop_phase"] == "blocked"
    assert snapshots["host-recovery"]["health_status"] == "idle"
    assert snapshots["host-recovery"]["last_gate_reason"] == "no-actionable-host-events"
    assert snapshots["operating-cycle"]["loop_phase"] == "submitting"
    assert snapshots["operating-cycle"]["health_status"] == "active"
    assert snapshots["operating-cycle"]["last_gate_reason"] == "active-industry"
    assert snapshots["operating-cycle"]["submit_count"] == 1

    stopped = tasks.loop_snapshots()
    assert stopped["host-recovery"]["loop_phase"] == "stopped"
    assert stopped["host-recovery"]["health_status"] == "stopped"
    assert stopped["operating-cycle"]["loop_phase"] == "stopped"
    assert stopped["operating-cycle"]["health_status"] == "stopped"


@pytest.mark.asyncio
async def test_start_automation_tasks_dispatches_operating_cycle_when_gate_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submissions: list[dict[str, object]] = []
    submitted = asyncio.Event()

    async def _record_submit(
        dispatcher,
        capability_service,
        *,
        capability_ref,
        title,
        owner_agent_id,
        payload,
    ):
        _ = dispatcher
        _ = capability_service
        submissions.append(
            {
                "capability_ref": capability_ref,
                "title": title,
                "owner_agent_id": owner_agent_id,
                "payload": dict(payload),
            },
        )
        submitted.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        runtime_lifecycle_module,
        "automation_interval_seconds",
        lambda *_args, **_kwargs: 0,
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "submit_kernel_automation_task",
        _record_submit,
    )

    tasks = start_automation_tasks(
        kernel_dispatcher=SimpleNamespace(),
        capability_service=SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        environment_service=SimpleNamespace(
            should_run_host_recovery=lambda **_kwargs: (
                False,
                "no-actionable-host-events",
            ),
        ),
        industry_service=SimpleNamespace(
            should_run_operating_cycle=lambda: (True, "active-industry"),
        ),
        learning_service=SimpleNamespace(
            should_run_strategy_cycle=lambda **_kwargs: (
                False,
                "no-actionable-failure-pattern",
            ),
        ),
        logger=logging.getLogger(__name__),
    )

    try:
        await asyncio.wait_for(submitted.wait(), timeout=0.2)
    finally:
        await stop_automation_tasks(tasks)

    assert len(submissions) == 1
    assert submissions[0]["capability_ref"] == "system:run_operating_cycle"
    assert submissions[0]["owner_agent_id"] == "copaw-main-brain"
    assert submissions[0]["payload"] == {
        "actor": "system:automation",
        "source": "automation:operating_cycle",
        "force": False,
        "entry_source": "automation-loop",
        "automation_task_id": (
            "copaw-main-brain:operating-cycle:system:run_operating_cycle"
        ),
        "coordinator_contract": "automation-coordinator/v1",
        "automation_loop_name": "operating-cycle",
        "durable_coordinator_contract": "durable-runtime-coordinator/v1",
        "durable_coordinator_entrypoint": "automation-loop",
        "durable_coordinator_id": (
            "copaw-main-brain:operating-cycle:system:run_operating_cycle"
        ),
    }


@pytest.mark.asyncio
async def test_start_automation_tasks_skips_dispatch_when_preflight_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submissions: list[dict[str, object]] = []

    async def _record_submit(
        dispatcher,
        capability_service,
        *,
        capability_ref,
        title,
        owner_agent_id,
        payload,
    ):
        _ = dispatcher
        _ = capability_service
        submissions.append(
            {
                "capability_ref": capability_ref,
                "title": title,
                "owner_agent_id": owner_agent_id,
                "payload": dict(payload),
            },
        )
        return SimpleNamespace(phase="completed")

    monkeypatch.setattr(
        runtime_lifecycle_module,
        "automation_interval_seconds",
        lambda *_args, **_kwargs: 0,
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "submit_kernel_automation_task",
        _record_submit,
    )

    tasks = start_automation_tasks(
        kernel_dispatcher=SimpleNamespace(),
        capability_service=SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        environment_service=SimpleNamespace(
            should_run_host_recovery=lambda **_kwargs: (
                False,
                "no-actionable-host-events",
            ),
        ),
        industry_service=SimpleNamespace(
            should_run_operating_cycle=lambda: (False, "open-backlog-drained"),
        ),
        learning_service=SimpleNamespace(
            should_run_strategy_cycle=lambda **_kwargs: (
                False,
                "no-actionable-failure-pattern",
            ),
        ),
        logger=logging.getLogger(__name__),
    )

    try:
        await asyncio.sleep(0.05)
    finally:
        await stop_automation_tasks(tasks)

    assert submissions == []


@pytest.mark.asyncio
async def test_start_automation_tasks_dispatches_host_recovery_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submissions: list[dict[str, object]] = []
    submitted = asyncio.Event()

    async def _record_submit(
        dispatcher,
        capability_service,
        *,
        capability_ref,
        title,
        owner_agent_id,
        payload,
    ):
        _ = dispatcher
        _ = capability_service
        submissions.append(
            {
                "capability_ref": capability_ref,
                "title": title,
                "owner_agent_id": owner_agent_id,
                "payload": dict(payload),
            },
        )
        submitted.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        runtime_lifecycle_module,
        "automation_interval_seconds",
        lambda *_args, **_kwargs: 0,
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "submit_kernel_automation_task",
        _record_submit,
    )

    tasks = start_automation_tasks(
        kernel_dispatcher=SimpleNamespace(),
        capability_service=SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        environment_service=SimpleNamespace(
            should_run_host_recovery=lambda **_kwargs: (True, "host-events-pending"),
        ),
        industry_service=SimpleNamespace(
            should_run_operating_cycle=lambda: (False, "open-backlog-drained"),
        ),
        learning_service=SimpleNamespace(
            should_run_strategy_cycle=lambda **_kwargs: (
                False,
                "no-actionable-failure-pattern",
            ),
        ),
        logger=logging.getLogger(__name__),
    )

    try:
        await asyncio.wait_for(submitted.wait(), timeout=0.2)
    finally:
        await stop_automation_tasks(tasks)

    assert len(submissions) == 1
    assert submissions[0]["capability_ref"] == "system:run_host_recovery"
    assert submissions[0]["payload"] == {
        "actor": "system:automation",
        "source": "automation:host_recovery",
        "limit": 25,
        "allow_cross_process_recovery": True,
        "entry_source": "automation-loop",
        "automation_task_id": (
            "copaw-main-brain:host-recovery:system:run_host_recovery"
        ),
        "coordinator_contract": "automation-coordinator/v1",
        "automation_loop_name": "host-recovery",
        "durable_coordinator_contract": "durable-runtime-coordinator/v1",
        "durable_coordinator_entrypoint": "automation-loop",
        "durable_coordinator_id": (
            "copaw-main-brain:host-recovery:system:run_host_recovery"
        ),
    }


@pytest.mark.asyncio
async def test_stop_automation_tasks_completes_during_shutdown_cancellation() -> None:
    gate = asyncio.Event()

    async def _loop() -> None:
        try:
            await gate.wait()
        except asyncio.CancelledError:
            raise

    managed = [asyncio.create_task(_loop(), name="managed-automation")]

    async def _shutdown() -> bool:
        await stop_automation_tasks(managed)
        return all(task.done() for task in managed)

    shutdown_task = asyncio.create_task(_shutdown(), name="shutdown-stop-automation")
    await asyncio.sleep(0)
    shutdown_task.cancel()

    assert await shutdown_task is True
    assert shutdown_task.cancelled() is False


@pytest.mark.asyncio
async def test_runtime_restart_coordinator_waits_for_existing_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = RuntimeRestartCoordinator(
        app=FastAPI(),
        agent_runtime_app=FastAPI(),
        bootstrap=SimpleNamespace(),
        runtime_host=object(),
        logger=logging.getLogger(__name__),
    )
    called = False
    gate = asyncio.Event()

    async def _unexpected_restart(*, restart_requester_task) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(coordinator, "_do_restart_services", _unexpected_restart)
    coordinator._restart_task = asyncio.create_task(gate.wait(), name="existing-restart")

    waiter = asyncio.create_task(coordinator.restart_services())
    await asyncio.sleep(0)

    assert called is False

    gate.set()
    await waiter


@pytest.mark.asyncio
async def test_runtime_restart_coordinator_does_not_require_retired_actor_runtime_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    app = FastAPI()
    app.state.schedule_repository = "schedule-repository"
    app.state.environment_service = "environment-service"
    app.state.decision_request_repository = "decision-repository"
    app.state.kernel_task_store = "kernel-task-store"
    app.state.agent_runtime_repository = "agent-runtime-repository"
    app.state.human_assist_task_service = "human-assist-task-service"
    app.state.backlog_item_repository = "backlog-item-repository"
    app.state.assignment_repository = "assignment-repository"
    app.state.goal_repository = "goal-repository"
    app.state.goal_override_repository = "goal-override-repository"
    app.state.task_repository = "task-repository"
    app.state.task_runtime_repository = "task-runtime-repository"
    app.state.runtime_event_bus = "runtime-event-bus"
    app.state.automation_tasks = []

    agent_runtime_app = FastAPI()

    class _CapabilityService:
        def set_mcp_manager(self, value) -> None:
            captured["capability_service_mcp_manager"] = value

    class _TurnExecutor:
        def set_mcp_manager(self, value) -> None:
            captured["turn_executor_mcp_manager"] = value

    class _IndustryService:
        def set_schedule_runtime(self, **kwargs) -> None:
            captured["industry_schedule_runtime"] = kwargs

    class _WorkflowTemplateService:
        def set_schedule_runtime(self, **kwargs) -> None:
            captured["workflow_schedule_runtime"] = kwargs

    bootstrap = SimpleNamespace(
        kernel_dispatcher="kernel-dispatcher",
        capability_service=_CapabilityService(),
        governance_service="governance-service",
        memory_sleep_service="memory-sleep-service",
        research_session_service="research-session-service",
        weixin_ilink_runtime_state="weixin-ilink-runtime-state",
        industry_service=_IndustryService(),
        workflow_template_service=_WorkflowTemplateService(),
        turn_executor=_TurnExecutor(),
    )
    coordinator = RuntimeRestartCoordinator(
        app=app,
        agent_runtime_app=agent_runtime_app,
        bootstrap=bootstrap,
        runtime_host=object(),
        logger=logging.getLogger(__name__),
    )

    monkeypatch.setattr(
        runtime_lifecycle_module,
        "get_config_path",
        lambda: "config.toml",
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "load_config",
        lambda _path: SimpleNamespace(),
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "runtime_manager_stack_from_app_state",
        lambda _state: "old-manager-stack",
    )

    async def _stop_runtime_manager_stack(stack, *, logger, error_mode, context, **kwargs) -> None:
        captured["stop_runtime_manager_stack"] = {
            "stack": stack,
            "logger": logger,
            "error_mode": error_mode,
            "context": context,
            **kwargs,
        }

    async def _initialize_mcp_manager(**kwargs):
        captured["initialize_mcp_manager"] = kwargs
        return "new-mcp-manager"

    async def _start_runtime_manager_stack(**kwargs):
        captured["start_runtime_manager_stack"] = kwargs
        return SimpleNamespace(job_repository="job-repository", cron_manager="cron-manager")

    monkeypatch.setattr(
        runtime_lifecycle_module,
        "stop_runtime_manager_stack",
        _stop_runtime_manager_stack,
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "initialize_mcp_manager",
        _initialize_mcp_manager,
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "start_runtime_manager_stack",
        _start_runtime_manager_stack,
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "run_startup_recovery",
        lambda **kwargs: captured.setdefault("run_startup_recovery", kwargs) or {"reason": "restart"},
    )
    monkeypatch.setattr(
        runtime_lifecycle_module,
        "attach_runtime_state",
        lambda *args, **kwargs: captured.setdefault(
            "attach_runtime_state",
            {"args": args, "kwargs": kwargs},
        ),
    )

    await coordinator._do_restart_services(restart_requester_task=None)

    startup_recovery_kwargs = captured["run_startup_recovery"]
    assert "actor_mailbox_service" not in startup_recovery_kwargs
    assert "exception_absorption_service" not in startup_recovery_kwargs
    assert captured["industry_schedule_runtime"]["schedule_writer"] == "job-repository"
    assert captured["workflow_schedule_runtime"]["cron_manager"] == "cron-manager"


@pytest.mark.asyncio
async def test_app_lifespan_startup_recovery_does_not_thread_retired_actor_runtime_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    app = FastAPI()

    class _RuntimeHost:
        def __init__(self) -> None:
            self.session_backend = "session-backend"
            self.conversation_compaction_service = "conversation-compaction-service"

        async def start(self) -> None:
            captured["runtime_host_started"] = True

        async def stop(self) -> None:
            captured["runtime_host_stopped"] = True

        def sync_turn_executor(self, value) -> None:
            captured.setdefault("sync_turn_executor", []).append(value)

        def set_restart_callback(self, value) -> None:
            captured["restart_callback"] = value

    class _IndustryService:
        def set_schedule_runtime(self, **kwargs) -> None:
            captured["industry_schedule_runtime"] = kwargs

    class _WorkflowTemplateService:
        def set_schedule_runtime(self, **kwargs) -> None:
            captured["workflow_schedule_runtime"] = kwargs

    class _EnvironmentService:
        def set_latest_recovery_report_sink(self, value) -> None:
            captured["latest_recovery_report_sink"] = value

        def set_latest_recovery_report(self, value) -> None:
            captured["latest_recovery_report"] = value

    bootstrap = SimpleNamespace(
        environment_service=_EnvironmentService(),
        repositories=SimpleNamespace(
            decision_request_repository="decision-repository",
            schedule_repository="schedule-repository",
            agent_runtime_repository="agent-runtime-repository",
            backlog_item_repository="backlog-item-repository",
            assignment_repository="assignment-repository",
            goal_repository="goal-repository",
            goal_override_repository="goal-override-repository",
            task_repository="task-repository",
            task_runtime_repository="task-runtime-repository",
            bootstrap_schedule_repository="bootstrap-schedule-repository",
            automation_loop_runtime_repository="automation-loop-runtime-repository",
        ),
        kernel_dispatcher="kernel-dispatcher",
        kernel_task_store="kernel-task-store",
        human_assist_task_service="human-assist-task-service",
        runtime_event_bus="runtime-event-bus",
        memory_sleep_service="memory-sleep-service",
        research_session_service="research-session-service",
        weixin_ilink_runtime_state="weixin-ilink-runtime-state",
        capability_service="capability-service",
        governance_service="governance-service",
        industry_service=_IndustryService(),
        workflow_template_service=_WorkflowTemplateService(),
        turn_executor="turn-executor",
        learning_service="learning-service",
    )

    class _RestartCoordinator:
        def __init__(self, **kwargs) -> None:
            captured["restart_coordinator_kwargs"] = kwargs

        async def restart_services(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(app_module, "resolve_environment_preflight_paths", lambda **_kwargs: {})
    monkeypatch.setattr(app_module, "assert_startup_environment_ready", lambda **_kwargs: "preflight")
    monkeypatch.setattr(app_module, "add_copaw_file_handler", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_module, "runtime_host", _RuntimeHost())
    monkeypatch.setattr(app_module, "load_config", lambda: SimpleNamespace())
    monkeypatch.setattr(
        app_module,
        "initialize_mcp_manager",
        lambda **_kwargs: asyncio.sleep(0, result="mcp-manager"),
    )
    monkeypatch.setattr(app_module, "build_runtime_bootstrap", lambda **_kwargs: bootstrap)
    monkeypatch.setattr(
        app_module,
        "run_startup_recovery",
        lambda **kwargs: captured.setdefault("run_startup_recovery", kwargs) or {"reason": "startup"},
    )
    monkeypatch.setattr(
        app_module,
        "start_runtime_manager_stack",
        lambda **_kwargs: asyncio.sleep(
            0,
            result=SimpleNamespace(job_repository="job-repository", cron_manager="cron-manager"),
        ),
    )
    monkeypatch.setattr(
        app_module,
        "attach_runtime_state",
        lambda _app, **kwargs: setattr(_app.state, "startup_recovery_summary", kwargs["startup_recovery_summary"]),
    )
    monkeypatch.setattr(app_module, "start_automation_tasks", lambda **_kwargs: [])
    monkeypatch.setattr(app_module, "build_latest_recovery_report", lambda **_kwargs: {"reason": "startup"})
    monkeypatch.setattr(app_module, "RuntimeRestartCoordinator", _RestartCoordinator)
    monkeypatch.setattr(app_module, "stop_automation_tasks", lambda *_args, **_kwargs: asyncio.sleep(0))
    monkeypatch.setattr(app_module, "runtime_manager_stack_from_app_state", lambda _state: "manager-stack")
    monkeypatch.setattr(app_module, "stop_runtime_manager_stack", lambda *_args, **_kwargs: asyncio.sleep(0))

    async with app_module.lifespan(app):
        pass

    startup_recovery_kwargs = captured["run_startup_recovery"]
    assert "actor_mailbox_service" not in startup_recovery_kwargs
    assert "exception_absorption_service" not in startup_recovery_kwargs
    assert captured["industry_schedule_runtime"]["schedule_writer"] == "job-repository"
    assert captured["workflow_schedule_runtime"]["cron_manager"] == "cron-manager"


class _FakeAutomationTaskStore:
    def __init__(self, tasks) -> None:
        self._tasks = list(tasks)

    def list_tasks(self, *, phase=None, owner_agent_id=None, limit=200):
        _ = limit
        items = list(self._tasks)
        if phase is not None:
            items = [task for task in items if getattr(task, "phase", None) == phase]
        if owner_agent_id is not None:
            items = [
                task
                for task in items
                if getattr(task, "owner_agent_id", None) == owner_agent_id
            ]
        return items


class _FakeAutomationDispatcher:
    def __init__(self, task_store) -> None:
        self.task_store = task_store
        self.submitted = []

    def submit(self, task):
        self.submitted.append(task)
        return SimpleNamespace(phase="executing", summary="executing", task_id=task.id)

    async def execute_task(self, task_id):
        return SimpleNamespace(phase="completed", summary=f"completed {task_id}")


@pytest.mark.asyncio
async def test_submit_kernel_automation_task_skips_duplicate_inflight_payload() -> None:
    payload = {
        "actor": "copaw-main-brain",
        "auto_apply": True,
        "auto_rollback": False,
        "failure_threshold": 2,
        "confirm_threshold": 6,
        "max_proposals": 5,
    }
    existing_task = SimpleNamespace(
        phase="waiting-confirm",
        capability_ref="system:run_learning_strategy",
        owner_agent_id="copaw-main-brain",
        payload=payload,
    )
    dispatcher = _FakeAutomationDispatcher(_FakeAutomationTaskStore([existing_task]))

    result = await submit_kernel_automation_task(
        dispatcher,
        SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        capability_ref="system:run_learning_strategy",
        title="Automation: learning-strategy",
        owner_agent_id="copaw-main-brain",
        payload=dict(payload),
    )

    assert getattr(result, "phase", None) == "skipped"
    assert dispatcher.submitted == []


def test_reap_stale_kernel_tasks_fails_expired_executing_tasks() -> None:
    stale_task = SimpleNamespace(id="ktask-stale", title="Stale task")
    fresh_task = SimpleNamespace(id="ktask-fresh", title="Fresh task")
    now = datetime.now(timezone.utc)

    class _TaskStore:
        def list_tasks(self, *, phase=None, owner_agent_id=None, limit=200):
            del owner_agent_id, limit
            assert phase == "executing"
            return [stale_task, fresh_task]

        def get_runtime_record(self, task_id):
            if task_id == "ktask-stale":
                return SimpleNamespace(updated_at=now - timedelta(seconds=120))
            if task_id == "ktask-fresh":
                return SimpleNamespace(updated_at=now - timedelta(seconds=5))
            return None

    class _Dispatcher:
        def __init__(self) -> None:
            self.task_store = _TaskStore()
            self._config = SimpleNamespace(execution_timeout_seconds=30.0)
            self.failed = []

        def fail_task(self, task_id, *, error, append_kernel_evidence=True):
            self.failed.append(
                {
                    "task_id": task_id,
                    "error": error,
                    "append_kernel_evidence": append_kernel_evidence,
                }
            )
            return SimpleNamespace(phase="failed", error=error)

    dispatcher = _Dispatcher()

    reaped = _reap_stale_kernel_tasks(dispatcher, logger=logging.getLogger(__name__))

    assert reaped == ["ktask-stale"]
    assert dispatcher.failed == [
        {
            "task_id": "ktask-stale",
            "error": "Execution timed out after 30 seconds.",
            "append_kernel_evidence": True,
        }
    ]


def test_reap_stale_kernel_tasks_reaps_execution_without_leaf_evidence_even_if_runtime_heartbeat_is_fresh() -> None:
    now = datetime.now(timezone.utc)
    stale_task = SimpleNamespace(
        id="ktask-no-leaf-progress",
        title="No leaf progress task",
        updated_at=now - timedelta(seconds=120),
    )

    class _TaskStore:
        def list_tasks(self, *, phase=None, owner_agent_id=None, limit=200):
            del owner_agent_id, limit
            assert phase == "executing"
            return [stale_task]

        def get_runtime_record(self, task_id):
            assert task_id == "ktask-no-leaf-progress"
            return SimpleNamespace(
                updated_at=now - timedelta(seconds=5),
                last_evidence_id=None,
                last_result_summary=None,
                last_error_summary=None,
            )

    class _Dispatcher:
        def __init__(self) -> None:
            self.task_store = _TaskStore()
            self._config = SimpleNamespace(execution_timeout_seconds=30.0)
            self.failed = []

        def fail_task(self, task_id, *, error, append_kernel_evidence=True):
            self.failed.append(
                {
                    "task_id": task_id,
                    "error": error,
                    "append_kernel_evidence": append_kernel_evidence,
                }
            )
            return SimpleNamespace(phase="failed", error=error)

    dispatcher = _Dispatcher()

    reaped = _reap_stale_kernel_tasks(dispatcher, logger=logging.getLogger(__name__))

    assert reaped == ["ktask-no-leaf-progress"]
    assert dispatcher.failed == [
        {
            "task_id": "ktask-no-leaf-progress",
            "error": "Execution timed out after 30 seconds.",
            "append_kernel_evidence": True,
        }
    ]


def test_should_run_learning_strategy_uses_service_preflight() -> None:
    allowed, reason = _should_run_learning_strategy(
        SimpleNamespace(
            should_run_strategy_cycle=lambda **_kwargs: (
                False,
                "no-actionable-failure-pattern",
            ),
        ),
    )

    assert allowed is False
    assert reason == "no-actionable-failure-pattern"


def test_should_run_operating_cycle_uses_service_preflight() -> None:
    allowed, reason = _should_run_operating_cycle(
        SimpleNamespace(
            should_run_operating_cycle=lambda: (
                False,
                "open-backlog-drained",
            ),
        ),
    )

    assert allowed is False
    assert reason == "open-backlog-drained"


def test_should_run_host_recovery_uses_service_preflight() -> None:
    allowed, reason = _should_run_host_recovery(
        SimpleNamespace(
            should_run_host_recovery=lambda **_kwargs: (
                False,
                "no-actionable-host-events",
            ),
        ),
    )

    assert allowed is False
    assert reason == "no-actionable-host-events"


@pytest.mark.asyncio
async def test_run_heartbeat_once_dispatches_main_brain_supervision_pulse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[SimpleNamespace] = []

    class _Dispatcher:
        def submit(self, task):
            submitted.append(task)
            return SimpleNamespace(
                phase="executing",
                summary="executing",
                task_id=task.id,
            )

        async def execute_task(self, task_id):
            return SimpleNamespace(
                phase="completed",
                summary=f"completed {task_id}",
                result={"count": 2},
            )

    monkeypatch.setattr(
        "copaw.app.crons.heartbeat.get_heartbeat_config",
        lambda: SimpleNamespace(active_hours=None, target="main"),
    )

    payload = await run_heartbeat_once(
        kernel_dispatcher=_Dispatcher(),
        ignore_active_hours=True,
    )

    assert payload["status"] == "success"
    assert payload["query_path"] == "system:run_operating_cycle"
    assert payload["query_preview"] == "main-brain supervision pulse"
    assert payload["processed_instance_count"] == 2
    assert len(submitted) == 1
    assert submitted[0].capability_ref == "system:run_operating_cycle"
    assert submitted[0].owner_agent_id == "copaw-main-brain"
    assert submitted[0].payload["source"] == "heartbeat:supervision-pulse"
