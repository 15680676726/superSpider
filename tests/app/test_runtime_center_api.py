# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.app.runtime_center.task_review_projection import build_task_review_payload
from copaw.evidence import EvidenceRecord, ReplayPointer
from copaw.memory import ActivationResult, KnowledgeNeuron
from copaw.state import SQLiteStateStore, TaskRecord, TaskRuntimeRecord, WorkContextRecord
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)
from copaw.utils.runtime_routes import task_route

from .runtime_center_api_parts.overview_governance import *  # noqa: F401,F403
from .runtime_center_api_parts.detail_environment import *  # noqa: F401,F403
from .runtime_center_api_parts.shared import build_runtime_center_app


def test_task_review_projects_acceptance_closeout_visibility() -> None:
    now = datetime(2026, 3, 27, 10, 0, tzinfo=timezone.utc)
    payload = build_task_review_payload(
        task=type(
            "Task",
            (),
            {
                "id": "task-acceptance-1",
                "title": "Close seller portal verification loop",
                "summary": "Verify the resumed seller session and capture replayable proof.",
                "owner_agent_id": "ops-agent",
                "status": "running",
                "acceptance_criteria": '{"kind":"kernel-task-meta-v1"}',
                "updated_at": now,
            },
        )(),
        runtime=type(
            "Runtime",
            (),
            {
                "current_phase": "executing",
                "last_result_summary": "Waiting for CAPTCHA clearance before resuming writer flow.",
                "last_error_summary": None,
                "updated_at": now,
                "risk_level": "guarded",
            },
        )(),
        decisions=[],
        evidence=[
            EvidenceRecord(
                id="evidence-step-1",
                task_id="task-acceptance-1",
                actor_ref="ops-agent",
                risk_level="guarded",
                action_summary="Captured pre-handoff checkpoint",
                result_summary="Seller portal state saved before human CAPTCHA takeover",
                created_at=now,
                metadata={
                    "step_id": "checkpoint-1",
                    "step_title": "Checkpoint before handoff",
                    "verification_status": "blocked",
                    "verification_reason": "captcha-required",
                },
                replay_pointers=(
                    ReplayPointer(
                        id="replay-step-1",
                        replay_type="browser-session",
                        storage_uri="file:///tmp/replay-step-1.json",
                        summary="Replay the seller portal checkpoint",
                        created_at=now,
                    ),
                ),
            ),
            EvidenceRecord(
                id="evidence-step-2",
                task_id="task-acceptance-1",
                actor_ref="ops-agent",
                risk_level="auto",
                action_summary="Verified DOM anchor after resume",
                result_summary="Header anchor confirmed after the session resumed",
                created_at=now.replace(minute=5),
                metadata={
                    "step_id": "verify-1",
                    "step_title": "Verify resumed page anchor",
                    "verification_status": "passed",
                },
            ),
        ],
        execution_feedback={
            "workspace_graph": {
                "workspace_id": "workspace:copaw:main",
                "handoff_checkpoint": {
                    "state": "agent-attached",
                    "reason": "captcha-required",
                    "owner_ref": "human-operator:alice",
                    "resume_kind": "host-companion-session",
                    "verification_channel": "runtime-center-self-check",
                    "checkpoint_ref": "checkpoint:captcha:jd-seller",
                    "return_condition": "captcha-cleared",
                },
            },
            "host_contract": {
                "host_mode": "attach-existing-session",
                "handoff_state": "agent-attached",
                "verification_channel": "runtime-center-self-check",
            },
            "recovery": {
                "status": "pending",
                "mode": "resume-runtime",
            },
            "browser_site_contract": {
                "browser_mode": "attach-existing-session",
                "site_contract_status": "governed-handoff",
                "last_verified_dom_anchor": "#seller-header",
            },
        },
        child_results=[],
        owner_agent={"name": "Ops Agent"},
        task_route=task_route("task-acceptance-1"),
    )

    assert payload["continuity"]["handoff"]["state"] == "agent-attached"
    assert payload["continuity"]["handoff"]["checkpoint_ref"] == "checkpoint:captcha:jd-seller"
    assert payload["continuity"]["handoff"]["return_condition"] == "captcha-cleared"
    assert payload["continuity"]["verification"]["channel"] == "runtime-center-self-check"
    assert payload["continuity"]["verification"]["status"] == "blocked"
    assert payload["continuity"]["verification"]["latest_anchor"] == "#seller-header"
    assert payload["evidence_status"]["total_count"] == 2
    assert payload["evidence_status"]["replayable_count"] == 1
    assert payload["evidence_status"]["verified_count"] == 1
    assert payload["evidence_status"]["task_evidence_route"] == (
        "/api/runtime-center/evidence?task_id=task-acceptance-1"
    )
    assert payload["evidence_status"]["recent_steps"][0]["evidence_id"] == "evidence-step-2"
    assert payload["evidence_status"]["recent_steps"][1]["replay_count"] == 1
    assert payload["evidence_status"]["recent_steps"][1]["replay_route"] == (
        "/api/runtime-center/replays/replay-step-1"
    )
    assert any("Handoff" in line for line in payload["summary_lines"])
    assert any("Verification" in line for line in payload["summary_lines"])


