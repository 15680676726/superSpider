# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from copaw.agents.react_agent import (
    _wrap_tool_function_for_toolkit,
    bind_tool_execution_delegate,
    bind_tool_preflight,
)
from copaw.agents.tools import execute_shell_command, get_current_time, read_file
from agentscope.tool import Toolkit


def test_wrap_tool_function_for_toolkit_coerces_async_dict_result() -> None:
    async def legacy_tool() -> dict[str, object]:
        return {"success": True, "summary": "delegated"}

    wrapped = _wrap_tool_function_for_toolkit(legacy_tool)
    response = asyncio.run(wrapped())

    assert isinstance(response, ToolResponse)
    assert '"success": true' in response.content[0]["text"]
    assert '"summary": "delegated"' in response.content[0]["text"]


def test_wrap_tool_function_for_toolkit_preserves_tool_response() -> None:
    expected = ToolResponse(
        content=[TextBlock(type="text", text="ok")],
    )

    async def modern_tool() -> ToolResponse:
        return expected

    wrapped = _wrap_tool_function_for_toolkit(modern_tool)
    response = asyncio.run(wrapped())

    assert response is expected


def test_wrap_tool_function_for_toolkit_can_skip_preflight_for_system_tools() -> None:
    async def system_tool() -> dict[str, object]:
        return {"success": True, "summary": "delegated"}

    wrapped = _wrap_tool_function_for_toolkit(
        system_tool,
        apply_preflight=False,
    )

    with bind_tool_preflight(
        lambda tool_name: ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"blocked:{tool_name}",
                ),
            ],
        ),
    ):
        response = asyncio.run(wrapped())

    assert isinstance(response, ToolResponse)
    assert '"success": true' in response.content[0]["text"]
    assert "blocked:system_tool" not in response.content[0]["text"]


def test_wrap_tool_function_for_toolkit_delegates_builtin_tools_to_bound_frontdoor() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def _delegate(capability_id: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((capability_id, dict(payload)))
        return {"success": True, "summary": "delegated-via-capability-frontdoor"}

    wrapped = _wrap_tool_function_for_toolkit(read_file)

    with bind_tool_execution_delegate(_delegate):
        response = asyncio.run(wrapped(file_path="notes.txt"))

    assert calls == [("tool:read_file", {"file_path": "notes.txt"})]
    assert response.content[0]["text"] == "delegated-via-capability-frontdoor"


def test_wrap_tool_function_for_toolkit_surfaces_delegate_failure_without_builtin_fallback() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def _delegate(capability_id: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((capability_id, dict(payload)))
        raise RuntimeError("delegate-unavailable")

    wrapped = _wrap_tool_function_for_toolkit(get_current_time)

    with bind_tool_execution_delegate(_delegate):
        response = asyncio.run(wrapped())

    assert calls == [("tool:get_current_time", {})]
    assert isinstance(response, ToolResponse)
    assert response.content
    assert "delegate-unavailable" in response.content[0]["text"]


def test_wrap_tool_function_for_toolkit_runs_preflight_before_delegate() -> None:
    delegate_calls: list[tuple[str, dict[str, object]]] = []

    async def _delegate(capability_id: str, payload: dict[str, object]) -> dict[str, object]:
        delegate_calls.append((capability_id, dict(payload)))
        return {"success": True, "summary": "delegated"}

    wrapped = _wrap_tool_function_for_toolkit(read_file)

    with bind_tool_execution_delegate(_delegate):
        with bind_tool_preflight(
            lambda tool_name, *_args, **_kwargs: ToolResponse(
                content=[TextBlock(type="text", text=f"blocked:{tool_name}")],
            ),
        ):
            response = asyncio.run(wrapped(file_path="blocked.txt"))

    assert response.content[0]["text"] == "blocked:read_file"
    assert delegate_calls == []


def test_shell_tool_schema_does_not_expose_path_format() -> None:
    toolkit = Toolkit()
    toolkit.register_tool_function(
        _wrap_tool_function_for_toolkit(execute_shell_command),
    )

    schema = toolkit.get_json_schemas()[0]["function"]["parameters"]["properties"]["cwd"]
    variants = list(schema.get("anyOf") or [])

    assert variants
    assert all(
        not (
            isinstance(item, dict)
            and item.get("type") == "string"
            and item.get("format") == "path"
        )
        for item in variants
    )
