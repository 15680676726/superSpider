# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .execution_support import (
    _tool_response_payload,
    _tool_response_success,
    _tool_response_summary,
)
from .models import CapabilityMount


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _adapter_contract(mount: CapabilityMount) -> dict[str, Any]:
    contract = dict((mount.metadata or {}).get("adapter_contract") or {})
    actions = contract.get("actions")
    contract["actions"] = list(actions) if isinstance(actions, list) else []
    return contract


def _resolve_action(
    contract: dict[str, Any],
    action_id: str,
) -> dict[str, Any] | None:
    for item in list(contract.get("actions") or []):
        if not isinstance(item, dict):
            continue
        if _string(item.get("action_id")) == action_id:
            return dict(item)
    return None


def _mcp_client_key(call_surface_ref: str | None) -> str | None:
    surface = _string(call_surface_ref)
    if surface is None:
        return None
    if surface.startswith("mcp:"):
        return surface.split(":", 1)[1].strip() or None
    return surface


def _http_request(
    *,
    base_url: str,
    transport_action_ref: str,
    payload: dict[str, Any],
) -> tuple[bool, str, object]:
    method = "POST"
    path = transport_action_ref
    if " " in transport_action_ref:
        method, path = transport_action_ref.split(" ", 1)
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method=method.upper(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30.0) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                parsed = raw
            return True, f"HTTP {response.status} {url}", parsed
    except HTTPError as exc:
        return False, f"HTTP {exc.code} {url}", exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        return False, str(exc), {"error": str(exc)}


def _resolve_sdk_callable(
    call_surface_ref: str | None,
    transport_action_ref: str,
):
    ref = _string(transport_action_ref) or _string(call_surface_ref)
    if ref is None:
        raise ValueError("SDK adapter is missing callable reference.")
    normalized = ref
    if normalized.startswith("module:"):
        normalized = normalized[len("module:") :]
    if ":" not in normalized:
        raise ValueError("SDK callable ref must look like module.path:callable_name")
    module_name, callable_name = normalized.rsplit(":", 1)
    module = importlib.import_module(module_name)
    target = getattr(module, callable_name, None)
    if target is None:
        raise ValueError(f"SDK callable '{callable_name}' not found in '{module_name}'")
    return target


class ExternalAdapterExecution:
    def __init__(
        self,
        *,
        mcp_manager: object | None,
        environment_service: object | None,
    ) -> None:
        self._mcp_manager = mcp_manager
        self._environment_service = environment_service

    def set_mcp_manager(self, mcp_manager: object | None) -> None:
        self._mcp_manager = mcp_manager

    def set_environment_service(self, environment_service: object | None) -> None:
        self._environment_service = environment_service

    async def execute_action(
        self,
        *,
        mount: CapabilityMount,
        action_id: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, object]:
        contract = _adapter_contract(mount)
        transport_kind = _string(contract.get("transport_kind"))
        action = _resolve_action(contract, action_id)
        if transport_kind is None or action is None:
            message = (
                f"External capability '{mount.id}' is not a formal adapter action surface."
            )
            return {
                "success": False,
                "summary": message,
                "error": message,
            }
        resolved_payload = dict(payload or {})
        transport_action_ref = _string(action.get("transport_action_ref")) or action_id
        if transport_kind == "mcp":
            return await self._execute_mcp_action(
                contract=contract,
                action_id=action_id,
                transport_action_ref=transport_action_ref,
                payload=resolved_payload,
            )
        if transport_kind == "http":
            return await self._execute_http_action(
                contract=contract,
                action_id=action_id,
                transport_action_ref=transport_action_ref,
                payload=resolved_payload,
            )
        if transport_kind == "sdk":
            return await self._execute_sdk_action(
                contract=contract,
                action_id=action_id,
                transport_action_ref=transport_action_ref,
                payload=resolved_payload,
            )
        message = f"Unsupported adapter transport '{transport_kind}'."
        return {"success": False, "summary": message, "error": message}

    async def _execute_mcp_action(
        self,
        *,
        contract: dict[str, Any],
        action_id: str,
        transport_action_ref: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        if self._mcp_manager is None:
            return {
                "success": False,
                "summary": "MCP manager is not available.",
                "error": "MCP manager is not available.",
            }
        client_key = _mcp_client_key(_string(contract.get("call_surface_ref")))
        if client_key is None:
            return {
                "success": False,
                "summary": "Adapter MCP client key is missing.",
                "error": "Adapter MCP client key is missing.",
            }
        client = await self._mcp_manager.get_client(client_key)
        if client is None:
            return {
                "success": False,
                "summary": f"MCP client '{client_key}' not found or not connected.",
                "error": f"MCP client '{client_key}' not found or not connected.",
            }
        callable_fn = await client.get_callable_function(
            transport_action_ref,
            wrap_tool_result=True,
            execution_timeout=None,
        )
        response = await callable_fn(**payload)
        summary = _tool_response_summary(response)
        success = _tool_response_success(response)
        response_payload = _tool_response_payload(response)
        return {
            "success": success,
            "summary": summary,
            "adapter_action": action_id,
            "transport_kind": "mcp",
            "client_key": client_key,
            "tool_name": transport_action_ref,
            "output": response_payload,
            "error": None if success else summary,
        }

    async def _execute_http_action(
        self,
        *,
        contract: dict[str, Any],
        action_id: str,
        transport_action_ref: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        base_url = _string(contract.get("call_surface_ref"))
        if base_url is None:
            return {
                "success": False,
                "summary": "HTTP adapter base URL is missing.",
                "error": "HTTP adapter base URL is missing.",
            }
        success, summary, output = await __import__("asyncio").to_thread(
            _http_request,
            base_url=base_url,
            transport_action_ref=transport_action_ref,
            payload=payload,
        )
        return {
            "success": success,
            "summary": summary,
            "adapter_action": action_id,
            "transport_kind": "http",
            "output": output,
            "error": None if success else summary,
        }

    async def _execute_sdk_action(
        self,
        *,
        contract: dict[str, Any],
        action_id: str,
        transport_action_ref: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        try:
            callable_fn = _resolve_sdk_callable(
                _string(contract.get("call_surface_ref")),
                transport_action_ref,
            )
            result = callable_fn(**payload)
            if hasattr(result, "__await__"):
                result = await result
            return {
                "success": True,
                "summary": f"Executed SDK adapter action '{action_id}'.",
                "adapter_action": action_id,
                "transport_kind": "sdk",
                "output": result,
                "error": None,
            }
        except Exception as exc:  # pragma: no cover - defensive boundary
            return {
                "success": False,
                "summary": str(exc),
                "adapter_action": action_id,
                "transport_kind": "sdk",
                "error": str(exc),
            }


__all__ = ["ExternalAdapterExecution"]
