# -*- coding: utf-8 -*-
"""Fallback slot configuration for provider resolution."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .provider_manager import ProviderManager


class ModelSlotConfig(BaseModel):
    provider_id: str = Field(
        ...,
        description="ID of the provider to use for this model slot",
    )
    model: str = Field(
        ...,
        description="ID of the model to use for this model slot",
    )


class ProviderFallbackConfig(BaseModel):
    enabled: bool = True
    candidates: List[ModelSlotConfig] = Field(default_factory=list)


class ProviderFallbackService:
    """Manage fallback chain configuration for provider routing."""

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    def get_fallback_config(self) -> ProviderFallbackConfig:
        return self._manager.fallback_config

    def get_fallback_slots(self) -> List[ModelSlotConfig]:
        return list(self._manager.fallback_config.candidates)

    def set_fallback_config(
        self,
        *,
        enabled: bool,
        candidates: List[ModelSlotConfig],
    ) -> ProviderFallbackConfig:
        normalized: list[ModelSlotConfig] = []
        seen: set[tuple[str, str]] = set()
        for candidate in candidates:
            key = (candidate.provider_id, candidate.model)
            if key in seen:
                continue
            provider = self._manager._registry_service.get_provider(
                candidate.provider_id,
            )
            if provider is None:
                raise ValueError(
                    f"Fallback provider '{candidate.provider_id}' not found.",
                )
            if not provider.has_model(candidate.model):
                raise ValueError(
                    "Fallback model "
                    f"'{candidate.model}' not found in provider "
                    f"'{candidate.provider_id}'.",
                )
            seen.add(key)
            normalized.append(candidate)
        self._manager.fallback_config = ProviderFallbackConfig(
            enabled=enabled,
            candidates=normalized,
        )
        self._manager._storage_service.save_fallback_config(
            self._manager.fallback_config,
        )
        return self._manager.fallback_config

    def iter_model_slot_candidates(self) -> list[tuple[str, ModelSlotConfig]]:
        candidates: list[tuple[str, ModelSlotConfig]] = []
        if self._manager.active_model is not None:
            candidates.append(("active", self._manager.active_model))
        if self._manager.fallback_config.enabled:
            candidates.extend(
                ("fallback", slot)
                for slot in self._manager.fallback_config.candidates
            )
        return candidates
