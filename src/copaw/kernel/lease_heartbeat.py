# -*- coding: utf-8 -*-
"""Shared background heartbeat loop for long-running leased work."""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class LeaseHeartbeat:
    """Keep a lease alive while long-running work is in flight."""

    def __init__(
        self,
        *,
        label: str,
        heartbeat: Callable[[], Any],
        interval_seconds: float = 15.0,
    ) -> None:
        self._label = label
        self._heartbeat = heartbeat
        self._interval_seconds = max(0.01, float(interval_seconds))
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "LeaseHeartbeat":
        self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(
            self._run(),
            name=f"copaw-lease-heartbeat:{self._label}",
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def pulse(self) -> None:
        await self._call_heartbeat()

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval_seconds)
                await self._call_heartbeat()
        except asyncio.CancelledError:
            raise

    async def _call_heartbeat(self) -> None:
        async with self._lock:
            try:
                result = self._heartbeat()
                if inspect.isawaitable(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("%s heartbeat failed", self._label)
