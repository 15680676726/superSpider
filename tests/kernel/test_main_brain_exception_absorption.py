# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from copaw.kernel.main_brain_exception_absorption import (
    MainBrainExceptionAbsorptionService,
)


@dataclass(slots=True)
class _Runtime:
    agent_id: str
    runtime_status: str = "idle"
    queue_depth: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class _MailboxItem:
    agent_id: str
    status: str
    task_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class _HumanAssistTask:
    id: str
    status: str
    updated_at: datetime
    task_id: str | None = None


def test_absorption_service_classifies_writer_contention_from_repeated_conflicts() -> None:
    now = datetime(2026, 4, 7, 10, 0, tzinfo=UTC)
    service = MainBrainExceptionAbsorptionService()

    summary = service.scan(
        runtimes=[
            _Runtime(
                agent_id="agent-1",
                runtime_status="blocked",
                metadata={
                    "writer_conflict_count": 3,
                    "writer_lock_scope": "desktop:sheet-1",
                    "last_error_summary": "Writer scope is already reserved.",
                },
            )
        ],
        mailbox_items=[],
        human_assist_tasks=[],
        now=now,
    )

    assert [case.case_kind for case in summary.active_cases] == ["writer-contention"]
    assert summary.case_counts["writer-contention"] == 1
    assert summary.recovery_counts["cleanup"] == 1
    assert "internal execution pressure" in summary.main_brain_summary


def test_absorption_service_classifies_waiting_confirm_orphan_without_creating_new_truth() -> None:
    now = datetime(2026, 4, 7, 10, 0, tzinfo=UTC)
    service = MainBrainExceptionAbsorptionService(waiting_confirm_orphan_after=timedelta(minutes=15))

    summary = service.scan(
        runtimes=[],
        mailbox_items=[
            _MailboxItem(
                agent_id="agent-2",
                status="blocked",
                task_id="task-confirm-1",
                metadata={
                    "task_phase": "waiting-confirm",
                    "updated_at": (now - timedelta(minutes=31)).isoformat(),
                    "checkpoint_id": "checkpoint-1",
                },
            )
        ],
        human_assist_tasks=[],
        now=now,
    )

    assert [case.case_kind for case in summary.active_cases] == ["waiting-confirm-orphan"]
    assert summary.active_cases[0].recovery_rung == "escalate"
    assert summary.active_cases[0].human_required is True


def test_absorption_service_classifies_retry_loop_and_progressless_runtime() -> None:
    now = datetime(2026, 4, 7, 10, 0, tzinfo=UTC)
    service = MainBrainExceptionAbsorptionService(
        retry_loop_threshold=3,
        progressless_runtime_after=timedelta(minutes=20),
    )

    summary = service.scan(
        runtimes=[
            _Runtime(
                agent_id="agent-retry",
                runtime_status="queued",
                metadata={
                    "retry_count": 4,
                    "retry_after_at": (now - timedelta(minutes=5)).isoformat(),
                },
            ),
            _Runtime(
                agent_id="agent-stuck",
                runtime_status="running",
                metadata={
                    "last_progress_at": (now - timedelta(minutes=45)).isoformat(),
                },
            ),
        ],
        mailbox_items=[],
        human_assist_tasks=[],
        now=now,
    )

    assert [case.case_kind for case in summary.active_cases] == [
        "retry-loop",
        "progressless-runtime",
    ]
    assert summary.case_counts["retry-loop"] == 1
    assert summary.case_counts["progressless-runtime"] == 1
    assert summary.recovery_counts["retry"] == 1
    assert summary.recovery_counts["replan"] == 1


def test_absorption_service_marks_human_assist_pressure_as_repeated_blocker_same_scope() -> None:
    now = datetime(2026, 4, 7, 10, 0, tzinfo=UTC)
    service = MainBrainExceptionAbsorptionService()

    summary = service.scan(
        runtimes=[
            _Runtime(
                agent_id="agent-ops",
                runtime_status="blocked",
                metadata={
                    "industry_instance_id": "industry-1",
                    "assignment_id": "assignment-1",
                    "blocked_scope_ref": "assignment:assignment-1",
                    "repeated_blocker_count": 2,
                },
            )
        ],
        mailbox_items=[],
        human_assist_tasks=[
            _HumanAssistTask(
                id="human-assist:1",
                status="handoff_blocked",
                task_id="task-1",
                updated_at=now - timedelta(minutes=10),
            )
        ],
        now=now,
    )

    assert [case.case_kind for case in summary.active_cases] == ["repeated-blocker-same-scope"]
    assert summary.active_cases[0].recovery_rung == "replan"
    assert summary.active_cases[0].human_required is False
    assert summary.human_required_case_count == 0


def test_absorption_service_classifies_stale_lease_from_long_held_runtime() -> None:
    now = datetime(2026, 4, 7, 10, 0, tzinfo=UTC)
    service = MainBrainExceptionAbsorptionService(stale_lease_after=timedelta(minutes=10))

    summary = service.scan(
        runtimes=[
            _Runtime(
                agent_id="agent-lease",
                runtime_status="running",
                metadata={
                    "lease_started_at": (now - timedelta(minutes=30)).isoformat(),
                    "environment_ref": "session:console:desktop-1",
                },
            )
        ],
        mailbox_items=[],
        human_assist_tasks=[],
        now=now,
    )

    assert [case.case_kind for case in summary.active_cases] == ["stale-lease"]
    assert summary.active_cases[0].recovery_rung == "cleanup"
