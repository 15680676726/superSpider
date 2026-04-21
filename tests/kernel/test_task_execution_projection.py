# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.task_execution_projection import (
    build_child_run_resume_payload,
    is_visible_execution_inflight,
    resolve_visible_execution_phase,
)


def test_resolve_visible_execution_phase_normalizes_existing_runtime_mailbox_and_task_statuses() -> None:
    assert resolve_visible_execution_phase(mailbox_status="queued") == "queued"
    assert resolve_visible_execution_phase(mailbox_status="leased") == "claimed"
    assert resolve_visible_execution_phase(mailbox_status="running") == "executing"
    assert resolve_visible_execution_phase(mailbox_status="blocked") == "waiting-confirm"
    assert resolve_visible_execution_phase(runtime_phase="risk-check") == "queued"
    assert resolve_visible_execution_phase(runtime_phase="executing") == "executing"
    assert resolve_visible_execution_phase(runtime_status="active") == "executing"
    assert resolve_visible_execution_phase(task_status="needs-confirm") == "waiting-confirm"
    assert resolve_visible_execution_phase(task_status="cancelled") == "cancelled"
    assert is_visible_execution_inflight("queued") is True
    assert is_visible_execution_inflight("claimed") is True
    assert is_visible_execution_inflight("executing") is True
    assert is_visible_execution_inflight("waiting-confirm") is True
    assert is_visible_execution_inflight("completed") is False


def test_resolve_visible_execution_phase_does_not_promote_cold_runtime_tasks_to_queued() -> None:
    assert (
        resolve_visible_execution_phase(
            runtime_status="cold",
            task_status="created",
        )
        is None
    )
    assert (
        resolve_visible_execution_phase(
            runtime_status="terminated",
            task_status="queued",
        )
        is None
    )


def test_build_child_run_resume_payload_preserves_continuity_fields() -> None:
    mailbox_item = SimpleNamespace(
        id="mailbox-1",
        agent_id="worker-1",
        source_agent_id="execution-core-agent",
        capability_ref="system:dispatch_query",
        work_context_id="work-1",
        conversation_thread_id="agent-chat:worker-1",
        metadata={
            "parent_task_id": "task-parent",
            "assignment_id": "assignment-1",
            "lane_id": "lane-1",
            "cycle_id": "cycle-1",
            "report_back_mode": "agent-report",
            "environment_ref": "session:console:shared",
            "industry_instance_id": "industry-1",
            "industry_role_id": "ops-worker",
            "execution_source": "delegation-compat",
            "access_mode": "shared-write",
            "lease_class": "writer",
            "writer_lock_scope": "workbook:weekly-report",
        },
        payload={
            "request_context": {
                "session_id": "industry-chat:industry-1:execution-core",
                "context_key": "control-thread:industry-1",
                "work_context_id": "work-1",
            },
            "meta": {
                "assignment_id": "assignment-shadow",
                "lane_id": "lane-shadow",
                "cycle_id": "cycle-shadow",
                "report_back_mode": "shadow-report",
                "environment_ref": "session:shadow",
            },
        },
    )

    payload = build_child_run_resume_payload(
        mailbox_item=mailbox_item,
        task_id="task-child",
        phase="waiting-confirm",
    )

    assert payload == {
        "mailbox_id": "mailbox-1",
        "task_id": "task-child",
        "phase": "waiting-confirm",
        "agent_id": "worker-1",
        "source_agent_id": "execution-core-agent",
        "capability_ref": "system:dispatch_query",
        "work_context_id": "work-1",
        "conversation_thread_id": "agent-chat:worker-1",
        "session_id": "industry-chat:industry-1:execution-core",
        "control_thread_id": "control-thread:industry-1",
        "assignment_id": "assignment-1",
        "lane_id": "lane-1",
        "cycle_id": "cycle-1",
        "report_back_mode": "agent-report",
        "parent_task_id": "task-parent",
        "environment_ref": "session:console:shared",
        "industry_instance_id": "industry-1",
        "industry_role_id": "ops-worker",
        "execution_source": "delegation-compat",
        "access_mode": "shared-write",
        "lease_class": "writer",
        "writer_lock_scope": "workbook:weekly-report",
    }
