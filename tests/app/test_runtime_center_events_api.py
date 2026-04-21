# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from copaw.app.runtime_events import RuntimeEventBus
from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.startup_recovery import StartupRecoverySummary
from copaw.memory.conversation_compaction_service import ConversationCompactionService
from copaw.state import SQLiteStateStore
from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state.capability_portfolio_service import CapabilityPortfolioService
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.skill_lifecycle_decision_service import SkillLifecycleDecisionService
from copaw.state.skill_trial_service import SkillTrialService


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(runtime_center_router)
    return app


def test_runtime_center_events_endpoint_streams_published_events() -> None:
    app = _build_app()
    bus = RuntimeEventBus()
    bus.publish(
        topic="task",
        action="completed",
        payload={"task_id": "task-1", "phase": "completed"},
    )
    app.state.runtime_event_bus = bus

    client = TestClient(app)
    response = client.get("/runtime-center/events", params={"once": True})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: runtime" in response.text
    assert '"event_name": "task.completed"' in response.text
    assert '"task_id": "task-1"' in response.text


def test_runtime_center_recovery_latest_endpoint_returns_summary() -> None:
    app = _build_app()
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="startup",
        reaped_expired_leases=2,
        recovered_orphaned_mailbox_items=3,
        pending_decisions=2,
        hydrated_waiting_confirm_tasks=1,
        active_schedules=3,
        absorption_action_kind="human-assist",
        absorption_action_summary="Need one governed confirmation to resume.",
        absorption_action_materialized=True,
        absorption_human_task_id="human-assist-1",
    )

    client = TestClient(app)
    response = client.get("/runtime-center/recovery/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reason"] == "startup"
    assert payload["source"] == "startup"
    assert payload["pending_decisions"] == 2
    assert payload["hydrated_waiting_confirm_tasks"] == 1
    assert payload["active_schedules"] == 3
    assert payload["absorption_action_kind"] == "human-assist"
    assert (
        payload["absorption_action_summary"]
        == "Need one governed confirmation to resume."
    )
    assert payload["absorption_action_materialized"] is True
    assert payload["absorption_human_task_id"] == "human-assist-1"
    assert payload["detail"]["leases"]["reaped_expired_leases"] == 2
    assert payload["detail"]["mailbox"]["recovered_orphaned_mailbox_items"] == 3
    assert payload["detail"]["decisions"]["pending_decisions"] == 2
    assert payload["detail"]["automation"]["active_schedules"] == 3


def test_runtime_center_recovery_latest_endpoint_prefers_canonical_latest_report() -> None:
    app = _build_app()
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="startup",
        pending_decisions=2,
        hydrated_waiting_confirm_tasks=1,
        active_schedules=3,
    )
    app.state.latest_recovery_report = {
        "reason": "runtime-recovery",
        "pending_decisions": 1,
        "active_schedules": 4,
        "latest_scope": "runtime",
    }

    client = TestClient(app)
    response = client.get("/runtime-center/recovery/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reason"] == "runtime-recovery"
    assert payload["source"] == "latest"
    assert payload["pending_decisions"] == 1
    assert payload["active_schedules"] == 4
    assert payload["latest_scope"] == "runtime"
    assert payload["detail"]["decisions"]["pending_decisions"] == 1
    assert payload["detail"]["automation"]["active_schedules"] == 4


def test_runtime_center_recovery_latest_endpoint_prefers_environment_runtime_report() -> None:
    app = _build_app()
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="startup",
        pending_decisions=2,
        active_schedules=3,
    )
    app.state.latest_recovery_report = {
        "reason": "stale-startup-alias",
        "pending_decisions": 9,
        "active_schedules": 9,
    }

    class FakeEnvironmentService:
        def get_latest_recovery_report(self):
            return {
                "reason": "runtime-recovery",
                "pending_decisions": 1,
                "active_schedules": 4,
                "executed": 2,
                "latest_scope": "runtime",
            }

    app.state.environment_service = FakeEnvironmentService()

    client = TestClient(app)
    response = client.get("/runtime-center/recovery/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reason"] == "runtime-recovery"
    assert payload["source"] == "latest"
    assert payload["pending_decisions"] == 1
    assert payload["active_schedules"] == 4
    assert payload["executed"] == 2
    assert payload["latest_scope"] == "runtime"


