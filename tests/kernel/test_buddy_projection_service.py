# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.state.models import HumanAssistTaskRecord
from copaw.state import SQLiteStateStore
from copaw.state.repositories_buddy import (
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)


def _build_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "buddy-projection.sqlite3")
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    onboarding = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        onboarding_session_repository=session_repository,
    )
    projection = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        onboarding_session_repository=session_repository,
        current_focus_resolver=lambda profile_id: {
            "profile_id": profile_id,
            "current_task_summary": "Ship the first portfolio case study",
            "why_now_summary": "Because this is the first proof that moves the final goal out of imagination.",
        },
    )
    return onboarding, projection


def test_buddy_projection_derives_growth_from_formal_truth(tmp_path) -> None:
    onboarding, projection = _build_services(tmp_path)
    identity = onboarding.submit_identity(
        display_name="Alex",
        profession="Designer",
        current_stage="transition",
        interests=["writing", "systems"],
        strengths=["systems thinking"],
        constraints=["time"],
        goal_intention="Build a meaningful long-term creative career.",
    )
    clarification = onboarding.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want leverage, proof of work, and independence.",
        existing_question_count=9,
    )
    onboarding.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
    )
    onboarding.name_buddy(session_id=identity.session_id, buddy_name="Nova")

    projection_payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)

    assert projection_payload.growth.intimacy >= 0
    assert projection_payload.growth.communication_count >= 2
    assert projection_payload.presentation.buddy_name == "Nova"
    assert projection_payload.presentation.current_task_summary == "Ship the first portfolio case study"
    assert projection_payload.presentation.why_now_summary.startswith("Because this is the first proof")


def test_buddy_projection_requires_profile_scope_when_multiple_profiles_exist(tmp_path) -> None:
    onboarding, projection = _build_services(tmp_path)
    first = onboarding.submit_identity(
        display_name="Alpha",
        profession="Designer",
        current_stage="transition",
        interests=["writing"],
        strengths=["systems thinking"],
        constraints=["time"],
        goal_intention="Build a meaningful long-term creative career.",
    )
    second = onboarding.submit_identity(
        display_name="Beta",
        profession="Operator",
        current_stage="exploring",
        interests=["content"],
        strengths=["consistency"],
        constraints=["money"],
        goal_intention="Build a durable direction with leverage.",
    )

    assert first.profile.profile_id != second.profile.profile_id

    try:
        projection.build_chat_surface()
    except ValueError as exc:
        assert "profile_id" in str(exc)
    else:
        raise AssertionError("expected Buddy surface to require explicit profile_id")


def test_buddy_projection_filters_human_assist_fallback_by_profile(tmp_path) -> None:
    onboarding, _projection = _build_services(tmp_path)
    identity = onboarding.submit_identity(
        display_name="Mina",
        profession="Operator",
        current_stage="exploring",
        interests=["content"],
        strengths=["consistency"],
        constraints=["money"],
        goal_intention="Find a real long-term direction.",
    )
    target_profile_id = identity.profile.profile_id
    other_profile_id = "profile-other"

    class _HumanAssistStub:
        def list_tasks(self, limit: int = 20):
            del limit
            return [
                HumanAssistTaskRecord(
                    profile_id=other_profile_id,
                    chat_thread_id="chat-2",
                    title="Other profile task",
                    summary="This should not leak across profiles.",
                    task_type="host-handoff-return",
                    status="issued",
                    required_action="Do the unrelated task",
                ),
                HumanAssistTaskRecord(
                    profile_id=target_profile_id,
                    chat_thread_id="chat-1",
                    title="Target profile task",
                    summary="This is the real current task.",
                    task_type="host-handoff-return",
                    status="issued",
                    required_action="Ship the scoped task",
                ),
            ]

    projection = BuddyProjectionService(
        profile_repository=_projection._profile_repository,
        growth_target_repository=_projection._growth_target_repository,
        relationship_repository=_projection._relationship_repository,
        onboarding_session_repository=_projection._onboarding_session_repository,
        human_assist_task_service=_HumanAssistStub(),
        current_focus_resolver=lambda _profile_id: {},
    )

    payload = projection.build_chat_surface(profile_id=target_profile_id)

    assert payload.presentation.current_task_summary == "Ship the scoped task"

