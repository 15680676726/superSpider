# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence


_FOLLOWUP_SYNTHESIS_KINDS = {"failed-report", "followup-needed", "conflict"}
_LIVE_BACKLOG_STATUSES = {"open", "selected", "materialized"}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _mapping_list(values: Sequence[object] | None, *, limit: int | None = None) -> list[dict[str, Any]]:
    items = [payload for payload in (_mapping(value) for value in list(values or [])) if payload]
    if isinstance(limit, int):
        return items[:limit]
    return items


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


def _timestamp(payload: Mapping[str, Any]) -> tuple[int, str]:
    for key in ("updated_at", "source_updated_at", "created_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            return (1, value.isoformat())
        text = _string(value)
        if text is not None:
            return (1, text)
    return (0, "")


def _sort_payloads(values: Sequence[object] | None) -> list[dict[str, Any]]:
    items = _mapping_list(values)
    return sorted(items, key=_timestamp, reverse=True)


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _resolve_synthesis(current_cycle: object | None, synthesis: Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(synthesis, Mapping):
        return dict(synthesis)
    cycle_payload = _mapping(current_cycle)
    return _mapping(cycle_payload.get("synthesis")) or _mapping(_mapping(cycle_payload.get("metadata")).get("report_synthesis"))


def _synthesis_has_pressure(synthesis: Mapping[str, Any]) -> bool:
    return bool(
        synthesis.get("needs_replan")
        or list(synthesis.get("conflicts") or [])
        or list(synthesis.get("holes") or [])
        or list(synthesis.get("replan_reasons") or [])
        or list(synthesis.get("recommended_actions") or [])
    )


def _backlog_is_followup(item: Mapping[str, Any]) -> bool:
    metadata = _mapping(item.get("metadata"))
    return bool(
        _string(metadata.get("source_report_id"))
        or list(metadata.get("source_report_ids") or [])
        or _string(metadata.get("synthesis_kind")) in _FOLLOWUP_SYNTHESIS_KINDS
    )


def _cycle_id(payload: Mapping[str, Any]) -> str | None:
    return _string(payload.get("cycle_id")) or _string(payload.get("id"))


def _source_report_ids(backlog_payload: Sequence[Mapping[str, Any]]) -> list[str]:
    return _unique_strings(
        *[
            _mapping(item.get("metadata")).get("source_report_ids")
            for item in backlog_payload
        ],
        [
            _mapping(item.get("metadata")).get("source_report_id")
            for item in backlog_payload
        ],
    )


def _cycle_matches_report_ids(cycle_payload: Mapping[str, Any], report_ids: Sequence[str]) -> bool:
    if not report_ids:
        return False
    synthesis = _resolve_synthesis(cycle_payload, None)
    latest_findings = _mapping_list(synthesis.get("latest_findings"))
    cycle_report_ids = _unique_strings([item.get("report_id") for item in latest_findings])
    return any(report_id in cycle_report_ids for report_id in report_ids)


def _select_anchor_cycle(
    *,
    current_cycle: Mapping[str, Any],
    cycles: Sequence[Mapping[str, Any]],
    backlog_payload: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not backlog_payload:
        return dict(current_cycle)
    source_report_ids = _source_report_ids(backlog_payload)
    for cycle_payload in cycles:
        if _cycle_matches_report_ids(cycle_payload, source_report_ids):
            return dict(cycle_payload)
    for cycle_payload in cycles:
        if _synthesis_has_pressure(_resolve_synthesis(cycle_payload, None)):
            return dict(cycle_payload)
    return dict(current_cycle)


def build_main_brain_cognitive_surface(
    *,
    current_cycle: object | None = None,
    cycles: Sequence[object] | None = None,
    backlog: Sequence[object] | None = None,
    agent_reports: Sequence[object] | None = None,
    synthesis: Mapping[str, Any] | None = None,
    followup_backlog: Sequence[object] | None = None,
    work_context_ids: Sequence[str] | None = None,
    control_thread_ids: Sequence[str] | None = None,
    environment_refs: Sequence[str] | None = None,
    recommended_action: str | None = None,
) -> dict[str, Any]:
    current_cycle_payload = _mapping(current_cycle)
    cycles_payload = _sort_payloads(cycles)
    current_cycle_id = _cycle_id(current_cycle_payload)
    if current_cycle_payload and current_cycle_id is not None and all(_cycle_id(item) != current_cycle_id for item in cycles_payload):
        cycles_payload.insert(0, current_cycle_payload)

    backlog_payload = _sort_payloads(followup_backlog) if followup_backlog is not None else [
        item
        for item in _sort_payloads(backlog)
        if _string(item.get("status")) in _LIVE_BACKLOG_STATUSES and _backlog_is_followup(item)
    ]
    anchor_cycle = _select_anchor_cycle(
        current_cycle=current_cycle_payload,
        cycles=cycles_payload,
        backlog_payload=backlog_payload,
    )
    anchor_cycle_id = _cycle_id(anchor_cycle)
    normalized_synthesis = _resolve_synthesis(anchor_cycle, synthesis)

    latest_findings = _mapping_list(normalized_synthesis.get("latest_findings"), limit=4)
    conflicts = _mapping_list(normalized_synthesis.get("conflicts"), limit=4)
    holes = _mapping_list(normalized_synthesis.get("holes"), limit=4)
    recommended_actions = _mapping_list(normalized_synthesis.get("recommended_actions"), limit=4)
    replan_reasons = _unique_strings(normalized_synthesis.get("replan_reasons"))

    reports_payload = _sort_payloads(agent_reports)
    latest_reports = latest_findings or [
        item
        for item in reports_payload
        if anchor_cycle_id is None or _string(item.get("cycle_id")) == anchor_cycle_id
    ][:3]

    continuity_work_context_ids = _unique_strings(
        work_context_ids,
        [item.get("work_context_id") for item in latest_reports],
        [_mapping(item.get("metadata")).get("work_context_id") for item in backlog_payload],
    )
    continuity_control_thread_ids = _unique_strings(
        control_thread_ids,
        [_mapping(item.get("metadata")).get("control_thread_id") for item in backlog_payload],
        [_mapping(item.get("metadata")).get("session_id") for item in backlog_payload],
    )
    continuity_environment_refs = _unique_strings(
        environment_refs,
        [_mapping(item.get("metadata")).get("environment_ref") for item in backlog_payload],
    )

    needs_replan = bool(
        backlog_payload
        or normalized_synthesis.get("needs_replan")
        or conflicts
        or holes
        or replan_reasons
    )
    resolved_action = _string(recommended_action)
    if resolved_action is None:
        if backlog_payload:
            resolved_action = "dispatch-followup"
        elif needs_replan:
            resolved_action = "review-reports-and-materialize-next-followup-cycle"
        else:
            resolved_action = "continue-cycle"
    judgment = {
        "cycle_id": anchor_cycle_id,
        "status": "replan-required" if backlog_payload else ("review-required" if needs_replan else "stable"),
        "summary": (
            replan_reasons[0]
            if replan_reasons
            else (
                f"{len(backlog_payload)} follow-up backlog item(s) still need main-brain closure."
                if backlog_payload
                else ("Main-brain should replan before dispatching more work." if needs_replan else "Main-brain closure is currently stable.")
            )
        ),
    }
    return _json_ready({
        "latest_reports": latest_reports,
        "synthesis": {
            "latest_findings": latest_findings,
            "conflicts": conflicts,
            "holes": holes,
            "recommended_actions": recommended_actions,
            "replan_reasons": replan_reasons,
            "needs_replan": needs_replan,
        },
        "needs_replan": needs_replan,
        "replan_reasons": replan_reasons,
        "judgment": judgment,
        "next_action": {
            "kind": resolved_action,
            "summary": resolved_action.replace("-", " "),
        },
        "followup_backlog": backlog_payload,
        "continuity": {
            "work_context_ids": continuity_work_context_ids,
            "control_thread_ids": continuity_control_thread_ids,
            "environment_refs": continuity_environment_refs,
        },
        "cycle_ids": _unique_strings([anchor_cycle_id], [_cycle_id(item) for item in cycles_payload]),
    })


__all__ = ["build_main_brain_cognitive_surface"]
