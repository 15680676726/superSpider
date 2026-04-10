# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyCollaborationContract,
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingContractCompileResult,
)
from copaw.kernel.buddy_onboarding_service import (
    BuddyOnboardingService,
    _CREATOR_DIRECTION,
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


class _RecordingContractCompiler:
    def __init__(self) -> None:
        self.compile_calls: list[dict[str, object]] = []

    def compile_contract(
        self,
        *,
        profile,
        collaboration_contract,
    ) -> BuddyOnboardingContractCompileResult:
        self.compile_calls.append(
            {
                "profile": profile,
                "collaboration_contract": collaboration_contract,
            }
        )
        return BuddyOnboardingContractCompileResult(
            candidate_directions=[_STOCKS_DIRECTION],
            recommended_direction=_STOCKS_DIRECTION,
            final_goal="Build a disciplined stock trading system with visible weekly evidence.",
            why_it_matters="Turn trading into a durable operating path instead of emotional reactions.",
            backlog_items=[
                BuddyOnboardingBacklogSeed(
                    lane_hint="growth-focus",
                    title="Define the first-cycle risk boundary",
                    summary="Lock the market scope, risk cap, and stop-loss rule for the first cycle.",
                    priority=3,
                    source_key="trading-boundary",
                )
            ],
        )


class _MultiCandidateContractCompiler(_RecordingContractCompiler):
    def compile_contract(
        self,
        *,
        profile,
        collaboration_contract,
    ) -> BuddyOnboardingContractCompileResult:
        compiled = super().compile_contract(
            profile=profile,
            collaboration_contract=collaboration_contract,
        )
        return compiled.model_copy(
            update={
                "candidate_directions": [_STOCKS_DIRECTION, _CREATOR_DIRECTION],
                "recommended_direction": _STOCKS_DIRECTION,
            }
        )


def _build_service(
    tmp_path,
    *,
    compiler=None,
) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-model-driven.sqlite3")
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        onboarding_reasoner=compiler or _RecordingContractCompiler(),
    )


def _build_service_with_planning(
    tmp_path,
    *,
    compiler=None,
) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-model-driven-planning.sqlite3")
    industry_repository = SqliteIndustryInstanceRepository(store)
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        industry_instance_repository=industry_repository,
        operating_lane_service=OperatingLaneService(repository=SqliteOperatingLaneRepository(store)),
        backlog_service=BacklogService(repository=SqliteBacklogItemRepository(store)),
        operating_cycle_service=OperatingCycleService(
            repository=SqliteOperatingCycleRepository(store)
        ),
        assignment_service=AssignmentService(repository=SqliteAssignmentRepository(store)),
        domain_capability_growth_service=BuddyDomainCapabilityGrowthService(
            domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
            industry_instance_repository=industry_repository,
            operating_lane_service=OperatingLaneService(
                repository=SqliteOperatingLaneRepository(store)
            ),
            backlog_service=BacklogService(repository=SqliteBacklogItemRepository(store)),
            operating_cycle_service=OperatingCycleService(
                repository=SqliteOperatingCycleRepository(store)
            ),
            assignment_service=AssignmentService(
                repository=SqliteAssignmentRepository(store)
            ),
        ),
        onboarding_reasoner=compiler or _RecordingContractCompiler(),
    )


def _contract_payload() -> dict[str, object]:
    return {
        "service_intent": "Turn trading ambition into a disciplined weekly execution path.",
        "collaboration_role": "orchestrator",
        "autonomy_level": "guarded-proactive",
        "confirm_boundaries": ["external spend", "irreversible actions"],
        "report_style": "decision-first",
        "collaboration_notes": "Escalate when an action would exceed the agreed risk boundary.",
    }


def test_submit_contract_passes_profile_and_collaboration_contract_to_compiler(tmp_path) -> None:
    compiler = _RecordingContractCompiler()
    service = _build_service(tmp_path, compiler=compiler)
    identity = service.submit_identity(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks"],
        strengths=["review"],
        constraints=["capital"],
        goal_intention="Build a real stock trading path.",
    )

    result = service.submit_contract(
        session_id=identity.session_id,
        **_contract_payload(),
    )

    compile_call = compiler.compile_calls[-1]

    assert result.status == "contract-ready"
    assert compile_call["profile"].profile_id == identity.profile.profile_id
    assert isinstance(compile_call["collaboration_contract"], BuddyCollaborationContract)
    assert (
        compile_call["collaboration_contract"].service_intent
        == _contract_payload()["service_intent"]
    )


def test_model_driven_confirm_requires_completed_contract_compile(tmp_path) -> None:
    service = _build_service_with_planning(tmp_path)
    identity = service.submit_identity(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks"],
        strengths=["review"],
        constraints=["capital"],
        goal_intention="Build a real stock trading path.",
    )

    with pytest.raises(ValueError, match="协作合同编译"):
        service.confirm_primary_direction(
            session_id=identity.session_id,
            selected_direction=_STOCKS_DIRECTION,
            capability_action="start-new",
        )


def test_model_driven_confirm_rejects_alternate_candidate_without_direction_specific_compile(
    tmp_path,
) -> None:
    compiler = _MultiCandidateContractCompiler()
    service = _build_service_with_planning(tmp_path, compiler=compiler)
    identity = service.submit_identity(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks", "writing"],
        strengths=["review"],
        constraints=["capital"],
        goal_intention="Build a real stock trading path.",
    )
    compiled = service.submit_contract(
        session_id=identity.session_id,
        **_contract_payload(),
    )

    assert compiled.candidate_directions == [_STOCKS_DIRECTION, _CREATOR_DIRECTION]

    with pytest.raises(ValueError, match="重新编译协作合同"):
        service.confirm_primary_direction(
            session_id=identity.session_id,
            selected_direction=_CREATOR_DIRECTION,
            capability_action="start-new",
        )
