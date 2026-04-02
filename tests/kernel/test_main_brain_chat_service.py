# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agentscope.message import Msg, TextBlock, ThinkingBlock

import copaw.kernel.main_brain_chat_service as main_brain_chat_service_module
from copaw.kernel.main_brain_chat_service import MainBrainChatService
from copaw.kernel.main_brain_commit_service import MainBrainCommitService
from copaw.kernel.main_brain_turn_result import (
    MainBrainActionEnvelope,
    MainBrainCommitState,
    MainBrainTurnResult,
)
from copaw.memory.models import MemoryRecallHit, MemoryRecallResponse
from copaw.state import MemoryFactIndexRecord


class _FakeSessionBackend:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], dict] = {}
        self.save_calls: list[tuple[str, str, dict]] = []
        self.load_calls: list[tuple[str, str]] = []

    def load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        allow_not_exist: bool = False,
    ) -> dict:
        _ = allow_not_exist
        self.load_calls.append((session_id, user_id))
        return dict(self.snapshots.get((session_id, user_id), {}))

    def save_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        payload: dict,
        source_ref: str,
    ) -> None:
        _ = source_ref
        snapshot = dict(payload)
        self.snapshots[(session_id, user_id)] = snapshot
        self.save_calls.append((session_id, user_id, snapshot))


class _SnapshotInspectingModel:
    def __init__(self, backend: _FakeSessionBackend, *, session_id: str, user_id: str) -> None:
        self.backend = backend
        self.session_id = session_id
        self.user_id = user_id
        self.stream = True
        self.snapshot_during_call: dict | None = None

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        self.snapshot_during_call = self.backend.load_session_snapshot(
            session_id=self.session_id,
            user_id=self.user_id,
            allow_not_exist=True,
        )
        return SimpleNamespace(content="已收到，这轮先继续聊天。")


class _EmptyResponseModel:
    def __init__(self) -> None:
        self.stream = True
        self.calls: list[bool] = []

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        self.calls.append(bool(self.stream))
        return SimpleNamespace(content="")


class _StaticResponseModel:
    def __init__(self, text: str) -> None:
        self.text = text
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        return SimpleNamespace(content=self.text)


class _StructuredResponseModel:
    def __init__(self, result: MainBrainTurnResult) -> None:
        self.result = result
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        return self.result


class _PromptCapturingResponseModel:
    def __init__(self, text: str) -> None:
        self.text = text
        self.stream = True
        self.calls: list[list[dict[str, str]]] = []

    async def __call__(self, *, messages, **kwargs):
        _ = kwargs
        self.calls.append([dict(item) for item in messages])
        return SimpleNamespace(content=self.text)


class _StreamingResponseModel:
    def __init__(self, *parts: str) -> None:
        self.parts = list(parts)
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)

        async def _stream():
            accumulated = ""
            for part in self.parts:
                accumulated += part
                yield SimpleNamespace(content=accumulated)

        return _stream()


class _StreamingThinkingResponseModel:
    def __init__(self) -> None:
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)

        async def _stream():
            yield SimpleNamespace(
                content=[
                    ThinkingBlock(type="thinking", thinking="先整理约束"),
                    TextBlock(type="text", text="先看目标"),
                ],
            )
            yield SimpleNamespace(
                content=[
                    ThinkingBlock(type="thinking", thinking="先整理约束，再确认下一步"),
                    TextBlock(type="text", text="先看目标，再给你下一步"),
                ],
            )

        return _stream()


class _KeyErroringChunk:
    def __init__(self, *, content: str) -> None:
        self.content = content

    def __getattr__(self, name: str):
        if name == "reasoning_content":
            raise KeyError(name)
        raise AttributeError(name)


class _StreamingKeyErroringReasoningResponseModel:
    def __init__(self, *parts: str) -> None:
        self.parts = list(parts)
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)

        async def _stream():
            accumulated = ""
            for part in self.parts:
                accumulated += part
                yield _KeyErroringChunk(content=accumulated)

        return _stream()


class _CancelledResponseModel:
    def __init__(self) -> None:
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        raise asyncio.CancelledError()


class _FakeIndustryService:
    def __init__(self) -> None:
        self.writeback_calls: list[dict[str, object]] = []
        self.kickoff_calls: list[dict[str, object]] = []
        self.writeback_event = asyncio.Event()

    def get_instance_detail(self, instance_id: str) -> object:
        return SimpleNamespace(
            instance_id=instance_id,
            execution_core_identity={"agent_id": "copaw-agent-runner"},
        )

    async def apply_execution_chat_writeback(self, **kwargs):
        self.writeback_calls.append(kwargs)
        self.writeback_event.set()
        return {"applied": True}

    async def kickoff_execution_from_chat(self, **kwargs):
        self.kickoff_calls.append(kwargs)
        return {"activated": True}


