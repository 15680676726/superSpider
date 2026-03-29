# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.crons.repo import StateBackedJobRepository
from copaw.app.routers.capability_market import router as capability_market_router
from copaw.app.routers.goals import router as goals_router
from copaw.app.routers.industry import router as industry_router
from copaw.app.routers.workflow_templates import (
    router as workflow_templates_router,
    run_router as workflow_runs_router,
)
from copaw.capabilities import CapabilityService
from copaw.evidence import EvidenceLedger
from copaw.goals import GoalService
from copaw.industry import IndustryService
from copaw.industry.service_context import build_industry_service_runtime_bindings
from copaw.kernel import AgentProfileService, KernelDispatcher, KernelTaskStore
from copaw.state import SQLiteStateStore
from copaw.state.strategy_memory_service import StateStrategyMemoryService
from copaw.state.repositories import (
    SqliteAgentProfileOverrideRepository,
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteIndustryInstanceRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteStrategyMemoryRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkflowPresetRepository,
    SqliteWorkflowRunRepository,
    SqliteWorkflowTemplateRepository,
)
from copaw.state import WorkflowTemplateRecord
from copaw.workflows.models import WorkflowLaunchRequest
from copaw.workflows import WorkflowTemplateService
from copaw.industry import (
    IndustryDraftGoal,
    IndustryDraftPlan,
    IndustryDraftSchedule,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
    canonicalize_industry_draft,
    industry_slug,
)


