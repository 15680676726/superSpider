from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from .runtime_center_api_parts.shared import (
    FakeAgentProfileService,
    FakeCapabilityService,
    FakeEvidenceQueryService,
    FakeGovernanceService,
    FakeIndustryService,
    FakeLearningService,
    FakeRoutineService,
    FakeStateQueryService,
    build_runtime_center_app,
)


class _LegacyAgentProfileService(FakeAgentProfileService):
    def list_agents(
        self,
        limit: int | None = 5,
        industry_instance_id: str | None = None,
    ):
        return super().list_agents(
            limit=limit,
            view="all",
            industry_instance_id=industry_instance_id,
        )


def test_runtime_center_human_cockpit_excludes_platform_control_agents_when_service_lacks_view_kwarg() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = _LegacyAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = SimpleNamespace(
        list_strategies=lambda limit=5: [
            {
                "id": "strategy-generic",
                "title": "Generic operator strategy",
                "status": "active",
                "summary": "Keep the system moving.",
                "updated_at": "2026-03-09T08:00:00+00:00",
            },
        ]
    )

    client = TestClient(app)
    response = client.get("/runtime-center/surface?sections=main_brain")

    assert response.status_code == 200
    cockpit = response.json()["main_brain"]["cockpit"]
    assert [item["agent_id"] for item in cockpit["agents"]] == ["ops-agent"]
