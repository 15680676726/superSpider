# -*- coding: utf-8 -*-
"""Provider/model slot resolution helpers."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

from pydantic import BaseModel, Field

from agentscope.model import ChatModelBase, OpenAIChatModel

from .provider_fallback_service import ModelSlotConfig

if TYPE_CHECKING:
    from .provider_manager import ProviderManager

logger = logging.getLogger(__name__)


class ActiveModelsInfo(BaseModel):
    active_llm: ModelSlotConfig | None
    resolved_llm: ModelSlotConfig | None = None
    fallback_enabled: bool = True
    fallback_chain: List[ModelSlotConfig] = Field(default_factory=list)
    fallback_applied: bool = False
    resolution_reason: str | None = None
    unavailable_candidates: List[str] = Field(default_factory=list)


class ProviderResolutionService:
    """Resolve active/fallback provider slots."""

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    def get_active_model(self) -> ModelSlotConfig | None:
        return self._manager.active_model

    def get_active_models_info(self) -> ActiveModelsInfo:
        resolved: ModelSlotConfig | None = None
        fallback_applied = False
        resolution_reason: str | None = None
        unavailable: list[str] = []
        try:
            resolved, fallback_applied, resolution_reason, unavailable = (
                self.resolve_model_slot()
            )
        except ValueError as exc:
            resolution_reason = str(exc)
        return ActiveModelsInfo(
            active_llm=self._manager.active_model,
            resolved_llm=resolved,
            fallback_enabled=self._manager.fallback_config.enabled,
            fallback_chain=list(self._manager.fallback_config.candidates),
            fallback_applied=fallback_applied,
            resolution_reason=resolution_reason,
            unavailable_candidates=unavailable,
        )

    def resolve_model_slot(
        self,
    ) -> tuple[ModelSlotConfig, bool, str, list[str]]:
        candidates = self._manager._fallback_service.iter_model_slot_candidates()
        if not candidates:
            raise ValueError("No active or fallback model configured.")

        unavailable: list[str] = []
        for source, slot in candidates:
            available, reason = self.slot_is_available(slot)
            if not available:
                unavailable.append(f"{slot.provider_id}/{slot.model}: {reason}")
                continue
            if source == "active":
                return slot, False, "Using configured active model.", unavailable
            if self._manager.active_model is None:
                return (
                    slot,
                    True,
                    "No active model configured; using fallback slot "
                    f"{slot.provider_id}/{slot.model}.",
                    unavailable,
                )
            return (
                slot,
                True,
                "Active model is unavailable; using fallback slot "
                f"{slot.provider_id}/{slot.model}.",
                unavailable,
            )

        detail = (
            "; ".join(unavailable)
            if unavailable
            else "No candidates were available."
        )
        raise ValueError(f"No available provider/model slot. {detail}")

    def slot_is_available(self, slot: ModelSlotConfig) -> tuple[bool, str]:
        provider = self._manager._registry_service.get_provider(slot.provider_id)
        if provider is None:
            return False, "provider not found"
        if not provider.has_model(slot.model):
            return False, "model not found"
        if (
            provider.require_api_key
            and not provider.is_local
            and not provider.api_key.strip()
        ):
            return False, "api key missing"
        return True, "ready"

    def get_preferred_chat_model_class(self) -> type[ChatModelBase]:
        candidates = self._manager._fallback_service.iter_model_slot_candidates()
        for _source, slot in candidates:
            available, _reason = self.slot_is_available(slot)
            if not available:
                continue
            provider = self._manager._registry_service.get_provider(slot.provider_id)
            if provider is None:
                continue
            if provider.is_local:
                return OpenAIChatModel
            try:
                return provider.get_chat_model_cls()
            except Exception:
                logger.warning(
                    "Failed to resolve chat model class for %s/%s",
                    slot.provider_id,
                    slot.model,
                )
        return OpenAIChatModel