class FakeTurnExecutor:
    async def stream_request(self, request, **kwargs):
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
                    title=f"{profile.primary_label()} control review",
                    summary="Recurring review for the control loop.",
                    cron="0 9 * * *",
                    timezone="UTC",
                    dispatch_mode="stream",
                ),
                IndustryDraftSchedule(
                    schedule_id="solution-review",
                    owner_agent_id=f"industry-solution-lead-{slug}",
                    title=f"{profile.primary_label()} solution review",
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


class FakeWorkflowEnvironmentService:
    def __init__(
        self,
        *,
        session_details: dict[str, dict[str, object]] | None = None,
        environment_details: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self._session_details = {
            key: dict(value)
            for key, value in dict(session_details or {}).items()
        }
        self._environment_details = {
            key: dict(value)
            for key, value in dict(environment_details or {}).items()
        }

    def get_session_detail(
        self,
        session_mount_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        return self._session_details.get(session_mount_id)

    def get_environment_detail(
        self,
        env_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        return self._environment_details.get(env_id)


def _build_workflow_app(tmp_path, *, environment_service=None) -> FastAPI:
    app = FastAPI()
    app.include_router(capability_market_router)
    app.include_router(goals_router)
    app.include_router(industry_router)
    app.include_router(workflow_templates_router)
    app.include_router(workflow_runs_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    goal_repository = SqliteGoalRepository(state_store)
    goal_override_repository = SqliteGoalOverrideRepository(state_store)
    industry_instance_repository = SqliteIndustryInstanceRepository(state_store)
    agent_profile_override_repository = SqliteAgentProfileOverrideRepository(
        state_store,
    )
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    strategy_memory_repository = SqliteStrategyMemoryRepository(state_store)
    workflow_preset_repository = SqliteWorkflowPresetRepository(state_store)
    workflow_template_repository = SqliteWorkflowTemplateRepository(state_store)
    workflow_run_repository = SqliteWorkflowRunRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    strategy_memory_service = StateStrategyMemoryService(
        repository=strategy_memory_repository,
    )
    capability_service = CapabilityService(
        turn_executor=FakeTurnExecutor(),
        agent_profile_override_repository=agent_profile_override_repository,
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
    industry_runtime_bindings = build_industry_service_runtime_bindings(
        state_store=state_store,
        schedule_repository=schedule_repository,
    )
    industry_service = IndustryService(
        goal_service=goal_service,
        industry_instance_repository=industry_instance_repository,
        goal_override_repository=goal_override_repository,
        agent_profile_override_repository=agent_profile_override_repository,
        evidence_ledger=evidence_ledger,
        capability_service=capability_service,
        strategy_memory_service=strategy_memory_service,
        state_store=state_store,
        runtime_bindings=industry_runtime_bindings,
        draft_generator=FakeIndustryDraftGenerator(),
        enable_hub_recommendations=False,
        enable_curated_skill_catalog=False,
        schedule_writer=StateBackedJobRepository(
            schedule_repository=schedule_repository,
        ),
    )
    agent_profile_service = AgentProfileService(
        override_repository=agent_profile_override_repository,
        industry_instance_repository=industry_instance_repository,
        capability_service=capability_service,
    )
    workflow_template_service = WorkflowTemplateService(
        workflow_template_repository=workflow_template_repository,
        workflow_run_repository=workflow_run_repository,
        workflow_preset_repository=workflow_preset_repository,
        goal_service=goal_service,
        goal_override_repository=goal_override_repository,
        schedule_repository=schedule_repository,
        industry_instance_repository=industry_instance_repository,
        strategy_memory_service=strategy_memory_service,
        task_repository=task_repository,
        decision_request_repository=decision_request_repository,
        agent_profile_override_repository=agent_profile_override_repository,
        agent_profile_service=agent_profile_service,
        evidence_ledger=evidence_ledger,
        capability_service=capability_service,
        schedule_writer=StateBackedJobRepository(
            schedule_repository=schedule_repository,
        ),
        environment_service=environment_service,
    )

    app.state.goal_service = goal_service
    app.state.industry_service = industry_service
    app.state.workflow_template_service = workflow_template_service
    app.state.workflow_template_repository = workflow_template_repository
    app.state.workflow_preset_repository = workflow_preset_repository
    app.state.workflow_run_repository = workflow_run_repository
    app.state.industry_instance_repository = industry_instance_repository
    app.state.strategy_memory_service = strategy_memory_service
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    app.state.agent_profile_service = agent_profile_service
    app.state.environment_service = environment_service
    capability_service.set_agent_profile_service(agent_profile_service)
    return app


def _launch_workflow_via_service(
    client: TestClient,
    *,
    template_id: str,
    industry_instance_id: str,
    parameters: dict[str, object],
    owner_agent_id: str | None = None,
    preset_id: str | None = None,
    environment_id: str | None = None,
    session_mount_id: str | None = None,
    execute: bool = False,
):
    return asyncio.run(
        client.app.state.workflow_template_service.launch_template(
            template_id,
            WorkflowLaunchRequest(
                industry_instance_id=industry_instance_id,
                owner_agent_id=owner_agent_id,
                preset_id=preset_id,
                environment_id=environment_id,
                session_mount_id=session_mount_id,
                parameters=parameters,
                activate=True,
                execute=execute,
            ),
        )
    )


def _bootstrap_industry(client: TestClient) -> str:
    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Industrial Equipment",
            "company_name": "Northwind Robotics",
            "product": "factory monitoring copilots",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": preview_payload["draft"],
            "auto_activate": True,
            "auto_dispatch": False,
            "execute": False,
        },
    )
    assert bootstrap.status_code == 200
    return bootstrap.json()["team"]["team_id"]


def _industry_role_agent_id(client: TestClient, instance_id: str, role_id: str) -> str:
    record = client.app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    for agent in list((record.team_payload or {}).get("agents") or []):
        if not isinstance(agent, dict):
            continue
        if agent.get("role_id") == role_id and str(agent.get("agent_id") or "").strip():
            return str(agent["agent_id"])
    raise AssertionError(f"role '{role_id}' was not found in industry team")


def _grant_capability_to_agent(
    client: TestClient,
    *,
    agent_id: str,
    capability_ids: list[str],
) -> None:
    capability_service = client.app.state.capability_service
    agent_profile_service = client.app.state.agent_profile_service
    original_get_capability = capability_service.get_capability
    original_get_surface = agent_profile_service.get_capability_surface
    granted = set(capability_ids)

    def patched_get_capability(capability_id: str):
        if capability_id in granted:
            return SimpleNamespace(id=capability_id, enabled=True)
        return original_get_capability(capability_id)

    def patched_get_capability_surface(target_agent_id: str):
        payload = dict(original_get_surface(target_agent_id) or {})
        if target_agent_id != agent_id:
            return payload
        effective = {
            str(item)
            for item in list(payload.get("effective_capabilities") or [])
            if str(item).strip()
        }
        baseline = {
            str(item)
            for item in list(payload.get("baseline_capabilities") or [])
            if str(item).strip()
        }
        effective.update(granted)
        payload["effective_capabilities"] = sorted(effective)
        payload["baseline_capabilities"] = sorted(baseline)
        return payload

    capability_service.get_capability = patched_get_capability
    agent_profile_service.get_capability_surface = patched_get_capability_surface


def _desktop_host_preflight_detail(
    *,
    environment_id: str = "env-desktop-host",
    session_mount_id: str = "session-desktop-host",
    continuity_status: str = "attached",
    continuity_source: str = "live-handle",
    access_mode: str = "writer",
    lease_class: str = "exclusive-writer",
    handoff_state: str | None = None,
    handoff_reason: str | None = None,
    recovery_status: str = "attached",
    recovery_recoverable: bool = True,
    recovery_note: str = "Live handle is mounted in the current runtime host.",
    active_alert_families: list[str] | None = None,
    host_blocker_family: str | None = None,
    host_blocker_response: str | None = None,
    current_gap_or_blocker: str | None = None,
    active_window_ref: str | None = "window:desktop-outreach",
    writer_lock_scope: str | None = "window:desktop-outreach",
    coordination_severity: str = "clear",
    coordination_reason: str | None = None,
    recommended_scheduler_action: str = "continue",
) -> dict[str, object]:
    gap = current_gap_or_blocker or handoff_reason
    mutation_ready = (
        continuity_status in {"attached", "restorable", "same-host-other-process"}
        and access_mode == "writer"
        and active_window_ref is not None
        and writer_lock_scope is not None
    )
    return {
        "environment_id": environment_id,
        "session_mount_id": session_mount_id,
        "host_companion_session": {
            "session_mount_id": session_mount_id,
            "environment_id": environment_id,
            "continuity_status": continuity_status,
            "continuity_source": continuity_source,
            "locality": {
                "same_host": True,
                "same_process": False,
                "startup_recovery_required": handoff_state in {
                    "active",
                    "manual-only-terminal",
                },
            },
        },
        "host_twin": {
            "projection_kind": "host_twin_projection",
            "is_projection": True,
            "is_truth_store": False,
            "environment_id": environment_id,
            "session_mount_id": session_mount_id,
            "continuity": {
                "status": continuity_status,
                "valid": continuity_status in {"attached", "restorable"},
                "continuity_source": continuity_source,
                "resume_kind": (
                    "resume-runtime" if continuity_status == "attached" else "fresh"
                ),
                "requires_human_return": handoff_state in {"active", "manual-only-terminal"},
            },
            "legal_recovery": {
                "path": "handoff" if handoff_state else "resume",
                "resume_kind": (
                    "resume-runtime" if recovery_status == "attached" else "fresh"
                ),
                "checkpoint_ref": "checkpoint:desktop-host" if handoff_state else None,
                "return_condition": "human-return" if handoff_state else None,
                "verification_channel": "runtime-center-self-check",
            },
            "active_blocker_families": list(active_alert_families or []),
            "latest_blocking_event": {
                "event_family": host_blocker_family,
                "recommended_runtime_response": host_blocker_response,
                "surface_refs": [active_window_ref] if active_window_ref else [],
            },
            "execution_mutation_ready": {
                "desktop_app": mutation_ready,
                "browser": False,
                "file_docs": False,
            },
            "app_family_twins": {
                "office_document": {
                    "active": active_window_ref is not None,
                    "family_kind": "office_document",
                    "surface_ref": active_window_ref,
                    "contract_status": (
                        "verified-writer" if mutation_ready else "blocked"
                    ),
                    "family_scope_ref": "app:excel" if active_window_ref else None,
                    "writer_lock_scope": writer_lock_scope,
                },
                "desktop_specialized": {
                    "active": active_window_ref is not None,
                    "family_kind": "desktop_specialized",
                    "surface_ref": active_window_ref,
                    "contract_status": (
                        "verified-writer" if mutation_ready else "blocked"
                    ),
                    "family_scope_ref": "app:desktop",
                },
            },
            "coordination": {
                "seat_owner_ref": "ops-agent",
                "workspace_owner_ref": "ops-agent",
                "writer_owner_ref": "ops-agent" if mutation_ready else None,
                "candidate_seat_refs": [environment_id],
                "selected_seat_ref": environment_id,
                "seat_selection_policy": "sticky-active-seat",
                "contention_forecast": {
                    "severity": coordination_severity,
                    "reason": coordination_reason or gap or "host coordination is clear",
                },
                "legal_owner_transition": {
                    "allowed": handoff_state is None,
                    "reason": (
                        "human handoff is still active"
                        if handoff_state
                        else "no ownership transfer required"
                    ),
                },
                "recommended_scheduler_action": recommended_scheduler_action,
                "expected_release_at": None,
            },
            "scheduler_inputs": {
                "active_blocker_family": host_blocker_family,
                "requires_human_return": handoff_state in {"active", "manual-only-terminal"},
                "recommended_scheduler_action": recommended_scheduler_action,
            },
            "recovery_inputs": {
                "pending_recovery_families": (
                    [host_blocker_family]
                    if host_blocker_family is not None
                    else []
                ),
            },
            "host_companion_session": {
                "session_mount_id": session_mount_id,
                "environment_id": environment_id,
                "continuity_status": continuity_status,
                "continuity_source": continuity_source,
                "locality": {
                    "same_host": True,
                    "same_process": False,
                    "startup_recovery_required": handoff_state in {
                        "active",
                        "manual-only-terminal",
                    },
                },
            },
        },
    }


def _browser_host_preflight_detail(
    *,
    environment_id: str = "env-browser-host",
    session_mount_id: str = "session-browser-host",
    continuity_status: str = "attached",
    continuity_source: str = "live-handle",
    active_blocker_families: list[str] | None = None,
    coordination_severity: str = "clear",
    coordination_reason: str | None = None,
    recommended_scheduler_action: str = "continue",
) -> dict[str, object]:
    return {
        "environment_id": environment_id,
        "session_mount_id": session_mount_id,
        "host_companion_session": {
            "session_mount_id": session_mount_id,
            "environment_id": environment_id,
            "continuity_status": continuity_status,
            "continuity_source": continuity_source,
            "locality": {
                "same_host": True,
                "same_process": False,
                "startup_recovery_required": False,
            },
        },
        "host_twin": {
            "projection_kind": "host_twin_projection",
            "is_projection": True,
            "is_truth_store": False,
            "environment_id": environment_id,
            "session_mount_id": session_mount_id,
            "continuity": {
                "status": continuity_status,
                "valid": continuity_status in {"attached", "restorable"},
                "continuity_source": continuity_source,
                "resume_kind": (
                    "resume-runtime" if continuity_status == "attached" else "fresh"
                ),
                "requires_human_return": False,
            },
            "legal_recovery": {
                "path": "resume",
                "resume_kind": "resume-runtime",
                "checkpoint_ref": None,
                "return_condition": None,
                "verification_channel": "runtime-center-self-check",
            },
            "active_blocker_families": list(active_blocker_families or []),
            "latest_blocking_event": {
                "event_family": None,
                "recommended_runtime_response": None,
                "surface_refs": ["browser:web:main"],
            },
            "execution_mutation_ready": {
                "browser": True,
                "desktop_app": False,
                "file_docs": False,
            },
            "app_family_twins": {
                "browser_backoffice": {
                    "active": True,
                    "family_kind": "browser_backoffice",
                    "surface_ref": "browser:web:main",
                    "contract_status": "verified-writer",
                    "family_scope_ref": "site:jd:seller-center",
                },
            },
            "coordination": {
                "seat_owner_ref": "ops-agent",
                "workspace_owner_ref": "ops-agent",
                "writer_owner_ref": "ops-agent",
                "candidate_seat_refs": [environment_id],
                "selected_seat_ref": environment_id,
                "seat_selection_policy": "sticky-active-seat",
                "contention_forecast": {
                    "severity": coordination_severity,
                    "reason": coordination_reason or "browser coordination is clear",
                },
                "legal_owner_transition": {
                    "allowed": True,
                    "reason": "no ownership transfer required",
                },
                "recommended_scheduler_action": recommended_scheduler_action,
                "expected_release_at": None,
            },
            "scheduler_inputs": {
                "active_blocker_family": None,
                "requires_human_return": False,
                "recommended_scheduler_action": recommended_scheduler_action,
            },
            "recovery_inputs": {
                "pending_recovery_families": [],
            },
            "host_companion_session": {
                "session_mount_id": session_mount_id,
                "environment_id": environment_id,
                "continuity_status": continuity_status,
                "continuity_source": continuity_source,
                "locality": {
                    "same_host": True,
                    "same_process": False,
                    "startup_recovery_required": False,
                },
            },
        },
    }


def test_workflow_templates_list_and_preview(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)

    listing = client.get("/workflow-templates")
    assert listing.status_code == 200
    payload = listing.json()
    template_ids = [item["template"]["template_id"] for item in payload]
    assert "industry-daily-control-loop" in template_ids
    daily_loop = next(
        item
        for item in payload
        if item["template"]["template_id"] == "industry-daily-control-loop"
    )
    assert daily_loop["dependency_status"]["system:dispatch_query"] is True

    preview = client.post(
        "/workflow-templates/industry-daily-control-loop/preview",
        json={
            "industry_instance_id": instance_id,
            "parameters": {
                "business_goal": "Push the next operating move",
                "daily_review_time": "0 8 * * *",
                "timezone": "UTC",
            },
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["industry_instance_id"] == instance_id
    assert preview_payload["strategy_memory"]["scope_type"] == "industry"
    assert preview_payload["strategy_memory"]["north_star"]
    assert preview_payload["strategy_memory"]["priority_order"]
    assert len(preview_payload["steps"]) == 3
    assert preview_payload["steps"][0]["execution_mode"] == "control"
    signal_step = next(
        step for step in preview_payload["steps"] if step["step_id"] == "research-goal"
    )
    assert signal_step["owner_role_id"] == "solution-lead"
    assert signal_step["owner_role_candidates"] == [
        "solution-lead",
        "researcher",
        "execution-core",
    ]


def test_workflow_preview_exposes_install_template_routes(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))

    preview = client.post(
        "/workflow-templates/desktop-outreach-smoke/preview",
        json={
            "parameters": {
                "target_application": "Desktop app",
                "recipient_name": "Target contact",
                "message_text": "Draft message",
            },
        },
    )

    assert preview.status_code == 200
    payload = preview.json()
    dependency = next(
        item
        for item in payload["dependencies"]
        if item["capability_id"] == "mcp:desktop_windows"
    )
    assert dependency["install_templates"][0]["template_id"] == "desktop-windows"
    assert dependency["install_templates"][0]["routes"]["market"] == (
        "/capability-market?tab=install-templates&template=desktop-windows"
    )
    assert dependency["install_templates"][0]["routes"]["install"] == (
        "/api/capability-market/install-templates/desktop-windows/install"
    )
    if not dependency["installed"]:
        assert "mcp:desktop_windows" in payload["missing_capability_ids"]


def test_workflow_presets_can_be_created_and_applied(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)

    created = client.post(
        "/workflow-templates/industry-daily-control-loop/presets",
        json={
            "name": "Morning push",
            "industry_scope": instance_id,
            "created_by": "copaw-operator",
            "parameters": {
                "business_goal": "Stabilize the morning operating move",
                "daily_review_time": "0 7 * * *",
                "timezone": "UTC",
            },
        },
    )

    assert created.status_code == 201
    preset_payload = created.json()
    assert preset_payload["template_id"] == "industry-daily-control-loop"
    assert preset_payload["parameter_overrides"]["daily_review_time"] == "0 7 * * *"

    listing = client.get(
        "/workflow-templates/industry-daily-control-loop/presets",
        params={"industry_instance_id": instance_id},
    )
    assert listing.status_code == 200
    assert any(item["id"] == preset_payload["id"] for item in listing.json())

    preview = client.post(
        "/workflow-templates/industry-daily-control-loop/preview",
        json={
            "industry_instance_id": instance_id,
            "preset_id": preset_payload["id"],
            "parameters": {
                "business_goal": "Override just the goal line",
            },
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["parameters"]["business_goal"] == "Override just the goal line"
    assert preview_payload["parameters"]["daily_review_time"] == "0 7 * * *"


def test_workflow_template_launch_route_is_retired(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)

    launched = client.post(
        "/workflow-templates/industry-weekly-research-synthesis/launch",
        json={
            "industry_instance_id": instance_id,
            "parameters": {
                "focus_area": "channel conversion",
                "weekly_review_cron": "0 12 * * 2",
                "timezone": "UTC",
            },
            "activate": True,
            "execute": False,
        },
    )
    assert launched.status_code == 404


def test_workflow_template_service_launch_materializes_run(tmp_path) -> None:
    detail = _browser_host_preflight_detail()
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(detail["session_mount_id"]): detail},
    )
    client = TestClient(_build_workflow_app(tmp_path, environment_service=environment_service))
    instance_id = _bootstrap_industry(client)

    launched = _launch_workflow_via_service(
        client,
        template_id="industry-weekly-research-synthesis",
        industry_instance_id=instance_id,
        environment_id=str(detail["environment_id"]),
        session_mount_id=str(detail["session_mount_id"]),
        parameters={
            "focus_area": "channel conversion",
            "weekly_review_cron": "0 12 * * 2",
            "timezone": "UTC",
        },
    )
    assert launched.run["template_id"] == "industry-weekly-research-synthesis"
    assert launched.run["status"] == "planned"
    assert len(launched.goals) == 2
    assert len(launched.schedules) == 1

    run_id = launched.run["run_id"]
    run_detail = client.get(f"/workflow-runs/{run_id}")
    assert run_detail.status_code == 200
    detail_payload = run_detail.json()
    assert detail_payload["run"]["run_id"] == run_id
    assert detail_payload["template"]["template_id"] == "industry-weekly-research-synthesis"
    assert detail_payload["routes"]["run"] == f"/api/workflow-runs/{run_id}"
    assert "resume" not in (detail_payload.get("routes") or {})
    assert detail_payload["diagnosis"]["status"] == "planned"
    assert detail_payload["diagnosis"]["host_snapshot"]["coordination"][
        "recommended_scheduler_action"
    ] == "continue"
    assert len(detail_payload["step_execution"]) == 3
    assert any(
        item["step_id"] == "weekly-research-goal"
        and item["status"] in {"planned", "running", "completed"}
        for item in detail_payload["step_execution"]
    )
    schedule_payload = detail_payload["schedules"][0]["spec_payload"]
    assert schedule_payload["meta"]["environment_id"] == detail["environment_id"]
    assert schedule_payload["meta"]["session_mount_id"] == detail["session_mount_id"]
    assert schedule_payload["meta"]["host_requirement"]["app_family"] == "browser_backoffice"
    assert schedule_payload["meta"]["host_snapshot"]["coordination"][
        "recommended_scheduler_action"
    ] == "continue"


def test_workflow_schedule_meta_uses_canonical_host_refs_when_launch_only_has_session_mount(
    tmp_path,
) -> None:
    detail = _browser_host_preflight_detail(
        environment_id="env:session:session:web:main",
        session_mount_id="session:web:main",
    )
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(detail["session_mount_id"]): detail},
    )
    client = TestClient(_build_workflow_app(tmp_path, environment_service=environment_service))
    instance_id = _bootstrap_industry(client)

    launched = _launch_workflow_via_service(
        client,
        template_id="industry-weekly-research-synthesis",
        industry_instance_id=instance_id,
        session_mount_id=str(detail["session_mount_id"]),
        parameters={
            "focus_area": "channel conversion",
            "weekly_review_cron": "0 12 * * 2",
            "timezone": "UTC",
        },
    )

    schedule_payload = launched.schedules[0]["spec_payload"]
    assert schedule_payload["meta"]["environment_ref"] == detail["environment_id"]
    assert schedule_payload["meta"]["environment_id"] == detail["environment_id"]
    assert schedule_payload["meta"]["session_mount_id"] == detail["session_mount_id"]
    assert schedule_payload["meta"]["host_snapshot"]["environment_id"] == detail["environment_id"]

def test_workflow_run_step_detail_stays_read_only_and_service_resume_rehydrates_missing_links(
    tmp_path,
) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)

    launched = _launch_workflow_via_service(
        client,
        template_id="industry-weekly-research-synthesis",
        industry_instance_id=instance_id,
        parameters={
            "focus_area": "channel conversion",
            "weekly_review_cron": "0 12 * * 2",
            "timezone": "UTC",
        },
    )
    run_id = launched.run["run_id"]

    detail = client.get(f"/workflow-runs/{run_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert "resume" not in (detail_payload.get("routes") or {})
    goal_step = next(
        item
        for item in detail_payload["step_execution"]
        if item["kind"] == "goal" and item["linked_goal_ids"]
    )
    schedule_step = next(
        item
        for item in detail_payload["step_execution"]
        if item["kind"] == "schedule" and item["linked_schedule_ids"]
    )

    step_detail = client.get(f"/workflow-runs/{run_id}/steps/{goal_step['step_id']}")
    assert step_detail.status_code == 200
    step_detail_payload = step_detail.json()
    assert step_detail_payload["step"]["step_id"] == goal_step["step_id"]
    assert step_detail_payload["linked_goals"]
    assert step_detail_payload["routes"]["run"] == f"/api/workflow-runs/{run_id}"
    assert "resume" not in (step_detail_payload.get("routes") or {})

    run_record = client.app.state.workflow_run_repository.get_run(run_id)
    assert run_record is not None
    metadata = dict(run_record.metadata or {})
    step_seed = []
    for item in list(metadata.get("step_execution_seed") or []):
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        if copied.get("step_id") == goal_step["step_id"]:
            copied["linked_goal_ids"] = []
        if copied.get("step_id") == schedule_step["step_id"]:
            copied["linked_schedule_ids"] = []
        step_seed.append(copied)
    client.app.state.workflow_run_repository.upsert_run(
        run_record.model_copy(
            update={
                "goal_ids": [
                    item
                    for item in list(run_record.goal_ids or [])
                    if item not in set(goal_step["linked_goal_ids"])
                ],
                "schedule_ids": [
                    item
                    for item in list(run_record.schedule_ids or [])
                    if item not in set(schedule_step["linked_schedule_ids"])
                ],
                "metadata": {
                    **metadata,
                    "step_execution_seed": step_seed,
                },
            },
        ),
    )

    retired = client.post(
        f"/workflow-runs/{run_id}/resume",
        json={"actor": "copaw-operator"},
    )
    assert retired.status_code == 404

    resumed = asyncio.run(
        client.app.state.workflow_template_service.resume_run(
            run_id,
            actor="copaw-operator",
        )
    )
    assert (dict(resumed.run or {}).get("metadata") or {}).get("resume_count") == 1
    resumed_goal_step = next(
        item
        for item in resumed.step_execution
        if item.step_id == goal_step["step_id"]
    )
    resumed_schedule_step = next(
        item
        for item in resumed.step_execution
        if item.step_id == schedule_step["step_id"]
    )
    assert resumed_goal_step.linked_goal_ids
    assert resumed_schedule_step.linked_schedule_ids

    resumed_step_detail = client.get(
        f"/workflow-runs/{run_id}/steps/{goal_step['step_id']}",
    )
    assert resumed_step_detail.status_code == 200
    resumed_step_detail_payload = resumed_step_detail.json()
    assert resumed_step_detail_payload["linked_goals"]
    assert resumed_step_detail_payload["routes"]["step"] == (
        f"/api/workflow-runs/{run_id}/steps/{goal_step['step_id']}"
    )


def test_workflow_preview_declares_host_requirements_and_phase6_coordination_blocker(
    tmp_path,
) -> None:
    detail = _desktop_host_preflight_detail(
        coordination_severity="blocked",
        coordination_reason="office writer ownership is contested",
        recommended_scheduler_action="handoff",
        active_alert_families=[],
        host_blocker_family=None,
        host_blocker_response=None,
    )
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(detail["session_mount_id"]): detail},
    )
    client = TestClient(
        _build_workflow_app(tmp_path, environment_service=environment_service),
    )
    instance_id = _bootstrap_industry(client)
    solution_lead_agent_id = _industry_role_agent_id(client, instance_id, "solution-lead")
    _grant_capability_to_agent(
        client,
        agent_id=solution_lead_agent_id,
        capability_ids=["mcp:desktop_windows"],
    )
    repository = client.app.state.workflow_template_repository
    repository.upsert_template(
        WorkflowTemplateRecord(
            template_id="phase6-office-document-smoke",
            title="Phase 6 Office Document Smoke",
            summary="Use office document host facts for a mutating desktop step.",
            category="desktop-ops",
            status="active",
            version="v1",
            owner_role_id="solution-lead",
            suggested_role_ids=["solution-lead"],
            dependency_capability_ids=["system:dispatch_query", "mcp:desktop_windows"],
            step_specs=[
                {
                    "id": "office-document-leaf",
                    "kind": "goal",
                    "execution_mode": "leaf",
                    "owner_role_id": "solution-lead",
                    "title": "Update the weekly workbook",
                    "summary": "Mutate the active office document.",
                    "required_capability_ids": [
                        "system:dispatch_query",
                        "mcp:desktop_windows",
                    ],
                    "environment_preflight": {
                        "surface_kind": "desktop",
                        "mutating": True,
                        "app_family": "office_document",
                    },
                },
            ],
        ),
    )

    preview = client.post(
        "/workflow-templates/phase6-office-document-smoke/preview",
        json={
            "industry_instance_id": instance_id,
            "environment_id": detail["environment_id"],
            "session_mount_id": detail["session_mount_id"],
        },
    )

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["host_requirements"][0]["step_id"] == "office-document-leaf"
    assert payload["host_requirements"][0]["app_family"] == "office_document"
    assert payload["host_requirements"][0]["surface_kind"] == "desktop"
    assert any(
        item["code"] == "host-twin-contention-forecast-blocked"
        for item in payload["launch_blockers"]
    )


def test_workflow_run_diagnosis_keeps_host_snapshot_and_resume_rechecks_live_host_truth(
    tmp_path,
) -> None:
    initial_detail = _desktop_host_preflight_detail(
        coordination_severity="clear",
        recommended_scheduler_action="continue",
        active_alert_families=[],
        host_blocker_family=None,
        host_blocker_response=None,
    )
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(initial_detail["session_mount_id"]): initial_detail},
    )
    client = TestClient(
        _build_workflow_app(tmp_path, environment_service=environment_service),
    )
    instance_id = _bootstrap_industry(client)
    solution_lead_agent_id = _industry_role_agent_id(client, instance_id, "solution-lead")
    _grant_capability_to_agent(
        client,
        agent_id=solution_lead_agent_id,
        capability_ids=["mcp:desktop_windows"],
    )

    launched = _launch_workflow_via_service(
        client,
        template_id="desktop-outreach-smoke",
        industry_instance_id=instance_id,
        environment_id=str(initial_detail["environment_id"]),
        session_mount_id=str(initial_detail["session_mount_id"]),
        parameters={
            "target_application": "Excel",
            "recipient_name": "Target contact",
            "message_text": "Prepare the weekly follow-up draft.",
        },
    )
    run_id = launched.run["run_id"]
    assert launched.diagnosis.host_snapshot["coordination"]["recommended_scheduler_action"] == (
        "continue"
    )
    assert launched.diagnosis.host_snapshot["host_companion_session"][
        "continuity_status"
    ] == "attached"
    assert launched.diagnosis.host_snapshot["host_twin_summary"]["host_companion_status"] == "attached"
    assert launched.diagnosis.host_snapshot["host_twin_summary"]["seat_count"] == 1

    environment_service._session_details[str(initial_detail["session_mount_id"])] = (
        _desktop_host_preflight_detail(
            environment_id=str(initial_detail["environment_id"]),
            session_mount_id=str(initial_detail["session_mount_id"]),
            coordination_severity="blocked",
            coordination_reason="office writer ownership is contested",
            recommended_scheduler_action="handoff",
            active_alert_families=[],
            host_blocker_family=None,
            host_blocker_response=None,
        )
    )

    with pytest.raises(ValueError):
        asyncio.run(
            client.app.state.workflow_template_service.resume_run(
                run_id,
                actor="copaw-operator",
            ),
        )

    run_detail = client.get(f"/workflow-runs/{run_id}")
    assert run_detail.status_code == 200
    detail_payload = run_detail.json()
    assert detail_payload["diagnosis"]["host_snapshot"]["coordination"][
        "recommended_scheduler_action"
    ] == "handoff"
    assert detail_payload["diagnosis"]["host_snapshot"]["host_twin_summary"][
        "host_companion_status"
    ] == "attached"
    assert "host-twin-contention-forecast-blocked" in detail_payload["diagnosis"][
        "blocking_codes"
    ]


