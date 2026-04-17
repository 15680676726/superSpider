# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.app.crons.executor import CronExecutor
from copaw.app.crons.models import CronJobSpec


class _FakeKernelDispatcher:
    def __init__(self) -> None:
        self.tasks = []

    def submit(self, task):
        self.tasks.append(task)
        return SimpleNamespace(phase="executing", task_id=task.id)

    async def execute_task(self, task_id: str):
        return SimpleNamespace(success=True, error=None, summary="ok")


class _FakeResearchSessionService:
    def __init__(self) -> None:
        self.started: list[dict[str, object]] = []
        self.ran: list[str] = []
        self.summarized: list[str] = []

    def start_session(self, **kwargs):
        self.started.append(dict(kwargs))
        session = SimpleNamespace(id="research-session-1", status="queued")
        return SimpleNamespace(session=session, stop_reason=None)

    def run_session(self, session_id: str):
        self.ran.append(session_id)
        session = SimpleNamespace(id=session_id, status="completed")
        return SimpleNamespace(session=session, stop_reason="completed")

    def summarize_session(self, session_id: str):
        self.summarized.append(session_id)
        session = SimpleNamespace(id=session_id, status="completed")
        return SimpleNamespace(session=session, stop_reason="completed")


def _agent_job(*, meta: dict[str, object] | None = None) -> CronJobSpec:
    return CronJobSpec.model_validate(
        {
            "id": "cron-job-1",
            "name": "Workflow host-aware cron",
            "enabled": True,
            "schedule": {
                "type": "cron",
                "cron": "0 9 * * 1",
                "timezone": "UTC",
            },
            "task_type": "agent",
            "request": {
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "continue workflow"}],
                    }
                ]
            },
            "dispatch": {
                "type": "channel",
                "channel": "console",
                "target": {"user_id": "workflow", "session_id": "workflow-run-1"},
                "mode": "final",
                "meta": {"summary": "resume scheduled step"},
            },
            "runtime": {
                "max_concurrency": 1,
                "timeout_seconds": 30,
                "misfire_grace_seconds": 30,
            },
            "meta": dict(meta or {}),
        }
    )


def test_cron_executor_prefers_stored_host_refs_over_session_fallback() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "environment_id": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "host_requirement": {"app_family": "browser_backoffice"},
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:session:session:web:main"
    assert submitted.payload["meta"]["session_mount_id"] == "session:web:main"
    assert submitted.payload["meta"]["host_requirement"] == {
        "app_family": "browser_backoffice"
    }


def test_cron_executor_falls_back_to_channel_session_when_no_host_ref_exists() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)

    asyncio.run(executor.execute(_agent_job()))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "session:console:workflow-run-1"


def test_cron_executor_uses_scheduler_inputs_from_host_snapshot_before_session_fallback() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "host_snapshot": {
                "environment_id": "env:host-snapshot",
                "session_mount_id": "session:host-snapshot",
                "scheduler_inputs": {
                    "environment_ref": "env:from-scheduler-inputs",
                    "session_mount_id": "session:from-scheduler-inputs",
                },
                "host_twin_summary": {
                    "recommended_scheduler_action": "continue",
                    "blocked_surface_count": 0,
                    "legal_recovery_mode": "resume",
                },
            },
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:from-scheduler-inputs"
    assert submitted.payload["meta"]["session_mount_id"] == "session:from-scheduler-inputs"
    assert submitted.payload["meta"]["coordinator_contract"] == "durable-runtime-coordinator/v1"
    assert submitted.payload["meta"]["coordinator_entrypoint"] == "cron-job"
    assert submitted.payload["meta"]["coordinator_id"] == "cron-job-1"
    assert submitted.payload["meta"]["host_snapshot"]["environment_id"] == "env:host-snapshot"
    assert submitted.payload["meta"]["host_snapshot"]["host_twin_summary"]["recommended_scheduler_action"] == "continue"
    assert submitted.payload["meta"]["host_snapshot"]["host_twin_summary"]["blocked_surface_count"] == 0


def test_cron_executor_prefers_scheduler_host_refs_over_stale_direct_meta_refs() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "environment_ref": "env:stale-direct-meta",
            "environment_id": "env:stale-direct-meta",
            "session_mount_id": "session:stale-direct-meta",
            "host_snapshot": {
                "environment_id": "env:host-snapshot",
                "session_mount_id": "session:host-snapshot",
                "scheduler_inputs": {
                    "environment_ref": "env:fresh-scheduler-inputs",
                    "environment_id": "env:fresh-scheduler-inputs",
                    "session_mount_id": "session:fresh-scheduler-inputs",
                },
            },
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:fresh-scheduler-inputs"
    assert submitted.payload["meta"]["session_mount_id"] == "session:fresh-scheduler-inputs"


def test_cron_executor_prefers_canonical_selected_seat_when_scheduler_inputs_are_missing() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "host_snapshot": {
                "environment_id": "env:stale-host-seat",
                "session_mount_id": "session:stale-host-seat",
                "host_twin_summary": {
                    "selected_seat_ref": "env:canonical-selected-seat",
                    "selected_session_mount_id": "session:canonical-selected-seat",
                    "recommended_scheduler_action": "continue",
                    "blocked_surface_count": 0,
                    "legal_recovery_mode": "resume",
                },
            },
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:canonical-selected-seat"
    assert submitted.payload["meta"]["session_mount_id"] == (
        "session:canonical-selected-seat"
    )