class _VersionedIndustryService:
    def __init__(self) -> None:
        self.version = 1

    def get_instance_detail(self, instance_id: str) -> object:
        return SimpleNamespace(
            instance_id=instance_id,
            label=f"Industry v{self.version}",
            summary=f"Runtime summary v{self.version}",
            execution_core_identity={"agent_id": "copaw-agent-runner"},
            team=SimpleNamespace(agents=[]),
            staffing={},
            assignments=[],
            backlog=[{"title": f"Backlog v{self.version}"}],
            lanes=[],
            agent_reports=[],
            current_cycle={"title": f"Cycle v{self.version}"},
        )


class _TruthFirstDerivedIndexService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.calls: list[dict[str, object]] = []
        self.entries = [
            MemoryFactIndexRecord(
                id="memory-fact-latest",
                source_type="knowledge_chunk",
                source_ref="chunk-latest",
                scope_type="work_context",
                scope_id="ctx-truth-first",
                owner_agent_id="ops-agent",
                title="Current operator preference",
                summary="Prefer governed checklist playback before outbound execution.",
                content_excerpt="Prefer governed checklist playback before outbound execution.",
                content_text="Prefer governed checklist playback before outbound execution.",
                tags=["preference", "latest"],
                updated_at=now,
                created_at=now - timedelta(minutes=5),
            ),
            MemoryFactIndexRecord(
                id="memory-fact-history",
                source_type="knowledge_chunk",
                source_ref="chunk-history",
                scope_type="work_context",
                scope_id="ctx-truth-first",
                owner_agent_id="ops-agent",
                title="Older follow-up history",
                summary="Previous cycle required evidence review before outbound release.",
                content_excerpt="Previous cycle required evidence review before outbound release.",
                content_text="Previous cycle required evidence review before outbound release.",
                tags=["history"],
                updated_at=now - timedelta(days=2),
                created_at=now - timedelta(days=2, minutes=5),
            ),
        ]

    def list_fact_entries(self, **kwargs):
        self.calls.append(dict(kwargs))
        scope_type = kwargs.get("scope_type")
        scope_id = kwargs.get("scope_id")
        limit = kwargs.get("limit")
        entries = [
            item
            for item in self.entries
            if (scope_type is None or item.scope_type == scope_type)
            and (scope_id is None or item.scope_id == scope_id)
        ]
        if isinstance(limit, int):
            return entries[:limit]
        return entries


class _TruthFirstMemoryRecallService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._derived_index_service = _TruthFirstDerivedIndexService()

    def recall(self, **kwargs):
        self.calls.append(dict(kwargs))
        return MemoryRecallResponse(
            query=str(kwargs.get("query") or ""),
            backend_used="lexical",
            hits=[
                MemoryRecallHit(
                    entry_id="memory-hit-lexical",
                    kind="knowledge_chunk",
                    title="Lexical fallback note",
                    summary="Lexical fallback still works after truth-first memory injection.",
                    content_excerpt="Lexical fallback still works after truth-first memory injection.",
                    source_type="knowledge_chunk",
                    source_ref="chunk-lexical",
                    scope_type="work_context",
                    scope_id="ctx-truth-first",
                    confidence=0.8,
                    quality_score=0.7,
                    score=1.0,
                    backend="lexical",
                )
            ],
        )


class _SnapshotCountingIndustryService:
    def __init__(self) -> None:
        self.version = 1
        self.calls = 0

    def get_instance_detail(self, instance_id: str) -> object:
        self.calls += 1
        return SimpleNamespace(
            instance_id=instance_id,
            label=f"Industry v{self.version}",
            summary=f"Runtime summary v{self.version}",
            execution_core_identity={"agent_id": "copaw-agent-runner"},
            team=SimpleNamespace(agents=[]),
            staffing={},
            assignments=[],
            backlog=[{"title": f"Backlog v{self.version}"}],
            lanes=[],
            agent_reports=[],
            current_cycle={"title": f"Cycle v{self.version}"},
        )


async def _snapshot_texts(
    service: MainBrainChatService,
    snapshot: dict,
) -> list[str]:
    memory = service._load_memory(snapshot)  # pylint: disable=protected-access
    messages = await memory.get_memory(prepend_summary=False)
    return [message.get_text_content() for message in messages]


@pytest.mark.asyncio
async def test_main_brain_chat_service_keeps_incoming_turn_in_cache_until_reply_finishes():
    backend = _FakeSessionBackend()
    model = _SnapshotInspectingModel(
        backend,
        session_id="sess-chat",
        user_id="user-chat",
    )
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: model,
    )
    request = SimpleNamespace(
        session_id="sess-chat",
        user_id="user-chat",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="先记住这条消息，再回复我。")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert streamed[0][0].get_text_content() == "已收到，这轮先继续聊天。"
    assert model.snapshot_during_call is not None
    assert await _snapshot_texts(service, model.snapshot_during_call) == []
    snapshot = backend.load_session_snapshot(
        session_id="sess-chat",
        user_id="user-chat",
        allow_not_exist=True,
    )
    assert await _snapshot_texts(service, snapshot) == [
        "先记住这条消息，再回复我。",
        "已收到，这轮先继续聊天。",
    ]
    assert len(backend.save_calls) == 1