def test_workflow_resume_refreshes_schedule_host_meta_from_live_host_twin(
    tmp_path,
) -> None:
    initial_detail = _browser_host_preflight_detail(
        environment_id="env-browser-host-a",
        session_mount_id="session-browser-host-a",
        continuity_source="live-handle",
        coordination_reason="initial browser writer path is clear",
        recommended_scheduler_action="continue",
    )
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(initial_detail["session_mount_id"]): initial_detail},
    )
    client = TestClient(
        _build_workflow_app(tmp_path, environment_service=environment_service),
    )
    instance_id = _bootstrap_industry(client)

    launched = _launch_workflow_via_service(
        client,
        template_id="industry-weekly-research-synthesis",
        industry_instance_id=instance_id,
        session_mount_id=str(initial_detail["session_mount_id"]),
        parameters={
            "focus_area": "channel conversion",
            "weekly_review_cron": "0 12 * * 2",
            "timezone": "UTC",
        },
    )
    run_id = launched.run["run_id"]
    schedule_id = launched.schedules[0]["id"]
    schedule_record = client.app.state.workflow_template_service._schedule_repository.get_schedule(
        schedule_id,
    )
    assert schedule_record is not None
    client.app.state.workflow_template_service._schedule_repository.upsert_schedule(
        schedule_record.model_copy(
            update={
                "enabled": False,
                "status": "paused",
            }
        )
    )

    rebound_detail = _browser_host_preflight_detail(
        environment_id="env-browser-host-b",
        session_mount_id="session-browser-host-a",
        continuity_source="rebound-live-handle",
        coordination_reason="browser writer path was rebound after recovery",
        recommended_scheduler_action="continue",
    )
    environment_service._session_details[str(initial_detail["session_mount_id"])] = (
        rebound_detail
    )

    resumed = asyncio.run(
        client.app.state.workflow_template_service.resume_run(
            run_id,
            actor="copaw-operator",
        ),
    )

    assert resumed.diagnosis.host_snapshot["environment_id"] == "env-browser-host-b"
    assert resumed.diagnosis.host_snapshot["host_twin_summary"]["host_companion_status"] == "attached"
    schedule_payload = client.app.state.workflow_template_service._schedule_repository.get_schedule(
        schedule_id,
    )
    assert schedule_payload is not None
    assert schedule_payload.spec_payload["meta"]["environment_ref"] == "env-browser-host-b"
    assert schedule_payload.spec_payload["meta"]["environment_id"] == "env-browser-host-b"
    assert schedule_payload.spec_payload["meta"]["session_mount_id"] == "session-browser-host-a"
    assert schedule_payload.spec_payload["meta"]["host_snapshot"]["continuity"][
        "continuity_source"
    ] == "rebound-live-handle"
    assert schedule_payload.spec_payload["meta"]["host_snapshot"]["host_twin_summary"][
        "host_companion_source"
    ] == "rebound-live-handle"
    assert schedule_payload.spec_payload["meta"]["host_snapshot"]["coordination"][
        "contention_forecast"
    ]["reason"] == "browser writer path was rebound after recovery"
    stored_run = client.app.state.workflow_run_repository.get_run(run_id)
    assert stored_run is not None
    assert stored_run.metadata["host_snapshot"]["environment_id"] == "env-browser-host-b"
    assert stored_run.metadata["host_snapshot"]["continuity"][
        "continuity_source"
    ] == "rebound-live-handle"
    assert stored_run.metadata["host_snapshot"]["host_twin_summary"]["host_companion_source"] == "rebound-live-handle"


