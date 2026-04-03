# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .identity import EXECUTION_CORE_AGENT_ID, EXECUTION_CORE_NAME, EXECUTION_CORE_ROLE_ID
from .report_synthesis import synthesize_reports
from ..state import (
    AgentReportRecord,
    AssignmentRecord,
    BacklogItemRecord,
    IndustryInstanceRecord,
    OperatingCycleRecord,
)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _unique_strings(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, Sequence):
            candidates = list(value)
        else:
            candidates = []
        for candidate in candidates:
            text = _string(candidate)
            if text is None or text in seen:
                continue
            seen.add(text)
            items.append(text)
    return items


def _activation_followup_metadata(synthesis: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(synthesis, Mapping):
        return {}
    activation = synthesis.get("activation")
    if not isinstance(activation, Mapping):
        return {}
    metadata: dict[str, Any] = {}
    for source_key, target_key in (
        ("top_entities", "activation_top_entities"),
        ("top_opinions", "activation_top_opinions"),
        ("top_relations", "activation_top_relations"),
        ("top_relation_kinds", "activation_top_relation_kinds"),
        ("top_constraints", "activation_top_constraints"),
        ("top_next_actions", "activation_top_next_actions"),
        ("support_refs", "activation_support_refs"),
    ):
        value = activation.get(source_key)
        if not isinstance(value, Sequence) or isinstance(value, str):
            continue
        copied = list(value)
        if copied:
            metadata[target_key] = copied
    relation_evidence = activation.get("top_relation_evidence")
    if isinstance(relation_evidence, Sequence) and not isinstance(relation_evidence, str):
        relation_ids = _unique_strings(
            [
                item.get("relation_id")
                for item in relation_evidence
                if isinstance(item, Mapping)
            ],
        )
        relation_source_refs = _unique_strings(
            *[
                item.get("source_refs")
                for item in relation_evidence
                if isinstance(item, Mapping)
            ],
        )
        if relation_ids:
            metadata["activation_top_relation_ids"] = relation_ids
        if relation_source_refs:
            metadata["activation_relation_source_refs"] = relation_source_refs
    return metadata


def synthesize_agent_reports(
    *,
    list_agent_report_records: Callable[..., list[AgentReportRecord]],
    instance_id: str,
    cycle_id: str | None,
    activation_result: object | None = None,
) -> dict[str, Any]:
    return synthesize_reports(
        list_agent_report_records(
            instance_id,
            cycle_id=cycle_id,
            limit=None,
        ),
        activation_result=activation_result,
    )


def record_report_synthesis_backlog(
    *,
    backlog_service: object | None,
    record: IndustryInstanceRecord,
    synthesis: Mapping[str, Any] | None,
    resolve_report_followup_metadata: Callable[[Mapping[str, Any] | None], dict[str, Any]],
) -> None:
    if backlog_service is None or not isinstance(synthesis, dict):
        return
    actions = synthesis.get("recommended_actions")
    if not isinstance(actions, list):
        return
    for action in actions:
        if not isinstance(action, dict):
            continue
        source_ref = _string(action.get("source_ref"))
        title = _string(action.get("title"))
        if source_ref is None or title is None:
            continue
        metadata = action.get("metadata")
        action_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        carried_metadata = resolve_report_followup_metadata(action_metadata)
        metadata = dict(action_metadata)
        if carried_metadata:
            metadata.update(carried_metadata)
        activation_metadata = _activation_followup_metadata(synthesis)
        if activation_metadata:
            metadata.update(activation_metadata)
        if not metadata:
            metadata = None
        try:
            priority = int(action.get("priority", 4))
        except (TypeError, ValueError):
            priority = 4
        backlog_service.record_chat_writeback(
            industry_instance_id=record.instance_id,
            lane_id=_string(action.get("lane_id")),
            title=title,
            summary=_string(action.get("summary")) or "",
            priority=priority,
            source_ref=source_ref,
            metadata=dict(metadata) if isinstance(metadata, dict) else None,
        )


def resolve_report_followup_metadata(
    *,
    action_metadata: Mapping[str, Any] | None,
    agent_report_repository: object | None,
    assignment_repository: object | None,
    backlog_service: object | None,
    build_report_followup_metadata_fn: Callable[
        ...,
        dict[str, Any],
    ] | None = None,
    merge_report_followup_metadata_fn: Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]
    | None = None,
) -> dict[str, Any]:
    metadata = dict(action_metadata or {})
    source_report_ids = _unique_strings(
        metadata.get("source_report_ids"),
        metadata.get("source_report_id"),
    )
    if not source_report_ids:
        return {}
    reports: list[AgentReportRecord] = []
    if agent_report_repository is not None:
        getter = getattr(agent_report_repository, "get_report", None)
        if callable(getter):
            for report_id in source_report_ids:
                report = getter(report_id)
                if isinstance(report, AgentReportRecord):
                    reports.append(report)

    contexts: list[tuple[AgentReportRecord | None, AssignmentRecord | None, BacklogItemRecord | None]] = []
    if reports:
        seen_assignment_ids: set[str] = set()
        assignments_by_report_id: dict[str, AssignmentRecord | None] = {}
        assignment_getter = (
            getattr(assignment_repository, "get_assignment", None)
            if assignment_repository is not None
            else None
        )
        if callable(assignment_getter):
            for report in reports:
                assignment_id = _string(getattr(report, "assignment_id", None))
                assignment = None
                if assignment_id is not None and assignment_id not in seen_assignment_ids:
                    assignment = assignment_getter(assignment_id)
                    seen_assignment_ids.add(assignment_id)
                elif assignment_id is not None:
                    assignment = assignments_by_report_id.get(assignment_id)
                assignments_by_report_id[assignment_id or ""] = assignment

        for report in reports:
            assignment = assignments_by_report_id.get(_string(report.assignment_id) or "")
            original_backlog_item = None
            if assignment is not None and backlog_service is not None:
                backlog_item_id = _string(getattr(assignment, "backlog_item_id", None))
                if backlog_item_id is not None:
                    original_backlog_item = backlog_service.get_item(backlog_item_id)
            contexts.append((report, assignment, original_backlog_item))
    else:
        contexts.append((None, None, None))

    build_metadata = build_report_followup_metadata_fn or build_report_followup_metadata
    merge_metadata = merge_report_followup_metadata_fn or merge_report_followup_metadata

    merged: dict[str, Any] = {}
    for report, assignment, original_backlog_item in contexts:
        continuity = build_metadata(
            report=report,
            assignment=assignment,
            original_backlog_item=original_backlog_item,
        )
        if not merged:
            merged = continuity
        elif continuity:
            merged = merge_metadata(merged, continuity)

    if not merged:
        return {}
    merged_source_ids = _unique_strings(merged.get("source_report_ids"), source_report_ids)
    if merged_source_ids:
        merged["source_report_ids"] = list(merged_source_ids)
        merged.setdefault("source_report_id", merged_source_ids[0])
    return merged


