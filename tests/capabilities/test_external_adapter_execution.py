# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.capabilities.external_adapter_execution import ExternalAdapterExecution
from copaw.capabilities.models import CapabilityMount


class _FakeMCPClient:
    def __init__(self) -> None:
        self.execution_timeout: float | None = None

    async def get_callable_function(
        self,
        tool_name: str,
        wrap_tool_result: bool = True,
        execution_timeout: float | None = None,
    ):
        self.execution_timeout = execution_timeout

        async def _callable(**tool_args):
            return {
                "success": True,
                "summary": f"Ran {tool_name} with {tool_args}",
                "wrap_tool_result": wrap_tool_result,
                "execution_timeout": execution_timeout,
            }

        return _callable


class _FakeMCPManager:
    def __init__(self, client: _FakeMCPClient | None = None) -> None:
        self._client = client or _FakeMCPClient()

    async def get_client(self, client_key: str):
        if client_key == "openspace":
            return self._client
        return None


class _FakeEphemeralMCPManager:
    def __init__(self) -> None:
        self._client = _FakeMCPClient()
        self.replace_calls: list[tuple[str, object, float]] = []
        self.closed = False

    async def replace_client(self, key: str, client_config, timeout: float = 60.0) -> None:
        self.replace_calls.append((key, client_config, timeout))

    async def get_client(self, client_key: str):
        if client_key == "adapter-stdio-probe":
            return self._client
        return None

    async def close_all(self) -> None:
        self.closed = True


