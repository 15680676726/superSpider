# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.kernel.buddy_domain_capability import derive_buddy_domain_key
from copaw.state import (
    AgentReportRecord,
    AssignmentRecord,
    BuddyDomainCapabilityRecord,
    GrowthTarget,
    HumanProfile,
    IndustryInstanceRecord,
    SQLiteStateStore,
)
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


def test_buddy_projection_preserves_explicit_legacy_control_thread_after_binding_backfill(
    tmp_path,
) -> None:
    _onboarding, projection, store = _build_services(tmp_path)
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    domain_repository = SqliteBuddyDomainCapabilityRepository(store)
    industry_repository = SqliteIndustryInstanceRepository(store)

    profile = HumanProfile(
        profile_id="profile-1",
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Return to creator work.",
    )
    profile_repository.upsert_profile(profile)
    growth_target_repository.upsert_target(
        GrowthTarget(
            profile_id=profile.profile_id,
            primary_direction="creator",
            final_goal="Return to creator work.",
            why_it_matters="This is still the real path.",
        ),
    )
    legacy_instance_id = f"buddy:{profile.profile_id}"
    industry_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id=legacy_instance_id,
            label=profile.display_name,
            summary="Legacy buddy carrier",
            owner_scope=profile.profile_id,
            status="active",
            profile_payload={},
            team_payload={},
            execution_core_identity_payload={},
            agent_ids=[],
            lifecycle_status="running",
            autonomy_status="coordinating",
        ),
    )
    historical_thread_id = "industry-chat:historical-thread:execution-core"
    domain_repository.upsert_domain_capability(
        BuddyDomainCapabilityRecord(
            profile_id=profile.profile_id,
            domain_key=derive_buddy_domain_key("creator"),
            domain_label="Creator",
            status="active",
            industry_instance_id="",
            control_thread_id=historical_thread_id,
        ),
    )

    payload = projection.build_chat_surface(profile_id=profile.profile_id)
    active = domain_repository.get_active_domain_capability(profile.profile_id)

    assert active is not None
    assert active.industry_instance_id == legacy_instance_id
    assert active.control_thread_id == historical_thread_id
    assert payload.execution_carrier is not None
    assert payload.execution_carrier["instance_id"] == legacy_instance_id
    assert payload.execution_carrier["control_thread_id"] == historical_thread_id
