# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingContractCompileResult,
)
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService, _STOCKS_DIRECTION
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


class _FakeCronManager:
    def __init__(self) -> None:
        self.jobs: list[object] = []

    async def create_or_replace_job(self, spec) -> None:
        self.jobs.append(spec)


class _BaseContractCompiler:
    def _result(self) -> BuddyOnboardingContractCompileResult:
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


class _BlockingContractCompiler(_BaseContractCompiler):
    def __init__(self) -> None:
        self.release_compile = threading.Event()

    def compile_contract(self, **kwargs) -> BuddyOnboardingContractCompileResult:
        _ = kwargs
        released = self.release_compile.wait(timeout=5)
        if not released:
            raise TimeoutError("test compile_contract gate timed out")
        return self._result()


class _FailOnceThenSucceedContractCompiler(_BaseContractCompiler):
    def __init__(self) -> None:
        self.calls = 0

    def compile_contract(self, **kwargs) -> BuddyOnboardingContractCompileResult:
        _ = kwargs
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("Buddy onboarding model timed out.")
        return self._result()


class _DeterministicContractCompiler(_BaseContractCompiler):
    def compile_contract(self, **kwargs) -> BuddyOnboardingContractCompileResult:
        _ = kwargs
        return self._result()


def _build_app(tmp_path, *, compiler) -> FastAPI:
    store = SQLiteStateStore(tmp_path / "buddy-async-contract.sqlite3")
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
        onboarding_reasoner=compiler,
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


def _wait_for_surface(
    client: TestClient,
    profile_id: str,
    *,
    operation_status: str,
    timeout: float = 5.0,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get("/buddy/surface", params={"profile_id": profile_id})
        assert response.status_code == 200
        payload = response.json()
        if payload["onboarding"]["operation_status"] == operation_status:
            return payload
        time.sleep(0.05)
    raise AssertionError(
        f"Buddy surface did not reach operation_status={operation_status!r} in time"
    )


def test_start_contract_compile_runs_in_background_and_surface_transitions_to_succeeded(
    tmp_path,
) -> None:
    compiler = _BlockingContractCompiler()
    client = TestClient(_build_app(tmp_path, compiler=compiler))
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()

    response = client.post(
        "/buddy/onboarding/contract/start",
        json={"session_id": identity["session_id"], **_contract_payload()},
    )

    assert response.status_code == 202
    handle = response.json()
    assert handle["operation_kind"] == "contract"
    running_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="running",
    )
    assert running_surface["onboarding"]["status"] == "contract-draft"
    compiler.release_compile.set()
    succeeded_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="succeeded",
    )
    assert succeeded_surface["onboarding"]["status"] == "contract-ready"
    assert succeeded_surface["onboarding"]["recommended_direction"] == _STOCKS_DIRECTION
    assert "next_question" not in succeeded_surface["onboarding"]


def test_sync_contract_submit_clears_stale_async_failure_on_surface(tmp_path) -> None:
    compiler = _FailOnceThenSucceedContractCompiler()
    client = TestClient(_build_app(tmp_path, compiler=compiler))
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()

    response = client.post(
        "/buddy/onboarding/contract/start",
        json={"session_id": identity["session_id"], **_contract_payload()},
    )

    assert response.status_code == 202
    handle = response.json()
    failed_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="failed",
    )
    assert failed_surface["onboarding"]["operation_error"] == "伙伴建档模型响应超时。"

    retry = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    )

    assert retry.status_code == 200
    surface = client.get("/buddy/surface", params={"profile_id": handle["profile_id"]}).json()
    assert surface["onboarding"]["status"] == "contract-ready"
    assert surface["onboarding"]["operation_status"] == "idle"
    assert surface["onboarding"]["operation_error"] == ""


def test_start_identity_operation_creates_distinct_profile_without_overwriting_latest(
    tmp_path,
) -> None:
    client = TestClient(_build_app(tmp_path, compiler=_DeterministicContractCompiler()))
    first = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()

    second_payload = {
        **_identity_payload(),
        "display_name": "Beta",
        "profession": "Operator",
        "goal_intention": "Build a second durable direction with leverage.",
    }
    response = client.post("/buddy/onboarding/identity/start", json=second_payload)

    assert response.status_code == 202
    handle = response.json()
    succeeded_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="succeeded",
    )
    profile_repository = client.app.state.buddy_onboarding_service._profile_repository  # pylint: disable=protected-access
    stored_first = profile_repository.get_profile(first["profile"]["profile_id"])

    assert handle["profile_id"] != first["profile"]["profile_id"]
    assert profile_repository.count_profiles() == 2
    assert stored_first is not None
    assert stored_first.display_name == _identity_payload()["display_name"]
    assert succeeded_surface["profile"]["display_name"] == "Beta"


def test_start_confirm_direction_materializes_execution_carrier_after_contract_ready(
    tmp_path,
) -> None:
    client = TestClient(_build_app(tmp_path, compiler=_DeterministicContractCompiler()))
    identity = client.post("/buddy/onboarding/identity", json=_identity_payload()).json()
    contract = client.post(
        "/buddy/onboarding/contract",
        json={"session_id": identity["session_id"], **_contract_payload()},
    ).json()

    response = client.post(
        "/buddy/onboarding/confirm-direction/start",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 202
    handle = response.json()
    succeeded_surface = _wait_for_surface(
        client,
        handle["profile_id"],
        operation_status="succeeded",
    )
    assert succeeded_surface["growth_target"] is not None
    assert succeeded_surface["execution_carrier"] is not None
    assert (
        succeeded_surface["onboarding"]["selected_direction"]
        == contract["recommended_direction"]
    )
