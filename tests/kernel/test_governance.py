# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.kernel.governance import GovernanceService
from copaw.kernel.models import KernelTask
from copaw.state import GovernanceControlRecord, SQLiteStateStore
from copaw.state.human_assist_task_service import HumanAssistTaskService
from copaw.state.repositories import (
    SqliteGovernanceControlRepository,
    SqliteHumanAssistTaskRepository,
)


def test_governance_service_no_longer_exposes_query_confirmation_policy_controls(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(control_repository=repository)

    status = service.get_status()

    assert not hasattr(service, "set_query_confirmation_policy")
    assert "query_confirmation_policies" not in status.metadata
    control = repository.get_control("runtime")
    assert control is not None
    assert "query_confirmation_policies" not in control.metadata


def test_governance_service_preserves_runtime_metadata_without_query_confirmation_policy(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(control_repository=repository)
    repository.upsert_control(
        GovernanceControlRecord(
            id="runtime",
            metadata={"retained": "ok"},
        )
    )

    status = service.get_status()

    assert status.metadata["retained"] == "ok"
    assert "query_confirmation_policies" not in status.metadata
    control = repository.get_control("runtime")
    assert control is not None
    assert control.metadata["retained"] == "ok"
    assert "query_confirmation_policies" not in control.metadata


def test_governance_service_hides_retired_goal_dispatch_from_blocked_capabilities(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(control_repository=repository)

    status = asyncio.run(
        service.emergency_stop(
        actor="operator",
        reason="test",
        )
    )

    assert "system:dispatch_query" in status.blocked_capability_refs
    assert "system:dispatch_goal" not in status.blocked_capability_refs


class _FakeEnvironmentService:
    def list_sessions(self, **kwargs):
        _ = kwargs
        return [SimpleNamespace(id="session:web:main")]

    def get_session_detail(self, session_mount_id: str, *, limit: int = 20):
        _ = limit
        if session_mount_id != "session:web:main":
            return None
        return {
            "session_mount_id": session_mount_id,
            "host_twin": {
                "active_blocker_families": ["modal-uac-login"],
                "continuity": {"requires_human_return": True},
                "ownership": {"handoff_owner_ref": "human-operator:alice"},
                "coordination": {
                    "recommended_scheduler_action": "handoff",
                    "summary": "human handoff is still active",
                },
                "legal_recovery": {
                    "path": "handoff",
                    "resume_kind": "resume-runtime",
                    "return_condition": "captcha-cleared",
                },
            },
        }


class _FakeCanonicalReadyEnvironmentService:
    def list_sessions(self, **kwargs):
        _ = kwargs
        return [SimpleNamespace(id="session:web:canonical")]

    def get_session_detail(self, session_mount_id: str, *, limit: int = 20):
        _ = limit
        if session_mount_id != "session:web:canonical":
            return None
        return {
            "session_mount_id": session_mount_id,
            "host_twin_summary": {
                "recommended_scheduler_action": "proceed",
                "blocked_surface_count": 0,
                "legal_recovery_mode": "resume-environment",
                "continuity_state": "ready",
                "seat_owner_ref": "ops-agent",
            },
            "host_twin": {
                "active_blocker_families": ["modal-uac-login"],
                "continuity": {"requires_human_return": True},
                "ownership": {"handoff_owner_ref": "human-operator:alice"},
                "coordination": {
                    "recommended_scheduler_action": "handoff",
                    "summary": "human handoff is still active",
                },
                "legal_recovery": {
                    "path": "handoff",
                    "resume_kind": "resume-runtime",
                    "return_condition": "captcha-cleared",
                },
                "host_twin_summary": {
                    "recommended_scheduler_action": "handoff",
                    "blocked_surface_count": 1,
                    "legal_recovery_mode": "handoff",
                    "continuity_state": "blocked",
                },
            },
        }


class _FakeHumanAssistTaskService:
    def list_tasks(self, **kwargs):
        chat_thread_id = kwargs.get("chat_thread_id")
        records = [
            SimpleNamespace(
                task_id="ha-1",
                id="ha-1",
                chat_thread_id="thread-1",
                status="handoff_blocked",
            ),
            SimpleNamespace(
                task_id="ha-2",
                id="ha-2",
                chat_thread_id="thread-2",
                status="need_more_evidence",
            ),
        ]
        if chat_thread_id is None:
            return records
        return [item for item in records if item.chat_thread_id == chat_thread_id]


class _FakeIndustryService:
    def list_instances(self, **kwargs):
        _ = kwargs
        return [SimpleNamespace(instance_id="industry-1")]

    def get_instance_detail(self, instance_id: str, **kwargs):
        _ = kwargs
        if instance_id != "industry-1":
            return None
        return {
            "instance_id": instance_id,
            "staffing": {
                "active_gap": {
                    "kind": "temporary-seat-proposal",
                    "target_role_name": "Browser Writer",
                    "requires_confirmation": True,
                    "decision_request_id": "decision-seat-1",
                },
                "pending_proposals": [
                    {
                        "decision_request_id": "decision-seat-1",
                        "status": "open",
                    },
                ],
                "temporary_seats": [],
            },
        }


def test_governance_status_surfaces_host_handoff_staffing_and_human_assist(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(
        control_repository=repository,
        environment_service=_FakeEnvironmentService(),
        human_assist_task_service=_FakeHumanAssistTaskService(),
        industry_service=_FakeIndustryService(),
    )

    status = service.get_status()

    assert status.host_twin["blocking_session_count"] == 1
    assert status.host_twin["blocking_families"] == ["modal-uac-login"]
    assert status.handoff["active"] is True
    assert status.handoff["owner_refs"] == ["human-operator:alice"]
    assert status.staffing["active_gap_count"] == 1
    assert status.staffing["pending_confirmation_count"] == 1
    assert status.staffing["decision_request_ids"] == ["decision-seat-1"]
    assert status.human_assist["open_count"] == 2
    assert status.human_assist["blocked_count"] == 1
    assert status.human_assist["need_more_evidence_count"] == 1


def test_governance_admission_blocks_dispatch_when_runtime_governance_requires_handoff(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(
        control_repository=repository,
        environment_service=_FakeEnvironmentService(),
        human_assist_task_service=_FakeHumanAssistTaskService(),
        industry_service=_FakeIndustryService(),
    )

    task = KernelTask(
        title="Dispatch browser work",
        capability_ref="system:dispatch_query",
        environment_ref="session:web:main",
        payload={
            "chat_thread_id": "thread-1",
            "industry_instance_id": "industry-1",
        },
    )

    reason = service.admission_block_reason(task)

    assert reason is not None
    assert "handoff" in reason.lower()


def test_governance_admission_issues_human_assist_task_for_host_handoff_once(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    human_assist_store = SQLiteStateStore(tmp_path / "human_assist.sqlite3")
    human_assist_service = HumanAssistTaskService(
        repository=SqliteHumanAssistTaskRepository(human_assist_store),
    )
    service = GovernanceService(
        control_repository=repository,
        environment_service=_FakeEnvironmentService(),
        human_assist_task_service=human_assist_service,
        industry_service=_FakeIndustryService(),
    )
    task = KernelTask(
        title="Dispatch browser work",
        capability_ref="system:dispatch_query",
        environment_ref="session:web:main",
        payload={
            "chat_thread_id": "thread-human-assist",
            "industry_instance_id": "industry-1",
            "assignment_id": "assignment-1",
            "task_id": "task-1",
        },
    )

    first_reason = service.admission_block_reason(task)
    second_reason = service.admission_block_reason(task)

    assert first_reason is not None
    assert second_reason is not None
    tasks = human_assist_service.list_tasks(chat_thread_id="thread-human-assist")
    assert len(tasks) == 1
    assert tasks[0].task_type == "host-handoff-return"
    assert tasks[0].reason_code == "host-handoff-active"
    assert tasks[0].resume_checkpoint_ref == "captcha-cleared"
    assert tasks[0].acceptance_spec["hard_anchors"] == ["captcha-cleared"]


def test_governance_admission_prefers_canonical_ready_host_twin_summary(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(
        control_repository=repository,
        environment_service=_FakeCanonicalReadyEnvironmentService(),
        human_assist_task_service=_FakeHumanAssistTaskService(),
        industry_service=_FakeIndustryService(),
    )

    task = KernelTask(
        title="Dispatch browser work",
        capability_ref="system:dispatch_query",
        environment_ref="session:web:canonical",
        payload={
            "chat_thread_id": "thread-canonical",
        },
    )

    reason = service.admission_block_reason(task)

    assert reason is None


def test_governance_status_prefers_canonical_ready_host_twin_summary(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(
        control_repository=repository,
        environment_service=_FakeCanonicalReadyEnvironmentService(),
        human_assist_task_service=_FakeHumanAssistTaskService(),
        industry_service=_FakeIndustryService(),
    )

    status = service.get_status()

    assert status.handoff["active"] is False
    assert status.handoff["session_ids"] == []
