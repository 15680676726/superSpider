# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest

from copaw.agents.routing_chat_model import RoutingChatModel, RoutingEndpoint
from copaw.providers.provider_manager import ProviderManager


class _DummyChatModel:
    stream = True
    preferred_chat_model_class = object

    async def __call__(self, *args, **kwargs):
        del args, kwargs
        return SimpleNamespace(content="ok", usage={})


class _ModeAwareChatModel:
    preferred_chat_model_class = object

    def __init__(self, label: str) -> None:
        self.label = label
        self.stream = True
        self.stream_history: list[bool] = []

    async def __call__(self, *args, **kwargs):
        del args, kwargs
        self.stream_history.append(bool(self.stream))
        if not self.stream:
            return SimpleNamespace(content=f"{self.label}-final", usage={})

        async def _stream():
            yield SimpleNamespace(content=f"{self.label}-stream", usage={})

        return _stream()


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


@pytest.mark.asyncio
async def test_routing_chat_model_propagates_non_stream_mode_to_endpoint_models() -> None:
    local = _ModeAwareChatModel("local")
    cloud = _ModeAwareChatModel("cloud")
    routing_cfg = SimpleNamespace(mode="local_first")
    model = RoutingChatModel(
        local_endpoint=RoutingEndpoint(
            provider_id="llamacpp",
            model_name="llama-local",
            model=local,
        ),
        cloud_endpoint=RoutingEndpoint(
            provider_id="openai",
            model_name="gpt-5",
            model=cloud,
        ),
        routing_cfg=routing_cfg,
    )
    model.stream = False

    result = await model(messages=[{"role": "user", "content": "hello"}])

    assert not hasattr(result, "__aiter__")
    assert getattr(result, "content", None) == "local-final"
    assert local.stream_history == [False]
    assert cloud.stream_history == []
