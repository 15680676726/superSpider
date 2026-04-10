# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.industry.models import IndustryProfile
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_service import (
    BuddyOnboardingService,
    _CREATOR_DIRECTION,
    _HEALTH_DIRECTION,
    _STOCKS_DIRECTION,
)
from copaw.kernel.buddy_domain_capability import derive_buddy_domain_key
from copaw.state import SQLiteStateStore
from copaw.state.main_brain_service import (
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from copaw.state.repositories import (
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


def _build_service(tmp_path) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding.sqlite3")
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        onboarding_reasoner=DeterministicBuddyReasoner(),
    )


def _build_service_with_planning(tmp_path) -> tuple[BuddyOnboardingService, SQLiteStateStore]:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-planning.sqlite3")
    industry_repository = SqliteIndustryInstanceRepository(store)
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
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
    service = BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
        domain_capability_growth_service=growth_service,
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


def test_buddy_onboarding_derives_direction_candidates_from_chinese_profile(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="林夏",
        profession="内容运营",
        current_stage="转型期",
        interests=["写作", "内容", "表达"],
        strengths=["长期主义", "表达能力"],
        constraints=["时间有限"],
        goal_intention="我想找到能长期积累、能靠作品和内容建立独立收入的方向。",
    )

    result = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="我不想一直做零碎执行，我想慢慢建立自己的内容作品和长期影响力。",
        existing_question_count=9,
    )

    assert result.finished is True
    assert _CREATOR_DIRECTION in result.candidate_directions
    assert result.recommended_direction == _CREATOR_DIRECTION


def test_buddy_onboarding_derives_video_creator_direction_from_chinese_profile(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="周舟",
        profession="社区运营",
        current_stage="探索期",
        interests=["视频表达", "讲故事"],
        strengths=["镜头感", "长期主义"],
        constraints=["时间有限"],
        goal_intention="我想做个人IP，通过视频和观点输出建立影响力。",
    )

    result = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="我不想一直做运营执行，我想做一个有内容作品和个人品牌的人。",
        existing_question_count=9,
    )

    assert result.finished is True
    assert _CREATOR_DIRECTION in result.candidate_directions
    assert result.recommended_direction == _CREATOR_DIRECTION


def test_buddy_onboarding_finishes_early_for_clear_stock_trading_goal(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Kai",
        profession="Analyst",
        current_stage="restart",
        interests=["stocks", "trading"],
        strengths=["discipline"],
        constraints=["money"],
        goal_intention="I want to build a real stock trading path and achieve financial freedom.",
    )

    result = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a durable trading system, better risk control, and independent income.",
    )

    assert result.finished is True
    assert result.question_count == 2
    assert result.next_question == ""
    assert _STOCKS_DIRECTION in result.candidate_directions
    assert result.recommended_direction == _STOCKS_DIRECTION


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
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a direction with growth and independent leverage.",
        existing_question_count=9,
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    assert result.growth_target.primary_direction == clarification.recommended_direction
    assert result.relationship.encouragement_style == "old-friend"
    assert result.domain_capability.domain_key == derive_buddy_domain_key(
        clarification.recommended_direction,
    )
    assert result.domain_capability.status == "active"


def test_buddy_confirm_primary_direction_accepts_free_text_direction_override(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Mina",
        profession="Operator",
        current_stage="restart",
        interests=["investing"],
        strengths=["consistency"],
        constraints=["money"],
        goal_intention="I want a real stock trading direction.",
    )
    service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want to stop drifting and build a disciplined trading path.",
        existing_question_count=9,
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction="Build a disciplined stock trading path with real risk control.",
        capability_action="start-new",
    )

    assert result.growth_target.primary_direction == (
        "Build a disciplined stock trading path with real risk control."
    )
    assert result.domain_capability.domain_key == derive_buddy_domain_key(
        result.growth_target.primary_direction,
    )


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
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a direction with growth and independent leverage.",
        existing_question_count=9,
    )
    service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    relationship = service.name_buddy(
        session_id=identity.session_id,
        buddy_name="Mochi",
    )

    assert relationship.buddy_name == "Mochi"


