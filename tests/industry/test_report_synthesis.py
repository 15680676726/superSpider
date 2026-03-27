# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from copaw.industry.report_synthesis import synthesize_reports
from copaw.state import AgentReportRecord


def _report(
    *,
    headline: str,
    owner_agent_id: str,
    result: str = "completed",
    assignment_id: str | None = None,
    goal_id: str | None = None,
    lane_id: str | None = None,
    findings: list[str] | None = None,
    uncertainties: list[str] | None = None,
    recommendation: str | None = None,
    needs_followup: bool = False,
    followup_reason: str | None = None,
) -> AgentReportRecord:
    return AgentReportRecord(
        industry_instance_id="industry-1",
        cycle_id="cycle-1",
        assignment_id=assignment_id,
        goal_id=goal_id,
        lane_id=lane_id,
        owner_agent_id=owner_agent_id,
        owner_role_id=f"role:{owner_agent_id}",
        headline=headline,
        summary=f"{headline} summary",
        result=result,
        findings=findings or [],
        uncertainties=uncertainties or [],
        recommendation=recommendation,
        needs_followup=needs_followup,
        followup_reason=followup_reason,
    )


def test_synthesize_reports_returns_clean_close_for_agreeing_reports() -> None:
    now = datetime.now(UTC)
    reports = [
        _report(
            headline="Inventory audit closed",
            owner_agent_id="agent-a",
            assignment_id="assignment-a",
            goal_id="goal-a",
            findings=["Inventory variance returned to baseline."],
        ).model_copy(update={"updated_at": now - timedelta(minutes=5)}),
        _report(
            headline="Support queue stabilized",
            owner_agent_id="agent-b",
            assignment_id="assignment-b",
            goal_id="goal-b",
            findings=["Ticket backlog stayed below the escalation threshold."],
        ).model_copy(update={"updated_at": now}),
    ]

    synthesis = synthesize_reports(reports)

    assert [entry["report_id"] for entry in synthesis["latest_findings"]] == [
        reports[0].id,
        reports[1].id,
    ]
    assert synthesis["conflicts"] == []
    assert synthesis["holes"] == []
    assert synthesis["recommended_actions"] == []
    assert synthesis["needs_replan"] is False


def test_synthesize_reports_emits_conflict_entry_for_conflicting_results() -> None:
    reports = [
        _report(
            headline="Warehouse issue resolved",
            owner_agent_id="agent-a",
            goal_id="goal-shared",
            lane_id="lane-ops",
            result="completed",
            findings=["The warehouse issue is resolved."],
        ),
        _report(
            headline="Warehouse issue still blocked",
            owner_agent_id="agent-b",
            goal_id="goal-shared",
            lane_id="lane-ops",
            result="failed",
            findings=["The warehouse issue is still blocked by missing approvals."],
        ),
    ]

    synthesis = synthesize_reports(reports)

    assert len(synthesis["conflicts"]) == 1
    conflict = synthesis["conflicts"][0]
    assert conflict["kind"] == "result-mismatch"
    assert set(conflict["report_ids"]) == {report.id for report in reports}
    assert synthesis["needs_replan"] is True


def test_synthesize_reports_turns_failed_report_into_replan_signal() -> None:
    report = _report(
        headline="Customer interview wave failed",
        owner_agent_id="agent-a",
        result="failed",
        lane_id="lane-research",
        uncertainties=["The interview recruiting list was incomplete."],
        recommendation="Rebuild the interview list before relaunching outreach.",
    )

    synthesis = synthesize_reports([report])

    assert synthesis["holes"] == [
        {
            "hole_id": f"failed-report:{report.id}",
            "kind": "failed-report",
            "report_id": report.id,
            "summary": "Customer interview wave failed requires main-brain follow-up.",
        },
    ]
    assert synthesis["recommended_actions"] == [
        {
            "action_id": f"follow-up:{report.id}",
            "action_type": "follow-up-backlog",
            "title": "Follow up: Customer interview wave failed",
            "summary": "Customer interview wave failed summary",
            "priority": 4,
            "lane_id": "lane-research",
            "source_ref": f"agent-report:{report.id}",
            "metadata": {
                "source_report_id": report.id,
                "source_report_ids": [report.id],
                "owner_agent_id": "agent-a",
                "industry_role_id": "role:agent-a",
                "report_back_mode": "summary",
                "synthesis_kind": "failed-report",
            },
        },
    ]
    assert synthesis["needs_replan"] is True


def test_synthesize_reports_keeps_needs_followup_visible() -> None:
    report = _report(
        headline="Weekend variance review completed",
        owner_agent_id="agent-a",
        lane_id="lane-support",
        findings=["Weekday response time stayed inside target."],
        needs_followup=True,
        followup_reason="Weekend variance still lacks a validated cause.",
        recommendation="Run a weekend deep-dive before changing staffing.",
    )

    synthesis = synthesize_reports([report])

    assert synthesis["latest_findings"][0]["report_id"] == report.id
    assert synthesis["latest_findings"][0]["needs_followup"] is True
    assert synthesis["holes"] == [
        {
            "hole_id": f"followup-needed:{report.id}",
            "kind": "followup-needed",
            "report_id": report.id,
            "summary": "Weekend variance still lacks a validated cause.",
        },
    ]
    assert synthesis["recommended_actions"][0]["source_ref"] == (
        f"agent-report-followup:{report.id}"
    )
    assert synthesis["needs_replan"] is True


def test_synthesize_reports_exposes_explicit_replan_reasons() -> None:
    reports = [
        _report(
            headline="Warehouse issue resolved",
            owner_agent_id="agent-a",
            assignment_id="assignment-shared",
            result="completed",
            findings=["The warehouse issue is resolved."],
        ),
        _report(
            headline="Warehouse issue still blocked",
            owner_agent_id="agent-b",
            assignment_id="assignment-shared",
            result="failed",
            findings=["The warehouse issue is still blocked by missing approvals."],
            recommendation="Escalate the missing approval blocker.",
        ),
    ]

    synthesis = synthesize_reports(reports)

    assert synthesis["needs_replan"] is True
    assert synthesis["replan_reasons"] == [
        "Reports disagree on assignment-shared.",
        "Warehouse issue still blocked requires main-brain follow-up.",
    ]
