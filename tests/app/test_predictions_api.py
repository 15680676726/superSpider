# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.predictions import router as predictions_router
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.capabilities import CapabilityService
from copaw.capabilities.remote_skill_contract import RemoteSkillCandidate
from copaw.config import load_config, save_config
from copaw.config.config import MCPClientConfig
from copaw.compiler.planning.assignment_planner import AssignmentPlanningCompiler
from copaw.compiler.planning.models import PlanningStrategyConstraints
from copaw.evidence import EvidenceLedger
from copaw.evidence.models import EvidenceRecord
from copaw.goals import GoalService
from copaw.goals.service_compiler import _GoalServiceCompilerMixin
from copaw.industry import IndustryService
from copaw.industry.service_context import build_industry_service_runtime_bindings
from copaw.kernel import AgentProfileService, KernelDispatcher, KernelTaskStore
from copaw.predictions import PredictionService
from copaw.state import (
    AgentProfileOverrideRecord,
    DecisionRequestRecord,
    GoalRecord,
    IndustryInstanceRecord,
    PredictionCaseRecord,
    PredictionRecommendationRecord,
    SQLiteStateStore,
    StrategyMemoryRecord,
    TaskRecord,
    TaskRuntimeRecord,
    WorkflowRunRecord,
)
from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state.capability_portfolio_service import CapabilityPortfolioService
from copaw.state.donor_trust_service import DonorTrustService
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.skill_lifecycle_decision_service import (
    SkillLifecycleDecisionService,
)
from copaw.state.skill_trial_service import SkillTrialService
from copaw.state.reporting_service import StateReportingService
from copaw.state.strategy_memory_service import StateStrategyMemoryService
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentRuntimeRepository,
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteIndustryInstanceRepository,
    SqlitePredictionCaseRepository,
    SqlitePredictionRecommendationRepository,
    SqlitePredictionReviewRepository,
    SqlitePredictionScenarioRepository,
    SqlitePredictionSignalRepository,
    SqliteRuntimeFrameRepository,
    SqliteOperatingCycleRepository,
    SqliteStrategyMemoryRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkflowRunRepository,
)


class FakeTurnExecutor:
    async def stream_request(self, request, **kwargs):
        yield {
            "object": "message",
            "status": "completed",
            "request": request,
            "kwargs": kwargs,
        }


class _InMemorySkillService:
    def __init__(self) -> None:
        self._skills: dict[str, SimpleNamespace] = {}

    def list_all_skills(self) -> list[object]:
        return list(self._skills.values())

    def list_available_skill_names(self) -> list[str]:
        return list(self._skills.keys())

    def list_available_skills(self) -> list[object]:
        return self.list_all_skills()

    def find_skill(self, skill_name: str) -> object | None:
        return self._skills.get(skill_name)

    def enable_skill(self, skill_name: str) -> None:
        skill = self._skills.get(skill_name)
        if skill is not None:
            skill.enabled = True

    def disable_skill(self, skill_name: str) -> None:
        skill = self._skills.get(skill_name)
        if skill is not None:
            skill.enabled = False

    def delete_skill(self, skill_name: str) -> bool:
        return self._skills.pop(skill_name, None) is not None

    def create_skill(self, **kwargs: object) -> object:
        name = str(kwargs.get("name") or "").strip()
        if not name:
            return False
        self._skills[name] = SimpleNamespace(
            name=name,
            enabled=False,
            source_url="",
            content=str(kwargs.get("content") or ""),
            source="customized",
            path=f"/tmp/{name}",
            references=kwargs.get("references") or {},
            scripts=kwargs.get("scripts") or {},
        )
        return True

    def install_skill_from_hub(self, **kwargs: object) -> object:
        bundle_url = str(kwargs.get("bundle_url") or "")
        name = (
            bundle_url.rstrip("/").rsplit("/", 1)[-1].split(".zip", 1)[0].replace("-", "_")
            or "installed_skill"
        )
        installed = SimpleNamespace(
            name=name,
            enabled=bool(kwargs.get("enable", True)),
            source_url=bundle_url,
            content="",
            source="hub",
            path=f"/tmp/{name}",
            references={},
            scripts={},
        )
        self._skills[name] = installed
        return installed

    def load_skill_file(
        self,
        *,
        skill_name: str,
        file_path: str,
        source: str,
    ) -> str | None:
        _ = file_path, source
        skill = self._skills.get(skill_name)
        return None if skill is None else str(getattr(skill, "content", "") or "")

    def sync_to_working_dir(
        self,
        *,
        skill_names: list[str] | None = None,
        force: bool = False,
    ) -> tuple[int, int]:
        _ = skill_names, force
        return (0, 0)