@pytest.mark.asyncio
async def test_main_brain_chat_service_throttles_snapshot_persistence_between_turns():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StaticResponseModel("纯聊天回复"),
    )
    request = SimpleNamespace(
        session_id="sess-throttle",
        user_id="user-throttle",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )

    for turn in range(3):
        msgs = [Msg(name="user", role="user", content=f"第 {turn + 1} 轮消息")]
        streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]
        assert streamed[0][0].get_text_content() == "纯聊天回复"

        if turn == 0:
            assert len(backend.save_calls) == 1
        if turn == 1:
            assert len(backend.save_calls) == 1
        if turn == 2:
            assert len(backend.save_calls) == 2


@pytest.mark.asyncio
async def test_main_brain_chat_service_reuses_cached_snapshot_for_pure_chat_turns():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StaticResponseModel("cached reply"),
    )
    request = SimpleNamespace(
        session_id="sess-cache-reuse",
        user_id="user-cache-reuse",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )

    for turn in range(2):
        msgs = [Msg(name="user", role="user", content=f"cache turn {turn + 1}")]
        streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]
        assert streamed[0][0].get_text_content() == "cached reply"

    assert len(backend.load_calls) == 1


@pytest.mark.asyncio
async def test_main_brain_chat_service_does_not_duplicate_save_on_clean_ttl_eviction(monkeypatch):
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StaticResponseModel("ttl reply"),
    )
    request = SimpleNamespace(
        session_id="sess-ttl",
        user_id="user-ttl",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    now = {"value": 1000.0}
    monkeypatch.setattr(
        main_brain_chat_service_module.time,
        "time",
        lambda: now["value"],
    )

    first_turn = [Msg(name="user", role="user", content="turn one")]
    _ = [item async for item in service.execute_stream(msgs=first_turn, request=request)]
    assert len(backend.save_calls) == 1

    cache_key = ("sess-ttl", "user-ttl")
    cache_entry = service._session_cache[cache_key]  # pylint: disable=protected-access
    cache_entry.last_used_at = (
        now["value"] - main_brain_chat_service_module._PURE_CHAT_SESSION_CACHE_TTL_SECONDS - 1
    )

    now["value"] += 1
    second_turn = [Msg(name="user", role="user", content="turn two")]
    _ = [item async for item in service.execute_stream(msgs=second_turn, request=request)]

    assert len(backend.save_calls) == 2


@pytest.mark.asyncio
async def test_main_brain_chat_service_uses_fallback_text_for_empty_model_response():
    backend = _FakeSessionBackend()
    model = _EmptyResponseModel()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: model,
    )
    request = SimpleNamespace(
        session_id="sess-empty",
        user_id="user-empty",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="开始前先回我一句。")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert "没有拿到有效回复" in streamed[0][0].get_text_content()
    assert model.calls == [True, False]
    snapshot = backend.load_session_snapshot(
        session_id="sess-empty",
        user_id="user-empty",
        allow_not_exist=True,
    )
    texts = await _snapshot_texts(service, snapshot)
    assert texts[0] == "开始前先回我一句。"
    assert "没有拿到有效回复" in texts[-1]


@pytest.mark.asyncio
async def test_main_brain_chat_service_streams_incremental_chunks_before_completion():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StreamingResponseModel("hello", " world"),
    )
    request = SimpleNamespace(
        session_id="sess-streaming",
        user_id="user-streaming",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="stream to me")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert len(streamed) == 2
    assert streamed[0][1] is False
    assert streamed[1][1] is True
    assert streamed[0][0].id == streamed[1][0].id
    assert streamed[0][0].get_text_content() == "hello"
    assert streamed[1][0].get_text_content() == "hello world"
    snapshot = backend.load_session_snapshot(
        session_id="sess-streaming",
        user_id="user-streaming",
        allow_not_exist=True,
    )
    texts = await _snapshot_texts(service, snapshot)
    assert texts[-1] == "hello world"


@pytest.mark.asyncio
async def test_main_brain_chat_service_reads_persisted_commit_state_from_bound_agent_snapshot():
    backend = _FakeSessionBackend()
    backend.save_session_snapshot(
        session_id="industry-chat:industry-v1-demo:execution-core",
        user_id="execution-core-agent",
        payload={
            "agent": {"memory": []},
            "main_brain": {
                "phase2_commit": {
                    "status": "confirm_required",
                    "action_type": "writeback_operating_truth",
                    "control_thread_id": "industry-chat:industry-v1-demo:execution-core",
                    "session_id": "industry-chat:industry-v1-demo:execution-core",
                    "summary": "Confirm the writeback before commit.",
                }
            },
        },
        source_ref="test:/phase2-commit",
    )
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StaticResponseModel("reply"),
    )
    request = SimpleNamespace(
        session_id="industry-chat:industry-v1-demo:execution-core",
        user_id="operator-user",
        agent_id="execution-core-agent",
        industry_instance_id="industry-v1-demo",
        work_context_id=None,
    )
    msgs = [Msg(name="user", role="user", content="continue")]

    _ = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    commit_state = getattr(request, "_copaw_main_brain_commit_state", None)
    assert commit_state is not None
    assert commit_state.status == "confirm_required"


