# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_onboarding_service import (
    BuddyOnboardingService,
    _CREATOR_DIRECTION,
)
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
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
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
    )

    assert result.growth_target.primary_direction == clarification.recommended_direction
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
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a direction with growth and independent leverage.",
        existing_question_count=9,
    )
    service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
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
    )

    assert result.execution_carrier is not None
    assert result.execution_carrier["instance_id"] == f"buddy:{result.growth_target.profile_id}"
    assert result.execution_carrier["team_generated"] is True

    industry_repository = SqliteIndustryInstanceRepository(store)
    lane_repository = SqliteOperatingLaneRepository(store)
    backlog_repository = SqliteBacklogItemRepository(store)
    cycle_repository = SqliteOperatingCycleRepository(store)
    assignment_repository = SqliteAssignmentRepository(store)

    instance = industry_repository.get_instance(f"buddy:{result.growth_target.profile_id}")
    assert instance is not None
    assert instance.current_cycle_id

    lanes = lane_repository.list_lanes(industry_instance_id=instance.instance_id)
    assert any(lane.industry_instance_id == instance.instance_id for lane in lanes)

    backlog = backlog_repository.list_items(industry_instance_id=instance.instance_id)
    assert any(item.industry_instance_id == instance.instance_id for item in backlog)

    cycles = cycle_repository.list_cycles(industry_instance_id=instance.instance_id)
    assert any(cycle.industry_instance_id == instance.instance_id for cycle in cycles)

    assignments = assignment_repository.list_assignments(industry_instance_id=instance.instance_id)
    assert any(assignment.industry_instance_id == instance.instance_id for assignment in assignments)


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