def _build_predictions_app(
    tmp_path,
    *,
    enable_remote_hub_search: bool = False,
    enable_remote_curated_search: bool = False,
    seed_cases: list[PredictionCaseRecord] | None = None,
    seed_recommendations: list[PredictionRecommendationRecord] | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(predictions_router)
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    goal_repository = SqliteGoalRepository(state_store)
    goal_override_repository = SqliteGoalOverrideRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    industry_instance_repository = SqliteIndustryInstanceRepository(state_store)
    workflow_run_repository = SqliteWorkflowRunRepository(state_store)
    prediction_case_repository = SqlitePredictionCaseRepository(state_store)
    prediction_scenario_repository = SqlitePredictionScenarioRepository(state_store)
    prediction_signal_repository = SqlitePredictionSignalRepository(state_store)
    prediction_recommendation_repository = SqlitePredictionRecommendationRepository(
        state_store,
    )
    prediction_review_repository = SqlitePredictionReviewRepository(state_store)
    strategy_memory_repository = SqliteStrategyMemoryRepository(state_store)
    agent_profile_override_repository = SqliteAgentProfileOverrideRepository(
        state_store,
    )
    agent_runtime_repository = SqliteAgentRuntimeRepository(state_store)
    agent_report_repository = SqliteAgentReportRepository(state_store)
    assignment_repository = SqliteAssignmentRepository(state_store)
    backlog_item_repository = SqliteBacklogItemRepository(state_store)
    operating_cycle_repository = SqliteOperatingCycleRepository(state_store)
    strategy_memory_service = StateStrategyMemoryService(
        repository=strategy_memory_repository,
    )
    skill_service = _InMemorySkillService()
    config_path = tmp_path / "copaw-config.json"
    config = load_config(config_path)
    config.mcp.clients["desktop_windows"] = MCPClientConfig(
        name="Desktop Windows",
        enabled=False,
        command="npx",
        args=["-y", "@jason.today/webmcp@latest"],
    )
    save_config(config, config_path)

    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        turn_executor=FakeTurnExecutor(),
        agent_profile_override_repository=agent_profile_override_repository,
        skill_service=skill_service,
        load_config_fn=lambda: load_config(config_path),
        save_config_fn=lambda config: save_config(config, config_path),
    )
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        capability_service=capability_service,
        task_store=task_store,
    )
    goal_service = GoalService(
        repository=goal_repository,
        override_repository=goal_override_repository,
        dispatcher=dispatcher,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        industry_instance_repository=industry_instance_repository,
    )
    capability_service.set_goal_service(goal_service)
    agent_profile_service = AgentProfileService(
        override_repository=agent_profile_override_repository,
        agent_runtime_repository=agent_runtime_repository,
        industry_instance_repository=industry_instance_repository,
        capability_service=capability_service,
    )
    _original_get_agent_detail = agent_profile_service.get_agent_detail

    def _prediction_agent_detail(agent_id: str):
        detail = _original_get_agent_detail(agent_id) or {"runtime": None}
        payload = dict(detail)
        runtime = dict(payload.get("runtime") or {})
        metadata = dict(runtime.get("metadata") or {})
        if (
            agent_id == "industry-solution-lead-demo"
            and "selected_seat_ref" not in metadata
        ):
            metadata["selected_seat_ref"] = "env-browser-primary"
        runtime["metadata"] = metadata
        payload["runtime"] = runtime
        return payload

    agent_profile_service.get_agent_detail = _prediction_agent_detail
    capability_service.set_agent_profile_service(agent_profile_service)
    reporting_service = StateReportingService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        goal_repository=goal_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        industry_instance_repository=industry_instance_repository,
        agent_profile_service=agent_profile_service,
        prediction_case_repository=prediction_case_repository,
        prediction_recommendation_repository=prediction_recommendation_repository,
        prediction_review_repository=prediction_review_repository,
    )
    industry_runtime_bindings = build_industry_service_runtime_bindings(
        agent_report_repository=agent_report_repository,
        agent_runtime_repository=agent_runtime_repository,
        assignment_repository=assignment_repository,
        backlog_item_repository=backlog_item_repository,
        operating_cycle_repository=operating_cycle_repository,
    )
    industry_service = IndustryService(
        goal_service=goal_service,
        industry_instance_repository=industry_instance_repository,
        goal_override_repository=goal_override_repository,
        agent_profile_override_repository=agent_profile_override_repository,
        evidence_ledger=evidence_ledger,
        agent_profile_service=agent_profile_service,
        capability_service=capability_service,
        strategy_memory_service=strategy_memory_service,
        state_store=state_store,
        runtime_bindings=industry_runtime_bindings,
    )
    capability_service.set_industry_service(industry_service)
    capability_donor_service = CapabilityDonorService(
        state_store=state_store,
    )
    capability_candidate_service = CapabilityCandidateService(
        state_store=state_store,
        donor_service=capability_donor_service,
    )
    skill_trial_service = SkillTrialService(
        state_store=state_store,
    )
    skill_lifecycle_decision_service = SkillLifecycleDecisionService(
        state_store=state_store,
    )
    donor_trust_service = DonorTrustService(
        donor_service=capability_donor_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
    )
    capability_portfolio_service = CapabilityPortfolioService(
        donor_service=capability_donor_service,
        candidate_service=capability_candidate_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
    )
    capability_candidate_service.import_active_baseline_artifacts(
        mounts=capability_service.list_public_capabilities(enabled_only=True),
    )
    for item in seed_cases or []:
        prediction_case_repository.upsert_case(item)
    for item in seed_recommendations or []:
        prediction_recommendation_repository.upsert_recommendation(item)
    prediction_service = PredictionService(
        case_repository=prediction_case_repository,
        scenario_repository=prediction_scenario_repository,
        signal_repository=prediction_signal_repository,
        recommendation_repository=prediction_recommendation_repository,
        review_repository=prediction_review_repository,
        evidence_ledger=evidence_ledger,
        reporting_service=reporting_service,
        goal_repository=goal_repository,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_request_repository,
        industry_instance_repository=industry_instance_repository,
        workflow_run_repository=workflow_run_repository,
        strategy_memory_service=strategy_memory_service,
        capability_service=capability_service,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        capability_portfolio_service=capability_portfolio_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        agent_profile_service=agent_profile_service,
        kernel_dispatcher=dispatcher,
        enable_remote_hub_search=enable_remote_hub_search,
        enable_remote_curated_search=enable_remote_curated_search,
    )

    goal_repository.upsert_goal(
        GoalRecord(
            id="goal-prediction",
            title="Stabilize outbound execution",
            summary="Reduce runtime friction before the next outbound push.",
            status="active",
            priority=3,
            owner_scope="industry-demo-scope",
            industry_instance_id="industry-demo",
        ),
    )
    industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-demo",
            label="Demo Industry",
            summary="Demo strategy-aware operating scope.",
            owner_scope="industry-demo-scope",
            status="active",
            agent_ids=["copaw-agent-runner", "industry-solution-lead-demo"],
            execution_core_identity_payload={"agent_id": "copaw-agent-runner"},
            team_payload={
                "agents": [
                    {
                        "role_id": "execution-core",
                        "agent_id": "copaw-agent-runner",
                        "agent_class": "business",
                    },
                    {
                        "role_id": "solution-lead",
                        "agent_id": "industry-solution-lead-demo",
                        "agent_class": "business",
                    },
                ]
            },
        ),
    )
    strategy_memory_service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:global:global:shared",
            scope_type="global",
            scope_id="global",
            title="Global execution strategy",
            summary="Prefer removing execution blockers before expanding scope.",
            north_star="Keep the operating loop stable and unblock execution first",
            priority_order=["稳定执行", "清理阻塞", "再做扩张"],
            execution_constraints=["Do not expand scope before core blockers are resolved"],
            current_focuses=["Stabilize outbound execution"],
            status="active",
        ),
    )
    strategy_memory_service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-demo:copaw-agent-runner",
            scope_type="industry",
            scope_id="industry-demo",
            owner_agent_id="copaw-agent-runner",
            owner_scope="industry-demo-scope",
            industry_instance_id="industry-demo",
            title="Industry demo strategy",
            summary="Unblock desktop outreach before scaling the next industry loop.",
            north_star="先打通桌面外呼链路，再扩大行业执行面",
            priority_order=["桌面外呼就绪", "能力缺口清理", "行业执行放量"],
            delegation_policy=["执行中枢负责统筹，叶子动作下放给行业岗位"],
            execution_constraints=["不要在能力缺口未补齐前扩大投放节奏"],
            current_focuses=["Stabilize outbound execution"],
            status="active",
        ),
    )
    workflow_run_repository.upsert_run(
        WorkflowRunRecord(
            run_id="run-desktop-gap",
            template_id="desktop-outreach-smoke",
            title="Desktop outreach smoke",
            summary="Guarded desktop outreach workflow.",
            status="planned",
            industry_instance_id="industry-demo",
            preview_payload={
                "dependencies": [
                    {
                        "capability_id": "mcp:desktop_windows",
                        "installed": False,
                        "available": False,
                        "enabled": False,
                        "target_agent_ids": ["industry-solution-lead-demo"],
                        "install_templates": [
                            {
                                "template_id": "desktop-windows",
                                "name": "Desktop Windows",
                                "installed": False,
                                "default_client_key": "desktop_windows",
                                "capability_tags": ["desktop"],
                                "routes": {
                                    "market": "/capability-market?tab=install-templates&template=desktop-windows",
                                },
                            }
                        ],
                    }
                ],
                "missing_capability_ids": ["mcp:desktop_windows"],
                "assignment_gap_capability_ids": [],
                "steps": [
                    {
                        "step_id": "desktop-leaf-action",
                        "execution_mode": "leaf",
                        "owner_role_id": "solution-lead",
                        "owner_agent_id": "industry-solution-lead-demo",
                    }
                ],
            },
        ),
    )

    app.state.goal_service = goal_service
    app.state.reporting_service = reporting_service
    app.state.prediction_service = prediction_service
    app.state.capability_service = capability_service
    app.state.capability_candidate_service = capability_candidate_service
    app.state.capability_donor_service = capability_donor_service
    app.state.donor_trust_service = donor_trust_service
    app.state.capability_portfolio_service = capability_portfolio_service
    app.state.skill_trial_service = skill_trial_service
    app.state.skill_lifecycle_decision_service = skill_lifecycle_decision_service
    app.state.kernel_dispatcher = dispatcher
    app.state.decision_request_repository = decision_request_repository
    app.state.agent_profile_service = agent_profile_service
    app.state.strategy_memory_service = strategy_memory_service
    app.state.industry_service = industry_service
    app.state.task_repository = task_repository
    app.state.task_runtime_repository = task_runtime_repository
    app.state.agent_profile_override_repository = agent_profile_override_repository
    app.state.agent_runtime_repository = agent_runtime_repository
    app.state.evidence_ledger = evidence_ledger
    app.state.workflow_run_repository = workflow_run_repository
    app.state.config_path = config_path

    return app