def test_task_review_normalizes_closeout_fallback_from_verification_payload() -> None:
    now = datetime(2026, 3, 27, 11, 0, tzinfo=timezone.utc)
    payload = build_task_review_payload(
        task=type(
            "Task",
            (),
            {
                "id": "task-acceptance-2",
                "title": "Review resumed seller portal acceptance closeout",
                "summary": "Confirm the resumed seller portal is safe to continue.",
                "owner_agent_id": "ops-agent",
                "status": "completed",
                "acceptance_criteria": '{"kind":"kernel-task-meta-v1"}',
                "updated_at": now,
            },
        )(),
        runtime=type(
            "Runtime",
            (),
            {
                "current_phase": "completed",
                "last_result_summary": "Acceptance closeout recorded after resume.",
                "last_error_summary": None,
                "updated_at": now,
                "risk_level": "auto",
            },
        )(),
        decisions=[],
        evidence=[
            EvidenceRecord(
                id="evidence-closeout-1",
                task_id="task-acceptance-2",
                actor_ref="ops-agent",
                risk_level="auto",
                action_summary="Review resumed seller portal acceptance closeout",
                result_summary="Replayable acceptance proof saved for operator review",
                created_at=now,
                metadata={
                    "checkpoint": {
                        "id": "closeout-1",
                        "title": "Review resumed seller portal acceptance closeout",
                    },
                    "verification": {
                        "verified": True,
                        "summary": "Seller portal anchor confirmed after resume",
                    },
                },
                replay_pointers=(
                    ReplayPointer(
                        id="replay-closeout-1",
                        replay_type="browser-session",
                        storage_uri="file:///tmp/replay-closeout-1.json",
                        summary="Replay the acceptance closeout proof",
                        created_at=now,
                    ),
                ),
            ),
        ],
        execution_feedback={},
        child_results=[],
        owner_agent={"name": "Ops Agent"},
        task_route=task_route("task-acceptance-2"),
    )

    assert payload["continuity"]["verification"]["status"] == "passed"
    assert payload["continuity"]["verification"]["reason"] == (
        "Seller portal anchor confirmed after resume"
    )
    assert payload["evidence_status"]["verified_count"] == 1
    assert payload["evidence_status"]["latest_replayable_evidence_id"] == "evidence-closeout-1"
    assert payload["evidence_status"]["latest_replayable_evidence_route"] == (
        "/api/runtime-center/evidence/evidence-closeout-1"
    )
    assert payload["evidence_status"]["latest_replayable_replay_route"] == (
        "/api/runtime-center/replays/replay-closeout-1"
    )
    assert payload["evidence_status"]["recent_steps"][0]["step_id"] == "closeout-1"
    assert payload["evidence_status"]["recent_steps"][0]["step_title"] == (
        "Review resumed seller portal acceptance closeout"
    )
    assert payload["evidence_status"]["recent_steps"][0]["verification_status"] == "passed"
    assert payload["evidence_status"]["recent_steps"][0]["verification_reason"] == (
        "Seller portal anchor confirmed after resume"
    )
    assert any("Verification: passed" in line for line in payload["summary_lines"])


