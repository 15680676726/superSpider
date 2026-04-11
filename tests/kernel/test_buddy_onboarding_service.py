# -*- coding: utf-8 -*-
from __future__ import annotations

from pydantic import BaseModel
import pytest

from copaw.industry.models import IndustryProfile
from copaw.kernel.buddy_domain_capability import derive_buddy_domain_key
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingReasonerUnavailableError,
)
from copaw.kernel.buddy_onboarding_service import (
    BuddyOnboardingService,
    _CREATOR_DIRECTION,
    _HEALTH_DIRECTION,
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
    SqliteScheduleRepository,
)
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)


def _contract_payload(
    *,
    service_intent: str = "Turn long-term goals into steady weekly execution.",
    collaboration_role: str = "orchestrator",
    autonomy_level: str = "proactive",
    confirm_boundaries: list[str] | None = None,
    report_style: str = "result-first",
    collaboration_notes: str = "Prefer concise updates with one concrete next step.",
) -> dict[str, object]:
    return {
        "service_intent": service_intent,
        "collaboration_role": collaboration_role,
        "autonomy_level": autonomy_level,
        "confirm_boundaries": confirm_boundaries or ["external spend", "irreversible actions"],
        "report_style": report_style,
        "collaboration_notes": collaboration_notes,
    }


class _ContractCompileResult(BaseModel):
    candidate_directions: list[str]
    recommended_direction: str
    final_goal: str
    why_it_matters: str
    backlog_items: list[BuddyOnboardingBacklogSeed]


class _DeterministicContractCompiler:
    def __init__(self) -> None:
        self.compile_calls: list[dict[str, object]] = []

    def compile_contract(
        self,
        *,
        profile,
        collaboration_contract,
    ) -> _ContractCompileResult:
        self.compile_calls.append(
            {
                "profile": profile,
                "collaboration_contract": collaboration_contract,
            }
        )
        direction = self._resolve_direction(
            profile_goal=profile.goal_intention,
            service_intent=str(getattr(collaboration_contract, "service_intent", "") or ""),
            notes=str(getattr(collaboration_contract, "collaboration_notes", "") or ""),
        )
        final_goal, why_it_matters, backlog_items = self._growth_plan(direction)
        return _ContractCompileResult(
            candidate_directions=[direction],
            recommended_direction=direction,
            final_goal=final_goal,
            why_it_matters=why_it_matters,
            backlog_items=backlog_items,
        )

    def _resolve_direction(
        self,
        *,
        profile_goal: str,
        service_intent: str,
        notes: str,
    ) -> str:
        source = " ".join([profile_goal, service_intent, notes]).lower()
        if any(token in source for token in ("stock", "stocks", "trade", "trading", "invest", "股票", "交易", "投资")):
            return _STOCKS_DIRECTION
        if any(token in source for token in ("health", "fitness", "exercise", "健康", "健身", "训练")):
            return _HEALTH_DIRECTION
        return _CREATOR_DIRECTION

    def _growth_plan(
        self,
        direction: str,
    ) -> tuple[str, str, list[BuddyOnboardingBacklogSeed]]:
        if direction == _STOCKS_DIRECTION:
            return (
                "Build a disciplined stock trading system with visible risk control evidence.",
                "This turns trading into a durable operating path instead of emotional reaction.",
                [
                    BuddyOnboardingBacklogSeed(
                        lane_hint="growth-focus",
                        title="Define trading boundaries",
                        summary="Lock the market scope, position sizing, and max-loss rule for the first cycle.",
                        priority=3,
                        source_key="trading-boundary",
                    ),
                    BuddyOnboardingBacklogSeed(
                        lane_hint="proof-of-work",
                        title="Produce the first review packet",
                        summary="Complete one evidence-backed review of a real or simulated trade sample.",
                        priority=2,
                        source_key="trading-review",
                    ),
                ],
            )
        if direction == _HEALTH_DIRECTION:
            return (
                "Build a repeatable health routine with visible weekly proof.",
                "This turns recovery into an operating rhythm instead of a vague intention.",
                [
                    BuddyOnboardingBacklogSeed(
                        lane_hint="growth-focus",
                        title="Lock the weekly routine",
                        summary="Define the minimum viable meal and workout rhythm for the coming week.",
                        priority=3,
                        source_key="health-routine",
                    ),
                    BuddyOnboardingBacklogSeed(
                        lane_hint="proof-of-work",
                        title="Record the first checkpoint",
                        summary="Capture the first weekly evidence checkpoint for training and recovery.",
                        priority=2,
                        source_key="health-checkpoint",
                    ),
                ],
            )
        return (
            "Build a durable writing and publishing path with visible proof-of-work.",
            "This turns expression into an accumulative path that can keep producing real artifacts.",
            [
                BuddyOnboardingBacklogSeed(
                    lane_hint="growth-focus",
                    title="Define the first publishing lane",
                    summary="Choose the topic, cadence, and minimum shippable unit for the first cycle.",
                    priority=3,
                    source_key="writing-direction",
                ),
                BuddyOnboardingBacklogSeed(
                    lane_hint="proof-of-work",
                    title="Ship the first publishable artifact",
                    summary="Finish the first chapter or draft and move it into a publish-ready state.",
                    priority=2,
                    source_key="writing-first-artifact",
                ),
            ],
        )


