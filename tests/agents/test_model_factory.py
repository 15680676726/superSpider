# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.agents import model_factory


def test_create_runtime_chat_model_uses_runtime_provider_facade(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(
        model_factory,
        "get_runtime_provider_facade",
        lambda provider_manager=None: SimpleNamespace(
            get_active_chat_model=lambda: sentinel,
        ),
    )

    assert model_factory.create_runtime_chat_model() is sentinel


def test_describe_runtime_model_surface_uses_runtime_provider_facade(monkeypatch) -> None:
    slot = SimpleNamespace(provider_id="openai", model="gpt-5.2")
    provider = SimpleNamespace(
        base_url="https://api.openai.com/v1",
        chat_model="gpt-5.2",
        is_local=False,
        require_api_key=True,
        api_key="secret-key",
    )
    runtime_provider = SimpleNamespace(
        get_active_model=lambda: slot,
        get_fallback_config=lambda: SimpleNamespace(enabled=False),
        get_fallback_slots=lambda: [],
        get_provider=lambda provider_id: provider if provider_id == "openai" else None,
    )
    monkeypatch.setattr(
        model_factory,
        "get_runtime_provider_facade",
        lambda provider_manager=None: runtime_provider,
    )
    monkeypatch.setattr(
        model_factory,
        "load_config",
        lambda: SimpleNamespace(
            agents=SimpleNamespace(
                llm_routing=SimpleNamespace(enabled=False),
            ),
        ),
    )

    payload = model_factory.describe_runtime_model_surface()

    assert payload["kind"] == "runtime-fallback"
    assert payload["active"]["provider_id"] == "openai"
    assert payload["active"]["model"] == "gpt-5.2"
    assert payload["active"]["provider"]["provider_missing"] is False