def test_workflow_preview_uses_candidate_role_strategy_when_primary_role_is_missing(
    tmp_path,
) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)
    record = client.app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    team_payload = dict(record.team_payload or {})
    team_payload["topology"] = "lead-plus-support"
    team_payload["agents"] = [
        agent
        for agent in list(team_payload.get("agents") or [])
        if isinstance(agent, dict) and agent.get("role_id") != "solution-lead"
    ]
    client.app.state.industry_instance_repository.upsert_instance(
        record.model_copy(
            update={
                "team_payload": team_payload,
                "agent_ids": [
                    agent_id
                    for agent_id in list(record.agent_ids or [])
                    if not str(agent_id).startswith("industry-solution-lead-")
                ],
            },
        ),
    )

    preview = client.post(
        "/workflow-templates/industry-weekly-research-synthesis/preview",
        json={
            "industry_instance_id": instance_id,
            "parameters": {
                "focus_area": "editorial positioning",
                "weekly_review_cron": "0 12 * * 2",
                "timezone": "UTC",
            },
        },
    )

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["can_launch"] is True
    leaf_step = next(
        step
        for step in payload["steps"]
        if step["step_id"] == "weekly-research-goal"
    )
    assert leaf_step["owner_role_id"] == "researcher"
    assert leaf_step["owner_agent_id"].endswith("researcher-northwind-robotics")
    assert leaf_step["owner_role_candidates"] == [
        "solution-lead",
        "researcher",
        "execution-core",
    ]


