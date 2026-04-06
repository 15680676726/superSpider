# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.capabilities.remote_skill_contract import RemoteSkillCandidate
from copaw.evidence.models import EvidenceRecord
from copaw.state import (
    AgentProfileOverrideRecord,
    DecisionRequestRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from copaw.state.repositories import (
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)
from tests.app.test_predictions_api import (
    _build_predictions_app,
    _create_prediction_case,
    _execute_prediction_recommendation_direct,
)


def _attach_runtime_center_state_query(app) -> None:
    store = app.state.task_repository._store
    app.state.state_query_service = RuntimeCenterStateQueryService(
        task_repository=app.state.task_repository,
        task_runtime_repository=app.state.task_runtime_repository,
        runtime_frame_repository=SqliteRuntimeFrameRepository(store),
        schedule_repository=SqliteScheduleRepository(store),
        goal_repository=SqliteGoalRepository(store),
        work_context_repository=SqliteWorkContextRepository(store),
        decision_request_repository=app.state.decision_request_repository,
        capability_candidate_service=app.state.capability_candidate_service,
        skill_trial_service=app.state.skill_trial_service,
        skill_lifecycle_decision_service=app.state.skill_lifecycle_decision_service,
        evidence_ledger=app.state.evidence_ledger,
        agent_profile_service=app.state.agent_profile_service,
    )


def _seed_underperforming_skill_trial_setup(app) -> None:
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
            id="task-legacy-outreach-1",
            title="Legacy outreach run failed",
            summary="Desktop outreach failed and needed operator takeover.",
            task_type="execution",
            status="failed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-legacy-outreach-1",
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
            id="decision-legacy-outreach-1",
            task_id="task-legacy-outreach-1",
            decision_type="operator-handoff",
            risk_level="guarded",
            summary="Operator took over the legacy outreach task.",
            status="approved",
            requested_by="copaw-operator",
        ),
    )
    app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-legacy-outreach-1",
            actor_ref="industry-solution-lead-demo",
            capability_ref="skill:legacy_outreach",
            risk_level="guarded",
            action_summary="legacy outreach run",
            result_summary="failed and required operator takeover",
        ),
    )


def test_prediction_remote_skill_trial_syncs_candidate_and_runtime_center_read_models(
    tmp_path,
    monkeypatch,
) -> None:
    app = _build_predictions_app(
        tmp_path,
        enable_remote_curated_search=True,
    )
    _attach_runtime_center_state_query(app)
    _seed_underperforming_skill_trial_setup(app)

    client = TestClient(app)
    capability_service = app.state.capability_service
    skill_service = capability_service._skill_service

    def _fake_search(_query: str, **_kwargs):
        return [
            RemoteSkillCandidate(
                candidate_key="hub:nextgen-outreach",
                source_kind="hub",
                source_label="SkillHub",
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

    created = _create_prediction_case(client)
    recommendation = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind")
        == "underperforming_capability"
    )
    candidate_id = recommendation["recommendation"]["metadata"]["candidate_id"]

    execution_payload = _execute_prediction_recommendation_direct(
        app,
        case_id=created["case"]["case_id"],
        recommendation_id=recommendation["recommendation"]["recommendation_id"],
    )

    assert execution_payload["execution"]["phase"] == "completed"

    candidate = app.state.capability_candidate_service.get_candidate(candidate_id)
    assert candidate is not None
    assert candidate.status == "trial"
    assert candidate.lifecycle_stage == "trial"

    trial_records = app.state.skill_trial_service.list_trials(candidate_id=candidate_id)
    assert len(trial_records) == 1
    assert trial_records[0].scope_ref == "env-browser-primary"
    assert trial_records[0].verdict == "passed"

    decision_records = app.state.skill_lifecycle_decision_service.list_decisions(
        candidate_id=candidate_id,
    )
    assert len(decision_records) == 1
    assert decision_records[0].decision_kind == "continue_trial"
    assert decision_records[0].to_stage == "trial"

    runtime_candidates = client.get(
        "/runtime-center/capabilities/candidates",
        params={"limit": 20},
    )
    assert runtime_candidates.status_code == 200
    runtime_candidate = next(
        item
        for item in runtime_candidates.json()
        if item["candidate_id"] == candidate_id
    )
    assert runtime_candidate["status"] == "trial"
    assert runtime_candidate["lifecycle_stage"] == "trial"
    assert runtime_candidate["lifecycle_history"]["trial_count"] == 1
    assert runtime_candidate["lifecycle_history"]["decision_count"] == 1
    assert runtime_candidate["lifecycle_history"]["latest_decision_kind"] == (
        "continue_trial"
    )

    runtime_trials = client.get(
        "/runtime-center/capabilities/trials",
        params={"candidate_id": candidate_id, "limit": 20},
    )
    assert runtime_trials.status_code == 200
    assert len(runtime_trials.json()) == 1
    assert runtime_trials.json()[0]["scope_ref"] == "env-browser-primary"

    runtime_decisions = client.get(
        "/runtime-center/capabilities/lifecycle-decisions",
        params={"candidate_id": candidate_id, "limit": 20},
    )
    assert runtime_decisions.status_code == 200
    assert len(runtime_decisions.json()) == 1
    assert runtime_decisions.json()[0]["decision_kind"] == "continue_trial"