class _LaneLessContractCompiler(_DeterministicContractCompiler):
    def _growth_plan(
        self,
        direction: str,
    ) -> tuple[str, str, list[BuddyOnboardingBacklogSeed]]:
        return (
            f"Build a durable path around {direction}.",
            "The system must reject compile results without lane hints.",
            [
                BuddyOnboardingBacklogSeed(
                    lane_hint="",
                    title="Ship the first proof point",
                    summary="Turn the first validated action into evidence without a lane.",
                    priority=3,
                    source_key="missing-lane",
                ),
            ],
        )


class _MultiCandidateContractCompiler(_DeterministicContractCompiler):
    def compile_contract(
        self,
        *,
        profile,
        collaboration_contract,
    ) -> _ContractCompileResult:
        compiled = super().compile_contract(
            profile=profile,
            collaboration_contract=collaboration_contract,
        )
        return _ContractCompileResult(
            candidate_directions=[_STOCKS_DIRECTION, _CREATOR_DIRECTION],
            recommended_direction=_STOCKS_DIRECTION,
            final_goal=compiled.final_goal,
            why_it_matters=compiled.why_it_matters,
            backlog_items=compiled.backlog_items,
        )


def _build_service(
    tmp_path,
    *,
    compiler: _DeterministicContractCompiler | None = None,
) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding.sqlite3")
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        onboarding_reasoner=compiler or _DeterministicContractCompiler(),
    )


def _build_service_with_planning(
    tmp_path,
    *,
    compiler: _DeterministicContractCompiler | None = None,
) -> tuple[BuddyOnboardingService, SQLiteStateStore]:
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
        onboarding_reasoner=compiler or _DeterministicContractCompiler(),
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
        schedule_repository=SqliteScheduleRepository(store),
        domain_capability_growth_service=growth_service,
    )
    return service, store


def test_submit_identity_creates_contract_draft_session_without_interview_fields(
    tmp_path,
) -> None:
    service = _build_service(tmp_path)

    result = service.submit_identity(
        display_name="Alex",
        profession="Designer",
        current_stage="transition",
        interests=["writing", "systems"],
        strengths=["systems thinking"],
        constraints=["time"],
        goal_intention="I feel lost but want meaningful long-term growth.",
    )

    payload = result.model_dump(mode="json")
    session = service._onboarding_session_repository.get_session(result.session_id)  # pylint: disable=protected-access

    assert result.session_id
    assert result.profile.profile_id
    assert payload["status"] == "contract-draft"
    assert "question_count" not in payload
    assert "next_question" not in payload
    assert session is not None
    assert session.status == "contract-draft"


def test_submit_contract_compiles_direction_goal_and_backlog_without_next_question(
    tmp_path,
) -> None:
    compiler = _DeterministicContractCompiler()
    service = _build_service(tmp_path, compiler=compiler)
    identity = service.submit_identity(
        display_name="Kai",
        profession="Analyst",
        current_stage="restart",
        interests=["stocks", "trading"],
        strengths=["discipline"],
        constraints=["money"],
        goal_intention="I want to build a real stock trading path and achieve financial freedom.",
    )
    contract = _contract_payload(
        service_intent="Turn trading ambition into a disciplined weekly execution path.",
        collaboration_notes="Escalate when a move would exceed my risk boundary.",
    )

    result = service.submit_contract(
        session_id=identity.session_id,
        **contract,
    )

    payload = result.model_dump(mode="json")
    stored_session = service._onboarding_session_repository.get_session(identity.session_id)  # pylint: disable=protected-access

    assert result.recommended_direction == _STOCKS_DIRECTION
    assert result.candidate_directions == [_STOCKS_DIRECTION]
    assert result.final_goal
    assert result.why_it_matters
    assert result.backlog_items
    assert "next_question" not in payload
    assert "finished" not in payload
    assert compiler.compile_calls[-1]["profile"].profile_id == identity.profile.profile_id
    assert (
        compiler.compile_calls[-1]["collaboration_contract"].service_intent
        == contract["service_intent"]
    )
    assert stored_session is not None
    assert stored_session.service_intent == contract["service_intent"]
    assert stored_session.collaboration_role == contract["collaboration_role"]
    assert stored_session.autonomy_level == contract["autonomy_level"]
    assert stored_session.report_style == contract["report_style"]
    assert stored_session.confirm_boundaries == contract["confirm_boundaries"]
    assert stored_session.draft_final_goal == result.final_goal
    assert stored_session.draft_why_it_matters == result.why_it_matters
    assert stored_session.draft_backlog_items


