from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from copaw.memory.conversation_compaction_service import ConversationCompactionService


class _HangingFileWatcher:
    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._watch_task = asyncio.create_task(self._run(), name="hanging-file-watcher")
        self._running = True

    async def _run(self) -> None:
        await asyncio.Event().wait()

    async def close(self) -> None:
        self._stop_event.set()
        if self._watch_task is not None:
            await self._watch_task
        self._running = False


class _CancelledFileWatcher:
    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._watch_task = asyncio.create_task(self._run(), name="cancelled-file-watcher")
        self._running = True

    async def _run(self) -> None:
        await asyncio.Event().wait()

    async def close(self) -> None:
        raise asyncio.CancelledError()


class _SelfCancellingFileWatcher:
    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._watch_task = asyncio.create_task(
            self._run(),
            name="self-cancelling-file-watcher",
        )
        self._running = True

    async def _run(self) -> None:
        await asyncio.Event().wait()

    async def close(self) -> None:
        current = asyncio.current_task()
        if current is not None:
            current.cancel()
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_conversation_compaction_service_close_force_stops_hanging_file_watcher() -> None:
    service = object.__new__(ConversationCompactionService)
    watcher = _HangingFileWatcher()
    cleanup_events: list[str] = []
    service._started = True
    service._close_timeout_seconds = 0.01
    service.service_context = SimpleNamespace(
        vector_stores={},
        file_stores={},
        file_watchers={"default": watcher},
        llms={},
        embedding_models={},
    )
    service._cleanup_tool_results = lambda: cleanup_events.append("cleanup")
    service.shutdown_thread_pool = lambda: cleanup_events.append("thread-pool")
    service.shutdown_ray = lambda: cleanup_events.append("ray")

    result = await asyncio.wait_for(service.close(), timeout=0.2)

    assert result is False
    assert watcher._stop_event.is_set() is True
    assert watcher._running is False
    assert watcher._watch_task.done() is True
    assert cleanup_events == ["cleanup", "thread-pool", "ray"]


@pytest.mark.asyncio
async def test_conversation_compaction_service_close_absorbs_cancelled_file_watcher() -> None:
    service = object.__new__(ConversationCompactionService)
    watcher = _CancelledFileWatcher()
    cleanup_events: list[str] = []
    service._started = True
    service._close_timeout_seconds = 0.01
    service.service_context = SimpleNamespace(
        vector_stores={},
        file_stores={},
        file_watchers={"default": watcher},
        llms={},
        embedding_models={},
    )
    service._cleanup_tool_results = lambda: cleanup_events.append("cleanup")
    service.shutdown_thread_pool = lambda: cleanup_events.append("thread-pool")
    service.shutdown_ray = lambda: cleanup_events.append("ray")

    result = await asyncio.wait_for(service.close(), timeout=0.2)

    assert result is False
    assert watcher._stop_event.is_set() is True
    assert watcher._running is False
    assert watcher._watch_task.done() is True
    assert cleanup_events == ["cleanup", "thread-pool", "ray"]


@pytest.mark.asyncio
async def test_conversation_compaction_service_close_clears_self_cancelled_watcher_residue() -> None:
    service = object.__new__(ConversationCompactionService)
    watcher = _SelfCancellingFileWatcher()
    cleanup_events: list[str] = []
    service._started = True
    service._close_timeout_seconds = 0.01
    service.service_context = SimpleNamespace(
        vector_stores={},
        file_stores={},
        file_watchers={"default": watcher},
        llms={},
        embedding_models={},
    )
    service._cleanup_tool_results = lambda: cleanup_events.append("cleanup")
    service.shutdown_thread_pool = lambda: cleanup_events.append("thread-pool")
    service.shutdown_ray = lambda: cleanup_events.append("ray")

    current = asyncio.current_task()
    assert current is not None
    assert current.cancelling() == 0

    try:
        result = await asyncio.wait_for(service.close(), timeout=0.2)
        assert result is False
        assert current.cancelling() == 0
        assert watcher._stop_event.is_set() is True
        assert watcher._running is False
        assert cleanup_events == ["cleanup", "thread-pool", "ray"]
    finally:
        uncancel = getattr(current, "uncancel", None)
        if callable(uncancel):
            while current.cancelling():
                uncancel()
