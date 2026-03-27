# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.providers.provider_manager import ModelSlotConfig, ProviderManager


def test_provider_manager_installs_internal_services() -> None:
    manager = ProviderManager()

    assert hasattr(manager, "_registry_service")
    assert hasattr(manager, "_storage_service")
    assert hasattr(manager, "_resolution_service")
    assert hasattr(manager, "_chat_model_factory")
    assert hasattr(manager, "_fallback_service")


def test_provider_manager_get_provider_delegates_to_registry_service() -> None:
    manager = ProviderManager()

    class StubRegistryService:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_provider(self, provider_id: str):
            self.calls.append(provider_id)
            return {"id": provider_id, "delegated": True}

    stub = StubRegistryService()
    manager._registry_service = stub  # type: ignore[attr-defined]

    result = manager.get_provider("openai")

    assert result == {"id": "openai", "delegated": True}
    assert stub.calls == ["openai"]


def test_provider_manager_resolve_model_slot_delegates_to_resolution_service() -> None:
    manager = ProviderManager()
    slot = ModelSlotConfig(provider_id="openai", model="gpt-5.2")

    class StubResolutionService:
        def __init__(self) -> None:
            self.called = False

        def resolve_model_slot(self):
            self.called = True
            return slot, True, "delegated", ["fallback"]

    stub = StubResolutionService()
    manager._resolution_service = stub  # type: ignore[attr-defined]

    result = manager.resolve_model_slot()

    assert result == (slot, True, "delegated", ["fallback"])
    assert stub.called is True


def test_provider_manager_set_fallback_config_delegates_to_fallback_service() -> None:
    manager = ProviderManager()
    slot = ModelSlotConfig(provider_id="openai", model="gpt-5.2")

    class StubFallbackService:
        def __init__(self) -> None:
            self.calls: list[tuple[bool, list[ModelSlotConfig]]] = []

        def set_fallback_config(self, *, enabled: bool, candidates):
            self.calls.append((enabled, list(candidates)))
            return {"enabled": enabled, "count": len(candidates)}

    stub = StubFallbackService()
    manager._fallback_service = stub  # type: ignore[attr-defined]

    result = manager.set_fallback_config(enabled=True, candidates=[slot])

    assert result == {"enabled": True, "count": 1}
    assert stub.calls == [(True, [slot])]


def test_provider_manager_build_chat_model_for_slot_delegates_to_factory() -> None:
    manager = ProviderManager()
    slot = ModelSlotConfig(provider_id="openai", model="gpt-5.2")

    class StubChatModelFactory:
        def __init__(self) -> None:
            self.calls: list[ModelSlotConfig] = []

        def build_chat_model_for_slot(self, target: ModelSlotConfig):
            self.calls.append(target)
            return {"slot": target.model, "delegated": True}

    stub = StubChatModelFactory()
    manager._chat_model_factory = stub  # type: ignore[attr-defined]

    result = manager.build_chat_model_for_slot(slot)

    assert result == {"slot": "gpt-5.2", "delegated": True}
    assert stub.calls == [slot]