def _create_prediction_case(client: TestClient) -> dict[str, object]:
    created = client.post(
        "/predictions",
        json={
            "title": "Outbound desktop readiness",
            "question": "What should we fix before the next guarded desktop outreach?",
            "summary": "Review the current runtime and workflow blockers.",
            "owner_scope": "industry-demo-scope",
            "industry_instance_id": "industry-demo",
            "workflow_run_id": "run-desktop-gap",
        },
    )
    assert created.status_code == 200
    return created.json()


def _execute_prediction_recommendation_direct(
    app: FastAPI,
    *,
    case_id: str,
    recommendation_id: str,
    actor: str = "copaw-operator",
) -> dict[str, object]:
    return asyncio.run(
        app.state.prediction_service.execute_recommendation(
            case_id,
            recommendation_id,
            actor=actor,
        ),
    ).model_dump(mode="json")


def test_predictions_api_create_list_and_detail(tmp_path) -> None:
    client = TestClient(_build_predictions_app(tmp_path))

    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]

    listing = client.get("/predictions")
    assert listing.status_code == 200
    payload = listing.json()
    assert len(payload) == 1
    assert payload[0]["case"]["case_id"] == case_id
    assert payload[0]["recommendation_count"] >= 2

    detail = client.get(f"/predictions/{case_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["case"]["input_payload"]["strategy_id"] == (
        "strategy:industry:industry-demo:copaw-agent-runner"
    )
    assert len(detail_payload["signals"]) >= 2
    signal_labels = {item["label"] for item in detail_payload["signals"]}
    assert "战略北极星" in signal_labels
    assert "战略优先级" in signal_labels
    assert len(detail_payload["scenarios"]) == 3
    assert any(
        "战略北极星" in " ".join(item["assumptions"])
        for item in detail_payload["scenarios"]
    )
    capability_recommendation = next(
        item
        for item in detail_payload["recommendations"]
        if item["recommendation"]["recommendation_type"] == "capability_recommendation"
    )
    assert capability_recommendation["recommendation"]["target_capability_ids"] == [
        "mcp:desktop_windows",
    ]
    assert capability_recommendation["recommendation"]["metadata"]["strategy_id"] == (
        "strategy:industry:industry-demo:copaw-agent-runner"
    )
    main_brain_handoff = next(
        item
        for item in detail_payload["recommendations"]
        if item["recommendation"]["action_kind"] == "manual:coordinate-main-brain"
    )
    assert main_brain_handoff["recommendation"]["executable"] is False
    assert main_brain_handoff["recommendation"]["status"] == "manual-only"
    assert main_brain_handoff["recommendation"]["target_goal_id"] == "goal-prediction"
    assert main_brain_handoff["recommendation"]["target_agent_id"]
    assert main_brain_handoff["recommendation"]["action_payload"] == {}
    assert "compat_goal_handoff" not in main_brain_handoff["recommendation"]["metadata"]
    assert main_brain_handoff["routes"]["coordinate"].endswith("/coordinate")


def test_predictions_consume_strategy_trigger_rules_into_signals_and_recommendations(
    tmp_path,
) -> None:
    app = _build_predictions_app(tmp_path)
    app.state.strategy_memory_service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-demo:copaw-agent-runner",
            scope_type="industry",
            scope_id="industry-demo",
            owner_agent_id="copaw-agent-runner",
            owner_scope="industry-demo-scope",
            industry_instance_id="industry-demo",
            title="Industry demo strategy",
            summary="Escalate weekend-demand uncertainty before expanding growth work.",
            north_star="Stabilize growth without scaling unresolved risk",
            priority_order=["review demand uncertainty", "protect growth lane", "expand later"],
            execution_constraints=["Do not scale outreach before weekend demand is revalidated"],
            strategic_uncertainties=[
                {
                    "uncertainty_id": "uncertainty-weekend-demand",
                    "statement": "Weekend demand model is still unverified.",
                    "scope": "strategy",
                    "impact_level": "high",
                    "current_confidence": 0.28,
                    "review_by_cycle": "cycle-weekly-1",
                    "escalate_when": ["confidence-drop"],
                }
            ],
            lane_budgets=[
                {
                    "lane_id": "lane-growth",
                    "budget_window": "next-2-cycles",
                    "target_share": 0.55,
                    "min_share": 0.4,
                    "max_share": 0.7,
                    "current_share": 0.78,
                    "review_pressure": "high",
                    "force_include_reason": "Protect validated growth experiments while the uncertainty stays open.",
                }
            ],
            strategy_trigger_rules=[
                {
                    "rule_id": "review-rule:weekend-demand",
                    "source_type": "review_rule",
                    "summary": "Weekend demand confidence dropped below threshold.",
                    "trigger_family": "confidence_collapse",
                    "decision_hint": "strategy_review_required",
                    "decision_kind": "strategy_review_required",
                    "trigger_signals": ["confidence-drop"],
                    "lane_ids": ["lane-growth"],
                    "uncertainty_ids": ["uncertainty-weekend-demand"],
                    "source": "strategy-memory",
                }
            ],
            current_focuses=["Stabilize outbound execution"],
            status="active",
        ),
    )
    client = TestClient(app)

    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]
    detail = client.get(f"/predictions/{case_id}")

    assert detail.status_code == 200
    payload = detail.json()
    trigger_signal = next(
        item
        for item in payload["signals"]
        if item["source_ref"] == "review-rule:weekend-demand"
    )
    assert trigger_signal["payload"]["decision_kind"] == "strategy_review_required"
    assert trigger_signal["payload"]["uncertainty_ids"] == ["uncertainty-weekend-demand"]

    uncertainty_signal = next(
        item
        for item in payload["signals"]
        if item["source_ref"] == "uncertainty-weekend-demand"
    )
    assert uncertainty_signal["payload"]["impact_level"] == "high"
    assert uncertainty_signal["payload"]["review_by_cycle"] == "cycle-weekly-1"

    lane_budget_signal = next(
        item
        for item in payload["signals"]
        if item["source_ref"] == "lane-budget:lane-growth"
    )
    assert lane_budget_signal["payload"]["review_pressure"] == "high"
    assert lane_budget_signal["payload"]["current_share"] == 0.78

    strategy_review = next(
        item
        for item in payload["recommendations"]
        if item["recommendation"]["metadata"].get("strategy_change_decision")
        == "strategy_review_required"
    )
    assert strategy_review["recommendation"]["action_kind"] == "manual:coordinate-main-brain"
    assert strategy_review["recommendation"]["metadata"]["trigger_rule_ids"] == [
        "review-rule:weekend-demand"
    ]
    assert strategy_review["recommendation"]["metadata"]["affected_lane_ids"] == [
        "lane-growth"
    ]
    assert strategy_review["recommendation"]["metadata"]["affected_uncertainty_ids"] == [
        "uncertainty-weekend-demand"
    ]