@pytest.mark.asyncio
async def test_main_brain_chat_service_preserves_thinking_blocks_in_streamed_reply():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StreamingThinkingResponseModel(),
    )
    request = SimpleNamespace(
        session_id="sess-thinking",
        user_id="user-thinking",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="先想一下再答。")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert len(streamed) == 2
    final_message = streamed[-1][0]
    blocks = final_message.get_content_blocks()
    assert blocks[0]["type"] == "thinking"
    assert blocks[0]["thinking"] == "先整理约束，再确认下一步"
    assert blocks[1]["type"] == "text"
    assert blocks[1]["text"] == "先看目标，再给你下一步"


@pytest.mark.asyncio
async def test_main_brain_chat_service_tolerates_stream_chunks_without_reasoning_content_attr():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StreamingKeyErroringReasoningResponseModel("hello", " world"),
    )
    request = SimpleNamespace(
        session_id="sess-keyerror-reasoning",
        user_id="user-keyerror-reasoning",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="stream to me")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert len(streamed) == 2
    assert streamed[-1][0].get_text_content() == "hello world"


@pytest.mark.asyncio
async def test_main_brain_chat_service_persists_latest_user_turn_when_request_is_cancelled():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _CancelledResponseModel(),
    )
    request = SimpleNamespace(
        session_id="sess-cancelled",
        user_id="user-cancelled",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="这轮先记下来，我等会回来继续。")]

    with pytest.raises(asyncio.CancelledError):
        _ = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    snapshot = backend.load_session_snapshot(
        session_id="sess-cancelled",
        user_id="user-cancelled",
        allow_not_exist=True,
    )
    texts = await _snapshot_texts(service, snapshot)
    assert texts == ["这轮先记下来，我等会回来继续。"]
    assert len(backend.save_calls) == 1


@pytest.mark.asyncio
async def test_main_brain_chat_service_interruption_forces_single_continuity_save_after_throttled_turns():
    backend = _FakeSessionBackend()
    models = [
        _StaticResponseModel("reply one"),
        _StaticResponseModel("reply two"),
        _CancelledResponseModel(),
    ]
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: models.pop(0),
    )
    request = SimpleNamespace(
        session_id="sess-cancelled-throttle",
        user_id="user-cancelled-throttle",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn one")],
            request=request,
        )
    ]
    assert len(backend.save_calls) == 1

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn two")],
            request=request,
        )
    ]
    assert len(backend.save_calls) == 1

    with pytest.raises(asyncio.CancelledError):
        _ = [
            item
            async for item in service.execute_stream(
                msgs=[Msg(name="user", role="user", content="turn three")],
                request=request,
            )
        ]

    assert len(backend.save_calls) == 2
    snapshot = backend.load_session_snapshot(
        session_id="sess-cancelled-throttle",
        user_id="user-cancelled-throttle",
        allow_not_exist=True,
    )
    texts = await _snapshot_texts(service, snapshot)
    assert texts == [
        "turn one",
        "reply one",
        "turn two",
        "reply two",
        "turn three",
    ]


@pytest.mark.asyncio
async def test_main_brain_chat_service_reuses_heavy_prompt_context_when_runtime_truth_is_stable(
    monkeypatch: pytest.MonkeyPatch,
):
    backend = _FakeSessionBackend()
    industry_service = _FakeIndustryService()
    model = _PromptCapturingResponseModel("ok")
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        model_factory=lambda: model,
    )
    request = SimpleNamespace(
        session_id="sess-cache-context",
        user_id="user-cache-context",
        industry_instance_id="industry-v1-demo",
        work_context_id=None,
        agent_id=None,
    )
    call_counts = {"runtime": 0, "cognitive": 0, "roster": 0}

    original_runtime_snapshot = main_brain_chat_service_module._format_runtime_snapshot
    original_cognitive_closure = main_brain_chat_service_module._format_cognitive_closure
    original_team_roster = main_brain_chat_service_module._format_team_roster

    def _count_runtime(detail: object | None) -> str:
        call_counts["runtime"] += 1
        return original_runtime_snapshot(detail)

    def _count_cognitive(*, detail: object | None, request: object) -> str:
        call_counts["cognitive"] += 1
        return original_cognitive_closure(detail=detail, request=request)

    def _count_roster(
        *,
        detail: object | None,
        agent_profile_service: object | None,
        industry_instance_id: str | None,
        owner_agent_id: str | None,
    ) -> list[str]:
        call_counts["roster"] += 1
        return original_team_roster(
            detail=detail,
            agent_profile_service=agent_profile_service,
            industry_instance_id=industry_instance_id,
            owner_agent_id=owner_agent_id,
        )

    monkeypatch.setattr(main_brain_chat_service_module, "_format_runtime_snapshot", _count_runtime)
    monkeypatch.setattr(main_brain_chat_service_module, "_format_cognitive_closure", _count_cognitive)
    monkeypatch.setattr(main_brain_chat_service_module, "_format_team_roster", _count_roster)

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn one")],
            request=request,
        )
    ]
    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn two")],
            request=request,
        )
    ]

    assert call_counts["runtime"] == 1
    assert call_counts["cognitive"] == 1
    assert call_counts["roster"] == 1
    assert len(model.calls) == 2


