# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import time

from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_service import BuddyOnboardingService
from copaw.kernel.buddy_projection_service import BuddyProjectionService
from copaw.state import SQLiteStateStore
from copaw.state.main_brain_service import (
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from copaw.state.repositories import (
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingCycleRepository,
    SqliteOperatingLaneRepository,
)
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)
from tests.app.industry_api_parts.shared import _build_industry_app


class _FakeIndustryService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def kickoff_execution_from_chat(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "activated": True,
            "industry_instance_id": kwargs["industry_instance_id"],
            "started_assignment_ids": ["assignment-1"],
        }


def test_buddy_confirm_direction_auto_activates_execution_when_industry_service_exists(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-activation.sqlite3")
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    industry_repository = SqliteIndustryInstanceRepository(store)
    lane_service = OperatingLaneService(repository=SqliteOperatingLaneRepository(store))
    backlog_service = BacklogService(repository=SqliteBacklogItemRepository(store))
    cycle_service = OperatingCycleService(repository=SqliteOperatingCycleRepository(store))
    assignment_service = AssignmentService(repository=SqliteAssignmentRepository(store))
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
    )
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        industry_instance_repository=industry_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_service,
        domain_capability_growth_service=growth_service,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        domain_capability_growth_service=growth_service,
        current_focus_resolver=lambda _profile_id: {},
    )
    fake_industry_service = _FakeIndustryService()
    app = FastAPI()
    app.include_router(buddy_router)
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    app.state.industry_service = fake_industry_service
    client = TestClient(app)

    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Analyst",
            "current_stage": "restart",
            "interests": ["stocks", "trading"],
            "strengths": ["discipline"],
            "constraints": ["money"],
            "goal_intention": "I want a real stock trading path.",
        },
    ).json()
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a durable trading system with clear risk control.",
        },
    ).json()

    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["activation"]["status"] == "queued"
    assert payload["activation"]["industry_instance_id"] == payload["execution_carrier"]["instance_id"]
    deadline = time.time() + 1.0
    while not fake_industry_service.calls and time.time() < deadline:
        time.sleep(0.02)
    assert fake_industry_service.calls[0]["industry_instance_id"] == payload["execution_carrier"]["instance_id"]
    assert fake_industry_service.calls[0]["trigger_source"] == "buddy-onboarding"

    instance_id = payload["execution_carrier"]["instance_id"]
    stored_instance = industry_repository.get_instance(instance_id)
    assert stored_instance is not None
    team_agents = list((stored_instance.team_payload or {}).get("agents") or [])
    assert len(team_agents) == 2
    specialist_agent_ids = {
        str(item.get("agent_id") or "").strip()
        for item in team_agents
        if str(item.get("agent_id") or "").strip()
    }
    assert specialist_agent_ids
    assert "copaw-agent-runner" not in specialist_agent_ids
    lanes = lane_service.list_lanes(industry_instance_id=instance_id, limit=None)
    assert lanes
    assert {lane.owner_agent_id for lane in lanes} == specialist_agent_ids
    assert {lane.owner_role_id for lane in lanes} == {"growth-focus", "proof-of-work"}

    assignments = assignment_service.list_assignments(
        industry_instance_id=instance_id,
        limit=None,
    )
    assert assignments
    assert {assignment.owner_agent_id for assignment in assignments} == specialist_agent_ids
    assert {assignment.owner_role_id for assignment in assignments} == {
        "growth-focus",
        "proof-of-work",
    }


