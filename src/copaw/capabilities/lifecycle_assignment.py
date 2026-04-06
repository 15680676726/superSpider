# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object | None) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _string(item)
        if text is None:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


@dataclass(frozen=True, slots=True)
class CapabilityLifecycleAssignmentContext:
    target_agent_id: str
    current_capability_ids: list[str]
    target_role_id: str | None = None
    selected_seat_ref: str | None = None
    session_overlay_capability_ids: list[str] | None = None
    role_prototype_capability_ids: list[str] | None = None


def resolve_capability_lifecycle_assignment_context(
    *,
    agent_profile_service: object | None,
    target_agent_id: str,
) -> CapabilityLifecycleAssignmentContext:
    target_role_id: str | None = None
    selected_seat_ref: str | None = None
    current_capability_ids: list[str] = []
    session_overlay_capability_ids: list[str] = []
    role_prototype_capability_ids: list[str] = []

    detail_getter = getattr(agent_profile_service, "get_agent_detail", None)
    if callable(detail_getter):
        detail = detail_getter(target_agent_id)
        if isinstance(detail, dict):
            runtime = detail.get("runtime")
            if isinstance(runtime, dict):
                target_role_id = _string(runtime.get("industry_role_id"))
                metadata = runtime.get("metadata")
                if isinstance(metadata, dict):
                    selected_seat_ref = _string(metadata.get("selected_seat_ref"))
                    layers = metadata.get("capability_layers")
                    if isinstance(layers, dict):
                        current_capability_ids = _string_list(
                            layers.get("effective_capability_ids"),
                        )
                        session_overlay_capability_ids = _string_list(
                            layers.get("session_overlay_capability_ids"),
                        )
                        role_prototype_capability_ids = _string_list(
                            layers.get("role_prototype_capability_ids"),
                        )

    surface_getter = getattr(agent_profile_service, "get_capability_surface", None)
    if callable(surface_getter):
        surface = surface_getter(target_agent_id)
        if isinstance(surface, dict):
            resolved = _string_list(surface.get("effective_capabilities"))
            if resolved:
                current_capability_ids = resolved

    agent_getter = getattr(agent_profile_service, "get_agent", None)
    if callable(agent_getter):
        agent = agent_getter(target_agent_id)
        if target_role_id is None:
            target_role_id = _string(getattr(agent, "industry_role_id", None))
        if not current_capability_ids and agent is not None:
            current_capability_ids = _string_list(getattr(agent, "capabilities", None))

    return CapabilityLifecycleAssignmentContext(
        target_agent_id=target_agent_id,
        current_capability_ids=current_capability_ids,
        target_role_id=target_role_id,
        selected_seat_ref=selected_seat_ref,
        session_overlay_capability_ids=session_overlay_capability_ids,
        role_prototype_capability_ids=role_prototype_capability_ids,
    )


def build_capability_lifecycle_assignment_payload(
    *,
    agent_profile_service: object | None,
    target_agent_id: str,
    capability_ids: list[str],
    capability_assignment_mode: str,
    reason: str,
    actor: str,
) -> dict[str, object]:
    context = resolve_capability_lifecycle_assignment_context(
        agent_profile_service=agent_profile_service,
        target_agent_id=target_agent_id,
    )
    target_capability_ids = _string_list(capability_ids)
    normalized_mode = (
        str(capability_assignment_mode or "merge").strip().lower() or "merge"
    )
    replace_mode = normalized_mode == "replace"
    protected_current = {
        item.lower()
        for item in list(context.session_overlay_capability_ids or [])
        if _string(item)
    }
    protected_current.update(
        item.lower()
        for item in list(context.role_prototype_capability_ids or [])
        if _string(item)
    )
    target_lookup = {item.lower() for item in target_capability_ids}
    replacement_target_ids = [
        capability_id
        for capability_id in context.current_capability_ids
        if capability_id.lower() not in protected_current
        and capability_id.lower() not in target_lookup
    ]
    return {
        "decision_kind": "replace_existing" if replace_mode else "promote_to_role",
        "target_agent_id": target_agent_id,
        "target_capability_ids": target_capability_ids,
        "replacement_target_ids": replacement_target_ids,
        "rollback_target_ids": replacement_target_ids if replace_mode else [],
        "selected_scope": "agent",
        "scope_ref": target_agent_id,
        "selected_seat_ref": context.selected_seat_ref,
        "target_role_id": context.target_role_id,
        "reason": reason,
        "actor": actor,
        "governed_mutation": True,
    }