@pytest.mark.asyncio
async def test_main_brain_chat_service_rebuilds_heavy_prompt_context_when_runtime_truth_changes(
    monkeypatch: pytest.MonkeyPatch,
):
    backend = _FakeSessionBackend()
    industry_service = _VersionedIndustryService()
    model = _PromptCapturingResponseModel("ok")
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        model_factory=lambda: model,
    )
    request = SimpleNamespace(
        session_id="sess-context-refresh",
        user_id="user-context-refresh",
        industry_instance_id="industry-v1-demo",
        work_context_id=None,
        agent_id=None,
    )
    call_counts = {"runtime": 0}
    original_runtime_snapshot = main_brain_chat_service_module._format_runtime_snapshot

    def _count_runtime(detail: object | None) -> str:
        call_counts["runtime"] += 1
        return original_runtime_snapshot(detail)

    monkeypatch.setattr(main_brain_chat_service_module, "_format_runtime_snapshot", _count_runtime)

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn one")],
            request=request,
        )
    ]

    industry_service.version = 2

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn two")],
            request=request,
        )
    ]

    assert call_counts["runtime"] == 2
    assert len(model.calls) == 2


def test_main_brain_chat_service_history_context_shaping_stays_bounded():
    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    prior_messages = [
        Msg(name="user", role="user", content=f"prior-{idx}-" + ("x" * 1200))
        for idx in range(12)
    ]
    current_messages = [
        Msg(name="assistant", role="assistant", content=f"current-{idx}-" + ("y" * 1200))
        for idx in range(4)
    ]

    history_messages = service._build_history_messages(  # pylint: disable=protected-access
        prior_messages=prior_messages,
        current_messages=current_messages,
    )

    assert len(history_messages) <= 8
    assert sum(len(item["content"]) for item in history_messages) <= 4200
    assert history_messages[-1]["role"] == "assistant"
    assert "current-3-" in history_messages[-1]["content"]


def test_main_brain_chat_service_prompt_prefers_truth_first_profile_before_lexical_recall():
    recall_service = _TruthFirstMemoryRecallService()
    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        memory_recall_service=recall_service,
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-truth-first",
        user_id="user-truth-first",
        industry_instance_id=None,
        work_context_id="ctx-truth-first",
        agent_id="ops-agent",
    )

    prompt_messages = service._build_prompt_messages(  # pylint: disable=protected-access
        request=request,
        query="Please use the current checklist before outbound execution",
        prior_messages=[],
        current_messages=[],
    )

    context_prompt = prompt_messages[1]["content"]
    assert "## Truth-First Memory Profile" in context_prompt
    assert "## Truth-First Memory Latest Facts" in context_prompt
    assert "## Truth-First Memory History" in context_prompt
    assert "## Truth-First Lexical Recall" in context_prompt
    assert "Current operator preference" in context_prompt
    assert "Older follow-up history" in context_prompt
    assert "Lexical fallback note" in context_prompt
    assert context_prompt.index("## Truth-First Memory Profile") < context_prompt.index(
        "## Truth-First Memory Latest Facts",
    )
    assert context_prompt.index("## Truth-First Memory Latest Facts") < context_prompt.index(
        "## Truth-First Lexical Recall",
    )
    assert recall_service._derived_index_service.calls[0]["scope_type"] == "work_context"
    assert recall_service._derived_index_service.calls[0]["scope_id"] == "ctx-truth-first"
    assert recall_service.calls[0]["scope_type"] == "work_context"
    assert recall_service.calls[0]["scope_id"] == "ctx-truth-first"


@pytest.mark.asyncio
async def test_main_brain_chat_service_skips_lexical_recall_for_short_followup_turns_and_reuses_cached_context():
    recall_service = _TruthFirstMemoryRecallService()
    model = _PromptCapturingResponseModel("ok")
    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        memory_recall_service=recall_service,
        model_factory=lambda: model,
    )
    request = SimpleNamespace(
        session_id="sess-short-followup",
        user_id="user-short-followup",
        industry_instance_id=None,
        work_context_id="ctx-truth-first",
        agent_id="ops-agent",
    )

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[
                Msg(
                    name="user",
                    role="user",
                    content="Please use the current checklist before outbound execution",
                )
            ],
            request=request,
        )
    ]
    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="继续")],
            request=request,
        )
    ]
    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="再继续")],
            request=request,
        )
    ]

    assert len(recall_service.calls) == 1
    context_prompt = model.calls[-1][1]["content"]
    assert "## Truth-First Lexical Recall" in context_prompt
    assert "short follow-up turn" in context_prompt
    timing = getattr(request, "_copaw_main_brain_timing", None)
    assert timing is not None
    assert timing["lexical_recall_mode"] == "skip_short_followup"
    assert timing["prompt_context_cache_hit"] is True


