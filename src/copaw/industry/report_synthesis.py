# -*- coding: utf-8 -*-
from __future__ import annotations

from hashlib import sha1
from typing import Any, Sequence

from ..state import AgentReportRecord

_SUCCESS_RESULTS = {"completed", "success"}
_FAILED_RESULTS = {"blocked", "cancelled", "failed"}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _iso_datetime(value: object | None) -> str | None:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return None


def _report_topic_key(report: AgentReportRecord) -> str | None:
    metadata = report.metadata if isinstance(report.metadata, dict) else {}
    return (
        _string(metadata.get("claim_key"))
        or _string(report.goal_id)
        or _string(report.lane_id)
        or _string(report.assignment_id)
    )


def _result_bucket(report: AgentReportRecord) -> str | None:
    result = (_string(report.result) or _string(report.status) or "").lower()
    if result in _SUCCESS_RESULTS:
        return "success"
    if result in _FAILED_RESULTS:
        return "failure"
    return result or None


def _latest_findings(reports: Sequence[AgentReportRecord]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for report in reports:
        findings.append(
            {
                "report_id": report.id,
                "cycle_id": report.cycle_id,
                "assignment_id": report.assignment_id,
                "goal_id": report.goal_id,
                "task_id": report.task_id,
                "lane_id": report.lane_id,
                "owner_agent_id": report.owner_agent_id,
                "owner_role_id": report.owner_role_id,
                "headline": report.headline,
                "summary": report.summary,
                "status": report.status,
                "result": report.result,
                "findings": list(report.findings or []),
                "uncertainties": list(report.uncertainties or []),
                "recommendation": report.recommendation,
                "needs_followup": bool(report.needs_followup),
                "followup_reason": report.followup_reason,
                "updated_at": _iso_datetime(report.updated_at),
            },
        )
    return findings


def _detect_conflicts(reports: Sequence[AgentReportRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[AgentReportRecord]] = {}
    for report in reports:
        topic_key = _report_topic_key(report)
        if topic_key is None:
            continue
        grouped.setdefault(topic_key, []).append(report)
    conflicts: list[dict[str, Any]] = []
    for topic_key, topic_reports in grouped.items():
        buckets = {_result_bucket(report) for report in topic_reports if _result_bucket(report)}
        if not {"success", "failure"}.issubset(buckets):
            continue
        report_ids = sorted(report.id for report in topic_reports)
        digest = sha1("|".join(report_ids).encode("utf-8")).hexdigest()[:12]
        conflicts.append(
            {
                "conflict_id": f"result-mismatch:{digest}",
                "kind": "result-mismatch",
                "topic_key": topic_key,
                "summary": f"Reports disagree on {topic_key}.",
                "report_ids": report_ids,
                "owner_agent_ids": sorted(
                    {
                        owner_agent_id
                        for report in topic_reports
                        if (owner_agent_id := _string(report.owner_agent_id)) is not None
                    }
                ),
            },
        )
    return conflicts


def _build_report_action(
    report: AgentReportRecord,
    *,
    source_ref: str,
    synthesis_kind: str,
) -> dict[str, Any]:
    return {
        "action_id": f"follow-up:{report.id}",
        "action_type": "follow-up-backlog",
        "title": f"Follow up: {report.headline}",
        "summary": report.summary,
        "priority": 4,
        "lane_id": report.lane_id,
        "source_ref": source_ref,
        "metadata": {
            "source_report_id": report.id,
            "source_report_ids": [report.id],
            "owner_agent_id": report.owner_agent_id,
            "industry_role_id": report.owner_role_id,
            "report_back_mode": "summary",
            "synthesis_kind": synthesis_kind,
        },
    }


def _detect_holes_and_actions(
    reports: Sequence[AgentReportRecord],
    conflicts: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    holes: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    seen_source_refs: set[str] = set()
    seen_issue_keys: set[str] = set()
    for report in reports:
        result = (_string(report.result) or "").lower()
        issue_key = _report_topic_key(report) or report.id
        if result in _FAILED_RESULTS:
            if issue_key in seen_issue_keys:
                continue
            seen_issue_keys.add(issue_key)
            holes.append(
                {
                    "hole_id": f"failed-report:{report.id}",
                    "kind": "failed-report",
                    "report_id": report.id,
                    "summary": f"{report.headline} requires main-brain follow-up.",
                },
            )
            action = _build_report_action(
                report,
                source_ref=f"agent-report:{report.id}",
                synthesis_kind="failed-report",
            )
            if action["source_ref"] not in seen_source_refs:
                seen_source_refs.add(action["source_ref"])
                actions.append(action)
            continue
        if report.needs_followup or _string(report.followup_reason):
            if issue_key in seen_issue_keys:
                continue
            seen_issue_keys.add(issue_key)
            holes.append(
                {
                    "hole_id": f"followup-needed:{report.id}",
                    "kind": "followup-needed",
                    "report_id": report.id,
                    "summary": _string(report.followup_reason)
                    or f"{report.headline} still needs follow-up.",
                },
            )
            action = _build_report_action(
                report,
                source_ref=f"agent-report-followup:{report.id}",
                synthesis_kind="followup-needed",
            )
            if action["source_ref"] not in seen_source_refs:
                seen_source_refs.add(action["source_ref"])
                actions.append(action)
    for conflict in conflicts:
        conflict_id = _string(conflict.get("conflict_id"))
        if conflict_id is None:
            continue
        holes.append(
            {
                "hole_id": f"conflict:{conflict_id}",
                "kind": "conflict",
                "report_ids": list(conflict.get("report_ids") or []),
                "summary": _string(conflict.get("summary")) or "Reports conflict.",
            },
        )
        source_ref = f"report-synthesis:{conflict_id}"
        if source_ref in seen_source_refs:
            continue
        seen_source_refs.add(source_ref)
        actions.append(
            {
                "action_id": f"resolve-conflict:{conflict_id}",
                "action_type": "follow-up-backlog",
                "title": "Resolve report conflict",
                "summary": _string(conflict.get("summary")) or "Reports conflict.",
                "priority": 4,
                "lane_id": None,
                "source_ref": source_ref,
                "metadata": {
                    "source_report_ids": list(conflict.get("report_ids") or []),
                    "report_back_mode": "summary",
                    "synthesis_kind": "conflict",
                },
            },
        )
    return holes, actions


def synthesize_reports(reports: Sequence[AgentReportRecord]) -> dict[str, Any]:
    normalized_reports = [
        report for report in reports if isinstance(report, AgentReportRecord)
    ]
    conflicts = _detect_conflicts(normalized_reports)
    holes, recommended_actions = _detect_holes_and_actions(
        normalized_reports,
        conflicts,
    )
    replan_reasons: list[str] = []
    seen_replan_reasons: set[str] = set()
    for summary in [
        *(_string(conflict.get("summary")) for conflict in conflicts),
        *(_string(hole.get("summary")) for hole in holes),
    ]:
        if summary is None or summary in seen_replan_reasons:
            continue
        seen_replan_reasons.add(summary)
        replan_reasons.append(summary)
    return {
        "latest_findings": _latest_findings(normalized_reports),
        "conflicts": conflicts,
        "holes": holes,
        "recommended_actions": recommended_actions,
        "replan_reasons": replan_reasons,
        "needs_replan": bool(conflicts or holes or recommended_actions),
    }
