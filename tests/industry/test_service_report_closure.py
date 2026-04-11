from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from copaw.industry.service_report_closure import (
    build_agent_report_control_thread_message,
    write_agent_report_back_to_control_thread,
)


class _FakeSessionBackend:
    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, str], dict[str, object]] = {}

    def load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        allow_not_exist: bool = False,
    ) -> dict[str, object] | None:
        payload = self._snapshots.get((session_id, user_id))
        if payload is None and not allow_not_exist:
            raise KeyError(session_id)
        return deepcopy(payload) if payload is not None else None

    def save_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        payload: dict[str, object],
        source_ref: str,
    ) -> None:
        _ = source_ref
        self._snapshots[(session_id, user_id)] = deepcopy(payload)


def test_build_agent_report_control_thread_message_is_readable() -> None:
    report = SimpleNamespace(
        id="report-1",
        owner_role_id="writer-seat",
        owner_agent_id="writer-agent",
        result="completed",
        status="recorded",
        summary="已完成第一章草稿并整理发布素材。",
        headline="完成《深蓝交易员》第一章",
        evidence_ids=["ev-1", "ev-2"],
        decision_ids=["decision-1"],
    )
    assignment = SimpleNamespace(title="写作并整理首章发布稿")

    message = build_agent_report_control_thread_message(
        report=report,
        assignment=assignment,
    )

    assert "我刚完成一项任务：完成《深蓝交易员》第一章" in message
    assert "负责人：writer-seat" in message
    assert "任务：写作并整理首章发布稿" in message
    assert "结论：已完成第一章草稿并整理发布素材。" in message
    assert "证据 2 / 决策 1" in message


def test_write_agent_report_back_to_control_thread_persists_routes_and_requested_surfaces() -> None:
    session_backend = _FakeSessionBackend()
    session_backend.save_session_snapshot(
        session_id="industry-chat:industry-v1-writer:execution-core",
        user_id="copaw-agent-runner",
        payload={"agent": {"memory": []}},
        source_ref="test:/initial",
    )

    record = SimpleNamespace(instance_id="industry-v1-writer")
    report = SimpleNamespace(
        id="report-1",
        headline="完成《深蓝交易员》第一章",
        summary="已完成第一章草稿并整理发布素材。",
        assignment_id="assignment-1",
        task_id="task-1",
        work_context_id="wc-1",
        owner_agent_id="writer-agent",
        owner_role_id="writer-seat",
        result="completed",
        status="recorded",
        evidence_ids=["ev-1", "ev-2"],
        decision_ids=["decision-1"],
    )
    assignment = SimpleNamespace(title="写作并整理首章发布稿", backlog_item_id=None)

    write_agent_report_back_to_control_thread(
        session_backend=session_backend,
        backlog_service=None,
        record=record,
        report=report,
        assignment=assignment,
        build_report_followup_metadata_fn=lambda **_: {
            "control_thread_id": "industry-chat:industry-v1-writer:execution-core",
            "session_id": "industry-chat:industry-v1-writer:execution-core",
            "environment_ref": "session:console:industry:industry-v1-writer",
            "chat_writeback_requested_surfaces": ["browser", "document"],
            "knowledge_writeback_topic_keys": ["writing", "publishing"],
            "knowledge_writeback_scope_type": "industry",
            "knowledge_writeback_scope_id": "industry-v1-writer",
        },
        build_agent_report_control_thread_message_fn=build_agent_report_control_thread_message,
        execution_core_role_id="execution-core",
        execution_core_agent_id="copaw-agent-runner",
    )

    snapshot = session_backend.load_session_snapshot(
        session_id="industry-chat:industry-v1-writer:execution-core",
        user_id="copaw-agent-runner",
        allow_not_exist=False,
    )

    assert snapshot is not None
    memory = snapshot["agent"]["memory"]
    report_message = next(
        item for item in memory if item.get("id") == "agent-report:report-1"
    )
    metadata = report_message["metadata"]
    assert metadata["message_kind"] == "agent-report-writeback"
    assert (
        metadata["report_route"]
        == "/api/runtime-center/industry/industry-v1-writer?report_id=report-1"
    )
    assert metadata["requested_surfaces"] == ["browser", "document"]
    assert metadata["knowledge_writeback_topic_keys"] == ["writing", "publishing"]
    assert metadata["knowledge_writeback_scope_type"] == "industry"
    assert metadata["knowledge_writeback_scope_id"] == "industry-v1-writer"
    assert report_message["content"][0]["text"].startswith("我刚完成一项任务：")
