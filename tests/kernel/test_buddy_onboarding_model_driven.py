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


class _FakeWritingBuddyReasoner:
    def plan_turn(
        self,
        *,
        profile,
        transcript,
        question_count: int,
        tightened: bool,
    ) -> BuddyOnboardingReasonedTurn:
        _ = (profile, transcript, tightened)
        finished = question_count >= 2
        return BuddyOnboardingReasonedTurn(
            finished=finished,
            next_question="" if finished else "你更想先写长篇连载，还是先做短篇练习？",
            candidate_directions=["建立稳定、可持续的写作与内容发布成长路径"],
            recommended_direction="建立稳定、可持续的写作与内容发布成长路径",
        )

    def build_growth_plan(
        self,
        *,
        profile,
        transcript,
        selected_direction: str,
    ) -> BuddyOnboardingGrowthPlan:
        _ = (profile, transcript)
        return BuddyOnboardingGrowthPlan(
            primary_direction=selected_direction,
            final_goal="先建立稳定的番茄写作与发布节奏，并产出第一轮作品证据。",
            why_it_matters="把写作从口头计划收成能持续发布、能形成作品资产的长期主线。",
            backlog_items=[
                BuddyOnboardingBacklogSeed(
                    lane_hint="growth-focus",
                    title="明确连载方向与更新节奏",
                    summary="先确定题材、更新频率和最小可持续字数目标。",
                    priority=3,
                    source_key="writing-direction",
                ),
                BuddyOnboardingBacklogSeed(
                    lane_hint="proof-of-work",
                    title="完成第一章并进入平台草稿",
                    summary="完成第一章初稿，准备进入番茄平台草稿箱。",
                    priority=2,
                    source_key="writing-first-chapter",
                ),
            ],
        )


