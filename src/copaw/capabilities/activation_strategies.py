# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Protocol

from ..app.mcp.runtime_contract import (
    build_mcp_activation_state,
    infer_mcp_activation_class,
)
from ..config.config import MCPClientConfig, MCPConfig
from .activation_models import ActivationClass, ActivationRequest, ActivationState


class ActivationStrategy(Protocol):
    async def resolve_context(self, request: ActivationRequest) -> Any: ...

    async def read_state(self, context: Any) -> ActivationState: ...

    async def remediate(
        self,
        context: Any,
        state: ActivationState,
    ) -> list[str]: ...


class _BaseMcpActivationStrategy:
    activation_class: ActivationClass

    def __init__(
        self,
        *,
        client_key: str,
        mcp_manager: object | None,
        capability_service: object | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._client_key = str(client_key).strip()
        self._mcp_manager = mcp_manager
        self._capability_service = capability_service
        self._config = dict(config or {})

    async def resolve_context(self, request: ActivationRequest) -> dict[str, Any]:
        metadata = dict(request.metadata or {})
        runtime_payload = dict(self._config)
        runtime_payload.update(metadata)
        scope_payload = _mapping(runtime_payload.get("mcp_scope_overlay"))
        scope_ref = _first_non_empty(
            runtime_payload.get("scope_ref"),
            scope_payload.get("scope_ref"),
            scope_payload.get("session_scope_ref"),
            scope_payload.get("seat_scope_ref"),
        )
        parent_scope_ref = _first_non_empty(
            runtime_payload.get("parent_scope_ref"),
            scope_payload.get("parent_scope_ref"),
            scope_payload.get("seat_scope_ref"),
        )
        overlay_mode = (
            _string(scope_payload.get("overlay_mode")) or "additive"
        ).strip().lower()
        timeout = _float_value(runtime_payload.get("timeout")) or 60.0
        return {
            "client_key": self._client_key,
            "scope_ref": scope_ref,
            "parent_scope_ref": parent_scope_ref,
            "overlay_mode": overlay_mode,
            "timeout": timeout,
            "scope_payload": scope_payload,
        }

    async def read_state(self, context: dict[str, Any]) -> ActivationState:
        requested_scope_ref = _string(context.get("scope_ref"))
        record = await self._get_runtime_record(
            self._client_key,
            scope_ref=requested_scope_ref,
        )
        if record is None and requested_scope_ref is not None:
            record = await self._get_runtime_record(self._client_key)
        activation_class = infer_mcp_activation_class(
            record,
            requested_scope_ref=requested_scope_ref
            if self.activation_class == "workspace-bound"
            else None,
        )
        if activation_class != self.activation_class and self.activation_class != "workspace-bound":
            requested_scope_ref = None
        return build_mcp_activation_state(
            record,
            activation_class=self.activation_class,
            requested_scope_ref=requested_scope_ref,
        )

    async def _get_runtime_record(
        self,
        client_key: str,
        *,
        scope_ref: str | None = None,
    ):
        if self._mcp_manager is None:
            return None
        getter = getattr(self._mcp_manager, "get_runtime_record", None)
        if not callable(getter):
            return None
        try:
            return await getter(client_key, scope_ref=scope_ref)
        except TypeError:
            return await getter(client_key)

    async def _get_client_config(
        self,
        *,
        scope_ref: str | None = None,
    ) -> MCPClientConfig | None:
        if self._mcp_manager is not None:
            getter = getattr(self._mcp_manager, "get_client_config", None)
            if callable(getter):
                try:
                    config = await getter(self._client_key, scope_ref=scope_ref)
                except TypeError:
                    config = await getter(self._client_key)
                if config is not None:
                    return config.model_copy(deep=True)
        if self._capability_service is not None:
            getter = getattr(self._capability_service, "get_mcp_client_config", None)
            if callable(getter):
                config = getter(self._client_key)
                if config is not None:
                    return config.model_copy(deep=True)
        info_getter = getattr(self._capability_service, "get_mcp_client_info", None)
        if callable(info_getter):
            info = info_getter(self._client_key)
            if isinstance(info, dict):
                try:
                    return MCPClientConfig(
                        name=str(info.get("name") or self._client_key),
                        description=str(info.get("description") or ""),
                        enabled=bool(info.get("enabled", True)),
                        transport=str(info.get("transport") or "stdio"),  # type: ignore[arg-type]
                        url=str(info.get("url") or ""),
                        command=str(info.get("command") or ""),
                        args=[str(item) for item in list(info.get("args") or [])],
                        cwd=str(info.get("cwd") or ""),
                    )
                except Exception:
                    return None
        return None


class McpWorkspaceActivationStrategy(_BaseMcpActivationStrategy):
    activation_class: ActivationClass = "workspace-bound"

    async def remediate(
        self,
        context: dict[str, Any],
        state: ActivationState,
    ) -> list[str]:
        _ = state
        if self._mcp_manager is None:
            return []
        mount_overlay = getattr(self._mcp_manager, "mount_scope_overlay", None)
        if not callable(mount_overlay):
            return []
        scope_ref = _string(context.get("scope_ref"))
        if scope_ref is None:
            return []
        overlay_client_config = _resolve_overlay_client_config(
            client_key=self._client_key,
            scope_payload=_mapping(context.get("scope_payload")),
        )
        if overlay_client_config is None:
            overlay_client_config = await self._get_client_config(scope_ref=None)
        if overlay_client_config is None:
            return []
        additive = str(context.get("overlay_mode") or "additive").strip().lower() != "replace"
        await mount_overlay(
            scope_ref,
            MCPConfig(clients={self._client_key: overlay_client_config}),
            parent_scope_ref=_string(context.get("parent_scope_ref")),
            additive=additive,
            timeout=float(context.get("timeout") or 60.0),
        )
        return ["mount-scope-overlay"]


class McpAuthActivationStrategy(_BaseMcpActivationStrategy):
    activation_class: ActivationClass = "auth-bound"

    async def remediate(
        self,
        context: dict[str, Any],
        state: ActivationState,
    ) -> list[str]:
        _ = context
        if state.reason in {
            "captcha_required",
            "two_factor_required",
            "explicit_human_confirm_required",
            "human_auth_required",
            "host_open_required",
        }:
            return []
        if self._mcp_manager is None:
            return []
        replace_client = getattr(self._mcp_manager, "replace_client", None)
        if not callable(replace_client):
            return []
        client_config = await self._get_client_config(scope_ref=None)
        if client_config is None:
            return []
        await replace_client(
            self._client_key,
            client_config,
            timeout=float(context.get("timeout") or 60.0),
        )
        return ["refresh-auth-runtime"]


class McpStatelessActivationStrategy(_BaseMcpActivationStrategy):
    activation_class: ActivationClass = "stateless"

    async def remediate(
        self,
        context: dict[str, Any],
        state: ActivationState,
    ) -> list[str]:
        _ = state
        if self._mcp_manager is None:
            return []
        replace_client = getattr(self._mcp_manager, "replace_client", None)
        if not callable(replace_client):
            return []
        client_config = await self._get_client_config(scope_ref=None)
        if client_config is None:
            return []
        await replace_client(
            self._client_key,
            client_config,
            timeout=float(context.get("timeout") or 60.0),
        )
        return ["reconnect-runtime-client"]


def build_mcp_activation_strategy(
    *,
    activation_class: ActivationClass,
    client_key: str,
    mcp_manager: object | None,
    capability_service: object | None = None,
    config: dict[str, Any] | None = None,
) -> ActivationStrategy:
    if activation_class == "workspace-bound":
        return McpWorkspaceActivationStrategy(
            client_key=client_key,
            mcp_manager=mcp_manager,
            capability_service=capability_service,
            config=config,
        )
    if activation_class == "auth-bound":
        return McpAuthActivationStrategy(
            client_key=client_key,
            mcp_manager=mcp_manager,
            capability_service=capability_service,
            config=config,
        )
    return McpStatelessActivationStrategy(
        client_key=client_key,
        mcp_manager=mcp_manager,
        capability_service=capability_service,
        config=config,
    )


def _resolve_overlay_client_config(
    *,
    client_key: str,
    scope_payload: dict[str, Any],
) -> MCPClientConfig | None:
    clients = _mapping(scope_payload.get("clients"))
    raw = _mapping(clients.get(client_key))
    if not raw and len(clients) == 1:
        raw = _mapping(next(iter(clients.values()), {}))
    if not raw:
        return None
    try:
        return MCPClientConfig.model_validate(raw)
    except Exception:
        return None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: object) -> str | None:
    raw = str(value or "").strip()
    return raw or None


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        resolved = _string(value)
        if resolved is not None:
            return resolved
    return None


def _float_value(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = _string(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


__all__ = [
    "ActivationStrategy",
    "McpAuthActivationStrategy",
    "McpStatelessActivationStrategy",
    "McpWorkspaceActivationStrategy",
    "build_mcp_activation_strategy",
]
