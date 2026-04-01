# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from copaw.industry.report_synthesis import synthesize_reports
from copaw.memory.activation_models import ActivationResult, KnowledgeNeuron
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
    metadata: dict[str, Any] | None = None,
    updated_at: datetime | None = None,
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
        metadata=metadata or {},
        updated_at=updated_at,
    )


def _activation(
    *,
    top_constraints: list[str] | None = None,
    top_next_actions: list[str] | None = None,
    support_refs: list[str] | None = None,
    contradictions: list[KnowledgeNeuron] | None = None,
) -> ActivationResult:
    return ActivationResult(
        query="review report closure",
        scope_type="industry",
        scope_id="industry-1",
        top_constraints=top_constraints or [],
        top_next_actions=top_next_actions or [],
        support_refs=support_refs or [],
        contradictions=contradictions or [],
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


def test_synthesize_reports_collapses_duplicate_followups_for_the_same_claim() -> None:
    reports = [
        _report(
            headline="Warehouse variance review A",
            owner_agent_id="agent-a",
            lane_id="lane-ops",
            findings=["Warehouse variance still lacks a validated cause."],
            needs_followup=True,
            followup_reason="Warehouse variance still lacks a validated cause.",
            metadata={"claim_key": "warehouse-variance"},
        ),
        _report(
            headline="Warehouse variance review B",
            owner_agent_id="agent-b",
            lane_id="lane-ops",
            findings=["Warehouse variance still lacks a validated cause."],
            needs_followup=True,
            followup_reason="Warehouse variance still lacks a validated cause.",
            metadata={"claim_key": "warehouse-variance"},
        ),
    ]

    synthesis = synthesize_reports(reports)

    assert len(synthesis["holes"]) == 1
    assert synthesis["holes"][0]["kind"] == "followup-needed"
    assert len(synthesis["recommended_actions"]) == 1
    assert synthesis["recommended_actions"][0]["metadata"]["source_report_ids"] == [
        reports[0].id,
        reports[1].id,
    ]
    assert synthesis["replan_reasons"] == [
        "Warehouse variance still lacks a validated cause.",
    ]
    assert synthesis["needs_replan"] is True


def test_synthesize_reports_uses_latest_report_per_topic_and_clears_old_pressure() -> None:
    now = datetime.now(UTC)
    reports = [
        _report(
            headline="Warehouse variance review blocked",
            owner_agent_id="agent-a",
            assignment_id="assignment-warehouse",
            lane_id="lane-ops",
            result="failed",
            findings=["The warehouse variance root cause is still unclear."],
            uncertainties=["Missing weekend scanner logs kept the review incomplete."],
            recommendation="Collect the missing logs before replanning inventory controls.",
            metadata={"claim_key": "warehouse-variance"},
            updated_at=now - timedelta(hours=2),
        ),
        _report(
            headline="Warehouse variance review resolved",
            owner_agent_id="agent-a",
            assignment_id="assignment-warehouse",
            lane_id="lane-ops",
            result="completed",
            findings=["Weekend scanner logs were recovered and the variance was explained."],
            recommendation="Keep the existing inventory control policy.",
            metadata={"claim_key": "warehouse-variance"},
            updated_at=now,
        ),
    ]

    synthesis = synthesize_reports(reports)

    assert [entry["report_id"] for entry in synthesis["latest_findings"]] == [
        reports[1].id,
    ]
    assert synthesis["latest_findings"][0]["topic_key"] == "warehouse-variance"
    assert synthesis["conflicts"] == []
    assert synthesis["holes"] == []
    assert synthesis["recommended_actions"] == []
    assert synthesis["replan_reasons"] == []
    assert synthesis["replan_decision"] == {
        "decision_id": "report-synthesis:clear",
        "status": "clear",
        "summary": "No unresolved report synthesis pressure.",
        "reason_ids": [],
        "source_report_ids": [],
        "topic_keys": [],
    }
    assert synthesis["replan_directives"] == []
    assert synthesis["needs_replan"] is False


def test_synthesize_reports_surfaces_uncertainty_and_evidence_insufficiency() -> None:
    report = _report(
        headline="Weekend variance review completed",
        owner_agent_id="agent-a",
        lane_id="lane-support",
        findings=["Weekday response time stayed inside target."],
        uncertainties=["Weekend variance still lacks a validated cause."],
        recommendation="Run a weekend deep-dive before changing staffing.",
        metadata={
            "claim_key": "weekend-variance",
            "evidence_status": "insufficient",
        },
    )

    synthesis = synthesize_reports([report])

    assert synthesis["conflicts"] == []
    assert synthesis["holes"] == [
        {
            "hole_id": f"uncertainty:{report.id}",
            "kind": "uncertainty",
            "report_id": report.id,
            "topic_key": "weekend-variance",
            "summary": "Weekend variance still lacks a validated cause.",
        },
        {
            "hole_id": f"evidence-insufficient:{report.id}",
            "kind": "evidence-insufficient",
            "report_id": report.id,
            "topic_key": "weekend-variance",
            "summary": "Weekend variance review completed lacks enough evidence for a durable main-brain conclusion.",
        },
    ]
    assert synthesis["recommended_actions"] == []
    assert synthesis["replan_reasons"] == [
        "Weekend variance still lacks a validated cause.",
        "Weekend variance review completed lacks enough evidence for a durable main-brain conclusion.",
    ]
    assert synthesis["replan_decision"] == {
        "decision_id": f"report-synthesis:needs-replan:{report.id}",
        "status": "needs-replan",
        "summary": "2 unresolved report synthesis signals require main-brain judgment.",
        "reason_ids": [
            f"uncertainty:{report.id}",
            f"evidence-insufficient:{report.id}",
        ],
        "source_report_ids": [report.id],
        "topic_keys": ["weekend-variance"],
    }
    assert synthesis["replan_directives"] == [
        {
            "directive_id": f"replan-directive:uncertainty:{report.id}",
            "kind": "follow-up",
            "pressure_kind": "uncertainty",
            "topic_key": "weekend-variance",
            "summary": "Weekend variance still lacks a validated cause.",
            "source_report_ids": [report.id],
            "lane_id": "lane-support",
            "owner_agent_id": "agent-a",
            "recommended_action_id": None,
        },
        {
            "directive_id": f"replan-directive:evidence-insufficient:{report.id}",
            "kind": "follow-up",
            "pressure_kind": "evidence-insufficient",
            "topic_key": "weekend-variance",
            "summary": "Weekend variance review completed lacks enough evidence for a durable main-brain conclusion.",
            "source_report_ids": [report.id],
            "lane_id": "lane-support",
            "owner_agent_id": "agent-a",
            "recommended_action_id": None,
        },
    ]
    assert synthesis["needs_replan"] is True


def test_synthesize_reports_detects_recommendation_conflicts_and_builds_directives() -> None:
    reports = [
        _report(
            headline="Warehouse variance review recommends overtime",
            owner_agent_id="agent-a",
            assignment_id="assignment-shared",
            lane_id="lane-ops",
            result="completed",
            findings=["Weekend staffing was thin during the spike."],
            recommendation="Add overtime coverage this weekend.",
            metadata={"claim_key": "warehouse-variance"},
        ),
        _report(
            headline="Warehouse variance review recommends no staffing change",
            owner_agent_id="agent-b",
            assignment_id="assignment-shared",
            lane_id="lane-ops",
            result="completed",
            findings=["The spike was caused by delayed supplier postings."],
            recommendation="Do not change staffing until supplier latency is verified.",
            metadata={"claim_key": "warehouse-variance"},
        ),
    ]

    synthesis = synthesize_reports(reports)

    assert len(synthesis["conflicts"]) == 1
    conflict = synthesis["conflicts"][0]
    assert conflict == {
        "conflict_id": conflict["conflict_id"],
        "kind": "recommendation-mismatch",
        "topic_key": "warehouse-variance",
        "summary": "Reports recommend different next steps for warehouse-variance.",
        "report_ids": [reports[0].id, reports[1].id],
        "owner_agent_ids": ["agent-a", "agent-b"],
    }
    assert synthesis["holes"] == []
    assert synthesis["recommended_actions"] == [
        {
            "action_id": f"resolve-conflict:{conflict['conflict_id']}",
            "action_type": "follow-up-backlog",
            "title": "Resolve report conflict",
            "summary": "Reports recommend different next steps for warehouse-variance.",
            "priority": 4,
            "lane_id": None,
            "source_ref": f"report-synthesis:{conflict['conflict_id']}",
            "metadata": {
                "source_report_ids": [reports[0].id, reports[1].id],
                "report_back_mode": "summary",
                "synthesis_kind": "conflict",
            },
        },
    ]
    assert synthesis["replan_reasons"] == [
        "Reports recommend different next steps for warehouse-variance.",
    ]
    assert synthesis["replan_decision"] == {
        "decision_id": f"report-synthesis:needs-replan:{conflict['conflict_id']}",
        "status": "needs-replan",
        "summary": "1 unresolved report synthesis signal requires main-brain judgment.",
        "reason_ids": [conflict["conflict_id"]],
        "source_report_ids": [reports[0].id, reports[1].id],
        "topic_keys": ["warehouse-variance"],
    }
    assert synthesis["replan_directives"] == [
        {
            "directive_id": f"replan-directive:{conflict['conflict_id']}",
            "kind": "resolve-conflict",
            "pressure_kind": "recommendation-mismatch",
            "topic_key": "warehouse-variance",
            "summary": "Reports recommend different next steps for warehouse-variance.",
            "source_report_ids": [reports[0].id, reports[1].id],
            "lane_id": None,
            "owner_agent_ids": ["agent-a", "agent-b"],
            "recommended_action_id": f"resolve-conflict:{conflict['conflict_id']}",
        },
    ]
    assert synthesis["needs_replan"] is True


def test_synthesize_reports_includes_activation_constraints_in_replan_surface() -> None:
    report = _report(
        headline="Weekend variance review completed",
        owner_agent_id="agent-a",
        lane_id="lane-support",
        findings=["Weekday response time stayed inside target."],
    )
    activation = _activation(
        top_constraints=["Staffing changes still require validated weekend-cause evidence."],
        top_next_actions=["Validate the weekend-cause hypothesis before changing staffing."],
        support_refs=["activation:support:weekend-variance"],
    )

    synthesis = synthesize_reports([report], activation_result=activation)

    assert synthesis["activation"]["top_constraints"] == [
        "Staffing changes still require validated weekend-cause evidence.",
    ]
    assert synthesis["activation"]["top_next_actions"] == [
        "Validate the weekend-cause hypothesis before changing staffing.",
    ]
    assert synthesis["activation"]["support_refs"] == [
        "activation:support:weekend-variance",
    ]
    assert synthesis["replan_decision"]["status"] == "needs-replan"
    assert synthesis["needs_replan"] is True


def test_synthesize_reports_surfaces_activation_contradictions() -> None:
    report = _report(
        headline="Warehouse issue resolved",
        owner_agent_id="agent-a",
        goal_id="goal-shared",
        lane_id="lane-ops",
        result="completed",
        findings=["The warehouse issue is resolved."],
    )
    contradiction = KnowledgeNeuron(
        neuron_id="fact:industry-1:warehouse-approval",
        kind="fact",
        scope_type="industry",
        scope_id="industry-1",
        title="Warehouse approval conflict",
        summary="Recent memory says the missing approval blocker remains unresolved.",
    )
    activation = _activation(contradictions=[contradiction])

    synthesis = synthesize_reports([report], activation_result=activation)

    assert synthesis["activation"]["contradiction_count"] == 1
    assert synthesis["replan_decision"]["status"] == "needs-replan"
    assert synthesis["needs_replan"] is True
