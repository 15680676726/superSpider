# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.learning import router as learning_router
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.capabilities import CapabilityService
from copaw.capabilities.install_templates import InstallTemplateExampleRunRecord
from copaw.config.config import MCPClientConfig
from copaw.evidence import EvidenceLedger
from copaw.industry import (
    IndustryBootstrapInstallResult,
    IndustryProfile,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
)
from copaw.kernel import KernelDispatcher, KernelTaskStore
from copaw.learning import LearningEngine, LearningService, PatchExecutor
from copaw.learning.runtime_bindings import LearningRuntimeBindings
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteAgentProfileOverrideRepository,
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def _build_learning_app(tmp_path) -> FastAPI:
    app = FastAPI()
    app.include_router(learning_router)
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    agent_profile_override_repository = SqliteAgentProfileOverrideRepository(state_store)
    goal_override_repository = SqliteGoalOverrideRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")

    learning_service = LearningService(
        engine=LearningEngine(tmp_path / "learning.db"),
        patch_executor=PatchExecutor(
            agent_profile_override_repository=agent_profile_override_repository,
            goal_override_repository=goal_override_repository,
        ),
        decision_request_repository=decision_request_repository,
        task_repository=task_repository,
        evidence_ledger=evidence_ledger,
    )
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
    )
    kernel_dispatcher = KernelDispatcher(
        task_store=KernelTaskStore(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            decision_request_repository=decision_request_repository,
            evidence_ledger=evidence_ledger,
        ),
        capability_service=capability_service,
    )
    learning_service.set_kernel_dispatcher(kernel_dispatcher)
    app.state.learning_service = learning_service
    app.state.learning_engine = learning_service.engine
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = kernel_dispatcher
    app.state.agent_profile_override_repository = agent_profile_override_repository
    app.state.goal_override_repository = goal_override_repository
    app.state.decision_request_repository = decision_request_repository
    app.state.task_repository = task_repository
    app.state.task_runtime_repository = task_runtime_repository
    app.state.evidence_ledger = evidence_ledger
    return app


class _FakeDiscoveryService:
    async def discover(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "success": True,
            "recommendations": [
                {
                    "recommendation_id": "browser-local:browser-local-default",
                    "install_kind": "builtin-runtime",
                    "template_id": "browser-local",
                    "title": "Local browser runtime",
                    "description": "Provision the governed browser runtime.",
                    "default_client_key": "browser-local-default",
                    "capability_ids": [],
                    "target_agent_ids": ["industry-solution-lead-demo"],
                    "match_signals": ["browser workflow", "form submission"],
                },
            ],
            "sop_templates": [],
            "warnings": [],
        }


class _FakeCapabilityService:
    def __init__(self) -> None:
        self._discovery_service = _FakeDiscoveryService()

    def get_discovery_service(self) -> _FakeDiscoveryService:
        return self._discovery_service


class _FakeIndustryService:
    async def build_acquisition_context_for_instance(
        self,
        instance_id: str,
    ) -> dict[str, object]:
        team = IndustryTeamBlueprint(
            team_id=instance_id,
            label="Northwind Demo Team",
            summary="Demo team for acquisition API tests.",
            agents=[
                IndustryRoleBlueprint(
                    role_id="solution-lead",
                    agent_id="industry-solution-lead-demo",
                    name="Northwind Solution Lead",
                    role_name="Solution Lead",
                    role_summary="Owns browser configuration and delivery setup.",
                    mission="Use the governed browser runtime to complete onboarding work.",
                    goal_kind="solution",
                    agent_class="business",
                    risk_level="guarded",
                    allowed_capabilities=[],
                    evidence_expectations=["onboarding summary"],
                ),
            ],
        )
        return {
            "profile": IndustryProfile(
                industry="Customer Operations",
                company_name="Northwind Robotics",
                product="Browser onboarding workflows",
                goals=["Launch the first governed browser workflow"],
            ),
            "team": team,
            "owner_scope": instance_id,
            "goal_context_by_agent": {
                "industry-solution-lead-demo": [
                    "Open the target site and sign in.",
                    "Complete the form and verify the result.",
                ],
            },
        }

    async def execute_install_plan_for_instance(
        self,
        instance_id: str,
        install_plan: list[object],
    ) -> list[IndustryBootstrapInstallResult]:
        item = install_plan[0]
        return [
            IndustryBootstrapInstallResult(
                install_kind="builtin-runtime",
                template_id=str(getattr(item, "template_id", "") or "browser-local"),
                client_key=str(
                    getattr(item, "client_key", "") or "browser-local-default",
                ),
                capability_ids=[],
                status="installed",
                detail=f"Installed browser runtime for {instance_id}.",
                installed=True,
            ),
        ]