def test_runtime_center_capability_candidates_endpoint_returns_state_query_projection() -> None:
    app = _build_app()

    class FakeStateQueryService:
        def list_capability_candidates(self, *, limit: int | None = None):
            return [
                {
                    "candidate_id": "cand-1",
                    "candidate_kind": "skill",
                    "candidate_source_kind": "external_remote",
                    "status": "candidate",
                },
            ][: limit or 20]

    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/capabilities/candidates", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {
            "candidate_id": "cand-1",
            "candidate_kind": "skill",
            "candidate_source_kind": "external_remote",
            "status": "candidate",
        },
    ]


def test_runtime_center_capability_trials_endpoint_returns_state_query_projection() -> None:
    app = _build_app()

    class FakeStateQueryService:
        def list_capability_trials(self, *, candidate_id: str | None = None, limit: int | None = None):
            assert candidate_id == "cand-1"
            return [
                {
                    "trial_id": "trial-1",
                    "candidate_id": "cand-1",
                    "scope_type": "seat",
                    "scope_ref": "seat-primary",
                    "verdict": "passed",
                },
            ][: limit or 20]

    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get(
        "/runtime-center/capabilities/trials",
        params={"candidate_id": "cand-1", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "trial_id": "trial-1",
            "candidate_id": "cand-1",
            "scope_type": "seat",
            "scope_ref": "seat-primary",
            "verdict": "passed",
        },
    ]


def test_runtime_center_capability_donors_endpoint_returns_state_query_projection() -> None:
    app = _build_app()

    class FakeStateQueryService:
        def list_capability_donors(self, *, limit: int | None = None):
            return [
                {
                    "donor_id": "donor-1",
                    "donor_kind": "skill",
                    "status": "active",
                    "trust_status": "trusted",
                },
            ][: limit or 20]

    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/capabilities/donors", params={"limit": 5})

    assert response.status_code == 200
    assert response.json() == [
        {
            "donor_id": "donor-1",
            "donor_kind": "skill",
            "status": "active",
            "trust_status": "trusted",
        },
    ]


def test_runtime_center_state_query_marks_project_donor_surfaces_as_compatibility_only() -> None:
    state_query = RuntimeCenterStateQueryService(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=None,
        schedule_repository=object(),
        goal_repository=None,
        work_context_repository=None,
        decision_request_repository=object(),
        capability_donor_service=SimpleNamespace(
            list_donors=lambda limit=20: [
                {
                    "donor_id": "donor-project-1",
                    "donor_kind": "project",
                    "status": "candidate",
                },
            ][: limit or 20],
        ),
        donor_package_service=SimpleNamespace(
            list_packages=lambda donor_id=None, limit=20: [
                {
                    "package_id": "pkg-project-1",
                    "donor_id": donor_id or "donor-project-1",
                    "package_kind": "github-archive-zip",
                },
            ][: limit or 20],
        ),
    )

    donors = state_query.list_capability_donors(limit=5)
    packages = state_query.list_capability_packages(donor_id="donor-project-1", limit=5)

    assert donors == [
        {
            "donor_id": "donor-project-1",
            "donor_kind": "project",
            "status": "candidate",
            "compatibility_mode": "compatibility/acquisition-only",
            "formal_surface": False,
        },
    ]
    assert packages == [
        {
            "package_id": "pkg-project-1",
            "donor_id": "donor-project-1",
            "package_kind": "github-archive-zip",
            "compatibility_mode": "compatibility/acquisition-only",
            "formal_surface": False,
        },
    ]


def test_runtime_center_capability_source_profiles_endpoint_returns_state_query_projection() -> None:
    app = _build_app()

    class FakeStateQueryService:
        def list_capability_source_profiles(self, *, limit: int | None = None):
            return [
                {
                    "source_profile_id": "source-1",
                    "source_kind": "external_catalog",
                    "trust_posture": "trusted",
                    "active": True,
                },
            ][: limit or 20]

    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get(
        "/runtime-center/capabilities/source-profiles",
        params={"limit": 5},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "source_profile_id": "source-1",
            "source_kind": "external_catalog",
            "trust_posture": "trusted",
            "active": True,
        },
    ]


