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
