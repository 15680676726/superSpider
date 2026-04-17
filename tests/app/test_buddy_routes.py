# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

import copaw.app.routers.buddy_routes as buddy_routes_module
from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import BuddyOnboardingBacklogSeed
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
    def compile_contract(
        self,
        *,
        profile,
        collaboration_contract,
    ) -> _ContractCompileResult:
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


class _MultiCandidateDirectionalCompiler(_DeterministicContractCompiler):
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

    def compile_contract_for_direction(
        self,
        *,
        profile,
        collaboration_contract,
        preferred_direction: str,
    ) -> _ContractCompileResult:
        final_goal, why_it_matters, backlog_items = self._growth_plan(preferred_direction)
        return _ContractCompileResult(
            candidate_directions=[_STOCKS_DIRECTION, _CREATOR_DIRECTION],
            recommended_direction=preferred_direction,
            final_goal=final_goal,
            why_it_matters=why_it_matters,
            backlog_items=backlog_items,
        )


class _FakeCronManager:
    def __init__(self) -> None:
        self.jobs: list[object] = []

    async def create_or_replace_job(self, spec) -> None:
        self.jobs.append(spec)


def _build_client(tmp_path) -> tuple[TestClient, SQLiteStateStore]:
    store = SQLiteStateStore(tmp_path / "buddy-routes.sqlite3")
    industry_repository = SqliteIndustryInstanceRepository(store)
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    onboarding_session_repository = SqliteBuddyOnboardingSessionRepository(store)
    lane_service = OperatingLaneService(repository=SqliteOperatingLaneRepository(store))
    backlog_service = BacklogService(repository=SqliteBacklogItemRepository(store))
    cycle_service = OperatingCycleService(repository=SqliteOperatingCycleRepository(store))
    assignment_service = AssignmentService(repository=SqliteAssignmentRepository(store))
    service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=onboarding_session_repository,
        onboarding_reasoner=_DeterministicContractCompiler(),
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
        schedule_repository=SqliteScheduleRepository(store),
        domain_capability_growth_service=BuddyDomainCapabilityGrowthService(
            domain_capability_repository=domain_capability_repository,
            industry_instance_repository=industry_repository,
            operating_lane_service=lane_service,
            backlog_service=backlog_service,
            operating_cycle_service=cycle_service,
            assignment_service=assignment_service,
        ),
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        onboarding_session_repository=onboarding_session_repository,
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=industry_repository,
    )
    app = FastAPI()
    app.state.buddy_onboarding_service = service
    app.state.buddy_projection_service = projection_service
    app.state.cron_manager = _FakeCronManager()
    app.include_router(buddy_router)
    return TestClient(app), store


def test_identity_route_returns_contract_draft_session(tmp_path) -> None:
    client, _store = _build_client(tmp_path)

    response = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Alex",
            "profession": "Designer",
            "current_stage": "transition",
            "interests": ["writing"],
            "strengths": ["systems thinking"],
            "constraints": ["time"],
            "goal_intention": "Find a long-term direction worth building.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["status"] == "contract-draft"
    assert "question_count" not in payload
    assert "next_question" not in payload


def test_contract_route_compiles_direction_and_confirm_persists_contract_fields(
    tmp_path,
) -> None:
    client, store = _build_client(tmp_path)
    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Mina",
            "profession": "Operator",
            "current_stage": "exploring",
            "interests": ["content"],
            "strengths": ["consistency"],
            "constraints": ["money"],
            "goal_intention": "Find a real long-term direction.",
        },
    ).json()
    contract = _contract_payload(
        service_intent="Turn creative ambition into a weekly publishing rhythm.",
        autonomy_level="guarded-proactive",
        confirm_boundaries=["external spend", "publishing under my real name"],
        report_style="decision-first",
        collaboration_notes="Escalate blockers with one recommendation.",
    )

    compiled = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **contract},
    )

    assert compiled.status_code == 200
    compiled_payload = compiled.json()
    assert compiled_payload["recommended_direction"] == _CREATOR_DIRECTION
    assert compiled_payload["candidate_directions"] == [_CREATOR_DIRECTION]
    assert compiled_payload["final_goal"]
    assert compiled_payload["backlog_items"]
    assert "next_question" not in compiled_payload
    assert "question_count" not in compiled_payload

    preview = client.post(
        "/buddy/onboarding/direction-transition-preview",
        json={
            "session_id": identity["session_id"],
            "selected_direction": compiled_payload["recommended_direction"],
        },
    )
    assert preview.status_code == 200
    assert preview.json()["recommended_action"] == "start-new"

    confirm = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": compiled_payload["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert confirm.status_code == 200
    confirm_payload = confirm.json()
    assert confirm_payload["growth_target"]["primary_direction"] == _CREATOR_DIRECTION
    assert confirm_payload["growth_target"]["final_goal"] == compiled_payload["final_goal"]
    assert confirm_payload["growth_target"]["why_it_matters"] == compiled_payload["why_it_matters"]
    assert confirm_payload["domain_capability"]["status"] == "active"
    assert (
        confirm_payload["execution_carrier"]["instance_id"]
        == confirm_payload["domain_capability"]["industry_instance_id"]
    )
    assert (
        confirm_payload["execution_carrier"]["control_thread_id"]
        == confirm_payload["domain_capability"]["control_thread_id"]
    )

    relationship = SqliteCompanionRelationshipRepository(store).get_relationship(
        identity["profile"]["profile_id"],
    )
    instance = SqliteIndustryInstanceRepository(store).get_instance(
        confirm_payload["domain_capability"]["industry_instance_id"],
    )

    assert relationship is not None
    assert relationship.service_intent == contract["service_intent"]
    assert relationship.collaboration_role == contract["collaboration_role"]
    assert relationship.autonomy_level == contract["autonomy_level"]
    assert relationship.confirm_boundaries == contract["confirm_boundaries"]
    assert relationship.report_style == contract["report_style"]
    assert relationship.collaboration_notes == contract["collaboration_notes"]
    assert instance is not None
    assert instance.execution_core_identity_payload["operator_service_intent"] == contract["service_intent"]
    assert instance.execution_core_identity_payload["collaboration_role"] == contract["collaboration_role"]
    assert instance.execution_core_identity_payload["autonomy_level"] == contract["autonomy_level"]
    assert instance.execution_core_identity_payload["report_style"] == contract["report_style"]
    assert instance.execution_core_identity_payload["confirm_boundaries"] == contract["confirm_boundaries"]
    assert instance.execution_core_identity_payload["operating_mode"]
    assert instance.execution_core_identity_payload["delegation_policy"]
    assert instance.execution_core_identity_payload["direct_execution_policy"]
    assert len(client.app.state.cron_manager.jobs) >= 2