def test_runtime_center_capability_portfolio_endpoint_returns_state_query_projection() -> None:
    app = _build_app()

    class FakeStateQueryService:
        def get_capability_portfolio_summary(self):
            return {
                "donor_count": 2,
                "active_donor_count": 1,
                "candidate_donor_count": 1,
                "trial_donor_count": 1,
                "fallback_only_candidate_count": 2,
                "over_budget_scope_count": 0,
                "scope_breakdown": [
                    {
                        "scope_key": "seat:role-ops:seat-a",
                        "donor_count": 2,
                        "candidate_count": 2,
                    },
                ],
            }

    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/capabilities/portfolio")

    assert response.status_code == 200
    assert response.json() == {
        "donor_count": 2,
        "active_donor_count": 1,
        "candidate_donor_count": 1,
        "trial_donor_count": 1,
        "fallback_only_candidate_count": 2,
        "over_budget_scope_count": 0,
        "scope_breakdown": [
            {
                "scope_key": "seat:role-ops:seat-a",
                "donor_count": 2,
                "candidate_count": 2,
            },
        ],
    }


def test_runtime_center_capability_discovery_endpoint_returns_state_query_projection() -> None:
    app = _build_app()

    class FakeStateQueryService:
        def get_capability_discovery_summary(self):
            return {
                "status": "ready",
                "source_profile_count": 2,
                "active_source_count": 2,
                "trusted_source_count": 1,
                "watchlist_source_count": 1,
                "fallback_only_source_count": 2,
                "by_source_kind": {
                    "external_catalog": 1,
                    "external_remote": 1,
                },
            }

    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/capabilities/discovery")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "source_profile_count": 2,
        "active_source_count": 2,
        "trusted_source_count": 1,
        "watchlist_source_count": 1,
        "fallback_only_source_count": 2,
        "by_source_kind": {
            "external_catalog": 1,
            "external_remote": 1,
        },
    }