def test_predictions_recommend_schedule_copy_points_to_fixed_sop_instead_of_workflow_templates(
    tmp_path,
) -> None:
    app = _build_predictions_app(tmp_path)
    app.state.workflow_run_repository.delete_run("run-desktop-gap")
    client = TestClient(app)

    created = client.post(
        "/predictions",
        json={
            "title": "Recurring automation gap",
            "question": "What recurring automation should we formalize next?",
            "summary": "The scope has active goals but no visible automation contract.",
            "owner_scope": "industry-demo-scope",
            "industry_instance_id": "industry-demo",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    recommendation = next(
        item
        for item in payload["recommendations"]
        if item["recommendation"]["recommendation_type"] == "schedule_recommendation"
    )

    assert recommendation["recommendation"]["summary"] == (
        "当前范围内已有活跃执行上下文，但缺少可见的自动化执行合同。"
        "建议把周期性工作收口为固定 SOP 或运行计划。"
    )


def test_prediction_service_collects_industry_tasks_without_goal_anchor(tmp_path) -> None:
    app = _build_predictions_app(tmp_path)
    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-industry-unowned",
            title="Industry-owned blocker follow-up",
            summary="This task belongs to the industry scope but has no goal or owner anchor.",
            task_type="analysis",
            status="failed",
            industry_instance_id="industry-demo",
            owner_agent_id=None,
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-industry-unowned",
            runtime_status="terminated",
            current_phase="failed",
            last_error_summary="Industry blocker still unresolved.",
        ),
    )
    client = TestClient(app)

    created = _create_prediction_case(client)
    case = PredictionCaseRecord.model_validate(created["case"])
    facts = app.state.prediction_service._collect_facts(case)

    assert any(task.id == "task-industry-unowned" for task in facts.tasks)
    assert "goal_ids" not in created["case"]["input_payload"]
    assert "task-industry-unowned" in created["case"]["input_payload"]["task_ids"]


def test_prediction_service_does_not_fallback_to_goal_id_queries_when_industry_tasks_exist(
    tmp_path,
) -> None:
    app = _build_predictions_app(tmp_path)
    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-industry-anchor",
            title="Industry runtime blocker",
            summary="Canonical industry task should be enough to build prediction task scope.",
            task_type="analysis",
            status="failed",
            industry_instance_id="industry-demo",
            owner_agent_id=None,
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-industry-anchor",
            runtime_status="terminated",
            current_phase="failed",
            last_error_summary="Industry runtime blocker remains unresolved.",
        ),
    )
    client = TestClient(app)
    created = _create_prediction_case(client)
    case = PredictionCaseRecord.model_validate(created["case"])

    original_list_tasks = app.state.task_repository.list_tasks

    def _guarded_list_tasks(*args, **kwargs):
        if kwargs.get("goal_ids"):
            raise AssertionError("prediction task collection should not fallback to goal_ids when industry task truth exists")
        return original_list_tasks(*args, **kwargs)

    app.state.task_repository.list_tasks = _guarded_list_tasks

    facts = app.state.prediction_service._collect_facts(case)

    assert facts.tasks
    assert any(task.id == "task-industry-anchor" for task in facts.tasks)
    assert "goal_ids" not in created["case"]["input_payload"]


def test_prediction_service_prefers_agent_task_truth_before_goal_fallback(
    tmp_path,
) -> None:
    app = _build_predictions_app(tmp_path)
    app.state.agent_profile_override_repository.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-solution-lead-demo",
            name="Solution Lead",
            role_name="Solution Lead",
            agent_class="business",
            status="active",
            industry_instance_id="industry-demo",
            industry_role_id="solution-lead",
        ),
    )
    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-agent-anchor",
            title="Agent runtime blocker",
            summary="Industry agent task should be enough to build prediction task scope.",
            task_type="analysis",
            status="running",
            industry_instance_id=None,
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    client = TestClient(app)
    created = _create_prediction_case(client)
    case = PredictionCaseRecord.model_validate(created["case"])

    original_list_tasks = app.state.task_repository.list_tasks

    def _guarded_list_tasks(*args, **kwargs):
        if kwargs.get("goal_ids"):
            raise AssertionError(
                "prediction task collection should prefer agent task truth before goal_ids fallback",
            )
        return original_list_tasks(*args, **kwargs)

    app.state.task_repository.list_tasks = _guarded_list_tasks

    facts = app.state.prediction_service._collect_facts(case)

    assert facts.tasks
    assert any(task.id == "task-agent-anchor" for task in facts.tasks)


def test_prediction_cycle_case_deduplicates_same_operating_fingerprint(tmp_path) -> None:
    app = _build_predictions_app(tmp_path)
    service = app.state.prediction_service

    first = service.create_cycle_case(
        industry_instance_id="industry-demo",
        industry_label="Demo Industry",
        owner_scope="industry-demo-scope",
        owner_agent_id="copaw-agent-runner",
        actor="system:operating-cycle",
        cycle_id="cycle-1",
        pending_report_ids=["report-a"],
        open_backlog_ids=["backlog-a"],
        open_backlog_source_refs=["operator:backlog-a"],
        meeting_window="morning",
        participant_inputs=[
            {
                "assignment_id": "assignment-1",
                "owner_agent_id": "industry-solution-lead-demo",
                "summary": "Researcher returned the latest market blockers.",
            }
        ],
        assignment_summaries=[
            {
                "assignment_id": "assignment-1",
                "headline": "Need a governed desktop capability decision",
            }
        ],
        lane_summaries=[
            {
                "lane_id": "lane-growth",
                "title": "Growth lane still blocked by runtime friction",
            }
        ],
    )
    second = service.create_cycle_case(
        industry_instance_id="industry-demo",
        industry_label="Demo Industry",
        owner_scope="industry-demo-scope",
        owner_agent_id="copaw-agent-runner",
        actor="system:operating-cycle",
        cycle_id="cycle-1",
        pending_report_ids=["report-a"],
        open_backlog_ids=["backlog-a"],
        open_backlog_source_refs=["operator:backlog-a"],
        meeting_window="morning",
        participant_inputs=[
            {
                "assignment_id": "assignment-1",
                "owner_agent_id": "industry-solution-lead-demo",
                "summary": "Researcher returned the latest market blockers.",
            }
        ],
        assignment_summaries=[
            {
                "assignment_id": "assignment-1",
                "headline": "Need a governed desktop capability decision",
            }
        ],
        lane_summaries=[
            {
                "lane_id": "lane-growth",
                "title": "Growth lane still blocked by runtime friction",
            }
        ],
    )

    assert first is not None
    assert second is not None
    assert first.case["case_kind"] == "cycle"
    assert first.case["metadata"]["meeting_contract"] == "main-brain-window-review-v1"
    assert first.case["metadata"]["meeting_mode"] == "structured-async"
    assert first.case["metadata"]["participant_mode"] == "structured-inputs"
    assert first.case["metadata"]["meeting_trigger_mode"] == "windowed-operating-cycle"
    assert first.case["metadata"]["meeting_window"] == "morning"
    assert first.case["metadata"]["review_date_local"]
    assert "goal_statuses" not in first.case["metadata"]
    assert first.case["metadata"]["participant_inputs"][0]["assignment_id"] == "assignment-1"
    assert first.case["metadata"]["assignment_summaries"][0]["assignment_id"] == "assignment-1"
    assert first.case["metadata"]["lane_summaries"][0]["lane_id"] == "lane-growth"
    assert second.case["case_id"] == first.case["case_id"]
    assert len(service.list_cases(case_kind="cycle")) == 1


