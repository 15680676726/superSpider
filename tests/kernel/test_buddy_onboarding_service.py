# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.state import SQLiteStateStore
from copaw.state.main_brain_service import (
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from copaw.state.models import IndustryInstanceRecord
from copaw.state.repositories_buddy import (
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)
from copaw.state.repositories import (
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingCycleRepository,
    SqliteOperatingLaneRepository,
)


def _build_service(tmp_path) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding.sqlite3")
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
    )


def _build_service_with_planning(tmp_path) -> tuple[BuddyOnboardingService, SQLiteStateStore]:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-planning.sqlite3")
    industry_repository = SqliteIndustryInstanceRepository(store)
    service = BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        industry_instance_repository=industry_repository,
        operating_lane_service=OperatingLaneService(
            repository=SqliteOperatingLaneRepository(store),
        ),
        backlog_service=BacklogService(
            repository=SqliteBacklogItemRepository(store),
        ),
        operating_cycle_service=OperatingCycleService(
            repository=SqliteOperatingCycleRepository(store),
        ),
        assignment_service=AssignmentService(
            repository=SqliteAssignmentRepository(store),
        ),
    )
    return service, store


def test_buddy_onboarding_caps_clarification_questions(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Alex",
        profession="Designer",
        current_stage="transition",
        interests=["writing", "systems"],
        strengths=["systems thinking"],
        constraints=["time"],
        goal_intention="I feel lost but want meaningful long-term growth.",
    )

    result = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I still feel lost and need help choosing a direction.",
    )

    assert result.finished is False
    assert result.question_count == 2

    capped = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I still feel lost",
        existing_question_count=9,
    )

    assert capped.finished is True
    assert capped.question_count == 9
    assert 1 <= len(capped.candidate_directions) <= 3
    assert capped.recommended_direction in capped.candidate_directions


def test_buddy_onboarding_requires_exactly_one_primary_direction(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Mina",
        profession="Operator",
        current_stage="exploring",
        interests=["content"],
        strengths=["consistency"],
        constraints=["money"],
        goal_intention="I want a bigger life direction.",
    )
    service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a direction with growth and independent leverage.",
        existing_question_count=9,
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction="Build an independent creator-business growth path",
    )

    assert result.growth_target.primary_direction == (
        "Build an independent creator-business growth path"
    )
    assert result.relationship.encouragement_style == "old-friend"


def test_buddy_naming_updates_relationship(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Mina",
        profession="Operator",
        current_stage="exploring",
        interests=["content"],
        strengths=["consistency"],
        constraints=["money"],
        goal_intention="I want a bigger life direction.",
    )
    service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a direction with growth and independent leverage.",
        existing_question_count=9,
    )
    service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction="Build an independent creator-business growth path",
    )

    relationship = service.name_buddy(
        session_id=identity.session_id,
        buddy_name="Mochi",
    )

    assert relationship.buddy_name == "Mochi"


def test_confirm_primary_direction_generates_formal_growth_scaffold(tmp_path) -> None:
    service, store = _build_service_with_planning(tmp_path)
    identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing", "content"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="I want a real creator direction that can change my life.",
    )
    service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a long-term creator path with proof of work and income autonomy.",
        existing_question_count=9,
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction="Build an independent creator-business growth path",
    )

    industry_repository = SqliteIndustryInstanceRepository(store)
    lane_repository = SqliteOperatingLaneRepository(store)
    backlog_repository = SqliteBacklogItemRepository(store)
    cycle_repository = SqliteOperatingCycleRepository(store)
    assignment_repository = SqliteAssignmentRepository(store)
    instance = industry_repository.get_instance(f"buddy:{identity.profile.profile_id}")

    assert result.growth_target.current_cycle_label
    assert instance is not None
    assert instance.label == identity.profile.display_name
    assert lane_repository.list_lanes(industry_instance_id=instance.instance_id, limit=None)
    assert backlog_repository.list_items(industry_instance_id=instance.instance_id, limit=None)
    assert cycle_repository.get_cycle(instance.current_cycle_id or "") is not None
    assert assignment_repository.list_assignments(industry_instance_id=instance.instance_id, limit=None)