def test_learning_service_mcp_onboarding_runs_live_trial(monkeypatch, tmp_path) -> None:
    class _FakeTrialMcpClient:
        async def list_tools(self):
            return {
                "tools": [
                    {
                        "name": "ping",
                        "inputSchema": {"type": "object", "properties": {}, "required": []},
                    },
                ],
            }

        async def get_callable_function(
            self,
            tool_name: str,
            wrap_tool_result: bool = True,
            execution_timeout: float | None = None,
        ):
            assert tool_name == "ping"
            assert wrap_tool_result is True
            assert execution_timeout == 15.0

            async def _callable(**tool_args):
                assert tool_args == {}
                return {
                    "success": True,
                    "summary": "Ping ok",
                    "payload": {"ok": True},
                }

            return _callable

    class _FakeTempMcpManager:
        def __init__(self) -> None:
            self._client = _FakeTrialMcpClient()
            self.replace_calls: list[tuple[str, MCPClientConfig, float]] = []
            self.closed = False

        async def get_client(self, key: str):
            return self._client if key == "io_github_example_filesystem" else None

        async def replace_client(
            self,
            key: str,
            client_config: MCPClientConfig,
            timeout: float = 60.0,
        ) -> None:
            self.replace_calls.append((key, client_config, timeout))

        async def close_all(self) -> None:
            self.closed = True

    config = SimpleNamespace(
        mcp=SimpleNamespace(
            clients={
                "io_github_example_filesystem": MCPClientConfig(
                    name="Filesystem MCP",
                    enabled=True,
                    transport="stdio",
                    command="npx",
                    args=["-y", "@scope/filesystem@1.0.0"],
                    env={},
                ),
            },
        ),
    )
    temp_manager = _FakeTempMcpManager()
    monkeypatch.setattr("copaw.learning.runtime_core.load_config", lambda: config)
    monkeypatch.setattr(
        "copaw.app.mcp.manager.MCPClientManager",
        lambda: temp_manager,
    )

    app = _build_learning_app(tmp_path)
    learning_service = app.state.learning_service
    learning_service.set_capability_service(SimpleNamespace(_mcp_manager=None))

    result = asyncio.run(
        learning_service._run_capability_trial_check(
            capability_id="mcp:io_github_example_filesystem",
            plan=SimpleNamespace(id="plan-demo"),
            proposal=SimpleNamespace(id="proposal-demo"),
        ),
    )

    assert result["status"] == "pass"
    assert result["detail"] == "ping"
    assert result["message"] == "Ping ok"
    assert result["metadata"]["tool_count"] == 1
    assert result["metadata"]["trial_tool_name"] == "ping"
    assert temp_manager.replace_calls
    assert temp_manager.closed is True


def test_learning_service_configure_bindings_sets_runtime_collaborators(tmp_path) -> None:
    app = _build_learning_app(tmp_path)
    service = app.state.learning_service
    industry_service = object()
    capability_service = object()
    kernel_dispatcher = object()
    fixed_sop_service = object()
    agent_profile_service = object()
    experience_memory_service = object()

    service.configure_bindings(
        LearningRuntimeBindings(
            industry_service=industry_service,
            capability_service=capability_service,
            kernel_dispatcher=kernel_dispatcher,
            fixed_sop_service=fixed_sop_service,
            agent_profile_service=agent_profile_service,
            experience_memory_service=experience_memory_service,
        ),
    )

    assert service._industry_service is industry_service
    assert service._capability_service is capability_service
    assert service._kernel_dispatcher is kernel_dispatcher
    assert service._fixed_sop_service is fixed_sop_service
    assert service._agent_profile_service is agent_profile_service
    assert service._experience_memory_service is experience_memory_service