def test_runtime_center_state_query_portfolio_summary_filters_local_and_baseline_candidates() -> None:
    class _CandidateService:
        def list_candidates(self, *, limit: int | None = None):
            return [
                SimpleNamespace(
                    candidate_id="cand-external-active",
                    donor_id="donor-external-a",
                    source_profile_id="source-external-a",
                    target_scope="seat",
                    target_role_id="role-ops",
                    target_seat_ref="seat-a",
                    status="active",
                    lifecycle_stage="active",
                    candidate_source_kind="external_remote",
                    ingestion_mode="prediction-recommendation",
                ),
                SimpleNamespace(
                    candidate_id="cand-external-trial",
                    donor_id="donor-external-b",
                    source_profile_id="source-external-b",
                    target_scope="seat",
                    target_role_id="role-ops",
                    target_seat_ref="seat-a",
                    status="candidate",
                    lifecycle_stage="trial",
                    candidate_source_kind="external_catalog",
                    ingestion_mode="prediction-recommendation",
                ),
                SimpleNamespace(
                    candidate_id="cand-local",
                    donor_id="donor-local",
                    source_profile_id="source-local",
                    target_scope="seat",
                    target_role_id="role-ops",
                    target_seat_ref="seat-a",
                    status="active",
                    lifecycle_stage="active",
                    candidate_source_kind="local_authored",
                    ingestion_mode="manual",
                ),
                SimpleNamespace(
                    candidate_id="cand-baseline",
                    donor_id="donor-baseline",
                    source_profile_id="source-baseline",
                    target_scope="seat",
                    target_role_id="role-ops",
                    target_seat_ref="seat-a",
                    status="active",
                    lifecycle_stage="baseline",
                    candidate_source_kind="external_catalog",
                    ingestion_mode="baseline-import",
                ),
            ]

    class _DonorService:
        def list_donors(self, *, limit: int | None = None):
            return [
                SimpleNamespace(donor_id="donor-external-a", source_kind="external_remote"),
                SimpleNamespace(donor_id="donor-external-b", source_kind="external_catalog"),
                SimpleNamespace(donor_id="donor-local", source_kind="local_authored"),
                SimpleNamespace(donor_id="donor-baseline", source_kind="external_catalog"),
            ]

        def list_source_profiles(self, *, limit: int | None = None):
            return []

        def list_trust_records(self, *, limit: int | None = None):
            return []

    class _TrialService:
        def list_trials(self, *, candidate_id: str | None = None, limit: int | None = None):
            return []

    class _DecisionService:
        def list_decisions(self, *, candidate_id: str | None = None, limit: int | None = None):
            return []

    portfolio_service = CapabilityPortfolioService(
        donor_service=_DonorService(),
        candidate_service=_CandidateService(),
        skill_trial_service=_TrialService(),
        skill_lifecycle_decision_service=_DecisionService(),
    )

    state_query = RuntimeCenterStateQueryService(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=None,
        schedule_repository=object(),
        goal_repository=None,
        work_context_repository=None,
        decision_request_repository=object(),
        capability_candidate_service=_CandidateService(),
        capability_donor_service=_DonorService(),
        capability_portfolio_service=portfolio_service,
    )

    payload = state_query.get_capability_portfolio_summary()

    assert payload["donor_count"] == 2
    assert payload["active_donor_count"] == 1
    assert payload["candidate_donor_count"] == 1
    assert payload["trial_donor_count"] == 1
    assert payload["fallback_only_candidate_count"] == 2
    assert payload["over_budget_scope_count"] == 0
    assert payload["planning_actions"] == []
    assert payload["scope_breakdown"] == [
        {
            "scope_key": "seat:role-ops:seat-a",
            "target_scope": "seat",
            "target_role_id": "role-ops",
            "target_seat_ref": "seat-a",
            "donor_count": 2,
            "candidate_count": 2,
            "active_candidate_count": 1,
            "trial_candidate_count": 1,
            "source_kind_count": {
                "external_catalog": 1,
                "external_remote": 1,
            },
        },
    ]


def test_runtime_center_state_query_discovery_summary_filters_fallback_only_sources() -> None:
    class _CandidateService:
        def list_candidates(self, *, limit: int | None = None):
            return [
                SimpleNamespace(
                    donor_id="donor-external-a",
                    source_profile_id="source-external-a",
                    candidate_source_kind="external_remote",
                    ingestion_mode="prediction-recommendation",
                ),
                SimpleNamespace(
                    donor_id="donor-external-b",
                    source_profile_id="source-external-b",
                    candidate_source_kind="external_catalog",
                    ingestion_mode="prediction-recommendation",
                ),
                SimpleNamespace(
                    donor_id="donor-local",
                    source_profile_id="source-local",
                    candidate_source_kind="local_authored",
                    ingestion_mode="manual",
                ),
                SimpleNamespace(
                    donor_id="donor-baseline",
                    source_profile_id="source-baseline",
                    candidate_source_kind="external_catalog",
                    ingestion_mode="baseline-import",
                ),
            ]

    class _DonorService:
        def list_donors(self, *, limit: int | None = None):
            return []

        def list_source_profiles(self, *, limit: int | None = None):
            return [
                SimpleNamespace(
                    source_profile_id="source-external-a",
                    source_kind="external_remote",
                    trust_posture="trusted",
                    active=True,
                ),
                SimpleNamespace(
                    source_profile_id="source-external-b",
                    source_kind="external_catalog",
                    trust_posture="watchlist",
                    active=True,
                ),
                SimpleNamespace(
                    source_profile_id="source-local",
                    source_kind="local_authored",
                    trust_posture="local",
                    active=True,
                ),
                SimpleNamespace(
                    source_profile_id="source-baseline",
                    source_kind="external_catalog",
                    trust_posture="trusted",
                    active=True,
                ),
            ]

        def list_trust_records(self, *, limit: int | None = None):
            return []

    class _TrialService:
        def list_trials(self, *, candidate_id: str | None = None, limit: int | None = None):
            return []

    class _DecisionService:
        def list_decisions(self, *, candidate_id: str | None = None, limit: int | None = None):
            return []

    portfolio_service = CapabilityPortfolioService(
        donor_service=_DonorService(),
        candidate_service=_CandidateService(),
        skill_trial_service=_TrialService(),
        skill_lifecycle_decision_service=_DecisionService(),
    )

    state_query = RuntimeCenterStateQueryService(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=None,
        schedule_repository=object(),
        goal_repository=None,
        work_context_repository=None,
        decision_request_repository=object(),
        capability_candidate_service=_CandidateService(),
        capability_donor_service=_DonorService(),
        capability_portfolio_service=portfolio_service,
    )

    payload = state_query.get_capability_discovery_summary()

    assert payload["status"] == "ready"
    assert payload["source_profile_count"] == 2
    assert payload["active_source_count"] == 2
    assert payload["trusted_source_count"] == 1
    assert payload["watchlist_source_count"] == 1
    assert payload["fallback_only_source_count"] == 2
    assert payload["by_source_kind"] == {
        "external_catalog": 1,
        "external_remote": 1,
    }


