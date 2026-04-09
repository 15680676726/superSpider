# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_onboarding_reasoner import BuddyOnboardingReasonedTurn
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.state import SQLiteStateStore
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)


class _TimeoutReasoner:
    def plan_turn(self, **kwargs) -> BuddyOnboardingReasonedTurn:
        raise TimeoutError("Buddy onboarding model timed out.")

    def build_growth_plan(self, **kwargs):
        raise AssertionError("build_growth_plan should not run in this test")


class _DelayedIndustryService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def kickoff_execution_from_chat(self, **kwargs):
        await asyncio.sleep(0.2)
        self.calls.append(dict(kwargs))
        return {
            "activated": True,
            "industry_instance_id": kwargs["industry_instance_id"],
        }


def _build_service(tmp_path, *, reasoner=None) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-route-latency.sqlite3")
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        onboarding_reasoner=reasoner,
    )


def test_identity_returns_gateway_timeout_when_reasoner_times_out(tmp_path) -> None:
    app = FastAPI()
    app.state.buddy_onboarding_service = _build_service(tmp_path, reasoner=_TimeoutReasoner())
    app.include_router(buddy_router)
    client = TestClient(app)

    response = client.post(
        "/buddy/onboarding/identity",
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

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_confirm_direction_queues_activation_instead_of_waiting_for_kickoff(tmp_path) -> None:
    industry_service = _DelayedIndustryService()
    app = FastAPI()
    app.state.buddy_onboarding_service = _build_service(tmp_path)
    app.state.industry_service = industry_service
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

    started = time.perf_counter()
    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
            "capability_action": "start-new",
        },
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    payload = response.json()
    assert payload["activation"]["status"] == "queued"
    assert payload["activation"]["trigger_source"] == "buddy-onboarding"
    assert elapsed < 0.15

    deadline = time.time() + 1.0
    while not industry_service.calls and time.time() < deadline:
        time.sleep(0.02)
    assert industry_service.calls
