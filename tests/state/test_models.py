# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timezone

import pytest
from pydantic import ValidationError

from copaw.state.models import (
    DecisionRequestRecord,
    GoalRecord,
    TaskRecord,
    TaskRuntimeRecord,
)


def test_goal_record_defaults_to_phase1_safe_values() -> None:
    record = GoalRecord(title="Phase 1 state foundation")

    assert record.status == "draft"
    assert record.priority == 0
    assert record.summary == ""
    assert record.owner_scope is None
    assert record.created_at == record.updated_at
    assert record.created_at.tzinfo == timezone.utc


def test_task_record_requires_non_empty_title() -> None:
    with pytest.raises(ValidationError):
        TaskRecord(task_type="refactor", title="   ")


def test_task_runtime_defaults_are_utc_and_low_risk() -> None:
    runtime = TaskRuntimeRecord(task_id="task-1")

    assert runtime.runtime_status == "cold"
    assert runtime.current_phase == "created"
    assert runtime.risk_level == "auto"
    assert runtime.updated_at.tzinfo == timezone.utc


def test_decision_request_auto_populates_terminal_resolution_time() -> None:
    decision = DecisionRequestRecord(
        task_id="task-1",
        decision_type="approve-external-action",
        summary="Need approval before external write.",
        status="approved",
    )

    assert decision.risk_level == "confirm"
    assert decision.resolved_at == decision.created_at


def test_decision_request_rejects_unknown_risk_level() -> None:
    with pytest.raises(ValidationError):
        DecisionRequestRecord(
            task_id="task-1",
            decision_type="approve-external-action",
            summary="Need approval before external write.",
            risk_level="high",  # type: ignore[arg-type]
        )
