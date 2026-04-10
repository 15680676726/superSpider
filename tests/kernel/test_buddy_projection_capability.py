# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.state import AgentReportRecord, AssignmentRecord, SQLiteStateStore
from copaw.state.main_brain_service import (
    AgentReportService,
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingCycleRepository,
    SqliteOperatingLaneRepository,
)
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)
from tests.shared.buddy_reasoners import DeterministicBuddyReasoner


def _build_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "buddy-projection-capability.sqlite3")
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    industry_repository = SqliteIndustryInstanceRepository(store)
    lane_service = OperatingLaneService(repository=SqliteOperatingLaneRepository(store))
    backlog_service = BacklogService(repository=SqliteBacklogItemRepository(store))
    cycle_service = OperatingCycleService(repository=SqliteOperatingCycleRepository(store))
    assignment_service = AssignmentService(repository=SqliteAssignmentRepository(store))
    report_service = AgentReportService(repository=SqliteAgentReportRepository(store))
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
        agent_report_service=report_service,
    )
    onboarding = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
        domain_capability_growth_service=growth_service,
        onboarding_reasoner=DeterministicBuddyReasoner(),
    )
    projection = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        domain_capability_growth_service=growth_service,
        current_focus_resolver=lambda profile_id: {
            "profile_id": profile_id,
            "current_task_summary": "Ship the first portfolio case study",
            "why_now_summary": "Because this is the first proof that moves the final goal out of imagination.",
            "single_next_action_summary": "Open the draft and write the headline plus three proof points.",
        },
    )
    return onboarding, projection, store


def test_buddy_projection_refreshes_stage_from_runtime_capability_growth(tmp_path) -> None:
    onboarding, projection, store = _build_services(tmp_path)
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
    assignment_repository = SqliteAssignmentRepository(store)
    report_repository = SqliteAgentReportRepository(store)
    instance_id = result.domain_capability.industry_instance_id
    assignments = assignment_repository.list_assignments(industry_instance_id=instance_id)
    assert assignments
    first_assignment = assignments[0]
    assignment_repository.upsert_assignment(
        first_assignment.model_copy(
            update={
                "status": "completed",
                "evidence_ids": ["ev-proof-1", "ev-proof-2"],
                "last_report_id": "report-buddy-1",
            }
        )
    )
    report_repository.upsert_report(
        AgentReportRecord(
            id="report-buddy-1",
            industry_instance_id=instance_id,
            cycle_id=first_assignment.cycle_id,
            assignment_id=first_assignment.id,
            lane_id=first_assignment.lane_id,
            headline="First proof shipped",
            summary="The first portfolio case study is now published.",
            status="recorded",
            result="completed",
            evidence_ids=["ev-proof-1", "ev-proof-2"],
        )
    )

    payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)

    assert payload.growth.capability_score > result.domain_capability.capability_score
    assert payload.growth.capability_points == 2
    assert payload.growth.settled_closure_count == 1
    assert payload.growth.execution_score > 0
    assert payload.growth.evidence_score > 0
    assert payload.growth.evolution_stage == "seed"
    assert payload.presentation.current_form == payload.growth.evolution_stage
    assert payload.growth.domain_label == result.domain_capability.domain_label


def test_relationship_experience_no_longer_upgrades_stage_without_domain_progress(tmp_path) -> None:
    onboarding, projection, _store = _build_services(tmp_path)
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
    baseline = projection.build_chat_surface(profile_id=identity.profile.profile_id)
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

    assert payload.growth.evolution_stage == baseline.growth.evolution_stage
    assert payload.growth.capability_score == baseline.growth.capability_score


def test_invalid_closure_without_report_or_evidence_does_not_add_points(tmp_path) -> None:
    onboarding, projection, store = _build_services(tmp_path)
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
    assignment_repository = SqliteAssignmentRepository(store)
    instance_id = result.domain_capability.industry_instance_id
    assignments = assignment_repository.list_assignments(industry_instance_id=instance_id)
    assert assignments
    first_assignment = assignments[0]
    assignment_repository.upsert_assignment(
        AssignmentRecord.model_validate(
            {
                **first_assignment.model_dump(mode="json"),
                "status": "completed",
                "evidence_ids": [],
                "last_report_id": None,
            }
        )
    )

    payload = projection.build_chat_surface(profile_id=identity.profile.profile_id)

    assert payload.growth.capability_points == 0
    assert payload.growth.settled_closure_count == 0
    assert payload.growth.evolution_stage == "seed"
