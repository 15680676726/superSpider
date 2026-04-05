# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.buddy_runtime_focus import build_buddy_current_focus_resolver


def test_buddy_current_focus_resolver_prefers_execution_core_focus() -> None:
    resolver = build_buddy_current_focus_resolver(
        agent_profile_service=SimpleNamespace(
            get_agent=lambda agent_id: SimpleNamespace(current_focus="Ship the first proof artifact"),
        ),
        growth_target_repository=SimpleNamespace(
            get_active_target=lambda profile_id: SimpleNamespace(
                why_it_matters="Because this is the first real proof that moves the long-term goal.",
            ),
        ),
        industry_instance_repository=SimpleNamespace(get_instance=lambda instance_id: None),
        assignment_service=SimpleNamespace(list_assignments=lambda **kwargs: []),
        backlog_service=SimpleNamespace(list_open_items=lambda **kwargs: []),
    )

    payload = resolver("profile-1")

    assert payload == {
        "current_task_summary": "Ship the first proof artifact",
        "why_now_summary": "Because this is the first real proof that moves the long-term goal.",
    }


def test_buddy_current_focus_resolver_falls_back_to_buddy_assignment_scaffold() -> None:
    resolver = build_buddy_current_focus_resolver(
        agent_profile_service=SimpleNamespace(
            get_agent=lambda agent_id: SimpleNamespace(current_focus=""),
        ),
        growth_target_repository=SimpleNamespace(
            get_active_target=lambda profile_id: SimpleNamespace(
                why_it_matters="Because the current cycle must start with a visible win.",
            ),
        ),
        industry_instance_repository=SimpleNamespace(
            get_instance=lambda instance_id: SimpleNamespace(
                instance_id=instance_id,
                current_cycle_id="cycle-1",
            ),
        ),
        assignment_service=SimpleNamespace(
            list_assignments=lambda **kwargs: [
                SimpleNamespace(status="queued", summary="Publish the first public artifact"),
            ],
        ),
        backlog_service=SimpleNamespace(list_open_items=lambda **kwargs: []),
    )

    payload = resolver("profile-1")

    assert payload == {
        "current_task_summary": "Publish the first public artifact",
        "why_now_summary": "Because the current cycle must start with a visible win.",
    }
