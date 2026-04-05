# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.memory.knowledge_writeback_service import KnowledgeWritebackService
from copaw.state import AgentReportRecord


def _report(
    *,
    headline: str = "Warehouse approval review",
    result: str = "completed",
    findings: list[str] | None = None,
    uncertainties: list[str] | None = None,
    recommendation: str | None = None,
    evidence_ids: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> AgentReportRecord:
    return AgentReportRecord(
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        cycle_id="cycle-1",
        assignment_id="assignment-1",
        lane_id="lane-ops",
        owner_agent_id="agent-a",
        owner_role_id="role:agent-a",
        headline=headline,
        summary=f"{headline} summary",
        result=result,
        findings=list(findings or []),
        uncertainties=list(uncertainties or []),
        recommendation=recommendation,
        evidence_ids=list(evidence_ids or []),
        metadata=dict(metadata or {}),
    )


def test_knowledge_writeback_service_builds_report_writeback_with_fact_opinion_evidence_and_relations() -> None:
    service = KnowledgeWritebackService()
    report = _report(
        findings=["Warehouse approval is verified."],
        recommendation="Keep the release paused until finance handoff clears.",
        evidence_ids=["evidence-1"],
        metadata={"verified_findings": True},
    )

    change = service.build_report_writeback(report=report)

    assert change.scope.scope_type == "work_context"
    assert change.scope.scope_id == "ctx-1"
    assert {"report", "event", "fact", "opinion", "evidence"} <= {
        item.node_type
        for item in change.upsert_nodes
    }
    assert {"produces", "derived_from"} <= {
        item.relation_type
        for item in change.upsert_relations
    }


def test_knowledge_writeback_service_downgrades_unverified_report_findings_to_opinion() -> None:
    service = KnowledgeWritebackService()
    report = _report(
        findings=["Weekend anomaly probably came from the staffing change."],
        metadata={"verified_findings": False},
    )

    change = service.build_report_writeback(report=report)
    finding_nodes = [
        item
        for item in change.upsert_nodes
        if item.node_id.startswith(f"report-finding:{report.id}:")
    ]

    assert finding_nodes
    assert {item.node_type for item in finding_nodes} == {"opinion"}


def test_knowledge_writeback_service_builds_failure_and_recovery_patterns_from_execution_outcome() -> None:
    service = KnowledgeWritebackService()

    change = service.build_execution_outcome_writeback(
        scope_type="task",
        scope_id="task-1",
        outcome_ref="runtime-1",
        outcome="failed",
        summary="Filesystem sync failed on permission error.",
        capability_ref="filesystem",
        evidence_refs=["evidence-1"],
        recovery_summary="Retry after refreshing the workspace lease.",
    )

    assert {"runtime_outcome", "failure_pattern", "recovery_pattern"} <= {
        item.node_type
        for item in change.upsert_nodes
    }
    assert {"indicates", "recovers_with"} <= {
        item.relation_type
        for item in change.upsert_relations
    }


def test_knowledge_writeback_service_keeps_human_boundary_writeback_out_of_fact_layer() -> None:
    service = KnowledgeWritebackService()

    change = service.build_human_boundary_writeback(
        scope_type="industry",
        scope_id="industry-1",
        boundary_kind="approval",
        summary="Operator approved the vendor outreach trial.",
        evidence_refs=["evidence-1"],
        source_refs=["decision:approval-1"],
    )

    assert [item.node_type for item in change.upsert_nodes] == ["approval"]
    assert all(item.node_type != "fact" for item in change.upsert_nodes)
