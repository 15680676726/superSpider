# -*- coding: utf-8 -*-
"""Formal runtime thread models and session-backed history reader."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentscope.memory import InMemoryMemory
from agentscope_runtime.engine.schemas.agent_schemas import Message
from pydantic import BaseModel, Field

from .channels.schema import DEFAULT_CHANNEL
from .runtime_agentscope import agentscope_msg_to_message


class RuntimeThreadSpec(BaseModel):
    """Formal runtime thread identity used by chat/runtime surfaces."""

    id: str = Field(min_length=1)
    name: str = Field(default="New Thread")
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    channel: str = Field(default=DEFAULT_CHANNEL)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, Any] = Field(default_factory=dict)


class RuntimeThreadHistory(BaseModel):
    """Recovered runtime thread message history."""

    messages: list[Message] = Field(default_factory=list)


class SessionRuntimeThreadHistoryReader:
    """Read runtime thread history directly from canonical session snapshots."""

    def __init__(self, *, session_backend: object | None = None) -> None:
        self._session_backend = session_backend

    async def get_thread_history(
        self,
        thread_spec: RuntimeThreadSpec,
    ) -> RuntimeThreadHistory:
        payload = await self._load_session_payload(
            session_id=thread_spec.session_id,
            user_id=thread_spec.user_id,
        )
        if not payload:
            return RuntimeThreadHistory(messages=[])

        memories = payload.get("agent", {}).get("memory", {})
        if isinstance(memories, list):
            memories = {"content": memories}
        if not isinstance(memories, dict) or not memories:
            return RuntimeThreadHistory(messages=[])

        memory = InMemoryMemory()
        memory.load_state_dict(memories)
        messages = agentscope_msg_to_message(await memory.get_memory())
        return RuntimeThreadHistory(messages=messages)

    async def _load_session_payload(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        backend = self._session_backend
        if backend is None:
            return None

        snapshot_loader = getattr(backend, "load_session_snapshot", None)
        if callable(snapshot_loader):
            payload = snapshot_loader(
                session_id=session_id,
                user_id=user_id,
                allow_not_exist=True,
            )
            return payload if isinstance(payload, dict) else None

        payload_loader = getattr(backend, "load_session_payload", None)
        if callable(payload_loader):
            payload = await payload_loader(
                session_id=session_id,
                user_id=user_id,
            )
            return payload if isinstance(payload, dict) else None

        return None
