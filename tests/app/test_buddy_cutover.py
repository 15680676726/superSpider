# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi.testclient import TestClient

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.state import SQLiteStateStore
from copaw.state.repositories_buddy import (
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
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        onboarding_session_repository=session_repository,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
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

    assert surface["presentation"]["buddy_name"] == "Mochi"
    assert summary["buddy_name"] == "Mochi"
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
        },
    ).json()

    execution_carrier = confirmation.get("execution_carrier")
    assert execution_carrier is not None
    assert execution_carrier["instance_id"] == f"buddy:{identity['profile']['profile_id']}"
    assert execution_carrier["owner_scope"] == identity["profile"]["profile_id"]
    assert execution_carrier["control_thread_id"] == (
        f"industry-chat:buddy:{identity['profile']['profile_id']}:execution-core"
    )
    assert execution_carrier["thread_id"] == (
        f"industry-chat:buddy:{identity['profile']['profile_id']}:execution-core"
    )
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
        onboarding_session_repository=session_repository,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
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
