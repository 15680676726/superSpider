# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import HTTPException, Request

from ...config import get_heartbeat_config
from ...utils.runtime_action_links import build_patch_actions as _build_patch_actions_factory
from .runtime_center_dependencies import _get_cron_manager
from .runtime_center_mutation_helpers import _get_runtime_center_facade_attr


def _model_dump_or_dict(value: object | None) -> dict[str, object] | None:
    if value is None:
        return None
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    return None


def _public_agent_payload(value: object | None) -> dict[str, object] | None:
    payload = _model_dump_or_dict(value)
    if payload is None:
        return None
    return payload


def _public_agent_detail_payload(value: object | None) -> dict[str, object] | None:
    payload = _model_dump_or_dict(value)
    if payload is None:
        return None
    agent_payload = _public_agent_payload(payload.get("agent"))
    if agent_payload is not None:
        payload["agent"] = agent_payload
    return payload


def _runtime_non_empty_str(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    resolved = value.strip()
    return resolved or None


def _runtime_mapping(value: object | None) -> dict[str, object]:
    payload = _model_dump_or_dict(value)
    return payload or {}


def _runtime_mapping_list(value: object | None) -> list[dict[str, object]]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[dict[str, object]] = []
    for item in items:
        payload = _runtime_mapping(item)
        if payload:
            normalized.append(payload)
    return normalized


def _runtime_text_list(*values: object | None) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            candidate = value.strip()
            if candidate and candidate not in seen:
                deduped.append(candidate)
                seen.add(candidate)
            continue
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    continue
                candidate = item.strip()
                if candidate and candidate not in seen:
                    deduped.append(candidate)
                    seen.add(candidate)
    return deduped


def _runtime_writeback_target(
    session_payload: dict[str, object],
    brief_payload: dict[str, object],
) -> dict[str, object] | None:
    writeback_target = _runtime_mapping(brief_payload.get("writeback_target"))
    if writeback_target:
        return {
            "scope_type": _runtime_non_empty_str(writeback_target.get("scope_type")),
            "scope_id": _runtime_non_empty_str(writeback_target.get("scope_id")),
        }

    work_context_id = _runtime_non_empty_str(session_payload.get("work_context_id"))
    if work_context_id:
        return {
            "scope_type": "work_context",
            "scope_id": work_context_id,
        }
    industry_instance_id = _runtime_non_empty_str(session_payload.get("industry_instance_id"))
    if industry_instance_id:
        return {
            "scope_type": "industry",
            "scope_id": industry_instance_id,
        }
    return None


def serialize_runtime_research_brief(
    *,
    session_payload: dict[str, object],
    round_payload: dict[str, object],
) -> dict[str, object]:
    session_metadata = _runtime_mapping(session_payload.get("metadata"))
    round_metadata = _runtime_mapping(round_payload.get("metadata"))
    brief_payload = (
        _runtime_mapping(round_payload.get("brief"))
        or _runtime_mapping(session_payload.get("brief"))
        or _runtime_mapping(round_metadata.get("brief"))
        or _runtime_mapping(session_metadata.get("brief"))
    )
    writeback_target = _runtime_writeback_target(session_payload, brief_payload)
    return {
        "goal": _runtime_non_empty_str(brief_payload.get("goal"))
        or _runtime_non_empty_str(session_payload.get("goal")),
        "question": _runtime_non_empty_str(brief_payload.get("question"))
        or _runtime_non_empty_str(round_payload.get("question")),
        "why_needed": _runtime_non_empty_str(brief_payload.get("why_needed")),
        "done_when": _runtime_non_empty_str(brief_payload.get("done_when")),
        "collection_mode_hint": _runtime_non_empty_str(
            brief_payload.get("collection_mode_hint"),
        ),
        "requested_sources": _runtime_text_list(brief_payload.get("requested_sources")),
        "writeback_target": writeback_target,
    }


def serialize_runtime_research_findings(
    *,
    session_payload: dict[str, object],
    round_payload: dict[str, object],
) -> list[dict[str, object]]:
    session_id = _runtime_non_empty_str(session_payload.get("id")) or "runtime-center-research"
    round_metadata = _runtime_mapping(round_payload.get("metadata"))
    structured_findings = _runtime_mapping_list(round_metadata.get("findings"))
    if structured_findings:
        return [
            {
                "finding_id": _runtime_non_empty_str(item.get("finding_id"))
                or f"{session_id}:finding:{index}",
                "finding_type": _runtime_non_empty_str(item.get("finding_type")) or "finding",
                "summary": _runtime_non_empty_str(item.get("summary")) or "",
                "supporting_source_ids": _runtime_text_list(
                    item.get("supporting_source_ids"),
                ),
                "supporting_evidence_ids": _runtime_text_list(
                    item.get("supporting_evidence_ids"),
                ),
                "conflicts": _runtime_text_list(item.get("conflicts")),
                "gaps": _runtime_text_list(item.get("gaps")),
            }
            for index, item in enumerate(structured_findings, start=1)
            if _runtime_non_empty_str(item.get("summary"))
        ]

    fallback_findings = _runtime_text_list(round_payload.get("new_findings"))
    if not fallback_findings:
        fallback_findings = _runtime_text_list(session_payload.get("stable_findings"))
    return [
        {
            "finding_id": f"{session_id}:finding:{index}",
            "finding_type": "finding",
            "summary": summary,
            "supporting_source_ids": [],
            "supporting_evidence_ids": [],
            "conflicts": [],
            "gaps": [],
        }
        for index, summary in enumerate(fallback_findings, start=1)
    ]


def serialize_runtime_research_sources(
    *,
    session_payload: dict[str, object],
    round_payload: dict[str, object],
) -> list[dict[str, object]]:
    session_id = _runtime_non_empty_str(session_payload.get("id")) or "runtime-center-research"
    round_metadata = _runtime_mapping(round_payload.get("metadata"))
    structured_sources = _runtime_mapping_list(round_payload.get("sources")) or _runtime_mapping_list(
        round_metadata.get("collected_sources"),
    )
    if structured_sources:
        return [
            {
                "source_id": _runtime_non_empty_str(item.get("source_id"))
                or f"{session_id}:source:{index}",
                "source_kind": _runtime_non_empty_str(item.get("source_kind")) or "source",
                "collection_action": _runtime_non_empty_str(item.get("collection_action"))
                or "read",
                "source_ref": _runtime_non_empty_str(item.get("source_ref")) or "",
                "normalized_ref": _runtime_non_empty_str(item.get("normalized_ref"))
                or _runtime_non_empty_str(item.get("source_ref"))
                or "",
                "title": _runtime_non_empty_str(item.get("title")) or "",
                "snippet": _runtime_non_empty_str(item.get("snippet")) or "",
                "access_status": _runtime_non_empty_str(item.get("access_status")) or "",
                "evidence_id": _runtime_non_empty_str(item.get("evidence_id")),
                "artifact_id": _runtime_non_empty_str(item.get("artifact_id")),
                "captured_at": item.get("captured_at"),
            }
            for index, item in enumerate(structured_sources, start=1)
            if _runtime_non_empty_str(item.get("source_ref"))
        ]

    fallback_links = _runtime_mapping_list(round_payload.get("selected_links")) or _runtime_mapping_list(
        round_payload.get("raw_links"),
    )
    return [
        {
            "source_id": f"{session_id}:source:{index}",
            "source_kind": _runtime_non_empty_str(item.get("kind")) or "web",
            "collection_action": "read",
            "source_ref": _runtime_non_empty_str(item.get("url")) or "",
            "normalized_ref": _runtime_non_empty_str(item.get("url")) or "",
            "title": _runtime_non_empty_str(item.get("title")) or "",
            "snippet": "",
            "access_status": "",
            "evidence_id": None,
            "artifact_id": None,
            "captured_at": None,
        }
        for index, item in enumerate(fallback_links, start=1)
        if _runtime_non_empty_str(item.get("url"))
    ]


def serialize_runtime_research_gaps(
    *,
    session_payload: dict[str, object],
    round_payload: dict[str, object],
) -> list[str]:
    round_metadata = _runtime_mapping(round_payload.get("metadata"))
    round_gaps = _runtime_text_list(
        round_metadata.get("gaps"),
        round_payload.get("remaining_gaps"),
    )
    if round_gaps:
        return round_gaps
    session_metadata = _runtime_mapping(session_payload.get("metadata"))
    return _runtime_text_list(
        session_metadata.get("gaps"),
        session_payload.get("open_questions"),
    )


def serialize_runtime_research_conflicts(
    *,
    session_payload: dict[str, object],
    round_payload: dict[str, object],
    findings_payload: list[dict[str, object]],
) -> list[str]:
    session_metadata = _runtime_mapping(session_payload.get("metadata"))
    round_metadata = _runtime_mapping(round_payload.get("metadata"))
    direct_conflicts = _runtime_text_list(
        round_metadata.get("conflicts"),
        session_metadata.get("conflicts"),
    )
    if direct_conflicts:
        return direct_conflicts
    return _runtime_text_list(
        *[item.get("conflicts") for item in findings_payload],
    )


def serialize_runtime_research_writeback_truth(
    *,
    session_payload: dict[str, object],
    round_payload: dict[str, object],
    brief_payload: dict[str, object],
) -> dict[str, object] | None:
    session_metadata = _runtime_mapping(session_payload.get("metadata"))
    round_metadata = _runtime_mapping(round_payload.get("metadata"))
    payload = _runtime_mapping(round_metadata.get("writeback_truth")) or _runtime_mapping(
        session_metadata.get("writeback_truth"),
    )
    writeback_target = _runtime_writeback_target(session_payload, brief_payload)
    scope_type = _runtime_non_empty_str(payload.get("scope_type")) or _runtime_non_empty_str(
        (writeback_target or {}).get("scope_type"),
    )
    scope_id = _runtime_non_empty_str(payload.get("scope_id")) or _runtime_non_empty_str(
        (writeback_target or {}).get("scope_id"),
    )
    report_id = _runtime_non_empty_str(payload.get("report_id")) or _runtime_non_empty_str(
        session_payload.get("final_report_id"),
    )
    status = _runtime_non_empty_str(payload.get("status")) or "pending"
    if not any((scope_type, scope_id, report_id, status)):
        return None
    return {
        "status": status,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "report_id": report_id,
    }


def _actor_runtime_payload(runtime: object) -> dict[str, object]:
    payload = _model_dump_or_dict(runtime)
    if payload is None:
        raise HTTPException(500, detail="Actor runtime payload is not serializable")
    agent_id = str(payload.get("agent_id") or "")
    if agent_id:
        payload["routes"] = {
            "detail": f"/api/runtime-center/actors/{agent_id}",
            "mailbox": f"/api/runtime-center/actors/{agent_id}/mailbox",
            "checkpoints": f"/api/runtime-center/actors/{agent_id}/checkpoints",
            "leases": f"/api/runtime-center/actors/{agent_id}/leases",
            "teammates": f"/api/runtime-center/actors/{agent_id}/teammates",
            "capabilities": f"/api/runtime-center/actors/{agent_id}/capabilities",
            "governed_capabilities": f"/api/runtime-center/actors/{agent_id}/capabilities/governed",
            "agent_capabilities": f"/api/runtime-center/agents/{agent_id}/capabilities",
        }
    return payload


def _actor_mailbox_payload(item: object) -> dict[str, object]:
    payload = _model_dump_or_dict(item)
    if payload is None:
        raise HTTPException(500, detail="Actor mailbox payload is not serializable")
    agent_id = str(payload.get("agent_id") or "")
    item_id = str(payload.get("id") or "")
    if agent_id and item_id:
        payload["route"] = f"/api/runtime-center/actors/{agent_id}/mailbox/{item_id}"
    return payload


def _serialize_knowledge_chunk(chunk: object) -> dict[str, object]:
    payload = _model_dump_or_dict(chunk)
    if payload is None:
        raise HTTPException(500, detail="Knowledge payload is not serializable")
    payload["route"] = f"/api/runtime-center/knowledge/{payload['id']}"
    memory_scope = _describe_memory_scope_from_service(chunk)
    if memory_scope is not None:
        payload.update(memory_scope)
    return payload


def _describe_memory_scope_from_service(chunk: object) -> dict[str, object] | None:
    document_id = None
    if isinstance(chunk, dict):
        document_id = chunk.get("document_id")
    else:
        document_id = getattr(chunk, "document_id", None)
    if not isinstance(document_id, str) or not document_id:
        return None
    if not document_id.startswith("memory:"):
        return None
    remainder = document_id[len("memory:") :]
    scope_type, separator, scope_id = remainder.partition(":")
    if not separator or not scope_type or not scope_id:
        return None
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
    }