@pytest.mark.asyncio
async def test_main_brain_chat_service_keeps_lexical_recall_for_short_explicit_history_queries():
    recall_service = _TruthFirstMemoryRecallService()
    model = _PromptCapturingResponseModel("ok")
    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        memory_recall_service=recall_service,
        model_factory=lambda: model,
    )
    request = SimpleNamespace(
        session_id="sess-explicit-memory",
        user_id="user-explicit-memory",
        industry_instance_id=None,
        work_context_id="ctx-truth-first",
        agent_id="ops-agent",
    )

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="Summarize the current checklist")],
            request=request,
        )
    ]
    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="按记录继续")],
            request=request,
        )
    ]

    assert len(recall_service.calls) == 2
    context_prompt = model.calls[-1][1]["content"]
    assert "Lexical fallback note" in context_prompt
    timing = getattr(request, "_copaw_main_brain_timing", None)
    assert timing is not None
    assert timing["lexical_recall_mode"] == "query_recall"


def test_main_brain_chat_service_prefers_work_context_recall_over_industry_scope_when_both_exist():
    recall_service = _TruthFirstMemoryRecallService()
    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        memory_recall_service=recall_service,
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-truth-first-both",
        user_id="user-truth-first-both",
        industry_instance_id="industry-v1-demo",
        work_context_id="ctx-truth-first",
        agent_id="ops-agent",
    )

    prompt_messages = service._build_prompt_messages(  # pylint: disable=protected-access
        request=request,
        query="Use the resumed work context before broad industry memory",
        prior_messages=[],
        current_messages=[],
    )

    context_prompt = prompt_messages[1]["content"]
    assert "Current operator preference" in context_prompt
    assert recall_service._derived_index_service.calls[0]["scope_type"] == "work_context"
    assert recall_service._derived_index_service.calls[0]["scope_id"] == "ctx-truth-first"
    assert recall_service.calls[0]["scope_type"] == "work_context"
    assert recall_service.calls[0]["scope_id"] == "ctx-truth-first"


def test_main_brain_chat_service_prompt_guides_structured_goal_and_auto_progression():
    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-prompt",
        user_id="user-prompt",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )

    prompt_messages = service._build_prompt_messages(  # pylint: disable=protected-access
        request=request,
        query="月入10万且零亏损",
        prior_messages=[],
        current_messages=[],
    )

    system_prompt = prompt_messages[0]["content"]
    assert "不要反复追问“是否开始执行”" in system_prompt
    assert "结构化执行目标" in system_prompt


def test_main_brain_chat_service_prompt_does_not_expose_execution_only_tool_names():
    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-prompt-no-tools",
        user_id="user-prompt-no-tools",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )

    prompt_messages = service._build_prompt_messages(  # pylint: disable=protected-access
        request=request,
        query="先帮我理解当前情况，再决定要不要继续执行",
        prior_messages=[],
        current_messages=[],
    )

    joined_prompt = "\n".join(message["content"] for message in prompt_messages)
    assert "dispatch_query" not in joined_prompt
    assert "delegate_task" not in joined_prompt
    assert "dispatch_goal" not in joined_prompt
    assert "dispatch_active_goals" not in joined_prompt
    assert "memory_search" not in joined_prompt


def test_main_brain_chat_service_prompt_includes_staffing_gap_and_researcher_state():
    class _StaffingIndustryService:
        def get_instance_detail(self, instance_id: str) -> object:
            assert instance_id == "industry-v1-demo"
            return SimpleNamespace(
                instance_id=instance_id,
                label="Northwind Robotics",
                summary="Field operations control team",
                execution_core_identity={"agent_id": "copaw-agent-runner"},
                team=SimpleNamespace(
                    agents=[
                        {
                            "role_id": "execution-core",
                            "agent_id": "copaw-agent-runner",
                            "name": "Execution Core",
                            "role_name": "Execution Core",
                        },
                        {
                            "role_id": "researcher",
                            "agent_id": "industry-researcher-demo",
                            "name": "Researcher",
                            "role_name": "Researcher",
                        },
                    ],
                ),
                staffing={
                    "active_gap": {
                        "kind": "career-seat-proposal",
                        "target_role_name": "Platform Trader",
                        "reason": "Need a long-term browser execution seat",
                        "requested_surfaces": ["browser"],
                        "decision_request_id": "decision-seat-1",
                        "requires_confirmation": True,
                    },
                    "pending_proposals": [
                        {
                            "kind": "career-seat-proposal",
                            "target_role_name": "Platform Trader",
                            "decision_request_id": "decision-seat-1",
                            "status": "open",
                        },
                    ],
                    "temporary_seats": [
                        {
                            "role_name": "Desktop Clerk",
                            "status": "assigned",
                        },
                    ],
                    "researcher": {
                        "role_name": "Researcher",
                        "status": "waiting-review",
                        "pending_signal_count": 2,
                    },
                },
                assignments=[],
                backlog=[],
                lanes=[],
            )

    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        industry_service=_StaffingIndustryService(),
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-staffing",
        user_id="user-staffing",
        industry_instance_id="industry-v1-demo",
        work_context_id=None,
        agent_id=None,
    )

    prompt_messages = service._build_prompt_messages(  # pylint: disable=protected-access
        request=request,
        query="把平台投放执行也纳入长期团队",
        prior_messages=[],
        current_messages=[],
    )

    context_prompt = prompt_messages[1]["content"]
    assert "Active staffing gap" in context_prompt
    assert "Platform Trader" in context_prompt
    assert "career-seat-proposal" in context_prompt
    assert "decision-seat-1" in context_prompt
    assert "Researcher" in context_prompt
    assert "pending signals: 2" in context_prompt