def merge_report_followup_metadata(
    base: Mapping[str, Any],
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if merged.get(key) in (None, "") and value not in (None, ""):
            merged[key] = value
    merged_surfaces = _unique_strings(
        merged.get("seat_requested_surfaces"),
        merged.get("chat_writeback_requested_surfaces"),
        extra.get("seat_requested_surfaces"),
        extra.get("chat_writeback_requested_surfaces"),
    )
    if merged_surfaces:
        merged["seat_requested_surfaces"] = list(merged_surfaces)
        merged["chat_writeback_requested_surfaces"] = list(merged_surfaces)
    merged_source_ids = _unique_strings(
        merged.get("source_report_ids"),
        extra.get("source_report_ids"),
    )
    if merged_source_ids:
        merged["source_report_ids"] = list(merged_source_ids)
        merged.setdefault("source_report_id", merged_source_ids[0])
    return merged


def build_report_followup_metadata(
    *,
    report: AgentReportRecord | None,
    assignment: AssignmentRecord | None,
    original_backlog_item: BacklogItemRecord | None,
) -> dict[str, Any]:
    carried: dict[str, Any] = {}
    original_metadata = (
        dict(original_backlog_item.metadata or {})
        if original_backlog_item is not None
        else {}
    )
    assignment_metadata = (
        dict(assignment.metadata or {})
        if assignment is not None
        else {}
    )
    report_metadata = (
        dict(report.metadata or {})
        if report is not None
        else {}
    )
    supervisor_owner_agent_id = _string(
        original_metadata.get("supervisor_owner_agent_id"),
    ) or _string(
        assignment_metadata.get("supervisor_owner_agent_id"),
    ) or _string(
        report_metadata.get("supervisor_owner_agent_id"),
    )
    supervisor_industry_role_id = _string(
        original_metadata.get("supervisor_industry_role_id"),
    ) or _string(
        assignment_metadata.get("supervisor_industry_role_id"),
    ) or _string(
        report_metadata.get("supervisor_industry_role_id"),
    )
    supervisor_role_name = _string(
        original_metadata.get("supervisor_role_name"),
    ) or _string(
        assignment_metadata.get("supervisor_role_name"),
    ) or _string(
        report_metadata.get("supervisor_role_name"),
    )
    for key in (
        "supervisor_owner_agent_id",
        "supervisor_industry_role_id",
        "supervisor_role_name",
        "environment_constraints",
        "evidence_expectations",
        "report_back_mode",
        "source",
        "chat_writeback_fingerprint",
        "chat_writeback_instruction",
        "chat_writeback_classes",
        "chat_writeback_target_role_name",
        "chat_writeback_target_match_signals",
        "chat_writeback_requested_surfaces",
        "chat_writeback_channel",
        "chat_writeback_gap_kind",
        "seat_resolution_kind",
        "seat_resolution_reason",
        "seat_requested_surfaces",
        "seat_target_role_id",
        "seat_target_role_name",
        "seat_target_agent_id",
        "decision_request_id",
        "proposal_status",
        "recommended_scheduler_action",
        "control_thread_id",
        "session_id",
        "environment_ref",
        "work_context_id",
    ):
        value = (
            original_metadata.get(key)
            if key in original_metadata
            else assignment_metadata.get(key)
            if key in assignment_metadata
            else report_metadata.get(key)
            if key in report_metadata
            else None
        )
        if value is not None:
            carried[key] = value
    requested_surfaces = _unique_strings(
        carried.get("seat_requested_surfaces"),
        carried.get("chat_writeback_requested_surfaces"),
        assignment_metadata.get("seat_requested_surfaces"),
        assignment_metadata.get("chat_writeback_requested_surfaces"),
        report_metadata.get("seat_requested_surfaces"),
        report_metadata.get("chat_writeback_requested_surfaces"),
    )
    if requested_surfaces:
        carried["seat_requested_surfaces"] = list(requested_surfaces)
        carried.setdefault(
            "chat_writeback_requested_surfaces",
            list(requested_surfaces),
        )
    if supervisor_owner_agent_id is not None:
        carried["owner_agent_id"] = supervisor_owner_agent_id
    if supervisor_industry_role_id is not None:
        carried["industry_role_id"] = supervisor_industry_role_id
        carried.setdefault("goal_kind", supervisor_industry_role_id)
    if supervisor_role_name is not None:
        carried["industry_role_name"] = supervisor_role_name
        carried["role_name"] = supervisor_role_name
        carried.setdefault("role_summary", supervisor_role_name)
    carried.setdefault("task_mode", "report-followup")
    if report is not None and _string(getattr(report, "work_context_id", None)) is not None:
        carried["work_context_id"] = report.work_context_id
    if report is not None:
        if _string(report.owner_agent_id) is not None:
            carried.setdefault("source_owner_agent_id", report.owner_agent_id)
        if _string(report.owner_role_id) is not None:
            carried.setdefault("source_industry_role_id", report.owner_role_id)
    if assignment is not None:
        if _string(assignment.owner_agent_id) is not None:
            carried.setdefault("source_owner_agent_id", assignment.owner_agent_id)
        if _string(assignment.owner_role_id) is not None:
            carried.setdefault("source_industry_role_id", assignment.owner_role_id)
    if original_backlog_item is not None and original_backlog_item.source_ref is not None:
        carried.setdefault("upstream_backlog_source_ref", original_backlog_item.source_ref)
    report_instance_id = _string(getattr(report, "industry_instance_id", None))
    report_owner_role_id = _string(getattr(report, "owner_role_id", None))
    if report_instance_id is not None and report_owner_role_id not in {None, EXECUTION_CORE_ROLE_ID}:
        carried.setdefault("supervisor_owner_agent_id", EXECUTION_CORE_AGENT_ID)
        carried.setdefault("supervisor_industry_role_id", EXECUTION_CORE_ROLE_ID)
        carried.setdefault("supervisor_role_name", EXECUTION_CORE_NAME)
        carried.setdefault("owner_agent_id", EXECUTION_CORE_AGENT_ID)
        carried.setdefault("industry_role_id", EXECUTION_CORE_ROLE_ID)
        carried.setdefault("industry_role_name", EXECUTION_CORE_NAME)
        carried.setdefault("role_name", EXECUTION_CORE_NAME)
        carried.setdefault("recommended_scheduler_action", "continue")
    control_thread_id = _string(carried.get("control_thread_id")) or _string(
        carried.get("session_id"),
    )
    if control_thread_id is None and report_instance_id is not None:
        control_thread_id = f"industry-chat:{report_instance_id}:{EXECUTION_CORE_ROLE_ID}"
    if control_thread_id is not None:
        carried["control_thread_id"] = control_thread_id
        carried["session_id"] = control_thread_id
    if _string(carried.get("environment_ref")) is None:
        instance_id = (
            _string(getattr(report, "industry_instance_id", None))
            or _string(getattr(assignment, "industry_instance_id", None))
        )
        if instance_id is not None:
            channel = _string(carried.get("chat_writeback_channel")) or "console"
            carried["environment_ref"] = f"session:{channel}:industry:{instance_id}"
    return carried


def persist_cycle_report_synthesis(
    *,
    cycle: OperatingCycleRecord | None,
    synthesis: Mapping[str, Any] | None,
    operating_cycle_repository: object | None,
    utc_now: Callable[[], object],
) -> OperatingCycleRecord | None:
    if (
        cycle is None
        or operating_cycle_repository is None
        or not isinstance(synthesis, dict)
    ):
        return cycle
    metadata = dict(cycle.metadata or {})
    metadata["report_synthesis"] = dict(synthesis)
    return operating_cycle_repository.upsert_cycle(
        cycle.model_copy(
            update={
                "metadata": metadata,
                "updated_at": utc_now(),
            },
        ),
    )


def write_agent_report_back_to_control_thread(
    *,
    session_backend: object | None,
    backlog_service: object | None,
    record: IndustryInstanceRecord,
    report: AgentReportRecord,
    assignment: AssignmentRecord | None,
    build_report_followup_metadata_fn: Callable[..., dict[str, Any]],
    build_agent_report_control_thread_message_fn: Callable[..., str],
    execution_core_role_id: str,
    execution_core_agent_id: str,
) -> None:
    if session_backend is None:
        return
    loader = getattr(session_backend, "load_session_snapshot", None)
    saver = getattr(session_backend, "save_session_snapshot", None)
    if not callable(loader) or not callable(saver):
        return
    original_backlog_item = None
    if assignment is not None and backlog_service is not None and assignment.backlog_item_id is not None:
        original_backlog_item = backlog_service.get_item(assignment.backlog_item_id)
    continuity = build_report_followup_metadata_fn(
        report=report,
        assignment=assignment,
        original_backlog_item=original_backlog_item,
    )
    session_id = (
        _string(continuity.get("control_thread_id"))
        or _string(continuity.get("session_id"))
        or f"industry-chat:{record.instance_id}:{execution_core_role_id}"
    )
    payload = loader(
        session_id=session_id,
        user_id=execution_core_agent_id,
        allow_not_exist=True,
    )
    if not isinstance(payload, dict):
        payload = {}
    payload = dict(payload)
    agent_state = payload.get("agent")
    if not isinstance(agent_state, dict):
        agent_state = {}
    memory_state = agent_state.get("memory")
    if isinstance(memory_state, list):
        messages = list(memory_state)
        agent_state["memory"] = messages
    elif isinstance(memory_state, dict):
        normalized_memory = dict(memory_state)
        content = normalized_memory.get("content")
        messages = list(content) if isinstance(content, list) else []
        normalized_memory["content"] = messages
        agent_state["memory"] = normalized_memory
    else:
        messages = []
        agent_state["memory"] = messages
    message_id = f"agent-report:{report.id}"
    if any(
        isinstance(item, dict) and _string(item.get("id")) == message_id
        for item in messages
    ):
        return
    messages.append(
        {
            "id": message_id,
            "role": "assistant",
            "object": "message",
            "type": "message",
            "status": "completed",
            "content": [
                {
                    "type": "text",
                    "text": build_agent_report_control_thread_message_fn(
                        report=report,
                        assignment=assignment,
                    ),
                },
            ],
            "metadata": {
                key: value
                for key, value in {
                    "synthetic": True,
                    "message_kind": "agent-report-writeback",
                    "industry_instance_id": record.instance_id,
                    "control_thread_id": _string(continuity.get("control_thread_id")),
                    "session_id": _string(continuity.get("session_id")),
                    "environment_ref": _string(continuity.get("environment_ref")),
                    "recommended_scheduler_action": _string(
                        continuity.get("recommended_scheduler_action"),
                    ),
                    "report_id": report.id,
                    "assignment_id": report.assignment_id,
                    "task_id": report.task_id,
                    "work_context_id": report.work_context_id,
                    "owner_agent_id": report.owner_agent_id,
                    "owner_role_id": report.owner_role_id,
                    "result": report.result,
                    "evidence_count": len(report.evidence_ids or []),
                    "decision_count": len(report.decision_ids or []),
                }.items()
                if value is not None and (not isinstance(value, str) or value.strip())
            },
        },
    )
    payload["agent"] = agent_state
    saver(
        session_id=session_id,
        user_id=execution_core_agent_id,
        payload=payload,
        source_ref=f"agent-report:{report.id}",
    )
    try:
        from ..app.console_push_store import append_now

        append_now(
            session_id,
            f"Main brain received agent report: {_string(report.headline) or report.id}",
        )
    except Exception:
        pass


def build_agent_report_control_thread_message(
    *,
    report: AgentReportRecord,
    assignment: AssignmentRecord | None,
) -> str:
    owner_label = (
        _string(report.owner_role_id)
        or _string(report.owner_agent_id)
        or "agent"
    )
    result_label = _string(report.result) or _string(report.status) or "reported"
    assignment_title = _string(assignment.title) if assignment is not None else None
    summary = _string(report.summary)
    lines = [
        f"Agent report: {_string(report.headline) or report.id}",
        f"Source: {owner_label}",
        f"Result: {result_label}",
    ]
    if assignment_title:
        lines.append(f"Assignment: {assignment_title}")
    if summary:
        lines.append(f"Summary: {summary}")
    lines.append(
        f"Evidence {len(report.evidence_ids or [])} / Decisions {len(report.decision_ids or [])}",
    )
    return "\n".join(lines)
