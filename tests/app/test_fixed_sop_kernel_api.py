# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.fixed_sops import router as fixed_sops_router
from copaw.evidence import EvidenceLedger
from copaw.sop_kernel import FixedSopService
from copaw.state import SQLiteStateStore, WorkflowRunRecord
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteWorkflowRunRepository,
)


def _build_app(tmp_path) -> FastAPI:
    app = FastAPI()
    app.include_router(fixed_sops_router)

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
    app.state.fixed_sop_service = FixedSopService(
        template_repository=template_repository,
        binding_repository=binding_repository,
        workflow_run_repository=workflow_run_repository,
        agent_report_repository=agent_report_repository,
        evidence_ledger=evidence_ledger,
    )
    return app


def test_list_fixed_sop_templates(tmp_path) -> None:
    client = TestClient(_build_app(tmp_path))

    response = client.get("/fixed-sops/templates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["items"][0]["template"]["template_id"]


def test_old_sop_adapters_route_is_gone(tmp_path) -> None:
    client = TestClient(_build_app(tmp_path))

    response = client.get("/sop-adapters/templates")

    assert response.status_code in {404, 410}


def test_legacy_sop_adapters_router_module_is_removed() -> None:
    assert importlib.util.find_spec("copaw.app.routers.sop_adapters") is None
