# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.state import SQLiteStateStore
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)


def _build_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "buddy-projection-capability.sqlite3")
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


def test_buddy_projection_reads_stage_from_active_domain_capability(tmp_path) -> None:
    onboarding, projection = _build_services(tmp_path)
    identity = onboarding.submit_identity(
        display_name="Alex",
        profession="Designer",
        current_stage="transition",
        interests=["writing"],
        strengths=["systems thinking"],
        constraints=["time"],
        goal_intention="Build a meaningful long-term creative career.",
    )
    clarification = onboarding.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want leverage, proof of work, and independence.",
        existing_question_count=9,
    )
    result = onboarding.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )
    projection._domain_capability_repository.upsert_domain_capability(  # pylint: disable=protected-access
        result.domain_capability.model_copy(
            update={
                "capability_score": 63,
                "strategy_score": 18,
                "execution_score": 24,
                "evidence_score": 12,
                "stability_score": 9,
                "evolution_stage": "seasoned",
            },
        )
    )

    payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)

    assert payload.growth.evolution_stage == "seasoned"
    assert payload.growth.capability_score == 63
    assert payload.presentation.current_form == "seasoned"
    assert payload.growth.domain_label == "写作"


def test_relationship_experience_no_longer_upgrades_stage_without_domain_progress(tmp_path) -> None:
    onboarding, projection = _build_services(tmp_path)
    identity = onboarding.submit_identity(
        display_name="Alex",
        profession="Designer",
        current_stage="transition",
        interests=["writing"],
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
        capability_action="start-new",
    )
    relationship = projection._relationship_repository.get_relationship(  # pylint: disable=protected-access
        identity.profile.profile_id,
    )
    assert relationship is not None
    projection._relationship_repository.upsert_relationship(  # pylint: disable=protected-access
        relationship.model_copy(
            update={
                "companion_experience": 500,
                "communication_count": 80,
                "pleasant_interaction_score": 100,
            },
        )
    )

    payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)

    assert payload.growth.evolution_stage == "seed"
    assert payload.growth.capability_score == 0