def test_submit_contract_rejects_compile_without_lane_hints(tmp_path) -> None:
    service = _build_service(tmp_path, compiler=_LaneLessContractCompiler())
    identity = service.submit_identity(
        display_name="Mina",
        profession="Operator",
        current_stage="restart",
        interests=["systems"],
        strengths=["consistency"],
        constraints=["money"],
        goal_intention="I want one real long-term direction.",
    )

    with pytest.raises(BuddyOnboardingReasonerUnavailableError):
        service.submit_contract(
            session_id=identity.session_id,
            **_contract_payload(),
        )


def test_submit_identity_creates_distinct_profile_for_new_onboarding(tmp_path) -> None:
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

    assert second.profile.profile_id != first.profile.profile_id
    assert second.profile.display_name == "Mina Updated"
    assert second.profile.profession == "Builder"
    assert service._profile_repository.count_profiles() == 2  # pylint: disable=protected-access


def test_start_identity_operation_creates_distinct_profile_without_overwriting_existing(
    tmp_path,
) -> None:
    service = _build_service(tmp_path)

    first = service.submit_identity(
        display_name="Alpha",
        profession="Operator",
        current_stage="exploring",
        interests=["content"],
        strengths=["consistency"],
        constraints=["money"],
        goal_intention="I want a bigger life direction.",
    )

    handle = service.start_identity_operation(
        display_name="Beta",
        profession="Builder",
        current_stage="restarting",
        interests=["systems"],
        strengths=["clarity"],
        constraints=["time"],
        goal_intention="I want one real long-term direction.",
    )

    stored_first = service._profile_repository.get_profile(first.profile.profile_id)  # pylint: disable=protected-access
    running_session = service._onboarding_session_repository.get_session(handle.session_id)  # pylint: disable=protected-access

    assert handle.profile_id != first.profile.profile_id
    assert service._profile_repository.count_profiles() == 2  # pylint: disable=protected-access
    assert stored_first is not None
    assert stored_first.display_name == "Alpha"
    assert running_session is not None
    assert running_session.profile_id == handle.profile_id
    assert running_session.operation_status == "running"


def test_confirm_primary_direction_persists_contract_and_execution_identity_payload(
    tmp_path,
) -> None:
    compiler = _DeterministicContractCompiler()
    service, store = _build_service_with_planning(tmp_path, compiler=compiler)
    identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing", "content"],
        strengths=["storytelling"],
        constraints=["time", "money"],
        goal_intention="I want a real creator direction that can change my life.",
    )
    contract = _contract_payload(
        service_intent="Turn creative ambition into a weekly publishing rhythm.",
        collaboration_role="orchestrator",
        autonomy_level="guarded-proactive",
        confirm_boundaries=["external spend", "publishing under my real name"],
        report_style="decision-first",
        collaboration_notes="Keep reports short and escalate blockers with one recommendation.",
    )
    compiled = service.submit_contract(
        session_id=identity.session_id,
        **contract,
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=compiled.recommended_direction,
        capability_action="start-new",
    )

    instance = SqliteIndustryInstanceRepository(store).get_instance(
        result.domain_capability.industry_instance_id,
    )
    growth_payload = result.growth_target.model_dump(mode="json")

    assert result.growth_target.primary_direction == compiled.recommended_direction
    assert result.growth_target.final_goal == compiled.final_goal
    assert result.growth_target.why_it_matters == compiled.why_it_matters
    assert "service_intent" not in growth_payload
    assert result.relationship.service_intent == contract["service_intent"]
    assert result.relationship.collaboration_role == contract["collaboration_role"]
    assert result.relationship.autonomy_level == contract["autonomy_level"]
    assert result.relationship.confirm_boundaries == contract["confirm_boundaries"]
    assert result.relationship.report_style == contract["report_style"]
    assert result.relationship.collaboration_notes == contract["collaboration_notes"]
    assert instance is not None
    assert instance.execution_core_identity_payload["operator_service_intent"] == contract["service_intent"]
    assert instance.execution_core_identity_payload["collaboration_role"] == contract["collaboration_role"]
    assert instance.execution_core_identity_payload["autonomy_level"] == contract["autonomy_level"]
    assert instance.execution_core_identity_payload["report_style"] == contract["report_style"]
    assert instance.execution_core_identity_payload["confirm_boundaries"] == contract["confirm_boundaries"]
    assert instance.execution_core_identity_payload["operating_mode"]
    assert instance.execution_core_identity_payload["delegation_policy"]
    assert instance.execution_core_identity_payload["direct_execution_policy"]
    assert len(compiler.compile_calls) == 1