def test_submit_identity_reuses_single_current_profile(tmp_path) -> None:
    service = _build_service(tmp_path)

    first = service.submit_identity(
        display_name="Mina",
        profession="Operator",
        current_stage="exploring",
        interests=["content"],
        strengths=["consistency"],
        constraints=["money"],
        goal_intention="I want a bigger life direction.",
    )
    second = service.submit_identity(
        display_name="Mina Updated",
        profession="Builder",
        current_stage="restarting",
        interests=["systems"],
        strengths=["clarity"],
        constraints=["time"],
        goal_intention="I want one real long-term direction.",
    )

    assert second.profile.profile_id == first.profile.profile_id
    assert second.profile.display_name == "Mina Updated"
    assert second.profile.profession == "Builder"
    assert service._profile_repository.count_profiles() == 1  # pylint: disable=protected-access


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
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a long-term creator path with proof of work and income autonomy.",
        existing_question_count=9,
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    assert result.execution_carrier is not None
    assert result.domain_capability.industry_instance_id
    assert result.execution_carrier["instance_id"] == result.domain_capability.industry_instance_id
    assert result.execution_carrier["control_thread_id"] == result.domain_capability.control_thread_id
    assert result.execution_carrier["team_generated"] is True

    industry_repository = SqliteIndustryInstanceRepository(store)
    lane_repository = SqliteOperatingLaneRepository(store)
    backlog_repository = SqliteBacklogItemRepository(store)
    cycle_repository = SqliteOperatingCycleRepository(store)
    assignment_repository = SqliteAssignmentRepository(store)

    instance = industry_repository.get_instance(result.domain_capability.industry_instance_id)
    assert instance is not None
    assert instance.current_cycle_id
    assert instance.autonomy_status == "coordinating"

    lanes = lane_repository.list_lanes(industry_instance_id=instance.instance_id)
    assert any(lane.industry_instance_id == instance.instance_id for lane in lanes)

    backlog = backlog_repository.list_items(industry_instance_id=instance.instance_id)
    assert any(item.industry_instance_id == instance.instance_id for item in backlog)

    cycles = cycle_repository.list_cycles(industry_instance_id=instance.instance_id)
    assert any(cycle.industry_instance_id == instance.instance_id for cycle in cycles)

    assignments = assignment_repository.list_assignments(industry_instance_id=instance.instance_id)
    assert any(assignment.industry_instance_id == instance.instance_id for assignment in assignments)
    assert result.domain_capability.capability_points == 0
    assert result.domain_capability.capability_score == 0
    assert result.domain_capability.strategy_score == 0
    assert result.domain_capability.evolution_stage == "seed"


def test_confirm_primary_direction_writes_direction_first_industry_profile(tmp_path) -> None:
    service, store = _build_service_with_planning(tmp_path)
    identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing", "content"],
        strengths=["storytelling"],
        constraints=["time", "money"],
        goal_intention="I want a real creator direction that can change my life.",
    )
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a long-term creator path with proof of work and income autonomy.",
        existing_question_count=9,
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    industry_repository = SqliteIndustryInstanceRepository(store)
    instance = industry_repository.get_instance(result.domain_capability.industry_instance_id)

    assert instance is not None
    profile = IndustryProfile.model_validate(instance.profile_payload)
    assert profile.industry == result.growth_target.primary_direction
    assert result.growth_target.final_goal in profile.goals
    assert set(profile.constraints) >= {"time", "money"}
    assert "profession" not in instance.profile_payload
    assert "current_stage" not in instance.profile_payload


def test_confirm_primary_direction_start_new_creates_fresh_domain_carrier_binding(tmp_path) -> None:
    service, store = _build_service_with_planning(tmp_path)
    creator_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Build a creator path with long-term proof of work.",
    )
    creator_clarification = service.answer_clarification_turn(
        session_id=creator_identity.session_id,
        answer="I want a creator direction with proof of work and leverage.",
        existing_question_count=9,
    )
    creator = service.confirm_primary_direction(
        session_id=creator_identity.session_id,
        selected_direction=creator_clarification.recommended_direction,
        capability_action="start-new",
    )

    health_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["health", "fitness"],
        strengths=["consistency"],
        constraints=["time"],
        goal_intention="I need to rebuild my health and discipline.",
    )
    service.answer_clarification_turn(
        session_id=health_identity.session_id,
        answer="I want to rebuild energy, exercise, and stable health habits.",
        existing_question_count=9,
    )
    health = service.confirm_primary_direction(
        session_id=health_identity.session_id,
        selected_direction=_HEALTH_DIRECTION,
        capability_action="start-new",
    )

    assert creator.domain_capability.industry_instance_id
    assert creator.domain_capability.control_thread_id
    assert health.domain_capability.industry_instance_id
    assert health.domain_capability.control_thread_id
    assert health.domain_capability.industry_instance_id != creator.domain_capability.industry_instance_id
    assert health.domain_capability.control_thread_id != creator.domain_capability.control_thread_id
    assert SqliteIndustryInstanceRepository(store).get_instance(
        health.domain_capability.industry_instance_id,
    ) is not None


