# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.state.models import HumanAssistTaskRecord
from copaw.state import SQLiteStateStore
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)
from tests.shared.buddy_reasoners import DeterministicBuddyReasoner


def _build_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "buddy-projection.sqlite3")
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    onboarding = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        onboarding_reasoner=DeterministicBuddyReasoner(),
    )
    projection = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        current_focus_resolver=lambda profile_id: {
            "profile_id": profile_id,
            "current_task_summary": "Ship the first portfolio case study",
            "why_now_summary": "Because this is the first proof that moves the final goal out of imagination.",
            "single_next_action_summary": "Open the draft and write the headline plus three proof points.",
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
    confirmation = onboarding.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )
    onboarding.name_buddy(session_id=identity.session_id, buddy_name="Nova")

    projection_payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)
    summary = projection.build_cockpit_summary(profile_id=identity.profile.profile_id)

    assert projection_payload.execution_carrier is not None
    assert (
        projection_payload.execution_carrier["instance_id"]
        == confirmation.domain_capability.industry_instance_id
    )
    assert (
        projection_payload.execution_carrier["thread_id"]
        == confirmation.domain_capability.control_thread_id
    )
    assert (
        projection_payload.execution_carrier["control_thread_id"]
        == confirmation.domain_capability.control_thread_id
    )
    assert projection_payload.growth.intimacy >= 0
    assert projection_payload.growth.communication_count >= 2
    assert projection_payload.growth.capability_points == 0
    assert summary["capability_points"] == projection_payload.growth.capability_points
    assert projection_payload.presentation.buddy_name == "Nova"
    assert projection_payload.presentation.current_task_summary == "Ship the first portfolio case study"
    assert projection_payload.presentation.why_now_summary.startswith("Because this is the first proof")
    assert projection_payload.presentation.single_next_action_summary == (
        "Open the draft and write the headline plus three proof points."
    )


def test_buddy_projection_resolves_current_profile_without_explicit_binding(tmp_path) -> None:
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

    payload = projection.build_chat_surface()

    assert second.profile.profile_id == first.profile.profile_id
    assert payload.profile.profile_id == first.profile.profile_id
    assert payload.profile.display_name == "Beta"
    assert payload.profile.profession == "Operator"


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
        domain_capability_repository=_projection._domain_capability_repository,
        onboarding_session_repository=_projection._onboarding_session_repository,
        human_assist_task_service=_HumanAssistStub(),
        current_focus_resolver=lambda _profile_id: {},
    )

    payload = projection.build_chat_surface(profile_id=target_profile_id)

    assert payload.presentation.current_task_summary == "Ship the scoped task"


def test_buddy_projection_prefers_human_assist_task_over_carrier_assignment(tmp_path) -> None:
    onboarding, _projection = _build_services(tmp_path)
    identity = onboarding.submit_identity(
        display_name="Lena",
        profession="Operator",
        current_stage="building",
        interests=["operations"],
        strengths=["follow-through"],
        constraints=["time"],
        goal_intention="Build a durable operating system for my work.",
    )

    class _HumanAssistStub:
        def list_tasks(self, limit: int = 20, profile_id: str | None = None):
            del limit
            assert profile_id == identity.profile.profile_id
            return [
                HumanAssistTaskRecord(
                    profile_id=identity.profile.profile_id,
                    chat_thread_id="chat-human-1",
                    title="Go on-site",
                    summary="The buddy should surface the human checkpoint first.",
                    task_type="host-handoff-return",
                    status="issued",
                    required_action="Visit the office and submit the paperwork.",
                ),
            ]

    projection = BuddyProjectionService(
        profile_repository=_projection._profile_repository,
        growth_target_repository=_projection._growth_target_repository,
        relationship_repository=_projection._relationship_repository,
        domain_capability_repository=_projection._domain_capability_repository,
        onboarding_session_repository=_projection._onboarding_session_repository,
        human_assist_task_service=_HumanAssistStub(),
        current_focus_resolver=lambda _profile_id: {
            "current_task_summary": "Publish the first public artifact",
            "why_now_summary": "Because the carrier still needs forward motion after this checkpoint.",
            "single_next_action_summary": "Open the artifact draft and ship it.",
        },
    )

    payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)

    assert payload.presentation.current_task_summary == "Visit the office and submit the paperwork."
    assert payload.presentation.single_next_action_summary.endswith(
        "Visit the office and submit the paperwork.",
    )
    assert payload.presentation.why_now_summary == (
        "Because the carrier still needs forward motion after this checkpoint."
    )


def test_buddy_projection_honestly_degrades_when_runtime_focus_is_missing(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "buddy-projection-degrade.sqlite3")
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    onboarding = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=session_repository,
        onboarding_reasoner=DeterministicBuddyReasoner(),
    )
    identity = onboarding.submit_identity(
        display_name="Mina",
        profession="Operator",
        current_stage="restart",
        interests=["writing"],
        strengths=["clarity"],
        constraints=["time"],
        goal_intention="Build a durable direction.",
    )
    clarification = onboarding.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want leverage and long-term growth.",
        existing_question_count=9,
    )
    onboarding.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )
    projection = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=session_repository,
        current_focus_resolver=lambda _profile_id: {},
    )

    payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)

    assert payload.presentation.current_task_summary == ""
    assert payload.presentation.why_now_summary == ""
    assert payload.presentation.single_next_action_summary == ""


def test_buddy_projection_turns_relationship_memory_into_companion_strategy(tmp_path) -> None:
    onboarding, projection = _build_services(tmp_path)
    identity = onboarding.submit_identity(
        display_name="Kai",
        profession="Designer",
        current_stage="restart",
        interests=["writing"],
        strengths=["clarity"],
        constraints=["time"],
        goal_intention="I want a durable direction with visible proof of work.",
    )
    clarification = onboarding.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a long-term direction with proof, leverage, and less drift.",
        existing_question_count=9,
    )
    onboarding.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )
    onboarding.name_buddy(session_id=identity.session_id, buddy_name="Nova")
    relationship = projection._relationship_repository.get_relationship(  # pylint: disable=protected-access
        identity.profile.profile_id,
    )
    assert relationship is not None
    projection._relationship_repository.upsert_relationship(  # pylint: disable=protected-access
        relationship.model_copy(
            update={
                "effective_reminders": ["先把任务缩成一个最小动作"],
                "ineffective_reminders": ["高压催促"],
                "avoidance_patterns": ["刷短视频逃避"],
            },
        ),
    )

    payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)

    assert "最小动作" in payload.presentation.companion_strategy_summary
    assert "高压催促" in payload.presentation.companion_strategy_summary
    assert "刷短视频逃避" in payload.presentation.companion_strategy_summary

