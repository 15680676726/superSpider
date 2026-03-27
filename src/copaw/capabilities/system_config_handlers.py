# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from pydantic import ValidationError

from ..config import AgentsRunningConfig, ChannelConfig, HeartbeatConfig
from ..config.config import AgentsLLMRoutingConfig, MCPClientConfig
from .execution_support import _build_channel_config, _model_dump_payload


class SystemConfigCapabilityFacade:
    def __init__(
        self,
        *,
        load_config_fn: Callable[[], Any],
        save_config_fn: Callable[[Any], None],
        set_capability_enabled_fn: Callable[..., dict[str, object]],
        delete_capability_fn: Callable[[str], dict[str, object]],
    ) -> None:
        self._load_config = load_config_fn
        self._save_config = save_config_fn
        self._set_capability_enabled = set_capability_enabled_fn
        self._delete_capability = delete_capability_fn

    def handle_set_capability_enabled(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        capability_name = str(resolved_payload.get("capability_id") or "")
        if not capability_name:
            return {"success": False, "error": "capability_id is required"}
        enabled = resolved_payload.get("enabled")
        if not isinstance(enabled, bool):
            return {"success": False, "error": "enabled must be a boolean"}
        result = self._set_capability_enabled(capability_name, enabled=enabled)
        if result.get("error"):
            return {"success": False, "error": str(result["error"])}
        return {
            "success": True,
            "summary": (
                f"Capability '{capability_name}' "
                f"{'enabled' if enabled else 'disabled'}."
            ),
            **result,
        }

    def handle_delete_capability(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        capability_name = str(resolved_payload.get("capability_id") or "")
        if not capability_name:
            return {"success": False, "error": "capability_id is required"}
        result = self._delete_capability(capability_name)
        if result.get("error"):
            return {"success": False, "error": str(result["error"])}
        return {
            "success": True,
            "summary": f"Capability '{capability_name}' deleted.",
            **result,
        }

    def handle_update_channels_config(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        payload = (
            resolved_payload.get("channels")
            or resolved_payload.get("config")
            or resolved_payload
        )
        try:
            channels = ChannelConfig.model_validate(payload)
        except ValidationError as exc:
            return {"success": False, "error": str(exc)}
        config = self._load_config()
        config.channels = channels
        self._save_config(config)
        return {
            "success": True,
            "summary": "Updated channel configuration.",
            "channels": channels.model_dump(mode="json"),
        }

    def handle_update_channel_config(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        channel_name = str(resolved_payload.get("channel_name") or "")
        if not channel_name:
            return {"success": False, "error": "channel_name is required"}
        payload = (
            resolved_payload.get("channel_config")
            or resolved_payload.get("config")
            or {}
        )
        try:
            channel_config = _build_channel_config(channel_name, payload)
        except (KeyError, ValidationError, ValueError) as exc:
            return {"success": False, "error": str(exc)}
        config = self._load_config()
        setattr(config.channels, channel_name, channel_config)
        self._save_config(config)
        return {
            "success": True,
            "summary": f"Updated channel '{channel_name}'.",
            "channel_name": channel_name,
            "channel_config": _model_dump_payload(channel_config),
        }

    def handle_update_heartbeat_config(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        payload = (
            resolved_payload.get("heartbeat")
            or resolved_payload.get("config")
            or resolved_payload
        )
        try:
            heartbeat = HeartbeatConfig.model_validate(payload)
        except ValidationError as exc:
            return {"success": False, "error": str(exc)}
        config = self._load_config()
        config.agents.defaults.heartbeat = heartbeat
        self._save_config(config)
        return {
            "success": True,
            "summary": "Updated heartbeat configuration.",
            "heartbeat": heartbeat.model_dump(mode="json", by_alias=True),
        }

    def handle_update_agents_llm_routing(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        payload = (
            resolved_payload.get("llm_routing")
            or resolved_payload.get("config")
            or resolved_payload
        )
        try:
            llm_routing = AgentsLLMRoutingConfig.model_validate(payload)
        except ValidationError as exc:
            return {"success": False, "error": str(exc)}
        config = self._load_config()
        config.agents.llm_routing = llm_routing
        self._save_config(config)
        return {
            "success": True,
            "summary": "Updated agent LLM routing configuration.",
            "llm_routing": llm_routing.model_dump(mode="json"),
        }

    def handle_update_agents_running_config(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        payload = (
            resolved_payload.get("running_config")
            or resolved_payload.get("config")
            or resolved_payload
        )
        try:
            running_config = AgentsRunningConfig.model_validate(payload)
        except ValidationError as exc:
            return {"success": False, "error": str(exc)}
        config = self._load_config()
        config.agents.running = running_config
        self._save_config(config)
        return {
            "success": True,
            "summary": "Updated agent running configuration.",
            "running_config": running_config.model_dump(mode="json"),
        }

    def handle_create_mcp_client(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        client_key = str(resolved_payload.get("client_key") or "").strip()
        if not client_key:
            return {"success": False, "error": "client_key is required"}
        payload = (
            resolved_payload.get("client")
            or resolved_payload.get("client_config")
            or {}
        )
        try:
            client_config = MCPClientConfig.model_validate(payload)
        except ValidationError as exc:
            return {"success": False, "error": str(exc)}
        config = self._load_config()
        if client_key in config.mcp.clients:
            return {
                "success": False,
                "error": f"MCP client '{client_key}' already exists",
            }
        config.mcp.clients[client_key] = client_config
        self._save_config(config)
        return {
            "success": True,
            "summary": f"Created MCP client '{client_key}'.",
            "client_key": client_key,
            "client": client_config.model_dump(mode="json"),
        }

    def handle_update_mcp_client(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        client_key = str(resolved_payload.get("client_key") or "").strip()
        if not client_key:
            return {"success": False, "error": "client_key is required"}
        payload = (
            resolved_payload.get("client")
            or resolved_payload.get("client_config")
            or {}
        )
        if not isinstance(payload, dict):
            return {
                "success": False,
                "error": "client update payload must be an object",
            }
        config = self._load_config()
        existing = config.mcp.clients.get(client_key)
        if existing is None:
            return {
                "success": False,
                "error": f"MCP client '{client_key}' not found",
            }
        update_data = dict(payload)
        if "env" in update_data and update_data["env"] is not None:
            updated_env = existing.env.copy() if existing.env else {}
            updated_env.update(update_data["env"])
            update_data["env"] = updated_env
        try:
            merged_data = existing.model_dump(mode="json")
            merged_data.update(update_data)
            client_config = MCPClientConfig.model_validate(merged_data)
        except ValidationError as exc:
            return {"success": False, "error": str(exc)}
        config.mcp.clients[client_key] = client_config
        self._save_config(config)
        return {
            "success": True,
            "summary": f"Updated MCP client '{client_key}'.",
            "client_key": client_key,
            "client": client_config.model_dump(mode="json"),
        }
