from __future__ import annotations

from copaw.state import SQLiteStateStore
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.skill_lifecycle_decision_service import (
    SkillLifecycleDecisionService,
)
from copaw.state.skill_trial_service import SkillTrialService


def test_skill_trial_service_creates_and_summarizes_trials(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="solution-lead",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/nextgen-outreach.zip",
        candidate_source_version="1.0.0",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="nextgen_outreach",
        summary="Governed remote skill candidate for outreach.",
    )

    created = trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        summary="Primary seat trial completed without operator takeover.",
        task_ids=["task-1", "task-2"],
        evidence_refs=["ev-1"],
        success_count=2,
        failure_count=0,
        handoff_count=0,
        operator_intervention_count=0,
        latency_summary={"avg_seconds": 12.4},
        metadata={"target_agent_id": "industry-solution-lead-demo"},
    )

    listed = trial_service.list_trials(candidate_id=candidate.candidate_id)
    summary = trial_service.summarize_trials(candidate_id=candidate.candidate_id)

    assert created.candidate_id == candidate.candidate_id
    assert listed[0].trial_id == created.trial_id
    assert summary == {
        "candidate_id": candidate.candidate_id,
        "trial_count": 1,
        "success_count": 2,
        "failure_count": 0,
        "handoff_count": 0,
        "operator_intervention_count": 0,
        "verdicts": {"passed": 1},
        "scope_refs": ["seat-primary"],
    }


def test_skill_lifecycle_decision_service_records_candidate_decisions(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="solution-lead",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/nextgen-outreach.zip",
        candidate_source_version="1.0.0",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="nextgen_outreach",
        summary="Governed remote skill candidate for outreach.",
    )

    created = decision_service.create_decision(
        candidate_id=candidate.candidate_id,
        decision_kind="promote_to_role",
        from_stage="trial",
        to_stage="active",
        reason="Primary seat trial is stable enough for governed wider rollout.",
        evidence_refs=["ev-1", "ev-2"],
        replacement_target_ids=["skill:legacy_outreach"],
        protection_lifted=False,
        applied_by="prediction-service",
        metadata={"source_recommendation_id": "rec-1"},
    )

    listed = decision_service.list_decisions(candidate_id=candidate.candidate_id)

    assert created.candidate_id == candidate.candidate_id
    assert created.decision_kind == "promote_to_role"
    assert listed[0].decision_id == created.decision_id
    assert listed[0].replacement_target_ids == ["skill:legacy_outreach"]
