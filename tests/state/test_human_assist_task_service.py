# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from copaw.evidence import EvidenceLedger
from copaw.state import HumanAssistTaskRecord, SQLiteStateStore
from copaw.state.human_assist_task_service import HumanAssistTaskService
from copaw.state.repositories import SqliteHumanAssistTaskRepository


def _build_service(tmp_path) -> HumanAssistTaskService:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteHumanAssistTaskRepository(store)
    return HumanAssistTaskService(
        repository=repository,
        evidence_ledger=EvidenceLedger(database_path=tmp_path / "evidence.sqlite3"),
    )


def _make_record(*, task_id: str = "task-1") -> HumanAssistTaskRecord:
    issued_at = datetime(2026, 3, 28, 11, 0, tzinfo=timezone.utc)
    return HumanAssistTaskRecord(
        id=f"human-assist:{task_id}",
        industry_instance_id="industry-1",
        assignment_id="assignment-1",
        task_id=task_id,
        chat_thread_id="industry-chat:industry-1:execution-core",
        title="上传回执截图",
        summary="系统缺少宿主完成证明。",
        task_type="evidence-submit",
        reason_code="blocked-by-proof",
        reason_summary="需要宿主上传付款回执。",
        required_action="请在聊天里上传回执截图并回复已完成。",
        submission_mode="chat-message",
        acceptance_mode="evidence_verified",
        acceptance_spec={
            "version": "v1",
            "hard_anchors": ["receipt"],
            "result_anchors": ["uploaded"],
            "negative_anchors": ["missing"],
            "failure_hint": "请补上传回执截图或说明截图中的付款标识。",
        },
        resume_checkpoint_ref="checkpoint:receipt-upload",
        reward_preview={"协作值": 2, "同调经验": 1},
        status="created",
        issued_at=issued_at,
        created_at=issued_at,
        updated_at=issued_at,
    )


def test_human_assist_task_service_requires_acceptance_contract_to_issue(tmp_path) -> None:
    service = _build_service(tmp_path)
    record = _make_record()
    record = record.model_copy(update={"acceptance_spec": {}})

    with pytest.raises(ValueError):
        service.issue_task(record)


def test_human_assist_task_service_accepts_submission_when_verification_passes(tmp_path) -> None:
    service = _build_service(tmp_path)
    issued = service.issue_task(_make_record())

    result = service.submit_and_verify(
        issued.id,
        submission_text="我已经 uploaded 了 receipt 截图。",
        submission_evidence_refs=["media-analysis-1"],
        submission_payload={
            "anchors": ["receipt", "uploaded"],
            "media_analysis_ids": ["media-analysis-1"],
        },
    )

    assert result.outcome == "accepted"
    assert result.resume_queued is True
    assert result.task.status == "resume_queued"
    assert result.task.reward_result["协作值"] == 2
    assert result.task.reward_result["granted"] is True
    assert "receipt" in result.matched_hard_anchors
    assert "uploaded" in result.matched_result_anchors


def test_human_assist_task_service_requests_more_evidence_when_anchors_are_missing(tmp_path) -> None:
    service = _build_service(tmp_path)
    issued = service.issue_task(_make_record())

    result = service.submit_and_verify(
        issued.id,
        submission_text="我完成了。",
        submission_evidence_refs=[],
    )

    assert result.outcome == "need_more_evidence"
    assert result.resume_queued is False
    assert result.task.status == "rejected"
    assert result.missing_hard_anchors == ["receipt"]
    assert result.missing_result_anchors == ["uploaded"]
    assert "补上传回执截图" in result.message


def test_human_assist_task_service_returns_current_active_task_for_thread(tmp_path) -> None:
    service = _build_service(tmp_path)
    first = service.issue_task(_make_record(task_id="task-older"))
    second = service.issue_task(
        _make_record(task_id="task-newer").model_copy(
            update={
                "issued_at": datetime(2026, 3, 28, 11, 10, tzinfo=timezone.utc),
                "created_at": datetime(2026, 3, 28, 11, 10, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 28, 11, 10, tzinfo=timezone.utc),
            },
        ),
    )

    closed_first = first.model_copy(update={"status": "closed"})
    service.upsert_task(closed_first)

    current = service.get_current_task(
        chat_thread_id="industry-chat:industry-1:execution-core",
    )

    assert current is not None
    assert current.id == second.id


def test_human_assist_task_service_excludes_resume_queued_from_current_task(tmp_path) -> None:
    service = _build_service(tmp_path)
    issued = service.issue_task(_make_record())

    service.submit_and_verify(
        issued.id,
        submission_text="uploaded receipt proof",
        submission_evidence_refs=["media-analysis-1"],
    )

    current = service.get_current_task(
        chat_thread_id="industry-chat:industry-1:execution-core",
    )

    assert current is None