def test_prediction_cycle_case_exposes_light_formal_planning_context_in_detail(tmp_path) -> None:
    app = _build_predictions_app(tmp_path)
    service = app.state.prediction_service

    detail = service.create_cycle_case(
        industry_instance_id="industry-demo",
        industry_label="Demo Industry",
        owner_scope="industry-demo-scope",
        owner_agent_id="copaw-agent-runner",
        actor="system:operating-cycle",
        cycle_id="cycle-1",
        pending_report_ids=["report-a", "report-b"],
        open_backlog_ids=["backlog-a"],
        open_backlog_source_refs=["operator:backlog-a"],
        meeting_window="morning",
        participant_inputs=[
            {
                "assignment_id": "assignment-1",
                "owner_agent_id": "industry-solution-lead-demo",
                "summary": "Researcher returned the latest market blockers.",
            }
        ],
        assignment_summaries=[
            {
                "assignment_id": "assignment-1",
                "headline": "Need a governed desktop capability decision",
            }
        ],
        lane_summaries=[
            {
                "lane_id": "lane-growth",
                "title": "Growth lane still blocked by runtime friction",
            }
        ],
        formal_planning_context={
            "review_ref": "formal-review:industry-demo:cycle-1",
            "review_window": "morning-review",
            "summary": "Formal planner wants the main brain to review report pressure.",
            "planning_policy": ["prefer-followup-before-net-new"],
            "strategy_constraints": {
                "mission": "Protect growth while validating the weekend anomaly.",
                "graph_focus_entities": [
                    "weekend-variance",
                    "lane-growth",
                ],
                "graph_focus_opinions": [
                    "staffing:caution:premature-change",
                ],
                "strategic_uncertainties": [
                    {
                        "uncertainty_id": "uncertainty-weekend-demand",
                        "statement": "Weekend demand may be structurally weaker than the lane assumes.",
                        "scope": "strategy",
                        "impact_level": "high",
                        "current_confidence": 0.34,
                        "review_by_cycle": "cycle-weekly-1",
                        "escalate_when": ["confidence-drop", "target-miss"],
                    }
                ],
                "lane_budgets": [
                    {
                        "lane_id": "lane-growth",
                        "budget_window": "next-2-cycles",
                        "target_share": 0.55,
                        "min_share": 0.4,
                        "max_share": 0.7,
                        "review_pressure": "high",
                        "force_include_reason": "Protect validated growth experiments while uncertainty is open.",
                    }
                ],
            },
            "cycle_decision": {
                "cycle_kind": "daily",
                "selected_lane_ids": ["lane-growth"],
                "selected_backlog_item_ids": ["backlog-a"],
                "max_assignment_count": 1,
                "summary": "Keep the cycle narrow while the growth uncertainty is unresolved.",
                "metadata": {
                    "graph_focus_entities": [
                        "weekend-variance",
                        "lane-growth",
                    ],
                    "graph_focus_opinions": [
                        "staffing:caution:premature-change",
                    ],
                },
            },
            "selected_lane_ids": ["lane-growth"],
            "selected_backlog_item_ids": ["backlog-a"],
            "metadata": {
                "pending_report_count": 2,
                "open_backlog_count": 1,
            },
        },
        report_synthesis={
            "recommended_actions": [{"action_id": "follow-up:1"}],
            "replan_directives": [{"directive_id": "dir-1"}],
            "activation": {
                "top_constraints": ["Need validated weekend cause."],
                "top_entities": ["weekend-variance"],
                "top_opinions": ["staffing:caution:premature-change"],
            },
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:failed-report:1",
                "status": "needs-replan",
                "decision_kind": "strategy_review_required",
                "summary": "1 unresolved report synthesis signal requires main-brain judgment.",
                "reason_ids": ["failed-report:1"],
                "source_report_ids": ["report-a"],
                "topic_keys": ["weekend-variance"],
                "trigger_context": {
                    "trigger_families": [
                        "confidence-collapse",
                        "repeated-contradiction",
                    ],
                    "strategic_uncertainty_ids": ["uncertainty-weekend-demand"],
                    "lane_budget_pressure": {
                        "lane-growth": "over-target-share",
                    },
                },
            },
        },
    )

    assert detail is not None
    planning = detail.case["planning"]
    assert planning["is_truth_store"] is False
    assert planning["source"] == "formal-cycle-review-overlap"
    assert planning["review_ref"] == "formal-review:industry-demo:cycle-1"
    assert planning["review_window"] == "morning-review"
    assert planning["planning_policy"] == ["prefer-followup-before-net-new"]
    assert planning["strategy_constraints"]["mission"] == (
        "Protect growth while validating the weekend anomaly."
    )
    assert planning["strategy_constraints"]["graph_focus_entities"] == [
        "weekend-variance",
        "lane-growth",
    ]
    assert planning["strategy_constraints"]["graph_focus_opinions"] == [
        "staffing:caution:premature-change",
    ]
    assert planning["strategy_constraints"]["strategic_uncertainties"][0][
        "uncertainty_id"
    ] == "uncertainty-weekend-demand"
    assert planning["strategy_constraints"]["lane_budgets"][0]["lane_id"] == (
        "lane-growth"
    )
    assert planning["cycle_decision"]["cycle_kind"] == "daily"
    assert planning["cycle_decision"]["selected_lane_ids"] == ["lane-growth"]
    assert planning["selected_lane_ids"] == ["lane-growth"]
    assert planning["selected_backlog_item_ids"] == ["backlog-a"]
    assert planning["participant_count"] == 1
    assert planning["assignment_count"] == 1
    assert planning["lane_count"] == 1
    assert planning["pending_report_count"] == 2
    assert planning["open_backlog_count"] == 1
    assert planning["replan"]["status"] == "needs-replan"
    assert planning["replan"]["decision_id"] == (
        "report-synthesis:needs-replan:failed-report:1"
    )
    assert planning["replan"]["decision_kind"] == "strategy_review_required"
    assert planning["replan"]["reason_ids"] == ["failed-report:1"]
    assert planning["replan"]["directive_count"] == 1
    assert planning["replan"]["recommended_action_count"] == 1
    assert "top_constraints" in planning["replan"]["activation_keys"]
    assert "top_entities" in planning["replan"]["activation_keys"]
    assert "top_opinions" in planning["replan"]["activation_keys"]
    assert planning["replan"]["trigger_context"]["trigger_families"] == [
        "confidence-collapse",
        "repeated-contradiction",
    ]
    assert planning["replan"]["trigger_context"]["strategic_uncertainty_ids"] == [
        "uncertainty-weekend-demand"
    ]
    assert detail.case["input_payload"]["planning"]["review_ref"] == (
        "formal-review:industry-demo:cycle-1"
    )
    assert detail.case["metadata"]["planning_snapshot"]["replan"]["status"] == (
        "needs-replan"
    )
    assert detail.case["metadata"]["planning_snapshot"]["replan"]["decision_kind"] == (
        "strategy_review_required"
    )
    assert detail.stats["planning_overlap"] is True
    assert detail.stats["planning_replan_status"] == "needs-replan"
    assert (
        detail.stats["planning_replan_decision_kind"]
        == "strategy_review_required"
    )


