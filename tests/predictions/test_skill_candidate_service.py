# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from copaw.capabilities.models import CapabilityMount
from copaw.discovery.models import NormalizedDiscoveryHit
from copaw.learning.skill_gap_detector import SkillGapDetector
from copaw.predictions.service_context import _PredictionServiceContextMixin
from copaw.predictions.service_recommendations import _PredictionServiceRecommendationMixin
from copaw.predictions.service_shared import _FactPack
from copaw.state import SQLiteStateStore
from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state.capability_portfolio_service import CapabilityPortfolioService
from copaw.state.models_prediction import (
    PredictionCaseRecord,
    PredictionRecommendationRecord,
    PredictionSignalRecord,
)
from copaw.state.skill_lifecycle_decision_service import SkillLifecycleDecisionService
from copaw.state.skill_candidate_service import (
    CapabilityCandidateService,
)
from copaw.state.skill_trial_service import SkillTrialService


def _build_service(tmp_path: Path) -> CapabilityCandidateService:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    return CapabilityCandidateService(state_store=store)


def _build_portfolio_services(
    tmp_path: Path,
) -> tuple[
    CapabilityCandidateService,
    CapabilityDonorService,
    SkillTrialService,
    SkillLifecycleDecisionService,
    CapabilityPortfolioService,
]:
    store = SQLiteStateStore(tmp_path / "portfolio.sqlite3")
    donor_service = CapabilityDonorService(state_store=store)
    candidate_service = CapabilityCandidateService(
        state_store=store,
        donor_service=donor_service,
    )
    trial_service = SkillTrialService(state_store=store)
    decision_service = SkillLifecycleDecisionService(state_store=store)
    portfolio_service = CapabilityPortfolioService(
        donor_service=donor_service,
        candidate_service=candidate_service,
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=decision_service,
    )
    return (
        candidate_service,
        donor_service,
        trial_service,
        decision_service,
        portfolio_service,
    )


class _RecordingRecommendationRepository:
    def __init__(
        self,
        recommendations: list[PredictionRecommendationRecord] | None = None,
    ) -> None:
        self._recommendations = list(recommendations or [])

    def list_recommendations(self, **_kwargs):
        return list(self._recommendations)


class _RecordingLifecycleDecisionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list_decisions(
        self,
        *,
        candidate_id: str | None = None,
        limit: int | None = None,
    ):
        _ = (candidate_id, limit)
        return []

    def create_decision(self, **kwargs):
        self.calls.append(dict(kwargs))


class _TrialFollowupHarness(_PredictionServiceContextMixin):
    def __init__(self, recommendations: list[PredictionRecommendationRecord]) -> None:
        self._recommendation_repository = _RecordingRecommendationRepository(
            recommendations=recommendations,
        )
        self._skill_gap_detector = SkillGapDetector()


class _RevisionRecommendationHarness(_PredictionServiceRecommendationMixin):
    def __init__(self, finding: dict[str, object]) -> None:
        self._finding = dict(finding)
        self._skill_lifecycle_decision_service = _RecordingLifecycleDecisionService()
        self._capability_service = object()

    def _hottest_agent(self, facts: _FactPack):
        _ = facts
        return None

    def _case_confidence(self, signals, reviews):
        _ = (signals, reviews)
        return 0.58

    def _team_role_gap_findings(self, *, case: PredictionCaseRecord, facts: _FactPack):
        _ = (case, facts)
        return {}

    def _register_capability_candidate(
        self,
        *,
        case: PredictionCaseRecord,
        summary: str,
        metadata: dict[str, object],
        action_payload: dict[str, object],
    ):
        _ = (case, summary)
        return metadata, action_payload

    def _capability_telemetry(self, *, case: PredictionCaseRecord, facts: _FactPack):
        _ = (case, facts)
        return {}

    def _missing_donor_capability_findings(self, *, facts: _FactPack):
        _ = facts
        return []

    def _underperforming_donor_capability_findings(
        self,
        *,
        facts: _FactPack,
        telemetry: dict[tuple[str, str], dict[str, object]],
    ):
        _ = (facts, telemetry)
        return []

    def _trial_followup_findings(
        self,
        *,
        case: PredictionCaseRecord,
        facts: _FactPack,
        telemetry: dict[tuple[str, str], dict[str, object]],
    ):
        _ = (case, facts, telemetry)
        return [dict(self._finding)]

    def _json_safe(self, payload):
        return payload


class _PredictionAgentProfileService:
    def get_agent_detail(self, agent_id: str):
        if agent_id != "industry-solution-lead-demo":
            return {"runtime": {"metadata": {}}}
        return {
            "runtime": {
                "metadata": {
                    "selected_seat_ref": "env-browser-primary",
                },
            },
        }


class _MCPCapabilityService:
    def __init__(self, existing_client: dict[str, object] | None) -> None:
        self._existing_client = dict(existing_client or {}) if existing_client else None

    def get_mcp_client_info(self, client_key: str):
        if self._existing_client is None:
            return None
        if str(self._existing_client.get("key") or "") == client_key:
            return dict(self._existing_client)
        return None