def test_task_review_exposes_host_twin_and_prefers_it_for_runtime_guidance() -> None:
    now = datetime(2026, 3, 27, 11, 30, tzinfo=timezone.utc)
    payload = build_task_review_payload(
        task=type(
            "Task",
            (),
            {
                "id": "task-host-twin-api-1",
                "title": "Resume workbook writer from host twin",
                "summary": "Recover the Orders workbook writing session.",
                "owner_agent_id": "ops-agent",
                "status": "running",
                "acceptance_criteria": '{"kind":"kernel-task-meta-v1"}',
                "updated_at": now,
            },
        )(),
        runtime=type(
            "Runtime",
            (),
            {
                "current_phase": "executing",
                "last_result_summary": "Workbook writer is paused for guarded recovery.",
                "last_error_summary": None,
                "updated_at": now,
                "risk_level": "guarded",
            },
        )(),
        decisions=[],
        evidence=[],
        execution_feedback={
            "host_twin": {
                "ownership": {
                    "seat_owner_agent_id": "ops-agent",
                    "handoff_owner_ref": "human-operator:alice",
                    "workspace_scope": "project:copaw",
                },
                "surface_mutability": {
                    "desktop_app": {
                        "surface_ref": "window:excel:orders",
                        "mutability": "blocked",
                        "safe_to_mutate": False,
                        "blocker_family": "modal-uac-login",
                    },
                },
                "blocked_surfaces": [
                    {
                        "surface_kind": "desktop_app",
                        "surface_ref": "window:excel:orders",
                        "reason": "captcha-required",
                        "event_family": "modal-uac-login",
                    },
                ],
                "trusted_anchors": [
                    {
                        "surface_ref": "window:excel:orders",
                        "anchor_ref": "excel://Orders!A1",
                        "label": "Orders workbook row 1",
                    },
                ],
                "legal_recovery": {
                    "path": "handoff",
                    "checkpoint_ref": "checkpoint:captcha:orders",
                    "resume_kind": "resume-runtime",
                    "verification_channel": "runtime-center-self-check",
                    "return_condition": "captcha-cleared",
                },
                "active_blocker_families": [
                    "modal-uac-login",
                ],
                "app_family_twins": {
                    "office_document": {
                        "active": True,
                        "family_kind": "office_document",
                        "surface_ref": "window:excel:orders",
                        "contract_status": "verified-writer",
                        "family_scope_ref": "app:excel",
                        "writer_lock_scope": "workbook:orders",
                    },
                },
                "coordination": {
                    "seat_owner_ref": "ops-agent",
                    "workspace_owner_ref": "ops-agent",
                    "writer_owner_ref": "ops-agent",
                    "candidate_seat_refs": ["env:session:session:web:main"],
                    "selected_seat_ref": "env:session:session:web:main",
                    "seat_selection_policy": "sticky-active-seat",
                    "contention_forecast": {
                        "severity": "blocked",
                        "reason": "captcha-required",
                    },
                    "legal_owner_transition": {
                        "allowed": False,
                        "reason": "human handoff is still active",
                    },
                    "recommended_scheduler_action": "handoff",
                },
            },
            "host_contract": {
                "status": "blocked",
                "blocked_reason": "legacy-host-blocker",
                "handoff_state": "handoff-required",
                "handoff_owner_ref": "agent:legacy-owner",
            },
            "recovery": {
                "status": "pending",
                "mode": "attach-environment",
            },
            "browser_site_contract": {
                "verification_anchor": "#legacy-anchor",
            },
        },
        child_results=[],
        owner_agent={"name": "Ops Agent"},
        task_route=task_route("task-host-twin-api-1"),
    )

    assert (
        payload["execution_runtime"]["host_twin"]["ownership"]["handoff_owner_ref"]
        == "human-operator:alice"
    )
    assert (
        payload["execution_runtime"]["host_twin"]["app_family_twins"]["office_document"][
            "writer_lock_scope"
        ]
        == "workbook:orders"
    )
    assert (
        payload["execution_runtime"]["host_twin"]["coordination"][
            "recommended_scheduler_action"
        ]
        == "handoff"
    )
    assert payload["continuity"]["handoff"]["owner_ref"] == "human-operator:alice"
    assert payload["continuity"]["handoff"]["resume_kind"] == "resume-runtime"
    assert payload["continuity"]["handoff"]["return_condition"] == "captcha-cleared"
    assert payload["continuity"]["verification"]["channel"] == "runtime-center-self-check"
    assert payload["continuity"]["verification"]["latest_anchor"] == "excel://Orders!A1"
    assert any("Coordination: handoff" in line for line in payload["summary_lines"])
    assert any("sticky-active-seat" in line for line in payload["summary_lines"])
    assert any(
        "Follow host coordination action: handoff" in action
        for action in payload["next_actions"]
    )
    assert any("modal-uac-login" in line for line in payload["summary_lines"])
    assert any("Orders workbook" in action for action in payload["next_actions"])
    assert any(
        "Host coordination contention is blocked" in risk
        for risk in payload["risks"]
    )
    assert any("modal-uac-login" in risk for risk in payload["risks"])


