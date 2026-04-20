# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.capabilities.external_adapter_contracts import (
    ExecutorProtocolSurface,
    derive_executor_surface,
    protocol_surface_from_metadata,
    protocol_surface_metadata,
)


def test_executor_protocol_surface_supports_app_server() -> None:
    surface = derive_executor_surface(
        metadata={
            "app_server_ref": "codex-app-server",
            "app_server_actions": [
                {
                    "action_id": "thread/start",
                    "callable_ref": "thread/start",
                    "input_schema": {"type": "object"},
                },
            ],
            "event_stream_supported": True,
            "thread_turn_control_supported": True,
            "runtime_provider_contract_kind": "runtime_provider",
        },
    )

    assert surface.protocol_surface_kind == "app_server"
    assert surface.transport_kind == "sdk"
    assert surface.call_surface_ref == "codex-app-server"
    assert surface.formal_adapter_eligible is True
    assert surface.hints["lifecycle_contract_kind"] == "thread_turn_control"
    assert surface.hints["event_return_path"] == "event_stream"
    assert surface.hints["runtime_provider_contract_kind"] == "runtime_provider"


def test_executor_protocol_surface_round_trips_app_server_metadata() -> None:
    surface = ExecutorProtocolSurface(
        protocol_surface_kind="app_server",
        transport_kind="sdk",
        call_surface_ref="codex-app-server",
        formal_adapter_eligible=True,
        hints={
            "actions": [{"action_id": "turn/start", "callable_ref": "turn/start"}],
            "event_return_path": "event_stream",
            "lifecycle_contract_kind": "thread_turn_control",
        },
    )

    restored = protocol_surface_from_metadata(protocol_surface_metadata(surface))

    assert restored is not None
    assert restored.protocol_surface_kind == "app_server"
    assert restored.transport_kind == "sdk"
    assert restored.hints["event_return_path"] == "event_stream"


def test_cli_runtime_without_event_contract_is_not_formal_executor() -> None:
    payload = derive_executor_surface({"execute_command": "python -m tool"})

    assert payload.protocol_surface_kind == "cli_runtime"
    assert payload.formal_adapter_eligible is False
    assert "no-stable-callable-surface" in payload.blockers
