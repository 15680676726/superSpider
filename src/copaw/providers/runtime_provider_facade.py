# -*- coding: utf-8 -*-
"""Thin runtime-facing facade over the compatibility ProviderManager."""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Protocol

from agentscope.model import ChatModelBase

from .provider import Provider
from .provider_chat_model_factory import build_active_chat_model
from .provider_fallback_service import ModelSlotConfig, ProviderFallbackConfig
from .provider_resolution_service import ActiveModelsInfo
from .provider import ProviderInfo

if TYPE_CHECKING:
    from .provider_manager import ProviderManager


class ProviderRuntimeSurface(Protocol):
    """Minimal runtime model-resolution surface for execution callers."""

    async def list_provider_info(self) -> list[ProviderInfo]: ...

    def get_provider(self, provider_id: str) -> Provider | None: ...

    def get_active_model(self) -> ModelSlotConfig | None: ...

    def get_active_models_info(self) -> ActiveModelsInfo: ...

    def get_fallback_config(self) -> ProviderFallbackConfig: ...

    def get_fallback_slots(self) -> list[ModelSlotConfig]: ...

    def resolve_model_slot(
        self,
    ) -> tuple[ModelSlotConfig, bool, str, list[str]]: ...

    def build_chat_model_for_slot(self, slot: ModelSlotConfig) -> ChatModelBase: ...

    def get_preferred_chat_model_class(self) -> type[ChatModelBase]: ...

    def get_active_chat_model(self) -> ChatModelBase: ...

    def resolve_runtime_provider_contract(self) -> dict[str, Any]: ...


class ProviderRuntimeFacade:
    """Runtime resolution wrapper that keeps ProviderManager out of callers."""

    def __init__(self, provider_manager: "ProviderManager") -> None:
        self._provider_manager = provider_manager
        self._active_chat_model_cache: tuple[tuple[str, str] | None, ChatModelBase] | None = None

    @property
    def provider_manager(self) -> "ProviderManager":
        return self._provider_manager

    def get_provider(self, provider_id: str) -> Provider | None:
        return self._provider_manager.get_provider(provider_id)

    async def list_provider_info(self) -> list[ProviderInfo]:
        result = self._provider_manager.list_provider_info()
        if inspect.isawaitable(result):
            return await result
        return result

    def get_active_model(self) -> ModelSlotConfig | None:
        return self._provider_manager.get_active_model()

    def get_active_models_info(self) -> ActiveModelsInfo:
        return self._provider_manager.get_active_models_info()

    def get_fallback_config(self) -> ProviderFallbackConfig:
        return self._provider_manager.get_fallback_config()

    def get_fallback_slots(self) -> list[ModelSlotConfig]:
        return self._provider_manager.get_fallback_slots()

    def resolve_model_slot(
        self,
    ) -> tuple[ModelSlotConfig, bool, str, list[str]]:
        return self._provider_manager.resolve_model_slot()

    def build_chat_model_for_slot(self, slot: ModelSlotConfig) -> ChatModelBase:
        return self._provider_manager.build_chat_model_for_slot(slot)

    def get_preferred_chat_model_class(self) -> type[ChatModelBase]:
        return self._provider_manager.get_preferred_chat_model_class()

    def get_active_chat_model(self) -> ChatModelBase:
        slot_getter = getattr(self._provider_manager, "get_active_model", None)
        slot = slot_getter() if callable(slot_getter) else None
        cache_key = None
        if slot is not None:
            cache_key = (slot.provider_id, slot.model)
        cached = self._active_chat_model_cache
        if cached is not None and cached[0] == cache_key:
            return cached[1]
        factory = getattr(self._provider_manager, "_chat_model_factory", None)
        if factory is not None and hasattr(factory, "get_active_chat_model"):
            model = factory.get_active_chat_model()
        else:
            model = build_active_chat_model(self._provider_manager)
        self._active_chat_model_cache = (cache_key, model)
        return model

    def resolve_runtime_provider_contract(self) -> dict[str, Any]:
        slot, fallback_applied, resolution_reason, unavailable = (
            self.resolve_model_slot()
        )
        provider = self.get_provider(slot.provider_id)
        if provider is None:
            raise ValueError(f"Provider '{slot.provider_id}' not found.")
        auth_mode = (
            "api_key"
            if bool(getattr(provider, "require_api_key", False))
            and not bool(getattr(provider, "is_local", False))
            else "none"
        )
        api_key = str(getattr(provider, "api_key", "") or "")
        if auth_mode == "api_key" and not api_key.strip():
            raise ValueError(f"Provider '{slot.provider_id}' is missing an API key.")
        return {
            "provider_id": slot.provider_id,
            "provider_name": str(getattr(provider, "name", slot.provider_id) or slot.provider_id),
            "model": slot.model,
            "base_url": str(getattr(provider, "base_url", "") or ""),
            "api_key": api_key,
            "auth_mode": auth_mode,
            "extra_headers": {},
            "provenance": {
                "resolution_reason": resolution_reason,
                "fallback_applied": fallback_applied,
                "unavailable_candidates": list(unavailable),
            },
        }


def get_runtime_provider_facade(
    *,
    provider_manager: "ProviderManager",
) -> ProviderRuntimeFacade:
    return ProviderRuntimeFacade(provider_manager)


def build_compat_runtime_provider_facade() -> ProviderRuntimeFacade:
    """Compatibility fallback for legacy utilities outside formal bootstrap wiring."""
    from .provider_manager import ProviderManager

    return ProviderRuntimeFacade(ProviderManager())
