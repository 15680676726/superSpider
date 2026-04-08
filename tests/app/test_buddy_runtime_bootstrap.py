# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.buddy_runtime_focus import (
    build_buddy_current_focus_resolver,
    resolve_active_human_assist_focus,
)
from copaw.state.models import HumanAssistTaskRecord


def test_buddy_current_focus_resolver_prefers_profile_scaffold_before_execution_core_focus() -> None:
    resolver = build_buddy_current_focus_resolver(
        agent_profile_service=SimpleNamespace(
            get_agent=lambda agent_id: SimpleNamespace(current_focus="Ship the first proof artifact"),
        ),
        growth_target_repository=SimpleNamespace(
            get_active_target=lambda profile_id: SimpleNamespace(
                why_it_matters="Because this is the first real proof that moves the long-term goal.",
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
        "why_now_summary": "Because this is the first real proof that moves the long-term goal.",
        "single_next_action_summary": "现在先完成这一步：Publish the first public artifact",
    }


def test_buddy_current_focus_resolver_does_not_leak_execution_core_focus_when_profile_scaffold_missing() -> None:
    resolver = build_buddy_current_focus_resolver(
        agent_profile_service=SimpleNamespace(
            get_agent=lambda agent_id: SimpleNamespace(current_focus="Ship the first proof artifact"),
        ),
        growth_target_repository=SimpleNamespace(
            get_active_target=lambda profile_id: SimpleNamespace(
                why_it_matters="Because the current cycle must start with a visible win.",
            ),
        ),
        industry_instance_repository=SimpleNamespace(get_instance=lambda instance_id: None),
        assignment_service=SimpleNamespace(list_assignments=lambda **kwargs: []),
        backlog_service=SimpleNamespace(list_open_items=lambda **kwargs: []),
    )

    payload = resolver("profile-1")

    assert payload == {
        "why_now_summary": "Because the current cycle must start with a visible win.",
    }


def test_buddy_current_focus_resolver_prefers_active_domain_instance_binding() -> None:
    resolver = build_buddy_current_focus_resolver(
        agent_profile_service=SimpleNamespace(),
        growth_target_repository=SimpleNamespace(
            get_active_target=lambda profile_id: SimpleNamespace(
                why_it_matters="Because this trading loop has to start from the first verified move.",
            ),
        ),
        domain_capability_repository=SimpleNamespace(
            get_active_domain_capability=lambda profile_id: SimpleNamespace(
                industry_instance_id="buddy:profile-1:domain-stocks",
            ),
        ),
        industry_instance_repository=SimpleNamespace(
            get_instance=lambda instance_id: (
                SimpleNamespace(
                    instance_id=instance_id,
                    current_cycle_id="cycle-stocks-1",
                )
                if instance_id == "buddy:profile-1:domain-stocks"
                else None
            ),
            list_instances=lambda **kwargs: [],
        ),
        assignment_service=SimpleNamespace(
            list_assignments=lambda **kwargs: [
                SimpleNamespace(status="queued", summary="Review yesterday's watchlist and set today's risk cap"),
            ],
        ),
        backlog_service=SimpleNamespace(list_open_items=lambda **kwargs: []),
    )

    payload = resolver("profile-1")

    assert payload["current_task_summary"] == "Review yesterday's watchlist and set today's risk cap"
    assert payload["why_now_summary"] == (
        "Because this trading loop has to start from the first verified move."
    )
    assert payload["single_next_action_summary"].endswith(
        "Review yesterday's watchlist and set today's risk cap",
    )


def test_resolve_active_human_assist_focus_prefers_open_human_task() -> None:
    payload = resolve_active_human_assist_focus(
        "profile-1",
        SimpleNamespace(
            list_tasks=lambda **kwargs: [
                HumanAssistTaskRecord(
                    profile_id="profile-1",
                    chat_thread_id="chat-1",
                    title="Already queued",
                    summary="This should be ignored once the runtime is already resuming.",
                    task_type="host-handoff-return",
                    status="resume_queued",
                    required_action="Wait for runtime resume",
                ),
                HumanAssistTaskRecord(
                    profile_id="profile-1",
                    chat_thread_id="chat-2",
                    title="Go on-site",
                    summary="Human checkpoint",
                    task_type="host-handoff-return",
                    status="issued",
                    required_action="Visit the office and submit the paperwork.",
                ),
            ],
        ),
    )

    assert payload is not None
    assert payload["current_task_summary"] == "Visit the office and submit the paperwork."
    assert payload["single_next_action_summary"].endswith(
        "Visit the office and submit the paperwork.",
    )