def test_runtime_center_state_query_candidate_projection_exposes_provenance_history_and_reentry(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    donor_service = CapabilityDonorService(state_store=state_store)
    candidate_service = CapabilityCandidateService(
        state_store=state_store,
        donor_service=donor_service,
    )
    trial_service = SkillTrialService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="mcp-bundle",
        target_scope="seat",
        target_role_id="operator",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://browser-runtime",
        candidate_source_version="2026.04.04",
        candidate_source_lineage="donor:browser-runtime",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="browser_runtime",
        summary="Governed browser runtime candidate.",
        lifecycle_stage="trial",
        metadata={
            "resolution_kind": "reuse_existing_candidate",
            "selected_candidate_id": "cand-previous-browser-runtime",
        },
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        canonical_package_id=candidate.canonical_package_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="failed",
        success_count=0,
        failure_count=2,
        operator_intervention_count=1,
        summary="Seat-local browser runtime drifted.",
    )
    decision_service.create_decision(
        candidate_id=candidate.candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        canonical_package_id=candidate.canonical_package_id,
        decision_kind="rollback",
        from_stage="trial",
        to_stage="blocked",
        reason="Seat-local runtime drift requires rollback.",
        replacement_target_ids=["mcp:browser_runtime"],
    )

    state_query = RuntimeCenterStateQueryService(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=None,
        schedule_repository=object(),
        goal_repository=None,
        work_context_repository=None,
        decision_request_repository=object(),
        capability_candidate_service=candidate_service,
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=decision_service,
    )

    payload = state_query.list_capability_candidates(limit=5)

    assert len(payload) == 1
    assert payload[0]["supply_path"] == "healthy-reuse"
    assert payload[0]["provenance"]["candidate_kind"] == "mcp-bundle"
    assert payload[0]["provenance"]["candidate_source_kind"] == "external_catalog"
    assert payload[0]["provenance"]["candidate_source_ref"] == "registry://browser-runtime"
    assert payload[0]["provenance"]["candidate_source_version"] == "2026.04.04"
    assert payload[0]["provenance"]["candidate_source_lineage"] == "donor:browser-runtime"
    assert payload[0]["provenance"]["ingestion_mode"] == "prediction-recommendation"
    assert payload[0]["provenance"]["donor_id"] == candidate.donor_id
    assert payload[0]["provenance"]["protection_flags"] == []
    assert payload[0]["target_scope_projection"] == {
        "target_scope": "seat",
        "target_role_id": "operator",
        "target_seat_ref": "seat-primary",
    }
    assert payload[0]["lifecycle_history"]["trial_count"] == 1
    assert payload[0]["lifecycle_history"]["decision_count"] == 1
    assert payload[0]["lifecycle_history"]["latest_trial_verdict"] == "failed"
    assert payload[0]["lifecycle_history"]["latest_decision_kind"] == "rollback"
    assert payload[0]["lifecycle_history"]["history"][0]["entry_kind"] == "decision"
    assert payload[0]["lifecycle_history"]["history"][0]["decision_kind"] == "rollback"
    assert payload[0]["lifecycle_history"]["history"][1]["entry_kind"] == "trial"
    assert payload[0]["lifecycle_history"]["history"][1]["scope_ref"] == "seat-primary"
    assert payload[0]["lifecycle_history"]["trial_scopes"] == [
        {
            "scope_key": "seat:seat-primary",
            "scope_type": "seat",
            "scope_ref": "seat-primary",
            "verdict": "failed",
            "operator_intervention_count": 1,
            "success_count": 0,
            "failure_count": 2,
        },
    ]
    assert payload[0]["replacement_lineage"] == {
        "lineage_root_id": candidate.candidate_id,
        "supersedes": [],
        "superseded_by": [],
        "replacement_target_ids": ["mcp:browser_runtime"],
        "rollback_target_ids": [],
        "replacement_relation": None,
    }
    assert payload[0]["drift_reentry"]["status"] == "pressure"
    assert payload[0]["drift_reentry"]["reentry_kind"] == "replacement"
    assert payload[0]["drift_reentry"]["replacement_pressure"] is True
    assert payload[0]["drift_reentry"]["retirement_pressure"] is False
    assert payload[0]["drift_reentry"]["revision_pressure"] is False
    assert "rollback" in payload[0]["drift_reentry"]["reasons"]


