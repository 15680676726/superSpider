# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyOnboardingGrowthPlan,
    BuddyOnboardingReasonedTurn,
)
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.state import HumanProfile, SQLiteStateStore
from copaw.state.repositories_buddy import (
    BuddyOnboardingSessionRecord,
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)
from tests.shared.buddy_reasoners import DeterministicBuddyReasoner


_UNSET = object()


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


class _BrokenReasoner:
    def plan_turn(self, **kwargs):
        raise RuntimeError("provider exploded")

    def build_growth_plan(self, **kwargs):
        raise RuntimeError("provider exploded")


class _IncompleteQuestionReasoner:
    def plan_turn(self, **kwargs) -> BuddyOnboardingReasonedTurn:
        return BuddyOnboardingReasonedTurn(
            finished=False,
            next_question="",
            candidate_directions=["Build a disciplined stock trading path."],
            recommended_direction="Build a disciplined stock trading path.",
        )

    def build_growth_plan(self, **kwargs):
        raise AssertionError("build_growth_plan should not run in this test")


class _IncompleteGrowthPlanReasoner:
    def plan_turn(self, **kwargs) -> BuddyOnboardingReasonedTurn:
        return BuddyOnboardingReasonedTurn(
            finished=True,
            next_question="",
            candidate_directions=["Build a disciplined stock trading path."],
            recommended_direction="Build a disciplined stock trading path.",
        )

    def build_growth_plan(self, **kwargs):
        return BuddyOnboardingGrowthPlan(
            primary_direction="Build a disciplined stock trading path.",
            final_goal="",
            why_it_matters="",
            backlog_items=[],
        )


def _build_service(tmp_path, *, reasoner=_UNSET) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-route-latency.sqlite3")
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        onboarding_reasoner=(
            DeterministicBuddyReasoner()
            if reasoner is _UNSET
            else reasoner
        ),
    )


def test_identity_returns_gateway_timeout_when_reasoner_times_out_for_ambiguous_goal(
    tmp_path,
) -> None:
    app = FastAPI()
    service = _build_service(tmp_path, reasoner=_TimeoutReasoner())
    app.state.buddy_onboarding_service = service
    app.include_router(buddy_router)
    client = TestClient(app)

    stale_profile = service._profile_repository.upsert_profile(  # pylint: disable=protected-access
        HumanProfile(
            display_name="Old Kai",
            profession="Trader",
            current_stage="restart",
            interests=["stocks"],
            strengths=["review"],
            constraints=["capital"],
            goal_intention="Old ambiguous goal.",
        )
    )
    service._onboarding_session_repository.upsert_session(  # pylint: disable=protected-access
        BuddyOnboardingSessionRecord(
            profile_id=stale_profile.profile_id,
            status="clarifying",
            question_count=1,
            next_question="Old question?",
            transcript=["????????"],
            candidate_directions=["Old direction"],
            recommended_direction="Old direction",
        ),
    )

    response = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Trader",
            "current_stage": "restart",
            "interests": ["stocks"],
            "strengths": ["review"],
            "constraints": ["capital"],
            "goal_intention": "Find a real long-term path.",
        },
    )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()
    session = service._onboarding_session_repository.get_latest_session_for_profile(  # pylint: disable=protected-access
        stale_profile.profile_id,
    )
    assert session is not None
    assert session.transcript == ["Find a real long-term path."]
    assert session.candidate_directions == []
    assert session.recommended_direction == ""


def test_identity_returns_service_unavailable_when_reasoner_fails(tmp_path) -> None:
    app = FastAPI()
    app.state.buddy_onboarding_service = _build_service(tmp_path, reasoner=_BrokenReasoner())
    app.include_router(buddy_router)
    client = TestClient(app)

    response = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Operator",
            "current_stage": "restart",
            "interests": ["systems"],
            "strengths": ["follow-through"],
            "constraints": ["time"],
            "goal_intention": "Find a real long-term path.",
        },
    )

    assert response.status_code == 503
    assert "model" in response.json()["detail"].lower()


def test_identity_returns_service_unavailable_when_reasoner_is_missing(tmp_path) -> None:
    app = FastAPI()
    app.state.buddy_onboarding_service = _build_service(tmp_path, reasoner=None)
    app.include_router(buddy_router)
    client = TestClient(app)

    response = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Operator",
            "current_stage": "restart",
            "interests": ["systems"],
            "strengths": ["follow-through"],
            "constraints": ["time"],
            "goal_intention": "Find a real long-term path.",
        },
    )

    assert response.status_code == 503
    assert "model" in response.json()["detail"].lower()


def test_identity_returns_service_unavailable_when_reasoner_omits_next_question(
    tmp_path,
) -> None:
    app = FastAPI()
    app.state.buddy_onboarding_service = _build_service(
        tmp_path,
        reasoner=_IncompleteQuestionReasoner(),
    )
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
            "goal_intention": "Find a real stock trading path.",
        },
    )

    assert response.status_code == 503
    assert "valid result" in response.json()["detail"].lower()


def test_clarify_returns_gateway_timeout_without_reusing_stale_recommendations(
    tmp_path,
) -> None:
    app = FastAPI()
    service = _build_service(tmp_path, reasoner=_TimeoutReasoner())
    app.state.buddy_onboarding_service = service
    app.include_router(buddy_router)
    client = TestClient(app)

    profile = service._profile_repository.upsert_profile(  # pylint: disable=protected-access
        HumanProfile(
            display_name="Kai",
            profession="Trader",
            current_stage="restart",
            interests=["stocks"],
            strengths=["review"],
            constraints=["capital"],
            goal_intention="Build a trading path.",
        )
    )
    session = service._onboarding_session_repository.upsert_session(  # pylint: disable=protected-access
        BuddyOnboardingSessionRecord(
            profile_id=profile.profile_id,
            status="clarifying",
            question_count=1,
            next_question="What exactly do you want?",
            transcript=["Build a trading path."],
            candidate_directions=["Old direction"],
            recommended_direction="Old direction",
        )
    )

    response = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": session.session_id,
            "answer": "I want a strict stock trading system.",
        },
    )

    assert response.status_code == 504
    latest = service._onboarding_session_repository.get_session(session.session_id)  # pylint: disable=protected-access
    assert latest is not None
    assert latest.transcript == [
        "Build a trading path.",
        "I want a strict stock trading system.",
    ]
    assert latest.next_question == ""
    assert latest.candidate_directions == []
    assert latest.recommended_direction == ""


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
    assert elapsed < 0.5

    deadline = time.time() + 1.0
    while not industry_service.calls and time.time() < deadline:
        time.sleep(0.02)
    assert industry_service.calls


def test_confirm_direction_returns_service_unavailable_when_growth_plan_is_incomplete(
    tmp_path,
) -> None:
    app = FastAPI()
    app.state.buddy_onboarding_service = _build_service(
        tmp_path,
        reasoner=_IncompleteGrowthPlanReasoner(),
    )
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
    )
    assert identity.status_code == 200
    session_id = identity.json()["session_id"]

    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": session_id,
            "selected_direction": "Build a disciplined stock trading path.",
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 503
    assert "valid result" in response.json()["detail"].lower()
