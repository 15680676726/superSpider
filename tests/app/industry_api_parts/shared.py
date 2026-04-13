# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sqlite3
import time
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.crons.repo import StateBackedJobRepository
from copaw.app.routers.goals import router as goals_router
from copaw.app.routers.industry import router as industry_router
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_session import SafeJSONSession
from copaw.app.runtime_center import (
    RuntimeCenterEvidenceQueryService,
    RuntimeCenterStateQueryService,
)
from copaw.agents.skills_hub import HubSkillResult
from copaw.capabilities.browser_runtime import BrowserRuntimeService
from copaw.capabilities import CapabilityMount, CapabilityService
from copaw.capabilities.skill_service import CapabilitySkillService
from copaw.capabilities.remote_skill_catalog import (
    CuratedSkillCatalogEntry,
    CuratedSkillCatalogSearchResponse,
    CuratedSkillCatalogSource,
)
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.goals import GoalService
from copaw.industry import (
    IndustryCapabilityRecommendation,
    IndustryDraftGenerator,
    IndustryDraftGoal,
    IndustryDraftPlan,
    IndustryDraftSchedule,
    IndustryPreviewRequest,
    IndustryRoleBlueprint,
    IndustryService,
    IndustryTeamBlueprint,
    IndustryProfile,
    canonicalize_industry_draft,
    compile_industry_schedule_seeds,
    industry_slug,
    normalize_industry_profile,
)
from copaw.industry.service import (
    _build_skillhub_query_candidates,
    _role_capability_family_ids,
    _standardize_recommendation_items,
)
from copaw.industry.service_context import build_industry_service_runtime_bindings
from copaw.kernel import (
    AgentProfileService,
    KernelDispatcher,
    KernelTaskStore,
    TaskDelegationService,
)
from copaw.predictions import PredictionService
from copaw.learning import (
    GrowthEvent,
    LearningEngine,
    LearningRuntimeBindings,
    LearningService,
    PatchExecutor,
)
from copaw.routines import RoutineService
from copaw.sop_kernel import FixedSopService
from copaw.state import (
    AgentProfileOverrideRecord,
    GoalOverrideRecord,
    IndustryInstanceRecord,
    SQLiteStateStore,
    TaskRecord,
    WorkContextService,
)
from copaw.state.reporting_service import StateReportingService
from copaw.state.strategy_memory_service import StateStrategyMemoryService
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteAgentRuntimeRepository,
    SqliteAgentThreadBindingRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteDecisionRequestRepository,
    SqliteExecutionRoutineRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingCycleRepository,
    SqliteOperatingLaneRepository,
    SqlitePredictionCaseRepository,
    SqlitePredictionRecommendationRepository,
    SqlitePredictionReviewRepository,
    SqlitePredictionScenarioRepository,
    SqlitePredictionSignalRepository,
    SqliteRoutineRunRepository,
    SqliteStrategyMemoryRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
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