def test_runtime_center_state_query_candidate_projection_exposes_adapter_assimilation_status(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "runtime-center-adapter-state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="project",
        target_scope="seat",
        target_role_id="execution-core",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://github.com/example/openspace-donor",
        candidate_source_version="main",
        candidate_source_lineage="donor:github:example/openspace-donor",
        canonical_package_id="pkg:github:example/openspace-donor",
        ingestion_mode="capability-market",
        proposed_skill_name="openspace_donor",
        summary="Governed external donor candidate.",
        metadata={
            "protocol_surface_kind": "native_mcp",
            "transport_kind": "mcp",
            "compiled_adapter_id": "adapter:openspace",
            "compiled_action_ids": ["execute_task"],
            "adapter_blockers": [],
        },
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        canonical_package_id=candidate.canonical_package_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        summary="Seat-local adapter trial completed.",
        metadata={
            "protocol_surface_kind": "native_mcp",
            "transport_kind": "mcp",
            "compiled_adapter_id": "adapter:openspace",
            "compiled_action_ids": ["execute_task"],
        },
    )

    state_query = RuntimeCenterStateQueryService(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=None,
        schedule_repository=object(),
        goal_repository=None,
        work_context_repository=None,
        decision_request_repository=object(),
        capability_candidate_service=candidate_service,
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=decision_service,
    )

    payload = state_query.list_capability_candidates(limit=5)

    assert len(payload) == 1
    assert payload[0]["protocol_surface_kind"] == "native_mcp"
    assert payload[0]["transport_kind"] == "mcp"
    assert payload[0]["compiled_adapter_id"] == "adapter:openspace"
    assert payload[0]["compiled_action_ids"] == ["execute_task"]
    assert payload[0]["promotion_blockers"] == []


