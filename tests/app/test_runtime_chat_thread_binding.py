# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi.testclient import TestClient

from copaw.app.runtime_threads import RuntimeThreadHistory, RuntimeThreadSpec
from copaw.state import ExecutorRuntimeInstanceRecord, ExecutorThreadBindingRecord

from .runtime_center_api_parts.shared import FakeTurnExecutor, build_runtime_center_app


class _FakeHistoryReader:
    async def get_thread_history(
        self,
        thread_spec: RuntimeThreadSpec,
    ) -> RuntimeThreadHistory:
        return RuntimeThreadHistory(
            messages=[
                {
                    "id": "msg-1",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": f"history:{thread_spec.user_id}"},
                    ],
                },
            ],
        )


class _FakeExecutorRuntimeService:
    def __init__(self, *bindings: ExecutorThreadBindingRecord) -> None:
        self._bindings = list(bindings)
        self._runtimes: dict[str, ExecutorRuntimeInstanceRecord] = {}

    def add_runtime(
        self,
        runtime: ExecutorRuntimeInstanceRecord,
        *bindings: ExecutorThreadBindingRecord,
    ) -> None:
        self._runtimes[runtime.runtime_id] = runtime
        self._bindings.extend(bindings)

    def list_thread_bindings(
        self,
        *,
        thread_id: str | None = None,
        limit: int | None = None,
        **_: object,
    ):
        bindings = self._bindings
        if isinstance(thread_id, str) and thread_id.strip():
            bindings = [binding for binding in bindings if binding.thread_id == thread_id]
        if isinstance(limit, int) and limit >= 0:
            return bindings[:limit]
        return bindings

    def get_runtime(self, runtime_id: str):
        return self._runtimes.get(runtime_id)


def _build_executor_runtime_service(*, thread_id: str, work_context_id: str) -> _FakeExecutorRuntimeService:
    runtime = ExecutorRuntimeInstanceRecord(
        runtime_id=f"runtime:{thread_id}",
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assignment-1",
        role_id="execution-core",
        thread_id=thread_id,
        runtime_status="ready",
        metadata={
            "owner_agent_id": "copaw-agent-runner",
            "continuity": {
                "control_thread_id": thread_id,
                "session_id": thread_id,
                "industry_instance_id": "buddy:profile-1:domain-1",
                "industry_role_id": "execution-core",
                "owner_scope": "profile-1",
                "work_context_id": work_context_id,
            },
        },
    )
    binding = ExecutorThreadBindingRecord(
        binding_id=f"binding:{thread_id}",
        runtime_id=runtime.runtime_id,
        role_id="execution-core",
        executor_provider_id="provider:codex",
        assignment_id="assignment-1",
        thread_id=thread_id,
        runtime_status="ready",
        metadata={
            "industry_instance_id": "buddy:profile-1:domain-1",
            "industry_role_id": "execution-core",
            "owner_scope": "profile-1",
            "continuity": {
                "control_thread_id": thread_id,
                "session_id": thread_id,
                "work_context_id": work_context_id,
            },
        },
    )
    service = _FakeExecutorRuntimeService()
    service.add_runtime(runtime, binding)
    return service


def test_runtime_center_chat_run_hydrates_control_thread_industry_context(tmp_path) -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    executor_runtime_service = _build_executor_runtime_service(
        thread_id="industry-chat:buddy:profile-1:domain-1:execution-core",
        work_context_id="ctx-buddy-execution-core",
    )
    app.state.turn_executor = turn_executor
    app.state.executor_runtime_service = executor_runtime_service
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-thread-binding-hydration",
            "session_id": "industry-chat:buddy:profile-1:domain-1:execution-core",
            "thread_id": "industry-chat:buddy:profile-1:domain-1:execution-core",
            "user_id": "operator-1",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {"type": "text", "text": "请派发这个任务。"},
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 1
    request_payload = turn_executor.stream_calls[0]["request_payload"]
    assert getattr(request_payload, "control_thread_id", None) == (
        "industry-chat:buddy:profile-1:domain-1:execution-core"
    )
    assert getattr(request_payload, "session_kind", None) == "industry-control-thread"
    assert getattr(request_payload, "industry_instance_id", None) == "buddy:profile-1:domain-1"
    assert getattr(request_payload, "industry_role_id", None) == "execution-core"
    assert getattr(request_payload, "owner_scope", None) == "profile-1"
    assert getattr(request_payload, "work_context_id", None) == "ctx-buddy-execution-core"
    assert getattr(request_payload, "buddy_profile_id", None) == "profile-1"


def test_runtime_center_conversation_default_payload_keeps_meta_optional(
    tmp_path,
) -> None:
    app = build_runtime_center_app()
    thread_id = "industry-chat:buddy:profile-1:domain-1:execution-core"
    app.state.executor_runtime_service = _build_executor_runtime_service(
        thread_id=thread_id,
        work_context_id="ctx-buddy-execution-core",
    )
    app.state.runtime_thread_history_reader = _FakeHistoryReader()
    client = TestClient(app)

    response = client.get(f"/runtime-center/conversations/{thread_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == thread_id
    assert isinstance(payload["messages"], list)
    assert payload["messages"][0]["role"] == "assistant"
    assert payload["meta"]["session_kind"] == "industry-control-thread"
    assert "main_brain_commit" not in payload["meta"]
    assert "human_assist_task" not in payload["meta"]
