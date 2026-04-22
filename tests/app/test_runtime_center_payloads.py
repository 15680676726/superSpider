# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.routers.runtime_center_payloads import (
    _actor_mailbox_payload,
    _actor_runtime_payload,
)


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


def test_actor_mailbox_payload_no_longer_emits_deleted_actor_mailbox_route() -> None:
    payload = _actor_mailbox_payload(
        {
            "id": "mailbox-1",
            "agent_id": "agent-1",
            "conversation_thread_id": "agent-chat:agent-1",
        },
    )

    assert payload["id"] == "mailbox-1"
    assert "route" not in payload