class _MissingMCPRecommendationHarness(_PredictionServiceRecommendationMixin):
    def __init__(
        self,
        *,
        candidate_service: CapabilityCandidateService,
        existing_client: dict[str, object] | None,
    ) -> None:
        self._capability_candidate_service = candidate_service
        self._capability_service = _MCPCapabilityService(existing_client)
        self._agent_profile_service = _PredictionAgentProfileService()
        self._skill_lifecycle_decision_service = _RecordingLifecycleDecisionService()
        self._skill_evolution_service = None

    def _hottest_agent(self, facts: _FactPack):
        _ = facts
        return {"agent_id": "industry-solution-lead-demo"}

    def _case_confidence(self, signals, reviews):
        _ = (signals, reviews)
        return 0.58

    def _team_role_gap_findings(self, *, case: PredictionCaseRecord, facts: _FactPack):
        _ = (case, facts)
        return {}

    def _missing_donor_capability_findings(self, *, facts: _FactPack):
        _ = facts
        return []

    def _capability_telemetry(self, *, case: PredictionCaseRecord, facts: _FactPack):
        _ = (case, facts)
        return {}

    def _underperforming_donor_capability_findings(
        self,
        *,
        facts: _FactPack,
        telemetry: dict[tuple[str, str], dict[str, object]],
    ):
        _ = (facts, telemetry)
        return []

    def _trial_followup_findings(
        self,
        *,
        case: PredictionCaseRecord,
        facts: _FactPack,
        telemetry: dict[tuple[str, str], dict[str, object]],
    ):
        _ = (case, facts, telemetry)
        return []

    def _json_safe(self, payload):
        return payload


class _AgentLoadRecommendationHarness(_PredictionServiceRecommendationMixin):
    def __init__(self) -> None:
        self._capability_service = object()
        self._skill_lifecycle_decision_service = _RecordingLifecycleDecisionService()

    def _hottest_agent(self, facts: _FactPack):
        _ = facts
        return {
            "agent_id": "industry-ops-hot",
            "name": "Ops Hot Seat",
            "failed_task_count": 1,
            "active_task_count": 4,
        }

    def _case_confidence(self, signals, reviews):
        _ = (signals, reviews)
        return 0.58

    def _team_role_gap_findings(self, *, case: PredictionCaseRecord, facts: _FactPack):
        _ = (case, facts)
        return {}

    def _missing_donor_capability_findings(self, *, facts: _FactPack):
        _ = facts
        return []

    def _capability_telemetry(self, *, case: PredictionCaseRecord, facts: _FactPack):
        _ = (case, facts)
        return {}

    def _underperforming_donor_capability_findings(
        self,
        *,
        facts: _FactPack,
        telemetry: dict[tuple[str, str], dict[str, object]],
    ):
        _ = (facts, telemetry)
        return []

    def _trial_followup_findings(
        self,
        *,
        case: PredictionCaseRecord,
        facts: _FactPack,
        telemetry: dict[tuple[str, str], dict[str, object]],
    ):
        _ = (case, facts, telemetry)
        return []

    def _json_safe(self, payload):
        return payload


def test_capability_candidate_service_normalizes_external_and_local_sources(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    external = service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="1.2.3",
        ingestion_mode="auto-install",
        proposed_skill_name="research_pack",
        summary="Remote research pack candidate.",
    )
    local = service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="local_authored",
        candidate_source_ref=str(tmp_path / "skills" / "research_pack" / "SKILL.md"),
        candidate_source_version="draft-v1",
        ingestion_mode="local-authoring",
        proposed_skill_name="research_pack_local",
        summary="Local authoring candidate.",
    )

    assert external.candidate_id != local.candidate_id
    assert external.candidate_kind == "skill"
    assert external.candidate_source_kind == "external_remote"
    assert external.ingestion_mode == "auto-install"
    assert local.candidate_source_kind == "local_authored"
    assert local.ingestion_mode == "local-authoring"

    stored = service.list_candidates()
    assert [item.candidate_source_kind for item in stored] == [
        "local_authored",
        "external_remote",
    ]


