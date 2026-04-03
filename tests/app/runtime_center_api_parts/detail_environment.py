# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from .shared import *  # noqa: F401,F403

from copaw.capabilities import CapabilityService
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelDispatcher, KernelTaskStore
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def _wire_governed_patch_runtime(app: FastAPI, tmp_path: Path) -> None:
    state_store = SQLiteStateStore(tmp_path / "patch-governance.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "patch-governance.evidence.sqlite3")
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        learning_service=app.state.learning_service,
    )
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


def test_runtime_center_detail_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.task_repository = FakeTaskRepository()
    app.state.goal_service = FakeGoalService()
    app.state.decision_request_repository = FakeDecisionRequestRepository()
    app.state.evidence_query_service = FakeEvidenceQueryService()

    client = TestClient(app)

    tasks = client.get("/runtime-center/tasks")
    assert tasks.status_code == 200
    assert tasks.json()[0]["id"] == "task-1"

    agents = client.get("/runtime-center/agents")
    assert agents.status_code == 200
    assert agents.json()[0]["agent_id"] == "ops-agent"
    assert "current_goal_id" not in agents.json()[0]
    assert "current_goal" not in agents.json()[0]

    task_detail = client.get("/runtime-center/tasks/task-1")
    assert task_detail.status_code == 200
    assert task_detail.json()["task"]["id"] == "task-1"
    assert task_detail.json()["route"] == "/api/runtime-center/tasks/task-1"

    goal_detail = client.get("/goals/goal-1/detail")
    assert goal_detail.status_code == 200
    assert goal_detail.json()["goal"]["id"] == "goal-1"

    agent_detail = client.get("/runtime-center/agents/ops-agent")
    assert agent_detail.status_code == 200
    assert agent_detail.json()["agent"]["agent_id"] == "ops-agent"
    assert agent_detail.json()["agent"]["current_focus_kind"] == "goal"
    assert agent_detail.json()["agent"]["current_focus_id"] == "goal-1"
    assert agent_detail.json()["agent"]["current_focus"] == "Launch runtime center"
    assert "current_goal_id" not in agent_detail.json()["agent"]
    assert "current_goal" not in agent_detail.json()["agent"]
    assert agent_detail.json()["tasks"][0]["route"] == "/api/runtime-center/tasks/task-1"
    assert agent_detail.json()["workspace"]["files_supported"] is True
    assert (
        agent_detail.json()["environments"][0]["route"]
        == "/api/runtime-center/environments/env:workspace:workspace:main"
    )

    patch_detail = client.get("/runtime-center/learning/patches/patch-1")
    assert patch_detail.status_code == 200
    assert patch_detail.json()["patch"]["id"] == "patch-1"
    assert patch_detail.json()["routes"]["goal"] == "/api/goals/goal-1/detail"
    assert (
        patch_detail.json()["actions"]["apply"]
        == "/api/runtime-center/learning/patches/patch-1/apply"
    )

    growth_detail = client.get("/runtime-center/learning/growth/growth-1")
    assert growth_detail.status_code == 200
    assert growth_detail.json()["event"]["id"] == "growth-1"
    assert growth_detail.json()["routes"]["patch"] == "/api/runtime-center/learning/patches/patch-1"


