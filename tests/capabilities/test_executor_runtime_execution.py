# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.capabilities.external_adapter_compiler import compile_external_adapter_contract
from copaw.capabilities.external_adapter_contracts import ExecutorProtocolSurface


def test_formal_executor_app_server_surface_compiles_into_contract() -> None:
    contract = compile_external_adapter_contract(
        capability_id="executor:codex",
        surface=ExecutorProtocolSurface(
            protocol_surface_kind="app_server",
            transport_kind="sdk",
            call_surface_ref="codex-app-server",
            formal_adapter_eligible=True,
            hints={
                "actions": [
                    {
                        "action_id": "thread/start",
                        "callable_ref": "thread/start",
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                    },
                ],
                "event_return_path": "event_stream",
                "lifecycle_contract_kind": "thread_turn_control",
            },
        ),
    )

    assert contract is not None
    assert contract.transport_kind == "sdk"
    assert contract.call_surface_ref == "codex-app-server"
    assert contract.actions[0].action_id == "thread/start"
    assert contract.actions[0].transport_action_ref == "thread/start"


def test_cli_runtime_only_surface_does_not_compile_into_executor_contract() -> None:
    contract = compile_external_adapter_contract(
        capability_id="executor:cli",
        surface=ExecutorProtocolSurface(protocol_surface_kind="cli_runtime"),
    )

    assert contract is None
