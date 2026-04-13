# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
import time

from copaw.app.crons.executor import CronExecutor
from copaw.app.crons.models import CronJobSpec
from copaw.app.routers.buddy_routes import router as buddy_router
from copaw.industry import IndustryCapabilityRecommendation
from copaw.industry.chat_writeback import build_chat_writeback_plan
from copaw.kernel.buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from copaw.kernel.buddy_onboarding_reasoner import (
    BuddyCollaborationContract,
    BuddyOnboardingBacklogSeed,
    BuddyOnboardingContractCompileResult,
)
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
from tests.shared.buddy_reasoners import DeterministicBuddyReasoner


class _CapturingCronKernelDispatcher:
    def __init__(self) -> None:
        self.tasks: list[object] = []

    def submit(self, task):
        self.tasks.append(task)
        return SimpleNamespace(phase="executing", task_id=task.id)

    async def execute_task(self, task_id: str):
        return SimpleNamespace(success=True, error=None, summary=task_id)


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


class _FlakyIndustryService:
    def __init__(self, *, fail_times: int = 1) -> None:
        self.fail_times = fail_times
        self.calls: list[dict[str, object]] = []

    async def kickoff_execution_from_chat(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("kickoff exploded")
        return {
            "activated": True,
            "industry_instance_id": kwargs["industry_instance_id"],
            "started_assignment_ids": ["assignment-1"],
        }


class _ContractWritingBuddyReasoner:
    def compile_contract(
        self,
        *,
        profile,
        collaboration_contract: BuddyCollaborationContract,
    ) -> BuddyOnboardingContractCompileResult:
        _ = (profile, collaboration_contract)
        return BuddyOnboardingContractCompileResult(
            candidate_directions=["Build a durable fiction writing and publishing path."],
            recommended_direction="Build a durable fiction writing and publishing path.",
            final_goal="Establish a steady fiction publishing rhythm and produce the first proof-of-work cycle.",
            why_it_matters="Turn writing from intention into a compounding publishing practice with visible assets.",
            backlog_items=[
                BuddyOnboardingBacklogSeed(
                    lane_hint="growth-focus",
                    title="Lock the story direction and publishing rhythm",
                    summary="Choose the format, cadence, and smallest sustainable chapter scope.",
                    priority=3,
                    source_key="writing-direction",
                ),
                BuddyOnboardingBacklogSeed(
                    lane_hint="proof-of-work",
                    title="Finish the first chapter and open the publishing draft",
                    summary="Draft the first chapter and prepare the real platform draft plus cover upload.",
                    priority=2,
                    source_key="writing-first-chapter",
                ),
            ],
        )


def _submit_contract(
    client: TestClient,
    session_id: str,
    **overrides,
) -> dict[str, object]:
    payload = {
        "session_id": session_id,
        "service_intent": "Help me build a durable trading system with clear risk control.",
        "collaboration_role": "orchestrator",
        "autonomy_level": "guarded-proactive",
        "confirm_boundaries": ["external spend"],
        "report_style": "result-first",
        "collaboration_notes": "Move the work forward but surface meaningful risk before acting.",
    }
    payload.update(overrides)
    response = client.post("/buddy/onboarding/contract", json=payload)
    assert response.status_code == 200
    return response.json()


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
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
    contract = _submit_contract(client, identity["session_id"])

    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
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


def test_buddy_confirm_direction_auto_retries_activation_after_transient_failure(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-activation-failure.sqlite3")
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
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
    fake_industry_service = _FlakyIndustryService(fail_times=1)
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
    contract = _submit_contract(
        client,
        identity["session_id"],
        service_intent="Help me build a durable trading system with clear risk control.",
    )

    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 200
    deadline = time.time() + 1.5
    session_payload = None
    while time.time() < deadline:
        session_payload = session_repository.get_latest_session_for_profile(
            identity["profile"]["profile_id"],
        )
        if (
            session_payload is not None
            and session_payload.activation_status == "succeeded"
            and int(session_payload.activation_attempt_count or 0) >= 2
        ):
            break
        time.sleep(0.02)

    assert session_payload is not None
    assert session_payload.activation_status == "succeeded"
    assert int(session_payload.activation_attempt_count or 0) >= 2
    assert len(fake_industry_service.calls) >= 2
    assert not str(session_payload.activation_error or "").strip()


def test_buddy_surface_requeues_failed_activation_and_marks_it_succeeded(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "buddy-onboarding-activation-retry.sqlite3")
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
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
    flaky_industry_service = _FlakyIndustryService(fail_times=1)
    app = FastAPI()
    app.include_router(buddy_router)
    app.state.buddy_onboarding_service = onboarding_service
    app.state.buddy_projection_service = projection_service
    app.state.industry_service = flaky_industry_service
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
    contract = _submit_contract(
        client,
        identity["session_id"],
        service_intent="Help me build a durable trading system with clear risk control.",
    )

    response = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    )

    assert response.status_code == 200
    deadline = time.time() + 2.0
    surface_payload = None
    while time.time() < deadline:
        candidate = client.get(
            "/buddy/surface",
            params={"profile_id": identity["profile"]["profile_id"]},
        )
        assert candidate.status_code == 200
        surface_payload = candidate.json()
        if surface_payload["onboarding"].get("activation_status") == "succeeded":
            break
        time.sleep(0.02)

    assert len(flaky_industry_service.calls) >= 2
    assert surface_payload is not None
    assert surface_payload["onboarding"]["activation_status"] == "succeeded"
    assert surface_payload["onboarding"]["activation_attempt_count"] >= 2


def test_buddy_writing_instance_auto_closes_browser_specialist_gap_before_temp_seat(
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
        onboarding_reasoner=_ContractWritingBuddyReasoner(),
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
            "display_name": "小满",
            "profession": "写作者",
            "current_stage": "重启",
            "interests": ["写作", "番茄"],
            "strengths": ["持续创作"],
            "constraints": ["需要先形成稳定节奏"],
            "goal_intention": "我想长期写小说，并真的在番茄持续发布。",
        },
    ).json()
    clarification = client.post(
        "/buddy/onboarding/contract",
        json={
            "session_id": identity["session_id"],
            "service_intent": "I want to build a durable fiction writing rhythm with publishing follow-through.",
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
    message_text = "请在浏览器里打开番茄创作平台草稿箱，继续写今天的小说章节，并从 Windows 桌面目录选择封面图片上传"
    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=message_text,
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                message_text,
                approved_classifications=["backlog"],
                goal_title="番茄章节草稿推进",
                goal_summary=message_text,
                goal_plan_steps=[
                    "打开番茄创作平台并进入当前作品草稿。",
                    "完成今天章节的草稿更新，并从 Windows 桌面目录选择封面图片上传。",
                    "把草稿推进结果和下一步写回。",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["dispatch_deferred"] is True
    assert result["target_owner_agent_id"] != "copaw-agent-runner"
    assert "capability-gap-closed" in result["classification"]
    assert "temporary-seat-proposal" not in result["classification"]
    assert "temporary-seat-auto" not in result["classification"]

    runtime = app.state.agent_runtime_repository.get_runtime(result["target_owner_agent_id"])
    assert runtime is not None
    capability_layers = runtime.metadata["capability_layers"]
    assert "tool:browser_use" in capability_layers["effective_capability_ids"]


def test_buddy_writing_instance_falls_back_to_staffing_proposal_when_templates_miss(
    tmp_path,
    monkeypatch,
) -> None:
    app = _build_industry_app(
        tmp_path,
        enable_curated_catalog=True,
    )
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
        onboarding_reasoner=_ContractWritingBuddyReasoner(),
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
            "display_name": "Man",
            "profession": "Writer",
            "current_stage": "restart",
            "interests": ["writing", "story"],
            "strengths": ["drafting"],
            "constraints": ["need publishing workflow"],
            "goal_intention": "I want to keep publishing fiction on a real platform.",
        },
    ).json()
    contract = _submit_contract(
        client,
        identity["session_id"],
        service_intent="Help me build a repeatable browser workflow for drafting and cover uploads.",
        collaboration_notes="Stay proactive on browser workflow setup and publishing evidence.",
    )
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
            "capability_action": "start-new",
        },
    ).json()

    instance_id = confirmation["execution_carrier"]["instance_id"]
    stored_instance = app.state.industry_instance_repository.get_instance(instance_id)
    assert stored_instance is not None
    proof_role = next(
        item
        for item in list((stored_instance.team_payload or {}).get("agents") or [])
        if item.get("role_id") == "proof-of-work"
    )
    target_agent_id = str(proof_role["agent_id"])

    monkeypatch.setattr(
        app.state.industry_service,
        "_build_install_template_recommendations",
        lambda **_kwargs: [],
    )

    async def _fake_build_curated_skill_recommendations(**_kwargs):
        return (
            [
                IndustryCapabilityRecommendation(
                    recommendation_id="curated-browser-gap",
                    install_kind="hub-skill",
                    template_id="browser-use-plus",
                    title="Browser Use Plus",
                    default_client_key="browser_use_plus",
                    capability_ids=["tool:browser_use"],
                    capability_families=["browser"],
                    suggested_role_ids=["proof-of-work"],
                    target_agent_ids=[target_agent_id],
                    risk_level="auto",
                    source_kind="skillhub-curated",
                    source_label="SkillHub Curated",
                    source_url="https://skillhub.example.com/browser-use-plus.zip",
                    version="1.0.0",
                    review_required=False,
                ),
            ],
            [],
        )

    monkeypatch.setattr(
        app.state.industry_service,
        "_build_curated_skill_recommendations",
        _fake_build_curated_skill_recommendations,
    )

    skill_service = app.state.capability_service._system_handler._skills._skill_service

    def _fake_install_skill_from_hub(
        *,
        bundle_url: str,
        version: str = "",
        enable: bool = True,
        overwrite: bool = False,
    ):
        _ = version, overwrite
        skill_service.create_skill(
            name="browser_use_plus",
            content=(
                "---\n"
                "name: browser_use_plus\n"
                "description: Browser skill installed from curated hub\n"
                "---\n"
                f"Installed from {bundle_url}"
            ),
            overwrite=True,
        )
        if enable:
            skill_service.enable_skill("browser_use_plus")
        return SimpleNamespace(
            name="browser_use_plus",
            enabled=enable,
            source_url=bundle_url,
        )

    skill_service.install_skill_from_hub = _fake_install_skill_from_hub

    message_text = (
        "Open the web publishing dashboard, continue today's chapter draft, "
        "and upload the latest cover image from Windows."
    )
    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=message_text,
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                message_text,
                approved_classifications=["backlog"],
                goal_title="Publishing workflow follow-up",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Open the publishing dashboard in the browser.",
                    "Continue the chapter draft and upload the new cover image.",
                    "Write back the publishing result and next step.",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["dispatch_deferred"] is True
    assert result["target_owner_agent_id"] != "copaw-agent-runner"
    assert "capability-gap-closed" not in result["classification"]
    assert "temporary-seat-proposal" in result["classification"]
    assert "temporary-seat-auto" not in result["classification"]
    assert result["decision_request_id"]

    pending_detail = app.state.industry_service.get_instance_detail(instance_id)
    assert pending_detail is not None
    assert pending_detail.staffing["active_gap"] is not None
    assert pending_detail.staffing["pending_proposals"]

    runtime = app.state.agent_runtime_repository.get_runtime(result["target_owner_agent_id"])
    if runtime is not None:
        capability_layers = runtime.metadata["capability_layers"]
        assert "tool:browser_use" not in capability_layers["effective_capability_ids"]

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
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
    contract = _submit_contract(client, identity["session_id"])

    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
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
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
    contract = _submit_contract(client, identity["session_id"])
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
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

    refreshed = growth_service.refresh_active_domain_capability(
        profile_id=identity["profile"]["profile_id"],
    )
    assert refreshed is not None

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
    leaf_assignments = []
    assignment_deadline = time.time() + 8.0
    while time.time() < assignment_deadline:
        repaired_assignments = app.state.assignment_repository.list_assignments(
            industry_instance_id=instance_id,
            limit=None,
        )
        leaf_assignments = [
            item
            for item in repaired_assignments
            if item.owner_role_id in {"growth-focus", "proof-of-work"}
        ]
        if leaf_assignments and {
            item.owner_agent_id for item in leaf_assignments
        } <= specialist_agent_ids:
            break
        time.sleep(0.2)
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
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
    contract = _submit_contract(client, identity["session_id"])
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
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
            and len(report_messages) >= len(reports)
            and all(report.processed for report in reports)
        ):
            break
        time.sleep(0.25)

    assert terminal_tasks
    assert reports
    assert report_messages
    assert all(report.processed for report in reports)
    assert len(report_messages) >= len(reports)
    assert {report.assignment_id for report in reports if report.assignment_id}
    assert {
        message.get("metadata", {}).get("control_thread_id")
        for message in report_messages
    } == {control_thread_id}
    first_message_text = (
        (((report_messages[0].get("content") or [])[0] or {}).get("text"))
        if report_messages
        else ""
    )
    assert "我刚完成" in str(first_message_text)


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
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
    contract = _submit_contract(client, identity["session_id"])
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
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
    assert {
        (schedule.spec_payload.get("request") or {}).get("buddy_profile_id")
        for schedule in schedules
    } == {identity["profile"]["profile_id"]}
    assert {
        (schedule.spec_payload.get("request") or {}).get("owner_scope")
        for schedule in schedules
    } == {identity["profile"]["profile_id"]}


def test_buddy_execution_core_schedule_dispatch_keeps_buddy_profile_binding(
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
        onboarding_reasoner=DeterministicBuddyReasoner(),
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
    contract = _submit_contract(client, identity["session_id"])
    confirmation = client.post(
        "/buddy/onboarding/confirm-direction",
        json={
            "session_id": identity["session_id"],
            "selected_direction": contract["recommended_direction"],
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

    dispatcher = _CapturingCronKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    asyncio.run(executor.execute(CronJobSpec.model_validate(schedules[0].spec_payload)))

    assert dispatcher.tasks
    submitted = dispatcher.tasks[0]
    request_payload = dict(submitted.payload.get("request") or {})
    assert request_payload.get("buddy_profile_id") == identity["profile"]["profile_id"]
    assert request_payload.get("owner_scope") == identity["profile"]["profile_id"]
    assert request_payload.get("session_id") == control_thread_id
    assert request_payload.get("control_thread_id") == control_thread_id