def _build_patch_actions(patch_id: str, status: str, risk_level: str) -> dict[str, str]:
    return _build_patch_actions_factory(
        patch_id,
        status=status,
        risk_level=risk_level,
    )


def _heartbeat_route() -> str:
    return "/api/runtime-center/heartbeat"


def _serialize_timestamp(value: object) -> str | None:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return None


def _serialize_heartbeat_surface(request: Request) -> dict[str, object]:
    manager = _get_cron_manager(request)
    heartbeat_getter = _get_runtime_center_facade_attr(
        "get_heartbeat_config",
        get_heartbeat_config,
    )
    heartbeat = heartbeat_getter()
    heartbeat_payload = heartbeat.model_dump(mode="json", by_alias=True)
    state_getter = getattr(manager, "get_heartbeat_state", None)
    state = state_getter() if callable(state_getter) else None
    last_status = str(getattr(state, "last_status", None) or "")
    route = _heartbeat_route()
    return {
        "heartbeat": heartbeat_payload,
        "runtime": {
            "status": "paused" if not heartbeat.enabled else (last_status or "scheduled"),
            "enabled": heartbeat.enabled,
            "every": heartbeat.every,
            "target": heartbeat.target,
            "activeHours": heartbeat_payload.get("activeHours"),
            "last_run_at": _serialize_timestamp(getattr(state, "last_run_at", None)),
            "next_run_at": _serialize_timestamp(getattr(state, "next_run_at", None)),
            "last_error": getattr(state, "last_error", None),
            "query_path": "system:run_operating_cycle",
        },
        "route": route,
        "actions": {
            "update": route,
            "run": f"{route}/run",
        },
    }


def _maybe_publish_runtime_event(
    request: Request,
    *,
    topic: str,
    action: str,
    payload: dict[str, object] | None = None,
) -> None:
    bus = getattr(request.app.state, "runtime_event_bus", None)
    if bus is None or not callable(getattr(bus, "publish", None)):
        return
    bus.publish(topic=topic, action=action, payload=payload)


__all__ = [name for name in globals() if not name.startswith("__")]
