# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..app.mcp.manager import MCPClientManager
from ..config.config import MCPClientConfig
from .donor_execution_envelope import run_donor_execution_envelope
from .donor_provider_injection import (
    _CONFIG_WRAPPER_ENV_KEY,
    build_donor_injection_payload,
    resolve_donor_provider_contract,
)
from .external_adapter_contracts import donor_execution_envelope_from_metadata
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
    return None


def _resolve_script_command_path(script_name: str, *, scripts_dir: str) -> str | None:
    normalized = _string(script_name)
    base_dir = _string(scripts_dir)
    if normalized is None or base_dir is None:
        return None
    normalized_base = base_dir.rstrip("/\\")
    for suffix in (".exe", "-script.py", ".cmd", ".bat", ""):
        candidate = f"{normalized_base}\\{normalized}{suffix}"
        try:
            with open(candidate, "rb"):
                return candidate
        except OSError:
            continue
    return None


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
    surface_ref = _string(call_surface_ref)
    if ":" in normalized:
        module_name, callable_name = normalized.split(":", 1)
    elif surface_ref is not None and surface_ref.startswith("module:"):
        module_name = surface_ref[len("module:") :]
        callable_name = normalized
    else:
        raise ValueError("SDK callable ref must look like module.path:callable_name")
    module = importlib.import_module(module_name)
    segments = [segment for segment in callable_name.split(".") if segment]
    target: object = module
    for index, segment in enumerate(segments):
        target = getattr(target, segment, None)
        if target is None:
            raise ValueError(
                f"SDK callable '{callable_name}' not found in '{module_name}'"
            )
        if inspect.isclass(target) and index < len(segments) - 1:
            signature = inspect.signature(target)
            required = [
                parameter
                for parameter in signature.parameters.values()
                if parameter.kind
                not in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
                and parameter.default is inspect._empty
            ]
            if required:
                raise ValueError(
                    f"SDK class '{target.__name__}' requires constructor arguments."
                )
            target = target()
    if not callable(target):
        raise ValueError(f"SDK callable '{callable_name}' is not callable.")
    return target


