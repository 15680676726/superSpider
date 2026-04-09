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


class _FakeStaleTopLevelSummaryEnvironmentService:
    def list_sessions(self, **kwargs):
        _ = kwargs
        return [SimpleNamespace(id="session:web:stale-top-level")]

    def get_session_detail(self, session_mount_id: str, *, limit: int = 20):
        _ = limit
        if session_mount_id != "session:web:stale-top-level":
            return None
        return {
            "session_mount_id": session_mount_id,
            "host_twin_summary": {
                "recommended_scheduler_action": "handoff",
                "blocked_surface_count": 1,
                "legal_recovery_mode": "handoff",
                "continuity_state": "blocked",
            },
            "host_twin": {
                "continuity": {
                    "status": "attached",
                    "valid": True,
                    "requires_human_return": False,
                },
                "coordination": {
                    "recommended_scheduler_action": "proceed",
                },
                "legal_recovery": {
                    "path": "resume-environment",
                    "resume_kind": "resume-environment",
                },
                "blocked_surfaces": [],
            },
        }


class _FakeFreshDetachedEnvironmentService:
    def list_sessions(self, **kwargs):
        _ = kwargs
        return [
            SimpleNamespace(
                id="session:console:industry-chat:buddy:profile-1:domain-stock:execution-core",
            ),
        ]

    def get_session_detail(self, session_mount_id: str, *, limit: int = 20):
        _ = limit
        if (
            session_mount_id
            != "session:console:industry-chat:buddy:profile-1:domain-stock:execution-core"
        ):
            return None
        return {
            "session_mount_id": session_mount_id,
            "host_twin": {
                "continuity": {
                    "status": "blocked",
                    "valid": False,
                    "requires_human_return": False,
                },
                "coordination": {
                    "recommended_scheduler_action": "proceed",
                },
                "legal_recovery": {
                    "path": "fresh",
                    "resume_kind": "fresh",
                },
                "blocked_surfaces": [],
            },
        }


