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


def test_cli_runtime_surface_is_not_adapter_eligible() -> None:
    surface = classify_external_protocol_surface(
        metadata={"execute_command": "python -m donor_app"},
    )

    assert surface.protocol_surface_kind == "cli_runtime"
    assert surface.formal_adapter_eligible is False
    assert "no-stable-callable-surface" in surface.blockers