def test_contract_start_route_returns_contract_operation_kind(tmp_path, monkeypatch) -> None:
    client, store = _build_client(tmp_path)
    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Trader",
            "current_stage": "restart",
            "interests": ["stocks", "trading"],
            "strengths": ["review"],
            "constraints": ["capital"],
            "goal_intention": "Build a real stock trading path.",
        },
    ).json()

    def _run_now(*, name, work) -> None:
        _ = name
        work()

    monkeypatch.setattr(buddy_routes_module, "_spawn_buddy_onboarding_operation", _run_now)

    response = client.post(
        "/buddy/onboarding/contract/start",
        json={"session_id": identity["session_id"], **_contract_payload()},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["operation_kind"] == "contract"
    session = SqliteBuddyOnboardingSessionRepository(store).get_session(identity["session_id"])
    assert session is not None
    assert session.operation_kind == "contract"
    assert session.operation_status == "succeeded"
    assert session.recommended_direction
    assert session.draft_final_goal


def test_direction_transition_preview_suggests_keep_active_for_same_domain(tmp_path) -> None:
    client, _store = _build_client(tmp_path)
    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Mina",
            "profession": "Writer",
            "current_stage": "restart",
            "interests": ["writing", "content"],
            "strengths": ["consistency"],
            "constraints": ["money"],
            "goal_intention": "Build a creator direction.",
        },
    ).json()
    compiled = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    ).json()
    client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": compiled["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    resumed_identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Mina",
            "profession": "Writer",
            "current_stage": "restart",
            "interests": ["writing", "content"],
            "strengths": ["consistency"],
            "constraints": ["money"],
            "goal_intention": "Scale the same creator direction.",
        },
    ).json()
    resumed_contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": resumed_identity["session_id"], **_contract_payload()},
    ).json()

    preview = client.post(
        "/buddy/onboarding/direction-transition-preview",
        json={
            "session_id": resumed_identity["session_id"],
            "selected_direction": resumed_contract["recommended_direction"],
        },
    )

    assert preview.status_code == 200
    assert preview.json()["suggestion_kind"] == "same-domain"
    assert preview.json()["recommended_action"] == "keep-active"


def test_direction_transition_preview_and_confirm_supports_directional_recompile_for_second_candidate(
    tmp_path,
) -> None:
    client, _store = _build_client(tmp_path)
    client.app.state.buddy_onboarding_service._onboarding_reasoner = _MultiCandidateDirectionalCompiler()  # pylint: disable=protected-access
    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Mina",
            "profession": "Trader",
            "current_stage": "restart",
            "interests": ["stocks", "writing"],
            "strengths": ["consistency"],
            "constraints": ["money"],
            "goal_intention": "Build a real trading path but keep writing as an alternative direction.",
        },
    ).json()
    compiled = client.post(
        "/buddy/onboarding/contract",
        json={
            "session_id": identity["session_id"],
            **_contract_payload(
                service_intent="Turn trading ambition into a disciplined weekly execution path.",
            ),
        },
    ).json()

    preview = client.post(
        "/buddy/onboarding/direction-transition-preview",
        json={
            "session_id": identity["session_id"],
            "selected_direction": _CREATOR_DIRECTION,
        },
    )
    confirm = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": _CREATOR_DIRECTION,
            "capability_action": "start-new",
        },
    )

    assert compiled["candidate_directions"] == [_STOCKS_DIRECTION, _CREATOR_DIRECTION]
    assert preview.status_code == 200
    assert preview.json()["selected_direction"] == _CREATOR_DIRECTION
    assert confirm.status_code == 200
    assert confirm.json()["growth_target"]["primary_direction"] == _CREATOR_DIRECTION


