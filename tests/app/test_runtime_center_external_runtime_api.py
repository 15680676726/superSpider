# -*- coding: utf-8 -*-
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.capabilities import CapabilityMount, CapabilityService
from copaw.capabilities.sources.external_packages import list_external_package_capabilities
from copaw.config.config import Config, ExternalCapabilityPackageConfig
from copaw.kernel import KernelResult
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
    execute_calls: list[str] = []

    class _Dispatcher:
        def submit(self, task):
            captured["task"] = task
            return KernelResult(
                task_id=task.id,
                trace_id=task.trace_id,
                success=True,
                phase="executing",
                summary="admitted",
            )

        async def execute_task(self, task_id: str):
            execute_calls.append(task_id)
            task = captured["task"]
            return KernelResult(
                task_id=task_id,
                trace_id=task.trace_id,
                success=True,
                phase="completed",
                summary="started",
                output=dict(task.payload or {}),
            )

    client.app.state.kernel_dispatcher = _Dispatcher()

    async def _unexpected_execute_task(task) -> dict[str, object]:
        raise AssertionError("route should go through kernel dispatcher admission")

    monkeypatch.setattr(
        client.app.state.capability_service,
        "execute_task",
        _unexpected_execute_task,
    )

    response = client.post(
        "/runtime-center/external-runtimes/actions",
        json={
            "capability_id": "runtime:flask",
            "action": "start",
            "session_mount_id": "session-1",
        },
    )

    assert response.status_code == 200
    task = captured["task"]
    assert "runtime_id" not in task.payload
    assert task.capability_ref == "runtime:flask"
    assert task.risk_level == "guarded"
    assert execute_calls == [task.id]
    assert response.json()["phase"] == "completed"
    assert response.json()["output"]["action"] == "start"


def test_runtime_center_stop_action_omits_start_only_fields(tmp_path, monkeypatch) -> None:
    client, _ = _build_runtime_center_app(tmp_path)
    captured: dict[str, object] = {}
    execute_calls: list[str] = []

    class _Dispatcher:
        def submit(self, task):
            captured["task"] = task
            return KernelResult(
                task_id=task.id,
                trace_id=task.trace_id,
                success=False,
                phase="waiting-confirm",
                summary="needs confirmation",
                decision_request_id="decision-runtime-1",
            )

        async def execute_task(self, task_id: str):
            execute_calls.append(task_id)
            raise AssertionError("waiting-confirm tasks must not execute immediately")

    client.app.state.kernel_dispatcher = _Dispatcher()

    async def _unexpected_execute_task(task) -> dict[str, object]:
        raise AssertionError("route should go through kernel dispatcher admission")

    monkeypatch.setattr(
        client.app.state.capability_service,
        "execute_task",
        _unexpected_execute_task,
    )

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
    task = captured["task"]
    assert task.payload["runtime_id"] == "runtime-123"
    assert task.risk_level == "guarded"
    assert "args" not in task.payload
    assert "retention_policy" not in task.payload
    assert "port_override" not in task.payload
    assert "health_path_override" not in task.payload
    assert execute_calls == []
    assert response.json()["phase"] == "waiting-confirm"


def test_runtime_center_action_route_passes_mcp_tool_execution_fields(tmp_path) -> None:
    captured: dict[str, object] = {}

    capability_service = CapabilityService(
        registry=_StaticCapabilityRegistry(
            [
                CapabilityMount(
                    id="mcp:desktop_windows",
                    name="desktop_windows",
                    summary="Windows desktop MCP adapter",
                    kind="remote-mcp",
                    source_kind="mcp",
                    risk_level="guarded",
                    environment_requirements=["desktop"],
                    evidence_contract=["call-record"],
                    role_access_policy=["all"],
                    enabled=True,
                ),
            ]
        ),
    )

    class _Dispatcher:
        def submit(self, task):
            captured["task"] = task
            return KernelResult(
                task_id=task.id,
                trace_id=task.trace_id,
                success=True,
                phase="executing",
                summary="admitted",
            )

        async def execute_task(self, task_id: str):
            task = captured["task"]
            return KernelResult(
                task_id=task_id,
                trace_id=task.trace_id,
                success=True,
                phase="completed",
                summary="executed",
                output=dict(task.payload or {}),
            )

    app = FastAPI()
    app.include_router(runtime_center_router)
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = _Dispatcher()
    client = TestClient(app)

    response = client.post(
        "/runtime-center/external-runtimes/actions",
        json={
            "capability_id": "mcp:desktop_windows",
            "action": "run",
            "tool_name": "get_foreground_window",
            "tool_args": {"include_process": True},
            "scope_ref": "assignment:mcp-live-1",
            "mcp_scope_overlay": {
                "scope_ref": "assignment:mcp-live-1",
                "overlay_mode": "additive",
            },
        },
    )

    assert response.status_code == 200
    task = captured["task"]
    assert task.capability_ref == "mcp:desktop_windows"
    assert task.payload["tool_name"] == "get_foreground_window"
    assert task.payload["tool_args"] == {"include_process": True}
    assert task.payload["scope_ref"] == "assignment:mcp-live-1"
    assert task.payload["mcp_scope_overlay"] == {
        "scope_ref": "assignment:mcp-live-1",
        "overlay_mode": "additive",
    }
