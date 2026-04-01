# -*- coding: utf-8 -*-
"""Supervisor loop for resident actor workers."""
from __future__ import annotations

import asyncio
from typing import Any

from .actor_mailbox import ActorMailboxService
from .actor_worker import ActorWorker
from ..state.repositories import BaseAgentRuntimeRepository


class ActorSupervisor:
    """One resident supervisor drives all actor workers from a shared loop."""

    def __init__(
        self,
        *,
        runtime_repository: BaseAgentRuntimeRepository,
        mailbox_service: ActorMailboxService,
        worker: ActorWorker,
        runtime_event_bus: object | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._runtime_repository = runtime_repository
        self._mailbox_service = mailbox_service
        self._worker = worker
        self._runtime_event_bus = runtime_event_bus
        self._poll_interval_seconds = max(0.2, float(poll_interval_seconds))
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._agent_locks: dict[str, asyncio.Lock] = {}
        self._agent_tasks: dict[str, asyncio.Task[bool]] = {}

    async def start(self) -> None:
        if self._loop_task is not None and not self._loop_task.done():
            return
        self._stop_event = asyncio.Event()
        self._loop_task = asyncio.create_task(self._run_loop(), name="copaw-actor-supervisor")
        self._publish_runtime_event(topic="actor-supervisor", action="started", payload={})

    async def stop(self) -> None:
        self._stop_event.set()
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        running_tasks = [
            task
            for task in self._agent_tasks.values()
            if not task.done()
        ]
        for task in running_tasks:
            task.cancel()
        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)
        self._publish_runtime_event(topic="actor-supervisor", action="stopped", payload={})

    def mailbox_service(self) -> ActorMailboxService:
        return self._mailbox_service

    async def run_agent_once(self, agent_id: str) -> bool:
        lock = self._agent_locks.setdefault(agent_id, asyncio.Lock())
        if lock.locked():
            return False
        async with lock:
            existing = self._agent_tasks.get(agent_id)
            if existing is not None and not existing.done():
                return False
            task = asyncio.create_task(
                self._worker.run_once(agent_id),
                name=f"copaw-actor:{agent_id}",
            )
            self._agent_tasks[agent_id] = task
            try:
                return await task
            finally:
                if self._agent_tasks.get(agent_id) is task:
                    self._agent_tasks.pop(agent_id, None)

    async def run_poll_cycle(self) -> bool:
        agent_ids = [
            runtime.agent_id
            for runtime in self._runtime_repository.list_runtimes(limit=None)
            if runtime.desired_state == "active"
            and runtime.runtime_status != "retired"
            and (
                runtime.queue_depth > 0
                or runtime.runtime_status in {"queued", "claimed", "executing", "waiting", "running"}
            )
        ]
        if not agent_ids:
            return False
        results = await asyncio.gather(
            *(self.run_agent_once(agent_id) for agent_id in agent_ids),
        )
        return any(results)

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                ran_any = await self.run_poll_cycle()
                if not ran_any:
                    await asyncio.sleep(self._poll_interval_seconds)
        except asyncio.CancelledError:
            raise

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._runtime_event_bus is None:
            return
        self._runtime_event_bus.publish(topic=topic, action=action, payload=payload)
