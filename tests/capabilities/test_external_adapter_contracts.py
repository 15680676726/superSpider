# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.capabilities.external_adapter_contracts import (
    classify_external_protocol_surface,
)


def test_native_mcp_surface_is_adapter_eligible() -> None:
    surface = classify_external_protocol_surface(
        metadata={
            "mcp_server_ref": "mcp:openspace",
            "mcp_tools": [
                {
                    "name": "execute_task",
                    "input_schema": {"type": "object"},
                },
            ],
        },
    )

    assert surface.protocol_surface_kind == "native_mcp"
    assert surface.transport_kind == "mcp"
    assert surface.formal_adapter_eligible is True
    assert surface.call_surface_ref == "mcp:openspace"


def test_native_mcp_surface_without_tools_does_not_crash() -> None:
    surface = classify_external_protocol_surface(
        metadata={
            "mcp_server_ref": "script:openspace-mcp",
        },
    )

    assert surface.protocol_surface_kind == "native_mcp"
    assert surface.transport_kind == "mcp"
    assert surface.formal_adapter_eligible is False
    assert "no-typed-action-surface" in surface.blockers
    assert surface.hints["actions"] == []


def test_mcp_surface_without_tools_falls_back_to_sdk_when_sdk_actions_exist() -> None:
    surface = classify_external_protocol_surface(
        metadata={
            "mcp_server_ref": "script:openspace-mcp",
            "sdk_entry_ref": "module:openspace",
            "sdk_actions": [
                {
                    "action_id": "OpenSpace.execute",
                    "callable_ref": "module:openspace:OpenSpace.execute",
                    "input_schema": {"type": "object"},
                },
            ],
        },
    )

    assert surface.protocol_surface_kind == "sdk"
    assert surface.transport_kind == "sdk"
    assert surface.formal_adapter_eligible is True
    assert surface.call_surface_ref == "module:openspace"
    assert surface.hints["actions"][0]["action_id"] == "OpenSpace.execute"


def test_cli_runtime_surface_is_not_adapter_eligible() -> None:
    surface = classify_external_protocol_surface(
        metadata={"execute_command": "python -m donor_app"},
    )

    assert surface.protocol_surface_kind == "cli_runtime"
    assert surface.formal_adapter_eligible is False
    assert "no-stable-callable-surface" in surface.blockers