def test_confirm_primary_direction_restore_archived_reuses_archived_carrier_binding(tmp_path) -> None:
    service = _build_service_with_planning(tmp_path)[0]
    creator_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Build a creator path with long-term proof of work.",
    )
    creator_clarification = service.answer_clarification_turn(
        session_id=creator_identity.session_id,
        answer="I want a creator direction with proof of work and leverage.",
        existing_question_count=9,
    )
    creator = service.confirm_primary_direction(
        session_id=creator_identity.session_id,
        selected_direction=creator_clarification.recommended_direction,
        capability_action="start-new",
    )
    creator_instance_id = creator.domain_capability.industry_instance_id
    creator_thread_id = creator.domain_capability.control_thread_id

    health_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["health", "fitness"],
        strengths=["consistency"],
        constraints=["time"],
        goal_intention="I need to rebuild my health and discipline.",
    )
    service.answer_clarification_turn(
        session_id=health_identity.session_id,
        answer="I want to rebuild energy, exercise, and stable health habits.",
        existing_question_count=9,
    )
    service.confirm_primary_direction(
        session_id=health_identity.session_id,
        selected_direction=_HEALTH_DIRECTION,
        capability_action="start-new",
    )

    creator_return_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Return to creator work.",
    )
    creator_return_clarification = service.answer_clarification_turn(
        session_id=creator_return_identity.session_id,
        answer="I want to return to the same creator direction I was already building.",
        existing_question_count=9,
    )
    preview = service.preview_primary_direction_transition(
        session_id=creator_return_identity.session_id,
        selected_direction=creator_return_clarification.recommended_direction,
    )
    restored = service.confirm_primary_direction(
        session_id=creator_return_identity.session_id,
        selected_direction=creator_return_clarification.recommended_direction,
        capability_action="restore-archived",
        target_domain_id=preview.archived_matches[0]["domain_id"],
    )

    assert restored.domain_capability.industry_instance_id == creator_instance_id
    assert restored.domain_capability.control_thread_id == creator_thread_id
    assert restored.execution_carrier is not None
    assert restored.execution_carrier["instance_id"] == creator_instance_id
    assert restored.execution_carrier["control_thread_id"] == creator_thread_id


def test_record_chat_interaction_increments_strong_pull_for_stuck_or_avoidance_messages(
    tmp_path,
) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["clarity"],
        constraints=["time"],
        goal_intention="Build a real long-term direction.",
    )

    relationship = service.record_chat_interaction(
        profile_id=identity.profile.profile_id,
        user_message="I'm stuck, I keep avoiding this, and I don't want to do it right now.",
        interaction_mode="chat",
    )

    assert relationship is not None
    assert relationship.strong_pull_count == 1
    assert relationship.communication_count == 0
    assert relationship.companion_experience == 0


def test_record_chat_interaction_advances_growth_only_on_runtime_checkpoint(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["clarity"],
        constraints=["time"],
        goal_intention="Build a real long-term direction.",
    )

    relationship = service.record_chat_interaction(
        profile_id=identity.profile.profile_id,
        user_message="I completed the submission and got an accepted checkpoint.",
        interaction_mode="checkpoint",
    )

    assert relationship is not None
    assert relationship.communication_count == 1
    assert relationship.companion_experience > 0


def test_preview_primary_direction_transition_keeps_same_domain_capability(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Build a creator path with long-term proof of work.",
    )
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a creator direction with proof of work and leverage.",
        existing_question_count=9,
    )
    first = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )
    seeded = first.domain_capability.model_copy(
        update={"capability_score": 68, "evolution_stage": "seasoned"},
    )
    service._domain_capability_repository.upsert_domain_capability(  # pylint: disable=protected-access
        seeded,
    )

    second_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing", "content"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Scale the same creator direction further.",
    )
    second_clarification = service.answer_clarification_turn(
        session_id=second_identity.session_id,
        answer="I want to stay on the same creator track and push it further.",
        existing_question_count=9,
    )

    preview = service.preview_primary_direction_transition(
        session_id=second_identity.session_id,
        selected_direction=second_clarification.recommended_direction,
    )
    result = service.confirm_primary_direction(
        session_id=second_identity.session_id,
        selected_direction=second_clarification.recommended_direction,
        capability_action="keep-active",
    )

    assert preview.suggestion_kind == "same-domain"
    assert preview.recommended_action == "keep-active"
    assert result.domain_capability.capability_score == 68
    assert result.domain_capability.evolution_stage == "seasoned"


