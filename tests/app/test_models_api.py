# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import copaw.providers.provider_manager as provider_manager_module
from copaw.app.routers.providers import router as providers_router
from copaw.providers.provider_manager import ModelSlotConfig, ProviderManager


@pytest.fixture
def isolated_secret_dir(monkeypatch, tmp_path: Path) -> Path:
    secret_dir = tmp_path / ".copaw.secret"
    monkeypatch.setattr(provider_manager_module, "SECRET_DIR", secret_dir)
    return secret_dir


def build_client(manager: ProviderManager) -> TestClient:
    app = FastAPI()
    app.include_router(providers_router)
    app.state.provider_manager = manager
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
        "/models/fallback",
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
        "/models/fallback",
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
    app.state.provider_manager = _BrittleManager()
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