def test_main_brain_chat_service_prompt_includes_structured_cognitive_closure_state():
    class _CognitiveIndustryService:
        def get_instance_detail(self, instance_id: str) -> object:
            assert instance_id == "industry-v1-demo"
            return SimpleNamespace(
                instance_id=instance_id,
                label="Northwind Robotics",
                summary="Field operations control team",
                execution_core_identity={"agent_id": "copaw-agent-runner"},
                team=SimpleNamespace(agents=[]),
                staffing={},
                assignments=[],
                backlog=[],
                lanes=[],
                agent_reports=[
                    {
                        "report_id": "report-weekend-1",
                        "headline": "Weekend variance review completed",
                        "summary": "Weekday response time stayed stable, but the weekend cause is unresolved.",
                    },
                ],
                current_cycle={
                    "title": "Weekend variance closure",
                    "synthesis": {
                        "latest_findings": [
                            {
                                "report_id": "report-weekend-1",
                                "headline": "Weekend variance review completed",
                                "summary": "Weekend variance still lacks a validated cause.",
                                "needs_followup": True,
                            },
                        ],
                        "conflicts": [
                            {
                                "kind": "result-mismatch",
                                "summary": "Reports disagree on assignment-shared.",
                                "report_ids": ["report-weekend-1", "report-weekend-2"],
                            },
                        ],
                        "holes": [
                            {
                                "kind": "followup-needed",
                                "summary": "Weekend variance still lacks a validated cause.",
                                "report_id": "report-weekend-1",
                            },
                        ],
                        "needs_replan": True,
                        "replan_reasons": [
                            "Reports disagree on assignment-shared.",
                            "Weekend variance still lacks a validated cause.",
                        ],
                    },
                },
            )

    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        industry_service=_CognitiveIndustryService(),
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-cognitive",
        user_id="user-cognitive",
        industry_instance_id="industry-v1-demo",
        work_context_id=None,
        agent_id=None,
    )

    prompt_messages = service._build_prompt_messages(  # pylint: disable=protected-access
        request=request,
        query="先判断这两个报告冲突还要不要重排",
        prior_messages=[],
        current_messages=[],
    )

    context_prompt = prompt_messages[1]["content"]
    assert "## 主脑 cognitive closure" in context_prompt
    assert "needs_replan=yes" in context_prompt
    assert "Reports disagree on assignment-shared." in context_prompt
    assert "Weekend variance still lacks a validated cause." in context_prompt
    assert "Weekend variance review completed" in context_prompt


@pytest.mark.asyncio
async def test_main_brain_chat_service_never_schedules_background_intake_for_control_thread():
    backend = _FakeSessionBackend()
    industry_service = _FakeIndustryService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        model_factory=lambda: _StaticResponseModel("我先接住这件事，后台继续推进。"),
    )
    request = SimpleNamespace(
        session_id="sess-intake",
        user_id="user-intake",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        work_context_id=None,
        agent_id=None,
        channel="console",
    )

    msgs = [Msg(name="user", role="user", content="把这个需求接过去，往前推进")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert streamed[0][0].get_text_content() == "我先接住这件事，后台继续推进。"
    await asyncio.sleep(0)
    assert industry_service.writeback_calls == []
    assert industry_service.kickoff_calls == []
    assert service._background_tasks == set()  # pylint: disable=protected-access


@pytest.mark.asyncio
async def test_main_brain_chat_service_reuses_scope_snapshot_for_same_work_context():
    backend = _FakeSessionBackend()
    industry_service = _SnapshotCountingIndustryService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        memory_recall_service=_TruthFirstMemoryRecallService(),
        model_factory=lambda: _PromptCapturingResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-scope-snapshot",
        user_id="user-scope-snapshot",
        industry_instance_id="industry-v1-demo",
        work_context_id="work-context-1",
        agent_id="ops-agent",
    )

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn one")],
            request=request,
        )
    ]
    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn two")],
            request=request,
        )
    ]

    snapshot_service = service._scope_snapshot_service  # pylint: disable=protected-access
    assert snapshot_service.calls == ["work-context-1"]


@pytest.mark.asyncio
async def test_main_brain_chat_service_rebuilds_scope_snapshot_after_dirty_mark():
    backend = _FakeSessionBackend()
    industry_service = _SnapshotCountingIndustryService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        memory_recall_service=_TruthFirstMemoryRecallService(),
        model_factory=lambda: _PromptCapturingResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-scope-dirty",
        user_id="user-scope-dirty",
        industry_instance_id="industry-v1-demo",
        work_context_id="work-context-1",
        agent_id="ops-agent",
    )

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn one")],
            request=request,
        )
    ]
    service.mark_scope_snapshot_dirty(work_context_id="work-context-1")
    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="turn two")],
            request=request,
        )
    ]

    snapshot_service = service._scope_snapshot_service  # pylint: disable=protected-access
    assert snapshot_service.calls == ["work-context-1", "work-context-1"]


