# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeMcpRegistryCatalog:
    def list_catalog(self, **_kwargs):
        raise AssertionError("MCP catalog is not used by the cooperative Phase 2 tests")

    def get_catalog_detail(self, *args, **kwargs):
        raise AssertionError("MCP catalog is not used by the cooperative Phase 2 tests")

    def materialize_install_plan(self, *args, **kwargs):
        raise AssertionError("MCP catalog is not used by the cooperative Phase 2 tests")


def build_runtime_app(tmp_path) -> FastAPI:
    from copaw.app.routers.capability_market import (
        router as capability_market_router,
    )
    from copaw.app.runtime_events import RuntimeEventBus
    from copaw.capabilities import CapabilityService
    from copaw.evidence import EvidenceLedger
    from copaw.environments import (
        EnvironmentRegistry,
        EnvironmentRepository,
        EnvironmentService,
        SessionMountRepository,
    )
    from copaw.kernel import KernelDispatcher, KernelTaskStore
    from copaw.state import SQLiteStateStore
    from copaw.state.repositories import (
        SqliteDecisionRequestRepository,
        SqliteRuntimeFrameRepository,
        SqliteTaskRepository,
        SqliteTaskRuntimeRepository,
    )

    app = FastAPI()
    app.include_router(capability_market_router)
    state_store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    environment_repository = EnvironmentRepository(state_store)
    session_mount_repository = SessionMountRepository(state_store)
    environment_registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_mount_repository,
    )
    environment_service = EnvironmentService(registry=environment_registry)
    environment_service.set_session_repository(session_mount_repository)
    runtime_event_bus = RuntimeEventBus()
    environment_service.set_runtime_event_bus(runtime_event_bus)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    capability_service = CapabilityService()
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        capability_service=capability_service,
        task_store=task_store,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    app.state.decision_request_repository = decision_request_repository
    app.state.state_store = state_store
    app.state.environment_service = environment_service
    app.state.runtime_event_bus = runtime_event_bus
    app.state.mcp_registry_catalog = FakeMcpRegistryCatalog()
    return app


@pytest.mark.parametrize(
    ("template_id", "default_capability_id"),
    [
        ("browser-companion", "system:browser_companion_runtime"),
        ("document-office-bridge", "system:document_bridge_runtime"),
        ("host-watchers", "system:host_watchers_runtime"),
        ("windows-app-adapters", "system:windows_app_adapter_runtime"),
    ],
)
def test_phase2_cooperative_template_detail_contracts(
    tmp_path,
    template_id: str,
    default_capability_id: str,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))

    response = client.get(f"/capability-market/install-templates/{template_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == template_id
    assert payload["install_kind"] == "builtin-runtime"
    assert payload["source_kind"] == "system"
    assert payload["default_capability_id"] == default_capability_id
    assert payload["manifest"]["capability_ids"] == [default_capability_id]
    assert payload["routes"]["detail"] == (
        f"/api/capability-market/install-templates/{template_id}"
    )
    assert payload["routes"]["install"] == (
        f"/api/capability-market/install-templates/{template_id}/install"
    )
    assert payload["routes"]["doctor"] == (
        f"/api/capability-market/install-templates/{template_id}/doctor"
    )
    assert payload["routes"]["example_run"] == (
        f"/api/capability-market/install-templates/{template_id}/example-run"
    )


def test_phase2_install_template_listing_includes_all_cooperative_families(
    tmp_path,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))

    response = client.get("/capability-market/install-templates")

    assert response.status_code == 200
    payload = {item["id"]: item for item in response.json()}
    assert payload["browser-companion"]["default_capability_id"] == (
        "system:browser_companion_runtime"
    )
    assert payload["document-office-bridge"]["default_capability_id"] == (
        "system:document_bridge_runtime"
    )
    assert payload["host-watchers"]["default_capability_id"] == (
        "system:host_watchers_runtime"
    )
    assert payload["windows-app-adapters"]["default_capability_id"] == (
        "system:windows_app_adapter_runtime"
    )


def test_phase2_host_watchers_doctor_example_and_install_contract(
    tmp_path,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))

    doctor = client.get("/capability-market/install-templates/host-watchers/doctor")
    example = client.post(
        "/capability-market/install-templates/host-watchers/example-run",
        json={},
    )
    installed = client.post(
        "/capability-market/install-templates/host-watchers/install",
        json={},
    )

    assert doctor.status_code == 200
    doctor_payload = doctor.json()
    assert doctor_payload["template_id"] == "host-watchers"

    assert example.status_code == 200
    example_payload = example.json()
    assert example_payload["template_id"] == "host-watchers"

    assert installed.status_code == 201
    install_payload = installed.json()
    assert install_payload["template_id"] == "host-watchers"
    assert install_payload["source_kind"] == "system"
    assert install_payload["assigned_capability_ids"] == [
        "system:host_watchers_runtime"
    ]