def test_confirm_primary_direction_archives_old_domain_and_starts_new_one(tmp_path) -> None:
    service = _build_service(tmp_path)
    creator_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Build a creator path with long-term proof of work.",
    )
    creator_clarification = service.answer_clarification_turn(
        session_id=creator_identity.session_id,
        answer="I want a creator direction with proof of work and leverage.",
        existing_question_count=9,
    )
    creator_result = service.confirm_primary_direction(
        session_id=creator_identity.session_id,
        selected_direction=creator_clarification.recommended_direction,
        capability_action="start-new",
    )
    service._domain_capability_repository.upsert_domain_capability(  # pylint: disable=protected-access
        creator_result.domain_capability.model_copy(
            update={"capability_score": 68, "evolution_stage": "seasoned"},
        )
    )

    health_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["health", "fitness"],
        strengths=["consistency"],
        constraints=["time"],
        goal_intention="I need to rebuild my health and discipline.",
    )
    health_clarification = service.answer_clarification_turn(
        session_id=health_identity.session_id,
        answer="I want to rebuild energy, exercise, and stable health habits.",
        existing_question_count=9,
    )

    preview = service.preview_primary_direction_transition(
        session_id=health_identity.session_id,
        selected_direction=_HEALTH_DIRECTION,
    )
    result = service.confirm_primary_direction(
        session_id=health_identity.session_id,
        selected_direction=_HEALTH_DIRECTION,
        capability_action="start-new",
    )
    records = service._domain_capability_repository.list_domain_capabilities(  # pylint: disable=protected-access
        creator_identity.profile.profile_id,
    )
    creator_record = next(
        record
        for record in records
        if record.domain_key == derive_buddy_domain_key(creator_result.growth_target.primary_direction)
    )

    assert health_clarification.recommended_direction == _HEALTH_DIRECTION
    assert preview.suggestion_kind == "start-new-domain"
    assert result.domain_capability.domain_key == derive_buddy_domain_key(
        result.growth_target.primary_direction,
    )
    assert result.domain_capability.capability_score == 0
    assert result.domain_capability.evolution_stage == "seed"
    assert creator_record.status == "archived"
    assert creator_record.capability_score == 68


def test_confirm_primary_direction_restores_matching_archived_domain(tmp_path) -> None:
    service = _build_service(tmp_path)
    creator_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Build a creator path with long-term proof of work.",
    )
    creator_clarification = service.answer_clarification_turn(
        session_id=creator_identity.session_id,
        answer="I want a creator direction with proof of work and leverage.",
        existing_question_count=9,
    )
    creator_result = service.confirm_primary_direction(
        session_id=creator_identity.session_id,
        selected_direction=creator_clarification.recommended_direction,
        capability_action="start-new",
    )
    service._domain_capability_repository.upsert_domain_capability(  # pylint: disable=protected-access
        creator_result.domain_capability.model_copy(
            update={"capability_score": 68, "evolution_stage": "seasoned"},
        )
    )

    health_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["health", "fitness"],
        strengths=["consistency"],
        constraints=["time"],
        goal_intention="I need to rebuild my health and discipline.",
    )
    service.answer_clarification_turn(
        session_id=health_identity.session_id,
        answer="I want to rebuild energy, exercise, and stable health habits.",
        existing_question_count=9,
    )
    service.confirm_primary_direction(
        session_id=health_identity.session_id,
        selected_direction=_HEALTH_DIRECTION,
        capability_action="start-new",
    )

    creator_return_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Return to creator work.",
    )
    creator_return_clarification = service.answer_clarification_turn(
        session_id=creator_return_identity.session_id,
        answer="I want to return to the same creator direction I was already building.",
        existing_question_count=9,
    )

    preview = service.preview_primary_direction_transition(
        session_id=creator_return_identity.session_id,
        selected_direction=creator_return_clarification.recommended_direction,
    )
    restored = service.confirm_primary_direction(
        session_id=creator_return_identity.session_id,
        selected_direction=creator_return_clarification.recommended_direction,
        capability_action="restore-archived",
        target_domain_id=preview.archived_matches[0]["domain_id"],
    )
    active = service._domain_capability_repository.get_active_domain_capability(  # pylint: disable=protected-access
        creator_identity.profile.profile_id,
    )

    assert preview.suggestion_kind == "switch-to-archived-domain"
    assert preview.recommended_action == "restore-archived"
    assert restored.domain_capability.domain_key == derive_buddy_domain_key(
        creator_result.growth_target.primary_direction,
    )
    assert restored.domain_capability.capability_score == 68
    assert restored.domain_capability.evolution_stage == "seasoned"
    assert active is not None
    assert active.domain_key == derive_buddy_domain_key(
        creator_result.growth_target.primary_direction,
    )
