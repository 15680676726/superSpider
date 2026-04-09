# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
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


def _build_client(tmp_path) -> TestClient:
    store = SQLiteStateStore(tmp_path / "buddy-routes.sqlite3")
    service = BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
    )
    app = FastAPI()
    app.state.buddy_onboarding_service = service
    app.include_router(buddy_router)
    return TestClient(app)


class _FakeCronManager:
    def __init__(self) -> None:
        self.jobs: list[object] = []

    async def create_or_replace_job(self, spec) -> None:
        self.jobs.append(spec)


def test_create_identity_profile_returns_session_token(tmp_path) -> None:
    client = _build_client(tmp_path)

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
    assert payload["question_count"] == 1
    assert payload["next_question"]


def test_clarification_route_caps_after_nine_questions(tmp_path) -> None:
    client = _build_client(tmp_path)
    identity = client.post(
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
    ).json()

    response = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I still feel lost",
            "existing_question_count": 9,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["finished"] is True
    assert payload["question_count"] == 9
    assert 1 <= len(payload["candidate_directions"]) <= 3


def test_confirm_primary_direction_and_name_buddy(tmp_path) -> None:
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

    clarify = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a direction with leverage, identity growth, and real independence.",
            "existing_question_count": 9,
        },
    )
    recommended = clarify.json()["recommended_direction"]

    preview = client.post(
        "/buddy/onboarding/direction-transition-preview",
        json={
            "session_id": identity["session_id"],
            "selected_direction": recommended,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["recommended_action"] == "start-new"

    confirm = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": recommended,
            "capability_action": "start-new",
        },
    )
    assert confirm.status_code == 200
    assert confirm.json()["growth_target"]["primary_direction"] == recommended
    assert confirm.json()["domain_capability"]["status"] == "active"
    assert (
        confirm.json()["execution_carrier"]["instance_id"]
        == confirm.json()["domain_capability"]["industry_instance_id"]
    )
    assert (
        confirm.json()["execution_carrier"]["control_thread_id"]
        == confirm.json()["domain_capability"]["control_thread_id"]
    )

    naming = client.post(
        "/buddy/name",
        json={
            "session_id": identity["session_id"],
            "buddy_name": "Nova",
        },
    )
    assert naming.status_code == 200
    assert naming.json()["buddy_name"] == "Nova"


def test_direction_transition_preview_suggests_keep_active_for_same_domain(tmp_path) -> None:
    client = _build_client(tmp_path)
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
    clarify = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a creator direction with leverage and long-term proof of work.",
            "existing_question_count": 9,
        },
    ).json()
    client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarify["recommended_direction"],
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
    resumed_clarify = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": resumed_identity["session_id"],
            "answer": "I want to stay on the same creator direction and push it further.",
            "existing_question_count": 9,
        },
    ).json()

    preview = client.post(
        "/buddy/onboarding/direction-transition-preview",
        json={
            "session_id": resumed_identity["session_id"],
            "selected_direction": resumed_clarify["recommended_direction"],
        },
    )

    assert preview.status_code == 200
    assert preview.json()["suggestion_kind"] == "same-domain"
    assert preview.json()["recommended_action"] == "keep-active"


def test_confirm_direction_registers_durable_buddy_schedules_with_cron_manager(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "buddy-routes-cron.sqlite3")
    industry_repository = SqliteIndustryInstanceRepository(store)
    lane_service = OperatingLaneService(repository=SqliteOperatingLaneRepository(store))
    backlog_service = BacklogService(repository=SqliteBacklogItemRepository(store))
    cycle_service = OperatingCycleService(repository=SqliteOperatingCycleRepository(store))
    assignment_service = AssignmentService(repository=SqliteAssignmentRepository(store))
    service = BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
        schedule_repository=SqliteScheduleRepository(store),
        domain_capability_growth_service=BuddyDomainCapabilityGrowthService(
            domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
            industry_instance_repository=industry_repository,
            operating_lane_service=lane_service,
            backlog_service=backlog_service,
            operating_cycle_service=cycle_service,
            assignment_service=assignment_service,
        ),
    )
    app = FastAPI()
    app.state.buddy_onboarding_service = service
    app.state.cron_manager = _FakeCronManager()
    app.include_router(buddy_router)
    client = TestClient(app)

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
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a durable trading system with strict risk control.",
        },
    ).json()

    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 200
    assert len(app.state.cron_manager.jobs) >= 2
