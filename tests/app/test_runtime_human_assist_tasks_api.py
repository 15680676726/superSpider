# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from copaw.app.runtime_center import RuntimeCenterStateQueryService
from copaw.evidence import EvidenceLedger
from copaw.state import HumanAssistTaskRecord, SQLiteStateStore
from copaw.state.human_assist_task_service import HumanAssistTaskService
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteHumanAssistTaskRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)

from .runtime_center_api_parts.shared import FakeTurnExecutor, build_runtime_center_app


def _make_human_assist_task(*, task_id: str = "task-1") -> HumanAssistTaskRecord:
    timestamp = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    return HumanAssistTaskRecord(
        id=f"human-assist:{task_id}",
        industry_instance_id="industry-1",
        assignment_id="assignment-1",
        task_id=task_id,
        chat_thread_id="industry-chat:industry-1:execution-core",
        title="Upload receipt proof",
        summary="Host proof is required before resume.",
        task_type="evidence-submit",
        reason_code="blocked-by-proof",
        reason_summary="Payment receipt still needs host confirmation.",
        required_action="Upload the receipt in chat and say it is finished.",
        submission_mode="chat-message",
        acceptance_mode="evidence_verified",
        acceptance_spec={
            "version": "v1",
            "hard_anchors": ["receipt"],
            "result_anchors": ["uploaded"],
            "failure_hint": "Provide receipt proof before acceptance.",
        },
        reward_preview={"sync_points": 2, "familiarity_exp": 1},
        resume_checkpoint_ref="checkpoint:receipt-upload",
        status="created",
        created_at=timestamp,
        updated_at=timestamp,
    )


def _build_human_assist_app(tmp_path):
    app = build_runtime_center_app()
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    service = HumanAssistTaskService(
        repository=SqliteHumanAssistTaskRepository(state_store),
        evidence_ledger=evidence_ledger,
    )
    app.state.human_assist_task_service = service
    app.state.state_query_service = RuntimeCenterStateQueryService(
        task_repository=SqliteTaskRepository(state_store),
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        decision_request_repository=SqliteDecisionRequestRepository(state_store),
        evidence_ledger=evidence_ledger,
        human_assist_task_service=service,
    )
    turn_executor = FakeTurnExecutor()
    app.state.turn_executor = turn_executor
    return app, service, turn_executor


def test_runtime_center_human_assist_task_endpoints(tmp_path) -> None:
    app, service, _turn_executor = _build_human_assist_app(tmp_path)
    issued = service.issue_task(_make_human_assist_task())
    client = TestClient(app)

    list_response = client.get(
        "/runtime-center/human-assist-tasks",
        params={"chat_thread_id": issued.chat_thread_id},
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["id"] == issued.id

    current_response = client.get(
        "/runtime-center/human-assist-tasks/current",
        params={"chat_thread_id": issued.chat_thread_id},
    )
    assert current_response.status_code == 200
    assert current_response.json()["id"] == issued.id

    detail_response = client.get(f"/runtime-center/human-assist-tasks/{issued.id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["task"]["id"] == issued.id


def test_runtime_center_chat_run_intercepts_human_assist_submission(tmp_path) -> None:
    app, service, turn_executor = _build_human_assist_app(tmp_path)
    issued = service.issue_task(_make_human_assist_task())
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-accept",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "I finished it. I uploaded the receipt proof.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert service.get_task(issued.id).status == "resume_queued"
    assert '"outcome":"accepted"' in response.text

    current_response = client.get(
        "/runtime-center/human-assist-tasks/current",
        params={"chat_thread_id": issued.chat_thread_id},
    )
    assert current_response.status_code == 404


def test_runtime_center_chat_run_reports_missing_human_assist_evidence(tmp_path) -> None:
    app, service, turn_executor = _build_human_assist_app(tmp_path)
    issued = service.issue_task(_make_human_assist_task(task_id="task-2"))
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-retry",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {"type": "text", "text": "I finished it."},
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert service.get_task(issued.id).status == "rejected"
    assert '"outcome":"need_more_evidence"' in response.text
