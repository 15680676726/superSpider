# -*- coding: utf-8 -*-
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.capabilities import CapabilityService
from copaw.capabilities.sources.external_packages import list_external_package_capabilities
from copaw.config.config import Config, ExternalCapabilityPackageConfig
from copaw.state import ExternalCapabilityRuntimeService, SQLiteStateStore
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteExternalCapabilityRuntimeRepository,
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)


class _StaticCapabilityRegistry:
    def __init__(self, mounts) -> None:
        self._mounts = list(mounts)

    def list_capabilities(self):
        return [mount.model_copy(deep=True) for mount in self._mounts]


def _build_runtime_center_app(tmp_path) -> tuple[TestClient, ExternalCapabilityRuntimeService]:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repository = SqliteExternalCapabilityRuntimeRepository(state_store)
    runtime_service = ExternalCapabilityRuntimeService(repository=runtime_repository)
    query_service = RuntimeCenterStateQueryService(
        task_repository=SqliteTaskRepository(state_store),
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        runtime_frame_repository=SqliteRuntimeFrameRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        goal_repository=SqliteGoalRepository(state_store),
        work_context_repository=SqliteWorkContextRepository(state_store),
        decision_request_repository=SqliteDecisionRequestRepository(state_store),
        external_runtime_service=runtime_service,
    )
    config = Config(
        external_capability_packages={
            "runtime:flask": ExternalCapabilityPackageConfig(
                capability_id="runtime:flask",
                name="flask",
                summary="Flask runtime component",
                kind="runtime-component",
                source_kind="runtime",
                source_url="https://github.com/pallets/flask",
                package_ref="git+https://github.com/pallets/flask.git",
                package_kind="git-repo",
                enabled=True,
                execute_command="python -m flask run",
                healthcheck_command="python -m flask --version",
                runtime_kind="service",
                supported_actions=[
                    "describe",
                    "start",
                    "healthcheck",
                    "stop",
                    "restart",
                ],
                scope_policy="session",
                ready_probe_kind="command",
                ready_probe_config={"command": "python -m flask --version"},
                stop_strategy="terminate",
                startup_entry_ref="module:flask",
                environment_requirements=["process", "network"],
                evidence_contract=["shell-command", "runtime-event"],
            ),
        },
    )
    with patch(
        "copaw.capabilities.sources.external_packages.load_config",
        return_value=config,
    ):
        mounts = list_external_package_capabilities()
    capability_service = CapabilityService(
        registry=_StaticCapabilityRegistry(mounts),
        state_store=state_store,
        external_runtime_service=runtime_service,
        load_config_fn=lambda: config,
        save_config_fn=lambda updated: None,
    )
    app = FastAPI()
    app.include_router(runtime_center_router)
    app.state.state_query_service = query_service
    app.state.capability_service = capability_service
    return TestClient(app), runtime_service


def test_runtime_center_lists_external_runtimes(tmp_path) -> None:
    client, runtime_service = _build_runtime_center_app(tmp_path)
    runtime = runtime_service.create_or_reuse_service_runtime(
        capability_id="runtime:flask",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="python -m flask run",
    )
    runtime_service.mark_runtime_ready(runtime.runtime_id, process_id=12345)

    response = client.get("/runtime-center/external-runtimes")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["runtime_id"] == runtime.runtime_id
    assert payload[0]["capability_id"] == "runtime:flask"
    assert payload[0]["status"] == "ready"


def test_runtime_center_returns_external_runtime_detail(tmp_path) -> None:
    client, runtime_service = _build_runtime_center_app(tmp_path)
    runtime = runtime_service.create_or_reuse_service_runtime(
        capability_id="runtime:flask",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="python -m flask run",
    )

    response = client.get(f"/runtime-center/external-runtimes/{runtime.runtime_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"]["runtime_id"] == runtime.runtime_id
    assert payload["runtime"]["capability_id"] == "runtime:flask"


def test_runtime_center_start_action_omits_null_runtime_id(tmp_path, monkeypatch) -> None:
    client, _ = _build_runtime_center_app(tmp_path)
    captured: dict[str, object] = {}

    async def _fake_execute_task(task) -> dict[str, object]:
        captured.update(dict(task.payload or {}))
        return {
            "success": True,
            "output": dict(task.payload or {}),
        }

    monkeypatch.setattr(client.app.state.capability_service, "execute_task", _fake_execute_task)

    response = client.post(
        "/runtime-center/external-runtimes/actions",
        json={
            "capability_id": "runtime:flask",
            "action": "start",
            "session_mount_id": "session-1",
        },
    )

    assert response.status_code == 200
    assert "runtime_id" not in captured
    assert response.json()["output"]["action"] == "start"


def test_runtime_center_stop_action_omits_start_only_fields(tmp_path, monkeypatch) -> None:
    client, _ = _build_runtime_center_app(tmp_path)
    captured: dict[str, object] = {}

    async def _fake_execute_task(task) -> dict[str, object]:
        captured.update(dict(task.payload or {}))
        return {
            "success": True,
            "output": dict(task.payload or {}),
        }

    monkeypatch.setattr(client.app.state.capability_service, "execute_task", _fake_execute_task)

    response = client.post(
        "/runtime-center/external-runtimes/actions",
        json={
            "capability_id": "runtime:flask",
            "action": "stop",
            "runtime_id": "runtime-123",
            "session_mount_id": "session-1",
        },
    )

    assert response.status_code == 200
    assert captured["runtime_id"] == "runtime-123"
    assert "args" not in captured
    assert "retention_policy" not in captured
    assert "port_override" not in captured
    assert "health_path_override" not in captured