def test_task_review_prefers_canonical_host_twin_summary_after_reentry() -> None:
    now = datetime(2026, 3, 29, 12, 30, tzinfo=timezone.utc)
    payload = build_task_review_payload(
        task=type(
            "Task",
            (),
            {
                "id": "task-host-twin-api-reentry-1",
                "title": "Resume clean reentry",
                "summary": "Use canonical host summary instead of stale handoff metadata.",
                "owner_agent_id": "ops-agent",
                "status": "running",
                "acceptance_criteria": '{"kind":"kernel-task-meta-v1"}',
                "updated_at": now,
            },
        )(),
        runtime=type(
            "Runtime",
            (),
            {
                "current_phase": "executing",
                "last_result_summary": "Clean reentry confirmed by host summary.",
                "last_error_summary": None,
                "updated_at": now,
                "risk_level": "guarded",
            },
        )(),
        decisions=[],
        evidence=[],
        execution_feedback={
            "host_twin_summary": {
                "recommended_scheduler_action": "proceed",
                "blocked_surface_count": 0,
                "legal_recovery_mode": "resume-environment",
                "contention_severity": "clear",
                "contention_reason": "clean reentry confirmed",
                "host_companion_status": "attached",
                "host_companion_source": "live-handle",
                "continuity_state": "ready",
            },
            "host_twin": {
                "ownership": {
                    "handoff_owner_ref": "human-operator:alice",
                },
                "blocked_surfaces": [
                    {
                        "surface_kind": "desktop_app",
                        "surface_ref": "window:excel:orders",
                        "reason": "stale-captcha",
                        "event_family": "modal-uac-login",
                    },
                ],
                "legal_recovery": {
                    "path": "handoff",
                    "checkpoint_ref": "checkpoint:captcha:orders",
                    "resume_kind": "resume-environment",
                    "verification_channel": "runtime-center-self-check",
                },
                "coordination": {
                    "recommended_scheduler_action": "handoff",
                    "contention_forecast": {
                        "severity": "blocked",
                        "reason": "stale-captcha",
                    },
                },
            },
            "host_contract": {
                "status": "blocked",
                "blocked_reason": "legacy-host-blocker",
                "handoff_state": "handoff-required",
                "handoff_reason": "legacy-handoff",
            },
            "recovery": {
                "status": "pending",
                "mode": "attach-environment",
            },
        },
        child_results=[],
        owner_agent={"name": "Ops Agent"},
        task_route=task_route("task-host-twin-api-reentry-1"),
    )

    assert (
        payload["execution_runtime"]["host_twin_summary"]["recommended_scheduler_action"]
        == "proceed"
    )
    assert (
        payload["execution_runtime"]["host_twin_summary"]["continuity_state"]
        == "ready"
    )
    assert payload["continuity"]["handoff"]["state"] is None
    assert payload["continuity"]["handoff"]["reason"] is None
    assert payload["continuity"]["handoff"]["resume_kind"] == "resume-environment"
    assert any("Host twin coordination: proceed" in line for line in payload["summary_lines"])
    assert not any("Handoff:" in line for line in payload["summary_lines"])
    assert not any(
        "Follow host coordination action: handoff" in action
        for action in payload["next_actions"]
    )
    assert not any("Handoff is active" in risk for risk in payload["risks"])
    assert not any("Host blocker detected" in risk for risk in payload["risks"])


