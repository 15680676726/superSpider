# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.ollama_models import admin_router as ollama_admin_router
from copaw.app.routers.ollama_models import router as ollama_router


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(ollama_router)
    app.include_router(ollama_admin_router)
    return TestClient(app)


def test_ollama_admin_download_route_uses_canonical_provider_admin_service() -> None:
    calls: list[str] = []

    class _FakeProviderAdminService:
        async def add_ollama_model(self, *, name: str) -> None:
            calls.append(name)

    app = FastAPI()
    app.include_router(ollama_router)
    app.include_router(ollama_admin_router)
    app.state.provider_admin_service = _FakeProviderAdminService()
    client = TestClient(app)

    response = client.post(
        "/providers/admin/ollama-models/download",
        json={"name": "qwen3:latest"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "qwen3:latest"
    assert calls == ["qwen3:latest"]


def test_ollama_admin_write_route_rejects_missing_admin_surface() -> None:
    client = build_client()

    response = client.post(
        "/providers/admin/ollama-models/download",
        json={"name": "qwen3:latest"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "provider_admin_service is not attached to app.state"


def test_ollama_write_routes_are_not_exposed_on_read_surface() -> None:
    client = build_client()

    response = client.post(
        "/ollama-models/download",
        json={"name": "qwen3:latest"},
    )

    assert response.status_code == 404