class _FakeCommerceBuddyReasoner:
    def plan_turn(
        self,
        *,
        profile,
        transcript,
        question_count: int,
        tightened: bool,
    ) -> BuddyOnboardingReasonedTurn:
        _ = (profile, transcript, tightened)
        finished = question_count >= 2
        return BuddyOnboardingReasonedTurn(
            finished=finished,
            next_question="" if finished else "你是先做选品调研，还是先做平台上架和首批内容发布？",
            candidate_directions=["建立稳定的跨境电商选品与平台发布增长路径"],
            recommended_direction="建立稳定的跨境电商选品与平台发布增长路径",
        )

    def build_growth_plan(
        self,
        *,
        profile,
        transcript,
        selected_direction: str,
    ) -> BuddyOnboardingGrowthPlan:
        _ = (profile, transcript)
        return BuddyOnboardingGrowthPlan(
            primary_direction=selected_direction,
            final_goal="先建立可持续的跨境电商选品、上架和首批成交验证链路。",
            why_it_matters="把跨境电商从模糊想法收成能持续验证、能逐步放大的真实业务主线。",
            backlog_items=[
                BuddyOnboardingBacklogSeed(
                    lane_hint="market-research",
                    title="完成首轮选品调研",
                    summary="先明确目标平台、目标客群和首批可验证商品池。",
                    priority=3,
                    source_key="market-research",
                ),
                BuddyOnboardingBacklogSeed(
                    lane_hint="platform-publishing",
                    title="完成首批平台上架草稿",
                    summary="把首批商品图文、卖点和上架草稿准备到可直接发布的状态。",
                    priority=2,
                    source_key="platform-publishing",
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
        profession="探索者",
        current_stage="重启",
        interests=["复盘", "独立成长"],
        strengths=["复盘"],
        constraints=["资金有限"],
        goal_intention="我想找到一条真正值得长期投入的人生主方向。",
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


def test_confirm_primary_direction_shapes_domain_specific_specialist_capabilities(tmp_path) -> None:
    service, store = _build_service_with_planning(
        tmp_path,
        reasoner=_FakeWritingBuddyReasoner(),
    )
    identity = service.submit_identity(
        display_name="小满",
        profession="写作者",
        current_stage="重启",
        interests=["写作", "番茄"],
        strengths=["连续创作"],
        constraints=["需要先形成稳定节奏"],
        goal_intention="我想长期写小说，并真的在番茄持续发布。",
    )
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="我想先把长篇连载写起来，再逐步稳定更新。",
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    industry_repository = SqliteIndustryInstanceRepository(store)
    stored_instance = industry_repository.get_instance(result.domain_capability.industry_instance_id)
    assert stored_instance is not None
    agents = list((stored_instance.team_payload or {}).get("agents") or [])
    by_role = {
        str(item.get("role_id") or "").strip(): item
        for item in agents
        if str(item.get("role_id") or "").strip()
    }

    proof = by_role["proof-of-work"]
    growth = by_role["growth-focus"]

    assert "tool:browser_use" in list(proof.get("allowed_capabilities") or [])
    assert "content" in list(proof.get("preferred_capability_families") or [])
    assert "browser" in list(proof.get("preferred_capability_families") or [])
    assert "workflow" in list(proof.get("preferred_capability_families") or [])
    assert "content" in list(growth.get("preferred_capability_families") or [])


def test_confirm_primary_direction_materializes_model_lane_hints_into_dynamic_specialist_roles(
    tmp_path,
) -> None:
    service, store = _build_service_with_planning(
        tmp_path,
        reasoner=_FakeCommerceBuddyReasoner(),
    )
    identity = service.submit_identity(
        display_name="Lina",
        profession="Operator",
        current_stage="restart",
        interests=["跨境电商", "选品", "平台上架"],
        strengths=["执行", "整理"],
        constraints=["需要先验证第一批商品"],
        goal_intention="我想把跨境电商做成能持续经营的业务。",
    )
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="我想先把选品和平台上架这两条线跑起来。",
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    industry_repository = SqliteIndustryInstanceRepository(store)
    lane_repository = SqliteOperatingLaneRepository(store)
    assignment_repository = SqliteAssignmentRepository(store)
    stored_instance = industry_repository.get_instance(result.domain_capability.industry_instance_id)
    assert stored_instance is not None
    agents = list((stored_instance.team_payload or {}).get("agents") or [])
    by_role = {
        str(item.get("role_id") or "").strip(): item
        for item in agents
        if str(item.get("role_id") or "").strip()
    }

    assert "market-research" in by_role
    assert "platform-publishing" in by_role
    assert "growth-focus" not in by_role
    assert "proof-of-work" not in by_role

    lanes = lane_repository.list_lanes(industry_instance_id=result.domain_capability.industry_instance_id)
    assert {lane.owner_role_id for lane in lanes} == {"market-research", "platform-publishing"}

    assignments = assignment_repository.list_assignments(
        industry_instance_id=result.domain_capability.industry_instance_id,
        limit=None,
    )
    assert {assignment.owner_role_id for assignment in assignments} == {
        "market-research",
        "platform-publishing",
    }


def test_growth_refresh_restores_dynamic_specialist_roles_from_agent_ids_when_team_payload_is_missing(
    tmp_path,
) -> None:
    service, store = _build_service_with_planning(
        tmp_path,
        reasoner=_FakeCommerceBuddyReasoner(),
    )
    identity = service.submit_identity(
        display_name="Lina",
        profession="Operator",
        current_stage="restart",
        interests=["跨境电商", "选品", "平台上架"],
        strengths=["执行", "整理"],
        constraints=["需要先验证第一批商品"],
        goal_intention="我想把跨境电商做成能持续经营的业务。",
    )
    clarification = service.answer_clarification_turn(
        session_id=identity.session_id,
        answer="我想先把选品和平台上架这两条线跑起来。",
    )
    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=clarification.recommended_direction,
        capability_action="start-new",
    )

    instance_repository = SqliteIndustryInstanceRepository(store)
    instance_id = result.domain_capability.industry_instance_id
    stored_instance = instance_repository.get_instance(instance_id)
    assert stored_instance is not None
    instance_repository.upsert_instance(
        stored_instance.model_copy(
            update={
                "team_payload": {
                    "team_id": instance_id,
                    "label": stored_instance.label,
                    "summary": stored_instance.summary,
                    "agents": [],
                },
            },
        ),
    )

    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        industry_instance_repository=instance_repository,
        operating_lane_service=OperatingLaneService(
            repository=SqliteOperatingLaneRepository(store),
        ),
        assignment_service=AssignmentService(
            repository=SqliteAssignmentRepository(store),
        ),
    )
    growth_service.refresh_active_domain_capability(
        profile_id=result.domain_capability.profile_id,
    )

    repaired = instance_repository.get_instance(instance_id)
    assert repaired is not None
    agents = list((repaired.team_payload or {}).get("agents") or [])
    by_role = {
        str(item.get("role_id") or "").strip(): item
        for item in agents
        if str(item.get("role_id") or "").strip()
    }
    assert "market-research" in by_role
    assert "platform-publishing" in by_role
    assert "growth-focus" not in by_role
    assert "proof-of-work" not in by_role
