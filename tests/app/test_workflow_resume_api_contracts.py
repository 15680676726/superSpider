# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.workflow_templates import run_router
from copaw.workflows import WorkflowTemplateService


class _FailingWorkflowTemplateService(WorkflowTemplateService):
    async def resume_run(self, run_id: str, *, actor: str = "copaw-operator", execute=None):
        raise ValueError("Workflow run has active launch or governance blockers.")


def test_workflow_resume_route_maps_launch_blockers_to_400() -> None:
    app = FastAPI()
    app.include_router(run_router)
    app.state.workflow_template_service = object.__new__(_FailingWorkflowTemplateService)
    client = TestClient(app)

    response = client.post(
        "/workflow-runs/run-1/resume",
        json={"actor": "tester", "execute": False},
    )

    assert response.status_code == 400
    assert "launch or governance blockers" in response.json()["detail"]
