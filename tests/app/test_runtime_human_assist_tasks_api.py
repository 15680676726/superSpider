# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from copaw.app.runtime_center import RuntimeCenterStateQueryService
from copaw.capabilities import CapabilityService
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelDispatcher, KernelTaskStore
from copaw.state import HumanAssistTaskRecord, SQLiteStateStore
from copaw.state.human_assist_task_service import HumanAssistTaskService
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteHumanAssistTaskRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)

from .runtime_center_api_parts.shared import (
    FakeCronManager,
    FakeScheduleStateQueryService,
    FakeTurnExecutor,
    build_runtime_center_app,
    make_job,
)


class _FakeQueryExecutionService:
    def __init__(
        self,
        *,
        resume_result: dict[str, object] | None = None,
        resume_error: Exception | None = None,
        resume_results: list[object] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self._resume_result = dict(resume_result or {"resumed": True, "summary": "resume finished"})
        self._resume_error = resume_error
        self._resume_results = list(resume_results or [])

    def resume_human_assist_task(self, *, task: object) -> dict[str, object]:
        self.calls.append(str(getattr(task, "id", "")))
        if self._resume_results:
            next_result = self._resume_results.pop(0)
            if isinstance(next_result, Exception):
                raise next_result
            if isinstance(next_result, dict):
                return dict(next_result)
            return {"resumed": bool(next_result)}
        if self._resume_error is not None:
            raise self._resume_error
        return dict(self._resume_result)


class _AsyncQueryExecutionService:
    def __init__(
        self,
        *,
        resume_result: dict[str, object] | None = None,
        delay_seconds: float = 0.2,
    ) -> None:
        self.calls: list[str] = []
        self._resume_result = dict(
            resume_result or {"resumed": True, "summary": "resume finished"},
        )
        self._delay_seconds = delay_seconds

    async def resume_human_assist_task(self, *, task: object) -> dict[str, object]:
        self.calls.append(str(getattr(task, "id", "")))
        await asyncio.sleep(self._delay_seconds)
        return dict(self._resume_result)


class _RecordingHumanAssistTaskService:
    def __init__(self, task: HumanAssistTaskRecord) -> None:
        self._task = task
        self.submit_calls: list[dict[str, object]] = []

    def get_current_task(self, *, chat_thread_id: str):
        if chat_thread_id != self._task.chat_thread_id:
            return None
        if str(self._task.status).strip().lower() in {"closed", "handoff_blocked"}:
            return None
        return self._task

    def submit_and_verify(
        self,
        task_id: str,
        *,
        submission_text: str | None,
        submission_evidence_refs: list[str],
        submission_payload: dict[str, object],
    ):
        self.submit_calls.append(
            {
                "task_id": task_id,
                "submission_text": submission_text,
                "submission_evidence_refs": list(submission_evidence_refs),
                "submission_payload": dict(submission_payload),
            },
        )
        return SimpleNamespace(
            outcome="accepted",
            task=self._task,
            message="accepted",
            resume_queued=False,
            matched_hard_anchors=["receipt"],
            matched_result_anchors=["uploaded"],
            missing_hard_anchors=[],
            missing_result_anchors=[],
            matched_negative_anchors=[],
        )

    def mark_closed(self, task_id: str, *, summary: str, resume_payload: dict[str, object]):
        del task_id, summary, resume_payload
        self._task = self._task.model_copy(update={"status": "closed"})
        return self._task


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


def _build_human_assist_app(tmp_path, *, query_execution_service: object | None = None):
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
    query_execution_service = query_execution_service or _FakeQueryExecutionService()
    app.state.turn_executor = turn_executor
    app.state.query_execution_service = query_execution_service
    return app, service, turn_executor, query_execution_service


def _wire_governed_schedule_runtime(app, manager: FakeCronManager, tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "schedule-governance.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "schedule-governance.evidence.sqlite3")
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
    )
    capability_service.set_cron_manager(manager)
    kernel_dispatcher = KernelDispatcher(
        task_store=KernelTaskStore(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            decision_request_repository=decision_request_repository,
            evidence_ledger=evidence_ledger,
        ),
        capability_service=capability_service,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = kernel_dispatcher
    app.state.decision_request_repository = decision_request_repository
    app.state.evidence_ledger = evidence_ledger


def test_runtime_center_human_assist_task_endpoints(tmp_path) -> None:
    app, service, _turn_executor, _query_execution_service = _build_human_assist_app(
        tmp_path,
    )
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


def test_runtime_center_chat_run_intercepts_human_assist_submission_when_explicit_action_is_set(
    tmp_path,
) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
    )
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
            "requested_actions": ["submit_human_assist"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Receipt uploaded.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == [issued.id]
    assert service.get_task(issued.id).status == "closed"
    assert '"outcome":"accepted"' in response.text

    current_response = client.get(
        "/runtime-center/human-assist-tasks/current",
        params={"chat_thread_id": issued.chat_thread_id},
    )
    assert current_response.status_code == 404


def test_runtime_center_chat_run_preserves_requested_actions_in_submission_payload(
    tmp_path,
) -> None:
    task = _make_human_assist_task(task_id="task-requested-actions").model_copy(
        update={"status": "issued"},
    )
    recording_service = _RecordingHumanAssistTaskService(task)
    app, _service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
        query_execution_service=_FakeQueryExecutionService(),
    )
    app.state.human_assist_task_service = recording_service
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-requested-actions",
            "session_id": task.chat_thread_id,
            "thread_id": task.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "requested_actions": ["submit_human_assist"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Receipt uploaded.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == [task.id]
    assert recording_service.submit_calls[0]["submission_payload"]["requested_actions"] == [
        "submit_human_assist",
    ]
    assert recording_service.submit_calls[0]["submission_payload"]["interaction_mode"] == "auto"
    assert recording_service.submit_calls[0]["submission_payload"]["chat_thread_id"] == task.chat_thread_id
    assert recording_service.get_current_task(chat_thread_id=task.chat_thread_id) is None


def test_runtime_center_chat_run_accepts_human_assist_submission_from_plain_text_anchor_match(
    tmp_path,
) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
    )
    issued = service.issue_task(_make_human_assist_task(task_id="task-plain-text"))
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-plain-text",
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
    assert query_execution_service.calls == [issued.id]
    assert service.get_task(issued.id).status == "closed"
    assert '"outcome":"accepted"' in response.text


def test_runtime_center_chat_run_falls_back_to_normal_chat_when_no_current_human_assist_task(
    tmp_path,
) -> None:
    app, _service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
    )
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-no-current-task",
            "session_id": "industry-chat:industry-1:execution-core",
            "thread_id": "industry-chat:industry-1:execution-core",
            "user_id": "host-user",
            "channel": "console",
            "requested_actions": ["submit_human_assist"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Receipt uploaded.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 1
    assert query_execution_service.calls == []
    assert '"status": "completed"' in response.text


def test_runtime_center_chat_run_reports_missing_human_assist_evidence(tmp_path) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
    )
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
            "requested_actions": ["submit_human_assist"],
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
    assert query_execution_service.calls == []
    assert service.get_task(issued.id).status == "need_more_evidence"
    assert '"outcome":"need_more_evidence"' in response.text


