# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingGrowthPlan,
    BuddyOnboardingReasonedTurn,
)
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService, _STOCKS_DIRECTION
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


class _CachedTurnReasoner:
    def __init__(self) -> None:
        self.turn_calls: list[dict[str, object]] = []
        self.plan_calls: list[dict[str, object]] = []

    def plan_turn(
        self,
        *,
        profile,
        transcript,
        question_count: int,
        tightened: bool,
    ) -> BuddyOnboardingReasonedTurn:
        self.turn_calls.append(
            {
                "profile_id": profile.profile_id,
                "transcript": list(transcript),
                "question_count": question_count,
                "tightened": tightened,
            },
        )
        return BuddyOnboardingReasonedTurn(
            finished=question_count >= 2,
            next_question="" if question_count >= 2 else "What trading horizon do you want first?",
            candidate_directions=[_STOCKS_DIRECTION],
            recommended_direction=_STOCKS_DIRECTION,
            final_goal="Build a disciplined stock trading path with verifiable review evidence.",
            why_it_matters="Turn vague money goals into a durable trading capability.",
            backlog_items=[
                BuddyOnboardingBacklogSeed(
                    lane_hint="growth-focus",
                    title="Define the trading boundary",
                    summary="Lock the market scope, time horizon, risk cap, and stop-loss rule.",
                    priority=3,
                    source_key="trading-boundary",
                ),
                BuddyOnboardingBacklogSeed(
                    lane_hint="proof-of-work",
                    title="Produce the first trade review",
                    summary="Create one reviewable trade note with entry, risk, and outcome evidence.",
                    priority=2,
                    source_key="trade-review",
                ),
            ],
        )

    def build_growth_plan(
        self,
        *,
        profile,
        transcript,
        selected_direction: str,
    ) -> BuddyOnboardingGrowthPlan:
        self.plan_calls.append(
            {
                "profile_id": profile.profile_id,
                "transcript": list(transcript),
                "selected_direction": selected_direction,
            },
        )
        return BuddyOnboardingGrowthPlan(
            primary_direction=selected_direction,
            final_goal="fallback should not run",
            why_it_matters="fallback should not run",
            backlog_items=[],
        )


def _build_service_with_planning(tmp_path, *, reasoner) -> tuple[BuddyOnboardingService, SQLiteStateStore]:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-latency.sqlite3")
    industry_repository = SqliteIndustryInstanceRepository(store)
    service = BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        industry_instance_repository=industry_repository,
        operating_lane_service=OperatingLaneService(repository=SqliteOperatingLaneRepository(store)),
        backlog_service=BacklogService(repository=SqliteBacklogItemRepository(store)),
        operating_cycle_service=OperatingCycleService(repository=SqliteOperatingCycleRepository(store)),
        assignment_service=AssignmentService(repository=SqliteAssignmentRepository(store)),
        domain_capability_growth_service=BuddyDomainCapabilityGrowthService(
            domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
            industry_instance_repository=industry_repository,
            operating_lane_service=OperatingLaneService(repository=SqliteOperatingLaneRepository(store)),
            backlog_service=BacklogService(repository=SqliteBacklogItemRepository(store)),
            operating_cycle_service=OperatingCycleService(repository=SqliteOperatingCycleRepository(store)),
            assignment_service=AssignmentService(repository=SqliteAssignmentRepository(store)),
        ),
        onboarding_reasoner=reasoner,
    )
    return service, store


def test_confirm_primary_direction_reuses_cached_reasoned_turn_without_second_model_call(tmp_path) -> None:
    reasoner = _CachedTurnReasoner()
    service, store = _build_service_with_planning(tmp_path, reasoner=reasoner)

    identity = service.submit_identity(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks", "trading"],
        strengths=["review"],
        constraints=["capital"],
        goal_intention="Build a real stock trading path.",
    )
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="I want a durable swing-trading path with strict risk control.",
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    backlog = SqliteBacklogItemRepository(store).list_items(
        industry_instance_id=result.domain_capability.industry_instance_id,
    )

    assert result.growth_target.final_goal == (
        "Build a disciplined stock trading path with verifiable review evidence."
    )
    assert [item.title for item in backlog] == [
        "Define the trading boundary",
        "Produce the first trade review",
    ]
    assert reasoner.plan_calls == []
