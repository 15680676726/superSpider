# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from copaw.evidence.models import EvidenceRecord
from copaw.state import (
    BacklogItemRecord,
    StrategyMemoryRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from tests.app.test_main_brain_optimization_loop_e2e import (
    _configure_remote_skill_install,
    _seed_legacy_outreach_failure,
)
from tests.app.test_predictions_api import (
    _build_predictions_app,
    _create_prediction_case,
    _execute_prediction_recommendation_direct,
)


def test_review_results_write_back_into_next_main_brain_planning_turn(
    tmp_path,
    monkeypatch,
) -> None:
    app = _build_predictions_app(
        tmp_path,
        enable_remote_curated_search=True,
    )
    client = TestClient(app)
    _seed_legacy_outreach_failure(app)
    _configure_remote_skill_install(app, monkeypatch)

    created = _create_prediction_case(client)
    first_case_id = created["case"]["case_id"]

    handoff = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["action_kind"] == "manual:coordinate-main-brain"
    )
    handoff_response = client.post(
        f"/predictions/{first_case_id}/recommendations/"
        f"{handoff['recommendation']['recommendation_id']}/coordinate",
        json={"actor": "copaw-operator"},
    )
    assert handoff_response.status_code == 200

    trial_recommendation = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind")
        == "underperforming_capability"
    )
    _execute_prediction_recommendation_direct(
        app,
        case_id=first_case_id,
        recommendation_id=trial_recommendation["recommendation"]["recommendation_id"],
    )

    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-nextgen-outreach-planning",
            title="NextGen outreach completed",
            summary="Guarded desktop outreach completed without operator takeover.",
            task_type="execution",
            status="completed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-nextgen-outreach-planning",
            runtime_status="terminated",
            current_phase="completed",
            risk_level="guarded",
            last_result_summary="NextGen outreach completed cleanly.",
            last_error_summary=None,
            last_owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-nextgen-outreach-planning",
            actor_ref="industry-solution-lead-demo",
            capability_ref="skill:nextgen_outreach",
            risk_level="guarded",
            action_summary="nextgen outreach run",
            result_summary="completed without operator intervention",
        ),
    )

    second_case = client.post(
        "/predictions",
        json={
            "title": "Remote rollout review",
            "question": "Should we retire the legacy outreach capability now?",
            "summary": "Review the completed remote skill trial.",
            "owner_scope": "industry-demo-scope",
            "industry_instance_id": "industry-demo",
        },
    )
    assert second_case.status_code == 200
    second_case_payload = second_case.json()
    second_case_id = second_case_payload["case"]["case_id"]
    retirement = next(
        item
        for item in second_case_payload["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind") == "capability_retirement"
    )
    _execute_prediction_recommendation_direct(
        app,
        case_id=second_case_id,
        recommendation_id=retirement["recommendation"]["recommendation_id"],
    )
    app.state.donor_trust_service.refresh_trust_records()

    strategy_memory_service = app.state.strategy_memory_service
    industry_strategy = strategy_memory_service.get_active_strategy(
        scope_type="industry",
        scope_id="industry-demo",
        owner_agent_id="copaw-agent-runner",
    )
    assert industry_strategy is not None
    strategy_memory_service.upsert_strategy(
        StrategyMemoryRecord.model_validate(
            {
                **industry_strategy.model_dump(mode="python"),
                "planning_policy": ["single-assignment-cycle"],
            },
        ),
    )

    industry_service = app.state.industry_service
    industry_service.set_prediction_service(app.state.prediction_service)
    record = industry_service.get_instance_record("industry-demo")
    assert record is not None

    review_item = BacklogItemRecord(
        id="backlog-capability-governance",
        industry_instance_id="industry-demo",
        title="Review capability governance retirement pressure and donor trust",
        summary="Review retirement pressure, donor trust, and future discovery pressure before new expansion.",
        status="open",
        priority=1,
        source_kind="operator",
        source_ref="operator:capability-governance-review",
        created_at=record.updated_at,
        updated_at=record.updated_at,
    )
    expansion_item = BacklogItemRecord(
        id="backlog-expansion-push",
        industry_instance_id="industry-demo",
        title="Launch a brand new outbound market expansion push",
        summary="Expand outreach volume into a new market this cycle.",
        status="open",
        priority=1,
        source_kind="operator",
        source_ref="operator:expansion-push",
        created_at=record.updated_at + timedelta(seconds=1),
        updated_at=record.updated_at + timedelta(seconds=1),
    )

    case_id, _ = industry_service._create_cycle_prediction_opportunities(
        record=record,
        actor="system:test",
        force=True,
        current_cycle=None,
        open_backlog=[review_item, expansion_item],
        pending_reports=[],
        created_reports=[],
        processed_reports=[],
        strategy_constraints=industry_service._compile_strategy_constraints(record=record),
        activation_result=None,
        task_subgraph=None,
    )

    assert case_id is not None
    detail = app.state.prediction_service.get_case_detail(case_id)
    planning = detail.case["planning"]
    writeback = planning["strategy_constraints"]["optimization_writeback"]

    assert planning["selected_backlog_item_ids"] == ["backlog-capability-governance"]
    assert "prefer-capability-governance-before-net-new" in planning["planning_policy"]
    assert writeback["summary"]["actionable_count"] >= 1
    assert writeback["donor_trust"]["retired_count"] >= 1
    assert writeback["portfolio"]["retire_pressure_count"] >= 1
    assert writeback["future_discovery_pressure"]["actionable_count"] >= 1
    assert (
        planning["replan"]["optimization_writeback"]["future_discovery_pressure"][
            "actionable_count"
        ]
        >= 1
    )