def test_runtime_center_chat_run_need_more_evidence_preserves_hidden_continuity_context(
    tmp_path,
) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
    )
    issued = service.issue_task(
        _make_human_assist_task(task_id="task-need-more-evidence-context").model_copy(
            update={
                "submission_payload": {
                    "work_context_id": "ctx-need-more-evidence",
                    "control_thread_id": "industry-chat:industry-1:execution-core",
                    "environment_ref": "desktop:session-1",
                    "recommended_scheduler_action": "handoff",
                    "main_brain_runtime": {
                        "work_context_id": "ctx-need-more-evidence",
                        "environment_ref": "desktop:session-1",
                        "control_thread_id": "industry-chat:industry-1:execution-core",
                        "recommended_scheduler_action": "handoff",
                    },
                },
            },
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-need-more-evidence-context",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "requested_actions": ["submit_human_assist"],
            "main_brain_runtime": {
                "review_note": "host replied but anchors are still missing",
            },
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {"type": "text", "text": "I checked it."},
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == []
    current = service.get_task(issued.id)
    assert current.status == "need_more_evidence"
    assert '"outcome":"need_more_evidence"' in response.text
    assert current.submission_payload["work_context_id"] == "ctx-need-more-evidence"
    assert current.submission_payload["control_thread_id"] == "industry-chat:industry-1:execution-core"
    assert current.submission_payload["environment_ref"] == "desktop:session-1"
    assert current.submission_payload["recommended_scheduler_action"] == "handoff"
    assert (
        current.submission_payload["main_brain_runtime"]["work_context_id"]
        == "ctx-need-more-evidence"
    )
    assert (
        current.submission_payload["main_brain_runtime"]["environment_ref"]
        == "desktop:session-1"
    )
    assert (
        current.submission_payload["main_brain_runtime"]["control_thread_id"]
        == "industry-chat:industry-1:execution-core"
    )
    assert (
        current.submission_payload["main_brain_runtime"]["recommended_scheduler_action"]
        == "handoff"
    )
    assert (
        current.submission_payload["main_brain_runtime"]["review_note"]
        == "host replied but anchors are still missing"
    )


def test_runtime_center_chat_run_marks_handoff_blocked_when_resume_cannot_start(
    tmp_path,
) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
        query_execution_service=_FakeQueryExecutionService(
            resume_results=[
                {"resumed": False, "reason": "resume_unavailable"},
                {"resumed": False, "reason": "resume_unavailable"},
            ],
        ),
    )
    issued = service.issue_task(_make_human_assist_task(task_id="task-resume-fail"))
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-resume-fail",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "requested_actions": ["submit_human_assist"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Receipt uploaded.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == [issued.id, issued.id]
    assert service.get_task(issued.id).status == "handoff_blocked"
    assert "没接上后续流程" in response.text


def test_runtime_center_chat_run_retries_human_assist_resume_before_blocking(
    tmp_path,
) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
        query_execution_service=_FakeQueryExecutionService(
            resume_results=[
                {"resumed": False, "reason": "resume_unavailable"},
                {"resumed": True, "summary": "resume finished"},
            ],
        ),
    )
    issued = service.issue_task(_make_human_assist_task(task_id="task-resume-retry"))
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-resume-retry",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "requested_actions": ["submit_human_assist"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Receipt uploaded.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == [issued.id, issued.id]
    assert service.get_task(issued.id).status == "closed"
    assert "没接上后续流程" not in response.text
