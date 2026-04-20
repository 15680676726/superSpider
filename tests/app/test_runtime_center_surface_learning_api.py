# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router


class _FakeStateQueryService:
    def get_surface_learning_scope(
        self,
        *,
        scope_type: str,
        scope_id: str,
        task_id: str | None = None,
        work_context_id: str | None = None,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        owner_agent_id: str | None = None,
        limit: int = 3,
    ) -> dict[str, object] | None:
        _ = (
            task_id,
            work_context_id,
            agent_id,
            industry_instance_id,
            owner_agent_id,
            limit,
        )
        if scope_type != "work_context" or scope_id != "work-surface-1":
            return None
        return {
            "scope_type": "work_context",
            "scope_id": "work-surface-1",
            "scope_level": "work_context",
            "version": 4,
            "updated_at": "2026-04-20T10:00:00+00:00",
            "live_graph": {
                "surface_kind": "browser",
                "confidence": 0.92,
                "control_count": 4,
                "result_count": 1,
                "blocker_count": 0,
            },
            "latest_evidence": [
                {
                    "id": "evidence:surface-transition:1",
                    "kind": "surface-transition",
                    "action_summary": "publish listing",
                    "result_summary": "listing moved into published state",
                }
            ],
            "active_twins": [
                {
                    "twin_id": "twin:publish",
                    "capability_name": "publish_listing",
                    "summary": "Publish the current listing.",
                    "surface_kind": "browser",
                    "version": 4,
                }
            ],
            "active_playbook": {
                "playbook_id": "playbook:publish",
                "summary": "Publish the listing and verify the result.",
                "capability_names": ["publish_listing"],
                "recommended_steps": ["Open publish dialog", "Confirm publish"],
                "success_signals": ["published confirmation"],
                "version": 4,
            },
            "reward_ranking": [
                {
                    "capability_name": "publish_listing",
                    "score": 18.0,
                    "reasons": ["assignment+12.0", "strategy+6.0"],
                }
            ],
        }


def _build_client() -> TestClient:
    app = FastAPI()
    app.state.state_query_service = _FakeStateQueryService()
    app.include_router(runtime_center_router)
    return TestClient(app)


def test_runtime_center_knowledge_surface_api_returns_aggregated_surface_learning_payload() -> None:
    client = _build_client()

    response = client.get(
        "/runtime-center/knowledge/surface",
        params={"scope_type": "work_context", "scope_id": "work-surface-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["live_graph"]["surface_kind"] == "browser"
    assert payload["latest_evidence"][0]["kind"] == "surface-transition"
    assert payload["active_playbook"]["capability_names"] == ["publish_listing"]
    assert payload["reward_ranking"][0]["capability_name"] == "publish_listing"


def test_runtime_center_memory_surface_api_includes_surface_learning_summary() -> None:
    client = _build_client()

    response = client.get(
        "/runtime-center/memory/surface",
        params={"scope_type": "work_context", "scope_id": "work-surface-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface_learning"]["scope_level"] == "work_context"
    assert payload["surface_learning"]["active_playbook"]["capability_names"] == [
        "publish_listing"
    ]
