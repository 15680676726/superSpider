# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router

from tests.state.test_reporting_service import _build_service


def _build_client(tmp_path) -> TestClient:
    app = FastAPI()
    app.state.reporting_service = _build_service(tmp_path)
    app.include_router(runtime_center_router)
    return TestClient(app)


def test_runtime_center_reports_api_returns_formal_reports(tmp_path) -> None:
    client = _build_client(tmp_path)

    response = client.get("/runtime-center/reports")
    assert response.status_code == 200
    payload = response.json()
    assert [item["window"] for item in payload] == ["daily", "weekly", "monthly"]
    assert payload[1]["evidence_count"] == 2
    assert payload[1]["patch_count"] == 1
    assert payload[1]["completed_tasks"][0]["task_id"] == "task-1"
    assert payload[1]["next_steps"] == [
        "Confirm whether to rollback the signal change."
    ]
    assert payload[1]["metrics"][0]["key"] == "task_success_rate"


def test_runtime_center_reports_api_supports_agent_scope(tmp_path) -> None:
    client = _build_client(tmp_path)

    response = client.get(
        "/runtime-center/reports",
        params={
            "window": "weekly",
            "scope_type": "agent",
            "scope_id": "research-agent",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["scope_type"] == "agent"
    assert payload[0]["scope_id"] == "research-agent"
    assert payload[0]["task_ids"] == ["task-2"]
    assert payload[0]["blockers"]


def test_runtime_center_performance_api_returns_metrics_and_agents(tmp_path) -> None:
    client = _build_client(tmp_path)

    response = client.get("/runtime-center/performance", params={"window": "weekly"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["window"] == "weekly"
    assert len(payload["metrics"]) == 9
    metric_keys = {item["key"] for item in payload["metrics"]}
    assert "prediction_hit_rate" in metric_keys
    assert "recommendation_adoption_rate" in metric_keys
    assert "recommendation_execution_benefit" in metric_keys
    assert payload["agent_breakdown"][0]["agent_id"] in {
        "ops-agent",
        "research-agent",
    }