def test_buddy_surface_is_pure_read_without_repair_side_effects(
    tmp_path,
    monkeypatch,
) -> None:
    client, _store = _build_client(tmp_path)
    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Mina",
            "profession": "Writer",
            "current_stage": "restart",
            "interests": ["writing"],
            "strengths": ["consistency"],
            "constraints": ["time"],
            "goal_intention": "Build a durable writing direction.",
        },
    ).json()
    profile_id = identity["profile"]["profile_id"]

    calls = {
        "repair_active_domain_schedules": 0,
        "repair_failed_activation": 0,
    }

    def _repair_active_domain_schedules(*, profile_id: str) -> None:
        _ = profile_id
        calls["repair_active_domain_schedules"] += 1

    def _repair_failed_activation(*, profile_id: str):
        _ = profile_id
        calls["repair_failed_activation"] += 1
        return None

    monkeypatch.setattr(
        client.app.state.buddy_onboarding_service,
        "repair_active_domain_schedules",
        _repair_active_domain_schedules,
    )
    monkeypatch.setattr(
        client.app.state.buddy_onboarding_service,
        "repair_failed_activation",
        _repair_failed_activation,
    )

    response = client.get("/buddy/surface", params={"profile_id": profile_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["profile_id"] == profile_id
    assert calls["repair_active_domain_schedules"] == 0
    assert calls["repair_failed_activation"] == 0


def test_buddy_entry_returns_resume_onboarding_for_existing_profile(tmp_path) -> None:
    client, _store = _build_client(tmp_path)
    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Mina",
            "profession": "Writer",
            "current_stage": "restart",
            "interests": ["writing"],
            "strengths": ["consistency"],
            "constraints": ["time"],
            "goal_intention": "Build a durable writing direction.",
        },
    ).json()
    profile_id = identity["profile"]["profile_id"]

    response = client.get("/buddy/entry", params={"profile_id": profile_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "resume-onboarding"
    assert payload["profile_id"] == profile_id
    assert payload["session_id"] == identity["session_id"]


def test_buddy_entry_returns_chat_ready_for_completed_onboarding(tmp_path) -> None:
    client, _store = _build_client(tmp_path)
    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Mina",
            "profession": "Writer",
            "current_stage": "restart",
            "interests": ["writing", "content"],
            "strengths": ["consistency"],
            "constraints": ["time"],
            "goal_intention": "Build a creator direction.",
        },
    ).json()
    contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    ).json()
    confirm = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    ).json()
    name_response = client.post(
        "/buddy/name",
        json={
            "session_id": identity["session_id"],
            "buddy_name": "Nova",
        },
    )
    assert name_response.status_code == 200

    response = client.get(
        "/buddy/entry",
        params={"profile_id": confirm["session"]["profile_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "chat-ready"
    assert payload["profile_id"] == confirm["session"]["profile_id"]
    assert payload["session_id"] is None
    assert payload["profile_display_name"] == "Mina"
    assert payload["execution_carrier"]["instance_id"] == confirm["execution_carrier"]["instance_id"]
    assert payload["execution_carrier"]["current_cycle_id"] == confirm["execution_carrier"]["current_cycle_id"]


def test_buddy_entry_uses_lightweight_entry_projection_instead_of_full_surface(
    tmp_path,
    monkeypatch,
) -> None:
    client, _store = _build_client(tmp_path)
    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Mina",
            "profession": "Writer",
            "current_stage": "restart",
            "interests": ["writing"],
            "strengths": ["consistency"],
            "constraints": ["time"],
            "goal_intention": "Build a durable writing direction.",
        },
    ).json()
    profile_id = identity["profile"]["profile_id"]

    calls = {"entry": 0}

    def _build_optional_entry_payload(*, profile_id: str | None = None):
        calls["entry"] += 1
        assert profile_id == identity["profile"]["profile_id"]
        return {
            "mode": "resume-onboarding",
            "profile_id": identity["profile"]["profile_id"],
            "session_id": identity["session_id"],
            "profile_display_name": None,
            "execution_carrier": None,
        }

    def _build_optional_chat_surface(*, profile_id: str | None = None):
        raise AssertionError(
            f"full buddy surface should not be built for /buddy/entry (profile_id={profile_id})"
        )

    monkeypatch.setattr(
        client.app.state.buddy_projection_service,
        "build_optional_entry_payload",
        _build_optional_entry_payload,
        raising=False,
    )
    monkeypatch.setattr(
        client.app.state.buddy_projection_service,
        "build_optional_chat_surface",
        _build_optional_chat_surface,
    )

    response = client.get("/buddy/entry", params={"profile_id": profile_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "resume-onboarding"
    assert payload["profile_id"] == profile_id
    assert calls["entry"] == 1