def test_workflow_run_cancel_archives_goals_and_pauses_schedules(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)

    launched = _launch_workflow_via_service(
        client,
        template_id="industry-weekly-research-synthesis",
        industry_instance_id=instance_id,
        parameters={
            "focus_area": "channel conversion",
            "weekly_review_cron": "0 10 * * 1",
            "timezone": "UTC",
        },
    )
    run_id = launched.run["run_id"]

    cancelled = client.post(
        f"/workflow-runs/{run_id}/cancel",
        json={
            "actor": "copaw-operator",
            "reason": "No longer needed",
        },
    )
    assert cancelled.status_code == 200
    payload = cancelled.json()
    assert payload["run"]["status"] == "cancelled"
    assert payload["run"]["metadata"]["cancelled_by"] == "copaw-operator"
    assert all(goal["status"] == "archived" for goal in payload["goals"])
    assert all(schedule["status"] == "paused" for schedule in payload["schedules"])


def test_workflow_preview_reports_assignment_gap_and_internal_launch_stays_blocked(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)
    repository = client.app.state.workflow_template_repository
    repository.upsert_template(
        WorkflowTemplateRecord(
            template_id="assignment-gap-smoke",
            title="Assignment Gap Smoke",
            summary="Require an installed capability that the target agent does not currently own.",
            category="smoke",
            status="active",
            version="v1",
            dependency_capability_ids=["tool:send_file_to_user"],
            suggested_role_ids=["solution-lead", "researcher"],
            owner_role_id="solution-lead",
            step_specs=[
                {
                    "id": "solution-lead-send-file",
                    "kind": "goal",
                    "execution_mode": "leaf",
                    "owner_role_id": "solution-lead",
                    "owner_role_candidates": ["solution-lead", "researcher"],
                    "title": "Solution lead share handoff",
                    "summary": "Send the prepared file to the operator.",
                    "required_capability_ids": ["tool:send_file_to_user"],
                    "plan_steps": ["Send the prepared file."],
                },
            ],
            metadata={"builtin": False},
        ),
    )

    preview = client.post(
        "/workflow-templates/assignment-gap-smoke/preview",
        json={"industry_instance_id": instance_id},
    )

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["can_launch"] is False
    assert payload["missing_capability_ids"] == []
    assert payload["assignment_gap_capability_ids"] == ["tool:send_file_to_user"]
    assert payload["steps"][0]["assignment_gap_capability_ids"] == ["tool:send_file_to_user"]
    assert any(item["code"] == "assignment-gap" for item in payload["launch_blockers"])

    try:
        _launch_workflow_via_service(
            client,
            template_id="assignment-gap-smoke",
            industry_instance_id=instance_id,
            parameters={},
        )
    except ValueError as exc:
        assert "blocked" in str(exc).lower()
    else:
        raise AssertionError("expected assignment-gap launch to stay blocked")

