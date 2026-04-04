# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import copaw.providers.provider_manager as provider_manager_module
from copaw.app.routers.providers import admin_router as providers_admin_router
from copaw.app.routers.providers import router as providers_router
from copaw.providers.provider_admin_service import ProviderAdminService
from copaw.providers.provider import ProviderInfo
from copaw.providers.provider_manager import ModelSlotConfig, ProviderManager
from copaw.providers.runtime_provider_facade import get_runtime_provider_facade


@pytest.fixture
def isolated_secret_dir(monkeypatch, tmp_path: Path) -> Path:
    secret_dir = tmp_path / ".copaw.secret"
    monkeypatch.setattr(provider_manager_module, "SECRET_DIR", secret_dir)
    return secret_dir


def build_client(manager: ProviderManager) -> TestClient:
    app = FastAPI()
    app.include_router(providers_router)
    app.include_router(providers_admin_router)
    app.state.runtime_provider = get_runtime_provider_facade(
        provider_manager=manager,
    )
    app.state.provider_admin_service = ProviderAdminService(manager)
    return TestClient(app)


def test_get_active_models_exposes_fallback_resolution(
    isolated_secret_dir: Path,
) -> None:
    manager = ProviderManager()
    manager.update_provider("openai", {"api_key": ""})
    manager.update_provider("dashscope", {"api_key": "sk-fallback"})
    manager.active_model = ModelSlotConfig(provider_id="openai", model="gpt-5")
    manager.set_fallback_config(
        enabled=True,
        candidates=[
            ModelSlotConfig(provider_id="dashscope", model="qwen3-max"),
        ],
    )
    client = build_client(manager)

    response = client.get("/models/active")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_llm"] == {
        "provider_id": "openai",
        "model": "gpt-5",
    }
    assert payload["resolved_llm"] == {
        "provider_id": "dashscope",
        "model": "qwen3-max",
    }
    assert payload["fallback_enabled"] is True
    assert payload["fallback_chain"] == [
        {
            "provider_id": "dashscope",
            "model": "qwen3-max",
        },
    ]
    assert payload["fallback_applied"] is True
    assert "using fallback slot dashscope/qwen3-max" in payload["resolution_reason"]
    assert "openai/gpt-5: api key missing" in payload["unavailable_candidates"]


def test_provider_fallback_api_round_trips_config(
    isolated_secret_dir: Path,
) -> None:
    manager = ProviderManager()
    client = build_client(manager)

    initial = client.get("/models/fallback")

    assert initial.status_code == 200
    assert initial.json() == {"enabled": True, "candidates": []}

    updated = client.put(
        "/providers/admin/fallback",
        json={
            "enabled": True,
            "candidates": [
                {"provider_id": "openai", "model": "gpt-5"},
                {"provider_id": "dashscope", "model": "qwen3-max"},
            ],
        },
    )

    assert updated.status_code == 200
    assert updated.json() == {
        "enabled": True,
        "candidates": [
            {"provider_id": "openai", "model": "gpt-5"},
            {"provider_id": "dashscope", "model": "qwen3-max"},
        ],
    }

    fetched = client.get("/models/fallback")

    assert fetched.status_code == 200
    assert fetched.json() == updated.json()
    assert client.put("/models/fallback", json=updated.json()).status_code == 405


@pytest.mark.parametrize(
    ("candidate", "expected_detail"),
    [
        (
            {"provider_id": "missing", "model": "gpt-5"},
            "Fallback provider 'missing' not found.",
        ),
        (
            {"provider_id": "openai", "model": "missing-model"},
            "Fallback model 'missing-model' not found in provider 'openai'.",
        ),
    ],
)
def test_provider_fallback_api_rejects_invalid_candidates(
    isolated_secret_dir: Path,
    candidate: dict[str, str],
    expected_detail: str,
) -> None:
    manager = ProviderManager()
    client = build_client(manager)

    response = client.put(
        "/providers/admin/fallback",
        json={
            "enabled": True,
            "candidates": [candidate],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail


def test_provider_test_route_avoids_python_deepcopy_for_provider_clones() -> None:
    class _BrittleProvider:
        def __init__(self) -> None:
            self.api_key = ""
            self.base_url = ""

        def __getattr__(self, name: str):
            raise KeyError(name)

        def model_copy(self, *, deep: bool = False):
            _ = deep
            clone = _BrittleProvider()
            clone.api_key = self.api_key
            clone.base_url = self.base_url
            return clone

        async def check_connection(self, timeout: float = 5) -> bool:
            _ = timeout
            return True

    class _BrittleManager:
        def get_provider(self, provider_id: str):
            assert provider_id == "brittle"
            return _BrittleProvider()

    app = FastAPI()
    app.include_router(providers_router)
    app.state.runtime_provider = _BrittleManager()
    client = TestClient(app)

    response = client.post(
        "/models/brittle/test",
        json={"api_key": "override", "base_url": "https://example.test"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Connection successful",
    }


def test_provider_admin_config_route_uses_canonical_service() -> None:
    calls: list[tuple[str, dict[str, str | None]]] = []

    class _FakeProviderAdminService:
        async def configure_provider(
            self,
            provider_id: str,
            *,
            api_key: str | None,
            base_url: str | None,
            chat_model: str | None,
        ) -> ProviderInfo:
            calls.append(
                (
                    provider_id,
                    {
                        "api_key": api_key,
                        "base_url": base_url,
                        "chat_model": chat_model,
                    },
                ),
            )
            return ProviderInfo(
                id=provider_id,
                name="OpenAI",
                base_url=base_url or "",
                api_key=api_key or "",
                chat_model=chat_model or "OpenAIChatModel",
            )

    app = FastAPI()
    app.include_router(providers_admin_router)
    app.state.provider_admin_service = _FakeProviderAdminService()
    client = TestClient(app)

    response = client.put(
        "/providers/admin/openai/config",
        json={
            "api_key": "sk-test",
            "base_url": "https://example.test/v1",
            "chat_model": "OpenAIChatModel",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "openai"
    assert calls == [
        (
            "openai",
            {
                "api_key": "sk-test",
                "base_url": "https://example.test/v1",
                "chat_model": "OpenAIChatModel",
            },
        ),
    ]


def test_provider_admin_route_rejects_missing_admin_surface_instead_of_singleton_fallback(
) -> None:
    app = FastAPI()
    app.include_router(providers_admin_router)
    client = TestClient(app)

    response = client.put(
        "/providers/admin/openai/config",
        json={"api_key": "sk-test"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "provider admin surface is not attached to app.state"


def test_list_providers_reads_from_runtime_provider_without_provider_manager_fallback() -> None:
    class _RuntimeProviderOnly:
        async def list_provider_info(self):
            return [
                ProviderInfo(
                    id="runtime-only",
                    name="Runtime Only",
                    base_url="",
                    api_key="",
                    chat_model="OpenAIChatModel",
                ),
            ]

    app = FastAPI()
    app.include_router(providers_router)
    app.state.runtime_provider = _RuntimeProviderOnly()
    client = TestClient(app)

    response = client.get("/models")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "runtime-only",
            "name": "Runtime Only",
            "base_url": "",
            "api_key": "",
            "chat_model": "OpenAIChatModel",
            "models": [],
            "extra_models": [],
            "is_local": False,
            "freeze_url": False,
            "require_api_key": True,
            "is_custom": False,
            "api_key_prefix": "",
        },
    ]
