# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from copaw.agents.react_agent import (
    _wrap_tool_function_for_toolkit,
    bind_tool_preflight,
)


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
