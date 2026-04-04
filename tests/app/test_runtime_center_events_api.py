# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from copaw.app.runtime_events import RuntimeEventBus
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.startup_recovery import StartupRecoverySummary
from copaw.memory.conversation_compaction_service import ConversationCompactionService


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
    }
