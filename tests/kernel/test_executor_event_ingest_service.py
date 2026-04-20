# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from copaw.kernel.executor_runtime_port import ExecutorNormalizedEvent
from copaw.kernel.executor_event_ingest_service import (
    ExecutorEventIngestContext,
    ExecutorEventIngestService,
)


def _context(**overrides: object) -> ExecutorEventIngestContext:
    base = {
        "runtime_id": "runtime-1",
        "executor_id": "codex",
        "assignment_id": "assignment-1",
        "task_id": "task-1",
        "industry_instance_id": "industry-1",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "owner_agent_id": "agent-1",
        "owner_role_id": "role-1",
        "assignment_title": "Ship Task 5",
        "assignment_summary": "Implement executor event ingest",
        "risk_level": "guarded",
    }
    base.update(overrides)
    return ExecutorEventIngestContext(**base)


def test_ingest_plan_event_returns_executor_event_record_only() -> None:
    service = ExecutorEventIngestService()
    result = service.ingest_event(
        context=_context(),
        event=ExecutorNormalizedEvent(
            event_type="plan_submitted",
            source_type="plan",
            payload={
                "plan_summary": "Inspect runtime state and emit Task 5 payloads",
                "steps": ["inspect", "normalize", "report"],
            },
            raw_method="turn/plan/updated",
        ),
    )

    assert result.event_record.projection_kind == "plan"
    assert result.event_record.summary == "Inspect runtime state and emit Task 5 payloads"
    assert result.event_record.assignment_id == "assignment-1"
    assert result.event_record.runtime_id == "runtime-1"
    assert result.event_record.payload["steps"] == ["inspect", "normalize", "report"]
    assert result.evidence_payload is None
    assert result.report_payload is None


@pytest.mark.parametrize(
    ("source_type", "payload", "expected_kind", "action_fragment", "result_fragment"),
    [
        (
            "commandExecution",
            {
                "command": "pytest tests/kernel/test_executor_event_ingest_service.py -q",
                "exit_code": 0,
                "status": "completed",
            },
            "executor-command",
            "pytest tests/kernel/test_executor_event_ingest_service.py -q",
            "exit code 0",
        ),
        (
            "fileChange",
            {
                "path": "src/copaw/kernel/executor_event_ingest_service.py",
                "change_type": "modified",
                "summary": "Added ingest service",
            },
            "executor-file-change",
            "src/copaw/kernel/executor_event_ingest_service.py",
            "Added ingest service",
        ),
        (
            "mcpToolCall",
            {
                "tool_name": "filesystem.read_file",
                "server_name": "workspace",
                "status": "ok",
            },
            "executor-mcp-call",
            "filesystem.read_file",
            "workspace",
        ),
    ],
)
def test_ingest_evidence_events_builds_evidence_payloads(
    source_type: str,
    payload: dict[str, object],
    expected_kind: str,
    action_fragment: str,
    result_fragment: str,
) -> None:
    service = ExecutorEventIngestService()
    result = service.ingest_event(
        context=_context(),
        event=ExecutorNormalizedEvent(
            event_type="evidence_emitted",
            source_type=source_type,
            payload=payload,
            raw_method="item/completed",
        ),
    )

    assert result.event_record.projection_kind == "evidence"
    assert result.report_payload is None
    assert result.evidence_payload is not None
    assert result.evidence_payload["task_id"] == "task-1"
    assert result.evidence_payload["actor_ref"] == "executor:codex"
    assert result.evidence_payload["capability_ref"] == "executor:codex"
    assert result.evidence_payload["risk_level"] == "guarded"
    assert result.evidence_payload["kind"] == expected_kind
    assert action_fragment in result.evidence_payload["action_summary"]
    assert result_fragment in result.evidence_payload["result_summary"]
    assert result.evidence_payload["metadata"]["assignment_id"] == "assignment-1"
    assert result.evidence_payload["metadata"]["executor_runtime_id"] == "runtime-1"
    assert result.evidence_payload["metadata"]["executor_raw_method"] == "item/completed"


@pytest.mark.parametrize(
    ("event_type", "payload", "expected_result", "needs_followup", "summary_fragment", "uncertainty_fragment"),
    [
        (
            "task_completed",
            {"summary": "Drafted the patch and focused tests passed."},
            "completed",
            False,
            "Drafted the patch",
            None,
        ),
        (
            "task_failed",
            {"error": "pytest failed due to missing task context"},
            "failed",
            True,
            "pytest failed due to missing task context",
            "pytest failed due to missing task context",
        ),
    ],
)
def test_ingest_terminal_events_builds_report_payloads(
    event_type: str,
    payload: dict[str, object],
    expected_result: str,
    needs_followup: bool,
    summary_fragment: str,
    uncertainty_fragment: str | None,
) -> None:
    service = ExecutorEventIngestService()
    result = service.ingest_event(
        context=_context(),
        event=ExecutorNormalizedEvent(
            event_type=event_type,
            source_type="turn",
            payload=payload,
            raw_method=f"turn/{expected_result}",
        ),
    )

    assert result.event_record.projection_kind == "report"
    assert result.evidence_payload is None
    assert result.report_payload is not None
    assert result.report_payload["industry_instance_id"] == "industry-1"
    assert result.report_payload["assignment_id"] == "assignment-1"
    assert result.report_payload["task_id"] == "task-1"
    assert result.report_payload["owner_agent_id"] == "agent-1"
    assert result.report_payload["owner_role_id"] == "role-1"
    assert result.report_payload["report_kind"] == "executor-terminal"
    assert result.report_payload["result"] == expected_result
    assert result.report_payload["needs_followup"] is needs_followup
    assert summary_fragment in result.report_payload["summary"]
    assert "Ship Task 5" in result.report_payload["headline"]
    if expected_result == "completed":
        assert summary_fragment in result.report_payload["findings"][0]
        assert result.report_payload["uncertainties"] == []
    else:
        assert result.report_payload["findings"] == []
        assert uncertainty_fragment in result.report_payload["uncertainties"][0]


def test_ingest_evidence_event_without_task_context_skips_evidence_payload() -> None:
    service = ExecutorEventIngestService()
    result = service.ingest_event(
        context=_context(task_id=None),
        event=ExecutorNormalizedEvent(
            event_type="evidence_emitted",
            source_type="commandExecution",
            payload={"command": "git status", "exit_code": 0},
            raw_method="item/completed",
        ),
    )

    assert result.event_record.projection_kind == "evidence"
    assert result.evidence_payload is None
    assert result.report_payload is None


def test_ingest_unknown_event_keeps_generic_event_without_secondary_payloads() -> None:
    service = ExecutorEventIngestService()
    result = service.ingest_event(
        context=_context(),
        event=ExecutorNormalizedEvent(
            event_type="turn_progressed",
            source_type="turn",
            payload={"message": "Executor still running"},
            raw_method="turn/progress",
        ),
    )

    assert result.event_record.projection_kind == "generic"
    assert result.event_record.summary == "Executor still running"
    assert result.evidence_payload is None
    assert result.report_payload is None