def test_capability_candidate_service_baseline_import_reuses_existing_candidate(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    mount = CapabilityMount(
        id="skill:research",
        name="Research",
        summary="Research bundle",
        kind="skill-bundle",
        source_kind="skill",
        risk_level="guarded",
        enabled=True,
        package_ref="https://example.com/skills/research-pack.zip",
        package_kind="hub-bundle",
        package_version="1.2.3",
    )

    first = service.import_active_baseline_artifacts(
        mounts=[mount],
        target_role_id="researcher",
    )
    second = service.import_active_baseline_artifacts(
        mounts=[mount],
        target_role_id="researcher",
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].candidate_id == second[0].candidate_id
    assert first[0].status == "active"
    assert first[0].lifecycle_stage == "baseline"
    assert first[0].ingestion_mode == "baseline-import"
    assert len(service.list_candidates()) == 1


def test_capability_candidate_service_tracks_baseline_protection_and_lineage(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    mount = CapabilityMount(
        id="mcp:browser",
        name="Browser MCP",
        summary="Browser runtime",
        kind="remote-mcp",
        source_kind="mcp",
        risk_level="guarded",
        enabled=True,
        package_ref="registry://browser",
        package_kind="registry",
        package_version="2026.04.03",
        metadata={
            "required_by_role_blueprint": True,
            "protected_from_auto_replace": True,
        },
    )

    imported = service.import_active_baseline_artifacts(
        mounts=[mount],
        target_role_id="operator",
    )[0]

    assert imported.candidate_kind == "mcp-bundle"
    assert imported.protection_flags == [
        "protected_from_auto_replace",
        "required_by_role_blueprint",
    ]
    assert imported.lineage_root_id == imported.candidate_id
    assert imported.candidate_source_kind == "external_catalog"


def test_capability_candidate_service_materializes_donor_truth_and_portfolio_summary(
    tmp_path: Path,
) -> None:
    (
        candidate_service,
        donor_service,
        trial_service,
        decision_service,
        portfolio_service,
    ) = _build_portfolio_services(tmp_path)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="1.2.3",
        candidate_source_lineage="candidate:research-pack",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="research_pack",
        summary="Remote research pack candidate.",
    )
    baseline = candidate_service.normalize_candidate_source(
        candidate_kind="mcp-bundle",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://browser",
        candidate_source_version="2026.04.04",
        candidate_source_lineage="donor:browser-registry",
        ingestion_mode="baseline-import",
        proposed_skill_name="browser_registry",
        summary="Browser runtime baseline.",
        status="active",
        lifecycle_stage="baseline",
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-1",
        verdict="passed",
        success_count=2,
        summary="Remote donor passed scoped trial.",
    )
    decision_service.create_decision(
        candidate_id=baseline.candidate_id,
        decision_kind="retire",
        from_stage="active",
        to_stage="retired",
        reason="Registry donor is no longer aligned with the target seat.",
    )

    assert candidate.donor_id is not None
    assert candidate.package_id is not None
    assert candidate.source_profile_id is not None
    assert baseline.donor_id is not None
    assert baseline.donor_id != candidate.donor_id

    donors = donor_service.list_donors()
    source_profiles = donor_service.list_source_profiles()
    packages = donor_service.list_packages()
    trust_records = donor_service.list_trust_records()
    portfolio = portfolio_service.summarize_portfolio()

    assert len(donors) == 2
    assert len(source_profiles) == 2
    assert len(packages) == 2
    assert len(trust_records) == 2
    assert {item.trust_posture for item in source_profiles} == {
        "trusted",
        "watchlist",
    }
    donor_by_id = {item.donor_id: item for item in donors}
    package_by_id = {item.package_id: item for item in packages}
    source_profile_by_id = {
        item.source_profile_id: item
        for item in source_profiles
    }
    trust_by_donor_id = {item.donor_id: item for item in trust_records}

    assert donor_by_id[candidate.donor_id].source_kind == "external_remote"
    assert donor_by_id[baseline.donor_id].source_kind == "external_catalog"
    assert donor_by_id[candidate.donor_id].canonical_package_id is not None
    assert donor_by_id[baseline.donor_id].canonical_package_id is not None
    assert (
        donor_by_id[candidate.donor_id].canonical_package_id
        != donor_by_id[baseline.donor_id].canonical_package_id
    )
    assert donor_by_id[candidate.donor_id].candidate_source_lineage == "candidate:research-pack"
    assert donor_by_id[baseline.donor_id].candidate_source_lineage == "donor:browser-registry"
    assert source_profile_by_id[candidate.source_profile_id].source_lineage == "candidate:research-pack"
    assert source_profile_by_id[baseline.source_profile_id].source_lineage == "donor:browser-registry"
    assert (
        "https://example.com/skills/research-pack.zip"
        in donor_by_id[candidate.donor_id].source_aliases
    )
    assert "registry://browser" in donor_by_id[baseline.donor_id].source_aliases
    assert package_by_id[candidate.package_id].canonical_package_id == donor_by_id[candidate.donor_id].canonical_package_id
    assert package_by_id[baseline.package_id].canonical_package_id == donor_by_id[baseline.donor_id].canonical_package_id
    assert trust_by_donor_id[candidate.donor_id].last_candidate_id == candidate.candidate_id
    assert trust_by_donor_id[candidate.donor_id].last_package_id == candidate.package_id
    assert trust_by_donor_id[baseline.donor_id].last_candidate_id == baseline.candidate_id
    assert trust_by_donor_id[baseline.donor_id].last_package_id == baseline.package_id
    assert trust_by_donor_id[baseline.donor_id].last_canonical_package_id == package_by_id[baseline.package_id].canonical_package_id
    assert portfolio["donor_count"] == 2
    assert portfolio["active_donor_count"] == 1
    assert portfolio["candidate_donor_count"] == 1
    assert portfolio["trial_donor_count"] == 1
    assert portfolio["trusted_source_count"] == 1
    assert portfolio["watchlist_source_count"] == 1
    assert portfolio["retire_pressure_count"] == 1
    assert portfolio["degraded_donor_count"] == 0
    assert any(
        item["action"] == "review_retirement_pressure"
        for item in portfolio["planning_actions"]
    )


def test_capability_candidate_service_preserves_github_project_source_ref(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    imported = service.import_normalized_discovery_hits(
        normalized_hits=[
            NormalizedDiscoveryHit(
                candidate_kind="project",
                candidate_source_kind="external_remote",
                display_name="acme/browser-pilot",
                summary="GitHub browser automation donor.",
                candidate_source_ref="https://github.com/acme/browser-pilot",
                candidate_source_version="main",
                candidate_source_lineage="donor:github:acme/browser-pilot",
                canonical_package_id="pkg:github:acme/browser-pilot",
                equivalence_class="pkg:github:acme/browser-pilot",
            ),
        ],
        target_scope="seat",
        target_role_id="execution-core",
        target_seat_ref="seat-1",
    )

    assert len(imported) == 1
    assert imported[0].candidate_kind == "project"
    assert imported[0].candidate_source_ref == "https://github.com/acme/browser-pilot"
    assert imported[0].canonical_package_id == "pkg:github:acme/browser-pilot"


def test_capability_portfolio_service_reports_runtime_discovery_and_package_metadata(
    tmp_path: Path,
) -> None:
    (
        candidate_service,
        _donor_service,
        _trial_service,
        _decision_service,
        portfolio_service,
    ) = _build_portfolio_services(tmp_path)

    candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="1.2.3",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="research_pack",
        summary="Governed remote research pack candidate.",
        status="active",
        lifecycle_stage="active",
    )
    candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="local_authored",
        candidate_source_ref=str(tmp_path / "skills" / "local_research" / "SKILL.md"),
        candidate_source_version="draft-v1",
        ingestion_mode="manual",
        proposed_skill_name="local_research",
        summary="Local authored fallback skill.",
        status="active",
        lifecycle_stage="active",
    )
    candidate_service.normalize_candidate_source(
        candidate_kind="mcp-bundle",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://browser",
        candidate_source_version="2026.04.04",
        ingestion_mode="baseline-import",
        proposed_skill_name="browser_registry",
        summary="Baseline browser runtime.",
        status="active",
        lifecycle_stage="baseline",
    )

    portfolio = portfolio_service.get_runtime_portfolio_summary()
    discovery = portfolio_service.get_runtime_discovery_summary()

    assert portfolio["donor_count"] == 1
    assert portfolio["active_donor_count"] == 1
    assert portfolio["fallback_only_candidate_count"] == 2
    assert portfolio["package_kind_count"] == {"skill": 1}
    assert portfolio["candidate_source_kind_count"] == {"external_remote": 1}
    assert portfolio["routes"]["discovery"] == "/api/runtime-center/capabilities/discovery"

    assert discovery["status"] == "degraded"
    assert discovery["source_profile_count"] == 1
    assert discovery["trusted_source_count"] == 0
    assert discovery["active_source_count"] == 1
    assert discovery["watchlist_source_count"] == 1
    assert discovery["fallback_only_source_count"] == 2
    assert discovery["by_source_kind"] == {"external_remote": 1}