class _FakeRuntimeProviderFacade:
    def __init__(self, *, contract: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self._contract = dict(contract or {})
        self._error = error

    def resolve_runtime_provider_contract(self) -> dict[str, object]:
        if self._error is not None:
            raise self._error
        return dict(self._contract)


class _SlowMCPClient(_FakeMCPClient):
    async def get_callable_function(
        self,
        tool_name: str,
        wrap_tool_result: bool = True,
        execution_timeout: float | None = None,
    ):
        self.execution_timeout = execution_timeout

        async def _callable(**tool_args):
            await asyncio.sleep(1.1)
            return {
                "success": True,
                "summary": f"Ran {tool_name} with {tool_args}",
            }

        return _callable


def _build_mount() -> CapabilityMount:
    return CapabilityMount(
        id="adapter:openspace",
        name="openspace",
        summary="Governed external adapter compiled into formal CoPaw business actions.",
        kind="adapter",
        source_kind="adapter",
        risk_level="guarded",
        metadata={
            "adapter_contract": {
                "compiled_adapter_id": "adapter:openspace",
                "transport_kind": "mcp",
                "call_surface_ref": "mcp:openspace",
                "actions": [
                    {
                        "action_id": "execute_task",
                        "transport_action_ref": "execute_task",
                        "input_schema": {"type": "object"},
                        "output_schema": {},
                    },
                ],
            },
        },
    )


def test_compiled_mcp_adapter_action_calls_bound_transport() -> None:
    manager = _FakeMCPManager()
    execution = ExternalAdapterExecution(
        mcp_manager=manager,
        environment_service=None,
    )

    result = asyncio.run(
        execution.execute_action(
            mount=_build_mount(),
            action_id="execute_task",
            payload={"task": "hello"},
        ),
    )

    assert result["success"] is True
    assert result["adapter_action"] == "execute_task"
    assert result["transport_kind"] == "mcp"
    assert result["summary"] == "Ran execute_task with {'task': 'hello'}"
    assert manager._client.execution_timeout == 120.0


def test_compiled_mcp_adapter_action_threads_execution_envelope_timeout() -> None:
    manager = _FakeMCPManager()
    mount = _build_mount().model_copy(
        update={
            "metadata": {
                **dict(_build_mount().metadata or {}),
                "execution_envelope": {
                    "action_timeout_sec": 7,
                },
            },
        },
    )
    execution = ExternalAdapterExecution(
        mcp_manager=manager,
        environment_service=None,
    )

    result = asyncio.run(
        execution.execute_action(
            mount=mount,
            action_id="execute_task",
            payload={"task": "hello"},
        ),
    )

    assert result["success"] is True
    assert manager._client.execution_timeout == 7


def test_external_adapter_execution_times_out_hanging_mcp_action() -> None:
    manager = _FakeMCPManager(client=_SlowMCPClient())
    mount = _build_mount().model_copy(
        update={
            "metadata": {
                **dict(_build_mount().metadata or {}),
                "execution_envelope": {
                    "action_timeout_sec": 1,
                    "heartbeat_interval_sec": 1,
                },
            },
        },
    )
    execution = ExternalAdapterExecution(
        mcp_manager=manager,
        environment_service=None,
    )

    result = asyncio.run(
        execution.execute_action(
            mount=mount,
            action_id="execute_task",
            payload={"task": "hello"},
        ),
    )

    assert result["success"] is False
    assert result["error_type"] == "timeout_error"
    assert result["outcome"] == "timeout"
    assert result["heartbeat_count"] >= 1


def test_compiled_script_mcp_adapter_action_uses_ephemeral_stdio_client(
    monkeypatch,
) -> None:
    execution = ExternalAdapterExecution(
        mcp_manager=None,
        environment_service=None,
    )
    temp_manager = _FakeEphemeralMCPManager()
    monkeypatch.setattr(
        "copaw.capabilities.external_adapter_execution.MCPClientManager",
        lambda: temp_manager,
    )
    monkeypatch.setattr(
        "copaw.capabilities.external_adapter_execution._resolve_script_command_path",
        lambda script_name, *, scripts_dir: f"{scripts_dir}/{script_name}.exe",
    )
    mount = CapabilityMount(
        id="adapter:openspace",
        name="openspace",
        summary="Governed external adapter compiled into formal CoPaw business actions.",
        kind="adapter",
        source_kind="adapter",
        risk_level="guarded",
        metadata={
            "scripts_dir": "D:/fake/.venv/Scripts",
            "adapter_contract": {
                "compiled_adapter_id": "adapter:openspace",
                "transport_kind": "mcp",
                "call_surface_ref": "script:openspace-mcp",
                "actions": [
                    {
                        "action_id": "execute_task",
                        "transport_action_ref": "execute_task",
                        "input_schema": {"type": "object"},
                        "output_schema": {},
                    },
                ],
            },
        },
    )

    result = asyncio.run(
        execution.execute_action(
            mount=mount,
            action_id="execute_task",
            payload={"task": "hello"},
        ),
    )

    assert result["success"] is True
    assert result["transport_kind"] == "mcp"
    assert result["tool_name"] == "execute_task"
    assert result["summary"] == "Ran execute_task with {'task': 'hello'}"
    assert temp_manager.closed is True
    assert len(temp_manager.replace_calls) == 1
    _, client_config, timeout = temp_manager.replace_calls[0]
    assert timeout == 30.0
    assert client_config.command.endswith("openspace-mcp.exe")


def test_external_adapter_execution_injects_provider_contract_before_stdio_launch(
    monkeypatch,
) -> None:
    temp_manager = _FakeEphemeralMCPManager()
    monkeypatch.setattr(
        "copaw.capabilities.external_adapter_execution.MCPClientManager",
        lambda: temp_manager,
    )
    monkeypatch.setattr(
        "copaw.capabilities.external_adapter_execution._resolve_script_command_path",
        lambda script_name, *, scripts_dir: f"{scripts_dir}/{script_name}.exe",
    )
    execution = ExternalAdapterExecution(
        mcp_manager=None,
        environment_service=None,
        provider_runtime_facade=_FakeRuntimeProviderFacade(
            contract={
                "provider_id": "openai",
                "provider_name": "OpenAI",
                "model": "gpt-5.2",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-live-secret",
                "auth_mode": "api_key",
                "provenance": {
                    "resolution_reason": "Using configured active model.",
                    "fallback_applied": False,
                    "unavailable_candidates": [],
                },
            },
        ),
    )
    mount = CapabilityMount(
        id="adapter:openspace",
        name="openspace",
        summary="Governed external adapter compiled into formal CoPaw business actions.",
        kind="adapter",
        source_kind="adapter",
        risk_level="guarded",
        provider_ref="github",
        metadata={
            "scripts_dir": "D:/fake/.venv/Scripts",
            "provider_injection_mode": "environment",
            "host_compatibility_requirements": {
                "required_provider_contract_kind": "cooperative_provider_runtime",
            },
            "adapter_contract": {
                "compiled_adapter_id": "adapter:openspace",
                "transport_kind": "mcp",
                "call_surface_ref": "script:openspace-mcp",
                "actions": [
                    {
                        "action_id": "execute_task",
                        "transport_action_ref": "execute_task",
                        "input_schema": {"type": "object"},
                        "output_schema": {},
                    },
                ],
            },
        },
    )

    result = asyncio.run(
        execution.execute_action(
            mount=mount,
            action_id="execute_task",
            payload={"task": "hello"},
        ),
    )

    assert result["success"] is True
    assert result["provider_injection"]["mode"] == "environment"
    assert result["provider_injection"]["provider"]["provider_id"] == "openai"
    assert (
        result["provider_injection"]["env"]["COPAW_PROVIDER_API_KEY"]
        != "sk-live-secret"
    )
    _, client_config, _ = temp_manager.replace_calls[0]
    assert client_config.env["COPAW_PROVIDER_ID"] == "openai"
    assert client_config.env["COPAW_PROVIDER_API_KEY"] == "sk-live-secret"


def test_external_adapter_execution_fails_fast_when_provider_contract_cannot_resolve(
    monkeypatch,
) -> None:
    temp_manager = _FakeEphemeralMCPManager()
    monkeypatch.setattr(
        "copaw.capabilities.external_adapter_execution.MCPClientManager",
        lambda: temp_manager,
    )
    monkeypatch.setattr(
        "copaw.capabilities.external_adapter_execution._resolve_script_command_path",
        lambda script_name, *, scripts_dir: f"{scripts_dir}/{script_name}.exe",
    )
    execution = ExternalAdapterExecution(
        mcp_manager=None,
        environment_service=None,
        provider_runtime_facade=_FakeRuntimeProviderFacade(
            error=ValueError("No active or fallback model configured."),
        ),
    )
    mount = CapabilityMount(
        id="adapter:openspace",
        name="openspace",
        summary="Governed external adapter compiled into formal CoPaw business actions.",
        kind="adapter",
        source_kind="adapter",
        risk_level="guarded",
        metadata={
            "scripts_dir": "D:/fake/.venv/Scripts",
            "provider_injection_mode": "environment",
            "host_compatibility_requirements": {
                "required_provider_contract_kind": "cooperative_provider_runtime",
            },
            "adapter_contract": {
                "compiled_adapter_id": "adapter:openspace",
                "transport_kind": "mcp",
                "call_surface_ref": "script:openspace-mcp",
                "actions": [
                    {
                        "action_id": "execute_task",
                        "transport_action_ref": "execute_task",
                        "input_schema": {"type": "object"},
                        "output_schema": {},
                    },
                ],
            },
        },
    )

    result = asyncio.run(
        execution.execute_action(
            mount=mount,
            action_id="execute_task",
            payload={"task": "hello"},
        ),
    )

    assert result["success"] is False
    assert result["error_type"] == "provider_resolution_error"
    assert result["provider_resolution_status"] == "failed"
    assert temp_manager.replace_calls == []