class SlowTurnExecutor:
    def __init__(self, *, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds

    async def stream_request(self, request, **kwargs):
        await asyncio.sleep(self.delay_seconds)
        yield {
            "object": "message",
            "status": "completed",
            "request": request,
            "kwargs": kwargs,
        }


class FakeIndustryDraftGenerator:
    def describe(self) -> dict[str, str]:
        return {
            "provider_id": "fake-provider",
            "model": "fake-industry-draft",
        }

    async def generate(self, *, profile, owner_scope, media_context=None):
        return self.build_draft(profile, owner_scope)

    def build_draft(self, profile, owner_scope):
        slug = industry_slug(profile)
        raw_draft = IndustryDraftPlan(
            team=IndustryTeamBlueprint(
                team_id="",
                label=f"{profile.primary_label()} AI Draft",
                summary=(
                    f"Editable AI-generated team draft for {profile.primary_label()} in {profile.industry}."
                ),
                topology="lead-plus-support",
                agents=[
                    IndustryRoleBlueprint(
                        role_id="execution-core",
                        agent_id="copaw-agent-runner",
                        name="白泽执行中枢",
                        role_name="白泽执行中枢",
                        role_summary="Owns the operating brief and the next move.",
                        mission="Turn the brief into the next evidence-backed operating move.",
                        goal_kind="execution-core",
                        agent_class="business",
                        activation_mode="persistent",
                        suspendable=False,
                        reports_to=None,
                        risk_level="guarded",
                        environment_constraints=[],
                        allowed_capabilities=[],
                        evidence_expectations=[],
                    ),
                    IndustryRoleBlueprint(
                        role_id="researcher",
                        agent_id="",
                        name=f"{profile.primary_label()} Researcher",
                        role_name="Industry Researcher",
                        role_summary="Collects market and operating signals.",
                        mission="Return high-signal research for the execution core to act on.",
                        goal_kind="researcher",
                        agent_class="system",
                        activation_mode="persistent",
                        suspendable=False,
                        reports_to="execution-core",
                        risk_level="guarded",
                        environment_constraints=[],
                        allowed_capabilities=[],
                        evidence_expectations=[],
                    ),
                    IndustryRoleBlueprint(
                        role_id="solution-lead",
                        agent_id="",
                        name=f"{profile.primary_label()} Solution Lead",
                        role_name="Solution Lead",
                        role_summary="Shapes the offer and operating design.",
                        mission="Turn the brief into an operator-ready solution scope.",
                        goal_kind="solution",
                        agent_class="business",
                        activation_mode="persistent",
                        suspendable=False,
                        reports_to="execution-core",
                        risk_level="guarded",
                        environment_constraints=[],
                        allowed_capabilities=[],
                        evidence_expectations=[],
                    ),
                ],
            ),
            goals=[
                IndustryDraftGoal(
                    goal_id="execution-core-goal",
                    kind="execution-core",
                    owner_agent_id="copaw-agent-runner",
                    title=f"Operate {profile.primary_label()} as an industry team",
                    summary="Create the next operating brief and action path.",
                    plan_steps=[
                        "Review the current brief.",
                        "Choose the next operating move.",
                        "Return an evidence-backed recommendation.",
                    ],
                ),
                IndustryDraftGoal(
                    goal_id="research-goal",
                    kind="researcher",
                    owner_agent_id=f"industry-researcher-{slug}",
                    title=f"Research {profile.primary_label()} market signals",
                    summary="Collect domain, stakeholder, and operating signals.",
                    plan_steps=[
                        "Scan the current market context.",
                        "Summarize stakeholder needs.",
                    ],
                ),
                IndustryDraftGoal(
                    goal_id="solution-goal",
                    kind="solution",
                    owner_agent_id=f"industry-solution-lead-{slug}",
                    title=f"Shape {profile.primary_label()} solution scope",
                    summary="Define the next operator-ready scope decision.",
                    plan_steps=[
                        "Clarify the offer shape.",
                        "List dependencies and next design decisions.",
                    ],
                ),
            ],
            schedules=[
                IndustryDraftSchedule(
                    schedule_id="execution-core-review",
                    owner_agent_id="copaw-agent-runner",
                    title=f"{profile.primary_label()} 白泽执行中枢复盘",
                    summary="Recurring review for the team's execution core loop.",
                    cron="0 9 * * *",
                    timezone="UTC",
                    dispatch_mode="stream",
                ),
                IndustryDraftSchedule(
                    schedule_id="research-review",
                    owner_agent_id=f"industry-researcher-{slug}",
                    title=f"{profile.primary_label()} Research Review",
                    summary="Recurring research review.",
                    cron="0 10 * * 2",
                    timezone="UTC",
                    dispatch_mode="stream",
                ),
                IndustryDraftSchedule(
                    schedule_id="solution-review",
                    owner_agent_id=f"industry-solution-lead-{slug}",
                    title=f"{profile.primary_label()} Solution Review",
                    summary="Recurring solution review.",
                    cron="0 11 * * 4",
                    timezone="UTC",
                    dispatch_mode="final",
                ),
            ],
            generation_summary=(
                f"AI generated a contextual industry draft for {profile.primary_label()}."
            ),
        )
        return canonicalize_industry_draft(
            profile,
            raw_draft,
            owner_scope=owner_scope,
        )


class DesktopIndustryDraftGenerator(FakeIndustryDraftGenerator):
    def build_draft(self, profile, owner_scope):
        draft = super().build_draft(profile, owner_scope)
        for role in draft.team.agents:
            if role.role_id != "solution-lead":
                continue
            role.role_summary = "Handles customer follow-up through a desktop client and keeps the Excel delivery checklist current."
            role.mission = "Send messages in Windows desktop apps, switch windows, and update Excel results."
            role.allowed_capabilities = [
                *list(role.allowed_capabilities or []),
                "mcp:desktop_windows",
            ]
        for goal in draft.goals:
            if goal.kind != "solution":
                continue
            goal.plan_steps = [
                "Open the target conversation in the desktop client.",
                "Send the next follow-up message and record the result.",
                "Update the Excel delivery checklist.",
            ]
        return draft


class BrowserIndustryDraftGenerator(FakeIndustryDraftGenerator):
    def build_draft(self, profile, owner_scope):
        draft = super().build_draft(profile, owner_scope)
        for role in draft.team.agents:
            if role.role_id != "solution-lead":
                continue
            role.role_summary = "Owns browser-based login, form completion, and operations configuration in the customer portal."
            role.mission = "Complete login, form submission, and result verification through the web dashboard."
        for goal in draft.goals:
            if goal.kind != "solution":
                continue
            goal.plan_steps = [
                "Open the target site and sign in.",
                "Complete the form and submit the configuration.",
                "Verify the dashboard result and return evidence.",
            ]
        return draft


class HubSkillIndustryDraftGenerator(FakeIndustryDraftGenerator):
    def build_draft(self, profile, owner_scope):
        draft = super().build_draft(profile, owner_scope)
        for role in draft.team.agents:
            if role.role_id != "solution-lead":
                continue
            role.role_summary = "Owns Salesforce pipeline hygiene and CRM follow-up execution."
            role.mission = (
                "Use Salesforce to update leads, maintain CRM fields, and prepare operator follow-up."
            )
            role.allowed_capabilities = [
                *list(role.allowed_capabilities or []),
                "skill:salesforce",
            ]
        for goal in draft.goals:
            if goal.kind != "solution":
                continue
            goal.plan_steps = [
                "Review the Salesforce pipeline for the active account set.",
                "Update CRM records and note the next follow-up move.",
                "Return the operator-ready status summary.",
            ]
        return draft


def bootstrap_draft_goals(payload: dict) -> list[dict]:
    return list(payload.get("draft", {}).get("goals") or [])


def bootstrap_goal_ids(payload: dict) -> list[str]:
    return [
        str(item["goal_id"])
        for item in bootstrap_draft_goals(payload)
        if item.get("goal_id") is not None
    ]


def bootstrap_goal_by_owner(payload: dict, owner_agent_id: str) -> dict:
    return next(
        item
        for item in bootstrap_draft_goals(payload)
        if item.get("owner_agent_id") == owner_agent_id
    )


def bootstrap_schedule_summaries(payload: dict) -> list[dict]:
    return list(payload.get("schedule_summaries") or [])


def bootstrap_schedule_ids(payload: dict) -> list[str]:
    return [
        str(item["schedule_id"])
        for item in bootstrap_schedule_summaries(payload)
        if item.get("schedule_id") is not None
    ]


def bootstrap_schedule_by_role(payload: dict, role_id: str) -> dict:
    return next(
        item
        for item in bootstrap_schedule_summaries(payload)
        if item.get("industry_role_id") == role_id
        or item.get("spec_payload", {}).get("request", {}).get("industry_role_id") == role_id
    )


def _build_industry_app(
    tmp_path,
    *,
    draft_generator=None,
    turn_executor=None,
    enable_hub_recommendations=False,
    enable_curated_catalog=False,
) -> FastAPI:
    app = FastAPI()
    app.include_router(goals_router)
    app.include_router(industry_router)
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    session_backend = SafeJSONSession(database_path=tmp_path / "session-state.sqlite3")
    browser_runtime_service = BrowserRuntimeService(state_store)
    goal_repository = SqliteGoalRepository(state_store)
    goal_override_repository = SqliteGoalOverrideRepository(state_store)
    industry_instance_repository = SqliteIndustryInstanceRepository(state_store)
    strategy_memory_repository = SqliteStrategyMemoryRepository(state_store)
    operating_lane_repository = SqliteOperatingLaneRepository(state_store)
    backlog_item_repository = SqliteBacklogItemRepository(state_store)
    operating_cycle_repository = SqliteOperatingCycleRepository(state_store)
    assignment_repository = SqliteAssignmentRepository(state_store)
    agent_report_repository = SqliteAgentReportRepository(state_store)
    workflow_run_repository = SqliteWorkflowRunRepository(state_store)
    agent_profile_override_repository = SqliteAgentProfileOverrideRepository(
        state_store,
    )
    agent_runtime_repository = SqliteAgentRuntimeRepository(state_store)
    agent_thread_binding_repository = SqliteAgentThreadBindingRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    work_context_repository = SqliteWorkContextRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    prediction_case_repository = SqlitePredictionCaseRepository(state_store)
    prediction_scenario_repository = SqlitePredictionScenarioRepository(state_store)
    prediction_signal_repository = SqlitePredictionSignalRepository(state_store)
    prediction_recommendation_repository = SqlitePredictionRecommendationRepository(
        state_store,
    )
    prediction_review_repository = SqlitePredictionReviewRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    environment_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=environment_repository,
            session_repository=session_repository,
        ),
    )
    environment_service.set_session_repository(session_repository)
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        turn_executor=turn_executor or FakeTurnExecutor(),
        skill_service=CapabilitySkillService(),
    )
    work_context_service = WorkContextService(repository=work_context_repository)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        work_context_service=work_context_service,
    )
    dispatcher = KernelDispatcher(
        capability_service=capability_service,
        task_store=task_store,
    )
    learning_service = LearningService(
        engine=LearningEngine(tmp_path / "learning.db"),
        patch_executor=PatchExecutor(
            goal_override_repository=goal_override_repository,
            agent_profile_override_repository=agent_profile_override_repository,
        ),
        decision_request_repository=decision_request_repository,
        task_repository=task_repository,
        evidence_ledger=evidence_ledger,
    )
    strategy_memory_service = StateStrategyMemoryService(
        repository=strategy_memory_repository,
    )
    fixed_sop_service = FixedSopService(
        template_repository=SqliteFixedSopTemplateRepository(state_store),
        binding_repository=SqliteFixedSopBindingRepository(state_store),
        workflow_run_repository=workflow_run_repository,
        agent_report_repository=agent_report_repository,
        evidence_ledger=evidence_ledger,
    )
    routine_service = RoutineService(
        routine_repository=SqliteExecutionRoutineRepository(state_store),
        routine_run_repository=SqliteRoutineRunRepository(state_store),
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        kernel_dispatcher=dispatcher,
        state_store=state_store,
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
        learning_service=learning_service,
        strategy_memory_service=strategy_memory_service,
        industry_instance_repository=industry_instance_repository,
    )
    agent_profile_service = AgentProfileService(
        override_repository=agent_profile_override_repository,
        agent_runtime_repository=agent_runtime_repository,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        capability_service=capability_service,
        learning_service=learning_service,
        goal_service=goal_service,
        industry_instance_repository=industry_instance_repository,
        agent_thread_binding_repository=agent_thread_binding_repository,
    )
    reporting_service = StateReportingService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        goal_repository=goal_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        industry_instance_repository=industry_instance_repository,
        agent_profile_service=agent_profile_service,
        prediction_case_repository=prediction_case_repository,
        prediction_recommendation_repository=prediction_recommendation_repository,
        prediction_review_repository=prediction_review_repository,
    )
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
        workflow_run_repository=None,
        strategy_memory_service=strategy_memory_service,
        capability_service=capability_service,
        agent_profile_service=agent_profile_service,
        kernel_dispatcher=dispatcher,
    )
    state_query_service = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        schedule_repository=schedule_repository,
        goal_repository=goal_repository,
        goal_service=goal_service,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        agent_profile_service=agent_profile_service,
        work_context_repository=work_context_repository,
    )
    evidence_query_service = RuntimeCenterEvidenceQueryService(
        evidence_ledger=evidence_ledger,
    )
    industry_runtime_bindings = build_industry_service_runtime_bindings(
        state_store=state_store,
        kernel_dispatcher=dispatcher,
        operating_lane_repository=operating_lane_repository,
        backlog_item_repository=backlog_item_repository,
        operating_cycle_repository=operating_cycle_repository,
        assignment_repository=assignment_repository,
        agent_report_repository=agent_report_repository,
        agent_runtime_repository=agent_runtime_repository,
        agent_thread_binding_repository=agent_thread_binding_repository,
        schedule_repository=schedule_repository,
        strategy_memory_repository=strategy_memory_repository,
        workflow_run_repository=workflow_run_repository,
        prediction_case_repository=prediction_case_repository,
        prediction_scenario_repository=prediction_scenario_repository,
        prediction_signal_repository=prediction_signal_repository,
        prediction_recommendation_repository=prediction_recommendation_repository,
        prediction_review_repository=prediction_review_repository,
        browser_runtime_service=browser_runtime_service,
        memory_retain_service=None,
    )
    industry_service = IndustryService(
        goal_service=goal_service,
        industry_instance_repository=industry_instance_repository,
        session_backend=session_backend,
        goal_override_repository=goal_override_repository,
        agent_profile_override_repository=agent_profile_override_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        agent_profile_service=agent_profile_service,
        capability_service=capability_service,
        strategy_memory_service=strategy_memory_service,
        state_store=state_store,
        runtime_bindings=industry_runtime_bindings,
        draft_generator=draft_generator or FakeIndustryDraftGenerator(),
        enable_hub_recommendations=enable_hub_recommendations,
        enable_curated_skill_catalog=enable_curated_catalog,
        schedule_writer=StateBackedJobRepository(
            schedule_repository=schedule_repository,
        ),
        work_context_service=work_context_service,
    )
    fixed_sop_service._agent_report_repository = industry_service._agent_report_repository
    industry_service.set_prediction_service(prediction_service)
    goal_service.set_agent_profile_service(agent_profile_service)
    set_dispatcher_industry_service = getattr(dispatcher, "set_industry_service", None)
    if callable(set_dispatcher_industry_service):
        set_dispatcher_industry_service(industry_service)
    capability_service.set_agent_profile_service(agent_profile_service)
    capability_service.set_agent_profile_override_repository(
        agent_profile_override_repository,
    )
    capability_service.set_routine_service(routine_service)
    capability_service.set_fixed_sop_service(fixed_sop_service)
    capability_service.get_discovery_service().set_fixed_sop_service(fixed_sop_service)
    fixed_sop_service.set_routine_service(routine_service)
    learning_service.configure_bindings(
        LearningRuntimeBindings(
            industry_service=industry_service,
            capability_service=capability_service,
            kernel_dispatcher=dispatcher,
            fixed_sop_service=fixed_sop_service,
            agent_profile_service=agent_profile_service,
        ),
    )
    app.state.capability_service = capability_service
    app.state.goal_service = goal_service
    app.state.state_store = state_store
    app.state.goal_override_repository = goal_override_repository
    app.state.industry_instance_repository = industry_instance_repository
    app.state.agent_profile_override_repository = agent_profile_override_repository
    app.state.agent_runtime_repository = agent_runtime_repository
    app.state.agent_thread_binding_repository = agent_thread_binding_repository
    app.state.task_repository = task_repository
    app.state.task_runtime_repository = task_runtime_repository
    app.state.runtime_frame_repository = runtime_frame_repository
    app.state.work_context_repository = work_context_repository
    app.state.work_context_service = work_context_service
    app.state.decision_request_repository = decision_request_repository
    app.state.evidence_ledger = evidence_ledger
    app.state.learning_service = learning_service
    app.state.agent_profile_service = agent_profile_service
    app.state.state_query_service = state_query_service
    app.state.evidence_query_service = evidence_query_service
    app.state.kernel_dispatcher = dispatcher
    app.state.reporting_service = reporting_service
    app.state.strategy_memory_service = strategy_memory_service
    app.state.schedule_repository = schedule_repository
    app.state.operating_lane_repository = industry_service._operating_lane_repository
    app.state.backlog_item_repository = industry_service._backlog_item_repository
    app.state.operating_cycle_repository = industry_service._operating_cycle_repository
    app.state.assignment_repository = industry_service._assignment_repository
    app.state.agent_report_repository = industry_service._agent_report_repository
    app.state.operating_lane_service = industry_service._operating_lane_service
    app.state.backlog_service = industry_service._backlog_service
    app.state.operating_cycle_service = industry_service._operating_cycle_service
    app.state.assignment_service = industry_service._assignment_service
    app.state.agent_report_service = industry_service._agent_report_service
    app.state.browser_runtime_service = browser_runtime_service
    app.state.routine_service = routine_service
    app.state.fixed_sop_service = fixed_sop_service
    app.state.prediction_service = prediction_service
    app.state.session_backend = session_backend
    app.state.industry_service = industry_service
    return app


__all__ = [name for name in globals() if not name.startswith("__")]
