# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import BaseModel

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import BuddyOnboardingBacklogSeed
from copaw.kernel.buddy_onboarding_service import (
    BuddyOnboardingService,
    _CREATOR_DIRECTION,
    _STOCKS_DIRECTION,
)
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.state import AgentReportRecord, SQLiteStateStore
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
    SqliteScheduleRepository,
)
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)

from .runtime_center_api_parts.shared import FakeTurnExecutor, build_runtime_center_app


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


def _build_client(tmp_path) -> TestClient:
    store = SQLiteStateStore(tmp_path / "buddy-cutover.sqlite3")
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        onboarding_reasoner=_DeterministicContractCompiler(),
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        current_focus_resolver=lambda _profile_id: {
            "current_task_summary": "Finish today's current task",
            "why_now_summary": "This unlocks the next real milestone.",
        },
    )
    app = build_runtime_center_app()
    app.include_router(buddy_router)
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    return TestClient(app)


def _build_client_with_growth(tmp_path) -> tuple[TestClient, SQLiteStateStore]:
    store = SQLiteStateStore(tmp_path / "buddy-cutover-growth.sqlite3")
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
    schedule_repository = SqliteScheduleRepository(store)
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
        agent_report_service=report_service,
    )
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        onboarding_reasoner=_DeterministicContractCompiler(),
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
        schedule_repository=schedule_repository,
        domain_capability_growth_service=growth_service,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        domain_capability_growth_service=growth_service,
        current_focus_resolver=lambda _profile_id: {
            "current_task_summary": "Finish today's current task",
            "why_now_summary": "This unlocks the next real milestone.",
        },
    )
    app = build_runtime_center_app()
    app.include_router(buddy_router)
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    app.state.schedule_repository = schedule_repository
    return TestClient(app), store


def _identity_payload() -> dict[str, object]:
    return {
        "display_name": "Mina",
        "profession": "Operator",
        "current_stage": "exploring",
        "interests": ["content"],
        "strengths": ["consistency"],
        "constraints": ["money"],
        "goal_intention": "Find a real long-term direction.",
    }


def test_clarify_routes_are_removed_and_contract_route_is_live(tmp_path) -> None:
    client = _build_client(tmp_path)
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()

    clarify = client.post(
        "/buddy/onboarding/clarify",
        json={"session_id": identity["session_id"], "answer": "anything"},
    )
    clarify_start = client.post(
        "/buddy/onboarding/clarify/start",
        json={"session_id": identity["session_id"], "answer": "anything"},
    )
    contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    )

    assert clarify.status_code == 404
    assert clarify_start.status_code == 404
    assert contract.status_code == 200
    assert "question_count" not in contract.json()
    assert "next_question" not in contract.json()


def test_buddy_surface_and_runtime_center_surface_share_same_projection(tmp_path) -> None:
    client = _build_client(tmp_path)
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()
    contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    ).json()
    client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    )
    client.post(
        "/buddy/name",
        json={"session_id": identity["session_id"], "buddy_name": "Mochi"},
    )

    surface = client.get("/buddy/surface").json()
    runtime_surface = client.get(
        f"/runtime-center/surface?sections=main_brain&buddy_profile_id={surface['profile']['profile_id']}",
    ).json()
    summary = runtime_surface["main_brain"]["buddy_summary"]

    assert surface["execution_carrier"]["instance_id"]
    assert surface["execution_carrier"]["control_thread_id"] == surface["execution_carrier"]["thread_id"]
    assert surface["presentation"]["buddy_name"] == "Mochi"
    assert summary["buddy_name"] == "Mochi"
    assert summary["evolution_stage"] == surface["growth"]["evolution_stage"]
    assert summary["capability_score"] == surface["growth"]["capability_score"]
    assert summary["current_task_summary"] == "Finish today's current task"


