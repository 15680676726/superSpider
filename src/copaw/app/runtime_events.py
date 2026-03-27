# -*- coding: utf-8 -*-
"""Runtime event bus for Runtime Center realtime updates."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class RuntimeEvent(BaseModel):
    event_id: int = Field(..., ge=1)
    topic: str
    action: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def event_name(self) -> str:
        return f"{self.topic}.{self.action}"


class RuntimeEventBus:
    """Small in-memory event bus with replay buffer and async waiting."""

    def __init__(self, *, max_events: int = 500) -> None:
        self._events: deque[RuntimeEvent] = deque(maxlen=max(50, max_events))
        self._next_event_id = 1
        self._condition = asyncio.Condition()

    def publish(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            event_id=self._next_event_id,
            topic=topic,
            action=action,
            payload=dict(payload or {}),
        )
        self._next_event_id += 1
        self._events.append(event)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return event
        loop.create_task(self._notify_waiters())
        return event

    def list_events(
        self,
        *,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[RuntimeEvent]:
        if limit <= 0:
            return []
        events = [event for event in self._events if event.event_id > after_id]
        return events[-limit:]

    async def wait_for_events(
        self,
        *,
        after_id: int = 0,
        timeout: float = 25.0,
        limit: int = 100,
    ) -> list[RuntimeEvent]:
        existing = self.list_events(after_id=after_id, limit=limit)
        if existing:
            return existing
        async with self._condition:
            existing = self.list_events(after_id=after_id, limit=limit)
            if existing:
                return existing
            try:
                await asyncio.wait_for(self._condition.wait(), timeout=max(1.0, timeout))
            except TimeoutError:
                return []
        return self.list_events(after_id=after_id, limit=limit)

    async def _notify_waiters(self) -> None:
        async with self._condition:
            self._condition.notify_all()


__all__ = ["RuntimeEvent", "RuntimeEventBus"]
