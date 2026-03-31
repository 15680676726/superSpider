# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers import router as root_router


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(root_router)
    return app


def test_legacy_skill_and_mcp_routes_are_removed_from_runtime_surface() -> None:
    client = TestClient(build_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/skills" not in paths
    assert "/skills/available" not in paths
    assert "/mcp" not in paths
    assert "/mcp/{client_key}" not in paths


def test_legacy_skill_and_mcp_routes_return_404() -> None:
    client = TestClient(build_app())

    assert client.get("/skills").status_code == 404
    assert client.get("/skills/available").status_code == 404
    assert client.get("/mcp").status_code == 404
    assert client.get("/mcp/browser").status_code == 404


def test_retired_runtime_and_goal_frontdoors_are_removed_from_openapi() -> None:
    client = TestClient(build_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/runtime-center/chat/intake" not in paths
    assert "/runtime-center/chat/orchestrate" not in paths
    assert "/runtime-center/tasks/{task_id}/delegate" not in paths
    assert "/runtime-center/goals/{goal_id}" not in paths
    assert "/runtime-center/goals/{goal_id}/compile" not in paths
    assert "/runtime-center/goals/{goal_id}/dispatch" not in paths
    assert "/goals" not in paths
    assert "/goals/{goal_id}" not in paths
    assert "/goals/{goal_id}/compile" not in paths
    assert "/goals/{goal_id}/dispatch" not in paths
    assert "/goals/automation/dispatch-active" not in paths
    assert "/goals/{goal_id}/detail" in paths
    assert "/learning/patches/{patch_id}/approve" not in paths
    assert "/learning/patches/{patch_id}/reject" not in paths
    assert "/learning/patches/{patch_id}/apply" not in paths
    assert "/learning/patches/{patch_id}/rollback" not in paths


def test_retired_runtime_and_goal_frontdoors_return_404() -> None:
    client = TestClient(build_app())

    assert client.post("/runtime-center/chat/intake", json={"id": "req-intake"}).status_code == 404
    assert (
        client.post("/runtime-center/chat/orchestrate", json={"id": "req-orchestrate"}).status_code
        == 404
    )
    assert (
        client.post(
            "/runtime-center/tasks/task-1/delegate",
            json={
                "title": "Worker follow-up",
                "owner_agent_id": "worker",
                "prompt_text": "Review the evidence and draft the next step.",
            },
        ).status_code
        == 404
    )
    assert (
        client.get("/runtime-center/goals/goal-1").status_code
        == 404
    )
    assert (
        client.post(
            "/runtime-center/goals/goal-1/compile",
            json={"context": {"source": "runtime-center"}},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/runtime-center/goals/goal-1/dispatch",
            json={"trigger": "manual", "source": "runtime-center"},
        ).status_code
        == 404
    )
    assert client.get("/goals").status_code == 404
    assert client.post("/goals", json={"title": "Retired frontdoor"}).status_code == 404
    assert client.get("/goals/goal-1").status_code == 404
    assert client.patch("/goals/goal-1", json={"title": "Retired frontdoor"}).status_code == 404
    assert client.delete("/goals/goal-1").status_code == 404
    assert client.post("/goals/goal-1/compile", json={"context": {"source": "legacy"}}).status_code == 404
    assert client.get("/goals/goal-1/detail").status_code == 503
    assert client.post("/goals/goal-1/dispatch", json={"trigger": "manual"}).status_code == 404
    assert client.post("/goals/automation/dispatch-active", json={"source": "runtime-center"}).status_code == 404
    assert client.post("/learning/patches/patch-1/approve", json={"actor": "ops"}).status_code == 404
    assert client.post("/learning/patches/patch-1/reject", json={"actor": "ops"}).status_code == 404
    assert client.post("/learning/patches/patch-1/apply", json={"actor": "ops"}).status_code == 404
    assert client.post("/learning/patches/patch-1/rollback", json={"actor": "ops"}).status_code == 404


def test_goal_detail_stays_the_only_public_goals_frontdoor_method() -> None:
    client = TestClient(build_app())

    openapi_response = client.get("/openapi.json")

    assert openapi_response.status_code == 200
    detail_methods = openapi_response.json()["paths"]["/goals/{goal_id}/detail"].keys()
    assert set(detail_methods) == {"get"}

    assert client.get("/goals/goal-1/detail").status_code == 503
    assert client.post("/goals/goal-1/detail", json={"title": "forbidden"}).status_code == 405
    assert client.patch("/goals/goal-1/detail", json={"title": "forbidden"}).status_code == 405
    assert client.delete("/goals/goal-1/detail").status_code == 405
