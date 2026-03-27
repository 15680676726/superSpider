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
