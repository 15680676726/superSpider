# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.fixed_sops import router as fixed_sops_router
from copaw.evidence import EvidenceLedger
from copaw.sop_kernel import FixedSopService
from copaw.state import SQLiteStateStore, WorkflowRunRecord
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteWorkflowRunRepository,
)


class _FakeEnvironmentService:
    def __init__(self, detail: dict[str, object]) -> None:
        self._detail = detail

    def get_session_detail(
        self,
        session_mount_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        if session_mount_id != "session-desktop-1":
            return None
        return dict(self._detail)

    def get_environment_detail(
        self,
        env_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        if env_id != "env-desktop-1":
            return None
        return dict(self._detail)


def _host_detail(
    *,
    recommended_scheduler_action: str,
    requires_human_return: bool = False,
    legal_recovery_path: str = "resume",
    legal_recovery_reason: str | None = None,
    host_blocker_family: str | None = None,
    host_blocker_response: str | None = None,
) -> dict[str, object]:
    summary = {
        "host_companion_status": (
            "restorable" if recommended_scheduler_action == "continue" else "attached"
        ),
        "seat_owner_ref": "ops-agent",
        "active_app_family_keys": ["office_document"],
        "blocked_surface_refs": [],
        "blocked_surface_count": 0,
        "legal_recovery_mode": (
            "resume-environment" if legal_recovery_path == "resume" else legal_recovery_path
        ),
        "recommended_scheduler_action": recommended_scheduler_action,
        "contention_severity": "clear" if recommended_scheduler_action == "continue" else "blocked",
        "contention_reason": legal_recovery_reason or "host coordination is clear",
        "requires_human_return": requires_human_return,
    }
    return {
        "environment_id": "env-desktop-1",
        "session_mount_id": "session-desktop-1",
        "host_companion_session": {
            "session_mount_id": "session-desktop-1",
            "environment_id": "env-desktop-1",
            "continuity_status": (
                "restorable" if recommended_scheduler_action == "continue" else "attached"
            ),
            "continuity_source": "live-handle",
            "locality": {
                "same_host": True,
                "same_process": False,
                "startup_recovery_required": requires_human_return,
            },
        },
        "host_twin": {
            "projection_kind": "host_twin_projection",
            "is_projection": True,
            "is_truth_store": False,
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
            "continuity": {
                "status": "attached",
                "valid": True,
                "continuity_source": "live-handle",
                "requires_human_return": requires_human_return,
            },
            "legal_recovery": {
                "path": legal_recovery_path,
                "reason": legal_recovery_reason,
            },
            "latest_blocking_event": {
                "event_family": host_blocker_family,
                "recommended_runtime_response": host_blocker_response,
            },
            "execution_mutation_ready": {
                "desktop_app": recommended_scheduler_action == "continue",
                "browser": False,
                "file_docs": False,
            },
            "app_family_twins": {
                "office_document": {
                    "active": True,
                    "family_kind": "office_document",
                    "surface_ref": "window:excel:main",
                    "contract_status": (
                        "verified-writer" if recommended_scheduler_action == "continue" else "blocked"
                    ),
                    "family_scope_ref": "app:excel",
                    "writer_lock_scope": "workbook:monthly-report",
                },
            },
            "coordination": {
                "seat_owner_ref": "ops-agent",
                "workspace_owner_ref": "ops-agent",
                "writer_owner_ref": (
                    "ops-agent" if recommended_scheduler_action == "continue" else None
                ),
                "candidate_seat_refs": ["env-desktop-1"],
                "selected_seat_ref": "env-desktop-1",
                "seat_selection_policy": "sticky-active-seat",
                "contention_forecast": {
                    "severity": (
                        "clear" if recommended_scheduler_action == "continue" else "blocked"
                    ),
                    "reason": (
                        "desktop writer path is clear"
                        if recommended_scheduler_action == "continue"
                        else "human handoff is still active"
                    ),
                },
                "recommended_scheduler_action": recommended_scheduler_action,
                "expected_release_at": None,
            },
            "scheduler_inputs": {
                "active_blocker_family": host_blocker_family,
                "requires_human_return": requires_human_return,
                "recommended_scheduler_action": recommended_scheduler_action,
            },
            "host_companion_session": {
                "session_mount_id": "session-desktop-1",
                "environment_id": "env-desktop-1",
                "continuity_status": (
                    "restorable" if recommended_scheduler_action == "continue" else "attached"
                ),
                "continuity_source": "live-handle",
                "locality": {
                    "same_host": True,
                    "same_process": False,
                    "startup_recovery_required": requires_human_return,
                },
            },
            "host_twin_summary": summary,
        },
    }


def _create_host_binding(client: TestClient) -> str:
    response = client.post(
        "/fixed-sops/bindings",
        json={
            "template_id": "fixed-sop-http-routine-bridge",
            "binding_name": f"Host Aware SOP {uuid.uuid4()}",
            "status": "active",
            "metadata": {
                "environment_id": "env-desktop-1",
                "session_mount_id": "session-desktop-1",
                "host_requirement": {
                    "surface_kind": "desktop",
                    "app_family": "office_document",
                    "mutating": True,
                },
            },
        },
    )
    assert response.status_code == 201
    return response.json()["binding"]["binding_id"]


def _build_app(tmp_path, *, environment_service=None) -> FastAPI:
    app = FastAPI()
    app.include_router(fixed_sops_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    template_repository = SqliteFixedSopTemplateRepository(state_store)
    binding_repository = SqliteFixedSopBindingRepository(state_store)
    workflow_run_repository = SqliteWorkflowRunRepository(state_store)
    agent_report_repository = SqliteAgentReportRepository(state_store)
    workflow_run_repository.upsert_run(
        WorkflowRunRecord(
            run_id="workflow-run-1",
            template_id="workflow-template-a",
            title="Workflow Run A",
            status="draft",
        ),
    )
    app.state.fixed_sop_service = FixedSopService(
        template_repository=template_repository,
        binding_repository=binding_repository,
        workflow_run_repository=workflow_run_repository,
        agent_report_repository=agent_report_repository,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
    )
    return app


def test_list_fixed_sop_templates(tmp_path) -> None:
    client = TestClient(_build_app(tmp_path))

    response = client.get("/fixed-sops/templates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["items"][0]["template"]["template_id"]


def test_old_sop_adapters_route_is_gone(tmp_path) -> None:
    client = TestClient(_build_app(tmp_path))

    response = client.get("/sop-adapters/templates")

    assert response.status_code in {404, 410}


def test_legacy_sop_adapters_router_module_is_removed() -> None:
    assert importlib.util.find_spec("copaw.app.routers.sop_adapters") is None


def test_fixed_sop_doctor_and_run_api_surface_host_preflight_blockers(tmp_path) -> None:
    client = TestClient(
        _build_app(
            tmp_path,
            environment_service=_FakeEnvironmentService(
                _host_detail(recommended_scheduler_action="handoff"),
            ),
        )
    )
    binding_id = _create_host_binding(client)

    doctor = client.post(f"/fixed-sops/bindings/{binding_id}/doctor")

    assert doctor.status_code == 200
    doctor_payload = doctor.json()
    assert doctor_payload["status"] == "blocked"
    assert doctor_payload["environment_id"] == "env-desktop-1"
    assert doctor_payload["session_mount_id"] == "session-desktop-1"
    assert doctor_payload["host_requirement"]["app_family"] == "office_document"
    assert doctor_payload["host_preflight"]["coordination"][
        "recommended_scheduler_action"
    ] == "handoff"
    assert doctor_payload["host_preflight"]["host_twin_summary"]["host_companion_status"] == "attached"

    run = client.post(
        f"/fixed-sops/bindings/{binding_id}/run",
        json={
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
        },
    )

    assert run.status_code == 400
    assert "host preflight" in run.json()["detail"]


def test_fixed_sop_run_detail_exposes_host_preflight_snapshot(tmp_path) -> None:
    client = TestClient(
        _build_app(
            tmp_path,
            environment_service=_FakeEnvironmentService(
                _host_detail(recommended_scheduler_action="continue"),
            ),
        )
    )
    binding_id = _create_host_binding(client)

    run = client.post(
        f"/fixed-sops/bindings/{binding_id}/run",
        json={
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
        },
    )

    assert run.status_code == 200
    workflow_run_id = run.json()["workflow_run_id"]
    detail = client.get(f"/fixed-sops/runs/{workflow_run_id}")

    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["environment_id"] == "env-desktop-1"
    assert detail_payload["session_mount_id"] == "session-desktop-1"
    assert detail_payload["host_requirement"]["app_family"] == "office_document"
    assert detail_payload["host_preflight"]["coordination"][
        "recommended_scheduler_action"
    ] == "continue"
    assert detail_payload["host_preflight"]["host_twin_summary"]["host_companion_status"] == "restorable"
    assert detail_payload["host_preflight"]["host_twin_summary"]["active_app_family_keys"]
    assert detail_payload["host_preflight"]["host_twin_summary"]["seat_owner_ref"] == "ops-agent"
    assert detail_payload["host_preflight"]["host_twin_summary"]["blocked_surface_count"] == 0
    assert detail_payload["host_preflight"]["host_twin_summary"]["legal_recovery_mode"] == (
        "resume-environment"
    )
    assert detail_payload["host_preflight"]["host_twin_summary"][
        "recommended_scheduler_action"
    ] == "continue"


def test_fixed_sop_doctor_and_run_api_block_handoff_only_recovery_state(tmp_path) -> None:
    client = TestClient(
        _build_app(
            tmp_path,
            environment_service=_FakeEnvironmentService(
                _host_detail(
                    recommended_scheduler_action="continue",
                    requires_human_return=True,
                    legal_recovery_path="handoff",
                    legal_recovery_reason=(
                        "Manual login must be completed before control can return."
                    ),
                ),
            ),
        )
    )
    binding_id = _create_host_binding(client)

    doctor = client.post(f"/fixed-sops/bindings/{binding_id}/doctor")

    assert doctor.status_code == 200
    doctor_payload = doctor.json()
    assert doctor_payload["status"] == "blocked"
    host_check = next(item for item in doctor_payload["checks"] if item["key"] == "host-preflight")
    assert "manual login" in host_check["message"].lower() or "control can return" in host_check[
        "message"
    ].lower()
    assert doctor_payload["host_preflight"]["host_twin_summary"]["host_companion_status"] == "attached"

    run = client.post(
        f"/fixed-sops/bindings/{binding_id}/run",
        json={
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
        },
    )

    assert run.status_code == 400
    assert "host preflight" in run.json()["detail"]


def test_fixed_sop_api_ignores_stale_handoff_metadata_when_canonical_summary_is_proceed(
    tmp_path,
) -> None:
    detail = _host_detail(
        recommended_scheduler_action="proceed",
        requires_human_return=True,
        legal_recovery_path="handoff",
        legal_recovery_reason="stale handoff metadata should not block canonical proceed",
        host_blocker_family="modal-uac-login",
        host_blocker_response="handoff",
    )
    detail["host_twin"]["host_twin_summary"] = {
        "active_app_family_keys": ["office_document"],
        "seat_owner_ref": "ops-agent",
        "blocked_surface_count": 0,
        "legal_recovery_mode": "resume-environment",
        "recommended_scheduler_action": "proceed",
    }
    client = TestClient(
        _build_app(
            tmp_path,
            environment_service=_FakeEnvironmentService(detail),
        )
    )
    binding_id = _create_host_binding(client)

    doctor = client.post(f"/fixed-sops/bindings/{binding_id}/doctor")

    assert doctor.status_code == 200
    doctor_payload = doctor.json()
    assert doctor_payload["status"] == "ready"
    assert doctor_payload["host_preflight"]["host_twin_summary"][
        "recommended_scheduler_action"
    ] == "proceed"
    assert doctor_payload["host_preflight"]["host_twin_summary"][
        "legal_recovery_mode"
    ] == "resume-environment"

    run = client.post(
        f"/fixed-sops/bindings/{binding_id}/run",
        json={
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
        },
    )

    assert run.status_code == 200
