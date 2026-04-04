# -*- coding: utf-8 -*-
"""Canonical admin write service for provider configuration."""
from __future__ import annotations

from typing import Optional

from .provider import ModelInfo, ProviderInfo
from .provider_registry import PROVIDER_OLLAMA
from .provider_manager import (
    ActiveModelsInfo,
    ModelSlotConfig,
    ProviderFallbackConfig,
    ProviderManager,
)


class ProviderAdminService:
    """Unify provider/runtime write actions behind a single admin surface."""

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def configure_provider(
        self,
        provider_id: str,
        *,
        api_key: Optional[str],
        base_url: Optional[str],
        chat_model: Optional[str],
    ) -> ProviderInfo:
        ok = self._manager.update_provider(
            provider_id,
            {
                "api_key": api_key,
                "base_url": base_url,
                "chat_model": chat_model,
            },
        )
        if not ok:
            raise ValueError(f"Provider '{provider_id}' not found")
        provider_info = await self._manager.get_provider_info(provider_id)
        if provider_info is None:
            raise ValueError(f"Provider '{provider_id}' not found after update")
        return provider_info

    async def create_custom_provider(self, provider: ProviderInfo) -> ProviderInfo:
        return await self._manager.add_custom_provider(provider)

    def remove_custom_provider(self, provider_id: str) -> bool:
        return self._manager.remove_custom_provider(provider_id)

    async def discover_provider_models(
        self,
        provider_id: str,
        *,
        api_key: Optional[str],
        base_url: Optional[str],
        chat_model: Optional[str],
    ) -> list[ModelInfo]:
        ok = self._manager.update_provider(
            provider_id,
            {
                "api_key": api_key,
                "base_url": base_url,
                "chat_model": chat_model,
            },
        )
        if not ok:
            raise ValueError(f"Provider '{provider_id}' not found")
        return await self._manager.fetch_provider_models(
            provider_id,
            update_target="extra_models",
        )

    async def add_provider_model(
        self,
        provider_id: str,
        *,
        model_id: str,
        name: str,
    ) -> ProviderInfo:
        return await self._manager.add_model_to_provider(
            provider_id=provider_id,
            model_info=ModelInfo(id=model_id, name=name),
        )

    async def remove_provider_model(
        self,
        provider_id: str,
        *,
        model_id: str,
    ) -> ProviderInfo:
        return await self._manager.delete_model_from_provider(
            provider_id=provider_id,
            model_id=model_id,
        )

    async def set_active_model(
        self,
        *,
        provider_id: str,
        model_id: str,
    ) -> ActiveModelsInfo:
        await self._manager.activate_model(provider_id, model_id)
        return self._manager.get_active_models_info()

    def set_fallback_config(
        self,
        *,
        enabled: bool,
        candidates: list[ModelSlotConfig],
    ) -> ProviderFallbackConfig:
        return self._manager.set_fallback_config(
            enabled=enabled,
            candidates=candidates,
        )

    def refresh_local_model_catalog(self) -> None:
        self._manager.update_local_models()

    async def add_ollama_model(self, *, name: str) -> None:
        provider = self._manager.get_provider(PROVIDER_OLLAMA.id)
        if provider is None:
            raise ValueError(f"Provider '{PROVIDER_OLLAMA.id}' not found")
        await provider.add_model(
            ModelInfo(id=name, name=name),
        )

    async def delete_ollama_model(self, *, name: str) -> None:
        provider = self._manager.get_provider(PROVIDER_OLLAMA.id)
        if provider is None:
            raise ValueError(f"Provider '{PROVIDER_OLLAMA.id}' not found")
        await provider.delete_model(model_id=name)


def build_provider_admin_service(
    provider_manager: ProviderManager,
) -> ProviderAdminService:
    return ProviderAdminService(provider_manager)
