# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from copaw.app.runtime_center.task_review_projection import (
    build_task_review_payload,
    trace_id_from_kernel_meta,
)
from copaw.evidence import EvidenceRecord
from copaw.utils.runtime_routes import (
    agent_route,
    decision_route,
    goal_route,
    schedule_route,
    task_route,
    work_context_route,
)


def test_runtime_routes_share_one_contract() -> None:
    assert task_route("task-1") == "/api/runtime-center/tasks/task-1"
    assert goal_route("goal-1") == "/api/goals/goal-1/detail"
    assert agent_route("agent-1") == "/api/runtime-center/agents/agent-1"
    assert decision_route("decision-1") == "/api/runtime-center/decisions/decision-1"
    assert schedule_route("schedule-1") == "/api/runtime-center/schedules/schedule-1"
    assert work_context_route("ctx-1") == "/api/runtime-center/work-contexts/ctx-1"


def test_trace_id_from_kernel_meta_prefers_explicit_trace_id() -> None:
    assert trace_id_from_kernel_meta("task-1", {"trace_id": "trace-override"}) == "trace-override"
    assert trace_id_from_kernel_meta("task-1", {}) == "trace:task-1"


def test_build_task_review_payload_preserves_runtime_review_contract() -> None:
    now = datetime(2026, 3, 26, 8, 0, tzinfo=timezone.utc)
    task = SimpleNamespace(
        id="task-1",
        title="Organize desktop files",
        summary="Move desktop files into categorized folders",
        owner_agent_id="agent-1",
        status="running",
        acceptance_criteria='{"kernel":"meta"}',
        updated_at=now,
    )
    runtime = SimpleNamespace(
        current_phase="executing",
        last_result_summary="Document files were moved to target folders",
        last_error_summary=None,
        updated_at=now,
        risk_level="guarded",
    )
    decisions = [SimpleNamespace(status="open")]
    evidence = [
        EvidenceRecord(
            id="evidence-1",
            task_id="task-1",
            actor_ref="agent-1",
            risk_level="auto",
            action_summary="Move desktop documents",
            result_summary="Documents moved successfully",
            created_at=now,
        ),
    ]

    payload = build_task_review_payload(
        task=task,
        runtime=runtime,
        decisions=decisions,
        evidence=evidence,
        execution_feedback={
            "current_stage": "file sorting",
            "effective_actions": ["group by file extension before moving"],
            "avoid_repeats": ["do not rescan already moved folders"],
        },
        child_results=[
            {"status": "completed"},
            {"status": "running"},
        ],
        owner_agent={"name": "Desktop Clerk"},
        task_route=task_route("task-1"),
    )

    assert payload["status"] == "running"
    assert payload["phase"] == "executing"
    assert payload["pending_decision_count"] == 1
    assert payload["child_task_count"] == 2
    assert payload["child_terminal_count"] == 1
    assert payload["owner_agent_name"] == "Desktop Clerk"
    assert payload["task_route"] == "/api/runtime-center/tasks/task-1"
    assert payload["review_route"] == "/api/runtime-center/tasks/task-1/review"
    assert payload["summary_lines"][0].endswith("Move desktop files into categorized folders")
    assert payload["next_actions"]
    assert payload["risks"]


