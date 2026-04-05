# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.capabilities.external_adapter_compiler import (
    compile_external_adapter_contract,
)
from copaw.capabilities.external_adapter_contracts import ExternalProtocolSurface


def test_native_mcp_surface_compiles_into_formal_adapter_contract() -> None:
    contract = compile_external_adapter_contract(
        capability_id="adapter:demo",
        surface=ExternalProtocolSurface(
            protocol_surface_kind="native_mcp",
            transport_kind="mcp",
            call_surface_ref="mcp:demo",
            formal_adapter_eligible=True,
            hints={
                "actions": [
                    {
                        "action_id": "execute_task",
                        "tool_name": "execute_task",
                        "input_schema": {"type": "object"},
                    },
                ],
            },
        ),
    )

    assert contract is not None
    assert contract.transport_kind == "mcp"
    assert contract.actions[0].action_id == "execute_task"
    assert contract.actions[0].transport_action_ref == "execute_task"


def test_cli_runtime_only_surface_is_blocked_from_adapter_compilation() -> None:
    blocked = compile_external_adapter_contract(
        capability_id="adapter:demo",
        surface=ExternalProtocolSurface(protocol_surface_kind="cli_runtime"),
    )

    assert blocked is None
