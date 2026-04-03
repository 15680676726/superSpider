# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.capabilities.execution_context import CapabilityExecutionContext


def test_execution_context_keeps_existing_kernel_identity_fields() -> None:
    context = CapabilityExecutionContext(
        task_id="ktask:test",
        goal_id="goal:test",
        owner_agent_id="execution-core",
        capability_ref="tool:read_file",
        environment_ref="session:console:test",
        risk_level="guarded",
    )

    assert context.task_id == "ktask:test"
    assert context.goal_id == "goal:test"
    assert context.owner_agent_id == "execution-core"
    assert context.capability_ref == "tool:read_file"
    assert context.environment_ref == "session:console:test"
    assert context.risk_level == "guarded"


def test_execution_context_marks_read_actions_as_read_only() -> None:
    context = CapabilityExecutionContext(
        task_id="ktask:test",
        capability_ref="tool:read_file",
        action_mode="read",
    )

    assert context.is_read_only is True


def test_execution_context_carries_contract_fields() -> None:
    context = CapabilityExecutionContext(
        task_id="ktask:test",
        capability_ref="tool:read_file",
        action_mode="read",
        concurrency_class="parallel-read",
        preflight_policy="inline",
        evidence_mode="tool-bridge",
    )

    assert context.concurrency_class == "parallel-read"
    assert context.preflight_policy == "inline"
    assert context.evidence_mode == "tool-bridge"


def test_execution_context_tracks_writer_lock_discipline_for_writes() -> None:
    task = SimpleNamespace(
        id="ktask:test",
        trace_id="trace:test",
        goal_id="goal:test",
        work_context_id="work:test",
        owner_agent_id="execution-core",
        capability_ref="tool:write_file",
        environment_ref="session:console:test",
        risk_level="guarded",
    )

    context = CapabilityExecutionContext.from_kernel_task(
        task,
        action_mode="write",
        concurrency_class="serial-write",
        writer_lock_scope="file:C:/tmp/report.txt",
        writer_lock_required=True,
        payload={"file_path": "C:/tmp/report.txt"},
    )

    assert context.is_read_only is False
    assert context.trace_id == "trace:test"
    assert context.work_context_id == "work:test"
    assert context.concurrency_class == "serial-write"
    assert context.writer_lock_scope == "file:C:/tmp/report.txt"
    assert context.writer_lock_required is True