def test_workflow_preview_reports_budget_overflow_for_business_agent(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)
    capability_service = client.app.state.capability_service
    repository = client.app.state.workflow_template_repository

    baseline = {
        "tool:browser_use",
        "tool:edit_file",
        "tool:get_current_time",
        "tool:read_file",
        "tool:write_file",
        "system:dispatch_query",
    }
    extra_capabilities = [
        mount.id
        for mount in capability_service.list_capabilities(enabled_only=True)
        if mount.id not in baseline
    ]
    assert len(extra_capabilities) >= 14
    extra_capabilities = extra_capabilities[:20]

    repository.upsert_template(
        WorkflowTemplateRecord(
            template_id="budget-overflow-smoke",
            title="Budget Overflow Smoke",
            summary="Force a business agent over the V4 capability budget.",
            category="smoke",
            status="active",
            version="v1",
            dependency_capability_ids=list(extra_capabilities),
            suggested_role_ids=["solution-lead"],
            owner_role_id="solution-lead",
            step_specs=[
                {
                    "id": "solution-lead-overflow",
                    "kind": "goal",
                    "execution_mode": "leaf",
                    "owner_role_id": "solution-lead",
                    "title": "Overflow solution lead capability set",
                    "summary": "Demand too many extra capabilities for one business agent.",
                    "required_capability_ids": list(extra_capabilities),
                    "plan_steps": ["Attempt an over-budget capability loadout."],
                },
            ],
            metadata={"builtin": False},
        ),
    )

    preview = client.post(
        "/workflow-templates/budget-overflow-smoke/preview",
        json={"industry_instance_id": instance_id},
    )

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["can_launch"] is False
    budget_status = next(
        item
        for item in payload["budget_status_by_agent"]
        if item["role_id"] == "solution-lead"
    )
    assert budget_status["agent_class"] == "business"
    assert budget_status["extra_limit"] == 12
    assert budget_status["planned_extra_count"] > budget_status["extra_limit"]
    assert budget_status["blocking"] is True
    assert any(item["code"] == "capability-budget-exceeded" for item in payload["launch_blockers"])