def test_runtime_center_evidence_endpoint_filters_by_task_id() -> None:
    class FakeEvidenceQueryService:
        def list_recent_records(self, limit: int = 20):
            raise AssertionError("task_id filter should bypass list_recent_records")

        def list_by_capability_ref(self, capability_ref: str, *, limit: int = 20):
            raise AssertionError("task_id filter should bypass capability filtering")

        def list_by_task(self, task_id: str, *, limit: int | None = None):
            assert task_id == "task-1"
            assert limit == 7
            return [
                type(
                    "EvidenceRecord",
                    (),
                    {
                        "id": "evidence-1",
                        "task_id": "task-1",
                        "actor_ref": "ops-agent",
                        "environment_ref": "session:web:main",
                        "capability_ref": "system:dispatch_query",
                        "risk_level": "guarded",
                        "action_summary": "Captured runtime checkpoint",
                        "result_summary": "Checkpoint stored with replay pointer",
                        "created_at": now,
                        "status": "recorded",
                        "input_digest": None,
                        "output_digest": None,
                        "metadata": {},
                        "artifacts": (),
                        "replay_pointers": (),
                    },
                )(),
            ]

        def serialize_record(self, record):
            return {
                "id": record.id,
                "task_id": record.task_id,
                "result_summary": record.result_summary,
            }

    now = datetime(2026, 3, 27, 10, 0, tzinfo=timezone.utc)
    app = build_runtime_center_app()
    app.state.evidence_query_service = FakeEvidenceQueryService()

    client = TestClient(app)
    response = client.get(
        "/runtime-center/evidence",
        params={"task_id": " task-1 ", "capability_ref": "ignored", "limit": 7},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "evidence-1",
            "task_id": "task-1",
            "result_summary": "Checkpoint stored with replay pointer",
        },
    ]


class _FakeMemoryActivationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def activate_for_query(self, **kwargs) -> ActivationResult:
        self.calls.append(dict(kwargs))
        return ActivationResult(
            query=str(kwargs.get("query") or ""),
            scope_type="work_context",
            scope_id=str(kwargs.get("work_context_id") or "ctx-1"),
            activated_neurons=[
                KnowledgeNeuron(
                    neuron_id="fact-approval-blocker",
                    kind="fact",
                    scope_type="work_context",
                    scope_id="ctx-1",
                    title="Approval blocker",
                    summary="Outbound approval remains blocked pending finance sign-off.",
                    entity_keys=["finance-queue", "outbound-approval"],
                    source_refs=["memory:fact:approval-blocker"],
                    evidence_refs=["evidence-approval-1"],
                    activation_score=0.91,
                ),
                KnowledgeNeuron(
                    neuron_id="strategy-outbound-guardrail",
                    kind="strategy",
                    scope_type="work_context",
                    scope_id="ctx-1",
                    title="Outbound guardrail",
                    summary="Do not bypass guarded approval workflow.",
                    entity_keys=["outbound-approval"],
                    source_refs=["strategy:industry-ops"],
                    activation_score=0.77,
                ),
            ],
            contradictions=[
                KnowledgeNeuron(
                    neuron_id="fact-legacy-approval",
                    kind="fact",
                    scope_type="work_context",
                    scope_id="ctx-1",
                    title="Legacy approval claim",
                    summary="An older note claimed approval was clear.",
                    source_refs=["memory:fact:legacy-approval"],
                    activation_score=0.41,
                ),
            ],
            support_refs=[
                "memory:fact:approval-blocker",
                "strategy:industry-ops",
            ],
            evidence_refs=["evidence-approval-1"],
            strategy_refs=["strategy:industry-ops"],
            top_entities=["outbound-approval", "finance-queue"],
            top_constraints=["Wait for finance sign-off", "Do not bypass guarded approval"],
            top_next_actions=["Escalate finance approval"],
            metadata={"activated_count": 2},
        )


