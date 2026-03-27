# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    AgentResponse,
)

from copaw.app.agent_runtime import create_agent_runtime_app


class FakeTurnExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[AgentRequest, dict[str, object]]] = []

    async def stream_request(self, request: AgentRequest, **kwargs):
        self.calls.append((request, kwargs))
        yield AgentResponse(id=request.id, session_id=request.session_id)


def _build_app(*, turn_executor: FakeTurnExecutor | None) -> tuple[FastAPI, FastAPI]:
    main_app = FastAPI()
    api_router = APIRouter(prefix="/api")

    @api_router.get("/agent/files")
    async def list_agent_files():
        return [{"name": "kept-by-main-api"}]

    main_app.include_router(api_router)
    if turn_executor is not None:
        main_app.state.turn_executor = turn_executor

    agent_runtime_app = create_agent_runtime_app()
    agent_runtime_app.state.parent_app = main_app
    main_app.mount("/api/agent", agent_runtime_app)
    return main_app, agent_runtime_app


def test_direct_agent_process_streams_kernel_events() -> None:
    turn_executor = FakeTurnExecutor()
    app, agent_runtime_app = _build_app(turn_executor=turn_executor)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/process",
            json={
                "id": "req-1",
                "session_id": "sess-1",
                "user_id": "user-1",
                "channel": "console",
                "input": [],
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"id":"req-1"' in response.text
    assert '"session_id":"sess-1"' in response.text
    assert len(turn_executor.calls) == 1
    request, kwargs = turn_executor.calls[0]
    assert request.session_id == "sess-1"
    assert request.user_id == "user-1"
    assert request.channel == "console"
    assert kwargs == {}
    assert agent_runtime_app.state._local_tasks == {}


def test_agent_runtime_mount_preserves_main_agent_routes() -> None:
    turn_executor = FakeTurnExecutor()
    app, _agent_runtime_app = _build_app(turn_executor=turn_executor)

    with TestClient(app) as client:
        files_response = client.get("/api/agent/files")
        health_response = client.get("/api/agent/health")
        root_response = client.get("/api/agent/")

    assert files_response.status_code == 200
    assert files_response.json() == [{"name": "kept-by-main-api"}]
    assert health_response.status_code == 200
    assert health_response.json()["runner"] == "ready"
    assert root_response.status_code == 200
    assert root_response.json()["endpoints"]["process"] == "/process"


def test_direct_agent_process_requires_turn_executor() -> None:
    app, _agent_runtime_app = _build_app(turn_executor=None)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/process",
            json={
                "id": "req-1",
                "session_id": "sess-1",
                "user_id": "user-1",
                "channel": "console",
                "input": [],
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Kernel turn executor is not initialized",
    }
