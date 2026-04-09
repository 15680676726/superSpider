# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_execution_carrier import build_buddy_execution_carrier_handoff
from copaw.state import HumanProfile


def _profile() -> HumanProfile:
    return HumanProfile(
        profile_id="profile-1",
        display_name="Buddy",
        profession="designer",
        current_stage="building",
        interests=[],
        strengths=[],
        constraints=[],
        goal_intention="ship better work",
    )


def test_buddy_execution_carrier_handoff_prefers_canonical_control_thread_from_instance_id() -> None:
    payload = build_buddy_execution_carrier_handoff(
        profile=_profile(),
        instance_id="buddy:profile-1:domain-current",
        control_thread_id="industry-chat:buddy:profile-1:domain-stale:execution-core",
        label="Buddy Carrier",
        current_cycle_id="cycle-1",
        team_generated=True,
    )

    assert payload["control_thread_id"] == (
        "industry-chat:buddy:profile-1:domain-current:execution-core"
    )
    assert payload["thread_id"] == payload["control_thread_id"]
    assert payload["chat_binding"]["control_thread_id"] == payload["control_thread_id"]