def test_runtime_center_environment_read_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.environment_service = FakeEnvironmentService()

    client = TestClient(app)

    env_response = client.get("/runtime-center/environments")
    assert env_response.status_code == 200
    assert env_response.json()[0]["id"].startswith("env:session:")
    assert env_response.json()[0]["host_contract"]["host_mode"] == "local-managed"
    assert env_response.json()[0]["seat_runtime"]["seat_ref"] == "env:session:session:web:main"
    assert env_response.json()[0]["workspace_graph"]["workspace_id"] == "workspace:copaw:main"
    assert env_response.json()[0]["workspace_graph"]["projection_kind"] == "workspace_graph_projection"
    assert env_response.json()[0]["workspace_graph"]["is_projection"] is True
    assert env_response.json()[0]["workspace_graph"]["clipboard_refs"] == ["clipboard:workspace:main"]
    assert env_response.json()[0]["workspace_graph"]["download_bucket_refs"] == [
        "download-bucket:workspace:copaw:main",
    ]
    assert env_response.json()[0]["workspace_graph"]["lock_refs"] == ["excel:writer-lock"]
    assert env_response.json()[0]["workspace_graph"]["active_surface_refs"] == [
        "browser:web:main",
        "window:excel:main",
        "doc:workspace:copaw",
        "clipboard:workspace:main",
        "download-bucket:workspace:copaw:main",
    ]
    assert env_response.json()[0]["workspace_graph"]["workspace_components"] == {
        "browser_context_count": 1,
        "app_window_count": 1,
        "file_doc_count": 1,
        "clipboard_count": 1,
        "download_bucket_count": 1,
        "lock_count": 1,
    }
    assert env_response.json()[0]["workspace_graph"]["handoff_checkpoint"]["state"] == (
        "agent-attached"
    )
    assert env_response.json()[0]["workspace_graph"]["active_lock_summary"] == "excel:writer-lock"
    assert env_response.json()[0]["workspace_graph"]["download_status"] == {
        "bucket_refs": ["download-bucket:workspace:copaw:main"],
        "active_bucket_ref": "download-bucket:workspace:copaw:main",
        "download_policy": "workspace-bucket",
        "download_verification": True,
        "latest_download_event": {
            "event_id": 3,
            "event_name": "download-finished",
            "topic": "download",
            "action": "download-completed",
            "created_at": "2026-03-09T09:02:00+00:00",
            "severity": "low",
            "recommended_runtime_response": "re-observe",
        },
    }
    assert env_response.json()[0]["workspace_graph"]["surface_contracts"] == {
        "browser_active_site": "jd:seller-center",
        "browser_site_contract_status": "verified-writer",
        "desktop_app_identity": "excel",
        "desktop_app_contract_status": "verified-writer",
    }
    assert env_response.json()[0]["workspace_graph"]["owner_agent_id"] == "ops-agent"
    assert env_response.json()[0]["workspace_graph"]["account_scope_ref"] == (
        "windows:user:alice"
    )
    assert env_response.json()[0]["workspace_graph"]["workspace_scope"] == "project:copaw"
    assert env_response.json()[0]["workspace_graph"]["ownership"] == {
        "owner_agent_id": "ops-agent",
        "handoff_owner_ref": "human-operator:alice",
        "account_scope_ref": "windows:user:alice",
        "workspace_scope": "project:copaw",
        "session_scope": "desktop-user-session",
        "lease_class": "seat-runtime",
        "access_mode": "desktop-app",
    }
    assert env_response.json()[0]["workspace_graph"]["collision_facts"] == {
        "account_scope_ref": "windows:user:alice",
        "writer_lock_scope": "workbook:weekly-report",
        "active_lock_summary": "excel:writer-lock",
        "handoff_state": "agent-attached",
        "handoff_reason": "captcha-required",
        "handoff_owner_ref": "human-operator:alice",
        "current_gap_or_blocker": None,
        "blocking_event_family": "modal-uac-login",
        "shared_surface_owner": "ops-agent",
        "requires_human_return": True,
    }
    assert env_response.json()[0]["workspace_graph"]["collision_summary"] == "excel:writer-lock"
    assert env_response.json()[0]["workspace_graph"]["locks"] == [
        {
            "resource_ref": "excel:writer-lock",
            "summary": "excel:writer-lock",
            "surface_ref": "window:excel:main",
            "account_scope_ref": "windows:user:alice",
            "writer_lock": {
                "status": "held",
                "scope": "workbook:weekly-report",
                "owner_agent_id": "ops-agent",
                "lease_class": "seat-runtime",
                "access_mode": "desktop-app",
                "handoff_state": "agent-attached",
                "handoff_owner_ref": "human-operator:alice",
            },
        },
    ]
    assert (
        env_response.json()[0]["workspace_graph"]["surfaces"]["browser"]["context_refs"]
        == ["browser:web:main"]
    )
    assert (
        env_response.json()[0]["workspace_graph"]["surfaces"]["browser"]["active_tab"]["site"]
        == "jd:seller-center"
    )
    assert (
        env_response.json()[0]["workspace_graph"]["surfaces"]["desktop"]["active_window"][
            "window_scope"
        ]
        == "window:excel:main"
    )
    assert (
        env_response.json()[0]["workspace_graph"]["surfaces"]["file_docs"]["active_doc_ref"]
        == "doc:workspace:copaw"
    )
    assert (
        env_response.json()[0]["workspace_graph"]["surfaces"]["clipboard"][
            "active_clipboard_ref"
        ]
        == "clipboard:workspace:main"
    )
    assert (
        env_response.json()[0]["workspace_graph"]["surfaces"]["downloads"]["active_bucket"][
            "bucket_ref"
        ]
        == "download-bucket:workspace:copaw:main"
    )
    assert (
        env_response.json()[0]["workspace_graph"]["surfaces"]["host_blocker"]["event_family"]
        == "modal-uac-login"
    )
    assert "derived runtime projection" in env_response.json()[0]["workspace_graph"]["projection_note"]
    assert (
        env_response.json()[0]["host_event_summary"]["latest_event"]["event_name"]
        == "network-restored"
    )
    assert env_response.json()[0]["host_event_summary"]["supported_families"] == [
        "active-window",
        "modal-uac-login",
        "download-completed",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    ]
    assert env_response.json()[0]["host_event_summary"]["family_counts"] == {
        "active-window": 1,
        "modal-uac-login": 1,
        "download-completed": 1,
        "process-exit-restart": 1,
        "lock-unlock": 1,
        "network-power": 1,
    }
    assert (
        env_response.json()[0]["host_event_summary"]["latest_event_by_family"]["modal-uac-login"][
            "recommended_runtime_response"
        ]
        == "handoff"
    )
    assert env_response.json()[0]["host_event_summary"]["active_alert_families"] == [
        "modal-uac-login",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    ]

    env_limited_response = client.get(
        "/runtime-center/environments",
        params={"limit": 0},
    )
    assert env_limited_response.status_code == 200
    assert env_limited_response.json() == []

    summary_response = client.get("/runtime-center/environments/summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["total"] == 1

    detail_response = client.get(
        "/runtime-center/environments/env:session:session:web:main",
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["ref"] == "session:web:main"
    assert detail_response.json()["stats"]["session_count"] == 1
    assert detail_response.json()["host_contract"]["lease_class"] == "seat-runtime"
    assert detail_response.json()["host_contract"]["handoff_state"] == "agent-attached"
    assert detail_response.json()["seat_runtime"]["host_mode"] == "local-managed"
    assert detail_response.json()["seat_runtime"]["status"] == "active"
    assert detail_response.json()["seat_runtime"]["occupancy_state"] == "occupied"
    assert detail_response.json()["seat_runtime"]["candidate_seat_refs"] == [
        "env:session:session:web:main",
    ]
    assert (
        detail_response.json()["seat_runtime"]["selected_seat_ref"]
        == "env:session:session:web:main"
    )
    assert (
        detail_response.json()["seat_runtime"]["seat_selection_policy"]
        == "sticky-active-seat"
    )
    assert (
        detail_response.json()["host_companion_session"]["session_mount_id"]
        == "session:web:main"
    )
    assert (
        detail_response.json()["browser_site_contract"]["browser_mode"]
        == "attach-existing-session"
    )
    assert (
        detail_response.json()["browser_site_contract"]["site_contract_status"]
        == "verified-writer"
    )
    assert (
        detail_response.json()["browser_site_contract"]["last_verified_dom_anchor"]
        == "#shop-header"
    )
    assert detail_response.json()["desktop_app_contract"]["app_identity"] == "excel"
    assert (
        detail_response.json()["desktop_app_contract"]["control_channel"]
        == "accessibility-tree"
    )
    assert (
        detail_response.json()["desktop_app_contract"]["window_anchor_summary"]
        == "Excel > Weekly Report.xlsx > Sheet1!A1"
    )
    assert detail_response.json()["workspace_graph"]["workspace_id"] == "workspace:copaw:main"
    assert detail_response.json()["workspace_graph"]["projection_kind"] == (
        "workspace_graph_projection"
    )
    assert detail_response.json()["workspace_graph"]["is_projection"] is True
    assert detail_response.json()["workspace_graph"]["pending_handoff_summary"] == "agent-attached"
    assert detail_response.json()["workspace_graph"]["clipboard_refs"] == [
        "clipboard:workspace:main",
    ]
    assert detail_response.json()["workspace_graph"]["download_bucket_refs"] == [
        "download-bucket:workspace:copaw:main",
    ]
    assert detail_response.json()["workspace_graph"]["lock_refs"] == ["excel:writer-lock"]
    assert detail_response.json()["workspace_graph"]["active_surface_refs"] == [
        "browser:web:main",
        "window:excel:main",
        "doc:workspace:copaw",
        "clipboard:workspace:main",
        "download-bucket:workspace:copaw:main",
    ]
    assert detail_response.json()["workspace_graph"]["workspace_components"] == {
        "browser_context_count": 1,
        "app_window_count": 1,
        "file_doc_count": 1,
        "clipboard_count": 1,
        "download_bucket_count": 1,
        "lock_count": 1,
    }
    assert detail_response.json()["workspace_graph"]["handoff_checkpoint"] == {
        "state": "agent-attached",
        "reason": "captcha-required",
        "owner_ref": "human-operator:alice",
        "resume_kind": "host-companion-session",
        "verification_channel": "runtime-center-self-check",
        "checkpoint_ref": "checkpoint:captcha:jd-seller",
        "return_condition": "captcha-cleared",
        "summary": "agent-attached",
    }
    assert detail_response.json()["workspace_graph"]["active_lock_summary"] == "excel:writer-lock"
    assert detail_response.json()["workspace_graph"]["download_status"] == {
        "bucket_refs": ["download-bucket:workspace:copaw:main"],
        "active_bucket_ref": "download-bucket:workspace:copaw:main",
        "download_policy": "workspace-bucket",
        "download_verification": True,
        "latest_download_event": {
            "event_id": 3,
            "event_name": "download-finished",
            "topic": "download",
            "action": "download-completed",
            "created_at": "2026-03-09T09:02:00+00:00",
            "severity": "low",
            "recommended_runtime_response": "re-observe",
        },
    }
    assert detail_response.json()["workspace_graph"]["surface_contracts"] == {
        "browser_active_site": "jd:seller-center",
        "browser_site_contract_status": "verified-writer",
        "desktop_app_identity": "excel",
        "desktop_app_contract_status": "verified-writer",
    }
    assert detail_response.json()["workspace_graph"]["owner_agent_id"] == "ops-agent"
    assert detail_response.json()["workspace_graph"]["account_scope_ref"] == (
        "windows:user:alice"
    )
    assert detail_response.json()["workspace_graph"]["workspace_scope"] == "project:copaw"
    assert detail_response.json()["workspace_graph"]["locks"] == [
        {
            "resource_ref": "excel:writer-lock",
            "summary": "excel:writer-lock",
            "surface_ref": "window:excel:main",
            "account_scope_ref": "windows:user:alice",
            "writer_lock": {
                "status": "held",
                "scope": "workbook:weekly-report",
                "owner_agent_id": "ops-agent",
                "lease_class": "seat-runtime",
                "access_mode": "desktop-app",
                "handoff_state": "agent-attached",
                "handoff_owner_ref": "human-operator:alice",
            },
        },
    ]
    assert detail_response.json()["workspace_graph"]["ownership"] == {
        "owner_agent_id": "ops-agent",
        "handoff_owner_ref": "human-operator:alice",
        "account_scope_ref": "windows:user:alice",
        "workspace_scope": "project:copaw",
        "session_scope": "desktop-user-session",
        "lease_class": "seat-runtime",
        "access_mode": "desktop-app",
    }
    assert detail_response.json()["workspace_graph"]["collision_facts"] == {
        "account_scope_ref": "windows:user:alice",
        "writer_lock_scope": "workbook:weekly-report",
        "active_lock_summary": "excel:writer-lock",
        "handoff_state": "agent-attached",
        "handoff_reason": "captcha-required",
        "handoff_owner_ref": "human-operator:alice",
        "current_gap_or_blocker": None,
        "blocking_event_family": "modal-uac-login",
        "shared_surface_owner": "ops-agent",
        "requires_human_return": True,
    }
    assert detail_response.json()["workspace_graph"]["collision_summary"] == "excel:writer-lock"
    assert detail_response.json()["workspace_graph"]["surfaces"] == {
        "browser": {
            "context_refs": ["browser:web:main"],
            "active_tab": {
                "tab_id": "page:jd:seller-center:home",
                "site": "jd:seller-center",
                "tab_scope": "single-tab",
                "login_state": "authenticated",
                "account_scope_ref": "windows:user:alice",
                "handoff_state": "agent-attached",
                "resume_kind": "host-companion-session",
                "verification_channel": "runtime-center-self-check",
                "current_gap_or_blocker": None,
            },
            "site_contract_status": "verified-writer",
            "download_policy": "workspace-bucket",
        },
        "desktop": {
            "window_refs": ["window:excel:main"],
            "active_window": {
                "window_ref": "window:excel:main",
                "app_identity": "excel",
                "window_scope": "window:excel:main",
                "window_anchor_summary": "Excel > Weekly Report.xlsx > Sheet1!A1",
                "writer_lock_scope": "workbook:weekly-report",
                "account_scope_ref": "windows:user:alice",
                "handoff_state": "agent-attached",
                "resume_kind": "host-companion-session",
                "verification_channel": "runtime-center-self-check",
                "current_gap_or_blocker": None,
            },
            "app_contract_status": "verified-writer",
            "adapter_refs": ["app-adapter:excel", "app-adapter:file-explorer"],
        },
        "file_docs": {
            "refs": ["doc:workspace:copaw"],
            "active_doc_ref": "doc:workspace:copaw",
            "workspace_scope": "project:copaw",
        },
        "clipboard": {
            "refs": ["clipboard:workspace:main"],
            "active_clipboard_ref": "clipboard:workspace:main",
            "workspace_scope": "project:copaw",
        },
        "downloads": {
            "bucket_refs": ["download-bucket:workspace:copaw:main"],
            "active_bucket": {
                "bucket_ref": "download-bucket:workspace:copaw:main",
                "download_policy": "workspace-bucket",
                "download_verification": True,
                "latest_event_family": "download-completed",
            },
        },
        "host_blocker": {
            "event_family": "modal-uac-login",
            "event_name": "captcha-required",
            "recommended_runtime_response": "handoff",
        },
    }
    assert "derived runtime projection" in detail_response.json()["workspace_graph"]["projection_note"]
    assert detail_response.json()["host_twin"]["projection_kind"] == "host_twin_projection"
    assert detail_response.json()["host_twin"]["is_projection"] is True
    assert detail_response.json()["host_twin"]["is_truth_store"] is False
    assert detail_response.json()["host_twin"]["seat_ref"] == "env:session:session:web:main"
    assert detail_response.json()["host_twin"]["environment_id"] == "env:session:session:web:main"
    assert detail_response.json()["host_twin"]["session_mount_id"] == "session:web:main"
    assert detail_response.json()["host_twin"]["ownership"] == {
        "seat_owner_agent_id": "ops-agent",
        "handoff_owner_ref": "human-operator:alice",
        "account_scope_ref": "windows:user:alice",
        "workspace_scope": "project:copaw",
        "ownership_source": "workspace_graph.ownership",
        "active_owner_kind": "agent-with-human-handoff",
    }
    assert detail_response.json()["host_twin"]["surface_mutability"] == {
        "browser": {
            "surface_ref": "browser:web:main",
            "mutability": "blocked",
            "safe_to_mutate": False,
            "blocker_family": "modal-uac-login",
        },
        "desktop_app": {
            "surface_ref": "window:excel:main",
            "mutability": "blocked",
            "safe_to_mutate": False,
            "blocker_family": "modal-uac-login",
        },
        "file_docs": {
            "surface_ref": "doc:workspace:copaw",
            "mutability": "blocked",
            "safe_to_mutate": False,
            "blocker_family": "modal-uac-login",
        },
    }
    assert detail_response.json()["host_twin"]["blocked_surfaces"] == [
        {
            "surface_kind": "browser",
            "surface_ref": "browser:web:main",
            "reason": "captcha-required",
            "event_family": "modal-uac-login",
        },
        {
            "surface_kind": "desktop_app",
            "surface_ref": "window:excel:main",
            "reason": "captcha-required",
            "event_family": "modal-uac-login",
        },
        {
            "surface_kind": "file_docs",
            "surface_ref": "doc:workspace:copaw",
            "reason": "captcha-required",
            "event_family": "modal-uac-login",
        },
    ]
    assert detail_response.json()["host_twin"]["continuity"] == {
        "status": "guarded",
        "valid": True,
        "continuity_source": "registered-restorer",
        "resume_kind": "host-companion-session",
        "requires_human_return": True,
    }
    assert detail_response.json()["host_twin"]["trusted_anchors"] == [
        {
            "anchor_kind": "browser-dom",
            "surface_ref": "browser:web:main",
            "anchor_ref": "#shop-header",
            "source": "browser_site_contract.last_verified_dom_anchor",
        },
        {
            "anchor_kind": "desktop-window",
            "surface_ref": "window:excel:main",
            "anchor_ref": "Excel > Weekly Report.xlsx > Sheet1!A1",
            "source": "desktop_app_contract.window_anchor_summary",
        },
        {
            "anchor_kind": "checkpoint",
            "surface_ref": "checkpoint:captcha:jd-seller",
            "anchor_ref": "checkpoint:captcha:jd-seller",
            "source": "workspace_graph.handoff_checkpoint",
        },
    ]
    assert detail_response.json()["host_twin"]["legal_recovery"] == {
        "path": "handoff",
        "checkpoint_ref": "checkpoint:captcha:jd-seller",
        "resume_kind": "host-companion-session",
        "verification_channel": "runtime-center-self-check",
        "return_condition": "captcha-cleared",
    }
    assert detail_response.json()["host_twin"]["active_blocker_families"] == [
        "modal-uac-login",
    ]
    assert detail_response.json()["host_twin"]["latest_blocking_event"] == {
        "event_family": "modal-uac-login",
        "event_name": "captcha-required",
        "recommended_runtime_response": "handoff",
        "surface_refs": [
            "browser:web:main",
            "window:excel:main",
            "doc:workspace:copaw",
        ],
    }
    assert detail_response.json()["host_twin"]["execution_mutation_ready"] == {
        "browser": False,
        "desktop_app": False,
        "file_docs": False,
    }
    assert detail_response.json()["host_twin"]["app_family_twins"] == {
        "browser_backoffice": {
            "active": True,
            "family_kind": "browser_backoffice",
            "surface_ref": "browser:web:main",
            "contract_status": "verified-writer",
            "family_scope_ref": "site:jd:seller-center",
        },
        "messaging_workspace": {
            "active": False,
            "family_kind": "messaging_workspace",
            "surface_ref": None,
            "contract_status": "inactive",
            "family_scope_ref": None,
        },
        "office_document": {
            "active": True,
            "family_kind": "office_document",
            "surface_ref": "window:excel:main",
            "contract_status": "verified-writer",
            "family_scope_ref": "app:excel",
            "writer_lock_scope": "workbook:weekly-report",
        },
        "desktop_specialized": {
            "active": False,
            "family_kind": "desktop_specialized",
            "surface_ref": None,
            "contract_status": "inactive",
            "family_scope_ref": None,
        },
    }
    assert detail_response.json()["host_twin"]["coordination"] == {
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
        "expected_release_at": None,
    }
    assert "derived runtime projection" in detail_response.json()["host_twin"]["projection_note"]
    assert "not a second truth source" in detail_response.json()["host_twin"]["projection_note"]
    assert (
        detail_response.json()["cooperative_adapter_availability"]["projection_kind"]
        == "cooperative_adapter_availability_projection"
    )
    assert detail_response.json()["cooperative_adapter_availability"]["is_projection"] is True
    assert (
        detail_response.json()["cooperative_adapter_availability"]["environment_id"]
        == "env:session:session:web:main"
    )
    assert (
        detail_response.json()["cooperative_adapter_availability"]["session_mount_id"]
        == "session:web:main"
    )
    assert (
        detail_response.json()["cooperative_adapter_availability"]["browser_companion"]["available"]
        is True
    )
    assert (
        detail_response.json()["cooperative_adapter_availability"]["document_bridge"]["status"]
        == "ready"
    )
    assert (
        detail_response.json()["cooperative_adapter_availability"]["watchers"]["downloads"]["status"]
        == "healthy"
    )
    assert (
        detail_response.json()["cooperative_adapter_availability"]["windows_app_adapters"]["app_identity"]
        == "excel"
    )
    assert detail_response.json()["recovery"]["status"] == "restorable"
    assert detail_response.json()["recovery"]["startup_recovery_required"] is False
    assert (
        detail_response.json()["host_event_summary"]["latest_event"]["event_name"]
        == "network-restored"
    )
    assert detail_response.json()["host_event_summary"]["supported_families"] == [
        "active-window",
        "modal-uac-login",
        "download-completed",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    ]
    assert detail_response.json()["host_event_summary"]["family_counts"] == {
        "active-window": 1,
        "modal-uac-login": 1,
        "download-completed": 1,
        "process-exit-restart": 1,
        "lock-unlock": 1,
        "network-power": 1,
    }
    assert (
        detail_response.json()["host_event_summary"]["latest_event_by_family"]["process-exit-restart"][
            "severity"
        ]
        == "high"
    )
    assert detail_response.json()["host_event_summary"]["active_alert_families"] == [
        "modal-uac-login",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    ]
    assert detail_response.json()["host_events"][0]["event_name"] == "window-focus-changed"
    assert detail_response.json()["host_events"][0]["event_family"] == "active-window"
    assert detail_response.json()["host_events"][0]["recommended_runtime_response"] == "re-observe"
    assert detail_response.json()["host_events"][0]["severity"] == "medium"
    assert detail_response.json()["host_events"][1]["event_family"] == "modal-uac-login"
    assert detail_response.json()["host_events"][1]["recommended_runtime_response"] == "handoff"
    assert detail_response.json()["host_events"][1]["severity"] == "high"
    assert detail_response.json()["host_events"][2]["event_family"] == "download-completed"
    assert detail_response.json()["host_events"][2]["recommended_runtime_response"] == "re-observe"
    assert detail_response.json()["host_events"][2]["severity"] == "low"
    assert detail_response.json()["host_events"][3]["event_family"] == "process-exit-restart"
    assert detail_response.json()["host_events"][3]["recommended_runtime_response"] == "recover"
    assert detail_response.json()["host_events"][3]["severity"] == "high"
    assert detail_response.json()["host_events"][4]["event_family"] == "lock-unlock"
    assert detail_response.json()["host_events"][4]["recommended_runtime_response"] == "recover"
    assert detail_response.json()["host_events"][4]["severity"] == "high"
    assert detail_response.json()["host_events"][5]["event_family"] == "network-power"
    assert detail_response.json()["host_events"][5]["recommended_runtime_response"] == "retry"
    assert detail_response.json()["host_events"][5]["severity"] == "medium"

    sessions_response = client.get("/runtime-center/sessions")
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["id"] == "session:web:main"
    assert sessions_response.json()[0]["host_contract"]["access_mode"] == "desktop-app"
    assert sessions_response.json()[0]["recovery"]["recoverable"] is True

    session_detail = client.get("/runtime-center/sessions/session:web:main")
    assert session_detail.status_code == 200
    assert session_detail.json()["channel"] == "web"
    assert session_detail.json()["environment"]["id"] == "env:session:session:web:main"
    assert session_detail.json()["host_contract"]["session_scope"] == "desktop-user-session"
    assert (
        session_detail.json()["host_contract"]["verification_channel"]
        == "runtime-center-self-check"
    )
    assert (
        session_detail.json()["browser_site_contract"]["active_tab_ref"]
        == "page:jd:seller-center:home"
    )
    assert session_detail.json()["browser_site_contract"]["tab_scope"] == "single-tab"
    assert (
        session_detail.json()["desktop_app_contract"]["active_process_ref"]
        == "process:4242"
    )
    assert (
        session_detail.json()["desktop_app_contract"]["app_contract_status"]
        == "verified-writer"
    )
    assert session_detail.json()["seat_runtime"]["active_session_mount_id"] == "session:web:main"
    assert session_detail.json()["seat_runtime"]["status"] == "active"
    assert session_detail.json()["seat_runtime"]["occupancy_state"] == "occupied"
    assert session_detail.json()["seat_runtime"]["candidate_seat_refs"] == [
        "env:session:session:web:main",
    ]
    assert (
        session_detail.json()["seat_runtime"]["selected_seat_ref"]
        == "env:session:session:web:main"
    )
    assert session_detail.json()["workspace_graph"]["workspace_id"] == "workspace:copaw:main"
    assert session_detail.json()["workspace_graph"]["projection_kind"] == (
        "workspace_graph_projection"
    )
    assert session_detail.json()["workspace_graph"]["is_projection"] is True
    assert session_detail.json()["workspace_graph"]["clipboard_refs"] == [
        "clipboard:workspace:main",
    ]
    assert session_detail.json()["workspace_graph"]["download_bucket_refs"] == [
        "download-bucket:workspace:copaw:main",
    ]
    assert session_detail.json()["workspace_graph"]["lock_refs"] == ["excel:writer-lock"]
    assert session_detail.json()["workspace_graph"]["workspace_components"]["clipboard_count"] == 1
    assert session_detail.json()["workspace_graph"]["active_lock_summary"] == "excel:writer-lock"
    assert session_detail.json()["workspace_graph"]["download_status"]["download_verification"] is True
    assert (
        session_detail.json()["workspace_graph"]["surface_contracts"]["browser_active_site"]
        == "jd:seller-center"
    )
    assert session_detail.json()["workspace_graph"]["ownership"]["owner_agent_id"] == "ops-agent"
    assert (
        session_detail.json()["workspace_graph"]["collision_facts"]["writer_lock_scope"]
        == "workbook:weekly-report"
    )
    assert (
        session_detail.json()["workspace_graph"]["locks"][0]["writer_lock"]["owner_agent_id"]
        == "ops-agent"
    )
    assert (
        session_detail.json()["workspace_graph"]["surfaces"]["browser"]["active_tab"]["tab_id"]
        == "page:jd:seller-center:home"
    )
    assert (
        session_detail.json()["workspace_graph"]["surfaces"]["file_docs"]["active_doc_ref"]
        == "doc:workspace:copaw"
    )
    assert (
        session_detail.json()["workspace_graph"]["surfaces"]["clipboard"][
            "active_clipboard_ref"
        ]
        == "clipboard:workspace:main"
    )
    assert (
        session_detail.json()["workspace_graph"]["surfaces"]["host_blocker"][
            "recommended_runtime_response"
        ]
        == "handoff"
    )
    assert session_detail.json()["workspace_graph"]["handoff_checkpoint"]["checkpoint_ref"] == (
        "checkpoint:captcha:jd-seller"
    )
    assert "derived runtime projection" in session_detail.json()["workspace_graph"]["projection_note"]
    assert session_detail.json()["host_twin"]["projection_kind"] == "host_twin_projection"
    assert session_detail.json()["host_twin"]["is_projection"] is True
    assert session_detail.json()["host_twin"]["is_truth_store"] is False
    assert session_detail.json()["host_twin"]["ownership"]["seat_owner_agent_id"] == "ops-agent"
    assert (
        session_detail.json()["host_twin"]["ownership"]["ownership_source"]
        == "workspace_graph.ownership"
    )
    assert session_detail.json()["host_twin"]["surface_mutability"]["browser"] == {
        "surface_ref": "browser:web:main",
        "mutability": "blocked",
        "safe_to_mutate": False,
        "blocker_family": "modal-uac-login",
    }
    assert session_detail.json()["host_twin"]["surface_mutability"]["desktop_app"] == {
        "surface_ref": "window:excel:main",
        "mutability": "blocked",
        "safe_to_mutate": False,
        "blocker_family": "modal-uac-login",
    }
    assert session_detail.json()["host_twin"]["surface_mutability"]["file_docs"] == {
        "surface_ref": "doc:workspace:copaw",
        "mutability": "blocked",
        "safe_to_mutate": False,
        "blocker_family": "modal-uac-login",
    }
    assert session_detail.json()["host_twin"]["blocked_surfaces"] == [
        {
            "surface_kind": "browser",
            "surface_ref": "browser:web:main",
            "reason": "captcha-required",
            "event_family": "modal-uac-login",
        },
        {
            "surface_kind": "desktop_app",
            "surface_ref": "window:excel:main",
            "reason": "captcha-required",
            "event_family": "modal-uac-login",
        },
        {
            "surface_kind": "file_docs",
            "surface_ref": "doc:workspace:copaw",
            "reason": "captcha-required",
            "event_family": "modal-uac-login",
        },
    ]
    assert session_detail.json()["host_twin"]["continuity"] == {
        "status": "guarded",
        "valid": True,
        "continuity_source": "registered-restorer",
        "resume_kind": "host-companion-session",
        "requires_human_return": True,
    }
    assert session_detail.json()["host_twin"]["trusted_anchors"][0] == {
        "anchor_kind": "browser-dom",
        "surface_ref": "browser:web:main",
        "anchor_ref": "#shop-header",
        "source": "browser_site_contract.last_verified_dom_anchor",
    }
    assert session_detail.json()["host_twin"]["trusted_anchors"][1] == {
        "anchor_kind": "desktop-window",
        "surface_ref": "window:excel:main",
        "anchor_ref": "Excel > Weekly Report.xlsx > Sheet1!A1",
        "source": "desktop_app_contract.window_anchor_summary",
    }
    assert session_detail.json()["host_twin"]["trusted_anchors"][2] == {
        "anchor_kind": "checkpoint",
        "surface_ref": "checkpoint:captcha:jd-seller",
        "anchor_ref": "checkpoint:captcha:jd-seller",
        "source": "workspace_graph.handoff_checkpoint",
    }
    assert session_detail.json()["host_twin"]["legal_recovery"] == {
        "path": "handoff",
        "checkpoint_ref": "checkpoint:captcha:jd-seller",
        "resume_kind": "host-companion-session",
        "verification_channel": "runtime-center-self-check",
        "return_condition": "captcha-cleared",
    }
    assert session_detail.json()["host_twin"]["active_blocker_families"] == [
        "modal-uac-login",
    ]
    assert session_detail.json()["host_twin"]["latest_blocking_event"] == {
        "event_family": "modal-uac-login",
        "event_name": "captcha-required",
        "recommended_runtime_response": "handoff",
        "surface_refs": [
            "browser:web:main",
            "window:excel:main",
            "doc:workspace:copaw",
        ],
    }
    assert session_detail.json()["host_twin"]["execution_mutation_ready"] == {
        "browser": False,
        "desktop_app": False,
        "file_docs": False,
    }
    assert session_detail.json()["host_twin"]["app_family_twins"]["browser_backoffice"] == {
        "active": True,
        "family_kind": "browser_backoffice",
        "surface_ref": "browser:web:main",
        "contract_status": "verified-writer",
        "family_scope_ref": "site:jd:seller-center",
    }
    assert session_detail.json()["host_twin"]["app_family_twins"]["office_document"] == {
        "active": True,
        "family_kind": "office_document",
        "surface_ref": "window:excel:main",
        "contract_status": "verified-writer",
        "family_scope_ref": "app:excel",
        "writer_lock_scope": "workbook:weekly-report",
    }
    assert session_detail.json()["host_twin"]["coordination"] == {
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
        "expected_release_at": None,
    }
    assert "derived runtime projection" in session_detail.json()["host_twin"]["projection_note"]
    assert "not a second truth source" in session_detail.json()["host_twin"]["projection_note"]
    assert session_detail.json()["host_companion_session"]["locality"]["same_host"] is True
    assert (
        session_detail.json()["cooperative_adapter_availability"]["preferred_execution_path"]
        == "cooperative-native-first"
    )
    assert (
        session_detail.json()["cooperative_adapter_availability"]["fallback_mode"]
        == "ui-fallback-last"
    )
    assert (
        session_detail.json()["cooperative_adapter_availability"]["browser_companion"]["transport_ref"]
        == "transport:cdp:local"
    )
    assert (
        session_detail.json()["cooperative_adapter_availability"]["document_bridge"]["supported_families"]
        == ["spreadsheets", "documents"]
    )
    assert (
        session_detail.json()["cooperative_adapter_availability"]["watchers"]["filesystem"]["available"]
        is True
    )
    assert (
        session_detail.json()["cooperative_adapter_availability"]["windows_app_adapters"]["adapter_refs"]
        == ["app-adapter:excel", "app-adapter:file-explorer"]
    )
    assert session_detail.json()["host_event_summary"]["supported_families"] == [
        "active-window",
        "modal-uac-login",
        "download-completed",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    ]
    assert session_detail.json()["host_event_summary"]["latest_event_by_family"]["network-power"] == {
        "event_id": 6,
        "event_name": "network-restored",
        "topic": "network",
        "action": "connectivity-changed",
        "created_at": "2026-03-09T09:05:00+00:00",
        "severity": "medium",
        "recommended_runtime_response": "retry",
    }
    assert session_detail.json()["host_events"][0]["event_name"] == "window-focus-changed"
    assert session_detail.json()["host_events"][0]["event_family"] == "active-window"

    obs_response = client.get(
        "/runtime-center/observations",
        params={"environment_ref": "session:web:main"},
    )
    assert obs_response.status_code == 200
    assert obs_response.json()[0]["action_summary"] == "Ran ls"
    observation_detail = client.get("/runtime-center/observations/ev-1")
    assert observation_detail.status_code == 200
    assert observation_detail.json()["capability_ref"] == "tool:execute_shell_command"

    replays_response = client.get(
        "/runtime-center/replays",
        params={"environment_ref": "session:web:main"},
    )
    assert replays_response.status_code == 200
    assert replays_response.json()[0]["replay_id"] == "replay-1"
    replay_detail = client.get("/runtime-center/replays/replay-1")
    assert replay_detail.status_code == 200
    assert replay_detail.json()["storage_uri"] == "file:///tmp/replay-1.txt"

    artifacts_response = client.get(
        "/runtime-center/artifacts",
        params={"environment_ref": "session:web:main"},
    )
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()[0]["artifact_id"] == "artifact-1"
    artifact_detail = client.get("/runtime-center/artifacts/artifact-1")
    assert artifact_detail.status_code == 200
    assert artifact_detail.json()["storage_uri"] == "file:///tmp/artifact-1.txt"


def test_runtime_center_environment_detail_surfaces_host_twin_summary() -> None:
    class _RichEnvironmentService:
        def get_environment_detail(self, env_id: str, *args, **kwargs):
            _ = args, kwargs
            if env_id != "env:session:session:web:main":
                return None
            return {
                "ref": "session:web:main",
                "host_companion_session": {
                    "session_mount_id": "session:web:main",
                    "environment_id": "env:session:session:web:main",
                    "continuity_status": "restorable",
                    "continuity_source": "live-handle",
                },
                "host_twin_summary": {
                    "host_companion_status": "restorable",
                    "host_companion_source": "live-handle",
                    "continuity_state": "blocked",
                    "seat_count": 2,
                    "ready_app_family_keys": [
                        "browser_backoffice",
                        "office_document",
                    ],
                    "blocked_app_family_keys": ["desktop_specialized"],
                },
            }

        def get_session_detail(self, session_mount_id: str, *args, **kwargs):
            _ = args, kwargs
            return self.get_environment_detail(session_mount_id)

    app = build_runtime_center_app()
    app.state.environment_service = _RichEnvironmentService()

    client = TestClient(app)
    response = client.get("/runtime-center/environments/env:session:session:web:main")

    assert response.status_code == 200
    payload = response.json()
    assert payload["host_twin_summary"]["host_companion_status"] == "restorable"
    assert payload["host_twin_summary"]["host_companion_source"] == "live-handle"
    assert payload["host_twin_summary"]["seat_count"] == 2
    assert payload["host_twin_summary"]["ready_app_family_keys"] == [
        "browser_backoffice",
        "office_document",
    ]
    assert payload["host_twin_summary"]["blocked_app_family_keys"] == [
        "desktop_specialized",
    ]
    assert payload["host_twin_summary"]["continuity_state"] == "blocked"


def test_runtime_center_environment_detail_prefers_canonical_host_twin_summary_after_reentry() -> None:
    class _ReentryEnvironmentService:
        def __init__(self) -> None:
            self._reentered = False

        def mark_reentered(self) -> None:
            self._reentered = True

        def get_environment_detail(self, env_id: str, *args, **kwargs):
            _ = args, kwargs
            if env_id != "env:session:session:web:main":
                return None
            return {
                "ref": "session:web:main",
                "host_companion_session": {
                    "session_mount_id": "session:web:main",
                    "environment_id": "env:session:session:web:main",
                    "continuity_status": "attached" if self._reentered else "restorable",
                    "continuity_source": "live-handle",
                },
                "host_twin_summary": {
                    "host_companion_status": "attached" if self._reentered else "restorable",
                    "host_companion_source": "live-handle",
                    "continuity_state": "ready" if self._reentered else "blocked",
                    "seat_count": 2,
                    "recommended_scheduler_action": "proceed" if self._reentered else "handoff",
                    "ready_app_family_keys": [
                        "browser_backoffice",
                        "office_document",
                    ],
                    "blocked_app_family_keys": [] if self._reentered else ["desktop_specialized"],
                },
                "metadata": {
                    "stale_checkpoint_state": "agent-attached",
                    "stale_recommended_scheduler_action": "handoff",
                },
            }

        def get_session_detail(self, session_mount_id: str, *args, **kwargs):
            _ = args, kwargs
            return self.get_environment_detail(session_mount_id)

    service = _ReentryEnvironmentService()
    app = build_runtime_center_app()
    app.state.environment_service = service

    client = TestClient(app)
    before = client.get("/runtime-center/environments/env:session:session:web:main")
    assert before.status_code == 200
    assert before.json()["host_twin_summary"]["recommended_scheduler_action"] == "handoff"
    assert before.json()["host_twin_summary"]["blocked_app_family_keys"] == ["desktop_specialized"]

    service.mark_reentered()
    after = client.get("/runtime-center/environments/env:session:session:web:main")
    assert after.status_code == 200
    payload = after.json()
    assert payload["metadata"]["stale_recommended_scheduler_action"] == "handoff"
    assert payload["host_twin_summary"]["host_companion_status"] == "attached"
    assert payload["host_twin_summary"]["recommended_scheduler_action"] == "proceed"
    assert payload["host_twin_summary"]["blocked_app_family_keys"] == []
    assert payload["host_twin_summary"]["continuity_state"] == "ready"


def test_runtime_center_environment_action_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.environment_service = FakeEnvironmentService()

    client = TestClient(app)

    force_release = client.post(
        "/runtime-center/sessions/session:web:main/lease/force-release",
        json={"reason": "manual release"},
    )
    assert force_release.status_code == 200
    assert force_release.json()["lease_status"] == "released"
    assert force_release.json()["metadata"]["lease_release_reason"] == "manual release"

    execute_replay = client.post(
        "/runtime-center/replays/replay-1/execute",
        json={"actor": "reviewer"},
    )
    assert execute_replay.status_code == 404


def test_runtime_center_bridge_lifecycle_endpoints_drive_canonical_environment_contract(
    tmp_path,
) -> None:
    from copaw.app.runtime_events import RuntimeEventBus
    from copaw.environments import (
        EnvironmentRegistry,
        EnvironmentRepository,
        EnvironmentService,
        SessionMountRepository,
    )

    app = build_runtime_center_app()
    state_store = SQLiteStateStore(tmp_path / "bridge-runtime-center.sqlite3")
    environment_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_repository,
    )
    environment_service = EnvironmentService(registry=registry)
    environment_service.set_session_repository(session_repository)
    runtime_event_bus = RuntimeEventBus(max_events=20)
    environment_service.set_runtime_event_bus(runtime_event_bus)
    app.state.environment_service = environment_service
    app.state.runtime_event_bus = runtime_event_bus

    lease = environment_service.acquire_session_lease(
        channel="web",
        session_id="main",
        owner="ops-agent",
        metadata={
            "environment_ref": "session:web:main",
            "worker_type": "cowork",
            "max_sessions": 4,
            "spawn_mode": "same-dir",
            "reuse_environment_id": "env:bridge:prior",
        },
        handle={"bridge": "worker"},
    )

    client = TestClient(app)

    ack = client.post(
        f"/runtime-center/sessions/{lease.id}/bridge/ack",
        json={
            "lease_token": lease.lease_token,
            "work_id": "work-1",
            "bridge_session_id": "bridge-session-1",
            "workspace_trusted": True,
            "elevated_auth_state": "trusted-device",
            "browser_attach_transport_ref": "transport:cdp:bridge-ack",
            "browser_attach_status": "attached",
            "browser_attach_session_ref": "browser-session:web:main",
            "browser_attach_scope_ref": "site:jd:seller-center",
            "browser_attach_reconnect_token": "reconnect-token-1",
        },
    )
    assert ack.status_code == 200
    assert ack.json()["metadata"]["bridge_work_status"] == "acknowledged"
    assert ack.json()["metadata"]["bridge_session_id"] == "bridge-session-1"

    heartbeat = client.post(
        f"/runtime-center/sessions/{lease.id}/bridge/heartbeat",
        json={
            "lease_token": lease.lease_token,
            "work_id": "work-1",
        },
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["metadata"]["bridge_work_status"] == "running"

    reconnect = client.post(
        f"/runtime-center/sessions/{lease.id}/bridge/reconnect",
        json={
            "lease_token": lease.lease_token,
            "work_id": "work-1",
            "browser_attach_transport_ref": "transport:cdp:bridge-reconnect",
            "browser_attach_status": "reconnecting",
            "browser_attach_session_ref": "browser-session:web:main",
            "browser_attach_scope_ref": "site:jd:seller-center",
            "browser_attach_reconnect_token": "reconnect-token-2",
        },
    )
    assert reconnect.status_code == 200
    assert reconnect.json()["metadata"]["bridge_work_status"] == "reconnecting"

    stop = client.post(
        f"/runtime-center/sessions/{lease.id}/bridge/stop",
        json={
            "work_id": "work-1",
            "force": True,
            "reason": "bridge supervisor stop",
        },
    )
    assert stop.status_code == 200
    assert stop.json()["metadata"]["bridge_work_status"] == "stopped"
    assert stop.json()["metadata"]["bridge_stop_mode"] == "force"

    session_detail = client.get(f"/runtime-center/sessions/{lease.id}")
    assert session_detail.status_code == 200
    detail_payload = session_detail.json()
    assert detail_payload["host_companion_session"]["bridge_registration"] == {
        "worker_type": "cowork",
        "max_sessions": 4,
        "spawn_mode": "same-dir",
        "reuse_environment_id": "env:bridge:prior",
        "bridge_work_id": "work-1",
        "bridge_work_status": "stopped",
        "bridge_heartbeat_at": detail_payload["host_companion_session"][
            "bridge_registration"
        ]["bridge_heartbeat_at"],
        "bridge_session_id": "bridge-session-1",
        "workspace_trusted": True,
        "elevated_auth_state": "trusted-device",
        "bridge_stopped_at": detail_payload["host_companion_session"][
            "bridge_registration"
        ]["bridge_stopped_at"],
        "bridge_stop_mode": "force",
    }
    assert detail_payload["seat_runtime"]["bridge_registration"][
        "bridge_work_status"
    ] == "stopped"
    assert detail_payload["browser_site_contract"]["attach_transport_ref"] is None
    assert detail_payload["browser_site_contract"]["attach_reconnect_token"] is None
    assert (
        detail_payload["cooperative_adapter_availability"]["browser_companion"][
            "transport_ref"
        ]
        is None
    )

    archive = client.post(
        f"/runtime-center/sessions/{lease.id}/bridge/archive",
        json={
            "lease_token": lease.lease_token,
            "reason": "worker archived after completion",
        },
    )
    assert archive.status_code == 200
    assert archive.json()["status"] == "archived"
    assert archive.json()["metadata"]["bridge_work_status"] == "archived"

    deregister = client.post(
        f"/runtime-center/environments/{lease.environment_id}/bridge/deregister",
        json={"reason": "bridge worker stopped"},
    )
    assert deregister.status_code == 200
    deregister_payload = deregister.json()
    assert deregister_payload["status"] == "deregistered"
    assert deregister_payload["metadata"]["bridge_environment_status"] == "deregistered"

    session_after = client.get(f"/runtime-center/sessions/{lease.id}")
    assert session_after.status_code == 200
    assert session_after.json()["status"] == "deregistered"
    assert (
        session_after.json()["host_companion_session"]["bridge_registration"][
            "bridge_work_status"
        ]
        == "deregistered"
    )

    event_names = [event.event_name for event in runtime_event_bus.list_events(limit=20)]
    assert "session.bridge-work-acknowledged" in event_names
    assert "session.bridge-work-heartbeat" in event_names
    assert "session.bridge-work-reconnecting" in event_names
    assert "session.bridge-work-stopped" in event_names
    assert "session.bridge-session-archived" in event_names
    assert "session.bridge-environment-deregistered" in event_names


def test_runtime_center_shared_operator_abort_endpoints_drive_canonical_environment_truth(
    tmp_path,
) -> None:
    from copaw.environments import (
        EnvironmentRegistry,
        EnvironmentRepository,
        EnvironmentService,
        SessionMountRepository,
    )

    app = build_runtime_center_app()
    state_store = SQLiteStateStore(tmp_path / "operator-abort-runtime-center.sqlite3")
    environment_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_repository,
    )
    environment_service = EnvironmentService(registry=registry)
    environment_service.set_session_repository(session_repository)
    app.state.environment_service = environment_service

    lease = environment_service.acquire_session_lease(
        channel="desktop",
        session_id="main",
        owner="ops-agent",
        metadata={
            "environment_ref": "session:web:main",
            "host_mode": "local-managed",
            "access_mode": "desktop-app",
        },
        handle={"bridge": "worker"},
    )
    environment_service.register_windows_app_adapter(
        session_mount_id=lease.id,
        adapter_refs=["app-adapter:excel"],
        app_identity="excel",
        control_channel="accessibility-tree",
        execution_guardrails={
            "operator_abort_channel": "browser",
        },
    )

    client = TestClient(app)

    request_abort = client.post(
        f"/runtime-center/sessions/{lease.id}/operator-abort",
        json={
            "channel": "browser",
            "reason": "operator emergency stop",
        },
    )
    assert request_abort.status_code == 200
    assert request_abort.json()["metadata"]["operator_abort_state"] == {
        "channel": "browser",
        "requested": True,
        "reason": "operator emergency stop",
        "requested_at": request_abort.json()["metadata"]["operator_abort_state"][
            "requested_at"
        ],
    }

    session_detail = client.get(f"/runtime-center/sessions/{lease.id}")
    assert session_detail.status_code == 200
    session_payload = session_detail.json()
    assert session_payload["metadata"]["operator_abort_state"]["requested"] is True
    assert session_payload["metadata"]["operator_abort_state"]["channel"] == "browser"
    assert session_payload["cooperative_adapter_availability"]["operator_abort_state"] == {
        "channel": "browser",
        "requested": True,
        "reason": "operator emergency stop",
        "requested_at": session_payload["cooperative_adapter_availability"][
            "operator_abort_state"
        ]["requested_at"],
    }
    assert (
        session_payload["cooperative_adapter_availability"]["windows_app_adapters"][
            "execution_guardrails"
        ]["operator_abort_requested"]
        is True
    )

    environment_detail = client.get(f"/runtime-center/environments/{lease.environment_id}")
    assert environment_detail.status_code == 200
    environment_payload = environment_detail.json()
    assert environment_payload["metadata"]["operator_abort_state"]["requested"] is True
    assert environment_payload["metadata"]["operator_abort_state"]["channel"] == "browser"
    assert environment_payload["desktop_app_contract"]["operator_abort_state"] == {
        "channel": "browser",
        "requested": True,
        "reason": "operator emergency stop",
        "requested_at": environment_payload["desktop_app_contract"][
            "operator_abort_state"
        ]["requested_at"],
    }

    clear_abort = client.post(
        f"/runtime-center/sessions/{lease.id}/operator-abort/clear",
        json={},
    )
    assert clear_abort.status_code == 200
    assert clear_abort.json()["metadata"]["operator_abort_state"] == {
        "channel": "browser",
        "requested": False,
        "reason": "operator abort cleared",
        "requested_at": clear_abort.json()["metadata"]["operator_abort_state"][
            "requested_at"
        ],
    }

    session_detail = client.get(f"/runtime-center/sessions/{lease.id}")
    assert session_detail.status_code == 200
    cleared_payload = session_detail.json()
    assert cleared_payload["metadata"]["operator_abort_state"]["requested"] is False
    assert cleared_payload["metadata"]["operator_abort_state"]["channel"] == "browser"
    assert (
        cleared_payload["cooperative_adapter_availability"]["operator_abort_state"][
            "requested"
        ]
        is False
    )


def test_runtime_center_patch_actions_are_first_class_routes(tmp_path) -> None:
    app = build_runtime_center_app()
    app.state.learning_service = FakeLearningService(
        patch_status="proposed",
        risk_level="confirm",
    )
    _wire_governed_patch_runtime(app, tmp_path)

    client = TestClient(app)

    overview = client.get("/runtime-center/overview")
    assert overview.status_code == 200
    cards = {card["key"]: card for card in overview.json()["cards"]}
    assert (
        cards["patches"]["entries"][0]["actions"]["approve"]
        == "/api/runtime-center/learning/patches/patch-1/approve"
    )

    blocked_apply = client.post(
        "/runtime-center/learning/patches/patch-1/apply",
        json={"actor": "reviewer"},
    )
    assert blocked_apply.status_code == 400

    approved = client.post(
        "/runtime-center/learning/patches/patch-1/approve",
        json={"actor": "reviewer"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    applied = client.post(
        "/runtime-center/learning/patches/patch-1/apply",
        json={"actor": "reviewer"},
    )
    assert applied.status_code == 200
    applied_payload = applied.json()
    assert applied_payload["applied"] is False
    assert applied_payload["result"]["phase"] == "waiting-confirm"
    apply_decision_id = applied_payload["result"]["decision_request_id"]
    assert apply_decision_id

    approve_apply = client.post(
        f"/runtime-center/decisions/{apply_decision_id}/approve",
        json={"resolution": "Apply the approved patch.", "execute": True},
    )
    assert approve_apply.status_code == 200
    assert approve_apply.json()["phase"] == "completed"
    assert approve_apply.json()["decision_request_id"] == apply_decision_id

    rolled_back = client.post(
        "/runtime-center/learning/patches/patch-1/rollback",
        json={"actor": "reviewer"},
    )
    assert rolled_back.status_code == 200
    rolled_back_payload = rolled_back.json()
    assert rolled_back_payload["rolled_back"] is False
    assert rolled_back_payload["result"]["phase"] == "waiting-confirm"
    rollback_decision_id = rolled_back_payload["result"]["decision_request_id"]
    assert rollback_decision_id

    approve_rollback = client.post(
        f"/runtime-center/decisions/{rollback_decision_id}/approve",
        json={"resolution": "Rollback the patch.", "execute": True},
    )
    assert approve_rollback.status_code == 200
    assert approve_rollback.json()["phase"] == "completed"
    assert approve_rollback.json()["decision_request_id"] == rollback_decision_id


def test_routines_api_detail_diagnosis_and_runs() -> None:
    app = build_routines_app()
    app.state.routine_service = FakeRoutineService()

    client = TestClient(app)

    list_response = client.get("/routines")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "routine-1"

    detail_response = client.get("/routines/routine-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["routine"]["routine_key"] == "jd-login-capture"
    assert detail_response.json()["routes"]["diagnosis"] == "/api/routines/routine-1/diagnosis"

    diagnosis_response = client.get("/routines/routine-1/diagnosis")
    assert diagnosis_response.status_code == 200
    assert diagnosis_response.json()["drift_status"] == "stable"

    runs_response = client.get("/routines/runs")
    assert runs_response.status_code == 200
    assert runs_response.json()[0]["id"] == "routine-run-1"

    run_response = client.get("/routines/runs/routine-run-1")
    assert run_response.status_code == 200
    assert run_response.json()["run"]["id"] == "routine-run-1"


def test_routines_api_create_from_evidence_and_replay() -> None:
    app = build_routines_app()
    service = FakeRoutineService()
    app.state.routine_service = service

    client = TestClient(app)

    create_response = client.post(
        "/routines/from-evidence",
        json={
            "evidence_ids": ["evidence-1"],
            "routine_key": "jd-login-capture",
            "name": "京东登录例行",
            "owner_agent_id": "ops-agent",
            "owner_scope": "jd-ops",
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["source_evidence_ids"] == ["evidence-1"]

    replay_response = client.post(
        "/routines/routine-1/replay",
        json={
            "source_type": "manual",
            "owner_agent_id": "ops-agent",
            "owner_scope": "jd-ops",
        },
    )
    assert replay_response.status_code == 404
    assert len(service.replay_requests) == 0
