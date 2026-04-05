# -*- coding: utf-8 -*-
from __future__ import annotations

from hashlib import sha1
from typing import Any, Sequence

from ..memory.knowledge_writeback_service import KnowledgeWritebackService
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


def _unique_strings(*collections: object) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for collection in collections:
        if isinstance(collection, str):
            items = [collection]
        elif isinstance(collection, Sequence):
            items = list(collection)
        else:
            items = []
        for item in items:
            text = _string(item)
            if text is None or text in seen:
                continue
            seen.add(text)
            values.append(text)
    return values


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


def _report_timestamp(report: AgentReportRecord) -> object:
    return report.updated_at or report.created_at or ""


def _owner_key(report: AgentReportRecord) -> str:
    return _string(report.owner_agent_id) or _string(report.owner_role_id) or report.id


def _latest_reports(reports: Sequence[AgentReportRecord]) -> list[AgentReportRecord]:
    latest_by_topic_owner: dict[tuple[str, str], AgentReportRecord] = {}
    passthrough_ids: set[str] = set()
    for report in reports:
        topic_key = _report_topic_key(report)
        if topic_key is None:
            passthrough_ids.add(report.id)
            continue
        key = (topic_key, _string(report.assignment_id) or report.id, _owner_key(report))
        current = latest_by_topic_owner.get(key)
        if current is None or _report_timestamp(report) >= _report_timestamp(current):
            latest_by_topic_owner[key] = report
    selected_ids = passthrough_ids | {report.id for report in latest_by_topic_owner.values()}
    return [report for report in reports if report.id in selected_ids]


