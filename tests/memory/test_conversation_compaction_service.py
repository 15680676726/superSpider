from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from copaw.memory import conversation_compaction_service as service_module
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


def test_conversation_compaction_service_init_does_not_eagerly_create_token_counter(
    monkeypatch,
    tmp_path,
) -> None:
    original_reme_init = service_module.ReMeLight.__init__

    def fake_reme_init(self, *args, **kwargs) -> None:
        self.service_context = SimpleNamespace(
            service_config=SimpleNamespace(file_watchers={}),
        )

    def fail_token_counter():
        raise AssertionError("token counter should stay lazy during service init")

    monkeypatch.setattr(service_module.ReMeLight, "__init__", fake_reme_init)
    monkeypatch.setattr(service_module, "_get_token_counter", fail_token_counter)

    try:
        service = service_module.ConversationCompactionService(working_dir=str(tmp_path))
    finally:
        monkeypatch.setattr(service_module.ReMeLight, "__init__", original_reme_init)

    assert getattr(service, "_token_counter", None) is None


def test_conversation_compaction_service_init_clears_embedding_runtime_config(
    monkeypatch,
    tmp_path,
) -> None:
    original_reme_init = service_module.ReMeLight.__init__

    def fake_reme_init(self, *args, **kwargs) -> None:
        self.service_context = SimpleNamespace(
            service_config=SimpleNamespace(
                file_watchers={},
                embedding_models={"default": SimpleNamespace(name="cfg-embedding")},
            ),
            embedding_models={"default": SimpleNamespace(name="runtime-embedding")},
        )

    monkeypatch.setattr(service_module.ReMeLight, "__init__", fake_reme_init)
    monkeypatch.setattr(service_module, "_get_token_counter", lambda: object())

    try:
        service = service_module.ConversationCompactionService(working_dir=str(tmp_path))
    finally:
        monkeypatch.setattr(service_module.ReMeLight, "__init__", original_reme_init)

    assert service.service_context.service_config.embedding_models == {}
    assert service.service_context.embedding_models == {"default": None}


@pytest.mark.asyncio
async def test_conversation_compaction_service_memory_search_uses_lexical_file_scan(
    tmp_path,
) -> None:
    memory_root = tmp_path / "memory"
    memory_root.mkdir()
    (tmp_path / "MEMORY.md").write_text(
        "# Runtime Notes\nDesign direction uses calm editorial layout.\n",
        encoding="utf-8",
    )
    (memory_root / "handoff.md").write_text(
        "OpenSpace integration uses direct API capability, no page clicking.\n",
        encoding="utf-8",
    )

    service = object.__new__(ConversationCompactionService)
    service.working_path = tmp_path
    service.memory_path = memory_root

    response = await service.memory_search(
        query="OpenSpace API capability",
        max_results=3,
        min_score=0.2,
    )

    assert response.content
    rendered = "\n".join(
        str(block.get("text", ""))
        for block in response.content
        if isinstance(block, dict)
    )
    assert "handoff.md" in rendered
    assert "OpenSpace integration uses direct API capability" in rendered
