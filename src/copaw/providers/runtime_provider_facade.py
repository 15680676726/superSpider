# -*- coding: utf-8 -*-
"""Thin runtime-facing facade over the compatibility ProviderManager."""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Protocol

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


class ProviderRuntimeFacade:
    """Runtime resolution wrapper that keeps ProviderManager out of callers."""

    def __init__(self, provider_manager: "ProviderManager") -> None:
        self._provider_manager = provider_manager

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
        factory = getattr(self._provider_manager, "_chat_model_factory", None)
        if factory is not None and hasattr(factory, "get_active_chat_model"):
            return factory.get_active_chat_model()
        return build_active_chat_model(self._provider_manager)


def get_runtime_provider_facade(
    *,
    provider_manager: "ProviderManager",
) -> ProviderRuntimeFacade:
    return ProviderRuntimeFacade(provider_manager)


def build_compat_runtime_provider_facade() -> ProviderRuntimeFacade:
    """Compatibility fallback for legacy utilities outside formal bootstrap wiring."""
    from .provider_manager import ProviderManager

    return ProviderRuntimeFacade(ProviderManager())