def test_confirm_primary_direction_requires_completed_contract_compile(tmp_path) -> None:
    service, _store = _build_service_with_planning(tmp_path)
    identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing", "content"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="I want a real creator direction that can change my life.",
    )

    with pytest.raises(ValueError, match="协作合同编译"):
        service.confirm_primary_direction(
            session_id=identity.session_id,
            selected_direction=_CREATOR_DIRECTION,
            capability_action="start-new",
        )

    assert service._growth_target_repository.get_active_target(identity.profile.profile_id) is None  # pylint: disable=protected-access
    assert service._relationship_repository.get_relationship(identity.profile.profile_id) is None  # pylint: disable=protected-access


def test_confirm_primary_direction_rejects_selected_direction_without_matching_compile(
    tmp_path,
) -> None:
    compiler = _MultiCandidateContractCompiler()
    service, _store = _build_service_with_planning(tmp_path, compiler=compiler)
    identity = service.submit_identity(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks", "writing"],
        strengths=["discipline"],
        constraints=["money"],
        goal_intention="I want a real stock trading path with visible proof.",
    )
    compiled = service.submit_contract(
        session_id=identity.session_id,
        **_contract_payload(
            service_intent="Turn trading ambition into a disciplined weekly execution path.",
        ),
    )

    assert compiled.candidate_directions == [_STOCKS_DIRECTION, _CREATOR_DIRECTION]

    with pytest.raises(ValueError, match="重新编译协作合同"):
        service.confirm_primary_direction(
            session_id=identity.session_id,
            selected_direction=_CREATOR_DIRECTION,
            capability_action="start-new",
        )

    assert service._growth_target_repository.get_active_target(identity.profile.profile_id) is None  # pylint: disable=protected-access
    assert len(compiler.compile_calls) == 1


def test_submit_contract_clears_stale_failed_async_operation_state(tmp_path) -> None:
    service = _build_service(tmp_path)
    identity = service.submit_identity(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks"],
        strengths=["review"],
        constraints=["capital"],
        goal_intention="Build a real stock trading path.",
    )
    service.mark_operation_failed(
        session_id=identity.session_id,
        operation_id="op-contract-failed",
        operation_kind="contract",
        error_message="old compiler failure",
    )

    service.submit_contract(
        session_id=identity.session_id,
        **_contract_payload(
            service_intent="Turn trading ambition into a disciplined weekly execution path.",
        ),
    )

    stored = service._onboarding_session_repository.get_session(identity.session_id)  # pylint: disable=protected-access

    assert stored is not None
    assert stored.status == "contract-ready"
    assert stored.operation_id == ""
    assert stored.operation_kind == ""
    assert stored.operation_status == "idle"
    assert stored.operation_error == ""