def test_buddy_confirm_direction_real_kickoff_creates_leaf_tasks_for_specialist_agents(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    store = app.state.state_store
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        operating_lane_service=app.state.operating_lane_service,
        backlog_service=app.state.backlog_service,
        operating_cycle_service=app.state.operating_cycle_service,
        assignment_service=app.state.assignment_service,
        agent_report_service=app.state.agent_report_service,
    )
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        operating_lane_service=app.state.operating_lane_service,
        backlog_service=app.state.backlog_service,
        operating_cycle_service=app.state.operating_cycle_service,
        assignment_service=app.state.assignment_service,
        schedule_repository=app.state.schedule_repository,
        domain_capability_growth_service=growth_service,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        domain_capability_growth_service=growth_service,
        current_focus_resolver=lambda _profile_id: {},
    )
    app.include_router(buddy_router)
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    client = TestClient(app)

    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Analyst",
            "current_stage": "restart",
            "interests": ["stocks", "trading"],
            "strengths": ["discipline"],
            "constraints": ["money"],
            "goal_intention": "I want a real stock trading path.",
        },
    ).json()
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a durable trading system with clear risk control.",
        },
    ).json()

    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert confirmation.status_code == 200
    payload = confirmation.json()
    instance_id = payload["execution_carrier"]["instance_id"]
    deadline = time.time() + 8.0
    tasks = []
    assignments = []
    while time.time() < deadline:
        assignments = app.state.assignment_repository.list_assignments(
            industry_instance_id=instance_id,
            limit=None,
        )
        assignment_ids = {item.id for item in assignments}
        tasks = [
            task
            for task in app.state.task_repository.list_tasks()
            if task.assignment_id in assignment_ids
        ]
        if tasks:
            break
        time.sleep(0.2)

    stored_instance = app.state.industry_instance_repository.get_instance(instance_id)
    assert stored_instance is not None
    specialist_agent_ids = {
        str(item.get("agent_id") or "").strip()
        for item in (stored_instance.team_payload or {}).get("agents", [])
        if str(item.get("agent_id") or "").strip()
    }
    assert specialist_agent_ids
    assert "copaw-agent-runner" not in specialist_agent_ids
    assert tasks
    assert {task.owner_agent_id for task in tasks} <= specialist_agent_ids
    assert {assignment.owner_agent_id for assignment in assignments} <= specialist_agent_ids


