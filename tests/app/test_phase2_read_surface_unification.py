# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers import router as root_router
from copaw.kernel.agent_profile import AgentProfile
from copaw.learning.surface_reward_service import SurfaceRewardService
from copaw.state import (
    AssignmentRecord,
    IndustryInstanceRecord,
    OperatingLaneRecord,
    SQLiteStateStore,
    StrategyMemoryRecord,
)
from copaw.state.models_surface_learning import SurfaceCapabilityTwinRecord, SurfacePlaybookRecord
from copaw.state.repositories import (
    SqliteAssignmentRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingLaneRepository,
    SqliteStrategyMemoryRepository,
    SqliteSurfaceCapabilityTwinRepository,
    SqliteSurfacePlaybookRepository,
)


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(root_router)
    return app


def test_legacy_skill_and_mcp_routes_are_removed_from_runtime_surface() -> None:
    client = TestClient(build_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/skills" not in paths
    assert "/skills/available" not in paths
    assert "/mcp" not in paths
    assert "/mcp/{client_key}" not in paths


def test_legacy_skill_and_mcp_routes_return_404() -> None:
    client = TestClient(build_app())

    assert client.get("/skills").status_code == 404
    assert client.get("/skills/available").status_code == 404
    assert client.get("/mcp").status_code == 404
    assert client.get("/mcp/browser").status_code == 404


def test_retired_runtime_and_goal_frontdoors_are_removed_from_openapi() -> None:
    client = TestClient(build_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/runtime-center/chat/intake" not in paths
    assert "/runtime-center/chat/orchestrate" not in paths
    assert "/runtime-center/tasks/{task_id}/delegate" not in paths
    assert "/runtime-center/goals/{goal_id}" not in paths
    assert "/runtime-center/goals/{goal_id}/compile" not in paths
    assert "/runtime-center/goals/{goal_id}/dispatch" not in paths
    assert "/goals" not in paths
    assert "/goals/{goal_id}" not in paths
    assert "/goals/{goal_id}/compile" not in paths
    assert "/goals/{goal_id}/dispatch" not in paths
    assert "/goals/automation/dispatch-active" not in paths
    assert "/goals/{goal_id}/detail" in paths
    assert "/workflow-templates" not in paths
    assert "/workflow-templates/{template_id}" not in paths
    assert "/workflow-templates/{template_id}/preview" not in paths
    assert "/workflow-templates/{template_id}/presets" not in paths
    assert "/workflow-runs" not in paths
    assert "/workflow-runs/{run_id}" not in paths
    assert "/workflow-runs/{run_id}/cancel" not in paths
    assert "/workflow-runs/{run_id}/steps/{step_id}" not in paths
    assert "/learning/patches/{patch_id}/approve" not in paths
    assert "/learning/patches/{patch_id}/reject" not in paths
    assert "/learning/patches/{patch_id}/apply" not in paths
    assert "/learning/patches/{patch_id}/rollback" not in paths
    assert "/models/{provider_id}/config" not in paths
    assert "/models/custom-providers" not in paths
    assert "/models/custom-providers/{provider_id}" not in paths
    assert "/models/{provider_id}/models" not in paths
    assert "/models/{provider_id}/models/{model_id}" not in paths
    assert "/local-models/download" not in paths
    assert "/local-models/cancel-download/{task_id}" not in paths
    assert "/local-models/{model_id}" not in paths
    assert "/ollama-models/download" not in paths
    assert "/ollama-models/download/{task_id}" not in paths
    assert "/ollama-models/{name}" not in paths
    assert set(paths["/models/active"].keys()) == {"get"}
    assert set(paths["/models/fallback"].keys()) == {"get"}
    assert "/providers/admin/{provider_id}/config" in paths
    assert "/providers/admin/active" in paths
    assert "/providers/admin/fallback" in paths
    assert "/providers/admin/local-models/download" in paths
    assert "/providers/admin/local-models/cancel-download/{task_id}" in paths
    assert "/providers/admin/local-models/{model_id}" in paths
    assert "/providers/admin/ollama-models/download" in paths
    assert "/providers/admin/ollama-models/download/{task_id}" in paths
    assert "/providers/admin/ollama-models/{name}" in paths


def test_retired_runtime_and_goal_frontdoors_return_404() -> None:
    client = TestClient(build_app())

    assert client.post("/runtime-center/chat/intake", json={"id": "req-intake"}).status_code == 404
    assert (
        client.post("/runtime-center/chat/orchestrate", json={"id": "req-orchestrate"}).status_code
        == 404
    )
    assert (
        client.post(
            "/runtime-center/tasks/task-1/delegate",
            json={
                "title": "Worker follow-up",
                "owner_agent_id": "worker",
                "prompt_text": "Review the evidence and draft the next step.",
            },
        ).status_code
        == 404
    )
    assert (
        client.get("/runtime-center/goals/goal-1").status_code
        == 404
    )
    assert (
        client.post(
            "/runtime-center/goals/goal-1/compile",
            json={"context": {"source": "runtime-center"}},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/runtime-center/goals/goal-1/dispatch",
            json={"trigger": "manual", "source": "runtime-center"},
        ).status_code
        == 404
    )
    assert client.get("/goals").status_code == 404
    assert client.post("/goals", json={"title": "Retired frontdoor"}).status_code == 404
    assert client.get("/goals/goal-1").status_code == 404
    assert client.patch("/goals/goal-1", json={"title": "Retired frontdoor"}).status_code == 404
    assert client.delete("/goals/goal-1").status_code == 404
    assert client.post("/goals/goal-1/compile", json={"context": {"source": "legacy"}}).status_code == 404
    assert client.get("/goals/goal-1/detail").status_code == 503
    assert client.post("/goals/goal-1/dispatch", json={"trigger": "manual"}).status_code == 404
    assert client.post("/goals/automation/dispatch-active", json={"source": "runtime-center"}).status_code == 404
    assert client.get("/workflow-templates").status_code == 404
    assert client.get("/workflow-templates/template-1").status_code == 404
    assert client.post(
        "/workflow-templates/template-1/preview",
        json={"goal_id": "goal-1"},
    ).status_code == 404
    assert client.get("/workflow-runs").status_code == 404
    assert client.get("/workflow-runs/run-1").status_code == 404
    assert client.post(
        "/workflow-runs/run-1/cancel",
        json={"actor": "ops", "reason": "retired"},
    ).status_code == 404
    assert client.put("/models/active", json={"provider_id": "openai", "model": "gpt-5"}).status_code == 405
    assert client.put(
        "/models/fallback",
        json={"enabled": True, "candidates": []},
    ).status_code == 405
    assert client.put(
        "/models/openai/config",
        json={"api_key": "sk-test"},
    ).status_code == 404
    assert client.post(
        "/local-models/download",
        json={"repo_id": "Qwen/Qwen", "backend": "llamacpp", "source": "huggingface"},
    ).status_code == 404
    assert client.post("/local-models/cancel-download/task-1").status_code == 404
    assert client.delete("/local-models/runtime-only").status_code == 404
    assert client.post("/ollama-models/download", json={"name": "qwen3:latest"}).status_code == 404
    assert client.delete("/ollama-models/download/task-1").status_code == 404
    assert client.delete("/ollama-models/qwen3:latest").status_code == 404
    assert client.post(
        "/models/custom-providers",
        json={"id": "custom", "name": "Custom"},
    ).status_code == 404
    assert client.post("/learning/patches/patch-1/approve", json={"actor": "ops"}).status_code == 404
    assert client.post("/learning/patches/patch-1/reject", json={"actor": "ops"}).status_code == 404
    assert client.post("/learning/patches/patch-1/apply", json={"actor": "ops"}).status_code == 404
    assert client.post("/learning/patches/patch-1/rollback", json={"actor": "ops"}).status_code == 404


def test_goal_detail_stays_the_only_public_goals_frontdoor_method() -> None:
    client = TestClient(build_app())

    openapi_response = client.get("/openapi.json")

    assert openapi_response.status_code == 200
    detail_methods = openapi_response.json()["paths"]["/goals/{goal_id}/detail"].keys()
    assert set(detail_methods) == {"get"}

    assert client.get("/goals/goal-1/detail").status_code == 503
    assert client.post("/goals/goal-1/detail", json={"title": "forbidden"}).status_code == 405
    assert client.patch("/goals/goal-1/detail", json={"title": "forbidden"}).status_code == 405
    assert client.delete("/goals/goal-1/detail").status_code == 405


def test_surface_reward_ranking_prefers_formal_goal_context_over_playbook_order(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "surface-reward.db")
    twin_repository = SqliteSurfaceCapabilityTwinRepository(state_store)
    playbook_repository = SqliteSurfacePlaybookRepository(state_store)
    strategy_repository = SqliteStrategyMemoryRepository(state_store)
    industry_instance_repository = SqliteIndustryInstanceRepository(state_store)
    operating_lane_repository = SqliteOperatingLaneRepository(state_store)
    assignment_repository = SqliteAssignmentRepository(state_store)
    industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-surface",
            label="Surface reward industry",
            summary="Reward ranking test",
            owner_scope="industry-surface-owner",
            status="running",
        ),
    )
    strategy_repository.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:reward",
            scope_type="industry",
            scope_id="industry-surface",
            industry_instance_id="industry-surface",
            title="Revenue strategy",
            mission="Publish revenue-generating listings first.",
            current_focuses=["publish listing"],
            priority_order=["publish listing", "improve conversion"],
            evidence_requirements=["published confirmation"],
        ),
    )
    operating_lane_repository.upsert_lane(
        OperatingLaneRecord(
            id="lane:publishing",
            industry_instance_id="industry-surface",
            lane_key="publishing",
            title="Publishing lane",
            summary="Push approved listings live.",
            owner_agent_id="agent:publisher",
            metadata={"evidence_expectations": ["published confirmation"]},
        ),
    )
    assignment_repository.upsert_assignment(
        AssignmentRecord(
            id="assignment:reward",
            industry_instance_id="industry-surface",
            lane_id="lane:publishing",
            owner_agent_id="agent:publisher",
            title="Publish the highest-priority listing",
            summary="Do not waste time on archive actions.",
            metadata={"success_criteria": ["published confirmation"]},
        ),
    )
    twin_repository.upsert(
        SurfaceCapabilityTwinRecord(
            twin_id="twin:archive",
            scope_level="work_context",
            scope_id="work-surface-1",
            capability_name="archive_listing",
            capability_kind="action",
            surface_kind="browser",
            summary="Archive a listing.",
            execution_steps=["open archive dialog", "confirm archive"],
            result_signals=["archived confirmation"],
            version=1,
            status="active",
        ),
    )
    twin_repository.upsert(
        SurfaceCapabilityTwinRecord(
            twin_id="twin:publish",
            scope_level="work_context",
            scope_id="work-surface-1",
            capability_name="publish_listing",
            capability_kind="action",
            surface_kind="browser",
            summary="Publish a listing.",
            execution_steps=["open publish dialog", "confirm publish"],
            result_signals=["published confirmation"],
            version=1,
            status="active",
        ),
    )
    playbook_repository.upsert(
        SurfacePlaybookRecord(
            playbook_id="playbook:1",
            scope_level="work_context",
            scope_id="work-surface-1",
            twin_id="twin:archive",
            summary="Current surface actions",
            capability_names=["archive_listing", "publish_listing"],
            recommended_steps=["archive first", "publish second"],
            execution_steps=["archive", "publish"],
            success_signals=["published confirmation"],
            version=1,
            status="active",
        ),
    )
    reward_service = SurfaceRewardService(
        surface_capability_twin_repository=twin_repository,
        surface_playbook_repository=playbook_repository,
        strategy_memory_repository=strategy_repository,
        operating_lane_repository=operating_lane_repository,
        assignment_repository=assignment_repository,
        agent_profile_service=type(
            "_AgentProfileService",
            (),
            {
                "get_agent": staticmethod(
                    lambda agent_id: AgentProfile(
                        agent_id=str(agent_id),
                        name="Publisher",
                        role_name="Publisher",
                        role_summary="Ships live listings.",
                        mission="Publish listings and verify they are live.",
                        evidence_expectations=["published confirmation"],
                    )
                )
            },
        )(),
    )

    projection = reward_service.refresh_reward_ranking(
        scope_level="work_context",
        scope_id="work-surface-1",
        industry_instance_id="industry-surface",
        lane_id="lane:publishing",
        assignment_id="assignment:reward",
        owner_agent_id="agent:publisher",
    )

    assert [item.capability_name for item in projection.ranking[:2]] == [
        "publish_listing",
        "archive_listing",
    ]
    assert projection.ranking[0].score > projection.ranking[1].score