def test_runtime_center_state_query_candidate_projection_exposes_baseline_protection_and_active_pack_composition(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "runtime-center-baseline-state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="mcp-bundle",
        target_scope="seat",
        target_role_id="operator",
        target_seat_ref="seat-browser",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://browser-runtime",
        candidate_source_version="2026.04.04",
        candidate_source_lineage="baseline:browser-runtime",
        ingestion_mode="baseline-import",
        proposed_skill_name="browser_runtime",
        summary="Baseline browser runtime.",
        status="active",
        lifecycle_stage="baseline",
        protection_flags=[
            "protected_from_auto_replace",
            "required_by_role_blueprint",
        ],
        metadata={"target_agent_id": "agent-browser-seat"},
    )

    class _AgentProfileService:
        def get_agent_detail(self, agent_id: str):
            assert agent_id == "agent-browser-seat"
            return {
                "runtime": {
                    "metadata": {
                        "capability_layers": {
                            "role_prototype_capability_ids": ["mcp:browser_runtime"],
                            "seat_instance_capability_ids": ["mcp:clipboard"],
                            "cycle_delta_capability_ids": ["skill:research_pack"],
                            "session_overlay_capability_ids": ["skill:browser_helper"],
                            "effective_capability_ids": [
                                "mcp:browser_runtime",
                                "mcp:clipboard",
                                "skill:research_pack",
                                "skill:browser_helper",
                            ],
                        }
                    }
                }
            }

    state_query = RuntimeCenterStateQueryService(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=None,
        schedule_repository=object(),
        goal_repository=None,
        work_context_repository=None,
        decision_request_repository=object(),
        capability_candidate_service=candidate_service,
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=decision_service,
        agent_profile_service=_AgentProfileService(),
    )

    payload = state_query.list_capability_candidates(limit=5)

    assert len(payload) == 1
    assert payload[0]["supply_path"] == "baseline-import"
    assert payload[0]["provenance"]["protection_flags"] == [
        "protected_from_auto_replace",
        "required_by_role_blueprint",
    ]
    assert payload[0]["baseline_projection"] == {
        "is_baseline_import": True,
        "is_active": True,
        "protection_flags": [
            "protected_from_auto_replace",
            "required_by_role_blueprint",
        ],
    }
    assert payload[0]["target_scope_projection"] == {
        "target_scope": "seat",
        "target_role_id": "operator",
        "target_agent_id": "agent-browser-seat",
        "target_seat_ref": "seat-browser",
    }
    assert payload[0]["active_pack_composition"] == {
        "target_scope": "seat",
        "target_role_id": "operator",
        "target_agent_id": "agent-browser-seat",
        "target_seat_ref": "seat-browser",
        "role_prototype_capability_ids": ["mcp:browser_runtime"],
        "seat_instance_capability_ids": ["mcp:clipboard"],
        "cycle_delta_capability_ids": ["skill:research_pack"],
        "session_overlay_capability_ids": ["skill:browser_helper"],
        "effective_capability_ids": [
            "mcp:browser_runtime",
            "mcp:clipboard",
            "skill:research_pack",
            "skill:browser_helper",
        ],
        "active_candidate_member": True,
    }


def test_runtime_center_capability_lifecycle_decisions_endpoint_returns_state_query_projection() -> None:
    app = _build_app()

    class FakeStateQueryService:
        def list_capability_lifecycle_decisions(
            self,
            *,
            candidate_id: str | None = None,
            limit: int | None = None,
        ):
            assert candidate_id == "cand-1"
            return [
                {
                    "decision_id": "decision-1",
                    "candidate_id": "cand-1",
                    "decision_kind": "promote_to_role",
                    "to_stage": "active",
                },
            ][: limit or 20]

    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get(
        "/runtime-center/capabilities/lifecycle-decisions",
        params={"candidate_id": "cand-1", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "decision_id": "decision-1",
            "candidate_id": "cand-1",
            "decision_kind": "promote_to_role",
            "to_stage": "active",
        },
    ]


def test_runtime_center_governance_patch_batch_rejects_empty_or_malformed_ids() -> None:
    app = _build_app()

    class _Result:
        def model_dump(self, *, mode: str = "json"):
            _ = mode
            return {"requested": 1}

    class _GovernanceService:
        def batch_patches(self, *, patch_ids, action, actor):
            _ = (patch_ids, action, actor)
            return _Result()

    app.state.governance_service = _GovernanceService()
    client = TestClient(app)

    empty_response = client.post(
        "/runtime-center/governance/patches/apply",
        json={"actor": "tester"},
    )
    malformed_response = client.post(
        "/runtime-center/governance/patches/apply",
        json={"patch_id": "patch-1", "actor": "tester"},
    )

    assert empty_response.status_code == 422
    assert malformed_response.status_code == 422


def test_runtime_center_governance_decision_batch_rejects_empty_or_malformed_ids() -> None:
    app = _build_app()

    class _Result:
        def model_dump(self, *, mode: str = "json"):
            _ = mode
            return {"requested": 1}

    class _GovernanceService:
        async def batch_decisions(self, *, decision_ids, action, actor, resolution, execute):
            _ = (decision_ids, action, actor, resolution, execute)
            return _Result()

    app.state.governance_service = _GovernanceService()
    client = TestClient(app)

    empty_response = client.post(
        "/runtime-center/governance/decisions/approve",
        json={"actor": "tester"},
    )
    malformed_response = client.post(
        "/runtime-center/governance/decisions/approve",
        json={"decision_id": "decision-1", "actor": "tester"},
    )

    assert empty_response.status_code == 422
    assert malformed_response.status_code == 422


