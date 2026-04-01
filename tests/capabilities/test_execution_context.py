# -*- coding: utf-8 -*-
from __future__ import annotations

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
