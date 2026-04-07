# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi.testclient import TestClient

from copaw.config import load_config
from tests.app.test_predictions_api import (
    _build_predictions_app,
    _create_prediction_case,
    _execute_prediction_recommendation_direct,
)


def test_missing_mcp_recommendation_executes_into_optimization_closure(tmp_path) -> None:
    app = _build_predictions_app(tmp_path)
    client = TestClient(app)

    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]
    recommendation = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["action_kind"] == "system:update_mcp_client"
    )
    metadata = recommendation["recommendation"]["metadata"]
    recommendation_id = recommendation["recommendation"]["recommendation_id"]
    candidate_id = metadata["candidate_id"]

    assert metadata["gap_kind"] == "missing_capability"
    assert metadata["optimization_stage"] == "trial"
    assert metadata["trial_scope"] == "single-seat"

    execution = _execute_prediction_recommendation_direct(
        app,
        case_id=case_id,
        recommendation_id=recommendation_id,
    )

    assert execution["execution"]["phase"] == "completed"
    assert load_config(app.state.config_path).mcp.clients["desktop_windows"].enabled is True

    detail = client.get(f"/predictions/{case_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    projection = next(
        item
        for item in detail_payload["optimization_cases"]
        if item["gap_kind"] == "missing_capability"
    )
    assert projection["discovery_case_id"] == case_id
    assert projection["challenger"]["candidate_id"] == candidate_id
    assert projection["trial_scope"]["scope_kind"] == "seat"
    assert projection["trial_scope"]["scope_ref"] == "env-browser-primary"
    assert projection["evaluator_verdict"]["aggregate_verdict"] == "passed"
    assert projection["lifecycle_decision"]["decision_kind"] == "continue_trial"

    overview = client.get("/runtime-center/governance/capability-optimizations")
    assert overview.status_code == 200
    overview_payload = overview.json()
    assert overview_payload["summary"]["missing_capability_count"] >= 1
    history_projection = next(
        item["projection"]
        for item in overview_payload["history"]
        if item["projection"]["discovery_case_id"] == case_id
        and item["projection"]["gap_kind"] == "missing_capability"
    )
    assert history_projection["challenger"]["candidate_id"] == candidate_id

    trials = app.state.skill_trial_service.list_trials(candidate_id=candidate_id, limit=5)
    assert len(trials) == 1
    assert trials[0].verdict == "passed"

    decisions = app.state.skill_lifecycle_decision_service.list_decisions(
        candidate_id=candidate_id,
        limit=5,
    )
    assert len(decisions) == 1
    assert decisions[0].decision_kind == "continue_trial"
