# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingContractCompileResult,
)
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService, _CREATOR_DIRECTION, _STOCKS_DIRECTION
from copaw.state import HumanProfile, SQLiteStateStore
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)


class _TimeoutContractCompiler:
    def compile_contract(self, **kwargs) -> BuddyOnboardingContractCompileResult:
        _ = kwargs
        raise TimeoutError("Buddy onboarding model timed out.")


class _BrokenContractCompiler:
    def compile_contract(self, **kwargs) -> BuddyOnboardingContractCompileResult:
        _ = kwargs
        raise RuntimeError("provider exploded")


class _DeterministicContractCompiler:
    def compile_contract(self, **kwargs) -> BuddyOnboardingContractCompileResult:
        _ = kwargs
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


class _MultiCandidateContractCompiler(_DeterministicContractCompiler):
    def compile_contract(self, **kwargs) -> BuddyOnboardingContractCompileResult:
        compiled = super().compile_contract(**kwargs)
        return compiled.model_copy(
            update={
                "candidate_directions": [_STOCKS_DIRECTION, _CREATOR_DIRECTION],
                "recommended_direction": _STOCKS_DIRECTION,
            }
        )


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


def _build_service(tmp_path, *, compiler) -> BuddyOnboardingService:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-route-latency.sqlite3")
    return BuddyOnboardingService(
        profile_repository=SqliteHumanProfileRepository(store),
        growth_target_repository=SqliteGrowthTargetRepository(store),
        relationship_repository=SqliteCompanionRelationshipRepository(store),
        domain_capability_repository=SqliteBuddyDomainCapabilityRepository(store),
        onboarding_session_repository=SqliteBuddyOnboardingSessionRepository(store),
        onboarding_reasoner=compiler,
    )


def _build_app(tmp_path, *, compiler) -> tuple[FastAPI, BuddyOnboardingService]:
    app = FastAPI()
    service = _build_service(tmp_path, compiler=compiler)
    app.state.buddy_onboarding_service = service
    app.include_router(buddy_router)
    return app, service


def _identity_payload() -> dict[str, object]:
    return {
        "display_name": "Kai",
        "profession": "Trader",
        "current_stage": "restart",
        "interests": ["stocks", "trading"],
        "strengths": ["review"],
        "constraints": ["capital"],
        "goal_intention": "Build a real stock trading path.",
    }


def _contract_payload() -> dict[str, object]:
    return {
        "service_intent": "Turn trading ambition into a disciplined weekly execution path.",
        "collaboration_role": "orchestrator",
        "autonomy_level": "guarded-proactive",
        "confirm_boundaries": ["external spend", "irreversible actions"],
        "report_style": "decision-first",
        "collaboration_notes": "Escalate when an action exceeds the agreed risk boundary.",
    }


def test_contract_returns_gateway_timeout_when_compiler_times_out(tmp_path) -> None:
    app, service = _build_app(tmp_path, compiler=_TimeoutContractCompiler())
    client = TestClient(app)
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()

    response = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "伙伴建档模型响应超时。"
    session = service._onboarding_session_repository.get_session(identity["session_id"])  # pylint: disable=protected-access
    assert session is not None
    assert session.status == "contract-draft"
    assert session.draft_direction == ""
    assert session.draft_final_goal == ""


def test_contract_returns_service_unavailable_when_compiler_fails(tmp_path) -> None:
    app, _service = _build_app(tmp_path, compiler=_BrokenContractCompiler())
    client = TestClient(app)
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()

    response = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    )

    assert response.status_code == 503
    assert "伙伴建档模型" in response.json()["detail"]


def test_confirm_direction_rejects_missing_contract_compile(tmp_path) -> None:
    app, _service = _build_app(tmp_path, compiler=_DeterministicContractCompiler())
    client = TestClient(app)
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()

    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": _STOCKS_DIRECTION,
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 400
    assert "协作合同编译" in response.json()["detail"]


def test_confirm_direction_rejects_alternate_candidate_without_matching_compile(
    tmp_path,
) -> None:
    app, _service = _build_app(tmp_path, compiler=_MultiCandidateContractCompiler())
    client = TestClient(app)
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()
    contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    ).json()

    assert contract["candidate_directions"] == [_STOCKS_DIRECTION, _CREATOR_DIRECTION]

    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": _CREATOR_DIRECTION,
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 400
    assert "重新编译协作合同" in response.json()["detail"]


def test_confirm_direction_queues_activation_instead_of_waiting_for_kickoff(tmp_path) -> None:
    industry_service = _DelayedIndustryService()
    app, _service = _build_app(tmp_path, compiler=_DeterministicContractCompiler())
    app.state.industry_service = industry_service
    client = TestClient(app)

    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()
    contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    ).json()

    started = time.perf_counter()
    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
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
