# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.capabilities.external_adapter_execution import ExternalAdapterExecution
from copaw.capabilities.models import CapabilityMount


class _FakeMCPClient:
    async def get_callable_function(
        self,
        tool_name: str,
        wrap_tool_result: bool = True,
        execution_timeout: float | None = None,
    ):
        async def _callable(**tool_args):
            return {
                "success": True,
                "summary": f"Ran {tool_name} with {tool_args}",
                "wrap_tool_result": wrap_tool_result,
                "execution_timeout": execution_timeout,
            }

        return _callable


class _FakeMCPManager:
    async def get_client(self, client_key: str):
        if client_key == "openspace":
            return _FakeMCPClient()
        return None


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
    execution = ExternalAdapterExecution(
        mcp_manager=_FakeMCPManager(),
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
