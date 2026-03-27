# -*- coding: utf-8 -*-
"""Disk persistence and legacy migration for providers."""
from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

from .openai_provider import OpenAIProvider
from .provider import ModelInfo, Provider
from .provider_fallback_service import ModelSlotConfig, ProviderFallbackConfig

if TYPE_CHECKING:
    from .provider_manager import ProviderManager

logger = logging.getLogger(__name__)


class ProviderStorageService:
    """Handle provider persistence and migration."""

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    def prepare_disk_storage(self) -> None:
        for path in [
            self._manager.root_path,
            self._manager.builtin_path,
            self._manager.custom_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(path, 0o700)
            except Exception:
                pass

    def provider_directory(self, *, is_builtin: bool):
        return self._manager.builtin_path if is_builtin else self._manager.custom_path

    def provider_path(self, provider_id: str, *, is_builtin: bool):
        return self.provider_directory(is_builtin=is_builtin) / f"{provider_id}.json"

    def config_path(self, filename: str):
        return self._manager.root_path / filename

    def save_json_file(self, path, payload: dict) -> None:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def load_json_file(self, path):
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return None

    def save_provider(
        self,
        provider: Provider,
        is_builtin: bool = False,
        skip_if_exists: bool = False,
    ) -> None:
        provider_path = self.provider_path(provider.id, is_builtin=is_builtin)
        if skip_if_exists and provider_path.exists():
            return
        self.save_json_file(provider_path, provider.model_dump())

    def load_provider(
        self,
        provider_id: str,
        is_builtin: bool = False,
    ) -> Provider | None:
        provider_path = self.provider_path(provider_id, is_builtin=is_builtin)
        try:
            data = self.load_json_file(provider_path)
            if data is None:
                return None
            return self._manager._registry_service.provider_from_data(data)
        except Exception as exc:
            logger.warning(
                "Failed to load provider '%s' from %s: %s",
                provider_id,
                provider_path,
                exc,
            )
            return None

    def save_active_model(self, active_model: ModelSlotConfig) -> None:
        self.save_json_file(
            self.config_path("active_model.json"),
            active_model.model_dump(),
        )

    def save_fallback_config(self, fallback_config: ProviderFallbackConfig) -> None:
        self.save_json_file(
            self.config_path("fallback_model.json"),
            fallback_config.model_dump(),
        )

    def load_active_model(self) -> ModelSlotConfig | None:
        data = self.load_json_file(self.config_path("active_model.json"))
        return ModelSlotConfig.model_validate(data) if data is not None else None

    def load_fallback_config(self) -> ProviderFallbackConfig | None:
        data = self.load_json_file(self.config_path("fallback_model.json"))
        return (
            ProviderFallbackConfig.model_validate(data)
            if data is not None
            else None
        )

    def migrate_legacy_providers(self) -> None:
        legacy_path = self._manager.root_path.parent / "providers.json"
        if not legacy_path.exists() or not legacy_path.is_file():
            return
        with open(legacy_path, "r", encoding="utf-8") as file:
            legacy_data = json.load(file)
        builtin_providers = legacy_data.get("providers", {})
        custom_providers = legacy_data.get("custom_providers", {})
        active_model = legacy_data.get("active_llm", {})
        for provider_id, config in builtin_providers.items():
            provider = self._manager._registry_service.get_provider(provider_id)
            if not provider:
                logger.warning(
                    "Legacy provider '%s' not found in registry, skipping migration.",
                    provider_id,
                )
                continue
            if "api_key" in config:
                provider.api_key = config["api_key"]
            if "extra_models" in config:
                provider.extra_models = [
                    ModelInfo.model_validate(model)
                    for model in config["extra_models"]
                ]
            if not provider.freeze_url and "base_url" in config:
                provider.base_url = config["base_url"]
            self.save_provider(provider, is_builtin=True)
        for provider_id, data in custom_providers.items():
            custom_provider = OpenAIProvider(
                id=provider_id,
                name=data.get("name", provider_id),
                base_url=data.get("base_url", ""),
                api_key=data.get("api_key", ""),
                is_custom=True,
            )
            if "models" in data:
                custom_provider.extra_models = [
                    ModelInfo.model_validate(model)
                    for model in data["models"]
                ]
            if "chat_model" in data:
                custom_provider.chat_model = data["chat_model"]
            self.save_provider(custom_provider, is_builtin=False)
        if active_model:
            try:
                self._manager.active_model = ModelSlotConfig.model_validate(
                    active_model,
                )
                self.save_active_model(self._manager.active_model)
            except Exception:
                logger.warning(
                    "Failed to migrate active model, using default.",
                )
        try:
            os.remove(legacy_path)
        except Exception:
            logger.warning(
                "Failed to remove legacy providers.json after migration.",
            )

    def init_from_storage(self) -> None:
        for builtin in self._manager.builtin_providers.values():
            provider = self.load_provider(builtin.id, is_builtin=True)
            if provider:
                builtin.base_url = provider.base_url
                builtin.api_key = provider.api_key
                builtin.extra_models = provider.extra_models
        for provider_file in self._manager.custom_path.glob("*.json"):
            provider = self.load_provider(provider_file.stem, is_builtin=False)
            if provider:
                self._manager.custom_providers[provider.id] = provider
        active_model = self.load_active_model()
        if active_model:
            self._manager.active_model = active_model
        fallback_config = self.load_fallback_config()
        if fallback_config is not None:
            self._manager.fallback_config = fallback_config

    def reload_from_storage(self) -> None:
        self._manager.custom_providers.clear()
        self._manager.active_model = None
        self._manager.fallback_config = ProviderFallbackConfig()
        self.init_from_storage()
        self._manager._registry_service.update_local_models()