@pytest.mark.parametrize(
    ("detail", "expected_code"),
    [
        (
            _desktop_host_preflight_detail(
                continuity_status="no-session",
                continuity_source="none",
                recovery_status="detached",
                recovery_recoverable=False,
                recovery_note="No recovery path is currently available.",
                current_gap_or_blocker="Host continuity is not currently attached.",
                active_window_ref=None,
                writer_lock_scope=None,
            ),
            "host-twin-continuity-invalid",
        ),
        (
            _desktop_host_preflight_detail(
                access_mode="read-only",
                current_gap_or_blocker="Writer lease is not currently available.",
                writer_lock_scope=None,
            ),
            "host-twin-writable-surface-unavailable",
        ),
        (
            _desktop_host_preflight_detail(
                handoff_state="manual-only-terminal",
                handoff_reason="Manual login is required before the session can continue.",
                recovery_status="same-host-other-process",
                recovery_recoverable=False,
                recovery_note="Return to the human handoff checkpoint before retrying.",
                current_gap_or_blocker="Manual login is required before the session can continue.",
            ),
            "host-twin-recovery-handoff-only",
        ),
        (
            _desktop_host_preflight_detail(
                active_alert_families=["modal-uac-login"],
                host_blocker_family="modal-uac-login",
                host_blocker_response="handoff",
                current_gap_or_blocker="Windows security prompt is blocking controlled input.",
            ),
            "host-twin-active-host-blockers",
        ),
    ],
)
def test_workflow_preview_reports_host_twin_preflight_blockers_for_mutating_desktop_work(
    tmp_path,
    detail,
    expected_code,
) -> None:
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(detail["session_mount_id"]): detail},
    )
    client = TestClient(
        _build_workflow_app(tmp_path, environment_service=environment_service),
    )
    instance_id = _bootstrap_industry(client)
    solution_lead_agent_id = _industry_role_agent_id(client, instance_id, "solution-lead")
    _grant_capability_to_agent(
        client,
        agent_id=solution_lead_agent_id,
        capability_ids=["mcp:desktop_windows"],
    )

    preview = client.post(
        "/workflow-templates/desktop-outreach-smoke/preview",
        json={
            "industry_instance_id": instance_id,
            "session_mount_id": detail["session_mount_id"],
            "parameters": {
                "target_application": "Desktop app",
                "recipient_name": "Target contact",
                "message_text": "Draft message",
            },
        },
    )

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["can_launch"] is False
    blocker = next(
        item for item in payload["launch_blockers"] if item["code"] == expected_code
    )
    assert blocker["step_ids"] == ["desktop-leaf-action"]


