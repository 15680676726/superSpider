# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.skill_lifecycle_decision_service import SkillLifecycleDecisionService
from copaw.state.skill_trial_service import SkillTrialService


class _FakeStateQueryService:
    def list_capability_packages(self, *, limit: int | None = None):
        return [
            {
                "package_id": "package-1",
                "donor_id": "donor-1",
                "package_kind": "skill",
            },
        ][: limit or 20]

    def list_capability_trust_records(self, *, limit: int | None = None):
        return [
            {
                "donor_id": "donor-1",
                "trust_status": "trusted",
                "trial_success_count": 3,
            },
        ][: limit or 20]

    def get_capability_scout_summary(self):
        return {
            "status": "ready",
            "last_mode": "opportunity",
            "imported_candidate_count": 2,
        }


def test_runtime_center_donor_routes_expose_packages_trust_and_scout() -> None:
    app = FastAPI()
    app.include_router(runtime_center_router)
    app.state.state_query_service = _FakeStateQueryService()
    client = TestClient(app)

    packages = client.get("/runtime-center/capabilities/packages")
    trust = client.get("/runtime-center/capabilities/trust")
    scout = client.get("/runtime-center/capabilities/scout")

    assert packages.status_code == 200
    assert packages.json()[0]["package_id"] == "package-1"
    assert trust.status_code == 200
    assert trust.json()[0]["trust_status"] == "trusted"
    assert scout.status_code == 200
    assert scout.json()["status"] == "ready"


def test_runtime_center_donor_routes_project_probe_and_contract_truth_from_trials_and_decisions(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)
    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="adapter",
        target_scope="seat",
        target_role_id="execution-core",
        target_seat_ref="seat-1",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://github.com/example/openspace-donor",
        candidate_source_version="main",
        ingestion_mode="capability-market",
        proposed_skill_name="openspace",
        summary="Probe-verified donor candidate.",
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        donor_id="donor-1",
        package_id="package-1",
        scope_type="seat",
        scope_ref="seat-1",
        verdict="passed",
        summary="Primary action verified.",
        verified_stage="primary_action_verified",
        provider_resolution_status="resolved",
        compatibility_status="compatible_native",
        metadata={
            "selected_adapter_action_id": "execute_task",
            "probe_result": {
                "probe_outcome": "succeeded",
                "probe_error_type": None,
                "probe_evidence_refs": ["ev-probe"],
            },
        },
    )
    decision_service.create_decision(
        candidate_id=candidate.candidate_id,
        donor_id="donor-1",
        package_id="package-1",
        decision_kind="continue_trial",
        from_stage="trial",
        to_stage="trial",
        reason="Primary action verified.",
        verified_stage="primary_action_verified",
        provider_resolution_status="resolved",
        compatibility_status="compatible_native",
        metadata={
            "selected_adapter_action_id": "execute_task",
            "probe_result": {
                "probe_outcome": "succeeded",
                "probe_error_type": None,
                "probe_evidence_refs": ["ev-probe"],
            },
        },
    )

    app = FastAPI()
    app.include_router(runtime_center_router)
    app.state.state_query_service = RuntimeCenterStateQueryService(
        task_repository=SqliteTaskRepository(state_store),
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        runtime_frame_repository=SqliteRuntimeFrameRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        goal_repository=SqliteGoalRepository(state_store),
        work_context_repository=SqliteWorkContextRepository(state_store),
        decision_request_repository=SqliteDecisionRequestRepository(state_store),
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=decision_service,
    )
    client = TestClient(app)

    trials = client.get(
        "/runtime-center/capabilities/trials",
        params={"candidate_id": candidate.candidate_id},
    )
    decisions = client.get(
        "/runtime-center/capabilities/lifecycle-decisions",
        params={"candidate_id": candidate.candidate_id},
    )

    assert trials.status_code == 200
    assert trials.json()[0]["verified_stage"] == "primary_action_verified"
    assert trials.json()[0]["provider_resolution_status"] == "resolved"
    assert trials.json()[0]["compatibility_status"] == "compatible_native"
    assert trials.json()[0]["selected_adapter_action_id"] == "execute_task"
    assert trials.json()[0]["probe_outcome"] == "succeeded"
    assert trials.json()[0]["probe_evidence_refs"] == ["ev-probe"]

    assert decisions.status_code == 200
    assert decisions.json()[0]["verified_stage"] == "primary_action_verified"
    assert decisions.json()[0]["selected_adapter_action_id"] == "execute_task"
    assert decisions.json()[0]["probe_outcome"] == "succeeded"