def test_build_task_review_payload_projects_execution_runtime_visibility_from_feedback() -> None:
    now = datetime(2026, 3, 26, 9, 0, tzinfo=timezone.utc)
    task = SimpleNamespace(
        id="task-host-1",
        title="Host Runtime Task",
        summary="Keep host session stable while processing files",
        owner_agent_id="agent-1",
        status="running",
        acceptance_criteria='{"kernel":"meta"}',
        updated_at=now,
    )
    runtime = SimpleNamespace(
        current_phase="executing",
        last_result_summary="Processing is waiting on host confirmation",
        last_error_summary=None,
        updated_at=now,
        risk_level="guarded",
    )
    payload = build_task_review_payload(
        task=task,
        runtime=runtime,
        decisions=[],
        evidence=[],
        execution_feedback={
            "workspace_graph": {
                "projection_kind": "workspace_graph_projection",
                "workspace_id": "ws-1",
                "active_lock_summary": "excel:writer-lock",
                "download_status": {
                    "bucket_refs": ["download-bucket:ws-1"],
                    "active_bucket_ref": "download-bucket:ws-1",
                    "download_policy": "download-bucket:ws-1",
                    "download_verification": True,
                },
                "surface_contracts": {
                    "browser_active_site": "jd:seller-center",
                    "browser_site_contract_status": "verified-writer",
                    "desktop_app_identity": "excel",
                    "desktop_app_contract_status": "handoff-required",
                },
                "locks": [
                    {
                        "resource_ref": "excel:writer-lock",
                        "writer_lock": {
                            "status": "held",
                            "owner_agent_id": "agent-1",
                        },
                    },
                ],
                "surfaces": {
                    "browser": {
                        "active_tab": {
                            "tab_id": "tab-7",
                            "site": "jd:seller-center",
                        },
                    },
                    "desktop": {
                        "active_window": {
                            "app_identity": "excel",
                            "window_scope": "window:excel:main",
                        },
                    },
                },
                "latest_host_event_summary": {
                    "event_name": "uac_prompt",
                    "severity": "guarded",
                },
            },
            "cooperative_adapter_availability": {
                "status": "available",
                "adapters": ["desktop", "browser"],
            },
            "host_contract": {
                "status": "blocked",
                "blocked_reason": "uac-prompt",
                "host_mode": "symbiotic",
                "handoff_state": "handoff-required",
                "handoff_reason": "uac-prompt",
                "verification_channel": "runtime-center-self-check",
            },
            "recovery": {
                "status": "pending",
                "mode": "resume-environment",
            },
            "host_event_summary": {
                "last_event": "uac_prompt",
                "count": 3,
                "counts_by_topic": {
                    "system": 2,
                    "browser": 1,
                },
                "latest_event": {
                    "event_name": "uac_prompt",
                    "topic": "system",
                    "action": "recovery",
                    "payload": {
                        "prompt_kind": "uac",
                        "window_title": "User Account Control",
                    },
                },
                "counts_by_topic": {
                    "system": 2,
                    "browser": 1,
                },
                "pending_recovery_events": [
                    {
                        "event_name": "uac_prompt",
                        "checkpoint": {
                            "resume_kind": "resume-environment",
                        },
                    },
                ],
            },
            "seat_runtime": {
                "seat_id": "seat-1",
                "session_id": "session-1",
                "status": "degraded",
            },
            "browser_site_contract": {
                "browser_mode": "attach-existing-session",
                "active_site": "jd:seller-center",
                "authenticated_continuation": True,
                "download_verification": True,
                "save_reopen_verification": True,
                "download_bucket_refs": ["download-bucket:ws-1"],
            },
            "desktop_app_contract": {
                "app_identity": "excel",
                "window_scope": "window:excel:main",
                "current_gap_or_blocker": "uac-prompt",
                "blocker_event_family": "modal-uac-login",
                "recovery_mode": "resume-environment",
            },
        },
        child_results=[],
        owner_agent={"name": "Seat Operator"},
        task_route=task_route("task-host-1"),
    )

    assert payload["execution_runtime"]["workspace"]["workspace_id"] == "ws-1"
    assert (
        payload["execution_runtime"]["workspace"]["projection_kind"]
        == "workspace_graph_projection"
    )
    assert (
        payload["execution_runtime"]["workspace"]["locks"][0]["resource_ref"]
        == "excel:writer-lock"
    )
    assert (
        payload["execution_runtime"]["workspace"]["locks"][0]["writer_lock"]["owner_agent_id"]
        == "agent-1"
    )
    assert (
        payload["execution_runtime"]["workspace"]["locks"][0]["writer_lock"]["status"]
        == "held"
    )
    assert (
        payload["execution_runtime"]["workspace"]["surfaces"]["browser"]["active_tab"]["tab_id"]
        == "tab-7"
    )
    assert (
        payload["execution_runtime"]["workspace"]["surfaces"]["desktop"]["active_window"]["window_scope"]
        == "window:excel:main"
    )
    assert (
        payload["execution_runtime"]["workspace"]["latest_host_event_summary"]["severity"]
        == "guarded"
    )
    assert (
        payload["execution_runtime"]["workspace"]["latest_host_event_summary"]["event_name"]
        == "uac_prompt"
    )
    assert payload["execution_runtime"]["workspace"]["download_status"]["download_verification"] is True
    assert (
        payload["execution_runtime"]["workspace"]["surface_contracts"]["browser_active_site"]
        == "jd:seller-center"
    )
    assert (
        payload["execution_runtime"]["workspace"]["surface_contracts"]["desktop_app_contract_status"]
        == "handoff-required"
    )
    assert (
        payload["execution_runtime"]["cooperative_adapter_availability"]["status"]
        == "available"
    )
    assert payload["execution_runtime"]["host"]["blocked_reason"] == "uac-prompt"
    assert payload["execution_runtime"]["recovery"]["mode"] == "resume-environment"
    assert payload["execution_runtime"]["host_event_summary"]["last_event"] == "uac_prompt"
    assert (
        payload["execution_runtime"]["host_event_summary"]["latest_event"]["payload"]["window_title"]
        == "User Account Control"
    )
    assert (
        payload["execution_runtime"]["host_event_summary"]["counts_by_topic"]["system"]
        == 2
    )
    assert (
        payload["execution_runtime"]["host_event_summary"]["pending_recovery_events"][0]["checkpoint"]["resume_kind"]
        == "resume-environment"
    )
    assert (
        payload["continuity"]["handoff"]["state"]
        == "handoff-required"
    )
    assert payload["continuity"]["handoff"]["reason"] == "uac-prompt"
    assert payload["execution_runtime"]["seat_runtime"]["seat_id"] == "seat-1"
    assert (
        payload["execution_runtime"]["browser_site_contract"]["active_site"]
        == "jd:seller-center"
    )
    assert (
        payload["execution_runtime"]["browser_site_contract"]["authenticated_continuation"]
        is True
    )
    assert (
        payload["execution_runtime"]["browser_site_contract"]["download_verification"]
        is True
    )
    assert (
        payload["execution_runtime"]["browser_site_contract"]["save_reopen_verification"]
        is True
    )
    assert (
        payload["execution_runtime"]["desktop_app_contract"]["app_identity"]
        == "excel"
    )
    assert (
        payload["execution_runtime"]["desktop_app_contract"]["current_gap_or_blocker"]
        == "uac-prompt"
    )
    assert (
        payload["execution_runtime"]["desktop_app_contract"]["blocker_event_family"]
        == "modal-uac-login"
    )
    assert any("Host blocker" in line for line in payload["summary_lines"])
    assert any("recovery" in action.lower() for action in payload["next_actions"])
    assert any("host blocker" in risk.lower() for risk in payload["risks"])


