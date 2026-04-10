# -*- coding: utf-8 -*-
from __future__ import annotations

from ..state import HumanProfile

EXECUTION_CORE_ROLE_ID = "execution-core"


def build_buddy_domain_instance_id(*, profile_id: str, domain_id: str) -> str:
    return f"buddy:{profile_id}:{domain_id}"


def build_buddy_domain_control_thread_id(*, instance_id: str) -> str:
    return f"industry-chat:{instance_id}:{EXECUTION_CORE_ROLE_ID}"


def build_buddy_execution_carrier_handoff(
    *,
    profile: HumanProfile,
    instance_id: str,
    label: str,
    current_cycle_id: str,
    team_generated: bool,
    control_thread_id: str | None = None,
) -> dict[str, object]:
    normalized_instance_id = str(instance_id or "").strip()
    normalized_control_thread_id = str(control_thread_id or "").strip()
    resolved_control_thread_id = (
        normalized_control_thread_id
        or (
            build_buddy_domain_control_thread_id(instance_id=normalized_instance_id)
            if normalized_instance_id
            else ""
        )
    )
    return {
        "instance_id": normalized_instance_id,
        "label": label,
        "owner_scope": profile.profile_id,
        "current_cycle_id": current_cycle_id,
        "team_generated": team_generated,
        "thread_id": resolved_control_thread_id,
        "control_thread_id": resolved_control_thread_id,
        "chat_binding": {
            "thread_id": resolved_control_thread_id,
            "control_thread_id": resolved_control_thread_id,
            "user_id": f"buddy:{profile.profile_id}",
            "channel": "console",
            "context_key": f"control-thread:{resolved_control_thread_id}",
            "binding_kind": "buddy-execution-carrier",
            "metadata": {
                "industry_instance_id": normalized_instance_id,
                "industry_role_id": EXECUTION_CORE_ROLE_ID,
                "industry_role_name": "execution-core",
                "owner_scope": profile.profile_id,
                "team_generated": team_generated,
            },
        },
    }


__all__ = [
    "EXECUTION_CORE_ROLE_ID",
    "build_buddy_domain_control_thread_id",
    "build_buddy_domain_instance_id",
    "build_buddy_execution_carrier_handoff",
]
