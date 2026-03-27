# -*- coding: utf-8 -*-

from typing import List

from fastapi import APIRouter, Body, HTTPException, Path, Request

from ...config import (
    load_config,
    ChannelConfig,
    ChannelConfigUnion,
    get_available_channels,
)
from ..channels.registry import BUILTIN_CHANNEL_KEYS
from ...config.config import AgentsLLMRoutingConfig
from .governed_mutations import dispatch_governed_mutation

router = APIRouter(prefix="/config", tags=["config"])


async def _dispatch_config_mutation(
    request: Request,
    *,
    capability_ref: str,
    title: str,
    payload: dict[str, object],
    fallback_risk: str = "guarded",
) -> dict[str, object]:
    return await dispatch_governed_mutation(
        request,
        capability_ref=capability_ref,
        title=title,
        payload=payload,
        environment_ref="config:runtime",
        fallback_risk=fallback_risk,
    )


@router.get(
    "/channels",
    summary="List all channels",
    description="Retrieve configuration for all available channels",
)
async def list_channels() -> dict:
    """List all channel configs (filtered by available channels)."""
    config = load_config()
    available = get_available_channels()

    # Get all channel configs from model_dump and __pydantic_extra__
    all_configs = config.channels.model_dump()
    extra = getattr(config.channels, "__pydantic_extra__", None) or {}
    all_configs.update(extra)

    # Return all available channels (use default config if not saved)
    result = {}
    for key in available:
        if key in all_configs:
            channel_data = (
                dict(all_configs[key])
                if isinstance(all_configs[key], dict)
                else all_configs[key]
            )
        else:
            # Channel registered but no config saved yet, use empty default
            channel_data = {"enabled": False, "bot_prefix": ""}
        if isinstance(channel_data, dict):
            channel_data["isBuiltin"] = key in BUILTIN_CHANNEL_KEYS
        result[key] = channel_data

    return result


@router.get(
    "/channels/types",
    summary="List channel types",
    description="Return all available channel type identifiers",
)
async def list_channel_types() -> List[str]:
    """Return available channel type identifiers (env-filtered)."""
    return list(get_available_channels())


@router.put(
    "/channels",
    response_model=ChannelConfig,
    summary="Update all channels",
    description="Update configuration for all channels at once",
)
async def put_channels(
    request: Request,
    channels_config: ChannelConfig = Body(
        ...,
        description="Complete channel configuration",
    ),
) -> ChannelConfig:
    """Update all channel configs."""
    result = await _dispatch_config_mutation(
        request,
        capability_ref="system:update_channels_config",
        title="Update all channel configs",
        payload={
            "channels": channels_config.model_dump(mode="json"),
            "actor": "copaw-operator",
        },
    )
    if not result.get("success"):
        raise HTTPException(400, detail=result.get("error") or "Channel update failed")
    return channels_config


@router.get(
    "/channels/{channel_name}",
    response_model=ChannelConfigUnion,
    summary="Get channel config",
    description="Retrieve configuration for a specific channel by name",
)
async def get_channel(
    channel_name: str = Path(
        ...,
        description="Name of the channel to retrieve",
        min_length=1,
    ),
) -> ChannelConfigUnion:
    """Get a specific channel config by name."""
    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    config = load_config()
    single_channel_config = getattr(config.channels, channel_name, None)
    if single_channel_config is None:
        extra = getattr(config.channels, "__pydantic_extra__", None) or {}
        single_channel_config = extra.get(channel_name)
    if single_channel_config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    return single_channel_config


@router.put(
    "/channels/{channel_name}",
    response_model=ChannelConfigUnion,
    summary="Update channel config",
    description="Update configuration for a specific channel by name",
)
async def put_channel(
    request: Request,
    channel_name: str = Path(
        ...,
        description="Name of the channel to update",
        min_length=1,
    ),
    single_channel_config: dict = Body(
        ...,
        description="Updated channel configuration",
    ),
) -> ChannelConfigUnion:
    """Update a specific channel config by name."""
    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    result = await _dispatch_config_mutation(
        request,
        capability_ref="system:update_channel_config",
        title=f"Update channel config {channel_name}",
        payload={
            "channel_name": channel_name,
            "channel_config": dict(single_channel_config),
            "actor": "copaw-operator",
        },
    )
    if not result.get("success"):
        raise HTTPException(400, detail=result.get("error") or "Channel update failed")
    return dict(single_channel_config)


@router.get(
    "/agents/llm-routing",
    response_model=AgentsLLMRoutingConfig,
    summary="Get agent LLM routing settings",
)
async def get_agents_llm_routing() -> AgentsLLMRoutingConfig:
    config = load_config()
    return config.agents.llm_routing


@router.put(
    "/agents/llm-routing",
    response_model=AgentsLLMRoutingConfig,
    summary="Update agent LLM routing settings",
)
async def put_agents_llm_routing(
    request: Request,
    body: AgentsLLMRoutingConfig = Body(...),
) -> AgentsLLMRoutingConfig:
    result = await _dispatch_config_mutation(
        request,
        capability_ref="system:update_agents_llm_routing",
        title="Update agent LLM routing",
        payload={
            "llm_routing": body.model_dump(mode="json"),
            "actor": "copaw-operator",
        },
    )
    if not result.get("success"):
        raise HTTPException(400, detail=result.get("error") or "LLM routing update failed")
    return body