def test_buddy_surface_repairs_legacy_buddy_execution_binding_before_chat(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    store = app.state.state_store
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        operating_lane_service=app.state.operating_lane_service,
        backlog_service=app.state.backlog_service,
        operating_cycle_service=app.state.operating_cycle_service,
        assignment_service=app.state.assignment_service,
        agent_report_service=app.state.agent_report_service,
    )
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        operating_lane_service=app.state.operating_lane_service,
        backlog_service=app.state.backlog_service,
        operating_cycle_service=app.state.operating_cycle_service,
        assignment_service=app.state.assignment_service,
        schedule_repository=app.state.schedule_repository,
        domain_capability_growth_service=growth_service,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        domain_capability_growth_service=growth_service,
        current_focus_resolver=lambda _profile_id: {},
    )
    app.include_router(buddy_router)
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    client = TestClient(app)

    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Analyst",
            "current_stage": "restart",
            "interests": ["stocks", "trading"],
            "strengths": ["discipline"],
            "constraints": ["money"],
            "goal_intention": "I want a real stock trading path.",
        },
    ).json()
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a durable trading system with clear risk control.",
        },
    ).json()
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
            "capability_action": "start-new",
        },
    ).json()

    instance_id = confirmation["execution_carrier"]["instance_id"]
    initial_deadline = time.time() + 8.0
    while time.time() < initial_deadline:
        initial_assignments = app.state.assignment_repository.list_assignments(
            industry_instance_id=instance_id,
            limit=None,
        )
        initial_assignment_ids = {item.id for item in initial_assignments}
        initial_tasks = [
            task
            for task in app.state.task_repository.list_tasks()
            if task.assignment_id in initial_assignment_ids
        ]
        if initial_tasks:
            break
        time.sleep(0.2)
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    app.state.industry_instance_repository.upsert_instance(
        record.model_copy(
            update={
                "team_payload": {
                    "team_id": instance_id,
                    "label": record.label,
                    "summary": record.summary,
                    "agents": [],
                },
                "agent_ids": [],
            },
        ),
    )
    lanes = app.state.operating_lane_service.list_lanes(
        industry_instance_id=instance_id,
        limit=None,
    )
    for lane in lanes:
        app.state.operating_lane_repository.upsert_lane(
            lane.model_copy(
                update={
                    "owner_agent_id": None,
                },
            ),
        )
    assignments = app.state.assignment_repository.list_assignments(
        industry_instance_id=instance_id,
        limit=None,
    )
    for assignment in assignments:
        metadata = dict(assignment.metadata or {})
        metadata["owner_agent_id"] = "copaw-agent-runner"
        app.state.assignment_repository.upsert_assignment(
            assignment.model_copy(
                update={
                    "owner_agent_id": "copaw-agent-runner",
                    "metadata": metadata,
                },
            ),
        )

    response = client.get(
        f"/buddy/surface?profile_id={identity['profile']['profile_id']}",
    )

    assert response.status_code == 200
    repaired = app.state.industry_instance_repository.get_instance(instance_id)
    assert repaired is not None
    specialist_agent_ids = {
        str(item.get("agent_id") or "").strip()
        for item in (repaired.team_payload or {}).get("agents", [])
        if str(item.get("agent_id") or "").strip()
    }
    assert specialist_agent_ids
    assert "copaw-agent-runner" not in specialist_agent_ids
    repaired_lanes = app.state.operating_lane_service.list_lanes(
        industry_instance_id=instance_id,
        limit=None,
    )
    assert {lane.owner_agent_id for lane in repaired_lanes} <= specialist_agent_ids
    repaired_assignments = app.state.assignment_repository.list_assignments(
        industry_instance_id=instance_id,
        limit=None,
    )
    leaf_assignments = [
        item
        for item in repaired_assignments
        if item.owner_role_id in {"growth-focus", "proof-of-work"}
    ]
    assert leaf_assignments
    assert {item.owner_agent_id for item in leaf_assignments} <= specialist_agent_ids


