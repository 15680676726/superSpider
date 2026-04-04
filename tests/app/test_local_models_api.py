# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers import local_models as local_models_router_module
from copaw.app.routers.local_models import admin_router as local_models_admin_router
from copaw.app.routers.local_models import router as local_models_router


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(local_models_router)
    app.include_router(local_models_admin_router)
    return TestClient(app)


def test_delete_local_model_uses_provider_admin_service_for_catalog_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []

    class _FakeProviderAdminService:
        def refresh_local_model_catalog(self) -> None:
            events.append("refresh")

    monkeypatch.setattr(
        local_models_router_module,
        "_get_provider_admin_service_from_request",
        lambda request=None: _FakeProviderAdminService(),
    )
    monkeypatch.setattr(
        "copaw.local_models.delete_local_model",
        lambda model_id: events.append(("delete", model_id)),
    )
    client = build_client()

    response = client.delete("/providers/admin/local-models/qwen-local")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "model_id": "qwen-local"}
    assert events == [("delete", "qwen-local"), "refresh"]


def test_delete_local_model_prefers_injected_provider_admin_service_over_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []

    class _InjectedProviderAdminService:
        def refresh_local_model_catalog(self) -> None:
            events.append("refresh")

    monkeypatch.setattr(
        "copaw.local_models.delete_local_model",
        lambda model_id: events.append(("delete", model_id)),
    )

    app = FastAPI()
    app.include_router(local_models_router)
    app.include_router(local_models_admin_router)
    app.state.provider_admin_service = _InjectedProviderAdminService()
    client = TestClient(app)

    response = client.delete("/providers/admin/local-models/runtime-only")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "model_id": "runtime-only"}
    assert events == [("delete", "runtime-only"), "refresh"]


def test_delete_local_model_rejects_missing_provider_admin_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "copaw.local_models.delete_local_model",
        lambda model_id: model_id,
    )

    app = FastAPI()
    app.include_router(local_models_router)
    app.include_router(local_models_admin_router)
    client = TestClient(app)

    response = client.delete("/providers/admin/local-models/runtime-only")

    assert response.status_code == 500
    assert response.json()["detail"] == "provider_admin_service is not attached to app.state"


@pytest.mark.asyncio
async def test_background_download_uses_provider_admin_service_for_catalog_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statuses: list[tuple[str, str]] = []
    events: list[object] = []

    class _FakeProviderAdminService:
        def refresh_local_model_catalog(self) -> None:
            events.append("refresh")

    async def _fake_get_task(task_id: str):
        assert task_id == "task-1"
        return SimpleNamespace(status=local_models_router_module.DownloadTaskStatus.PENDING)

    async def _fake_update_status(task_id: str, status, **kwargs):
        _ = kwargs
        statuses.append((task_id, status.value))

    async def _fake_pop_background_task(task_id: str):
        assert task_id == "task-1"
        return None

    async def _fake_push_append(channel: str, message: str) -> None:
        events.append((channel, message))

    monkeypatch.setattr(
        local_models_router_module,
        "_get_provider_admin_service_from_request",
        lambda request=None: _FakeProviderAdminService(),
    )
    monkeypatch.setattr(local_models_router_module, "get_task", _fake_get_task)
    monkeypatch.setattr(
        local_models_router_module,
        "update_status",
        _fake_update_status,
    )
    monkeypatch.setattr(
        local_models_router_module,
        "_pop_background_task",
        _fake_pop_background_task,
    )
    monkeypatch.setattr(
        "copaw.app.console_push_store.append",
        _fake_push_append,
    )
    monkeypatch.setattr(
        "copaw.local_models.LocalModelManager.download_model_sync",
        lambda **kwargs: SimpleNamespace(
            id="qwen-local",
            repo_id=kwargs["repo_id"],
            filename=kwargs["filename"] or "model.gguf",
            backend=SimpleNamespace(value="llamacpp"),
            source=SimpleNamespace(value="huggingface"),
            file_size=1024,
            local_path="D:/models/qwen.gguf",
            display_name="Qwen Local",
        ),
    )

    await local_models_router_module._run_download_in_background(
        task_id="task-1",
        body=local_models_router_module.DownloadRequest(repo_id="Qwen/Qwen", filename=None),
        provider_admin_service=_FakeProviderAdminService(),
    )

    assert statuses == [
        ("task-1", local_models_router_module.DownloadTaskStatus.DOWNLOADING.value),
        ("task-1", local_models_router_module.DownloadTaskStatus.COMPLETED.value),
    ]
    assert events == [("console", "Model downloaded: Qwen Local"), "refresh"]


def test_local_model_write_routes_are_not_exposed_on_read_surface() -> None:
    client = build_client()

    response = client.delete("/local-models/runtime-only")

    assert response.status_code == 404