def test_prediction_cycle_case_reuses_formal_planning_review_identity_for_dedupe(
    tmp_path,
) -> None:
    app = _build_predictions_app(tmp_path)
    service = app.state.prediction_service

    first = service.create_cycle_case(
        industry_instance_id="industry-demo",
        industry_label="Demo Industry",
        owner_scope="industry-demo-scope",
        owner_agent_id="copaw-agent-runner",
        actor="system:operating-cycle",
        cycle_id="cycle-1",
        pending_report_ids=["report-a"],
        open_backlog_ids=["backlog-a"],
        meeting_window="morning",
        formal_planning_context={
            "review_ref": "formal-review:industry-demo:cycle-1",
            "review_window": "morning-review",
        },
    )
    second = service.create_cycle_case(
        industry_instance_id="industry-demo",
        industry_label="Demo Industry",
        owner_scope="industry-demo-scope",
        owner_agent_id="copaw-agent-runner",
        actor="system:planning-review",
        cycle_id="cycle-1",
        pending_report_ids=["report-b"],
        open_backlog_ids=["backlog-b"],
        meeting_window="cycle-review",
        formal_planning_context={
            "review_ref": "formal-review:industry-demo:cycle-1",
            "review_window": "morning-review",
        },
    )

    assert first is not None
    assert second is not None
    assert first.case["planning"]["review_ref"] == "formal-review:industry-demo:cycle-1"
    assert second.case["case_id"] == first.case["case_id"]
    assert len(service.list_cases(case_kind="cycle")) == 1


def test_goal_compiler_assignment_context_keeps_uncertainty_and_budget_inputs() -> None:
    class _Compiler(_GoalServiceCompilerMixin):
        pass

    compiler = _Compiler()
    compiler._assignment_planning_compiler = AssignmentPlanningCompiler()

    assignment_context = compiler._build_assignment_plan_context(
        context={
            "assignment_id": "assignment-live-9",
            "backlog_item_id": "backlog-live-9",
            "lane_id": "lane-growth",
            "cycle_id": "cycle-daily-2",
            "goal_title": "Stabilize weekend demand assumptions",
            "goal_summary": "Keep growth work bounded while uncertainty remains open.",
            "strategy_mission": "Protect growth quality before scaling.",
            "strategy_lane_weights": {"lane-growth": 0.6},
            "strategy_strategic_uncertainties": [
                {
                    "uncertainty_id": "uncertainty-weekend-demand",
                    "statement": "Weekend demand model is still unverified.",
                    "scope": "strategy",
                    "impact_level": "high",
                    "review_by_cycle": "cycle-weekly-1",
                }
            ],
            "strategy_lane_budgets": [
                {
                    "lane_id": "lane-growth",
                    "budget_window": "next-2-cycles",
                    "target_share": 0.55,
                    "min_share": 0.4,
                    "max_share": 0.7,
                    "review_pressure": "high",
                    "force_include_reason": "Protect validated growth work while uncertainty is open.",
                }
            ],
            "strategy_constraints": {
                "strategic_uncertainties": [
                    {
                        "uncertainty_id": "uncertainty-weekend-demand",
                        "statement": "Weekend demand model is still unverified.",
                    }
                ],
                "lane_budgets": [
                    {
                        "lane_id": "lane-growth",
                        "budget_window": "next-2-cycles",
                        "force_include_reason": "Protect validated growth work while uncertainty is open.",
                    }
                ],
            },
        },
    )

    assert assignment_context["strategy_constraints"]["strategic_uncertainties"][0][
        "uncertainty_id"
    ] == "uncertainty-weekend-demand"
    assert assignment_context["strategy_constraints"]["lane_budgets"][0]["lane_id"] == (
        "lane-growth"
    )
    assert assignment_context["strategy_strategic_uncertainties"][0][
        "review_by_cycle"
    ] == "cycle-weekly-1"
    assert assignment_context["strategy_lane_budgets"][0]["force_include_reason"] == (
        "Protect validated growth work while uncertainty is open."
    )


def test_goal_compiler_assignment_context_accepts_typed_strategy_constraints() -> None:
    class _Compiler(_GoalServiceCompilerMixin):
        pass

    compiler = _Compiler()
    compiler._assignment_planning_compiler = AssignmentPlanningCompiler()

    typed_constraints = PlanningStrategyConstraints.from_context(
        {
            "strategy_constraints": SimpleNamespace(
                mission="Protect growth quality before scaling.",
                lane_weights={"lane-growth": 0.6},
                planning_policy=["prefer-evidence-before-external-move"],
                strategic_uncertainties=[
                    SimpleNamespace(
                        uncertainty_id="uncertainty-weekend-demand",
                        statement="Weekend demand model is still unverified.",
                        scope="strategy",
                        impact_level="high",
                        review_by_cycle="cycle-weekly-1",
                    ),
                ],
                lane_budgets=[
                    SimpleNamespace(
                        lane_id="lane-growth",
                        budget_window="next-2-cycles",
                        target_share=0.55,
                        min_share=0.4,
                        max_share=0.7,
                        review_pressure="high",
                        force_include_reason=(
                            "Protect validated growth work while uncertainty is open."
                        ),
                    ),
                ],
            ),
        },
    )

    assignment_context = compiler._build_assignment_plan_context(
        context={
            "assignment_id": "assignment-live-9",
            "backlog_item_id": "backlog-live-9",
            "lane_id": "lane-growth",
            "cycle_id": "cycle-daily-2",
            "goal_title": "Stabilize weekend demand assumptions",
            "goal_summary": "Keep growth work bounded while uncertainty remains open.",
            "strategy_constraints": typed_constraints,
        },
    )

    assert assignment_context["strategy_constraints"]["mission"] == (
        "Protect growth quality before scaling."
    )
    assert assignment_context["strategy_constraints"]["lane_weights"] == {
        "lane-growth": 0.6,
    }
    assert assignment_context["strategy_constraints"]["strategic_uncertainties"][0][
        "uncertainty_id"
    ] == "uncertainty-weekend-demand"
    assert assignment_context["strategy_lane_budgets"][0]["lane_id"] == "lane-growth"


def test_prediction_recommendation_executes_through_kernel(tmp_path) -> None:
    app = _build_predictions_app(tmp_path)
    client = TestClient(app)
    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]
    executable = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["action_kind"] == "system:update_mcp_client"
    )
    recommendation_id = executable["recommendation"]["recommendation_id"]

    payload = _execute_prediction_recommendation_direct(
        app,
        case_id=case_id,
        recommendation_id=recommendation_id,
    )
    assert payload["execution"]["phase"] == "completed"
    assert load_config(app.state.config_path).mcp.clients["desktop_windows"].enabled is True
    assert payload["detail"]["case"]["case_id"] == case_id
    refreshed = next(
        item
        for item in payload["detail"]["recommendations"]
        if item["recommendation"]["recommendation_id"] == recommendation_id
    )
    assert refreshed["recommendation"]["status"] == "executed"


def test_prediction_recommendation_coordinate_route_hands_off_to_main_brain(tmp_path) -> None:
    app = _build_predictions_app(tmp_path)
    client = TestClient(app)
    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]
    executable = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["action_kind"] == "manual:coordinate-main-brain"
    )
    recommendation_id = executable["recommendation"]["recommendation_id"]

    coordinated = client.post(
        f"/predictions/{case_id}/recommendations/{recommendation_id}/coordinate",
        json={"actor": "copaw-operator"},
    )

    assert coordinated.status_code == 200
    payload = coordinated.json()
    assert payload["detail"]["case"]["case_id"] == case_id
    assert payload["backlog_item_id"]
    assert payload["chat_thread_id"] == "industry-chat:industry-demo:execution-core"
    assert payload["chat_route"] == "/chat?threadId=industry-chat%3Aindustry-demo%3Aexecution-core"
    assert payload["coordination_reason"] in {"open-backlog", "cycle-inflight"}


