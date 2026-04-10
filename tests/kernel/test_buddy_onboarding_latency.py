# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyCollaborationContract,
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingContractCompileResult,
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


class _CachedContractReasoner:
    def __init__(self) -> None:
        self.compile_calls: list[dict[str, object]] = []

    def compile_contract(
        self,
        *,
        profile,
        collaboration_contract: BuddyCollaborationContract,
    ) -> BuddyOnboardingContractCompileResult:
        self.compile_calls.append(
            {
                "profile_id": profile.profile_id,
                "contract": collaboration_contract.model_dump(mode="json"),
            },
        )
        return BuddyOnboardingContractCompileResult(
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


def test_confirm_primary_direction_reuses_cached_contract_compile_without_second_model_call(tmp_path) -> None:
    reasoner = _CachedContractReasoner()
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
    contract = service.submit_contract(
        session_id=identity.session_id,
        service_intent="Help me build a durable swing-trading system with strict risk control.",
        collaboration_role="orchestrator",
        autonomy_level="guarded-proactive",
        confirm_boundaries=["external spend"],
        report_style="result-first",
        collaboration_notes="Keep the loop disciplined and evidence-based.",
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=contract.recommended_direction,
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
    assert len(reasoner.compile_calls) == 1