def test_learning_api_patch_lifecycle_and_runtime_center_reads(tmp_path) -> None:
    app = _build_learning_app(tmp_path)
    client = TestClient(app)

    created_proposal = client.post(
        "/learning/proposals",
        json={
            "title": "Improve goal detail visibility",
            "description": "Expose the missing goal-task-patch-growth bindings.",
            "source_agent_id": "copaw-agent-runner",
            "target_layer": "learning",
        },
    )
    assert created_proposal.status_code == 200
    proposal_id = created_proposal.json()["id"]

    runtime_proposals = client.get("/runtime-center/learning/proposals")
    assert runtime_proposals.status_code == 200
    assert any(item["id"] == proposal_id for item in runtime_proposals.json())

    created_patch = client.post(
        "/learning/patches",
        json={
            "kind": "plan_patch",
            "title": "Refine goal plan",
            "description": "Persist explicit plan steps for goal detail.",
            "proposal_id": proposal_id,
            "diff_summary": "goal_id=goal-detail;plan_steps=Inspect gap|Publish detail",
            "risk_level": "confirm",
        },
    )
    assert created_patch.status_code == 200
    created_patch_payload = created_patch.json()
    patch_id = created_patch_payload["patch"]["id"]
    assert created_patch_payload["decision_request"] is not None

    apply_before_approve = client.post(
        f"/runtime-center/learning/patches/{patch_id}/apply",
        json={"actor": "reviewer"},
    )
    assert apply_before_approve.status_code == 400

    approved = client.post(
        f"/runtime-center/learning/patches/{patch_id}/approve",
        json={"actor": "reviewer"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    applied = client.post(
        f"/runtime-center/learning/patches/{patch_id}/apply",
        json={"actor": "reviewer"},
    )
    assert applied.status_code == 200
    applied_payload = applied.json()
    assert applied_payload["applied"] is False
    assert applied_payload["result"]["phase"] == "waiting-confirm"
    decision_id = applied_payload["result"]["decision_request_id"]
    assert decision_id

    approved_apply = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Apply the approved patch.", "execute": True},
    )
    assert approved_apply.status_code == 200
    assert approved_apply.json()["phase"] == "completed"
    assert approved_apply.json()["decision_request_id"] == decision_id

    goal_override = app.state.goal_override_repository.get_override("goal-detail")
    assert goal_override is not None
    assert goal_override.plan_steps == ["Inspect gap", "Publish detail"]

    runtime_patches = client.get("/runtime-center/learning/patches")
    assert runtime_patches.status_code == 200
    assert any(item["id"] == patch_id for item in runtime_patches.json())

    runtime_growth = client.get("/runtime-center/learning/growth")
    assert runtime_growth.status_code == 200
    assert any(item["source_patch_id"] == patch_id for item in runtime_growth.json())

    rolled_back = client.post(
        f"/runtime-center/learning/patches/{patch_id}/rollback",
        json={"actor": "reviewer"},
    )
    assert rolled_back.status_code == 200
    rolled_back_payload = rolled_back.json()
    assert rolled_back_payload["rolled_back"] is False
    assert rolled_back_payload["result"]["phase"] == "waiting-confirm"
    rollback_decision_id = rolled_back_payload["result"]["decision_request_id"]
    assert rollback_decision_id

    approved_rollback = client.post(
        f"/runtime-center/decisions/{rollback_decision_id}/approve",
        json={"resolution": "Rollback the applied patch.", "execute": True},
    )
    assert approved_rollback.status_code == 200
    assert approved_rollback.json()["phase"] == "completed"
    assert approved_rollback.json()["decision_request_id"] == rollback_decision_id
    assert app.state.goal_override_repository.get_override("goal-detail") is None


def test_runtime_center_patch_action_routes_enter_governed_mutation_flow(tmp_path) -> None:
    app = _build_learning_app(tmp_path)
    client = TestClient(app)

    created_patch = client.post(
        "/learning/patches",
        json={
            "kind": "plan_patch",
            "title": "Runtime center patch flow",
            "description": "Exercise runtime-center patch action routes.",
            "diff_summary": "goal_id=goal-runtime;plan_steps=Review|Apply",
            "risk_level": "confirm",
        },
    )
    assert created_patch.status_code == 200
    patch_id = created_patch.json()["patch"]["id"]

    approve_response = client.post(
        f"/runtime-center/learning/patches/{patch_id}/approve",
        json={"actor": "runtime-reviewer"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    apply_response = client.post(
        f"/runtime-center/learning/patches/{patch_id}/apply",
        json={"actor": "runtime-reviewer"},
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert apply_payload["applied"] is False
    assert apply_payload["result"]["phase"] == "waiting-confirm"
    apply_decision_id = apply_payload["result"]["decision_request_id"]
    assert apply_decision_id

    apply_approval = client.post(
        f"/runtime-center/decisions/{apply_decision_id}/approve",
        json={"resolution": "Apply through governance.", "execute": True},
    )
    assert apply_approval.status_code == 200
    assert apply_approval.json()["phase"] == "completed"
    assert apply_approval.json()["decision_request_id"] == apply_decision_id

    rollback_response = client.post(
        f"/runtime-center/learning/patches/{patch_id}/rollback",
        json={"actor": "runtime-reviewer"},
    )
    assert rollback_response.status_code == 200
    rollback_payload = rollback_response.json()
    assert rollback_payload["rolled_back"] is False
    assert rollback_payload["result"]["phase"] == "waiting-confirm"
    rollback_decision_id = rollback_payload["result"]["decision_request_id"]
    assert rollback_decision_id

    rollback_approval = client.post(
        f"/runtime-center/decisions/{rollback_decision_id}/approve",
        json={"resolution": "Rollback through governance.", "execute": True},
    )
    assert rollback_approval.status_code == 200
    assert rollback_approval.json()["phase"] == "completed"
    assert rollback_approval.json()["decision_request_id"] == rollback_decision_id


def test_legacy_learning_patch_action_write_routes_are_retired(tmp_path) -> None:
    app = _build_learning_app(tmp_path)
    client = TestClient(app)

    created_patch = client.post(
        "/learning/patches",
        json={
            "kind": "plan_patch",
            "title": "Retired patch route",
            "description": "Legacy /learning patch action routes should be removed.",
            "diff_summary": "goal_id=goal-retired;plan_steps=Inspect|Apply",
            "risk_level": "confirm",
        },
    )
    assert created_patch.status_code == 200
    patch_id = created_patch.json()["patch"]["id"]

    for path in (
        f"/learning/patches/{patch_id}/approve",
        f"/learning/patches/{patch_id}/reject",
        f"/learning/patches/{patch_id}/apply",
        f"/learning/patches/{patch_id}/rollback",
    ):
        response = client.post(path, json={"actor": "runtime-reviewer"})
        assert response.status_code == 404


def test_learning_api_auto_patch_defaults_to_main_brain_approval(tmp_path) -> None:
    app = _build_learning_app(tmp_path)
    client = TestClient(app)

    created_patch = client.post(
        "/learning/patches",
        json={
            "kind": "plan_patch",
            "title": "Auto-approved patch",
            "description": "Low-risk patch should be adjudicated by the main brain.",
            "diff_summary": "goal_id=goal-auto;plan_steps=Inspect|Ship",
            "risk_level": "guarded",
        },
    )
    assert created_patch.status_code == 200
    payload = created_patch.json()
    patch_id = payload["patch"]["id"]
    assert payload["decision_request"] is None
    assert payload["patch"]["status"] == "approved"

    decisions = app.state.learning_service._decision_repo.list_decision_requests(
        task_id=patch_id,
    )
    assert len(decisions) == 1
    assert decisions[0].status == "approved"
    assert decisions[0].requested_by == "copaw-main-brain"

    runtime_patches = client.get(
        "/runtime-center/learning/patches",
        params={"status": "approved"},
    )
    assert runtime_patches.status_code == 200
    assert any(item["id"] == patch_id for item in runtime_patches.json())


def test_runtime_center_learning_lists_respect_limit(tmp_path) -> None:
    app = _build_learning_app(tmp_path)
    client = TestClient(app)

    for index in range(3):
        proposal = client.post(
            "/learning/proposals",
            json={
                "title": f"Proposal {index}",
                "description": "Limit test",
                "source_agent_id": "copaw-agent-runner",
                "target_layer": "learning",
            },
        )
        assert proposal.status_code == 200

        patch = client.post(
            "/learning/patches",
            json={
                "kind": "plan_patch",
                "title": f"Patch {index}",
                "description": "Limit test",
                "diff_summary": f"goal_id=goal-{index};plan_steps=Inspect|Apply",
                "risk_level": "guarded",
            },
        )
        assert patch.status_code == 200

    proposal_response = client.get(
        "/runtime-center/learning/proposals",
        params={"limit": 2},
    )
    assert proposal_response.status_code == 200
    assert len(proposal_response.json()) == 2

    patch_response = client.get(
        "/runtime-center/learning/patches",
        params={"limit": 2},
    )
    assert patch_response.status_code == 200
    assert len(patch_response.json()) == 2


def test_learning_api_acquisition_run_and_detail_routes(tmp_path, monkeypatch) -> None:
    async def _fake_example_run(*args, **kwargs):
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="success",
            started_at="2026-03-22T00:00:00Z",
            finished_at="2026-03-22T00:00:01Z",
            summary="Browser runtime smoke completed",
            operations=["start", "stop"],
        )

    monkeypatch.setattr(
        "copaw.capabilities.install_templates.run_install_template_example",
        _fake_example_run,
    )
    app = _build_learning_app(tmp_path)
    app.state.learning_service.set_industry_service(_FakeIndustryService())
    app.state.learning_service.set_capability_service(_FakeCapabilityService())
    app.state.learning_service.set_agent_profile_service(
        SimpleNamespace(
            get_capability_surface=lambda agent_id: {
                "effective_capabilities": [],
            },
        ),
    )
    client = TestClient(app)

    run_response = client.post(
        "/learning/acquisition/run",
        json={"industry_instance_id": "industry-v1-demo"},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["success"] is True
    assert payload["proposals_processed"] == 1
    assert payload["plans_materialized"] == 1
    assert payload["onboarding_passed"] == 1
    assert payload["pending_approvals"] == 0

    proposal_id = payload["proposals"][0]["id"]
    plan_id = payload["plans"][0]["id"]
    onboarding_id = payload["onboarding_runs"][0]["id"]
    decisions = app.state.learning_service._decision_repo.list_decision_requests(
        task_id=proposal_id,
    )
    assert len(decisions) == 1
    assert decisions[0].status == "approved"
    assert decisions[0].requested_by == "copaw-main-brain"

    proposal_list = client.get(
        "/learning/acquisition/proposals",
        params={"industry_instance_id": "industry-v1-demo"},
    )
    assert proposal_list.status_code == 200
    assert [item["id"] for item in proposal_list.json()] == [proposal_id]

    proposal_detail = client.get(f"/learning/acquisition/proposals/{proposal_id}")
    assert proposal_detail.status_code == 200
    assert proposal_detail.json()["status"] == "applied"

    plan_list = client.get(
        "/learning/acquisition/plans",
        params={"industry_instance_id": "industry-v1-demo"},
    )
    assert plan_list.status_code == 200
    assert [item["id"] for item in plan_list.json()] == [plan_id]

    plan_detail = client.get(f"/learning/acquisition/plans/{plan_id}")
    assert plan_detail.status_code == 200
    assert plan_detail.json()["status"] == "applied"

    onboarding_list = client.get(
        "/learning/acquisition/onboarding-runs",
        params={"industry_instance_id": "industry-v1-demo"},
    )
    assert onboarding_list.status_code == 200
    assert [item["id"] for item in onboarding_list.json()] == [onboarding_id]

    onboarding_detail = client.get(
        f"/learning/acquisition/onboarding-runs/{onboarding_id}",
    )
    assert onboarding_detail.status_code == 200
    onboarding_payload = onboarding_detail.json()
    assert onboarding_payload["status"] == "passed"
    assert any(
        item["key"] == "trial-run:browser-local" and item["status"] == "pass"
        for item in onboarding_payload["checks"]
    )


def test_learning_api_acquisition_review_gate_approves_and_materializes(
    tmp_path,
    monkeypatch,
) -> None:
    async def _fake_example_run(*args, **kwargs):
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="success",
            started_at="2026-03-22T00:00:00Z",
            finished_at="2026-03-22T00:00:01Z",
            summary="Browser runtime smoke completed",
            operations=["start", "stop"],
        )

    class _ReviewDiscoveryService(_FakeDiscoveryService):
        async def discover(self, payload: dict[str, object]) -> dict[str, object]:
            result = await super().discover(payload)
            recommendation = dict(result["recommendations"][0])
            recommendation["review_required"] = True
            recommendation["risk_level"] = "confirm"
            result["recommendations"] = [recommendation]
            return result

    class _ReviewCapabilityService(_FakeCapabilityService):
        def __init__(self) -> None:
            self._discovery_service = _ReviewDiscoveryService()

    monkeypatch.setattr(
        "copaw.capabilities.install_templates.run_install_template_example",
        _fake_example_run,
    )
    app = _build_learning_app(tmp_path)
    app.state.learning_service.set_industry_service(_FakeIndustryService())
    app.state.learning_service.set_capability_service(_ReviewCapabilityService())
    app.state.learning_service.set_agent_profile_service(
        SimpleNamespace(
            get_capability_surface=lambda agent_id: {
                "effective_capabilities": [],
            },
        ),
    )
    client = TestClient(app)

    run_response = client.post(
        "/learning/acquisition/run",
        json={"industry_instance_id": "industry-v1-demo"},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["success"] is True
    assert payload["proposals_processed"] == 1
    assert payload["pending_approvals"] == 1
    assert payload["plans_materialized"] == 0
    assert payload["onboarding_runs"] == []
    assert payload["decision_requests"][0]["status"] == "open"

    proposal_id = payload["proposals"][0]["id"]
    decision_id = payload["decision_requests"][0]["id"]
    proposal_detail = client.get(f"/learning/acquisition/proposals/{proposal_id}")
    assert proposal_detail.status_code == 200
    assert proposal_detail.json()["status"] == "open"
    assert proposal_detail.json()["decision_request_id"] == decision_id

    approve_response = client.post(
        f"/learning/acquisition/proposals/{proposal_id}/approve",
        json={"actor": "reviewer"},
    )
    assert approve_response.status_code == 200
    approve_payload = approve_response.json()
    assert approve_payload["proposal"]["status"] == "applied"
    assert approve_payload["proposal"]["approved_by"] == "reviewer"
    assert approve_payload["plan"]["status"] == "applied"
    assert approve_payload["onboarding_run"]["status"] == "passed"
    assert approve_payload["decision_request"]["status"] == "approved"
    assert approve_payload["kernel_result"]["phase"] == "completed"
    assert app.state.kernel_dispatcher.task_store.get(proposal_id).phase == "completed"


def test_learning_api_acquisition_review_gate_rejects_through_kernel(
    tmp_path,
) -> None:
    class _ReviewDiscoveryService(_FakeDiscoveryService):
        async def discover(self, payload: dict[str, object]) -> dict[str, object]:
            result = await super().discover(payload)
            recommendation = dict(result["recommendations"][0])
            recommendation["review_required"] = True
            recommendation["risk_level"] = "confirm"
            result["recommendations"] = [recommendation]
            return result

    class _ReviewCapabilityService(_FakeCapabilityService):
        def __init__(self) -> None:
            self._discovery_service = _ReviewDiscoveryService()

    app = _build_learning_app(tmp_path)
    app.state.learning_service.set_industry_service(_FakeIndustryService())
    app.state.learning_service.set_capability_service(_ReviewCapabilityService())
    app.state.learning_service.set_agent_profile_service(
        SimpleNamespace(
            get_capability_surface=lambda agent_id: {
                "effective_capabilities": [],
            },
        ),
    )
    client = TestClient(app)

    run_response = client.post(
        "/learning/acquisition/run",
        json={"industry_instance_id": "industry-v1-demo"},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    proposal_id = payload["proposals"][0]["id"]

    reject_response = client.post(
        f"/learning/acquisition/proposals/{proposal_id}/reject",
        json={"actor": "reviewer"},
    )
    assert reject_response.status_code == 200
    reject_payload = reject_response.json()
    assert reject_payload["proposal"]["status"] == "rejected"
    assert reject_payload["decision_request"]["status"] == "rejected"
    assert reject_payload["kernel_result"]["phase"] == "cancelled"
    assert app.state.kernel_dispatcher.task_store.get(proposal_id).phase == "cancelled"


def test_runtime_center_decision_routes_handle_acquisition_rejection(tmp_path) -> None:
    class _ReviewDiscoveryService(_FakeDiscoveryService):
        async def discover(self, payload: dict[str, object]) -> dict[str, object]:
            result = await super().discover(payload)
            recommendation = dict(result["recommendations"][0])
            recommendation["review_required"] = True
            recommendation["risk_level"] = "confirm"
            result["recommendations"] = [recommendation]
            return result

    class _ReviewCapabilityService(_FakeCapabilityService):
        def __init__(self) -> None:
            self._discovery_service = _ReviewDiscoveryService()

    app = _build_learning_app(tmp_path)
    app.state.learning_service.set_industry_service(_FakeIndustryService())
    app.state.learning_service.set_capability_service(_ReviewCapabilityService())
    app.state.learning_service.set_agent_profile_service(
        SimpleNamespace(
            get_capability_surface=lambda agent_id: {
                "effective_capabilities": [],
            },
        ),
    )
    client = TestClient(app)

    run_response = client.post(
        "/learning/acquisition/run",
        json={"industry_instance_id": "industry-v1-demo"},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    decision_id = payload["decision_requests"][0]["id"]
    proposal_id = payload["proposals"][0]["id"]

    reject_response = client.post(
        f"/runtime-center/decisions/{decision_id}/reject",
        json={"resolution": "not now"},
    )
    assert reject_response.status_code == 200
    reject_payload = reject_response.json()
    assert reject_payload["decision"]["status"] == "rejected"
    assert reject_payload["proposal"]["status"] == "rejected"

    proposal_detail = client.get(f"/learning/acquisition/proposals/{proposal_id}")
    assert proposal_detail.status_code == 200
    assert proposal_detail.json()["status"] == "rejected"


def test_learning_acquisition_run_admits_confirm_proposal_into_kernel_waiting_confirm(
    tmp_path,
) -> None:
    class _ReviewDiscoveryService(_FakeDiscoveryService):
        async def discover(self, payload: dict[str, object]) -> dict[str, object]:
            result = await super().discover(payload)
            recommendation = dict(result["recommendations"][0])
            recommendation["review_required"] = True
            recommendation["risk_level"] = "confirm"
            result["recommendations"] = [recommendation]
            return result

    class _ReviewCapabilityService(_FakeCapabilityService):
        def __init__(self) -> None:
            self._discovery_service = _ReviewDiscoveryService()

    app = _build_learning_app(tmp_path)
    app.state.learning_service.set_industry_service(_FakeIndustryService())
    app.state.learning_service.set_capability_service(_ReviewCapabilityService())
    app.state.learning_service.set_agent_profile_service(
        SimpleNamespace(
            get_capability_surface=lambda agent_id: {
                "effective_capabilities": [],
            },
        ),
    )
    client = TestClient(app)

    run_response = client.post(
        "/learning/acquisition/run",
        json={"industry_instance_id": "industry-v1-demo"},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    proposal = payload["proposals"][0]
    proposal_id = proposal["id"]
    decision_id = payload["decision_requests"][0]["id"]

    kernel_task = app.state.kernel_dispatcher.task_store.get(proposal_id)
    assert kernel_task is not None
    assert kernel_task.id == proposal_id
    assert kernel_task.title == proposal["title"]
    assert kernel_task.phase == "waiting-confirm"
    assert kernel_task.risk_level == "confirm"
    assert (
        app.state.decision_request_repository.get_decision_request(decision_id).task_id
        == proposal_id
    )


def test_runtime_center_decision_routes_approve_acquisition_without_legacy_proposal_special_case(
    tmp_path,
    monkeypatch,
) -> None:
    async def _fake_example_run(*args, **kwargs):
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="success",
            started_at="2026-03-22T00:00:00Z",
            finished_at="2026-03-22T00:00:01Z",
            summary="Browser runtime smoke completed",
            operations=["start", "stop"],
        )

    class _ReviewDiscoveryService(_FakeDiscoveryService):
        async def discover(self, payload: dict[str, object]) -> dict[str, object]:
            result = await super().discover(payload)
            recommendation = dict(result["recommendations"][0])
            recommendation["review_required"] = True
            recommendation["risk_level"] = "confirm"
            result["recommendations"] = [recommendation]
            return result

    class _ReviewCapabilityService(_FakeCapabilityService):
        def __init__(self) -> None:
            self._discovery_service = _ReviewDiscoveryService()

    async def _unexpected_legacy_approve(*args, **kwargs):
        raise AssertionError(
            "runtime-center decision approve should not call approve_acquisition_proposal directly",
        )

    monkeypatch.setattr(
        "copaw.capabilities.install_templates.run_install_template_example",
        _fake_example_run,
    )
    app = _build_learning_app(tmp_path)
    app.state.learning_service.set_industry_service(_FakeIndustryService())
    app.state.learning_service.set_capability_service(_ReviewCapabilityService())
    app.state.learning_service.set_agent_profile_service(
        SimpleNamespace(
            get_capability_surface=lambda agent_id: {
                "effective_capabilities": [],
            },
        ),
    )
    monkeypatch.setattr(
        app.state.learning_service,
        "approve_acquisition_proposal",
        _unexpected_legacy_approve,
    )
    client = TestClient(app)

    run_response = client.post(
        "/learning/acquisition/run",
        json={"industry_instance_id": "industry-v1-demo"},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    decision_id = payload["decision_requests"][0]["id"]
    proposal_id = payload["proposals"][0]["id"]

    approve_response = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "ship it"},
    )
    assert approve_response.status_code == 200
    approve_payload = approve_response.json()
    assert approve_payload["decision_request_id"] == decision_id
    assert approve_payload["decision"]["status"] == "approved"
    assert approve_payload["proposal"]["status"] == "applied"
    assert approve_payload["proposal"]["id"] == proposal_id
    assert approve_payload["plan"]["status"] == "applied"
    assert approve_payload["onboarding_run"]["status"] == "passed"
    assert approve_payload["kernel_result"]["phase"] == "completed"


def test_runtime_center_decision_routes_reject_acquisition_without_legacy_proposal_special_case(
    tmp_path,
    monkeypatch,
) -> None:
    class _ReviewDiscoveryService(_FakeDiscoveryService):
        async def discover(self, payload: dict[str, object]) -> dict[str, object]:
            result = await super().discover(payload)
            recommendation = dict(result["recommendations"][0])
            recommendation["review_required"] = True
            recommendation["risk_level"] = "confirm"
            result["recommendations"] = [recommendation]
            return result

    class _ReviewCapabilityService(_FakeCapabilityService):
        def __init__(self) -> None:
            self._discovery_service = _ReviewDiscoveryService()

    def _unexpected_legacy_reject(*args, **kwargs):
        raise AssertionError(
            "runtime-center decision reject should not call reject_acquisition_proposal directly",
        )

    app = _build_learning_app(tmp_path)
    app.state.learning_service.set_industry_service(_FakeIndustryService())
    app.state.learning_service.set_capability_service(_ReviewCapabilityService())
    app.state.learning_service.set_agent_profile_service(
        SimpleNamespace(
            get_capability_surface=lambda agent_id: {
                "effective_capabilities": [],
            },
        ),
    )
    monkeypatch.setattr(
        app.state.learning_service,
        "reject_acquisition_proposal",
        _unexpected_legacy_reject,
    )
    client = TestClient(app)

    run_response = client.post(
        "/learning/acquisition/run",
        json={"industry_instance_id": "industry-v1-demo"},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    decision_id = payload["decision_requests"][0]["id"]
    proposal_id = payload["proposals"][0]["id"]

    reject_response = client.post(
        f"/runtime-center/decisions/{decision_id}/reject",
        json={"resolution": "not now"},
    )
    assert reject_response.status_code == 200
    reject_payload = reject_response.json()
    assert reject_payload["decision_request_id"] == decision_id
    assert reject_payload["decision"]["status"] == "rejected"
    assert reject_payload["proposal"]["status"] == "rejected"
    assert reject_payload["proposal"]["id"] == proposal_id
    assert reject_payload["kernel_result"]["phase"] == "cancelled"