def test_prediction_service_drops_retired_dispatch_goal_recommendations_on_startup(
    tmp_path,
) -> None:
    app = _build_predictions_app(
        tmp_path,
        seed_cases=[
            PredictionCaseRecord(
                case_id="case-retired-dispatch-goal",
                title="Retired dispatch goal",
                summary="Seed case for startup compat migration.",
                status="open",
            ),
        ],
        seed_recommendations=[
            PredictionRecommendationRecord(
                recommendation_id="legacy-dispatch-goal",
                case_id="case-retired-dispatch-goal",
                recommendation_type="plan_recommendation",
                title="派发目标“Stabilize outbound execution”",
                summary="当前范围内已存在目标“Stabilize outbound execution”，但尚未进入本案例的受治理执行链。",
                action_kind="system:dispatch_goal",
                executable=True,
                auto_eligible=True,
                status="proposed",
                target_goal_id="goal-prediction",
                target_agent_id="copaw-agent-runner",
                action_payload={
                    "goal_id": "goal-prediction",
                    "owner_agent_id": "copaw-agent-runner",
                    "execute": True,
                    "activate": True,
                },
                metadata={"goal_title": "Stabilize outbound execution"},
            ),
        ],
    )
    client = TestClient(app)

    retained = app.state.prediction_service._recommendation_repository.get_recommendation(
        "legacy-dispatch-goal",
    )

    assert retained is None

    detail = client.get("/predictions/case-retired-dispatch-goal")

    assert detail.status_code == 200
    payload = detail.json()
    assert all(
        item["recommendation"]["recommendation_id"] != "legacy-dispatch-goal"
        for item in payload["recommendations"]
    )


def test_prediction_service_drops_retired_dispatch_active_goals_recommendations_on_startup(
    tmp_path,
) -> None:
    app = _build_predictions_app(
        tmp_path,
        seed_cases=[
            PredictionCaseRecord(
                case_id="case-retired-dispatch-active-goals",
                title="Retired dispatch active goals",
                summary="Seed case for startup compat migration.",
                status="open",
            ),
        ],
        seed_recommendations=[
            PredictionRecommendationRecord(
                recommendation_id="legacy-dispatch-active-goals",
                case_id="case-retired-dispatch-active-goals",
                recommendation_type="plan_recommendation",
                title="批量派发当前 active goals",
                summary="旧批量 goal dispatch recommendation 应在启动时被清洗。",
                action_kind="system:dispatch_active_goals",
                executable=True,
                auto_eligible=True,
                status="proposed",
                metadata={"goal_title": "Stabilize outbound execution"},
            ),
        ],
    )

    retained = app.state.prediction_service._recommendation_repository.get_recommendation(
        "legacy-dispatch-active-goals",
    )

    assert retained is None


def test_prediction_recommendation_execute_route_is_retired(tmp_path) -> None:
    client = TestClient(_build_predictions_app(tmp_path))
    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]
    executable = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["action_kind"] == "manual:coordinate-main-brain"
    )
    recommendation_id = executable["recommendation"]["recommendation_id"]

    retired = client.post(
        f"/predictions/{case_id}/recommendations/{recommendation_id}/execute",
        json={"actor": "copaw-operator"},
    )

    assert retired.status_code == 404


def test_prediction_recommends_and_executes_missing_team_role_update(tmp_path) -> None:
    app = _build_predictions_app(tmp_path)
    app.state.workflow_run_repository.upsert_run(
        WorkflowRunRecord(
            run_id="run-visual-gap",
            template_id="visual-asset-flow",
            title="Creative asset delivery",
            summary="Need visual assets and image refinement before the next rollout.",
            status="blocked",
            industry_instance_id="industry-demo",
            preview_payload={
                "steps": [
                    {
                        "step_id": "visual-design-leaf",
                        "title": "Produce product visuals",
                        "summary": "Create and refine product images for the next rollout.",
                        "execution_mode": "leaf",
                        "owner_role_id": "execution-core",
                        "owner_agent_id": "copaw-agent-runner",
                    }
                ],
            },
        ),
    )
    client = TestClient(app)

    created = client.post(
        "/predictions",
        json={
            "title": "Visual gap review",
            "question": "Should the team add a dedicated visual design role now?",
            "summary": "The execution core is still carrying visual production work.",
            "owner_scope": "industry-demo-scope",
            "industry_instance_id": "industry-demo",
            "workflow_run_id": "run-visual-gap",
        },
    )
    assert created.status_code == 200
    created_payload = created.json()
    role_recommendation = next(
        item
        for item in created_payload["recommendations"]
        if item["recommendation"]["action_kind"] == "system:update_industry_team"
    )
    recommendation = role_recommendation["recommendation"]
    assert recommendation["metadata"]["gap_kind"] == "team_role_gap"
    assert recommendation["metadata"]["family_id"] == "image"
    assert recommendation["metadata"]["suggested_role_id"] == "visual-design"
    assert recommendation["action_payload"]["role"]["employment_mode"] == "career"

    execution_payload = _execute_prediction_recommendation_direct(
        app,
        case_id=created_payload["case"]["case_id"],
        recommendation_id=recommendation["recommendation_id"],
    )
    assert execution_payload["execution"]["phase"] == "completed"
    assert execution_payload["decision"]["status"] == "approved"
    assert execution_payload["decision"]["requested_by"] == "copaw-main-brain"
    assert execution_payload["decision"]["requires_human_confirmation"] is False

    prediction_detail = client.get(f"/predictions/{created_payload['case']['case_id']}")
    assert prediction_detail.status_code == 200
    prediction_detail_payload = prediction_detail.json()
    refreshed = next(
        item
        for item in prediction_detail_payload["recommendations"]
        if item["recommendation"]["recommendation_id"] == recommendation["recommendation_id"]
    )
    assert refreshed["recommendation"]["status"] == "executed"

    detail = app.state.industry_service.get_instance_detail("industry-demo")
    assert detail is not None
    visual_role = next(
        agent
        for agent in detail.team.agents
        if agent.role_id == "visual-design"
    )
    assert visual_role.role_name == "视觉设计专员"
    assert any(goal.get("owner_agent_id") == visual_role.agent_id for goal in detail.goals)


def test_reporting_surface_prediction_metrics(tmp_path) -> None:
    app = _build_predictions_app(tmp_path)
    client = TestClient(app)
    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]
    executable = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["action_kind"] == "system:update_mcp_client"
    )
    recommendation_id = executable["recommendation"]["recommendation_id"]

    review = client.post(
        f"/predictions/{case_id}/reviews",
        json={
            "recommendation_id": recommendation_id,
            "reviewer": "copaw-operator",
            "summary": "Dispatching the goal helped push the next move.",
            "outcome": "hit",
            "adopted": True,
            "benefit_score": 0.8,
        },
    )
    assert review.status_code == 200
    assert review.json()["stats"]["review_count"] == 1

    executed = _execute_prediction_recommendation_direct(
        app,
        case_id=case_id,
        recommendation_id=recommendation_id,
    )
    assert executed["execution"]["phase"] == "completed"

    reports = client.get("/runtime-center/reports")
    assert reports.status_code == 200
    weekly = next(item for item in reports.json() if item["window"] == "weekly")
    assert weekly["prediction_count"] >= 1
    assert weekly["recommendation_count"] >= 1
    assert weekly["review_count"] >= 1
    assert weekly["auto_execution_count"] == 0

    performance = client.get("/runtime-center/performance", params={"window": "weekly"})
    assert performance.status_code == 200
    metric_keys = {item["key"] for item in performance.json()["metrics"]}
    assert "prediction_hit_rate" in metric_keys
    assert "recommendation_adoption_rate" in metric_keys
    assert "recommendation_execution_benefit" in metric_keys
