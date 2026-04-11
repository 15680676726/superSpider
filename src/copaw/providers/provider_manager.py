# -*- coding: utf-8 -*-
"""Compatibility facade for provider administration and legacy callers."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from agentscope.model import ChatModelBase

from copaw.constant import SECRET_DIR

from .provider import ModelInfo, Provider, ProviderInfo
from .provider_chat_model_factory import ProviderChatModelFactory, build_active_chat_model
from .provider_fallback_service import (
    ModelSlotConfig,
    ProviderFallbackConfig,
    ProviderFallbackService,
)
from .provider_registry import (
    PROVIDER_ALIYUN_CODINGPLAN,
    PROVIDER_ANTHROPIC,
    PROVIDER_AZURE_OPENAI,
    PROVIDER_DASHSCOPE,
    PROVIDER_LLAMACPP,
    PROVIDER_MLX,
    PROVIDER_MODELSCOPE,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    ProviderRegistryService,
)
from .provider_resolution_service import ActiveModelsInfo, ProviderResolutionService
from .provider_storage import ProviderStorageService

logger = logging.getLogger(__name__)


class ProviderManager:
    """Compatibility facade that delegates provider concerns to sub-services.

    Runtime/execution callers should prefer ``runtime_provider_facade`` instead
    of depending on this facade directly.
    """

    _instance = None

    def __init__(self) -> None:
        self.builtin_providers: Dict[str, Provider] = {}
        self.custom_providers: Dict[str, Provider] = {}
        self.active_model: ModelSlotConfig | None = None
        self.fallback_config = ProviderFallbackConfig()
        self.root_path: Path = SECRET_DIR / "providers"
        self.builtin_path: Path = self.root_path / "builtin"
        self.custom_path: Path = self.root_path / "custom"

        self._registry_service = ProviderRegistryService(self)
        self._storage_service = ProviderStorageService(self)
        self._fallback_service = ProviderFallbackService(self)
        self._resolution_service = ProviderResolutionService(self)
        self._chat_model_factory = ProviderChatModelFactory(self)

        self._storage_service.prepare_disk_storage()
        self._registry_service.init_builtins()
        try:
            self._storage_service.migrate_legacy_providers()
        except Exception as exc:
            logger.warning("Failed to migrate legacy providers: %s", exc)
        self._storage_service.init_from_storage()
        self._registry_service.update_local_models()

    async def list_provider_info(self) -> List[ProviderInfo]:
        return await self._registry_service.list_provider_info()

    def get_provider(self, provider_id: str) -> Provider | None:
        return self._registry_service.get_provider(provider_id)

    async def get_provider_info(self, provider_id: str) -> ProviderInfo | None:
        return await self._registry_service.get_provider_info(provider_id)

    def get_active_model(self) -> ModelSlotConfig | None:
        return self._resolution_service.get_active_model()

    def get_fallback_config(self) -> ProviderFallbackConfig:
        return self._fallback_service.get_fallback_config()

    def get_fallback_slots(self) -> List[ModelSlotConfig]:
        return self._fallback_service.get_fallback_slots()

    def get_active_models_info(self) -> ActiveModelsInfo:
        return self._resolution_service.get_active_models_info()

    def update_provider(self, provider_id: str, config: Dict) -> bool:
        provider = self.get_provider(provider_id)
        if not provider:
            return False
        provider.update_config(config)
        self._storage_service.save_provider(
            provider,
            is_builtin=self._registry_service.is_builtin_provider(provider_id),
        )
        return True

    async def fetch_provider_models(
        self,
        provider_id: str,
        update_target: str,
    ) -> List[ModelInfo]:
        provider = self.get_provider(provider_id)
        if not provider:
            return []
        try:
            models = await provider.fetch_models()
            for model in models:
                await provider.add_model(
                    model,
                    target=update_target,
                    ignore_duplicates=True,
                )
            self._storage_service.save_provider(
                provider,
                is_builtin=self._registry_service.is_builtin_provider(provider_id),
            )
            return models
        except Exception as exc:
            logger.warning(
                "Failed to fetch models for provider '%s': %s",
                provider_id,
                exc,
            )
            return []

    async def add_custom_provider(self, provider_data: ProviderInfo):
        if provider_data.id in self.builtin_providers:
            raise ValueError(f"'{provider_data.id}' conflicts with a built-in provider.")
        if provider_data.id in self.custom_providers:
            raise ValueError(f"Custom provider '{provider_data.id}' already exists.")
        provider_data.is_custom = True
        provider = self._registry_service.provider_from_data(
            provider_data.model_dump(),
        )
        self.custom_providers[provider.id] = provider
        self._storage_service.save_provider(provider, is_builtin=False)
        return await provider.get_info()

    def remove_custom_provider(self, provider_id: str) -> bool:
        if provider_id in self.custom_providers:
            del self.custom_providers[provider_id]
            provider_path = self.custom_path / f"{provider_id}.json"
            if provider_path.exists():
                provider_path.unlink()
            return True
        return False

    async def activate_model(self, provider_id: str, model_id: str):
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' not found.")
        if not provider.has_model(model_id):
            raise ValueError(
                f"Model '{model_id}' not found in provider '{provider_id}'.",
            )
        self.active_model = ModelSlotConfig(provider_id=provider_id, model=model_id)
        self._storage_service.save_active_model(self.active_model)

    async def add_model_to_provider(
        self,
        provider_id: str,
        model_info: ModelInfo,
    ) -> ProviderInfo:
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' not found.")
        await provider.add_model(model_info)
        self._storage_service.save_provider(
            provider,
            is_builtin=self._registry_service.is_builtin_provider(provider_id),
        )
        return await provider.get_info()

    async def delete_model_from_provider(
        self,
        provider_id: str,
        model_id: str,
    ) -> ProviderInfo:
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' not found.")
        await provider.delete_model(model_id=model_id)
        self._storage_service.save_provider(
            provider,
            is_builtin=self._registry_service.is_builtin_provider(provider_id),
        )
        return await provider.get_info()

    def _save_provider(
        self,
        provider: Provider,
        is_builtin: bool = False,
        skip_if_exists: bool = False,
    ) -> None:
        self._storage_service.save_provider(
            provider,
            is_builtin=is_builtin,
            skip_if_exists=skip_if_exists,
        )

    def load_provider(
        self,
        provider_id: str,
        is_builtin: bool = False,
    ) -> Provider | None:
        return self._storage_service.load_provider(
            provider_id,
            is_builtin=is_builtin,
        )

    def _provider_from_data(self, data: Dict) -> Provider:
        return self._registry_service.provider_from_data(data)

    def save_active_model(self, active_model: ModelSlotConfig) -> None:
        self._storage_service.save_active_model(active_model)

    def save_fallback_config(self, fallback_config: ProviderFallbackConfig) -> None:
        self._storage_service.save_fallback_config(fallback_config)

    def load_active_model(self) -> ModelSlotConfig | None:
        return self._storage_service.load_active_model()

    def load_fallback_config(self) -> ProviderFallbackConfig | None:
        return self._storage_service.load_fallback_config()

    def reload_from_storage(self) -> None:
        self._storage_service.reload_from_storage()

    def update_local_models(self) -> None:
        self._registry_service.update_local_models()

    def set_fallback_config(
        self,
        *,
        enabled: bool,
        candidates: List[ModelSlotConfig],
    ):
        return self._fallback_service.set_fallback_config(
            enabled=enabled,
            candidates=candidates,
        )

    def resolve_model_slot(
        self,
    ) -> tuple[ModelSlotConfig, bool, str, list[str]]:
        return self._resolution_service.resolve_model_slot()

    def _slot_is_available(self, slot: ModelSlotConfig) -> tuple[bool, str]:
        return self._resolution_service.slot_is_available(slot)

    def _iter_model_slot_candidates(self) -> list[tuple[str, ModelSlotConfig]]:
        return self._fallback_service.iter_model_slot_candidates()

    def build_chat_model_for_slot(
        self,
        slot: ModelSlotConfig,
        *,
        stream: bool = True,
    ) -> ChatModelBase:
        return self._chat_model_factory.build_chat_model_for_slot(
            slot,
            stream=stream,
        )

    def get_preferred_chat_model_class(self) -> type[ChatModelBase]:
        return self._chat_model_factory.get_preferred_chat_model_class()

    def create_runtime_facade(self):
        from .runtime_provider_facade import ProviderRuntimeFacade

        return ProviderRuntimeFacade(self)

    @staticmethod
    def get_instance() -> "ProviderManager":
        if ProviderManager._instance is None:
            ProviderManager._instance = ProviderManager()
        return ProviderManager._instance

    @staticmethod
    def get_active_chat_model() -> ChatModelBase:
        manager = ProviderManager.get_instance()
        from .runtime_provider_facade import get_runtime_provider_facade

        return get_runtime_provider_facade(
            provider_manager=manager,
        ).get_active_chat_model()