def test_buddy_confirm_direction_returns_execution_carrier_for_chat_binding(tmp_path) -> None:
    client = _build_client(tmp_path)
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()
    contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    ).json()
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    ).json()

    execution_carrier = confirmation.get("execution_carrier")
    assert execution_carrier is not None
    assert execution_carrier["instance_id"] == confirmation["domain_capability"]["industry_instance_id"]
    assert execution_carrier["owner_scope"] == identity["profile"]["profile_id"]
    assert execution_carrier["control_thread_id"] == confirmation["domain_capability"]["control_thread_id"]
    assert execution_carrier["thread_id"] == confirmation["domain_capability"]["control_thread_id"]
    assert execution_carrier["chat_binding"]["thread_id"] == execution_carrier["thread_id"]
    assert execution_carrier["chat_binding"]["control_thread_id"] == execution_carrier["control_thread_id"]
    assert execution_carrier["chat_binding"]["channel"] == "console"
    assert execution_carrier["chat_binding"]["binding_kind"] == "buddy-execution-carrier"


def test_runtime_center_chat_run_uses_confirmed_buddy_execution_carrier_binding(
    tmp_path,
) -> None:
    client, _store = _build_client_with_growth(tmp_path)
    turn_executor = FakeTurnExecutor()
    client.app.state.turn_executor = turn_executor

    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Analyst",
            "current_stage": "restart",
            "interests": ["stocks", "trading"],
            "strengths": ["discipline"],
            "constraints": ["money"],
            "goal_intention": "I want a real stock trading path.",
        },
    ).json()
    contract = client.post(
        "/buddy/onboarding/contract",
        json={
            "session_id": identity["session_id"],
            **_contract_payload(
                service_intent="Turn trading ambition into a disciplined weekly execution path.",
            ),
        },
    ).json()
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    ).json()

    control_thread_id = confirmation["execution_carrier"]["control_thread_id"]
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-buddy-confirmed-carrier",
            "session_id": control_thread_id,
            "thread_id": control_thread_id,
            "user_id": identity["profile"]["profile_id"],
            "channel": "console",
            "buddy_profile_id": identity["profile"]["profile_id"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Push the single most important step for today and report back after it ships.",
                        }
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    request_payload = turn_executor.stream_calls[0]["request_payload"]
    assert getattr(request_payload, "session_id", None) == control_thread_id
    assert getattr(request_payload, "thread_id", None) == control_thread_id
    assert getattr(request_payload, "control_thread_id", None) == control_thread_id
    assert getattr(request_payload, "buddy_profile_id", None) == identity["profile"]["profile_id"]
    assert getattr(request_payload, "session_kind", None) == "industry-control-thread"


def test_http_buddy_surfaces_refresh_capability_growth_from_runtime_truth(tmp_path) -> None:
    client, store = _build_client_with_growth(tmp_path)
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()
    contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    ).json()
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    ).json()

    assignment_repository = SqliteAssignmentRepository(store)
    report_repository = SqliteAgentReportRepository(store)
    instance_id = confirmation["domain_capability"]["industry_instance_id"]
    assignments = assignment_repository.list_assignments(industry_instance_id=instance_id)
    assert assignments
    first_assignment = assignments[0]
    assignment_repository.upsert_assignment(
        first_assignment.model_copy(
            update={
                "status": "completed",
                "evidence_ids": ["ev-http-1", "ev-http-2"],
                "last_report_id": "report-http-1",
            }
        )
    )
    report_repository.upsert_report(
        AgentReportRecord(
            id="report-http-1",
            industry_instance_id=instance_id,
            cycle_id=first_assignment.cycle_id,
            assignment_id=first_assignment.id,
            lane_id=first_assignment.lane_id,
            headline="HTTP proof shipped",
            summary="The first proof is available through the Buddy runtime.",
            status="recorded",
            result="completed",
            evidence_ids=["ev-http-1", "ev-http-2"],
        )
    )

    surface = client.get(f"/buddy/surface?profile_id={identity['profile']['profile_id']}").json()
    runtime_surface = client.get(
        f"/runtime-center/surface?sections=main_brain&buddy_profile_id={identity['profile']['profile_id']}",
    ).json()
    summary = runtime_surface["main_brain"]["buddy_summary"]

    assert surface["growth"]["capability_points"] == 2
    assert surface["growth"]["settled_closure_count"] == 1
    assert surface["growth"]["capability_score"] > 0
    assert surface["growth"]["execution_score"] > 0
    assert surface["growth"]["evidence_score"] > 0
    assert surface["growth"]["evolution_stage"] == "seed"
    assert summary["capability_score"] == surface["growth"]["capability_score"]
    assert summary["execution_score"] == surface["growth"]["execution_score"]
    assert summary["evidence_score"] == surface["growth"]["evidence_score"]