def test_capability_portfolio_service_emits_structured_governance_actions(
    tmp_path: Path,
) -> None:
    (
        candidate_service,
        _donor_service,
        trial_service,
        decision_service,
        portfolio_service,
    ) = _build_portfolio_services(tmp_path)

    created: list[object] = []
    for idx in range(1, 5):
        created.append(
            candidate_service.normalize_candidate_source(
                candidate_kind="skill",
                target_scope="seat",
                target_role_id="researcher",
                target_seat_ref="seat-1",
                candidate_source_kind="external_remote",
                candidate_source_ref=f"https://example.com/skills/research-pack-{idx}.zip",
                candidate_source_version=f"1.2.{idx}",
                ingestion_mode="prediction-recommendation",
                proposed_skill_name=f"research_pack_{idx}",
                summary=f"Governed research donor {idx}.",
                status="active" if idx == 1 else "candidate",
                lifecycle_stage="active" if idx == 1 else "trial",
            ),
        )
    trial_service.create_or_update_trial(
        candidate_id=created[0].candidate_id,
        scope_type="seat",
        scope_ref="seat-1",
        verdict="passed",
        success_count=2,
        summary="Seat trial passed.",
    )
    decision_service.create_decision(
        candidate_id=created[0].candidate_id,
        decision_kind="replace_existing",
        from_stage="trial",
        to_stage="active",
        reason="Replacement-first review required.",
    )
    decision_service.create_decision(
        candidate_id=created[1].candidate_id,
        decision_kind="retire",
        from_stage="active",
        to_stage="retired",
        reason="Retirement governance required.",
    )

    portfolio = portfolio_service.get_runtime_portfolio_summary()
    governance_actions = {
        item["action"]: item for item in portfolio["governance_actions"]
    }

    assert governance_actions["compact_over_budget_scope"]["scope_key"] == "seat:researcher:seat-1"
    assert governance_actions["compact_over_budget_scope"]["budget_limit"] == 3
    assert governance_actions["compact_over_budget_scope"]["donor_count"] == 4
    assert governance_actions["compact_over_budget_scope"]["target_scope"] == "seat"
    assert governance_actions["compact_over_budget_scope"]["target_role_id"] == "researcher"
    assert governance_actions["compact_over_budget_scope"]["target_seat_ref"] == "seat-1"
    assert governance_actions["review_replacement_pressure"]["priority"] == "high"
    assert created[0].donor_id in governance_actions["review_replacement_pressure"]["donor_ids"]
    assert governance_actions["review_retirement_pressure"]["priority"] == "high"
    assert created[1].donor_id in governance_actions["review_retirement_pressure"]["donor_ids"]
    assert any(
        item["action"] == "compact_over_budget_scope"
        for item in portfolio["planning_actions"]
    )


