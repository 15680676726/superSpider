# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from copaw.capabilities.remote_skill_contract import RemoteSkillCandidate
from copaw.evidence.models import EvidenceRecord
from copaw.state import (
    AgentProfileOverrideRecord,
    DecisionRequestRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from tests.app.test_predictions_api import (
    _build_predictions_app,
    _create_prediction_case,
    _execute_prediction_recommendation_direct,
)


def _seed_legacy_outreach_failure(app) -> None:
    capability_service = app.state.capability_service
    skill_service = capability_service._skill_service
    skill_service.create_skill(
        name="legacy_outreach",
        content=(
            "---\n"
            "name: legacy_outreach\n"
            "description: Legacy outreach skill\n"
            "---\n"
            "Legacy outreach skill"
        ),
        overwrite=True,
    )
    skill_service.enable_skill("legacy_outreach")
    app.state.agent_profile_override_repository.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-solution-lead-demo",
            name="Solution Lead",
            role_name="Solution Lead",
            role_summary="Own guarded outreach execution and follow-up.",
            industry_instance_id="industry-demo",
            industry_role_id="solution-lead",
            capabilities=["skill:legacy_outreach"],
            reason="seed legacy capability",
        ),
    )
    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-legacy-outreach-e2e",
            title="Legacy outreach run failed",
            summary="Desktop outreach failed and needed operator takeover.",
            task_type="execution",
            status="failed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-legacy-outreach-e2e",
            runtime_status="terminated",
            current_phase="failed",
            risk_level="guarded",
            last_result_summary="Legacy outreach stalled.",
            last_error_summary="Operator had to intervene.",
            last_owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.decision_request_repository.upsert_decision_request(
        DecisionRequestRecord(
            id="decision-legacy-outreach-e2e",
            task_id="task-legacy-outreach-e2e",
            decision_type="operator-handoff",
            risk_level="guarded",
            summary="Operator took over the legacy outreach task.",
            status="approved",
            requested_by="copaw-operator",
        ),
    )
    app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-legacy-outreach-e2e",
            actor_ref="industry-solution-lead-demo",
            capability_ref="skill:legacy_outreach",
            risk_level="guarded",
            action_summary="legacy outreach run",
            result_summary="failed and required operator takeover",
        ),
    )


def _configure_remote_skill_install(app, monkeypatch) -> None:
    capability_service = app.state.capability_service
    skill_service = capability_service._skill_service

    def _fake_search(_query: str, **_kwargs):
        return [
            RemoteSkillCandidate(
                candidate_key="hub:nextgen-outreach",
                source_kind="hub",
                source_label="SkillHub 商店",
                title="NextGen Outreach",
                description="A remote outreach skill optimized for guarded desktop follow-up.",
                bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/nextgen-outreach.zip",
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/nextgen-outreach.zip",
                slug="nextgen-outreach",
                version="1.0.0",
                install_name="nextgen_outreach",
                capability_ids=["skill:nextgen_outreach"],
                capability_tags=["skill", "remote"],
                review_required=False,
                search_query=_query,
            ),
        ]

    monkeypatch.setattr(
        "copaw.predictions.service.search_allowlisted_remote_skill_candidates",
        _fake_search,
    )

    def _fake_install_skill_from_hub(
        *,
        bundle_url: str,
        version: str = "",
        enable: bool = True,
        overwrite: bool = False,
    ):
        _ = version, overwrite
        skill_service.create_skill(
            name="nextgen_outreach",
            content=(
                "---\n"
                "name: nextgen_outreach\n"
                "description: NextGen outreach skill\n"
                "---\n"
                f"Installed from {bundle_url}"
            ),
            overwrite=True,
        )
        if enable:
            skill_service.enable_skill("nextgen_outreach")
        return SimpleNamespace(
            name="nextgen_outreach",
            enabled=enable,
            source_url=bundle_url,
        )

    capability_service._system_handler._skills._skill_service.install_skill_from_hub = (
        _fake_install_skill_from_hub
    )


def test_main_brain_governed_optimization_loop_e2e(tmp_path, monkeypatch) -> None:
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
    handoff_payload = handoff_response.json()
    assert handoff_payload["backlog_item_id"]
    assert handoff_payload["chat_thread_id"] == "industry-chat:industry-demo:execution-core"

    trial_recommendation = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind")
        == "underperforming_capability"
    )
    candidate_id = trial_recommendation["recommendation"]["metadata"]["candidate_id"]
    _execute_prediction_recommendation_direct(
        app,
        case_id=first_case_id,
        recommendation_id=trial_recommendation["recommendation"]["recommendation_id"],
    )

    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-nextgen-outreach-e2e",
            title="NextGen outreach completed",
            summary="Guarded desktop outreach completed without operator takeover.",
            task_type="execution",
            status="completed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-nextgen-outreach-e2e",
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
            task_id="task-nextgen-outreach-e2e",
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
    assert trial_projection["trial_scope"]["scope_ref"] == "env-browser-primary"
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
    assert retirement_projection["planning_impact"]["retirement_pressure"] is True
