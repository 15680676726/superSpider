# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from copaw.app.runtime_center.task_review_projection import serialize_child_rollup
from copaw.state import TaskRecord, TaskRuntimeRecord


def test_serialize_child_rollup_defaults_formal_surface_without_kernel_payload() -> None:
    timestamp = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    task = TaskRecord(
        id="task-no-kernel-payload",
        title="Collect screenshots",
        summary="Capture the latest storefront screenshots.",
        task_type="system:dispatch_query",
        status="running",
        owner_agent_id="ops-agent",
        created_at=timestamp,
        updated_at=timestamp,
    )
    runtime = TaskRuntimeRecord(
        task_id=task.id,
        runtime_status="active",
        current_phase="executing",
        risk_level="guarded",
        last_result_summary="Runtime owner took over the storefront review.",
        last_owner_agent_id="runtime-owner",
        updated_at=timestamp,
    )

    rollup = serialize_child_rollup(
        task,
        runtime,
        owner_agent={"agent_id": "runtime-owner", "name": "Runtime Owner"},
        work_context={"id": "ctx-1", "context_key": "control-thread:runtime-owner"},
    )

    assert rollup["id"] == "task-no-kernel-payload"
    assert rollup["summary"] == "Runtime owner took over the storefront review."
    assert rollup["owner_agent_name"] == "Runtime Owner"
    assert rollup["formal_surface"] is True
    assert "execution_source" not in rollup
    assert "compatibility_mode" not in rollup