class ExternalAdapterExecution:
    def __init__(
        self,
        *,
        mcp_manager: object | None,
        environment_service: object | None,
        provider_runtime_facade: object | None = None,
    ) -> None:
        self._mcp_manager = mcp_manager
        self._environment_service = environment_service
        self._provider_runtime_facade = provider_runtime_facade

    def set_mcp_manager(self, mcp_manager: object | None) -> None:
        self._mcp_manager = mcp_manager

    def set_environment_service(self, environment_service: object | None) -> None:
        self._environment_service = environment_service

    def set_provider_runtime_facade(
        self,
        provider_runtime_facade: object | None,
    ) -> None:
        self._provider_runtime_facade = provider_runtime_facade

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
        execution_envelope = donor_execution_envelope_from_metadata(mount.metadata or {})
        provider_contract = resolve_donor_provider_contract(
            mount=mount,
            provider_runtime_facade=self._provider_runtime_facade,
        )
        provider_injection = build_donor_injection_payload(
            provider_contract=provider_contract,
        )
        if provider_injection.get("provider_resolution_status") == "failed":
            message = str(
                provider_injection.get("error")
                or "Failed to resolve donor provider contract.",
            )
            return {
                "success": False,
                "summary": message,
                "error": message,
                "error_type": provider_injection.get("error_type"),
                "provider_resolution_status": provider_injection.get(
                    "provider_resolution_status",
                ),
                "provider_injection": provider_injection.get("operator_payload"),
            }
        transport_action_ref = _string(action.get("transport_action_ref")) or action_id
        if transport_kind == "mcp":
            return await self._execute_mcp_action(
                mount=mount,
                contract=contract,
                action_id=action_id,
                transport_action_ref=transport_action_ref,
                payload=resolved_payload,
                provider_injection=provider_injection,
                execution_envelope=execution_envelope,
            )
        if transport_kind == "http":
            return await self._execute_http_action(
                contract=contract,
                action_id=action_id,
                transport_action_ref=transport_action_ref,
                payload=resolved_payload,
                provider_injection=provider_injection,
                execution_envelope=execution_envelope,
            )
        if transport_kind == "sdk":
            return await self._execute_sdk_action(
                contract=contract,
                action_id=action_id,
                transport_action_ref=transport_action_ref,
                payload=resolved_payload,
                provider_injection=provider_injection,
                execution_envelope=execution_envelope,
            )
        message = f"Unsupported adapter transport '{transport_kind}'."
        return {
            "success": False,
            "summary": message,
            "error": message,
            "provider_injection": provider_injection.get("operator_payload"),
        }

    async def _execute_mcp_action(
        self,
        *,
        mount: CapabilityMount,
        contract: dict[str, Any],
        action_id: str,
        transport_action_ref: str,
        payload: dict[str, Any],
        provider_injection: dict[str, Any],
        execution_envelope: object | None,
    ) -> dict[str, object]:
        call_surface_ref = _string(contract.get("call_surface_ref"))
        client_key = _mcp_client_key(call_surface_ref)
        temp_manager: MCPClientManager | None = None
        try:
            if client_key is not None:
                if self._mcp_manager is None:
                    return {
                        "success": False,
                        "summary": "MCP manager is not available.",
                        "error": "MCP manager is not available.",
                    }
                client = await self._mcp_manager.get_client(client_key)
            else:
                scripts_dir = _string((mount.metadata or {}).get("scripts_dir")) or ""
                python_path = _string((mount.metadata or {}).get("python_path"))
                environment_root = _string((mount.metadata or {}).get("environment_root")) or ""
                command: str | None = None
                args: list[str] = []
                if call_surface_ref is not None and call_surface_ref.startswith("script:"):
                    command = _resolve_script_command_path(
                        call_surface_ref.split(":", 1)[1],
                        scripts_dir=scripts_dir,
                    )
                elif call_surface_ref is not None and call_surface_ref.startswith("module:"):
                    module_name = call_surface_ref.split(":", 1)[1].strip()
                    if python_path is not None and module_name:
                        command = python_path
                        args = ["-m", module_name]
                if command is None:
                    return {
                        "success": False,
                        "summary": "Adapter MCP transport is missing a resolvable stdio command.",
                        "error": "Adapter MCP transport is missing a resolvable stdio command.",
                        "provider_injection": provider_injection.get("operator_payload"),
                    }
                temp_manager = MCPClientManager()
                client_key = "adapter-stdio-probe"
                launch_args = list(args)
                launch_env: dict[str, str] = {}
                injection_mode = _string(provider_injection.get("mode"))
                if injection_mode == "environment":
                    launch_env.update(
                        {
                            str(key): str(value)
                            for key, value in dict(provider_injection.get("env") or {}).items()
                            if str(key).strip() and str(value).strip()
                        },
                    )
                elif injection_mode == "argument":
                    launch_args.extend(
                        [
                            str(item)
                            for item in list(provider_injection.get("args") or [])
                            if str(item).strip()
                        ],
                    )
                elif injection_mode == "config_wrapper":
                    wrapper = dict(provider_injection.get("config_wrapper") or {})
                    if wrapper:
                        launch_env[_CONFIG_WRAPPER_ENV_KEY] = json.dumps(
                            wrapper,
                            ensure_ascii=False,
                        )
                await temp_manager.replace_client(
                    client_key,
                    MCPClientConfig(
                        name=mount.name or mount.id,
                        command=command,
                        args=launch_args,
                        env=launch_env,
                        cwd=environment_root,
                    ),
                    timeout=30.0,
                )
                client = await temp_manager.get_client(client_key)
            if client is None:
                return {
                    "success": False,
                    "summary": f"MCP client '{client_key}' not found or not connected.",
                    "error": f"MCP client '{client_key}' not found or not connected.",
                    "provider_injection": provider_injection.get("operator_payload"),
                }
            callable_fn = await client.get_callable_function(
                transport_action_ref,
                wrap_tool_result=True,
                execution_timeout=(
                    float(getattr(execution_envelope, "action_timeout_sec"))
                    if execution_envelope is not None
                    else None
                ),
            )
            envelope_result = await run_donor_execution_envelope(
                label=f"adapter:{mount.id}:{action_id}",
                awaitable_factory=lambda: callable_fn(**payload),
                action_timeout_sec=(
                    float(getattr(execution_envelope, "action_timeout_sec"))
                    if execution_envelope is not None
                    else None
                ),
                heartbeat_interval_sec=(
                    float(getattr(execution_envelope, "heartbeat_interval_sec"))
                    if execution_envelope is not None
                    else None
                ),
                heartbeat_snapshot_factory=lambda: {
                    "transport_kind": "mcp",
                    "adapter_action": action_id,
                },
                cancel_grace_sec=(
                    float(getattr(execution_envelope, "cancel_grace_sec"))
                    if execution_envelope is not None
                    else None
                ),
            )
            if not envelope_result.get("success"):
                return {
                    "success": False,
                    "summary": str(envelope_result.get("summary") or ""),
                    "adapter_action": action_id,
                    "transport_kind": "mcp",
                    "client_key": client_key,
                    "tool_name": transport_action_ref,
                    "output": envelope_result.get("output"),
                    "error": envelope_result.get("error"),
                    "error_type": envelope_result.get("error_type"),
                    "outcome": envelope_result.get("outcome"),
                    "heartbeat_count": envelope_result.get("heartbeat_count", 0),
                    "heartbeat_snapshots": envelope_result.get("heartbeat_snapshots") or [],
                    "provider_injection": provider_injection.get("operator_payload"),
                }
            response = envelope_result.get("output")
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
                "outcome": "succeeded" if success else "failed",
                "heartbeat_count": envelope_result.get("heartbeat_count", 0),
                "heartbeat_snapshots": envelope_result.get("heartbeat_snapshots") or [],
                "provider_injection": provider_injection.get("operator_payload"),
            }
        finally:
            if temp_manager is not None:
                await temp_manager.close_all()

    async def _execute_http_action(
        self,
        *,
        contract: dict[str, Any],
        action_id: str,
        transport_action_ref: str,
        payload: dict[str, Any],
        provider_injection: dict[str, Any],
        execution_envelope: object | None,
    ) -> dict[str, object]:
        base_url = _string(contract.get("call_surface_ref"))
        if base_url is None:
            return {
                "success": False,
                "summary": "HTTP adapter base URL is missing.",
                "error": "HTTP adapter base URL is missing.",
                "provider_injection": provider_injection.get("operator_payload"),
            }
        envelope_result = await run_donor_execution_envelope(
            label=f"http-adapter:{action_id}",
            awaitable_factory=lambda: asyncio.to_thread(
                _http_request,
                base_url=base_url,
                transport_action_ref=transport_action_ref,
                payload=payload,
            ),
            action_timeout_sec=(
                float(getattr(execution_envelope, "action_timeout_sec"))
                if execution_envelope is not None
                else None
            ),
            heartbeat_interval_sec=(
                float(getattr(execution_envelope, "heartbeat_interval_sec"))
                if execution_envelope is not None
                else None
            ),
            heartbeat_snapshot_factory=lambda: {
                "transport_kind": "http",
                "adapter_action": action_id,
            },
        )
        if not envelope_result.get("success"):
            return {
                "success": False,
                "summary": str(envelope_result.get("summary") or ""),
                "adapter_action": action_id,
                "transport_kind": "http",
                "output": envelope_result.get("output"),
                "error": envelope_result.get("error"),
                "error_type": envelope_result.get("error_type"),
                "outcome": envelope_result.get("outcome"),
                "heartbeat_count": envelope_result.get("heartbeat_count", 0),
                "heartbeat_snapshots": envelope_result.get("heartbeat_snapshots") or [],
                "provider_injection": provider_injection.get("operator_payload"),
            }
        success, summary, output = envelope_result.get("output") or (False, "", None)
        return {
            "success": success,
            "summary": summary,
            "adapter_action": action_id,
            "transport_kind": "http",
            "output": output,
            "error": None if success else summary,
            "outcome": "succeeded" if success else "failed",
            "heartbeat_count": envelope_result.get("heartbeat_count", 0),
            "heartbeat_snapshots": envelope_result.get("heartbeat_snapshots") or [],
            "provider_injection": provider_injection.get("operator_payload"),
        }

    async def _execute_sdk_action(
        self,
        *,
        contract: dict[str, Any],
        action_id: str,
        transport_action_ref: str,
        payload: dict[str, Any],
        provider_injection: dict[str, Any],
        execution_envelope: object | None,
    ) -> dict[str, object]:
        try:
            callable_fn = _resolve_sdk_callable(
                _string(contract.get("call_surface_ref")),
                transport_action_ref,
            )
            async def _invoke_sdk() -> object:
                result = callable_fn(**payload)
                if hasattr(result, "__await__"):
                    return await result
                return result

            envelope_result = await run_donor_execution_envelope(
                label=f"sdk-adapter:{action_id}",
                awaitable_factory=_invoke_sdk,
                action_timeout_sec=(
                    float(getattr(execution_envelope, "action_timeout_sec"))
                    if execution_envelope is not None
                    else None
                ),
                heartbeat_interval_sec=(
                    float(getattr(execution_envelope, "heartbeat_interval_sec"))
                    if execution_envelope is not None
                    else None
                ),
                heartbeat_snapshot_factory=lambda: {
                    "transport_kind": "sdk",
                    "adapter_action": action_id,
                },
            )
            if not envelope_result.get("success"):
                return {
                    "success": False,
                    "summary": str(envelope_result.get("summary") or ""),
                    "adapter_action": action_id,
                    "transport_kind": "sdk",
                    "output": envelope_result.get("output"),
                    "error": envelope_result.get("error"),
                    "error_type": envelope_result.get("error_type"),
                    "outcome": envelope_result.get("outcome"),
                    "heartbeat_count": envelope_result.get("heartbeat_count", 0),
                    "heartbeat_snapshots": envelope_result.get("heartbeat_snapshots") or [],
                    "provider_injection": provider_injection.get("operator_payload"),
                }
            return {
                "success": True,
                "summary": f"Executed SDK adapter action '{action_id}'.",
                "adapter_action": action_id,
                "transport_kind": "sdk",
                "output": envelope_result.get("output"),
                "error": None,
                "outcome": "succeeded",
                "heartbeat_count": envelope_result.get("heartbeat_count", 0),
                "heartbeat_snapshots": envelope_result.get("heartbeat_snapshots") or [],
                "provider_injection": provider_injection.get("operator_payload"),
            }
        except Exception as exc:  # pragma: no cover - defensive boundary
            return {
                "success": False,
                "summary": str(exc),
                "adapter_action": action_id,
                "transport_kind": "sdk",
                "error": str(exc),
                "provider_injection": provider_injection.get("operator_payload"),
            }


__all__ = ["ExternalAdapterExecution"]
