# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

import pytest

from copaw.evidence import EvidenceLedger
from copaw.sop_kernel import (
    FixedSopBindingCreateRequest,
    FixedSopRunRequest,
    FixedSopService,
)
from copaw.state import SQLiteStateStore, WorkflowRunRecord
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteWorkflowRunRepository,
)


class _FakeEnvironmentService:
    def __init__(self, detail: dict[str, object]) -> None:
        self._detail = detail

    def get_session_detail(
        self,
        session_mount_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        if session_mount_id != "session-desktop-1":
            return None
        return dict(self._detail)

    def get_environment_detail(
        self,
        env_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        if env_id != "env-desktop-1":
            return None
        return dict(self._detail)


def _host_detail(
    *,
    recommended_scheduler_action: str,
    requires_human_return: bool = False,
    legal_recovery_path: str = "resume",
    legal_recovery_reason: str | None = None,
    host_blocker_family: str | None = None,
    host_blocker_response: str | None = None,
) -> dict[str, object]:
    summary = {
        "host_companion_status": (
            "restorable" if recommended_scheduler_action == "continue" else "attached"
        ),
        "seat_owner_ref": "ops-agent",
        "active_app_family_keys": ["office_document"],
        "blocked_surface_refs": [],
        "blocked_surface_count": 0,
        "legal_recovery_mode": (
            "resume-environment" if legal_recovery_path == "resume" else legal_recovery_path
        ),
        "recommended_scheduler_action": recommended_scheduler_action,
        "contention_severity": "clear" if recommended_scheduler_action == "continue" else "blocked",
        "contention_reason": legal_recovery_reason
        or "host coordination is clear",
        "requires_human_return": requires_human_return,
    }
    return {
        "environment_id": "env-desktop-1",
        "session_mount_id": "session-desktop-1",
        "host_companion_session": {
            "session_mount_id": "session-desktop-1",
            "environment_id": "env-desktop-1",
            "continuity_status": (
                "restorable" if recommended_scheduler_action == "continue" else "attached"
            ),
            "continuity_source": "live-handle",
            "locality": {
                "same_host": True,
                "same_process": False,
                "startup_recovery_required": requires_human_return,
            },
        },
        "host_twin": {
            "projection_kind": "host_twin_projection",
            "is_projection": True,
            "is_truth_store": False,
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
            "continuity": {
                "status": "attached",
                "valid": True,
                "continuity_source": "live-handle",
                "requires_human_return": requires_human_return,
            },
            "legal_recovery": {
                "path": legal_recovery_path,
                "reason": legal_recovery_reason,
            },
            "latest_blocking_event": {
                "event_family": host_blocker_family,
                "recommended_runtime_response": host_blocker_response,
            },
            "execution_mutation_ready": {
                "desktop_app": recommended_scheduler_action == "continue",
                "browser": False,
                "file_docs": False,
            },
            "app_family_twins": {
                "office_document": {
                    "active": True,
                    "family_kind": "office_document",
                    "surface_ref": "window:excel:main",
                    "contract_status": (
                        "verified-writer" if recommended_scheduler_action == "continue" else "blocked"
                    ),
                    "family_scope_ref": "app:excel",
                    "writer_lock_scope": "workbook:monthly-report",
                },
            },
            "coordination": {
                "seat_owner_ref": "ops-agent",
                "workspace_owner_ref": "ops-agent",
                "writer_owner_ref": (
                    "ops-agent" if recommended_scheduler_action == "continue" else None
                ),
                "candidate_seat_refs": ["env-desktop-1"],
                "selected_seat_ref": "env-desktop-1",
                "seat_selection_policy": "sticky-active-seat",
                "contention_forecast": {
                    "severity": (
                        "clear" if recommended_scheduler_action == "continue" else "blocked"
                    ),
                    "reason": (
                        "desktop writer path is clear"
                        if recommended_scheduler_action == "continue"
                        else "human handoff is still active"
                    ),
                },
                "recommended_scheduler_action": recommended_scheduler_action,
                "expected_release_at": None,
            },
            "scheduler_inputs": {
                "active_blocker_family": host_blocker_family,
                "requires_human_return": requires_human_return,
                "recommended_scheduler_action": recommended_scheduler_action,
            },
            "host_companion_session": {
                "session_mount_id": "session-desktop-1",
                "environment_id": "env-desktop-1",
                "continuity_status": (
                    "restorable" if recommended_scheduler_action == "continue" else "attached"
                ),
                "continuity_source": "live-handle",
                "locality": {
                    "same_host": True,
                    "same_process": False,
                    "startup_recovery_required": requires_human_return,
                },
            },
            "host_twin_summary": summary,
        },
    }


def _build_service(tmp_path, *, environment_service=None) -> FixedSopService:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    template_repository = SqliteFixedSopTemplateRepository(state_store)
    binding_repository = SqliteFixedSopBindingRepository(state_store)
    workflow_run_repository = SqliteWorkflowRunRepository(state_store)
    agent_report_repository = SqliteAgentReportRepository(state_store)
    workflow_run_repository.upsert_run(
        WorkflowRunRecord(
            run_id="workflow-run-1",
            template_id="workflow-template-a",
            title="Workflow Run A",
            status="draft",
        ),
    )
    return FixedSopService(
        template_repository=template_repository,
        binding_repository=binding_repository,
        workflow_run_repository=workflow_run_repository,
        agent_report_repository=agent_report_repository,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
    )


def test_fixed_sop_service_rejects_unknown_node_kind(tmp_path) -> None:
    service = _build_service(tmp_path)

    with pytest.raises(ValueError, match="unknown fixed SOP node kind"):
        service.validate_node_graph(
            [
                {
                    "node_id": "node-1",
                    "kind": "unsupported-node",
                }
            ]
        )


def test_fixed_sop_service_allows_only_minimal_node_set(tmp_path) -> None:
    service = _build_service(tmp_path)

    templates = service.list_templates()

    assert templates
    allowed_kinds = {
        "trigger",
        "guard",
        "http_request",
        "capability_call",
        "routine_call",
        "wait_callback",
        "writeback",
    }
    observed_kinds = {
        node["kind"]
        for template in templates
        for node in template.node_graph
    }
    assert observed_kinds
    assert observed_kinds <= allowed_kinds


def test_fixed_sop_service_blocks_mutating_run_when_host_preflight_requires_handoff(
    tmp_path,
) -> None:
    service = _build_service(
        tmp_path,
        environment_service=_FakeEnvironmentService(
            _host_detail(recommended_scheduler_action="handoff"),
        ),
    )
    binding = service.create_binding(
        FixedSopBindingCreateRequest(
            template_id="fixed-sop-http-routine-bridge",
            binding_name="Host Aware SOP",
            status="active",
            metadata={
                "environment_id": "env-desktop-1",
                "session_mount_id": "session-desktop-1",
                "host_requirement": {
                    "surface_kind": "desktop",
                    "app_family": "office_document",
                    "mutating": True,
                },
            },
        )
    )

    doctor = service.run_doctor(binding.binding.binding_id)

    assert doctor.status == "blocked"
    assert doctor.host_preflight["coordination"]["recommended_scheduler_action"] == "handoff"
    assert doctor.host_preflight["host_twin_summary"]["host_companion_status"] == "attached"

    with pytest.raises(ValueError, match="host preflight"):
        asyncio.run(
            service.run_binding(
                binding.binding.binding_id,
                FixedSopRunRequest(
                    environment_id="env-desktop-1",
                    session_mount_id="session-desktop-1",
                ),
            )
        )


def test_fixed_sop_service_records_host_snapshot_in_run_and_evidence(tmp_path) -> None:
    service = _build_service(
        tmp_path,
        environment_service=_FakeEnvironmentService(
            _host_detail(recommended_scheduler_action="continue"),
        ),
    )
    binding = service.create_binding(
        FixedSopBindingCreateRequest(
            template_id="fixed-sop-http-routine-bridge",
            binding_name="Host Aware SOP",
            status="active",
            metadata={
                "environment_id": "env-desktop-1",
                "session_mount_id": "session-desktop-1",
                "host_requirement": {
                    "surface_kind": "desktop",
                    "app_family": "office_document",
                    "mutating": True,
                },
            },
        )
    )

    response = asyncio.run(
        service.run_binding(
            binding.binding.binding_id,
            FixedSopRunRequest(
                environment_id="env-desktop-1",
                session_mount_id="session-desktop-1",
            ),
        )
    )

    detail = service.get_run(response.workflow_run_id or "")
    assert detail.host_preflight["coordination"]["recommended_scheduler_action"] == "continue"
    assert detail.host_preflight["host_twin_summary"]["host_companion_status"] == "restorable"
    assert detail.host_preflight["host_twin_summary"]["active_app_family_keys"]
    assert detail.host_preflight["host_twin_summary"]["seat_owner_ref"] == "ops-agent"
    assert detail.host_preflight["host_twin_summary"]["blocked_surface_count"] == 0
    assert detail.host_preflight["host_twin_summary"]["legal_recovery_mode"] == (
        "resume-environment"
    )
    assert detail.host_preflight["host_twin_summary"][
        "recommended_scheduler_action"
    ] == "continue"
    assert detail.environment_id == "env-desktop-1"
    assert detail.session_mount_id == "session-desktop-1"
    assert detail.host_requirement["app_family"] == "office_document"

    evidence = service._evidence_ledger.list_by_task(response.workflow_run_id or "")
    assert len(evidence) == 1
    assert evidence[0].environment_ref == "env-desktop-1"
    assert evidence[0].metadata["session_mount_id"] == "session-desktop-1"
    assert evidence[0].metadata["host_requirement"]["app_family"] == "office_document"
    assert evidence[0].metadata["host_preflight"]["coordination"][
        "recommended_scheduler_action"
    ] == "continue"
    assert evidence[0].metadata["host_preflight"]["host_twin_summary"][
        "host_companion_status"
    ] == "restorable"
    assert evidence[0].metadata["host_preflight"]["host_twin_summary"][
        "active_app_family_keys"
    ]
    assert evidence[0].metadata["host_preflight"]["host_twin_summary"][
        "seat_owner_ref"
    ] == "ops-agent"
    assert evidence[0].metadata["host_preflight"]["host_twin_summary"][
        "blocked_surface_count"
    ] == 0
    assert evidence[0].metadata["host_preflight"]["host_twin_summary"][
        "legal_recovery_mode"
    ] == "resume-environment"
    assert evidence[0].metadata["host_preflight"]["host_twin_summary"][
        "recommended_scheduler_action"
    ] == "continue"


def test_fixed_sop_service_blocks_mutating_run_when_host_recovery_requires_human_return(
    tmp_path,
) -> None:
    service = _build_service(
        tmp_path,
        environment_service=_FakeEnvironmentService(
            _host_detail(
                recommended_scheduler_action="continue",
                requires_human_return=True,
                legal_recovery_path="handoff",
                legal_recovery_reason="Manual login must be completed before control can return.",
            ),
        ),
    )
    binding = service.create_binding(
        FixedSopBindingCreateRequest(
            template_id="fixed-sop-http-routine-bridge",
            binding_name="Recovered Host SOP",
            status="active",
            metadata={
                "environment_id": "env-desktop-1",
                "session_mount_id": "session-desktop-1",
                "host_requirement": {
                    "surface_kind": "desktop",
                    "app_family": "office_document",
                    "mutating": True,
                },
            },
        )
    )

    doctor = service.run_doctor(binding.binding.binding_id)

    assert doctor.status == "blocked"
    host_check = next(item for item in doctor.checks if item.key == "host-preflight")
    assert "manual login" in host_check.message.lower() or "control can return" in host_check.message.lower()
    assert doctor.host_preflight["host_twin_summary"]["host_companion_status"] == "attached"

    with pytest.raises(ValueError, match="host preflight"):
        asyncio.run(
            service.run_binding(
                binding.binding.binding_id,
                FixedSopRunRequest(
                    environment_id="env-desktop-1",
                    session_mount_id="session-desktop-1",
                ),
            )
        )


def test_fixed_sop_service_ignores_stale_handoff_metadata_when_canonical_summary_is_proceed(
    tmp_path,
) -> None:
    detail = _host_detail(
        recommended_scheduler_action="proceed",
        requires_human_return=True,
        legal_recovery_path="handoff",
        legal_recovery_reason="stale handoff metadata should not block canonical proceed",
        host_blocker_family="modal-uac-login",
        host_blocker_response="handoff",
    )
    detail["host_twin"]["host_twin_summary"] = {
        "active_app_family_keys": ["office_document"],
        "seat_owner_ref": "ops-agent",
        "blocked_surface_count": 0,
        "legal_recovery_mode": "resume-environment",
        "recommended_scheduler_action": "proceed",
    }
    service = _build_service(
        tmp_path,
        environment_service=_FakeEnvironmentService(detail),
    )
    binding = service.create_binding(
        FixedSopBindingCreateRequest(
            template_id="fixed-sop-http-routine-bridge",
            binding_name="Host Canonical Proceed SOP",
            status="active",
            metadata={
                "environment_id": "env-desktop-1",
                "session_mount_id": "session-desktop-1",
                "host_requirement": {
                    "surface_kind": "desktop",
                    "app_family": "office_document",
                    "mutating": True,
                },
            },
        )
    )

    doctor = service.run_doctor(binding.binding.binding_id)

    assert doctor.status == "ready"
    host_check = next(item for item in doctor.checks if item.key == "host-preflight")
    assert host_check.status == "pass"
    assert doctor.host_preflight["host_twin_summary"]["recommended_scheduler_action"] == "proceed"
    assert doctor.host_preflight["host_twin_summary"]["legal_recovery_mode"] == (
        "resume-environment"
    )

    response = asyncio.run(
        service.run_binding(
            binding.binding.binding_id,
            FixedSopRunRequest(
                environment_id="env-desktop-1",
                session_mount_id="session-desktop-1",
            ),
        )
    )
    assert response.status == "success"