def test_prediction_remote_skill_trial_and_retirement_loop(
    tmp_path,
    monkeypatch,
) -> None:
    app = _build_predictions_app(
        tmp_path,
        enable_remote_curated_search=True,
    )
    client = TestClient(app)
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

    def _fake_install_skill_from_hub(*, bundle_url: str, version: str = "", enable: bool = True, overwrite: bool = False):
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

    capability_service._system_handler._skills._skill_service.install_skill_from_hub = _fake_install_skill_from_hub

    created = _create_prediction_case(client)
    case_id = created["case"]["case_id"]
    trial_recommendation = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind") == "underperforming_capability"
    )
    assert trial_recommendation["recommendation"]["metadata"]["search_queries"]
    assert trial_recommendation["recommendation"]["metadata"]["candidate"]["search_query"]
    candidate_id = trial_recommendation["recommendation"]["metadata"].get("candidate_id")
    assert isinstance(candidate_id, str) and candidate_id
    candidate_records = app.state.capability_candidate_service.list_candidates()
    assert any(item.candidate_id == candidate_id for item in candidate_records)
    recommendation_id = trial_recommendation["recommendation"]["recommendation_id"]

    execution_payload = _execute_prediction_recommendation_direct(
        app,
        case_id=case_id,
        recommendation_id=recommendation_id,
    )
    assert execution_payload["execution"]["phase"] == "completed"
    assert execution_payload["decision"]["status"] == "approved"
    assert execution_payload["decision"]["requested_by"] == "copaw-main-brain"
    assert execution_payload["decision"]["requires_human_confirmation"] is False

    detail = client.get(f"/predictions/{case_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    optimization_case = next(
        item
        for item in detail_payload["optimization_cases"]
        if item["gap_kind"] == "underperforming_capability"
    )
    refreshed = next(
        item
        for item in detail_payload["recommendations"]
        if item["recommendation"]["recommendation_id"] == recommendation_id
    )
    assert refreshed["recommendation"]["status"] == "executed"
    assert optimization_case["discovery_case_id"] == case_id
    assert optimization_case["gap_kind"] == "underperforming_capability"
    assert optimization_case["challenger"]["candidate_id"] == candidate_id
    assert optimization_case["challenger"]["donor_id"]
    assert optimization_case["trial_scope"]["scope_kind"] == "seat"
    assert optimization_case["trial_scope"]["scope_ref"] == "env-browser-primary"
    assert optimization_case["owner"]["agent_id"] == "industry-solution-lead-demo"
    assert optimization_case["evaluator_verdict"]["aggregate_verdict"] == "passed"
    assert optimization_case["planning_impact"]["future_review_pressure"] is False
    assert optimization_case["writeback_targets"] == [
        "planning_constraints",
        "donor_trust",
        "capability_portfolio_pressure",
        "future_discovery_pressure",
        "strategy_or_lane_reopen",
    ]
    trial_records = app.state.skill_trial_service.list_trials(candidate_id=candidate_id)
    assert len(trial_records) == 1
    assert trial_records[0].scope_ref == "env-browser-primary"
    assert trial_records[0].verdict == "passed"
    surface = app.state.agent_profile_service.get_capability_surface(
        "industry-solution-lead-demo",
    )
    assert "skill:nextgen_outreach" in surface["effective_capabilities"]
    assert "skill:legacy_outreach" not in surface["effective_capabilities"]

    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-nextgen-outreach-1",
            title="NextGen outreach completed",
            summary="Guarded desktop outreach completed without operator takeover.",
            task_type="execution",
            status="completed",
            owner_agent_id="industry-solution-lead-demo",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-nextgen-outreach-1",
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
            task_id="task-nextgen-outreach-1",
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
    second_payload = second_case.json()
    retirement = next(
        item
        for item in second_payload["recommendations"]
        if item["recommendation"]["metadata"].get("gap_kind") == "capability_retirement"
    )
    assert retirement["recommendation"]["action_kind"] == "system:apply_capability_lifecycle"
    assert retirement["recommendation"]["action_payload"]["decision_kind"] == "retire"
    assert retirement["recommendation"]["action_payload"]["candidate_id"] == candidate_id
    assert retirement["recommendation"]["action_payload"]["selected_scope"] == "seat"
    assert retirement["recommendation"]["action_payload"]["selected_seat_ref"] == (
        "env-browser-primary"
    )

    retirement_execution = _execute_prediction_recommendation_direct(
        app,
        case_id=second_payload["case"]["case_id"],
        recommendation_id=retirement["recommendation"]["recommendation_id"],
    )
    assert retirement_execution["execution"]["phase"] == "completed"
    retirement_projection = next(
        item
        for item in retirement_execution["detail"]["optimization_cases"]
        if item["gap_kind"] == "capability_retirement"
    )
    assert retirement_projection["discovery_case_id"] == second_payload["case"]["case_id"]
    assert retirement_projection["gap_kind"] == "capability_retirement"
    assert retirement_projection["baseline"]["capability_ids"] == [
        "skill:legacy_outreach",
    ]
    assert retirement_projection["challenger"]["candidate_id"] == candidate_id
    assert retirement_projection["evaluator_verdict"]["aggregate_verdict"] == "passed"
    assert retirement_projection["lifecycle_decision"]["decision_kind"] == "retire"
    assert retirement_projection["planning_impact"]["retirement_pressure"] is True
    assert retirement_projection["donor_trust_impact"]["retirement_count"] >= 1
    assert retirement_projection["rollback_route"]
    decision_records = app.state.skill_lifecycle_decision_service.list_decisions(
        candidate_id=candidate_id,
    )
    assert any(
        item.decision_kind == "retire" and item.to_stage == "retired"
        for item in decision_records
    )
    skill_service.delete_skill("legacy_outreach")
    skill_service.delete_skill("nextgen_outreach")


def test_predictions_api_assignment_gap_recommendation_uses_capability_lifecycle(
    tmp_path,
) -> None:
    app = _build_predictions_app(tmp_path)
    run = app.state.workflow_run_repository.get_run("run-desktop-gap")
    assert run is not None
    preview_payload = dict(run.preview_payload or {})
    dependencies = list(preview_payload.get("dependencies") or [])
    dependencies[0] = {
        **dict(dependencies[0]),
        "installed": True,
        "available": True,
        "enabled": True,
    }
    preview_payload["dependencies"] = dependencies
    preview_payload["missing_capability_ids"] = []
    preview_payload["assignment_gap_capability_ids"] = ["mcp:desktop_windows"]
    app.state.workflow_run_repository.upsert_run(
        run.model_copy(update={"preview_payload": preview_payload}),
    )
    client = TestClient(app)

    created = _create_prediction_case(client)
    recommendation = next(
        item
        for item in created["recommendations"]
        if item["recommendation"]["metadata"].get("capability_id") == "mcp:desktop_windows"
        and item["recommendation"]["target_agent_id"] == "industry-solution-lead-demo"
    )

    assert recommendation["recommendation"]["action_kind"] == "system:apply_capability_lifecycle"
    assert recommendation["recommendation"]["action_payload"]["decision_kind"] == "promote_to_role"
    assert recommendation["recommendation"]["action_payload"]["target_agent_id"] == (
        "industry-solution-lead-demo"
    )
    assert recommendation["recommendation"]["action_payload"]["target_capability_ids"] == [
        "mcp:desktop_windows",
    ]
