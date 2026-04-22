# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.capabilities.system_actor_handlers import SystemActorCapabilityFacade


class _MailboxItem:
    def __init__(self, mailbox_id: str, agent_id: str) -> None:
        self.id = mailbox_id
        self.agent_id = agent_id
        self.conversation_thread_id = f"agent-chat:{agent_id}"

    def model_dump(self, mode: str = "json") -> dict[str, str]:
        _ = mode
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "conversation_thread_id": self.conversation_thread_id,
        }


class _MailboxService:
    def enqueue_item(self, **kwargs):
        return _MailboxItem("mailbox-1", kwargs["agent_id"])

    def get_item(self, mailbox_id: str):
        if mailbox_id != "mailbox-1":
            return None
        return _MailboxItem("mailbox-1", "agent-1")

    def retry_item(self, mailbox_id: str):
        return _MailboxItem(mailbox_id, "agent-1")


def test_system_actor_enqueue_result_no_longer_emits_deleted_mailbox_route() -> None:
    facade = SystemActorCapabilityFacade(actor_mailbox_service=_MailboxService())

    result = asyncio.run(
        facade.execute(
            "system:enqueue_task",
            {
                "agent_id": "agent-1",
                "title": "Queue actor work",
                "payload": {},
            },
        ),
    )

    assert result["success"] is True
    assert result["mailbox"]["id"] == "mailbox-1"
    assert "route" not in result


def test_system_actor_retry_result_no_longer_emits_deleted_mailbox_route() -> None:
    facade = SystemActorCapabilityFacade(actor_mailbox_service=_MailboxService())

    result = asyncio.run(
        facade.execute(
            "system:retry_actor_mailbox",
            {
                "agent_id": "agent-1",
                "mailbox_id": "mailbox-1",
            },
        ),
    )

    assert result["success"] is True
    assert result["mailbox"]["id"] == "mailbox-1"
    assert "route" not in result