def test_skill_gap_detector_distinguishes_revision_replace_and_retire_pressures() -> None:
    detector = SkillGapDetector()

    replacement = detector.build_reentry_summary(
        trial_summary={
            "aggregate_verdict": "rollback_recommended",
            "operator_intervention_count": 1,
            "history": [
                {
                    "entry_kind": "decision",
                    "decision_kind": "rollback",
                    "replacement_target_ids": ["skill:legacy"],
                },
            ],
        },
        latest_decision_kind="rollback",
    )
    revision = detector.build_reentry_summary(
        trial_summary={
            "aggregate_verdict": "mixed",
            "operator_intervention_count": 1,
            "history": [
                {
                    "entry_kind": "trial",
                    "scope_type": "session",
                    "scope_ref": "session-1",
                    "verdict": "passed",
                },
            ],
        },
        latest_decision_kind="continue_trial",
    )
    retirement = detector.build_reentry_summary(
        trial_summary={
            "aggregate_verdict": "passed",
            "operator_intervention_count": 0,
            "history": [
                {
                    "entry_kind": "decision",
                    "decision_kind": "retire",
                },
            ],
        },
        latest_decision_kind="retire",
    )

    assert replacement["reentry_kind"] == "replacement"
    assert replacement["replacement_pressure"] is True
    assert replacement["revision_pressure"] is False
    assert replacement["retirement_pressure"] is False

    assert revision["reentry_kind"] == "revision"
    assert revision["replacement_pressure"] is False
    assert revision["revision_pressure"] is True
    assert revision["retirement_pressure"] is False

    assert retirement["reentry_kind"] == "retirement"
    assert retirement["replacement_pressure"] is False
    assert retirement["revision_pressure"] is False
    assert retirement["retirement_pressure"] is True


