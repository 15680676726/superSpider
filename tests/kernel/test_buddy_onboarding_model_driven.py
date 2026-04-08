# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingGrowthPlan,
    BuddyOnboardingReasonedTurn,
)
from copaw.kernel.buddy_onboarding_service import (
    BuddyOnboardingService,
    _STOCKS_DIRECTION,
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
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)


class _FakeBuddyReasoner:
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
        finished = question_count >= 2
        return BuddyOnboardingReasonedTurn(
            finished=finished,
            next_question="" if finished else "你想先做哪一类股票交易，短线、波段还是中长线？",
            candidate_directions=[_STOCKS_DIRECTION],
            recommended_direction=_STOCKS_DIRECTION,
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
            final_goal="先建立一套可验证的股票交易系统，并产出第一轮复盘证据。",
            why_it_matters="把炒股从模糊赚钱冲动，收成有纪律、可复盘、可持续的长期主线。",
            backlog_items=[
                BuddyOnboardingBacklogSeed(
                    lane_hint="growth-focus",
                    title="确定交易边界",
                    summary="先明确市场范围、周期、风险边界和止损纪律。",
                    priority=3,
                    source_key="trading-boundary",
                ),
                BuddyOnboardingBacklogSeed(
                    lane_hint="proof-of-work",
                    title="产出第一份交易复盘",
                    summary="用真实样本做第一份复盘，形成能被检验的证据。",
                    priority=2,
                    source_key="trading-review",
                ),
            ],
        )


def _build_service(tmp_path, *, reasoner=None) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-model.sqlite3")
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        onboarding_reasoner=reasoner,
    )


def _build_service_with_planning(tmp_path, *, reasoner=None) -> tuple[BuddyOnboardingService, SQLiteStateStore]:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-model-planning.sqlite3")
    industry_repository = SqliteIndustryInstanceRepository(store)
    service = BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
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
        domain_capability_growth_service=BuddyDomainCapabilityGrowthService(
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
        ),
        onboarding_reasoner=reasoner,
    )
    return service, store


def test_submit_identity_prefers_model_generated_next_question(tmp_path) -> None:
    service = _build_service(tmp_path, reasoner=_FakeBuddyReasoner())

    result = service.submit_identity(
        display_name="阿泽",
        profession="交易员",
        current_stage="重启",
        interests=["股票", "交易"],
        strengths=["复盘"],
        constraints=["资金有限"],
        goal_intention="我想靠炒股建立长期稳定的收入能力。",
    )

    assert result.next_question == "你想先做哪一类股票交易，短线、波段还是中长线？"


def test_answer_clarification_turn_prefers_model_reasoned_direction(tmp_path) -> None:
    reasoner = _FakeBuddyReasoner()
    service = _build_service(tmp_path, reasoner=reasoner)
    identity = service.submit_identity(
        display_name="阿泽",
        profession="交易员",
        current_stage="重启",
        interests=["股票", "交易"],
        strengths=["复盘"],
        constraints=["资金有限"],
        goal_intention="我想靠炒股建立长期稳定的收入能力。",
    )

    result = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="我想先做波段，重点先把回撤和仓位控制住。",
    )

    assert result.finished is True
    assert result.next_question == ""
    assert result.recommended_direction == _STOCKS_DIRECTION
    assert reasoner.turn_calls[-1]["question_count"] == 2


def test_confirm_primary_direction_uses_model_generated_growth_plan(tmp_path) -> None:
    reasoner = _FakeBuddyReasoner()
    service, store = _build_service_with_planning(tmp_path, reasoner=reasoner)
    identity = service.submit_identity(
        display_name="阿泽",
        profession="交易员",
        current_stage="重启",
        interests=["股票", "交易"],
        strengths=["复盘"],
        constraints=["资金有限"],
        goal_intention="我想靠炒股建立长期稳定的收入能力。",
    )
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="我想先做波段，重点先把回撤和仓位控制住。",
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    backlog_repository = SqliteBacklogItemRepository(store)
    backlog = backlog_repository.list_items(industry_instance_id=result.domain_capability.industry_instance_id)

    assert result.growth_target.final_goal == "先建立一套可验证的股票交易系统，并产出第一轮复盘证据。"
    assert result.growth_target.why_it_matters == (
        "把炒股从模糊赚钱冲动，收成有纪律、可复盘、可持续的长期主线。"
    )
    assert [item.title for item in backlog] == ["确定交易边界", "产出第一份交易复盘"]
    assert reasoner.plan_calls[-1]["selected_direction"] == _STOCKS_DIRECTION