def test_build_task_review_payload_uses_runtime_metadata_for_visibility_fallback() -> None:
    now = datetime(2026, 3, 26, 10, 0, tzinfo=timezone.utc)
    task = SimpleNamespace(
        id="task-host-2",
        title="Metadata Runtime Task",
        summary="Read runtime metadata and project it into review",
        owner_agent_id="agent-1",
        status="running",
        acceptance_criteria='{"kernel":"meta"}',
        updated_at=now,
    )
    runtime = SimpleNamespace(
        current_phase="executing",
        last_result_summary="Runtime metadata is present",
        last_error_summary=None,
        updated_at=now,
        risk_level="auto",
        metadata={
            "workspace_graph": {
                "workspace_id": "ws-meta",
                "projection_kind": "workspace_graph_projection",
                "surface_contracts": {
                    "browser_active_site": "shopify:admin",
                    "browser_site_contract_status": "verified-writer",
                    "desktop_app_identity": "notion",
                    "desktop_app_contract_status": "ready",
                },
                "locks": [
                    {
                        "resource_ref": "notion:writer-lock",
                        "writer_lock": {
                            "status": "held",
                            "owner_agent_id": "agent-1",
                        },
                    },
                ],
                "surfaces": {
                    "browser": {
                        "active_tab": {
                            "tab_id": "tab-meta",
                            "site": "shopify:admin",
                        },
                    },
                    "desktop": {
                        "active_window": {
                            "app_identity": "notion",
                            "window_scope": "window:notion:main",
                        },
                    },
                },
                "latest_host_event_summary": {
                    "event_name": "resume_attached",
                    "severity": "auto",
                },
            },
            "cooperative_adapter_availability": {
                "status": "degraded",
                "adapters": ["desktop"],
            },
            "host_contract": {"status": "ready", "host_mode": "symbiotic"},
            "recovery": {"status": "attached", "mode": "attach-environment"},
            "host_event_summary": {
                "last_event": "resume_attached",
                "latest_event": {
                    "event_name": "resume_attached",
                    "topic": "runtime",
                    "action": "attach",
                },
                "counts_by_topic": {
                    "runtime": 1,
                },
            },
            "seat_runtime": {"seat_id": "seat-meta"},
            "browser_site_contract": {
                "browser_mode": "managed-isolated",
                "active_site": "shopify:admin",
            },
            "desktop_app_contract": {
                "app_identity": "notion",
                "window_scope": "window:notion:main",
            },
        },
    )
    payload = build_task_review_payload(
        task=task,
        runtime=runtime,
        decisions=[],
        evidence=[],
        execution_feedback={},
        child_results=[],
        owner_agent={"name": "Seat Operator"},
        task_route=task_route("task-host-2"),
    )

    assert payload["execution_runtime"]["workspace"]["workspace_id"] == "ws-meta"
    assert (
        payload["execution_runtime"]["workspace"]["projection_kind"]
        == "workspace_graph_projection"
    )
    assert (
        payload["execution_runtime"]["workspace"]["locks"][0]["resource_ref"]
        == "notion:writer-lock"
    )
    assert (
        payload["execution_runtime"]["workspace"]["locks"][0]["writer_lock"]["status"]
        == "held"
    )
    assert (
        payload["execution_runtime"]["workspace"]["locks"][0]["writer_lock"]["owner_agent_id"]
        == "agent-1"
    )
    assert (
        payload["execution_runtime"]["workspace"]["surfaces"]["browser"]["active_tab"]["site"]
        == "shopify:admin"
    )
    assert (
        payload["execution_runtime"]["workspace"]["surfaces"]["desktop"]["active_window"]["window_scope"]
        == "window:notion:main"
    )
    assert (
        payload["execution_runtime"]["workspace"]["latest_host_event_summary"]["event_name"]
        == "resume_attached"
    )
    assert (
        payload["execution_runtime"]["workspace"]["surface_contracts"]["desktop_app_identity"]
        == "notion"
    )
    assert (
        payload["execution_runtime"]["workspace"]["surface_contracts"]["desktop_app_contract_status"]
        == "ready"
    )
    assert (
        payload["execution_runtime"]["cooperative_adapter_availability"]["status"]
        == "degraded"
    )
    assert payload["execution_runtime"]["host"]["host_mode"] == "symbiotic"
    assert payload["execution_runtime"]["recovery"]["mode"] == "attach-environment"
    assert payload["execution_runtime"]["host_event_summary"]["last_event"] == "resume_attached"
    assert (
        payload["execution_runtime"]["host_event_summary"]["latest_event"]["action"]
        == "attach"
    )
    assert (
        payload["execution_runtime"]["host_event_summary"]["counts_by_topic"]["runtime"]
        == 1
    )
    assert payload["execution_runtime"]["seat_runtime"]["seat_id"] == "seat-meta"
    assert (
        payload["execution_runtime"]["browser_site_contract"]["browser_mode"]
        == "managed-isolated"
    )
    assert (
        payload["execution_runtime"]["desktop_app_contract"]["window_scope"]
        == "window:notion:main"
    )


