# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi.testclient import TestClient

from copaw.app.runtime_threads import RuntimeThreadHistory, RuntimeThreadSpec
from copaw.state import AgentThreadBindingRecord, SQLiteStateStore
from copaw.state.repositories import SqliteAgentThreadBindingRepository

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


def test_runtime_center_chat_run_hydrates_control_thread_industry_context(tmp_path) -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    binding_repository = SqliteAgentThreadBindingRepository(state_store)
    binding_repository.upsert_binding(
        AgentThreadBindingRecord(
            thread_id="industry-chat:buddy:profile-1:domain-1:execution-core",
            agent_id="copaw-agent-runner",
            session_id="industry-chat:buddy:profile-1:domain-1:execution-core",
            channel="console",
            binding_kind="industry-role-alias",
            industry_instance_id="buddy:profile-1:domain-1",
            industry_role_id="execution-core",
            work_context_id="ctx-buddy-execution-core",
            owner_scope="profile-1",
        ),
    )
    app.state.turn_executor = turn_executor
    app.state.agent_thread_binding_repository = binding_repository
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
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    binding_repository = SqliteAgentThreadBindingRepository(state_store)
    thread_id = "industry-chat:buddy:profile-1:domain-1:execution-core"
    binding_repository.upsert_binding(
        AgentThreadBindingRecord(
            thread_id=thread_id,
            agent_id="copaw-agent-runner",
            session_id=thread_id,
            channel="console",
            binding_kind="industry-role-alias",
            industry_instance_id="buddy:profile-1:domain-1",
            industry_role_id="execution-core",
            work_context_id="ctx-buddy-execution-core",
            owner_scope="profile-1",
        ),
    )
    app.state.runtime_thread_history_reader = _FakeHistoryReader()
    app.state.agent_thread_binding_repository = binding_repository
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
