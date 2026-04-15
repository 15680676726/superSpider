# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from copaw.capabilities.remote_skill_catalog import (
    clear_curated_skill_catalog_cache,
    search_curated_skill_catalog,
)
from copaw.evidence.models import EvidenceRecord
from copaw.state import (
    BacklogItemRecord,
    StrategyMemoryRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from tests.app.test_predictions_api import (
    _build_predictions_app,
    _create_prediction_case,
    _execute_prediction_recommendation_direct,
)
from tests.app.test_skill_runtime_smoke import _seed_underperforming_skill_trial_setup


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


LIVE_OPTIMIZATION_SMOKE_SKIP_REASON = (
    "Set COPAW_RUN_LIVE_OPTIMIZATION_SMOKE=1 to run live optimization smoke "
    "coverage (opt-in; not part of default regression coverage)."
)


def _skip_when_live_remote_skill_discovery_is_unavailable(query: str) -> None:
    clear_curated_skill_catalog_cache()
    response = search_curated_skill_catalog(query, limit=3)
    if response.items:
        return
    reason = (
        response.warnings[0]
        if response.warnings
        else f"No curated remote skill candidates were returned for query '{query}'."
    )
    pytest.skip(f"Live remote skill discovery is unavailable: {reason}")


def _patch_skill_dirs(monkeypatch, tmp_path) -> tuple[Path, Path]:
    customized_dir = tmp_path / "customized"
    active_dir = tmp_path / "active"
    customized_dir.mkdir()
    active_dir.mkdir()
    monkeypatch.setattr("copaw.skill_service.get_customized_skills_dir", lambda: customized_dir)
    monkeypatch.setattr("copaw.skill_service.get_active_skills_dir", lambda: active_dir)
    return customized_dir, active_dir


def _close_prediction_app(app) -> None:
    close_ledger = getattr(getattr(app.state, "evidence_ledger", None), "close", None)
    if callable(close_ledger):
        close_ledger()


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_LIVE_OPTIMIZATION_SMOKE"),
    reason=LIVE_OPTIMIZATION_SMOKE_SKIP_REASON,
)
def test_live_remote_skill_optimization_loop_closes_into_planning_writeback(
    tmp_path,
    monkeypatch,
) -> None:
    customized_dir, active_dir = _patch_skill_dirs(monkeypatch, tmp_path)
    app = _build_predictions_app(
        tmp_path,
        enable_remote_curated_search=True,
        use_real_skill_service=True,
    )
    try:
        with TestClient(app) as client:
            _seed_underperforming_skill_trial_setup(app)

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
                (
                    item
                    for item in created["recommendations"]
                    if item["recommendation"]["metadata"].get("gap_kind")
                    == "underperforming_capability"
                ),
                None,
            )
            if trial_recommendation is None:
                _skip_when_live_remote_skill_discovery_is_unavailable(
                    "legacy outreach",
                )
                pytest.fail(
                    "Prediction case did not materialize an underperforming_capability recommendation.",
                )
            candidate_id = trial_recommendation["recommendation"]["metadata"]["candidate_id"]
            execution_payload = _execute_prediction_recommendation_direct(
                app,
                case_id=first_case_id,
                recommendation_id=trial_recommendation["recommendation"]["recommendation_id"],
            )

            assert execution_payload["execution"]["phase"] == "completed"
            output = execution_payload["execution"]["output"]
            installed_name = output["name"]
            installed_capability_ids = output["installed_capability_ids"]
            assert installed_name
            assert installed_capability_ids
            assert (customized_dir / installed_name / "SKILL.md").exists()
            assert (active_dir / installed_name / "SKILL.md").exists()

            trial_records = app.state.skill_trial_service.list_trials(candidate_id=candidate_id)
            assert len(trial_records) == 1
            assert trial_records[0].verdict == "passed"

            decision_records = app.state.skill_lifecycle_decision_service.list_decisions(
                candidate_id=candidate_id,
            )
            assert len(decision_records) == 1
            assert decision_records[0].decision_kind == "continue_trial"

            app.state.task_repository.upsert_task(
                TaskRecord(
                    id="task-live-remote-outreach",
                    title="Live remote outreach completed",
                    summary="Live remote skill completed without operator takeover.",
                    task_type="execution",
                    status="completed",
                    owner_agent_id="industry-solution-lead-demo",
                ),
            )
            app.state.task_runtime_repository.upsert_runtime(
                TaskRuntimeRecord(
                    task_id="task-live-remote-outreach",
                    runtime_status="terminated",
                    current_phase="completed",
                    risk_level="guarded",
                    last_result_summary="Live remote skill completed cleanly.",
                    last_error_summary=None,
                    last_owner_agent_id="industry-solution-lead-demo",
                ),
            )
            app.state.evidence_ledger.append(
                EvidenceRecord(
                    task_id="task-live-remote-outreach",
                    actor_ref="industry-solution-lead-demo",
                    capability_ref=installed_capability_ids[0],
                    risk_level="guarded",
                    action_summary="live remote outreach run",
                    result_summary="completed without operator intervention",
                ),
            )

            second_case = client.post(
                "/predictions",
                json={
                    "title": "Live remote rollout review",
                    "question": "Should we retire the legacy outreach capability now?",
                    "summary": "Review the completed live remote skill trial.",
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
                if item["recommendation"]["metadata"].get("gap_kind")
                == "capability_retirement"
            )
            retirement_payload = _execute_prediction_recommendation_direct(
                app,
                case_id=second_case_id,
                recommendation_id=retirement["recommendation"]["recommendation_id"],
            )
            assert retirement_payload["execution"]["phase"] == "completed"
            app.state.donor_trust_service.refresh_trust_records()

            response = client.get("/runtime-center/governance/capability-optimizations")
            assert response.status_code == 200
            payload = response.json()
            projected_cases = payload["actionable"] + payload["history"]
            trial_projection = next(
                item["projection"]
                for item in projected_cases
                if item["projection"]["discovery_case_id"] == first_case_id
                and item["projection"]["challenger"]["candidate_id"] == candidate_id
                and item["projection"]["gap_kind"] == "underperforming_capability"
            )
            retirement_projection = next(
                item["projection"]
                for item in projected_cases
                if item["projection"]["discovery_case_id"] == second_case_id
                and item["projection"]["challenger"]["candidate_id"] == candidate_id
                and item["projection"]["gap_kind"] == "capability_retirement"
            )
            assert trial_projection["evaluator_verdict"]["aggregate_verdict"] == "passed"
            assert trial_projection["writeback_targets"] == [
                "planning_constraints",
                "donor_trust",
                "capability_portfolio_pressure",
                "future_discovery_pressure",
                "strategy_or_lane_reopen",
            ]
            assert retirement_projection["lifecycle_decision"]["decision_kind"] == "retire"
            assert retirement_projection["donor_trust_impact"]["retirement_count"] >= 1

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
                id="backlog-capability-governance-live",
                industry_instance_id="industry-demo",
                title="Review capability governance retirement pressure and donor trust",
                summary="Review retirement pressure, donor trust, and future discovery pressure before new expansion.",
                status="open",
                priority=1,
                source_kind="operator",
                source_ref="operator:capability-governance-review-live",
                created_at=record.updated_at,
                updated_at=record.updated_at,
            )
            expansion_item = BacklogItemRecord(
                id="backlog-expansion-push-live",
                industry_instance_id="industry-demo",
                title="Launch a brand new outbound market expansion push",
                summary="Expand outreach volume into a new market this cycle.",
                status="open",
                priority=1,
                source_kind="operator",
                source_ref="operator:expansion-push-live",
                created_at=record.updated_at + timedelta(seconds=1),
                updated_at=record.updated_at + timedelta(seconds=1),
            )
            case_id, _ = industry_service._create_cycle_prediction_opportunities(
                record=record,
                actor="system:test-live",
                force=True,
                current_cycle=None,
                open_backlog=[review_item, expansion_item],
                pending_reports=[],
                created_reports=[],
                processed_reports=[],
                strategy_constraints=industry_service._compile_strategy_constraints(
                    record=record,
                ),
                activation_result=None,
                task_subgraph=None,
            )

            assert case_id is not None
            detail = app.state.prediction_service.get_case_detail(case_id)
            planning = detail.case["planning"]
            writeback = planning["strategy_constraints"]["optimization_writeback"]

            assert planning["selected_backlog_item_ids"] == [
                "backlog-capability-governance-live",
            ]
            assert "prefer-capability-governance-before-net-new" in planning[
                "planning_policy"
            ]
            assert writeback["summary"]["actionable_count"] >= 1
            assert writeback["donor_trust"]["retired_count"] >= 1
            assert writeback["portfolio"]["retire_pressure_count"] >= 1
            assert writeback["future_discovery_pressure"]["actionable_count"] >= 1
    finally:
        _close_prediction_app(app)