def test_install_template_assigns_capability_and_unlocks_workflow_launch(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))
    instance_id = _bootstrap_industry(client)
    config = SimpleNamespace(mcp=SimpleNamespace(clients={}))

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
    ):
        preview = client.post(
            "/workflow-templates/desktop-outreach-smoke/preview",
            json={
                "industry_instance_id": instance_id,
                "parameters": {
                    "target_application": "Desktop app",
                    "recipient_name": "Target contact",
                    "message_text": "Draft message",
                },
            },
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        assert preview_payload["can_launch"] is False
        assert "mcp:desktop_windows" in preview_payload["missing_capability_ids"]

        dependency = next(
            item
            for item in preview_payload["dependencies"]
            if item["capability_id"] == "mcp:desktop_windows"
        )
        target_agent_ids = dependency["target_agent_ids"]
        assert target_agent_ids

        installed = client.post(
            "/capability-market/install-templates/desktop-windows/install",
            json={
                "target_agent_ids": target_agent_ids,
                "capability_ids": ["mcp:desktop_windows"],
                "capability_assignment_mode": "merge",
                "workflow_resume": {
                    "template_id": "desktop-outreach-smoke",
                    "industry_instance_id": instance_id,
                    "parameters": {
                        "target_application": "Desktop app",
                        "recipient_name": "Target contact",
                        "message_text": "Draft message",
                    },
                    "resume_action": "preview",
                },
            },
        )
        assert installed.status_code == 201
        install_payload = installed.json()
        assert install_payload["template_id"] == "desktop-windows"
        assert install_payload["target_ref"] == "desktop_windows"
        assert install_payload["install_status"] == "installed"
        assert install_payload["assigned_capability_ids"] == ["mcp:desktop_windows"]
        assert install_payload["assignment_results"][0]["agent_id"] == target_agent_ids[0]
        assert install_payload["workflow_resume"]["return_path"] == (
            "/runtime-center?tab=automation&template=desktop-outreach-smoke"
        )

        capability_surface = client.app.state.agent_profile_service.get_capability_surface(
            target_agent_ids[0],
        )
        assert "mcp:desktop_windows" in capability_surface["effective_capabilities"]

        refreshed_preview = client.post(
            "/workflow-templates/desktop-outreach-smoke/preview",
            json={
                "industry_instance_id": instance_id,
                "parameters": {
                    "target_application": "Desktop app",
                    "recipient_name": "Target contact",
                    "message_text": "Draft message",
                },
            },
        )
        assert refreshed_preview.status_code == 200
        refreshed_payload = refreshed_preview.json()
        assert refreshed_payload["can_launch"] is True
        assert refreshed_payload["missing_capability_ids"] == []
        assert refreshed_payload["assignment_gap_capability_ids"] == []


def test_install_template_can_enable_existing_disabled_client(tmp_path) -> None:
    client = TestClient(_build_workflow_app(tmp_path))

    existing_client = SimpleNamespace(
        name="Windows Desktop Host",
        description="Desktop automation host",
        enabled=False,
        transport="stdio",
        url="",
        headers={},
        command="python",
        args=["-m", "copaw.adapters.desktop.windows_mcp_server"],
        env={},
        cwd="",
        registry=None,
        model_dump=lambda mode="json": {
            "name": "Windows Desktop Host",
            "description": "Desktop automation host",
            "enabled": False,
            "transport": "stdio",
            "url": "",
            "headers": {},
            "command": "python",
            "args": ["-m", "copaw.adapters.desktop.windows_mcp_server"],
            "env": {},
            "cwd": "",
            "registry": None,
        },
    )
    config = SimpleNamespace(
        mcp=SimpleNamespace(clients={"desktop_windows": existing_client}),
    )

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
    ):
        before = client.post(
            "/workflow-templates/desktop-outreach-smoke/preview",
            json={
                "parameters": {
                    "target_application": "Desktop app",
                    "recipient_name": "Target contact",
                    "message_text": "Draft message",
                },
            },
        )
        assert before.status_code == 200
        dependency = next(
            item
            for item in before.json()["dependencies"]
            if item["capability_id"] == "mcp:desktop_windows"
        )
        assert dependency["installed"] is True
        assert dependency["available"] is False
        assert dependency["enabled"] is False

        installed = client.post(
            "/capability-market/install-templates/desktop-windows/install",
            json={"enabled": True},
        )
        assert installed.status_code == 201
        payload = installed.json()
        assert payload["install_status"] == "enabled-existing"
        assert payload["enabled"] is True