def test_prediction_trial_followup_emits_revision_reentry_for_mixed_trial_drift() -> None:
    service = _TrialFollowupHarness(
        recommendations=[
            PredictionRecommendationRecord(
                recommendation_id="rec-trial-nextgen",
                case_id="case-trial-history",
                recommendation_type="capability_recommendation",
                title="Trial nextgen outreach",
                summary="Executed governed trial for the new outreach candidate.",
                action_kind="system:trial_remote_skill_assignment",
                executable=True,
                status="executed",
                target_agent_id="industry-solution-lead-demo",
                target_capability_ids=[
                    "skill:legacy_outreach",
                    "skill:nextgen_outreach",
                ],
                action_payload={
                    "candidate": {"install_name": "nextgen_outreach"},
                    "target_agent_id": "industry-solution-lead-demo",
                    "capability_ids": ["skill:nextgen_outreach"],
                    "replacement_capability_ids": ["skill:legacy_outreach"],
                    "capability_assignment_mode": "replace",
                },
                metadata={
                    "gap_kind": "underperforming_capability",
                    "optimization_stage": "trial",
                    "industry_instance_id": "industry-demo",
                    "candidate_id": "candidate-nextgen-outreach",
                    "target_agent_id": "industry-solution-lead-demo",
                    "replacement_capability_ids": ["skill:legacy_outreach"],
                    "replacement_capability_id": "skill:legacy_outreach",
                    "installed_capability_ids": ["skill:nextgen_outreach"],
                    "selected_seat_ref": "env-browser-primary",
                    "trial_scope": "single-seat",
                    "candidate_source_kind": "external_remote",
                    "candidate_source_ref": "hub:nextgen-outreach",
                    "candidate_source_lineage": "hub:nextgen-outreach",
                    "last_execution_output": {
                        "installed_capability_ids": ["skill:nextgen_outreach"],
                    },
                },
            ),
        ],
    )
    case = PredictionCaseRecord(
        case_id="case-trial-history",
        title="Trial history",
        summary="Seed case for revision follow-up.",
        industry_instance_id="industry-demo",
        owner_scope="industry-demo-scope",
    )
    facts = _FactPack(
        scope_type="industry",
        scope_id="industry-demo",
        report={},
        performance={},
        goals=[],
        tasks=[],
        workflows=[],
        agents=[],
        capabilities=[],
        strategy={},
    )

    findings = service._trial_followup_findings(
        case=case,
        facts=facts,
        telemetry={
            ("industry-solution-lead-demo", "skill:nextgen_outreach"): {
                "manual_intervention_rate": 0.5,
                "success_rate": 0.5,
                "failure_rate": 0.0,
                "sample_count": 2,
            },
            ("industry-solution-lead-demo", "skill:legacy_outreach"): {
                "manual_intervention_rate": 0.5,
                "success_rate": 0.5,
                "failure_rate": 0.0,
                "sample_count": 2,
            },
        },
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding["gap_kind"] == "capability_revision"
    assert finding["optimization_stage"] == "revision"
    assert finding["lifecycle_stage"] == "trial"
    assert finding["candidate_lifecycle_stage"] == "trial"
    assert finding["replacement_target_stage"] == "active"
    assert finding["old_capability_id"] == "skill:legacy_outreach"
    assert finding["new_capability_id"] == "skill:nextgen_outreach"
    assert finding["target_agent_id"] == "industry-solution-lead-demo"
    assert finding["candidate_id"] == "candidate-nextgen-outreach"
    assert finding["source_recommendation_id"] == "rec-trial-nextgen"
    assert finding["selected_seat_ref"] == "env-browser-primary"
    assert finding["trial_scope"] == "single-seat"
    assert finding["replacement_target_ids"] == ["skill:legacy_outreach"]
    assert finding["rollback_target_ids"] == ["skill:legacy_outreach"]
    assert finding["reentry_kind"] == "revision"
    assert finding["drift_summary"]["status"] == "pressure"
    assert finding["drift_summary"]["reentry_kind"] == "revision"
    assert finding["drift_summary"]["revision_pressure"] is True
    assert finding["drift_summary"]["replacement_pressure"] is False
    assert finding["drift_summary"]["retirement_pressure"] is False
    assert "human-takeover" in finding["drift_summary"]["reasons"]
    assert finding["drift_summary"]["replacement_target_ids"] == [
        "skill:legacy_outreach"
    ]
    assert finding["stats"]["new_stats"]["manual_intervention_rate"] == 0.5
    assert finding["stats"]["old_stats"]["manual_intervention_rate"] == 0.5
    assert finding["candidate_source_kind"] == "external_remote"
    assert finding["candidate_source_ref"] == "hub:nextgen-outreach"
    assert finding["candidate_source_lineage"] == "hub:nextgen-outreach"


def test_prediction_recommendations_convert_revision_reentry_into_formal_continue_trial() -> None:
    finding = {
        "gap_kind": "capability_revision",
        "optimization_stage": "revision",
        "lifecycle_stage": "trial",
        "candidate_lifecycle_stage": "trial",
        "replacement_target_stage": "active",
        "old_capability_id": "skill:legacy_outreach",
        "new_capability_id": "skill:nextgen_outreach",
        "target_agent_id": "industry-solution-lead-demo",
        "candidate_id": "candidate-nextgen-outreach",
        "source_recommendation_id": "rec-trial-nextgen",
        "selected_seat_ref": "env-browser-primary",
        "trial_scope": "single-seat",
        "replacement_target_ids": ["skill:legacy_outreach"],
        "rollback_target_ids": ["skill:legacy_outreach"],
        "reentry_kind": "revision",
        "drift_summary": {
            "status": "pressure",
            "reasons": ["human-takeover"],
            "reentry_kind": "revision",
            "replacement_pressure": False,
            "retirement_pressure": False,
            "revision_pressure": True,
            "replacement_target_ids": ["skill:legacy_outreach"],
        },
        "stats": {
            "new_stats": {"manual_intervention_rate": 0.5},
            "old_stats": {"manual_intervention_rate": 0.0},
        },
        "candidate_source_kind": "external_remote",
        "candidate_source_ref": "hub:nextgen-outreach",
        "candidate_source_lineage": "hub:nextgen-outreach",
    }
    service = _RevisionRecommendationHarness(finding)
    case = PredictionCaseRecord(
        case_id="case-trial-history",
        title="Trial history",
        summary="Seed case for revision follow-up.",
        industry_instance_id="industry-demo",
        owner_scope="industry-demo-scope",
    )
    facts = _FactPack(
        scope_type="industry",
        scope_id="industry-demo",
        report={},
        performance={},
        goals=[],
        tasks=[],
        workflows=[],
        agents=[],
        capabilities=[],
        strategy={},
    )

    recommendations = service._build_recommendations(
        case=case,
        facts=facts,
        signals=[
            PredictionSignalRecord(
                case_id=case.case_id,
                label="trial drift",
                summary="Trial stayed mixed and still needs operator intervention.",
                source_kind="report",
                source_ref="report:weekly",
                direction="negative",
                strength=0.4,
            ),
        ],
    )

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation.metadata["gap_kind"] == "capability_revision"
    assert recommendation.metadata["reentry_kind"] == "revision"
    assert recommendation.metadata["drift_summary"]["revision_pressure"] is True
    assert recommendation.action_kind == "system:apply_capability_lifecycle"
    assert recommendation.action_payload["decision_kind"] == "continue_trial"
    assert recommendation.action_payload["improvement_mode"] == "revision"
    assert recommendation.action_payload["selected_scope"] == "seat"
    assert recommendation.action_payload["selected_seat_ref"] == "env-browser-primary"
    assert recommendation.action_payload["replacement_target_ids"] == [
        "skill:legacy_outreach"
    ]
    assert recommendation.action_payload["rollback_target_ids"] == [
        "skill:legacy_outreach"
    ]
    [created] = service._skill_lifecycle_decision_service.calls
    assert created["decision_kind"] == "continue_trial"
    assert created["from_stage"] == "trial"
    assert created["to_stage"] == "trial"
    assert created["metadata"]["gap_kind"] == "capability_revision"
    assert created["metadata"]["trial_scope"] == "single-seat"


def test_prediction_missing_mcp_recommendation_carries_shared_trial_contract_metadata(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "mcp-trial-contract.sqlite3")
    donor_service = CapabilityDonorService(state_store=store)
    candidate_service = CapabilityCandidateService(
        state_store=store,
        donor_service=donor_service,
    )
    service = _MissingMCPRecommendationHarness(
        candidate_service=candidate_service,
        existing_client={
            "key": "desktop_windows",
            "name": "Desktop Windows",
            "enabled": False,
            "transport": "stdio",
        },
    )
    case = PredictionCaseRecord(
        case_id="case-mcp-gap",
        title="Desktop capability gap",
        summary="Need local desktop MCP before the workflow can continue.",
        industry_instance_id="industry-demo",
        owner_scope="industry-demo-scope",
    )
    facts = _FactPack(
        scope_type="industry",
        scope_id="industry-demo",
        report={},
        performance={},
        goals=[],
        tasks=[],
        workflows=[
            SimpleNamespace(
                run_id="run-desktop-gap",
                title="Desktop outreach smoke",
                preview_payload={
                    "dependencies": [
                        {
                            "capability_id": "mcp:desktop_windows",
                            "target_agent_ids": ["industry-solution-lead-demo"],
                            "install_templates": [
                                {
                                    "template_id": "desktop-windows",
                                    "name": "Desktop Windows",
                                    "default_client_key": "desktop_windows",
                                }
                            ],
                        }
                    ],
                    "missing_capability_ids": ["mcp:desktop_windows"],
                    "assignment_gap_capability_ids": [],
                },
            )
        ],
        agents=[],
        capabilities=[],
        strategy={},
    )

    recommendations = service._build_recommendations(case=case, facts=facts, signals=[])

    recommendation = next(
        item
        for item in recommendations
        if item.action_kind == "system:update_mcp_client"
    )
    assert recommendation.metadata["candidate_id"]
    assert recommendation.metadata["candidate_kind"] == "mcp-bundle"
    assert recommendation.metadata["candidate_source_kind"] == "external_catalog"
    assert recommendation.metadata["target_agent_id"] == "industry-solution-lead-demo"
    assert recommendation.metadata["selected_scope"] == "seat"
    assert recommendation.metadata["selected_seat_ref"] == "env-browser-primary"
    assert recommendation.metadata["rollback_target_ids"] == ["mcp:desktop_windows"]
    assert recommendation.metadata["target_capability_family"] == "mcp"
    assert recommendation.metadata["trial_contract"]["challenger_ref"] == (
        "template:desktop-windows:desktop_windows"
    )
    assert recommendation.metadata["trial_contract"]["rollback"]["fallback_action"] == (
        "disable_mcp_client"
    )
    assert recommendation.action_payload["trial_contract"]["selected_scope"] == "seat"


def test_prediction_hot_agent_load_shedding_recommendation_is_manual_only() -> None:
    service = _AgentLoadRecommendationHarness()
    case = PredictionCaseRecord(
        case_id="case-agent-load",
        title="Agent load pressure",
        summary="One execution seat is overloaded and needs governance review.",
        industry_instance_id="industry-demo",
        owner_scope="industry-demo-scope",
    )
    facts = _FactPack(
        scope_type="industry",
        scope_id="industry-demo",
        report={},
        performance={},
        goals=[],
        tasks=[],
        workflows=[],
        agents=[],
        capabilities=[],
        strategy={},
    )

    recommendations = service._build_recommendations(case=case, facts=facts, signals=[])

    recommendation = next(
        item for item in recommendations if item.target_agent_id == "industry-ops-hot"
    )
    assert recommendation.action_kind == "manual:coordinate-main-brain"
    assert recommendation.executable is False
    assert recommendation.status == "manual-only"
    assert recommendation.action_payload == {}


def test_capability_candidate_service_persists_candidate_attribution_fields(
    tmp_path: Path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    donor_service = CapabilityDonorService(state_store=state_store)
    candidate_service = CapabilityCandidateService(
        state_store=state_store,
        donor_service=donor_service,
    )

    created = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="2.4.0",
        candidate_source_lineage="donor:research-pack",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="research_pack",
        summary="Research automation donor candidate.",
        metadata={
            "source_aliases": [
                "https://mirror.example/research-pack.zip",
            ],
            "equivalence_class": "pkg:research-pack",
            "capability_overlap_score": 0.88,
            "replacement_relation": "replace_requested",
        },
    )

    reloaded = candidate_service.list_candidates(limit=1)[0]

    assert created.donor_id is not None
    assert created.package_id is not None
    assert created.source_profile_id is not None
    assert reloaded.canonical_package_id is not None
    assert reloaded.canonical_package_id == created.canonical_package_id
    assert "https://mirror.example/research-pack.zip" in reloaded.source_aliases
    assert "https://example.com/skills/research-pack.zip" in reloaded.source_aliases
    assert reloaded.equivalence_class == "pkg:research-pack"
    assert reloaded.capability_overlap_score == 0.88
    assert reloaded.replacement_relation == "replace_requested"


def test_capability_evolution_records_carry_formal_donor_execution_contract_statuses() -> None:
    from copaw.state.models_capability_evolution import (
        CapabilityCandidateRecord,
        SkillLifecycleDecisionRecord,
        SkillTrialRecord,
    )

    candidate = CapabilityCandidateRecord(
        candidate_kind="adapter",
        target_scope="seat",
        verified_stage="runtime_operable",
        provider_resolution_status="resolved",
        compatibility_status="compatible_native",
    )
    trial = SkillTrialRecord(
        candidate_id=candidate.candidate_id,
        scope_ref="seat-1",
        verified_stage="adapter_probe_passed",
        provider_resolution_status="resolved",
        compatibility_status="compatible_via_bridge",
    )
    decision = SkillLifecycleDecisionRecord(
        candidate_id=candidate.candidate_id,
        decision_kind="promote",
        verified_stage="primary_action_verified",
        provider_resolution_status="resolved",
        compatibility_status="compatible_native",
    )

    assert candidate.verified_stage == "runtime_operable"
    assert candidate.provider_resolution_status == "resolved"
    assert candidate.compatibility_status == "compatible_native"
    assert trial.verified_stage == "adapter_probe_passed"
    assert trial.provider_resolution_status == "resolved"
    assert trial.compatibility_status == "compatible_via_bridge"
    assert decision.verified_stage == "primary_action_verified"
    assert decision.provider_resolution_status == "resolved"
    assert decision.compatibility_status == "compatible_native"


def test_capability_candidate_service_persists_formal_donor_execution_contract_statuses(
    tmp_path: Path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    candidate_service = CapabilityCandidateService(state_store=state_store)

    created = candidate_service.normalize_candidate_source(
        candidate_kind="adapter",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/adapters/research-bridge.zip",
        candidate_source_version="2.0.0",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="research_bridge",
        summary="Research bridge donor candidate.",
        verified_stage="runtime_operable",
        provider_resolution_status="resolved",
        compatibility_status="compatible_native",
    )

    with state_store.connection() as conn:
        row = conn.execute(
            """
            SELECT verified_stage, provider_resolution_status, compatibility_status
            FROM capability_candidates
            WHERE candidate_id = ?
            """,
            (created.candidate_id,),
        ).fetchone()

    reloaded_service = CapabilityCandidateService(
        state_store=SQLiteStateStore(tmp_path / "state.sqlite3"),
    )
    reloaded = reloaded_service.get_candidate(created.candidate_id)

    assert row is not None
    assert row["verified_stage"] == "runtime_operable"
    assert row["provider_resolution_status"] == "resolved"
    assert row["compatibility_status"] == "compatible_native"
    assert reloaded is not None
    assert reloaded.verified_stage == "runtime_operable"
    assert reloaded.provider_resolution_status == "resolved"
    assert reloaded.compatibility_status == "compatible_native"


def test_capability_candidate_service_updates_formal_donor_execution_contract_statuses(
    tmp_path: Path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    candidate_service = CapabilityCandidateService(state_store=state_store)

    created = candidate_service.normalize_candidate_source(
        candidate_kind="adapter",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/adapters/research-bridge.zip",
        candidate_source_version="2.0.0",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="research_bridge",
        summary="Research bridge donor candidate.",
    )
    updated = candidate_service.update_candidate_status(
        created.candidate_id,
        verified_stage="adapter_probe_passed",
        provider_resolution_status="resolved",
        compatibility_status="compatible_via_bridge",
    )

    reloaded = CapabilityCandidateService(
        state_store=SQLiteStateStore(tmp_path / "state.sqlite3"),
    ).get_candidate(created.candidate_id)

    assert updated is not None
    assert updated.verified_stage == "adapter_probe_passed"
    assert updated.provider_resolution_status == "resolved"
    assert updated.compatibility_status == "compatible_via_bridge"
    assert reloaded is not None
    assert reloaded.verified_stage == "adapter_probe_passed"
    assert reloaded.provider_resolution_status == "resolved"
    assert reloaded.compatibility_status == "compatible_via_bridge"


def test_capability_evolution_schema_migrates_formal_donor_execution_contract_columns(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE capability_candidates (
                candidate_id TEXT PRIMARY KEY,
                donor_id TEXT,
                package_id TEXT,
                source_profile_id TEXT,
                canonical_package_id TEXT,
                candidate_source_kind TEXT,
                candidate_source_ref TEXT,
                candidate_source_version TEXT,
                target_scope TEXT,
                target_role_id TEXT,
                target_seat_ref TEXT,
                equivalence_class TEXT,
                updated_at TEXT
            );
            CREATE TABLE skill_trials (
                trial_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                donor_id TEXT,
                package_id TEXT,
                source_profile_id TEXT,
                scope_type TEXT,
                scope_ref TEXT,
                updated_at TEXT
            );
            CREATE TABLE skill_lifecycle_decisions (
                decision_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                donor_id TEXT,
                package_id TEXT,
                source_profile_id TEXT,
                decision_kind TEXT,
                updated_at TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    store = SQLiteStateStore(db_path)
    store.initialize()

    with store.connection() as conn:
        candidate_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(capability_candidates)")
        }
        trial_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(skill_trials)")
        }
        decision_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(skill_lifecycle_decisions)")
        }

    assert {
        "verified_stage",
        "provider_resolution_status",
        "compatibility_status",
    }.issubset(candidate_columns)
    assert {
        "verified_stage",
        "provider_resolution_status",
        "compatibility_status",
    }.issubset(trial_columns)
    assert {
        "verified_stage",
        "provider_resolution_status",
        "compatibility_status",
    }.issubset(decision_columns)


def test_import_normalized_discovery_hits_preserves_protocol_surface_metadata(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    hit = NormalizedDiscoveryHit(
        candidate_kind="adapter",
        candidate_source_kind="external_remote",
        display_name="OpenSpace MCP",
        summary="MCP-backed donor candidate.",
        candidate_source_ref="https://example.com/openspace",
        candidate_source_version="main",
        candidate_source_lineage="donor:github:hku/openspace",
        canonical_package_id="pkg:github:hku/openspace",
        equivalence_class="pkg:github:hku/openspace",
        protocol_surface_kind="native_mcp",
        transport_kind="mcp",
        call_surface_ref="mcp:openspace",
        formal_adapter_eligible=True,
    )

    imported = service.import_normalized_discovery_hits(
        normalized_hits=[hit],
        target_scope="seat",
        target_role_id="operator",
        target_seat_ref="seat-1",
    )

    assert len(imported) == 1
    assert imported[0].metadata["protocol_surface_kind"] == "native_mcp"
    assert imported[0].metadata["transport_kind"] == "mcp"
    assert imported[0].metadata["call_surface_ref"] == "mcp:openspace"
    assert imported[0].metadata["formal_adapter_eligible"] is True