def _build_runtime_center_activation_client(tmp_path):
    app = build_runtime_center_app()
    state_store = SQLiteStateStore(tmp_path / "runtime-center-activation.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)

    task_repository.upsert_task(
        TaskRecord(
            id="task-activation-1",
            title="Clear outbound approval blocker",
            summary="Investigate why outbound approval is still blocked.",
            task_type="analysis",
            status="running",
            owner_agent_id="ops-agent",
            work_context_id="ctx-1",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-activation-1",
            runtime_status="active",
            current_phase="executing",
            risk_level="guarded",
            last_owner_agent_id="ops-agent",
            last_result_summary="Finance sign-off is still missing for outbound approval.",
        ),
    )

    state_query = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=schedule_repository,
        decision_request_repository=decision_request_repository,
    )
    activation_service = _FakeMemoryActivationService()
    state_query._memory_activation_service = activation_service
    app.state.state_query_service = state_query
    return TestClient(app), activation_service


def _build_runtime_center_work_context_client(tmp_path) -> TestClient:
    app = build_runtime_center_app()
    state_store = SQLiteStateStore(tmp_path / "runtime-center-work-context.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    work_context_repository = SqliteWorkContextRepository(state_store)

    timestamp = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)
    work_context_repository.upsert_context(
        WorkContextRecord(
            id="ctx-api-1",
            title="API-backed work context",
            summary="Work-context route should read directly from projector-backed state.",
            context_type="control-thread",
            status="active",
            context_key="control-thread:runtime-center-api",
            owner_scope="ops-scope",
            owner_agent_id="task-owner",
            primary_thread_id="industry-chat:runtime-center-api",
            updated_at=timestamp,
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-api-1",
            title="Project runtime owner in API detail",
            summary="Route payload should follow runtime owner instead of stale task owner.",
            task_type="analysis",
            status="running",
            owner_agent_id="task-owner",
            work_context_id="ctx-api-1",
            created_at=timestamp,
            updated_at=timestamp,
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-api-1",
            runtime_status="active",
            current_phase="executing",
            risk_level="guarded",
            last_result_summary="Runtime owner has already taken over this work context.",
            last_owner_agent_id="runtime-owner",
            updated_at=timestamp,
        ),
    )

    app.state.state_query_service = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=schedule_repository,
        decision_request_repository=decision_request_repository,
        work_context_repository=work_context_repository,
    )
    return TestClient(app)