def test_build_task_review_payload_prefers_host_twin_visibility_when_present() -> None:
    now = datetime(2026, 3, 27, 9, 30, tzinfo=timezone.utc)
    task = SimpleNamespace(
        id="task-host-twin-1",
        title="Recover writer flow from host twin",
        summary="Resume the Orders workbook writer flow safely.",
        owner_agent_id="ops-agent",
        status="running",
        acceptance_criteria='{"kind":"kernel-task-meta-v1"}',
        updated_at=now,
    )
    runtime = SimpleNamespace(
        current_phase="executing",
        last_result_summary="Writer flow is paused pending host recovery.",
        last_error_summary=None,
        updated_at=now,
        risk_level="guarded",
    )

    payload = build_task_review_payload(
        task=task,
        runtime=runtime,
        decisions=[],
        evidence=[],
        execution_feedback={
            "host_companion_session": {
                "session_mount_id": "session-host-companion-1",
                "environment_id": "env-host-companion-1",
                "continuity_status": "restorable",
                "continuity_source": "live-handle",
                "locality": {
                    "same_host": True,
                    "same_process": False,
                    "startup_recovery_required": False,
                },
            },
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
                    "writer-lock",
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
                "multi_seat_coordination": {
                    "seat_count": 2,
                    "candidate_seat_refs": [
                        "env:session:session:web:main",
                        "env:session:session:backup",
                    ],
                    "selected_seat_ref": "env:session:session:web:main",
                    "seat_selection_policy": "sticky-active-seat",
                    "occupancy_state": "occupied",
                    "status": "active",
                    "host_companion_status": "restorable",
                    "active_surface_mix": ["browser", "desktop-app"],
                },
                "app_family_readiness": {
                    "active_family_keys": ["office_document"],
                    "active_family_count": 1,
                    "ready_family_keys": ["office_document"],
                    "ready_family_count": 1,
                    "blocked_family_keys": [],
                    "blocked_family_count": 0,
                    "family_statuses": {
                        "office_document": {
                            "active": True,
                            "ready": True,
                            "contract_status": "verified-writer",
                            "surface_ref": "window:excel:orders",
                            "family_scope_ref": "app:excel",
                            "writer_lock_scope": "workbook:orders",
                        },
                    },
                },
            },
            "host_contract": {
                "status": "blocked",
                "blocked_reason": "legacy-host-blocker",
                "handoff_state": "handoff-required",
                "handoff_reason": "legacy-handoff",
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
        task_route=task_route("task-host-twin-1"),
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
    assert (
        payload["execution_runtime"]["host_twin_summary"]["seat_owner_ref"]
        == "ops-agent"
    )
    assert (
        payload["execution_runtime"]["host_twin_summary"]["active_app_family_count"]
        == 1
    )
    assert payload["execution_runtime"]["host_twin_summary"]["active_app_family_keys"] == [
        "office_document",
    ]
    assert payload["execution_runtime"]["host_twin_summary"]["host_companion_status"] == "restorable"
    assert payload["execution_runtime"]["host_twin_summary"]["host_companion_source"] == "live-handle"
    assert payload["execution_runtime"]["host_twin_summary"]["seat_count"] == 2
    assert payload["execution_runtime"]["host_twin_summary"]["multi_seat_coordination"][
        "selected_seat_ref"
    ] == "env:session:session:web:main"
    assert payload["execution_runtime"]["host_twin_summary"]["app_family_readiness"][
        "ready_family_keys"
    ] == ["office_document"]
    assert (
        payload["execution_runtime"]["host_twin_summary"]["recommended_scheduler_action"]
        == "handoff"
    )
    assert payload["continuity"]["handoff"]["owner_ref"] == "human-operator:alice"
    assert payload["continuity"]["handoff"]["resume_kind"] == "resume-runtime"
    assert payload["continuity"]["verification"]["latest_anchor"] == "excel://Orders!A1"
    assert any("Coordination: handoff" in line for line in payload["summary_lines"])
    assert any("App families ready: office_document" in line for line in payload["summary_lines"])
    assert any("sticky-active-seat" in line for line in payload["summary_lines"])
    assert any(
        "Follow host coordination action: handoff" in action
        for action in payload["next_actions"]
    )
    assert any("modal-uac-login" in line for line in payload["summary_lines"])
    assert any("Orders workbook" in action for action in payload["next_actions"])
    assert any("resume-runtime" in action for action in payload["next_actions"])
    assert any(
        "Host coordination contention is blocked" in risk
        for risk in payload["risks"]
    )
    assert any("modal-uac-login" in risk for risk in payload["risks"])


def test_build_task_review_payload_prefers_canonical_host_twin_summary_for_reentry() -> None:
    now = datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc)
    task = SimpleNamespace(
        id="task-host-twin-reentry-1",
        title="Resume reentered writer session",
        summary="Prefer canonical host summary after clean reentry.",
        owner_agent_id="ops-agent",
        status="running",
        acceptance_criteria='{"kind":"kernel-task-meta-v1"}',
        updated_at=now,
    )
    runtime = SimpleNamespace(
        current_phase="executing",
        last_result_summary="Canonical host summary says the writer can continue.",
        last_error_summary=None,
        updated_at=now,
        risk_level="guarded",
    )

    payload = build_task_review_payload(
        task=task,
        runtime=runtime,
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
        task_route=task_route("task-host-twin-reentry-1"),
    )

    assert (
        payload["execution_runtime"]["host_twin_summary"]["recommended_scheduler_action"]
        == "proceed"
    )
    assert payload["continuity"]["handoff"]["state"] is None
    assert payload["continuity"]["handoff"]["reason"] is None
    assert payload["continuity"]["handoff"]["resume_kind"] == "resume-environment"
    assert any("Host twin coordination: proceed" in line for line in payload["summary_lines"])
    assert not any("Handoff:" in line for line in payload["summary_lines"])
    assert not any("Host blocker:" in line for line in payload["summary_lines"])
    assert not any(
        "Follow host coordination action: handoff" in action
        for action in payload["next_actions"]
    )
    assert not any("Handoff is active" in risk for risk in payload["risks"])
    assert not any("Host blocker detected" in risk for risk in payload["risks"])