def test_buddy_confirm_direction_writes_back_completed_reports_to_control_thread(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    store = app.state.state_store
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        operating_lane_service=app.state.operating_lane_service,
        backlog_service=app.state.backlog_service,
        operating_cycle_service=app.state.operating_cycle_service,
        assignment_service=app.state.assignment_service,
        agent_report_service=app.state.agent_report_service,
    )
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        operating_lane_service=app.state.operating_lane_service,
        backlog_service=app.state.backlog_service,
        operating_cycle_service=app.state.operating_cycle_service,
        assignment_service=app.state.assignment_service,
        schedule_repository=app.state.schedule_repository,
        domain_capability_growth_service=growth_service,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        domain_capability_growth_service=growth_service,
        current_focus_resolver=lambda _profile_id: {},
    )
    app.include_router(buddy_router)
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    client = TestClient(app)

    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Analyst",
            "current_stage": "restart",
            "interests": ["stocks", "trading"],
            "strengths": ["discipline"],
            "constraints": ["money"],
            "goal_intention": "I want a real stock trading path.",
        },
    ).json()
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a durable trading system with clear risk control.",
        },
    ).json()
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert confirmation.status_code == 200
    payload = confirmation.json()
    instance_id = payload["execution_carrier"]["instance_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    deadline = time.time() + 15.0
    reports = []
    report_messages = []
    terminal_tasks = []
    all_tasks = []
    while time.time() < deadline:
        reports = app.state.agent_report_service.list_reports(
            industry_instance_id=instance_id,
            limit=None,
        )
        all_tasks = app.state.task_repository.list_tasks(
            industry_instance_id=instance_id,
            limit=None,
        )
        terminal_tasks = [
            task for task in all_tasks if task.status in {"completed", "failed", "cancelled"}
        ]
        active_tasks = [
            task for task in all_tasks if task.status not in {"completed", "failed", "cancelled"}
        ]
        snapshot = app.state.session_backend.load_session_snapshot(
            session_id=control_thread_id,
            user_id="copaw-agent-runner",
            allow_not_exist=True,
        )
        message_buffer = []
        if isinstance(snapshot, dict):
            message_buffer = snapshot.get("agent", {}).get("memory") or []
            if isinstance(message_buffer, dict):
                message_buffer = message_buffer.get("content") or []
        report_messages = [
            message
            for message in message_buffer
            if isinstance(message, dict)
            and message.get("metadata", {}).get("message_kind") == "agent-report-writeback"
        ]
        if (
            all_tasks
            and not active_tasks
            and reports
            and len(reports) >= len(all_tasks)
            and report_messages
        ):
            break
        time.sleep(0.25)

    assert terminal_tasks
    assert reports
    assert report_messages
    assert all(report.processed for report in reports)
    assert {report.assignment_id for report in reports if report.assignment_id}
    assert {
        message.get("metadata", {}).get("control_thread_id")
        for message in report_messages
    } == {control_thread_id}


def test_buddy_confirm_direction_seeds_durable_execution_core_schedules(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    store = app.state.state_store
    profile_repository = SqliteHumanProfileRepository(store)
    growth_target_repository = SqliteGrowthTargetRepository(store)
    relationship_repository = SqliteCompanionRelationshipRepository(store)
    domain_capability_repository = SqliteBuddyDomainCapabilityRepository(store)
    session_repository = SqliteBuddyOnboardingSessionRepository(store)
    growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=domain_capability_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        operating_lane_service=app.state.operating_lane_service,
        backlog_service=app.state.backlog_service,
        operating_cycle_service=app.state.operating_cycle_service,
        assignment_service=app.state.assignment_service,
        agent_report_service=app.state.agent_report_service,
    )
    onboarding_service = BuddyOnboardingService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        operating_lane_service=app.state.operating_lane_service,
        backlog_service=app.state.backlog_service,
        operating_cycle_service=app.state.operating_cycle_service,
        assignment_service=app.state.assignment_service,
        schedule_repository=app.state.schedule_repository,
        domain_capability_growth_service=growth_service,
    )
    projection_service = BuddyProjectionService(
        profile_repository=profile_repository,
        growth_target_repository=growth_target_repository,
        relationship_repository=relationship_repository,
        domain_capability_repository=domain_capability_repository,
        onboarding_session_repository=session_repository,
        domain_capability_growth_service=growth_service,
        current_focus_resolver=lambda _profile_id: {},
    )
    app.include_router(buddy_router)
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    client = TestClient(app)

    identity = client.post(
        "/buddy/onboarding/identity",
        json={
            "display_name": "Kai",
            "profession": "Analyst",
            "current_stage": "restart",
            "interests": ["stocks", "trading"],
            "strengths": ["discipline"],
            "constraints": ["money"],
            "goal_intention": "I want a real stock trading path.",
        },
    ).json()
    clarification = client.post(
        "/buddy/onboarding/clarify",
        json={
            "session_id": identity["session_id"],
            "answer": "I want a durable trading system with clear risk control.",
        },
    ).json()
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": clarification["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert confirmation.status_code == 200
    payload = confirmation.json()
    instance_id = payload["execution_carrier"]["instance_id"]
    control_thread_id = payload["execution_carrier"]["control_thread_id"]
    schedules = [
        schedule
        for schedule in app.state.schedule_repository.list_schedules()
        if schedule.status != "deleted"
        and (
            schedule.spec_payload.get("meta", {}).get("industry_instance_id") == instance_id
            or schedule.spec_payload.get("request", {}).get("industry_instance_id") == instance_id
        )
    ]

    assert schedules
    assert {
        schedule.target_session_id
        for schedule in schedules
    } == {control_thread_id}
    assert all(schedule.enabled for schedule in schedules)
