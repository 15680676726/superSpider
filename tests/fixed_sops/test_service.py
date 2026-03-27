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


def _host_detail(*, recommended_scheduler_action: str) -> dict[str, object]:
    return {
        "environment_id": "env-desktop-1",
        "session_mount_id": "session-desktop-1",
        "host_twin": {
            "continuity": {
                "status": "attached",
                "valid": recommended_scheduler_action == "continue",
                "continuity_source": "live-handle",
                "requires_human_return": recommended_scheduler_action == "handoff",
            },
            "execution_mutation_ready": {
                "desktop_app": recommended_scheduler_action == "continue",
                "browser": False,
                "file_docs": False,
            },
            "coordination": {
                "seat_owner_ref": "ops-agent",
                "workspace_owner_ref": "ops-agent",
                "writer_owner_ref": (
                    "ops-agent" if recommended_scheduler_action == "continue" else None
                ),
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
            },
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
