# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyOnboardingGrowthPlan,
    BuddyOnboardingReasonedTurn,
)
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.kernel.buddy_projection_service import BuddyProjectionService
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
from tests.shared.buddy_reasoners import DeterministicBuddyReasoner


class _FakeCronManager:
    def __init__(self) -> None:
        self.jobs: list[object] = []

    async def create_or_replace_job(self, spec) -> None:
        self.jobs.append(spec)


class _BlockingIdentityReasoner(DeterministicBuddyReasoner):
    def __init__(self) -> None:
        self.release_plan_turn = threading.Event()

    def plan_turn(self, **kwargs) -> BuddyOnboardingReasonedTurn:
        released = self.release_plan_turn.wait(timeout=5)
        if not released:
            raise TimeoutError("test plan_turn gate timed out")
        return super().plan_turn(**kwargs)


class _BlockingConfirmReasoner(DeterministicBuddyReasoner):
    def __init__(self) -> None:
        self.release_growth_plan = threading.Event()

    def build_growth_plan(self, **kwargs) -> BuddyOnboardingGrowthPlan:
        released = self.release_growth_plan.wait(timeout=5)
        if not released:
            raise TimeoutError("test build_growth_plan gate timed out")
        return super().build_growth_plan(**kwargs)


class _TimeoutIdentityReasoner(DeterministicBuddyReasoner):
    def plan_turn(self, **kwargs) -> BuddyOnboardingReasonedTurn:
        raise TimeoutError("Buddy onboarding model timed out.")


def _build_app(tmp_path, *, reasoner) -> FastAPI:
    store = SQLiteStateStore(tmp_path / "buddy-async-onboarding.sqlite3")
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    onboarding_session_repository = SqliteBuddyOnboardingSessionRepository(store)
    industry_instance_repository = SqliteIndustryInstanceRepository(store)
    lane_service = OperatingLaneService(repository=SqliteOperatingLaneRepository(store))
    backlog_service = BacklogService(repository=SqliteBacklogItemRepository(store))
    cycle_service = OperatingCycleService(repository=SqliteOperatingCycleRepository(store))
    assignment_service = AssignmentService(repository=SqliteAssignmentRepository(store))
    schedule_repository = SqliteScheduleRepository(store)
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=industry_instance_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
    )
    service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=onboarding_session_repository,
        industry_instance_repository=industry_instance_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
        schedule_repository=schedule_repository,
        domain_capability_growth_service=growth_service,
        onboarding_reasoner=reasoner,
    )
    projection = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        onboarding_session_repository=onboarding_session_repository,
        domain_capability_repository=domain_capability_repository,
        domain_capability_growth_service=growth_service,
    )
    app = FastAPI()
    app.state.buddy_onboarding_service = service
    app.state.buddy_projection_service = projection
    app.state.cron_manager = _FakeCronManager()
    app.include_router(buddy_router)
    return app


def _wait_for_surface(client: TestClient, profile_id: str, *, operation_status: str, timeout: float = 5.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get("/buddy/surface", params={"profile_id": profile_id})
        assert response.status_code == 200
        payload = response.json()
        if payload["onboarding"]["operation_status"] == operation_status:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Buddy surface did not reach operation_status={operation_status!r} in time")


def test_start_identity_runs_in_background_and_surface_transitions_to_succeeded(tmp_path) -> None:
    reasoner = _BlockingIdentityReasoner()
    client = TestClient(_build_app(tmp_path, reasoner=reasoner))

    response = client.post(
        "/buddy/onboarding/identity/start",
        json={
            "display_name": "Kai",
            "profession": "Trader",
            "current_stage": "restart",
            "interests": ["stocks"],
            "strengths": ["review"],
            "constraints": ["capital"],
            "goal_intention": "Build a real stock trading path.",
        },
    )

    assert response.status_code == 202
    handle = response.json()
    assert handle["operation_kind"] == "identity"
    running_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="running",
    )
    assert running_surface["onboarding"]["session_id"] == handle["session_id"]
    assert running_surface["onboarding"]["operation_id"] == handle["operation_id"]
    reasoner.release_plan_turn.set()
    succeeded_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="succeeded",
    )
    assert succeeded_surface["onboarding"]["next_question"]
    assert succeeded_surface["onboarding"]["status"] == "clarifying"


def test_start_identity_surfaces_fail_closed_timeout(tmp_path) -> None:
    client = TestClient(_build_app(tmp_path, reasoner=_TimeoutIdentityReasoner()))

    response = client.post(
        "/buddy/onboarding/identity/start",
        json={
            "display_name": "Kai",
            "profession": "Trader",
            "current_stage": "restart",
            "interests": ["stocks"],
            "strengths": ["review"],
            "constraints": ["capital"],
            "goal_intention": "Build a real stock trading path.",
        },
    )

    assert response.status_code == 202
    handle = response.json()
    failed_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="failed",
    )
    assert "timed out" in failed_surface["onboarding"]["operation_error"].lower()
    assert failed_surface["onboarding"]["recommended_direction"] == ""


def test_start_confirm_direction_runs_in_background_and_materializes_execution_carrier(
    tmp_path,
) -> None:
    reasoner = _BlockingConfirmReasoner()
    client = TestClient(_build_app(tmp_path, reasoner=reasoner))

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
        "/buddy/onboarding/confirm-direction/start",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 202
    handle = response.json()
    running_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="running",
    )
    assert running_surface["onboarding"]["operation_kind"] == "confirm"
    reasoner.release_growth_plan.set()
    succeeded_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="succeeded",
    )
    assert succeeded_surface["growth_target"] is not None
    assert succeeded_surface["execution_carrier"] is not None
    assert succeeded_surface["onboarding"]["selected_direction"] == clarification["recommended_direction"]