def test_conversation_compaction_service_builds_visibility_payload() -> None:
    payload = ConversationCompactionService.build_visibility_payload(
        {
            "compaction_state": {
                "mode": "microcompact",
                "summary": "Compacted 2 oversized tool results.",
                "spill_count": 1,
                "replacement_count": 2,
            },
            "tool_result_budget": {
                "message_budget": 2400,
                "used_budget": 1800,
                "remaining_budget": 600,
            },
            "tool_use_summary": {
                "summary": "2 tool results compacted into artifact previews.",
                "artifact_refs": ["artifact://tool-result-1"],
                "result_items": [
                    {
                        "ref": "artifact://tool-result-1",
                        "kind": "file",
                        "label": "文件",
                        "summary": "执行结果文件",
                    },
                    {
                        "ref": "replay://tool-result-1",
                        "kind": "replay",
                        "label": "回放",
                    },
                    {
                        "ref": "artifact://tool-result-1",
                        "kind": "file",
                        "label": "文件",
                        "summary": "执行结果文件",
                    },
                    "drop-me",
                ],
            },
        }
    )

    assert payload["compaction_state"] == {
        "mode": "microcompact",
        "summary": "Compacted 2 oversized tool results.",
        "spill_count": 1,
        "replacement_count": 2,
    }
    assert payload["tool_result_budget"] == {
        "message_budget": 2400,
        "used_budget": 1800,
        "remaining_budget": 600,
    }
    assert payload["tool_use_summary"] == {
        "summary": "2 tool results compacted into artifact previews.",
        "artifact_refs": ["artifact://tool-result-1"],
        "result_items": [
            {
                "ref": "artifact://tool-result-1",
                "kind": "file",
                "label": "文件",
                "summary": "执行结果文件",
            },
            {
                "ref": "replay://tool-result-1",
                "kind": "replay",
                "label": "回放",
            },
        ],
    }


def test_conversation_compaction_service_derives_formal_result_items_from_concrete_refs() -> None:
    payload = ConversationCompactionService.build_visibility_payload(
        {
            "tool_use_summary": {
                "artifact_refs": [
                    "file:///tmp/report.md",
                    "replay://trace-1",
                    "file://artifacts/screenshot-1.png",
                    "artifact://tool-result-1",
                ],
            },
        }
    )

    assert payload["tool_use_summary"] == {
        "artifact_refs": [
            "file:///tmp/report.md",
            "replay://trace-1",
            "file://artifacts/screenshot-1.png",
            "artifact://tool-result-1",
        ],
        "result_items": [
            {
                "ref": "file:///tmp/report.md",
                "kind": "file",
                "label": "文件",
            },
            {
                "ref": "replay://trace-1",
                "kind": "replay",
                "label": "回放",
            },
            {
                "ref": "file://artifacts/screenshot-1.png",
                "kind": "screenshot",
                "label": "截图",
            },
        ],
    }


def test_conversation_compaction_service_preserves_formal_result_item_routes() -> None:
    payload = ConversationCompactionService.build_visibility_payload(
        {
            "tool_use_summary": {
                "artifact_refs": ["file:///tmp/report.md"],
                "result_items": [
                    {
                        "ref": "file:///tmp/report.md",
                        "kind": "file",
                        "label": "File",
                        "summary": "Saved report",
                        "route": "/api/runtime-center/artifacts/artifact-file-1",
                    }
                ],
            }
        }
    )

    assert payload["tool_use_summary"] == {
        "artifact_refs": ["file:///tmp/report.md"],
        "result_items": [
            {
                "ref": "file:///tmp/report.md",
                "kind": "file",
                "label": "File",
                "summary": "Saved report",
                "route": "/api/runtime-center/artifacts/artifact-file-1",
            }
        ],
    }