@pytest.mark.asyncio
async def test_main_brain_chat_service_persists_commit_state_and_reloads_it_from_session_snapshot():
    backend = _FakeSessionBackend()
    model = _StructuredResponseModel(
        MainBrainTurnResult(
            reply_text="我会先记录 backlog。",
            action_envelope=MainBrainActionEnvelope(
                kind="commit_action",
                action_type="create_backlog_item",
                summary="Create backlog",
                payload={
                    "lane_hint": "growth",
                    "title": "Follow up the latest request",
                    "summary": "Track the latest operator request",
                    "acceptance_hint": "Operator confirms backlog wording",
                    "source_refs": ["chat:1"],
                },
            ),
        ),
    )
    commit_service = MainBrainCommitService(
        session_backend=backend,
        action_handlers={
            "create_backlog_item": lambda envelope, request, commit_key: {
                "status": "committed",
                "record_id": "backlog-1",
                "commit_key": commit_key,
            }
        },
    )
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: model,
        commit_service=commit_service,
    )
    request = SimpleNamespace(
        session_id="industry-chat:industry-v1-demo:execution-core",
        user_id="user-commit-state",
        industry_instance_id="industry-v1-demo",
        work_context_id="work-context-1",
        control_thread_id="industry-chat:industry-v1-demo:execution-core",
        agent_id="ops-agent",
    )

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="Please record this as backlog")],
            request=request,
        )
    ]

    snapshot = backend.load_session_snapshot(
        session_id="industry-chat:industry-v1-demo:execution-core",
        user_id="ops-agent",
        allow_not_exist=True,
    )
    phase2 = snapshot["main_brain"]["phase2_commit"]
    assert phase2["status"] == "committed"
    assert phase2["record_id"] == "backlog-1"

    reloaded_service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    reloaded_state = reloaded_service.get_persisted_commit_state(
        session_id="industry-chat:industry-v1-demo:execution-core",
        user_id="ops-agent",
    )
    assert reloaded_state == MainBrainCommitState.model_validate(phase2)


@pytest.mark.asyncio
async def test_main_brain_chat_service_never_applies_shared_intake_contract_after_reply():
    backend = _FakeSessionBackend()
    industry_service = _FakeIndustryService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        model_factory=lambda: _StaticResponseModel("我先接住，后台继续推进。"),
    )
    request = SimpleNamespace(
        session_id="sess-intake-contract",
        user_id="user-intake-contract",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        work_context_id=None,
        agent_id=None,
        channel="console",
    )

    msgs = [Msg(name="user", role="user", content="把这件事接过去，继续往前推")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert streamed[0][0].get_text_content() == "我先接住，后台继续推进。"
    await asyncio.sleep(0)
    assert industry_service.writeback_calls == []
    assert industry_service.kickoff_calls == []


@pytest.mark.asyncio
async def test_main_brain_chat_service_explicit_chat_mode_does_not_schedule_background_intake():
    backend = _FakeSessionBackend()
    industry_service = _FakeIndustryService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        model_factory=lambda: _StaticResponseModel("只聊这轮，不进入执行。"),
    )
    request = SimpleNamespace(
        session_id="sess-chat-only",
        user_id="user-chat-only",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        work_context_id=None,
        agent_id=None,
        channel="console",
        interaction_mode="chat",
    )

    streamed = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="这轮只聊天，不要落单也不要开跑")],
            request=request,
        )
    ]

    await asyncio.sleep(0)

    assert streamed[0][0].get_text_content() == "只聊这轮，不进入执行。"
    assert industry_service.writeback_calls == []
    assert industry_service.kickoff_calls == []
    assert service._background_tasks == set()  # pylint: disable=protected-access


def test_main_brain_intake_extracts_latest_user_text_as_canonical_input():
    from copaw.kernel.main_brain_intake import extract_main_brain_intake_text

    msgs = [
        Msg(name="assistant", role="assistant", content="先确认一下现状。"),
        Msg(name="user", role="user", content="旧的目标先别动。"),
        Msg(name="assistant", role="assistant", content="收到。"),
        Msg(name="user", role="user", content="把新的增长目标接过去继续推进。"),
    ]

    assert extract_main_brain_intake_text(msgs) == "把新的增长目标接过去继续推进。"


def test_main_brain_intake_materializes_execute_task_contract_from_model_decision():
    from copaw.kernel.main_brain_intake import materialize_main_brain_intake_contract

    contract = materialize_main_brain_intake_contract(
        message_text="把新的增长目标接过去继续推进。",
        decision=SimpleNamespace(
            intent_kind="execute-task",
            should_writeback=False,
            approved_targets=[],
            strategy=None,
            goal=None,
            schedule=None,
            kickoff_allowed=True,
            explicit_execution_confirmation=False,
        ),
    )

    assert contract is not None
    assert contract.message_text == "把新的增长目标接过去继续推进。"
    assert contract.intent_kind == "execute-task"
    assert contract.writeback_requested is False
    assert contract.has_active_writeback_plan is True
    assert contract.should_kickoff is True
    assert contract.should_route_to_orchestrate is True
