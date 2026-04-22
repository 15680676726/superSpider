# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.routers import runtime_center_payloads as runtime_center_payloads_module
from copaw.app.routers.runtime_center_payloads import _actor_runtime_payload


def test_actor_runtime_payload_no_longer_emits_actor_read_routes() -> None:
    payload = _actor_runtime_payload(
        {
            "agent_id": "agent-1",
            "runtime_status": "idle",
        },
    )

    assert payload["agent_capabilities_route"] == "/api/runtime-center/agents/agent-1/capabilities"
    assert payload["routes"] == {
        "agent_capabilities": "/api/runtime-center/agents/agent-1/capabilities",
    }


def test_runtime_center_payloads_drop_actor_mailbox_payload_helper() -> None:
    assert not hasattr(runtime_center_payloads_module, "_actor_mailbox_payload")
