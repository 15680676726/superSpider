# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.main_brain_commit_service import MainBrainCommitService
from copaw.kernel.main_brain_turn_result import MainBrainActionEnvelope, MainBrainTurnResult


class _FakeSessionBackend:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], dict] = {}

    def load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        allow_not_exist: bool = False,
    ) -> dict:
        _ = allow_not_exist
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
        self.snapshots[(session_id, user_id)] = dict(payload)


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        session_id="industry-chat:industry-v1-demo:execution-core",
        control_thread_id="industry-chat:industry-v1-demo:execution-core",
        user_id="user-1",
        industry_instance_id="industry-v1-demo",
        work_context_id="work-context-1",
        agent_id="ops-agent",
    )


def test_main_brain_commit_service_rejects_invalid_payload_and_persists_failed_state() -> None:
    backend = _FakeSessionBackend()
    service = MainBrainCommitService(session_backend=backend)
    result = service.commit_turn_result(
        turn_result=MainBrainTurnResult(
            reply_text="reply",
            action_envelope=MainBrainActionEnvelope(
                kind="commit_action",
                action_type="create_backlog_item",
                payload={"title": "missing required fields"},
            ),
        ),
        request=_request(),
    )

    assert result.status == "commit_failed"
    assert result.reason == "payload_invalid"
    snapshot = backend.load_session_snapshot(
        session_id="industry-chat:industry-v1-demo:execution-core",
        user_id="ops-agent",
        allow_not_exist=True,
    )
    assert snapshot["main_brain"]["phase2_commit"]["status"] == "commit_failed"
    assert snapshot["main_brain"]["phase2_commit"]["reason"] == "payload_invalid"


def test_main_brain_commit_service_escalates_confirm_and_persists_state() -> None:
    backend = _FakeSessionBackend()
    service = MainBrainCommitService(
        session_backend=backend,
        risk_evaluator=lambda envelope, request: {
            "risk_level": "confirm",
            "reason": "high-risk mutation",
        },
    )
    result = service.commit_turn_result(
        turn_result=MainBrainTurnResult(
            reply_text="reply",
            action_envelope=MainBrainActionEnvelope(
                kind="commit_action",
                action_type="writeback_operating_truth",
                payload={
                    "target_kind": "strategy_memory",
                    "summary": "Update strategy",
                    "facts": ["fact-1"],
                    "source_refs": ["chat:1"],
                },
            ),
        ),
        request=_request(),
    )

    assert result.status == "confirm_required"
    assert result.risk_level == "confirm"
    snapshot = backend.load_session_snapshot(
        session_id="industry-chat:industry-v1-demo:execution-core",
        user_id="ops-agent",
        allow_not_exist=True,
    )
    assert snapshot["main_brain"]["phase2_commit"]["status"] == "confirm_required"


def test_main_brain_commit_service_reports_environment_failure() -> None:
    backend = _FakeSessionBackend()
    service = MainBrainCommitService(
        session_backend=backend,
        environment_checker=lambda envelope, request: {
            "available": False,
            "reason": "environment_unavailable",
            "recovery_options": ["resume", "handoff"],
        },
    )
    result = service.commit_turn_result(
        turn_result=MainBrainTurnResult(
            reply_text="reply",
            action_envelope=MainBrainActionEnvelope(
                kind="commit_action",
                action_type="orchestrate_execution",
                payload={
                    "goal_summary": "Run the browser task",
                    "requested_surfaces": ["browser"],
                    "work_context_id": "work-context-1",
                    "operator_intent_summary": "Continue the pending browser workflow",
                },
            ),
        ),
        request=_request(),
    )

    assert result.status == "commit_failed"
    assert result.reason == "environment_unavailable"
    assert result.recovery_options == ["resume", "handoff"]


def test_main_brain_commit_service_reports_governance_denied() -> None:
    backend = _FakeSessionBackend()
    service = MainBrainCommitService(
        session_backend=backend,
        governance_checker=lambda envelope, request: {
            "allowed": False,
            "reason": "governance_denied",
            "message": "Denied by governance",
        },
    )
    result = service.commit_turn_result(
        turn_result=MainBrainTurnResult(
            reply_text="reply",
            action_envelope=MainBrainActionEnvelope(
                kind="commit_action",
                action_type="submit_human_assist",
                payload={
                    "task_type": "checkpoint",
                    "request_summary": "Please confirm the checkpoint",
                    "acceptance_anchors": ["anchor-1"],
                    "continuity_ref": "resume:1",
                },
            ),
        ),
        request=_request(),
    )

    assert result.status == "governance_denied"
    assert result.reason == "governance_denied"


def test_main_brain_commit_service_persists_bound_thread_state_under_agent_id() -> None:
    backend = _FakeSessionBackend()
    service = MainBrainCommitService(
        session_backend=backend,
        risk_evaluator=lambda envelope, request: {
            "risk_level": "confirm",
            "reason": "high-risk mutation",
        },
    )
    request = _request()
    request.user_id = "operator-user"
    request.agent_id = "execution-core-agent"

    result = service.commit_turn_result(
        turn_result=MainBrainTurnResult(
            reply_text="reply",
            action_envelope=MainBrainActionEnvelope(
                kind="commit_action",
                action_type="writeback_operating_truth",
                payload={
                    "target_kind": "strategy_memory",
                    "summary": "Update strategy",
                    "facts": ["fact-1"],
                    "source_refs": ["chat:1"],
                },
            ),
        ),
        request=request,
    )

    assert result.status == "confirm_required"
    snapshot = backend.load_session_snapshot(
        session_id="industry-chat:industry-v1-demo:execution-core",
        user_id="execution-core-agent",
        allow_not_exist=True,
    )
    assert snapshot["main_brain"]["phase2_commit"]["status"] == "confirm_required"
    assert (
        backend.load_session_snapshot(
            session_id="industry-chat:industry-v1-demo:execution-core",
            user_id="operator-user",
            allow_not_exist=True,
        )
        == {}
    )


def test_main_brain_commit_service_deduplicates_by_commit_key() -> None:
    backend = _FakeSessionBackend()
    calls: list[str] = []
    service = MainBrainCommitService(
        session_backend=backend,
        action_handlers={
            "create_backlog_item": lambda envelope, request, commit_key: calls.append(commit_key) or {
                "status": "committed",
                "record_id": "backlog-1",
            }
        },
    )
    turn_result = MainBrainTurnResult(
        reply_text="reply",
        action_envelope=MainBrainActionEnvelope(
            kind="commit_action",
            action_type="create_backlog_item",
            payload={
                "lane_hint": "growth",
                "title": "Track operator request",
                "summary": "Persist the latest operator request",
                "acceptance_hint": "Operator confirms backlog wording",
                "source_refs": ["chat:1"],
            },
        ),
    )

    first = service.commit_turn_result(turn_result=turn_result, request=_request())
    second = service.commit_turn_result(turn_result=turn_result, request=_request())

    assert first.status == "committed"
    assert second.status == "committed"
    assert second.idempotent_replay is True
    assert len(calls) == 1