def test_runtime_center_task_detail_includes_activation_summary_when_available(tmp_path) -> None:
    client, activation_service = _build_runtime_center_activation_client(tmp_path)

    response = client.get("/runtime-center/tasks/task-activation-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["activation"]["scope_type"] == "work_context"
    assert payload["activation"]["scope_id"] == "ctx-1"
    assert payload["activation"]["activated_count"] == 2
    assert payload["activation"]["contradiction_count"] == 1
    assert payload["activation"]["top_entities"] == [
        "outbound-approval",
        "finance-queue",
    ]
    assert payload["activation"]["top_constraints"] == [
        "Wait for finance sign-off",
        "Do not bypass guarded approval",
    ]
    assert payload["activation"]["support_refs"] == [
        "memory:fact:approval-blocker",
        "strategy:industry-ops",
    ]
    assert "activated_neurons" not in payload["activation"]
    assert activation_service.calls[0]["task_id"] == "task-activation-1"
    assert activation_service.calls[0]["work_context_id"] == "ctx-1"


def test_runtime_center_tasks_overview_includes_activation_hint_for_current_focus(tmp_path) -> None:
    client, _ = _build_runtime_center_activation_client(tmp_path)

    response = client.get("/runtime-center/tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "task-activation-1"
    assert payload[0]["activation"]["top_constraints"] == [
        "Wait for finance sign-off",
        "Do not bypass guarded approval",
    ]
    assert payload[0]["activation"]["top_entities"] == [
        "outbound-approval",
        "finance-queue",
    ]
    assert payload[0]["activation"]["activated_count"] == 2


def test_runtime_center_work_contexts_list_reads_projector_backed_state(tmp_path) -> None:
    client = _build_runtime_center_work_context_client(tmp_path)

    response = client.get("/runtime-center/work-contexts")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0] == {
        "id": "ctx-api-1",
        "title": "API-backed work context",
        "kind": "work-context",
        "status": "active",
        "owner_scope": "ops-scope",
        "summary": "Work-context route should read directly from projector-backed state.",
        "updated_at": "2026-04-02T12:00:00Z",
        "route": "/api/runtime-center/work-contexts/ctx-api-1",
        "context_type": "control-thread",
        "context_key": "control-thread:runtime-center-api",
        "owner_agent_id": "task-owner",
        "industry_instance_id": None,
        "primary_thread_id": "industry-chat:runtime-center-api",
        "parent_work_context_id": None,
        "task_count": 1,
        "active_task_count": 1,
        "latest_task_id": "task-api-1",
        "latest_task_title": "Project runtime owner in API detail",
    }


def test_runtime_center_work_context_detail_reads_runtime_owner_from_state(tmp_path) -> None:
    client = _build_runtime_center_work_context_client(tmp_path)

    response = client.get("/runtime-center/work-contexts/ctx-api-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["work_context"]["id"] == "ctx-api-1"
    assert payload["route"] == "/api/runtime-center/work-contexts/ctx-api-1"
    assert payload["threads"] == ["industry-chat:runtime-center-api"]
    assert payload["stats"]["task_count"] == 1
    assert payload["stats"]["owner_agent_count"] == 1
    assert payload["agents"] == [
        {
            "agent_id": "runtime-owner",
            "name": "runtime-owner",
            "status": "unknown",
            "route": "/api/runtime-center/agents/runtime-owner",
        },
    ]
    assert payload["tasks"] == [
        {
            "id": "task-api-1",
            "title": "Project runtime owner in API detail",
            "status": "active",
            "phase": "executing",
            "summary": "Runtime owner has already taken over this work context.",
            "owner_agent_id": "runtime-owner",
            "owner_agent_name": "runtime-owner",
            "updated_at": "2026-04-02T12:00:00Z",
            "context_key": "control-thread:runtime-center-api",
            "work_context": {
                "id": "ctx-api-1",
                "title": "API-backed work context",
                "context_type": "control-thread",
                "status": "active",
                "context_key": "control-thread:runtime-center-api",
            },
            "route": "/api/runtime-center/tasks/task-api-1",
        },
    ]


def test_runtime_center_kernel_tasks_requires_canonical_state_query_method() -> None:
    app = build_runtime_center_app()

    class _LegacyOnlyStateQueryService:
        def get_tasks(self, **_kwargs):
            return [{"id": "legacy-task"}]

    app.state.state_query_service = _LegacyOnlyStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/kernel/tasks")

    assert response.status_code == 503
    assert response.json()["detail"] == "Kernel task queries are not available"
