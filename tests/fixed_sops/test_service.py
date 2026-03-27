# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from copaw.evidence import EvidenceLedger
from copaw.sop_kernel import FixedSopService
from copaw.state import SQLiteStateStore, WorkflowRunRecord
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteWorkflowRunRepository,
)


def _build_service(tmp_path) -> FixedSopService:
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
