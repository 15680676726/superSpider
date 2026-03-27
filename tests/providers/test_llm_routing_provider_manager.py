# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest

from copaw.providers.provider_manager import ProviderManager


class _DummyChatModel:
    stream = True
    preferred_chat_model_class = object

    async def __call__(self, *args, **kwargs):
        del args, kwargs
        return SimpleNamespace(content="ok", usage={})


def test_provider_manager_get_active_chat_model_returns_routing_when_enabled(
    monkeypatch,
) -> None:
    routing_cfg = SimpleNamespace(
        enabled=True,
        mode="local_first",
        local=SimpleNamespace(provider_id="llamacpp", model="llama-local"),
        cloud=SimpleNamespace(provider_id="openai", model="gpt-5"),
    )
    monkeypatch.setattr(
        "copaw.config.load_config",
        lambda: SimpleNamespace(agents=SimpleNamespace(llm_routing=routing_cfg)),
    )

    manager = SimpleNamespace(build_chat_model_for_slot=lambda _slot: _DummyChatModel())
    monkeypatch.setattr(
        "copaw.providers.provider_manager.ProviderManager.get_instance",
        staticmethod(lambda: manager),
    )

    model = ProviderManager.get_active_chat_model()
    from copaw.agents.routing_chat_model import RoutingChatModel

    assert isinstance(model, RoutingChatModel)


def test_provider_manager_get_active_chat_model_rejects_mismatched_families(
    monkeypatch,
) -> None:
    routing_cfg = SimpleNamespace(
        enabled=True,
        mode="local_first",
        local=SimpleNamespace(provider_id="llamacpp", model="llama-local"),
        cloud=SimpleNamespace(provider_id="openai", model="gpt-5"),
    )
    monkeypatch.setattr(
        "copaw.config.load_config",
        lambda: SimpleNamespace(agents=SimpleNamespace(llm_routing=routing_cfg)),
    )

    class _LocalModel(_DummyChatModel):
        preferred_chat_model_class = object

    class _CloudModel(_DummyChatModel):
        preferred_chat_model_class = str

    calls = {"n": 0}

    def _build(_slot):
        calls["n"] += 1
        return _LocalModel() if calls["n"] == 1 else _CloudModel()

    manager = SimpleNamespace(build_chat_model_for_slot=_build)
    monkeypatch.setattr(
        "copaw.providers.provider_manager.ProviderManager.get_instance",
        staticmethod(lambda: manager),
    )

    with pytest.raises(ValueError, match="formatter family"):
        ProviderManager.get_active_chat_model()

