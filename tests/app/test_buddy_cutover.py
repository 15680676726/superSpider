# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi.testclient import TestClient

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
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
)
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)

from .runtime_center_api_parts.shared import FakeTurnExecutor, build_runtime_center_app


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
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
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
    return TestClient(app), store


def test_buddy_surface_and_runtime_center_surface_share_same_projection(tmp_path) -> None:
    client = _build_client(tmp_path)
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
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a direction with leverage, identity growth, and real independence.",
            "existing_question_count": 9,
        },
    ).json()
    client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
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


def test_runtime_center_legacy_buddy_summary_route_is_removed(tmp_path) -> None:
    client = _build_client(tmp_path)

    response = client.get("/runtime-center/main-brain/buddy-summary")

    assert response.status_code == 404


def test_buddy_confirm_direction_returns_execution_carrier_for_chat_binding(tmp_path) -> None:
    client = _build_client(tmp_path)
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
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a direction with leverage, identity growth, and real independence.",
            "existing_question_count": 9,
        },
    ).json()
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
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


def test_runtime_center_chat_run_preserves_strong_pull_signal_for_buddy_growth(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "buddy-chat-run.sqlite3")
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=session_repository,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=session_repository,
    )
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    app.state.turn_executor = turn_executor
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    client = TestClient(app)

    identity = onboarding_service.submit_identity(
        display_name="Mina",
        profession="Operator",
        current_stage="restart",
        interests=["writing"],
        strengths=["follow-through"],
        constraints=["time"],
        goal_intention="Build a durable direction.",
    )

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-buddy-strong-pull",
            "session_id": "industry-chat:buddy:profile-1:execution-core",
            "user_id": "buddy-user",
            "channel": "console",
            "thread_id": "industry-chat:buddy:profile-1:execution-core",
            "buddy_profile_id": identity.profile.profile_id,
            "interaction_mode": "strong-pull",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "I'm stuck and I keep avoiding this. I don't want to do it.",
                        }
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert getattr(turn_executor.stream_calls[0]["request_payload"], "interaction_mode", None) == "auto"
    relationship = relationship_repository.get_relationship(identity.profile.profile_id)
    assert relationship is not None
    assert relationship.strong_pull_count == 1


def test_http_buddy_surfaces_refresh_capability_growth_from_runtime_truth(tmp_path) -> None:
    client, store = _build_client_with_growth(tmp_path)
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
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a direction with leverage, identity growth, and real independence.",
            "existing_question_count": 9,
        },
    ).json()
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
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

    assert surface["growth"]["capability_score"] > 0
    assert surface["growth"]["execution_score"] > 0
    assert surface["growth"]["evidence_score"] > 0
    assert surface["growth"]["evolution_stage"] != "seed"
    assert summary["capability_score"] == surface["growth"]["capability_score"]
    assert summary["execution_score"] == surface["growth"]["execution_score"]
    assert summary["evidence_score"] == surface["growth"]["evidence_score"]