def test_runtime_center_chat_run_marks_resume_queued_before_async_resume_closes(
    tmp_path,
) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
        query_execution_service=_AsyncQueryExecutionService(delay_seconds=0.2),
    )
    issued = service.issue_task(_make_human_assist_task(task_id="task-resume-queued"))
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-resume-queued",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "requested_actions": ["submit_human_assist"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Receipt uploaded.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == [issued.id]
    assert '"resume_queued":true' in response.text
    assert '"status":"resume_queued"' in response.text

    current_response = client.get(
        "/runtime-center/human-assist-tasks/current",
        params={"chat_thread_id": issued.chat_thread_id},
    )
    assert current_response.status_code == 404

    deadline = time.time() + 2.0
    while time.time() < deadline:
        if service.get_task(issued.id).status == "closed":
            break
        time.sleep(0.05)

    assert service.get_task(issued.id).status == "closed"


def test_runtime_center_chat_run_accepts_media_only_human_assist_submission(
    tmp_path,
) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
    )
    issued = service.issue_task(
        _make_human_assist_task(task_id="task-media-only").model_copy(
            update={
                "status": "issued",
                "acceptance_spec": {
                    "version": "v1",
                    "hard_anchors": ["analysis-receipt"],
                    "result_anchors": ["analysis-uploaded"],
                },
            },
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-media-only",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "media_analysis_ids": ["analysis-receipt", "analysis-uploaded"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == [issued.id]
    assert service.get_task(issued.id).status == "closed"
    assert '"outcome":"accepted"' in response.text


def test_runtime_center_chat_run_preserves_shared_work_context_across_schedule_resume_and_human_assist(
    tmp_path,
) -> None:
    shared_work_context_id = "ctx-shared-reentry"
    recommended_scheduler_action = "resume"
    schedule = make_job("sched-shared")
    schedule = schedule.model_copy(
        update={
            "meta": {
                "work_context_id": shared_work_context_id,
                "recommended_scheduler_action": recommended_scheduler_action,
            },
        },
    )
    manager = FakeCronManager([schedule])

    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
    )
    app.state.cron_manager = manager
    base_state_query_service = app.state.state_query_service
    schedule_state_query_service = FakeScheduleStateQueryService(manager)

    class _HybridStateQueryService:
        async def list_schedules(self, limit: int | None = 5):
            return await schedule_state_query_service.list_schedules(limit=limit)

        async def get_schedule_detail(self, schedule_id: str):
            return await schedule_state_query_service.get_schedule_detail(schedule_id)

        def __getattr__(self, name: str):
            return getattr(base_state_query_service, name)

    app.state.state_query_service = _HybridStateQueryService()
    _wire_governed_schedule_runtime(app, manager, tmp_path)

    issued = service.issue_task(_make_human_assist_task(task_id="task-shared-work-context"))
    client = TestClient(app)

    pause_response = client.post("/runtime-center/schedules/sched-shared/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["paused"] is True

    resume_response = client.post("/runtime-center/schedules/sched-shared/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["resumed"] is True

    schedule_detail = client.get("/runtime-center/schedules/sched-shared")
    assert schedule_detail.status_code == 200
    assert schedule_detail.json()["spec"]["meta"]["work_context_id"] == shared_work_context_id
    assert (
        schedule_detail.json()["spec"]["meta"]["recommended_scheduler_action"]
        == recommended_scheduler_action
    )

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-shared-work-context",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "requested_actions": ["submit_human_assist"],
            "work_context_id": shared_work_context_id,
            "main_brain_runtime": {
                "work_context_id": shared_work_context_id,
                "recommended_scheduler_action": recommended_scheduler_action,
            },
            "media_analysis_ids": ["analysis-receipt-shared"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Receipt uploaded.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == [issued.id]
    assert service.get_task(issued.id).status == "closed"
    assert '"outcome":"accepted"' in response.text

    task_detail = client.get(f"/runtime-center/human-assist-tasks/{issued.id}")
    assert task_detail.status_code == 200
    submission_payload = task_detail.json()["task"]["submission_payload"]
    assert submission_payload["main_brain_runtime"]["work_context_id"] == shared_work_context_id
    assert (
        submission_payload["main_brain_runtime"]["recommended_scheduler_action"]
        == recommended_scheduler_action
    )
    assert submission_payload["media_analysis_ids"] == ["analysis-receipt-shared"]


def test_runtime_center_chat_run_closed_human_assist_keeps_hidden_continuity_context(
    tmp_path,
) -> None:
    app, service, turn_executor, query_execution_service = _build_human_assist_app(
        tmp_path,
    )
    issued = service.issue_task(
        _make_human_assist_task(task_id="task-closed-context").model_copy(
            update={
                "submission_payload": {
                    "work_context_id": "ctx-closed-context",
                    "control_thread_id": "industry-chat:industry-1:execution-core",
                    "environment_ref": "desktop:session-closed",
                    "recommended_scheduler_action": "resume",
                    "main_brain_runtime": {
                        "work_context_id": "ctx-closed-context",
                        "control_thread_id": "industry-chat:industry-1:execution-core",
                        "environment_ref": "desktop:session-closed",
                        "recommended_scheduler_action": "resume",
                    },
                },
                "acceptance_spec": {
                    "version": "v1",
                    "hard_anchors": ["receipt"],
                    "result_anchors": ["uploaded"],
                    "failure_hint": "Provide receipt proof before acceptance.",
                },
            },
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-human-assist-closed-context",
            "session_id": issued.chat_thread_id,
            "thread_id": issued.chat_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "requested_actions": ["submit_human_assist"],
            "main_brain_runtime": {
                "review_note": "host confirmed the final receipt upload",
            },
            "media_analysis_ids": ["receipt", "uploaded"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {"type": "text", "text": "Receipt uploaded."},
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(turn_executor.stream_calls) == 0
    assert query_execution_service.calls == [issued.id]
    assert service.get_task(issued.id).status == "closed"
    assert '"outcome":"accepted"' in response.text

    task_detail = client.get(f"/runtime-center/human-assist-tasks/{issued.id}")
    assert task_detail.status_code == 200
    submission_payload = task_detail.json()["task"]["submission_payload"]
    assert submission_payload["work_context_id"] == "ctx-closed-context"
    assert submission_payload["control_thread_id"] == "industry-chat:industry-1:execution-core"
    assert submission_payload["environment_ref"] == "desktop:session-closed"
    assert submission_payload["recommended_scheduler_action"] == "resume"
    assert submission_payload["media_analysis_ids"] == ["receipt", "uploaded"]
    assert (
        submission_payload["main_brain_runtime"]["work_context_id"] == "ctx-closed-context"
    )
    assert (
        submission_payload["main_brain_runtime"]["control_thread_id"]
        == "industry-chat:industry-1:execution-core"
    )
    assert (
        submission_payload["main_brain_runtime"]["environment_ref"] == "desktop:session-closed"
    )
    assert (
        submission_payload["main_brain_runtime"]["recommended_scheduler_action"] == "resume"
    )
    assert (
        submission_payload["main_brain_runtime"]["review_note"]
        == "host confirmed the final receipt upload"
    )
