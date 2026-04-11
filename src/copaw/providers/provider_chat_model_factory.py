# -*- coding: utf-8 -*-
"""Chat-model construction for provider slots."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agentscope.model import ChatModelBase

from copaw.local_models import create_local_chat_model

from .provider_fallback_service import ModelSlotConfig

if TYPE_CHECKING:
    from .provider_manager import ProviderManager

logger = logging.getLogger(__name__)


class ProviderChatModelFactory:
    """Build chat-model instances from resolved provider slots."""

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    def build_chat_model_for_slot(
        self,
        slot: ModelSlotConfig,
        *,
        stream: bool = True,
    ) -> ChatModelBase:
        provider = self._manager._registry_service.get_provider(slot.provider_id)
        if provider is None:
            raise ValueError(f"Provider '{slot.provider_id}' not found.")
        if provider.is_local:
            return create_local_chat_model(
                model_id=slot.model,
                stream=stream,
                generate_kwargs={"max_tokens": None},
            )
        return provider.get_chat_model_instance(slot.model, stream=stream)

    def get_preferred_chat_model_class(self) -> type[ChatModelBase]:
        return self._manager._resolution_service.get_preferred_chat_model_class()

    def get_active_chat_model(self) -> ChatModelBase:
        return build_active_chat_model(self._manager)


def build_active_chat_model(manager: object) -> ChatModelBase:
    from .runtime_fallback_chat_model import RuntimeFallbackChatModel

    try:
        from copaw.config import load_config

        config = load_config()
        routing_cfg = getattr(
            getattr(config, "agents", None),
            "llm_routing",
            None,
        )
    except Exception:
        routing_cfg = None

    if not bool(getattr(routing_cfg, "enabled", False)):
        return RuntimeFallbackChatModel(manager)  # type: ignore[arg-type]

    from copaw.agents.routing_chat_model import RoutingChatModel, RoutingEndpoint

    local_cfg = getattr(routing_cfg, "local", None)
    local_provider_id = str(getattr(local_cfg, "provider_id", "") or "").strip()
    local_model_name = str(getattr(local_cfg, "model", "") or "").strip()
    if not local_provider_id or not local_model_name:
        raise ValueError(
            "agents.llm_routing.enabled=true requires "
            "agents.llm_routing.local.provider_id and .model.",
        )
    local_slot = ModelSlotConfig(
        provider_id=local_provider_id,
        model=local_model_name,
    )
    local_model = manager.build_chat_model_for_slot(local_slot)

    cloud_cfg = getattr(routing_cfg, "cloud", None)
    cloud_provider_id = str(getattr(cloud_cfg, "provider_id", "") or "").strip()
    cloud_model_name = str(getattr(cloud_cfg, "model", "") or "").strip()
    if cloud_provider_id and cloud_model_name:
        cloud_slot = ModelSlotConfig(
            provider_id=cloud_provider_id,
            model=cloud_model_name,
        )
        cloud_model = manager.build_chat_model_for_slot(cloud_slot)
    else:
        cloud_model = RuntimeFallbackChatModel(manager)  # type: ignore[arg-type]
        try:
            active = manager.get_active_model()
            if active is not None:
                cloud_provider_id = (
                    str(getattr(active, "provider_id", "")) or cloud_provider_id
                )
                cloud_model_name = (
                    str(getattr(active, "model", "")) or cloud_model_name
                )
        except Exception:
            pass
        cloud_provider_id = cloud_provider_id or "active"
        cloud_model_name = cloud_model_name or getattr(
            cloud_model,
            "model_name",
            "copaw-runtime",
        )

    local_family = getattr(
        local_model,
        "preferred_chat_model_class",
        local_model.__class__,
    )
    cloud_family = getattr(
        cloud_model,
        "preferred_chat_model_class",
        cloud_model.__class__,
    )
    if local_family is not cloud_family:
        raise ValueError(
            "agents.llm_routing local/cloud endpoints must share the same "
            "formatter family. "
            f"local={local_provider_id}/{local_model_name} "
            f"({getattr(local_family, '__name__', local_family)}), "
            f"cloud={cloud_provider_id}/{cloud_model_name} "
            f"({getattr(cloud_family, '__name__', cloud_family)}).",
        )

    model = RoutingChatModel(
        local_endpoint=RoutingEndpoint(
            provider_id=local_provider_id,
            model_name=local_model_name,
            model=local_model,
        ),
        cloud_endpoint=RoutingEndpoint(
            provider_id=cloud_provider_id,
            model_name=cloud_model_name,
            model=cloud_model,
        ),
        routing_cfg=routing_cfg,
    )
    model.preferred_chat_model_class = local_family
    return model