class _FakeBuddyThreadFallbackEnvironmentService:
    def list_sessions(self, **kwargs):
        _ = kwargs
        return [
            SimpleNamespace(
                id="session:console:industry:buddy:profile-1:domain-stock",
            ),
        ]

    def get_session_detail(self, session_mount_id: str, *, limit: int = 20):
        _ = limit
        if session_mount_id != "session:console:industry:buddy:profile-1:domain-stock":
            return None
        return {
            "session_mount_id": session_mount_id,
            "host_twin": {
                "continuity": {"requires_human_return": True},
                "ownership": {"handoff_owner_ref": "human-operator:alice"},
                "coordination": {"recommended_scheduler_action": "handoff"},
                "legal_recovery": {
                    "path": "handoff",
                    "resume_kind": "resume-runtime",
                    "return_condition": "checkpoint:stock",
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


def test_governance_status_exposes_decision_provenance_summary(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    decision_repository = SimpleNamespace(
        list_decision_requests=lambda: [
            SimpleNamespace(
                status="open",
                decision_type="tool-confirmation",
                risk_level="confirm",
                requested_by="execution-core",
            ),
            SimpleNamespace(
                status="reviewing",
                decision_type="tool-confirmation",
                risk_level="confirm",
                requested_by="execution-core",
            ),
            SimpleNamespace(
                status="open",
                decision_type="staffing-confirmation",
                risk_level="guarded",
                requested_by="main-brain",
            ),
            SimpleNamespace(
                status="approved",
                decision_type="ignored-terminal",
                risk_level="auto",
                requested_by="operator",
            ),
        ],
    )
    service = GovernanceService(
        control_repository=repository,
        decision_request_repository=decision_repository,
    )

    status = service.get_status()

    assert status.pending_decisions == 3
    assert status.decision_provenance["open_count"] == 3
    assert status.decision_provenance["by_type"] == [
        {"decision_type": "tool-confirmation", "count": 2},
        {"decision_type": "staffing-confirmation", "count": 1},
    ]
    assert status.decision_provenance["by_risk_level"] == [
        {"risk_level": "confirm", "count": 2},
        {"risk_level": "guarded", "count": 1},
    ]
    assert status.decision_provenance["by_requester"] == [
        {"requested_by": "execution-core", "count": 2},
        {"requested_by": "main-brain", "count": 1},
    ]


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


def test_governance_admission_prefers_derived_live_host_twin_over_stale_top_level_summary(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(
        control_repository=repository,
        environment_service=_FakeStaleTopLevelSummaryEnvironmentService(),
        human_assist_task_service=_FakeHumanAssistTaskService(),
        industry_service=_FakeIndustryService(),
    )

    task = KernelTask(
        title="Dispatch browser work after clean reentry",
        capability_ref="system:dispatch_query",
        environment_ref="session:web:stale-top-level",
        payload={
            "chat_thread_id": "thread-stale-top-level",
        },
    )

    reason = service.admission_block_reason(task)

    assert reason is None


def test_governance_admission_allows_writeback_only_query_through_handoff_gate(
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
        title="Write back backlog only",
        capability_ref="system:dispatch_query",
        environment_ref="session:web:main",
        payload={
            "chat_thread_id": "thread-writeback-only",
            "industry_instance_id": "industry-1",
            "request": {
                "requested_actions": ["writeback_backlog"],
            },
        },
    )

    reason = service.admission_block_reason(task)

    assert reason is None


def test_governance_admission_closes_stale_host_handoff_task_when_environment_no_longer_requires_return(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    human_assist_store = SQLiteStateStore(tmp_path / "human_assist.sqlite3")
    human_assist_service = HumanAssistTaskService(
        repository=SqliteHumanAssistTaskRepository(human_assist_store),
    )
    human_assist_service.ensure_host_handoff_task(
        chat_thread_id="industry-chat:buddy:profile-1:domain-stock:execution-core",
        title="Return host handoff",
        summary="Runtime handoff is active for the buddy execution thread.",
        required_action='Return after "fresh".',
        resume_checkpoint_ref="fresh",
        verification_anchor="fresh",
        block_evidence_refs=[
            "session:console:industry-chat:buddy:profile-1:domain-stock:execution-core",
        ],
        continuation_context={
            "session_id": "industry-chat:buddy:profile-1:domain-stock:execution-core",
            "control_thread_id": "industry-chat:buddy:profile-1:domain-stock:execution-core",
            "environment_ref": (
                "session:console:industry-chat:buddy:profile-1:domain-stock:execution-core"
            ),
            "recommended_scheduler_action": "handoff",
            "main_brain_runtime": {
                "environment_ref": (
                    "session:console:industry-chat:buddy:profile-1:domain-stock:execution-core"
                ),
                "recovery_mode": "fresh",
            },
        },
    )
    service = GovernanceService(
        control_repository=repository,
        environment_service=_FakeFreshDetachedEnvironmentService(),
        human_assist_task_service=human_assist_service,
        industry_service=_FakeIndustryService(),
    )

    task = KernelTask(
        title="Continue buddy execution chat",
        capability_ref="system:dispatch_query",
        environment_ref="session:console:industry-chat:buddy:profile-1:domain-stock:execution-core",
        payload={
            "chat_thread_id": "industry-chat:buddy:profile-1:domain-stock:execution-core",
            "session_id": "industry-chat:buddy:profile-1:domain-stock:execution-core",
            "control_thread_id": "industry-chat:buddy:profile-1:domain-stock:execution-core",
        },
    )

    reason = service.admission_block_reason(task)

    assert reason is None
    assert (
        human_assist_service.get_current_task(
            chat_thread_id="industry-chat:buddy:profile-1:domain-stock:execution-core",
        )
        is None
    )
    tasks = human_assist_service.list_tasks(
        chat_thread_id="industry-chat:buddy:profile-1:domain-stock:execution-core",
    )
    assert tasks[0].status == "closed"


def test_governance_admission_resolves_full_buddy_instance_id_from_control_thread(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(
        control_repository=repository,
        environment_service=_FakeBuddyThreadFallbackEnvironmentService(),
        human_assist_task_service=_FakeHumanAssistTaskService(),
        industry_service=_FakeIndustryService(),
    )

    task = KernelTask(
        title="Dispatch buddy control thread work",
        capability_ref="system:dispatch_query",
        payload={
            "chat_thread_id": "industry-chat:buddy:profile-1:domain-stock:execution-core",
            "control_thread_id": "industry-chat:buddy:profile-1:domain-stock:execution-core",
        },
    )

    reason = service.admission_block_reason(task)

    assert reason is not None
    assert "Runtime handoff is active" in reason


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