def test_cron_executor_persists_canonical_environment_id_when_only_environment_ref_is_available() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "host_snapshot": {
                "environment_ref": "env:canonical-host-ref",
                "session_mount_id": "session:canonical-host-ref",
            },
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:canonical-host-ref"
    assert submitted.payload["meta"]["environment_id"] == "env:canonical-host-ref"
    assert submitted.payload["meta"]["session_mount_id"] == "session:canonical-host-ref"


def test_cron_executor_dispatches_agent_with_shared_durable_request_context() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = CronJobSpec.model_validate(
        {
            "id": "cron-job-ctx-1",
            "name": "Shared durable path cron",
            "enabled": True,
            "schedule": {
                "type": "cron",
                "cron": "0 9 * * 1",
                "timezone": "UTC",
            },
            "task_type": "agent",
            "request": {
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "resume shared workflow"}],
                    }
                ],
                "control_thread_id": "thread-cron-ctx-1",
                "work_context_id": "ctx-cron-ctx-1",
                "main_brain_runtime": {
                    "work_context_id": "ctx-cron-ctx-1",
                    "recovery": {
                        "mode": "resume-environment",
                        "checkpoint_id": "checkpoint-cron-1",
                    },
                },
            },
            "dispatch": {
                "type": "channel",
                "channel": "console",
                "target": {
                    "user_id": "workflow",
                    "session_id": "workflow-run-ctx-1",
                },
                "mode": "final",
                "meta": {"summary": "resume durable path"},
            },
            "runtime": {
                "max_concurrency": 1,
                "timeout_seconds": 30,
                "misfire_grace_seconds": 30,
            },
            "meta": {
                "host_snapshot": {
                    "scheduler_inputs": {
                        "environment_ref": "env:cron-shared-path",
                        "session_mount_id": "session:cron-shared-path",
                    },
                },
            },
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:cron-shared-path"
    assert submitted.work_context_id == "ctx-cron-ctx-1"
    assert submitted.payload["request"]["entry_source"] == "cron-job"
    assert submitted.payload["request"]["coordinator_contract"] == "durable-runtime-coordinator/v1"
    assert submitted.payload["request"]["coordinator_entrypoint"] == "cron-job"
    assert submitted.payload["request"]["coordinator_id"] == "cron-job-ctx-1"
    assert submitted.payload["request"]["environment_ref"] == "env:cron-shared-path"
    assert submitted.payload["request"]["main_brain_runtime"]["environment"]["ref"] == (
        "env:cron-shared-path"
    )
    assert submitted.payload["request_context"]["session_id"] == "workflow-run-ctx-1"
    assert submitted.payload["request_context"]["control_thread_id"] == "thread-cron-ctx-1"
    assert submitted.payload["request_context"]["work_context_id"] == "ctx-cron-ctx-1"
    assert submitted.payload["request_context"]["channel"] == "console"
    assert submitted.payload["request_context"]["coordinator_contract"] == (
        "durable-runtime-coordinator/v1"
    )
    assert submitted.payload["request_context"]["coordinator_entrypoint"] == "cron-job"
    assert submitted.payload["request_context"]["coordinator_id"] == "cron-job-ctx-1"
    assert submitted.payload["request_context"]["main_brain_runtime"]["environment"]["ref"] == (
        "env:cron-shared-path"
    )
    assert submitted.payload["request_context"]["main_brain_runtime"]["recovery"]["mode"] == (
        "resume-environment"
    )


def test_cron_executor_routes_monitoring_brief_into_research_session_service() -> None:
    dispatcher = _FakeKernelDispatcher()
    research_service = _FakeResearchSessionService()
    executor = CronExecutor(
        kernel_dispatcher=dispatcher,
        research_session_service=research_service,
    )
    job = _agent_job(
        meta={
            "research_provider": "baidu-page",
            "research_mode": "monitoring-brief",
            "research_goal": "每天早上整理持仓股票相关新闻和监管变化",
            "owner_agent_id": "industry-researcher-demo",
            "industry_instance_id": "industry-v1-demo",
            "supervisor_agent_id": "copaw-agent-runner",
        }
    )

    asyncio.run(executor.execute(job))

    assert dispatcher.tasks == []
    assert research_service.started == [
        {
            "goal": "每天早上整理持仓股票相关新闻和监管变化",
            "trigger_source": "monitoring",
            "owner_agent_id": "industry-researcher-demo",
            "industry_instance_id": "industry-v1-demo",
            "work_context_id": None,
            "supervisor_agent_id": "copaw-agent-runner",
            "metadata": {
                "schedule_id": "cron-job-1",
                "schedule_name": "Workflow host-aware cron",
                "research_provider": "baidu-page",
                "research_mode": "monitoring-brief",
            },
        }
    ]
    assert research_service.ran == ["research-session-1"]
    assert research_service.summarized == ["research-session-1"]


def test_cron_executor_ignores_monitoring_stub_without_research_service() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "research_provider": "baidu-page",
            "research_mode": "monitoring-brief",
            "research_goal": "整理本周平台规则变化",
            "owner_agent_id": "industry-researcher-demo",
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
