# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.providers.provider_manager import ModelSlotConfig
from copaw.providers.runtime_provider_facade import (
    ProviderRuntimeFacade,
    get_runtime_provider_facade,
)


def test_runtime_provider_facade_delegates_model_resolution_and_factory() -> None:
    slot = ModelSlotConfig(provider_id="openai", model="gpt-5.2")
    active_models_info = SimpleNamespace(active_llm=slot, resolved_llm=slot)
    provider_info = {"id": "openai", "name": "OpenAI"}
    manager = SimpleNamespace(
        get_active_model=lambda: slot,
        get_fallback_config=lambda: SimpleNamespace(enabled=True),
        get_fallback_slots=lambda: [slot],
        get_provider=lambda provider_id: {"id": provider_id},
        list_provider_info=lambda: [provider_info],
        get_active_models_info=lambda: active_models_info,
        get_preferred_chat_model_class=lambda: str,
        resolve_model_slot=lambda: (slot, False, "configured", []),
        build_chat_model_for_slot=lambda target: {"slot": target.model},
    )
    manager._chat_model_factory = SimpleNamespace(
        get_active_chat_model=lambda: {"kind": "chat-model"},
    )

    facade = ProviderRuntimeFacade(manager)

    assert facade.get_active_model() is slot
    assert facade.get_fallback_config().enabled is True
    assert facade.get_fallback_slots() == [slot]
    assert facade.get_provider("openai") == {"id": "openai"}
    assert asyncio.run(facade.list_provider_info()) == [provider_info]
    assert facade.get_active_models_info() is active_models_info
    assert facade.get_preferred_chat_model_class() is str
    assert facade.resolve_model_slot() == (slot, False, "configured", [])
    assert facade.build_chat_model_for_slot(slot) == {"slot": "gpt-5.2"}
    assert facade.get_active_chat_model() == {"kind": "chat-model"}


def test_get_runtime_provider_facade_wraps_explicit_provider_manager() -> None:
    manager = SimpleNamespace()

    facade = get_runtime_provider_facade(provider_manager=manager)

    assert isinstance(facade, ProviderRuntimeFacade)
    assert facade.provider_manager is manager


def test_runtime_provider_facade_reuses_active_chat_model_for_same_slot() -> None:
    slot = ModelSlotConfig(provider_id="openai", model="gpt-5.2")
    built_models: list[object] = []

    def _build_model() -> object:
        model = {"kind": "chat-model", "build_index": len(built_models) + 1}
        built_models.append(model)
        return model

    manager = SimpleNamespace(
        get_active_model=lambda: slot,
        get_fallback_config=lambda: SimpleNamespace(enabled=True),
        get_fallback_slots=lambda: [slot],
        get_provider=lambda provider_id: {"id": provider_id},
        list_provider_info=lambda: [],
        get_active_models_info=lambda: SimpleNamespace(active_llm=slot, resolved_llm=slot),
        get_preferred_chat_model_class=lambda: str,
        resolve_model_slot=lambda: (slot, False, "configured", []),
        build_chat_model_for_slot=lambda target: {"slot": target.model},
    )
    manager._chat_model_factory = SimpleNamespace(get_active_chat_model=_build_model)

    facade = ProviderRuntimeFacade(manager)

    first = facade.get_active_chat_model()
    second = facade.get_active_chat_model()

    assert first is second
    assert built_models == [first]


def test_runtime_provider_facade_invalidates_cached_chat_model_after_active_slot_changes() -> None:
    active_slot = {"value": ModelSlotConfig(provider_id="openai", model="gpt-5.2")}
    built_models: list[object] = []

    def _build_model() -> object:
        slot = active_slot["value"]
        model = {
            "kind": "chat-model",
            "provider_id": slot.provider_id,
            "model": slot.model,
            "build_index": len(built_models) + 1,
        }
        built_models.append(model)
        return model

    manager = SimpleNamespace(
        get_active_model=lambda: active_slot["value"],
        get_fallback_config=lambda: SimpleNamespace(enabled=True),
        get_fallback_slots=lambda: [active_slot["value"]],
        get_provider=lambda provider_id: {"id": provider_id},
        list_provider_info=lambda: [],
        get_active_models_info=lambda: SimpleNamespace(
            active_llm=active_slot["value"],
            resolved_llm=active_slot["value"],
        ),
        get_preferred_chat_model_class=lambda: str,
        resolve_model_slot=lambda: (active_slot["value"], False, "configured", []),
        build_chat_model_for_slot=lambda target: {"slot": target.model},
    )
    manager._chat_model_factory = SimpleNamespace(get_active_chat_model=_build_model)

    facade = ProviderRuntimeFacade(manager)

    first = facade.get_active_chat_model()
    active_slot["value"] = ModelSlotConfig(provider_id="openai", model="gpt-5.3")
    second = facade.get_active_chat_model()

    assert first is not second
    assert [model["model"] for model in built_models] == ["gpt-5.2", "gpt-5.3"]