def _latest_findings(reports: Sequence[AgentReportRecord]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for report in _latest_reports(reports):
        findings.append(
            {
                "report_id": report.id,
                "cycle_id": report.cycle_id,
                "assignment_id": report.assignment_id,
                "goal_id": report.goal_id,
                "task_id": report.task_id,
                "lane_id": report.lane_id,
                "topic_key": _report_topic_key(report),
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
    for report in _latest_reports(reports):
        topic_key = _report_topic_key(report)
        if topic_key is None:
            continue
        grouped.setdefault(topic_key, []).append(report)
    conflicts: list[dict[str, Any]] = []
    for topic_key, topic_reports in grouped.items():
        buckets = {_result_bucket(report) for report in topic_reports if _result_bucket(report)}
        report_ids = [report.id for report in topic_reports]
        owner_agent_ids = [owner for owner in (_string(report.owner_agent_id) for report in topic_reports) if owner is not None]
        if {"success", "failure"}.issubset(buckets):
            digest = sha1("|".join(report_ids).encode("utf-8")).hexdigest()[:12]
            conflicts.append(
                {
                    "conflict_id": f"result-mismatch:{digest}",
                    "kind": "result-mismatch",
                    "topic_key": topic_key,
                    "summary": f"Reports disagree on {topic_key}.",
                    "report_ids": report_ids,
                    "owner_agent_ids": sorted(set(owner_agent_ids)),
                },
            )
            continue
        recommendations = {
            recommendation
            for report in topic_reports
            if (recommendation := _string(report.recommendation)) is not None
        }
        if len(recommendations) > 1:
            digest = sha1("|".join(report_ids).encode("utf-8")).hexdigest()[:12]
            conflicts.append(
                {
                    "conflict_id": f"recommendation-mismatch:{digest}",
                    "kind": "recommendation-mismatch",
                    "topic_key": topic_key,
                    "summary": f"Reports recommend different next steps for {topic_key}.",
                    "report_ids": report_ids,
                    "owner_agent_ids": sorted(set(owner_agent_ids)),
                },
            )
    return conflicts


def _build_report_action(report: AgentReportRecord, *, source_ref: str, synthesis_kind: str) -> dict[str, Any]:
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


def _append_action_source_report_id(action: dict[str, Any], report_id: str | None) -> None:
    normalized_report_id = _string(report_id)
    if normalized_report_id is None:
        return
    metadata = action.get("metadata")
    if not isinstance(metadata, dict):
        return
    source_report_ids = [
        item
        for item in [_string(value) for value in (metadata.get("source_report_ids") if isinstance(metadata.get("source_report_ids"), list) else [])]
        if item is not None
    ]
    if normalized_report_id not in source_report_ids:
        source_report_ids.append(normalized_report_id)
    metadata["source_report_ids"] = source_report_ids
    if source_report_ids:
        metadata["source_report_id"] = source_report_ids[0]


def _detect_holes_and_actions(
    reports: Sequence[AgentReportRecord],
    conflicts: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    holes: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    directives: list[dict[str, Any]] = []
    seen_source_refs: set[str] = set()
    seen_issue_keys: set[str] = set()
    action_by_issue_key: dict[str, dict[str, Any]] = {}
    for report in _latest_reports(reports):
        result = (_string(report.result) or "").lower()
        issue_key = _report_topic_key(report) or report.id
        topic_key = _report_topic_key(report)
        if result in _FAILED_RESULTS:
            if issue_key in seen_issue_keys:
                existing_action = action_by_issue_key.get(issue_key)
                if isinstance(existing_action, dict):
                    _append_action_source_report_id(existing_action, report.id)
                continue
            seen_issue_keys.add(issue_key)
            hole = {
                "hole_id": f"failed-report:{report.id}",
                "kind": "failed-report",
                "report_id": report.id,
                "summary": f"{report.headline} requires main-brain follow-up.",
            }
            holes.append(hole)
            action = _build_report_action(report, source_ref=f"agent-report:{report.id}", synthesis_kind="failed-report")
            _append_action_source_report_id(action, report.id)
            action_by_issue_key[issue_key] = action
            if action["source_ref"] not in seen_source_refs:
                seen_source_refs.add(action["source_ref"])
                actions.append(action)
            directives.append(
                {
                    "directive_id": f"replan-directive:{hole['hole_id']}",
                    "kind": "follow-up",
                    "pressure_kind": "failed-report",
                    "topic_key": topic_key,
                    "summary": hole["summary"],
                    "source_report_ids": [report.id],
                    "lane_id": report.lane_id,
                    "owner_agent_id": report.owner_agent_id,
                    "recommended_action_id": action["action_id"],
                },
            )
            continue
        if report.needs_followup or _string(report.followup_reason):
            if issue_key in seen_issue_keys:
                existing_action = action_by_issue_key.get(issue_key)
                if isinstance(existing_action, dict):
                    _append_action_source_report_id(existing_action, report.id)
                continue
            seen_issue_keys.add(issue_key)
            summary = _string(report.followup_reason) or f"{report.headline} still needs follow-up."
            hole = {
                "hole_id": f"followup-needed:{report.id}",
                "kind": "followup-needed",
                "report_id": report.id,
                "summary": summary,
            }
            holes.append(hole)
            action = _build_report_action(report, source_ref=f"agent-report-followup:{report.id}", synthesis_kind="followup-needed")
            _append_action_source_report_id(action, report.id)
            action_by_issue_key[issue_key] = action
            if action["source_ref"] not in seen_source_refs:
                seen_source_refs.add(action["source_ref"])
                actions.append(action)
            directives.append(
                {
                    "directive_id": f"replan-directive:{hole['hole_id']}",
                    "kind": "follow-up",
                    "pressure_kind": "followup-needed",
                    "topic_key": topic_key,
                    "summary": summary,
                    "source_report_ids": [report.id],
                    "lane_id": report.lane_id,
                    "owner_agent_id": report.owner_agent_id,
                    "recommended_action_id": action["action_id"],
                },
            )
        for uncertainty in list(report.uncertainties or []):
            summary = _string(uncertainty)
            if summary is None:
                continue
            hole = {
                "hole_id": f"uncertainty:{report.id}",
                "kind": "uncertainty",
                "report_id": report.id,
                "topic_key": topic_key,
                "summary": summary,
            }
            if hole not in holes:
                holes.append(hole)
                directives.append(
                    {
                        "directive_id": f"replan-directive:{hole['hole_id']}",
                        "kind": "follow-up",
                        "pressure_kind": "uncertainty",
                        "topic_key": topic_key,
                        "summary": summary,
                        "source_report_ids": [report.id],
                        "lane_id": report.lane_id,
                        "owner_agent_id": report.owner_agent_id,
                        "recommended_action_id": None,
                    },
                )
        metadata = report.metadata if isinstance(report.metadata, dict) else {}
        if _string(metadata.get('evidence_status')) == 'insufficient':
            summary = f"{report.headline} lacks enough evidence for a durable main-brain conclusion."
            hole = {
                "hole_id": f"evidence-insufficient:{report.id}",
                "kind": "evidence-insufficient",
                "report_id": report.id,
                "topic_key": topic_key,
                "summary": summary,
            }
            holes.append(hole)
            directives.append(
                {
                    "directive_id": f"replan-directive:{hole['hole_id']}",
                    "kind": "follow-up",
                    "pressure_kind": "evidence-insufficient",
                    "topic_key": topic_key,
                    "summary": summary,
                    "source_report_ids": [report.id],
                    "lane_id": report.lane_id,
                    "owner_agent_id": report.owner_agent_id,
                    "recommended_action_id": None,
                },
            )
    for conflict in conflicts:
        conflict_id = _string(conflict.get("conflict_id"))
        if conflict_id is None:
            continue
        summary = _string(conflict.get("summary")) or "Reports conflict."
        source_report_ids = list(conflict.get("report_ids") or [])
        action = {
            "action_id": f"resolve-conflict:{conflict_id}",
            "action_type": "follow-up-backlog",
            "title": "Resolve report conflict",
            "summary": summary,
            "priority": 4,
            "lane_id": None,
            "source_ref": f"report-synthesis:{conflict_id}",
            "metadata": {
                "source_report_ids": source_report_ids,
                "report_back_mode": "summary",
                "synthesis_kind": "conflict",
            },
        }
        actions.append(action)
        directives.append(
            {
                "directive_id": f"replan-directive:{conflict_id}",
                "kind": "resolve-conflict",
                "pressure_kind": _string(conflict.get("kind")) or "conflict",
                "topic_key": _string(conflict.get("topic_key")),
                "summary": summary,
                "source_report_ids": source_report_ids,
                "lane_id": None,
                "owner_agent_ids": list(conflict.get("owner_agent_ids") or []),
                "recommended_action_id": action["action_id"],
            },
        )
    return holes, actions, directives


def _build_replan_decision(*, holes: list[dict[str, Any]], conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    return _build_replan_decision_with_activation(
        holes=holes,
        conflicts=conflicts,
        activation_reason_ids=[],
    )


def _build_activation_summary(
    activation_result: object | None,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    if activation_result is None:
        return None, [], []
    top_entities = _unique_strings(getattr(activation_result, "top_entities", None))
    top_opinions = _unique_strings(getattr(activation_result, "top_opinions", None))
    top_relations = _unique_strings(getattr(activation_result, "top_relations", None))
    top_relation_kinds = _unique_strings(
        getattr(activation_result, "top_relation_kinds", None),
    )
    top_constraints = _unique_strings(getattr(activation_result, "top_constraints", None))
    top_next_actions = _unique_strings(getattr(activation_result, "top_next_actions", None))
    support_refs = _unique_strings(getattr(activation_result, "support_refs", None))
    top_relation_evidence: list[dict[str, Any]] = []
    for item in list(getattr(activation_result, "top_relation_evidence", None) or []):
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            payload = model_dump(mode="json")
        elif isinstance(item, dict):
            payload = dict(item)
        else:
            payload = None
        if isinstance(payload, dict):
            top_relation_evidence.append(payload)
    contradictions = list(getattr(activation_result, "contradictions", []) or [])
    contradiction_count = len(contradictions)
    reasons: list[str] = []
    reason_ids: list[str] = []
    if contradiction_count:
        label = "contradiction" if contradiction_count == 1 else "contradictions"
        reasons.append(
            f"Activation recall surfaced {contradiction_count} {label} that require main-brain review.",
        )
        reason_ids.append("activation:contradictions")
    for index, constraint in enumerate(top_constraints):
        reasons.append(constraint)
        reason_ids.append(f"activation:constraint:{index}")
    return (
        {
            "top_entities": top_entities,
            "top_opinions": top_opinions,
            "top_relations": top_relations,
            "top_relation_kinds": top_relation_kinds,
            "top_relation_evidence": top_relation_evidence,
            "top_constraints": top_constraints,
            "top_next_actions": top_next_actions,
            "support_refs": support_refs,
            "contradiction_count": contradiction_count,
        },
        reasons,
        reason_ids,
    )


def _build_replan_decision_with_activation(
    *,
    holes: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    activation_reason_ids: list[str],
) -> dict[str, Any]:
    reason_ids = (
        [item["hole_id"] for item in holes if _string(item.get("hole_id"))]
        + [item["conflict_id"] for item in conflicts if _string(item.get("conflict_id"))]
        + activation_reason_ids
    )
    source_report_ids = _unique_strings(
        [item.get("report_id") for item in holes],
        *[item.get("report_ids") for item in holes if isinstance(item.get("report_ids"), list)],
        *[item.get("report_ids") for item in conflicts if isinstance(item.get("report_ids"), list)],
    )
    topic_keys = _unique_strings(
        [item.get("topic_key") for item in holes],
        [item.get("topic_key") for item in conflicts],
    )
    if not reason_ids:
        return {
            "decision_id": "report-synthesis:clear",
            "status": "clear",
            "summary": "No unresolved report synthesis pressure.",
            "reason_ids": [],
            "source_report_ids": [],
            "topic_keys": [],
        }
    primary_ref = (
        conflicts[0]["conflict_id"]
        if conflicts
        else (source_report_ids[0] if source_report_ids else activation_reason_ids[0])
    )
    signal_word = "signal" if len(reason_ids) == 1 else "signals"
    return {
        "decision_id": f"report-synthesis:needs-replan:{primary_ref}",
        "status": "needs-replan",
        "summary": f"{len(reason_ids)} unresolved report synthesis {signal_word} {('requires' if len(reason_ids) == 1 else 'require')} main-brain judgment.",
        "reason_ids": reason_ids,
        "source_report_ids": source_report_ids,
        "topic_keys": topic_keys,
    }


def synthesize_reports(
    reports: Sequence[AgentReportRecord],
    *,
    activation_result: object | None = None,
    knowledge_writeback_service: object | None = None,
) -> dict[str, Any]:
    normalized_reports = [report for report in reports if isinstance(report, AgentReportRecord)]
    latest_reports = _latest_reports(normalized_reports)
    conflicts = _detect_conflicts(latest_reports)
    holes, recommended_actions, replan_directives = _detect_holes_and_actions(latest_reports, conflicts)
    (
        activation_payload,
        activation_reasons,
        activation_reason_ids,
    ) = _build_activation_summary(activation_result)
    replan_reasons: list[str] = []
    seen_replan_reasons: set[str] = set()
    for summary in [
        *(_string(conflict.get("summary")) for conflict in conflicts),
        *(_string(hole.get("summary")) for hole in holes),
        *activation_reasons,
    ]:
        if summary is None or summary in seen_replan_reasons:
            continue
        seen_replan_reasons.add(summary)
        replan_reasons.append(summary)
    replan_decision = _build_replan_decision_with_activation(
        holes=holes,
        conflicts=conflicts,
        activation_reason_ids=activation_reason_ids,
    )
    knowledge_writeback = None
    service = knowledge_writeback_service
    if service is None:
        service = KnowledgeWritebackService()
    build_writeback = getattr(service, "build_report_synthesis_writeback", None)
    summarize_change = getattr(service, "summarize_change", None)
    if callable(build_writeback) and callable(summarize_change):
        writeback_change = build_writeback(
            reports=latest_reports,
            activation_result=activation_result,
        )
        apply_change = getattr(service, "apply_change", None)
        if callable(apply_change):
            apply_change(writeback_change)
        writeback_summary = summarize_change(writeback_change)
        if isinstance(writeback_summary, dict) and (
            writeback_summary.get("node_ids")
            or writeback_summary.get("relation_ids")
        ):
            writeback_summary = dict(writeback_summary)
            writeback_summary["source_report_ids"] = [
                report.id
                for report in latest_reports
            ]
            writeback_summary["topic_keys"] = _unique_strings(
                _report_topic_key(report)
                for report in latest_reports
            )
            knowledge_writeback = writeback_summary
    payload = {
        "latest_findings": _latest_findings(normalized_reports),
        "conflicts": conflicts,
        "holes": holes,
        "recommended_actions": recommended_actions,
        "replan_reasons": replan_reasons,
        "replan_decision": replan_decision,
        "replan_directives": replan_directives,
        "needs_replan": bool(
            conflicts
            or holes
            or recommended_actions
            or activation_reason_ids
        ),
    }
    if activation_payload is not None:
        payload["activation"] = activation_payload
    if knowledge_writeback is not None:
        payload["knowledge_writeback"] = knowledge_writeback
    return payload