def test_confirm_primary_direction_clears_stale_failed_async_operation_state(tmp_path) -> None:
    service, _store = _build_service_with_planning(tmp_path)
    identity = service.submit_identity(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks"],
        strengths=["review"],
        constraints=["capital"],
        goal_intention="Build a real stock trading path.",
    )
    compiled = service.submit_contract(
        session_id=identity.session_id,
        **_contract_payload(
            service_intent="Turn trading ambition into a disciplined weekly execution path.",
        ),
    )
    service.mark_operation_failed(
        session_id=identity.session_id,
        operation_id="op-confirm-failed",
        operation_kind="confirm",
        error_message="old confirmation failure",
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=compiled.recommended_direction,
        capability_action="start-new",
    )

    assert result.session.status == "confirmed"
    assert result.session.operation_id == ""
    assert result.session.operation_kind == ""
    assert result.session.operation_status == "idle"
    assert result.session.operation_error == ""


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
    compiled = service.submit_contract(
        session_id=identity.session_id,
        **_contract_payload(),
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=compiled.recommended_direction,
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
    backlog = backlog_repository.list_items(industry_instance_id=instance.instance_id)
    cycles = cycle_repository.list_cycles(industry_instance_id=instance.instance_id)
    assignments = assignment_repository.list_assignments(industry_instance_id=instance.instance_id)

    assert any(lane.industry_instance_id == instance.instance_id for lane in lanes)
    assert any(item.industry_instance_id == instance.instance_id for item in backlog)
    assert any(cycle.industry_instance_id == instance.instance_id for cycle in cycles)
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
    compiled = service.submit_contract(
        session_id=identity.session_id,
        **_contract_payload(),
    )

    result = service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=compiled.recommended_direction,
        capability_action="start-new",
    )

    instance = SqliteIndustryInstanceRepository(store).get_instance(
        result.domain_capability.industry_instance_id,
    )

    assert instance is not None
    profile = IndustryProfile.model_validate(instance.profile_payload)
    assert profile.industry == result.growth_target.primary_direction
    assert result.growth_target.final_goal in profile.goals
    assert set(profile.constraints) >= {"time", "money"}
    assert "profession" not in instance.profile_payload
    assert "current_stage" not in instance.profile_payload


def test_confirm_primary_direction_start_new_and_restore_archived_domain_carrier(
    tmp_path,
) -> None:
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
    creator_compiled = service.submit_contract(
        session_id=creator_identity.session_id,
        **_contract_payload(),
    )
    creator = service.confirm_primary_direction(
        session_id=creator_identity.session_id,
        selected_direction=creator_compiled.recommended_direction,
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
    health_compiled = service.submit_contract(
        session_id=health_identity.session_id,
        **_contract_payload(
            service_intent="Turn recovery into a steady weekly execution rhythm.",
            collaboration_notes="Escalate if a step would exceed the current recovery boundary.",
        ),
    )
    health = service.confirm_primary_direction(
        session_id=health_identity.session_id,
        selected_direction=health_compiled.recommended_direction,
        capability_action="start-new",
    )

    assert health.domain_capability.industry_instance_id != creator.domain_capability.industry_instance_id
    assert health.domain_capability.control_thread_id != creator.domain_capability.control_thread_id
    assert SqliteIndustryInstanceRepository(store).get_instance(
        health.domain_capability.industry_instance_id,
    ) is not None

    creator_return_identity = service.submit_identity(
        display_name="Nora",
        profession="Writer",
        current_stage="restart",
        interests=["writing"],
        strengths=["storytelling"],
        constraints=["time"],
        goal_intention="Return to creator work.",
    )
    creator_return_compiled = service.submit_contract(
        session_id=creator_return_identity.session_id,
        **_contract_payload(),
    )
    preview = service.preview_primary_direction_transition(
        session_id=creator_return_identity.session_id,
        selected_direction=creator_return_compiled.recommended_direction,
    )
    restored = service.confirm_primary_direction(
        session_id=creator_return_identity.session_id,
        selected_direction=creator_return_compiled.recommended_direction,
        capability_action="restore-archived",
        target_domain_id=preview.archived_matches[0]["domain_id"],
    )
    active = service._domain_capability_repository.get_active_domain_capability(  # pylint: disable=protected-access
        creator_identity.profile.profile_id,
    )

    assert preview.suggestion_kind == "switch-to-archived-domain"
    assert preview.recommended_action == "restore-archived"
    assert restored.domain_capability.domain_key == derive_buddy_domain_key(
        creator.growth_target.primary_direction,
    )
    assert restored.domain_capability.industry_instance_id == creator_instance_id
    assert restored.domain_capability.control_thread_id == creator_thread_id
    assert active is not None
    assert active.domain_key == derive_buddy_domain_key(
        creator.growth_target.primary_direction,
    )


def test_name_buddy_updates_relationship_after_contract_confirmation(tmp_path) -> None:
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
    compiled = service.submit_contract(
        session_id=identity.session_id,
        **_contract_payload(),
    )
    service.confirm_primary_direction(
        session_id=identity.session_id,
        selected_direction=compiled.recommended_direction,
        capability_action="start-new",
    )

    relationship = service.name_buddy(
        session_id=identity.session_id,
        buddy_name="Mochi",
    )

    assert relationship.buddy_name == "Mochi"
