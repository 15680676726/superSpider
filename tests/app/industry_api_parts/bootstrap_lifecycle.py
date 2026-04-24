# -*- coding: utf-8 -*-
from __future__ import annotations

from urllib.parse import quote

from .shared import *  # noqa: F401,F403
from ..test_capability_market_api import FakeMcpRegistryCatalog
from copaw.app.console_push_store import take_all
from copaw.capabilities.system_team_handlers import SystemTeamCapabilityFacade
from copaw.industry import IndustryBootstrapInstallItem, IndustryCapabilityRecommendation
from copaw.industry.chat_writeback import build_chat_writeback_plan
from copaw.kernel.persistence import decode_kernel_task_metadata, encode_kernel_task_metadata
from copaw.memory.activation_models import ActivationResult
from copaw.memory import KnowledgeGraphService
from copaw.memory.knowledge_graph_models import (
    KnowledgeGraphPath,
    KnowledgeGraphNode,
    KnowledgeGraphRelation,
    KnowledgeGraphScope,
    TaskSubgraph,
)
from copaw.state import (
    AgentReportRecord,
    AssignmentRecord,
    BacklogItemRecord,
    IndustryInstanceRecord,
    OperatingCycleRecord,
    TaskRecord,
    TaskRuntimeRecord,
)


def _wait_until(predicate, *, timeout_seconds: float = 1.5, interval_seconds: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_seconds)
    return bool(predicate())


def test_industry_service_facade_delegates_bootstrap_to_bootstrap_service() -> None:
    service = IndustryService.__new__(IndustryService)
    calls: list[object] = []
    expected = object()

    async def _fake_bootstrap(request):
        calls.append(request)
        return expected

    service._bootstrap_service = SimpleNamespace(bootstrap_v1=_fake_bootstrap)
    request = object()

    result = asyncio.run(service.bootstrap_v1(request))

    assert result is expected
    assert calls == [request]


def test_industry_bootstrap_persists_final_edited_draft(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    preview_response = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Industrial Equipment",
            "company_name": "Northwind Robotics",
            "product": "factory monitoring copilots",
            "goals": ["launch two pilot deployments"],
        },
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    draft = preview_payload["draft"]

    execution_core = next(
        role
        for role in draft["team"]["agents"]
        if role["role_id"] == "execution-core"
    )
    business_role = next(
        role
        for role in draft["team"]["agents"]
        if role["agent_class"] == "business" and role["role_id"] != "execution-core"
    )
    business_role["name"] = "Northwind Workflow Architect"
    business_role["role_name"] = "Workflow Architect"
    business_role["role_summary"] = "Owns workflow design and rollout framing."
    business_role["mission"] = "Turn the brief into a rollout-ready operating workflow."
    draft["team"]["label"] = "Northwind Robotics Operating Cell"
    draft["team"]["summary"] = "Edited operator-ready industry team draft."
    draft["generation_summary"] = "Operator reviewed and refined the AI draft."

    custom_role = {
        "schema_version": "industry-role-blueprint-v1",
        "role_id": "field-enablement",
        "agent_id": "industry-field-enablement-northwind-robotics",
        "name": "Northwind Field Enablement Lead",
        "role_name": "Field Enablement Lead",
        "role_summary": "Owns pilot enablement and operator onboarding.",
        "mission": "Make the first deployments repeatable for frontline operators.",
        "goal_kind": "field-enablement",
        "agent_class": "business",
        "activation_mode": "persistent",
        "suspendable": False,
        "reports_to": execution_core["agent_id"],
        "risk_level": "guarded",
        "environment_constraints": [
            "kernel-governed query dispatch only",
            "workspace draft/edit allowed",
        ],
        "allowed_capabilities": [
            "system:dispatch_query",
            "tool:browser_use",
            "tool:read_file",
        ],
        "evidence_expectations": [
            "pilot enablement brief",
            "operator adoption checklist",
        ],
    }
    draft["team"]["agents"].append(custom_role)
    draft["goals"].append(
        {
            "goal_id": "field-enablement-goal",
            "kind": "field-enablement",
            "owner_agent_id": custom_role["agent_id"],
            "title": "Make the first pilot rollout repeatable",
            "summary": "Define the enablement path for pilot operators and field teams.",
            "plan_steps": [
                "Map the first deployment workflow.",
                "Clarify onboarding and adoption checkpoints.",
            ],
        },
    )
    draft["schedules"].append(
        {
            "schedule_id": "field-enablement-review",
            "owner_agent_id": custom_role["agent_id"],
            "title": "Field Enablement Review",
            "summary": "Weekly review for pilot enablement progress.",
            "cron": "0 15 * * 3",
            "timezone": "UTC",
            "dispatch_channel": "console",
            "dispatch_mode": "final",
        },
    )

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "goal_priority": 4,
            "auto_dispatch": True,
            "auto_activate": True,
            "execute": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    instance_id = payload["team"]["team_id"]

    stored_instance = app.state.industry_instance_repository.get_instance(instance_id)
    assert stored_instance is not None
    assert stored_instance.label == "Northwind Robotics Operating Cell"
    assert stored_instance.summary == "Edited operator-ready industry team draft."
    assert (
        stored_instance.execution_core_identity_payload["industry_instance_id"]
        == instance_id
    )
    assert (
        stored_instance.execution_core_identity_payload["agent_id"]
        == "copaw-agent-runner"
    )
    assert any(
        agent["name"] == "Northwind Workflow Architect"
        for agent in stored_instance.team_payload["agents"]
    )
    assert any(
        agent["name"] == "Northwind Field Enablement Lead"
        for agent in stored_instance.team_payload["agents"]
    )
    assert "industry-field-enablement-northwind-robotics" in stored_instance.agent_ids

    assert any(
        result["owner_agent_id"] == "industry-field-enablement-northwind-robotics"
        for result in bootstrap_draft_goals(payload)
    )
    assert any(
        result["schedule_id"].endswith("field-enablement-review")
        for result in bootstrap_schedule_summaries(payload)
    )

    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    runtime_payload = runtime_detail.json()
    assert runtime_payload["label"] == "Northwind Robotics Operating Cell"
    assert runtime_payload["execution_core_identity"]["industry_label"] == (
        "Northwind Robotics Operating Cell"
    )
    assert any(
        axis.startswith("行业聚焦：")
        for axis in runtime_payload["execution_core_identity"]["thinking_axes"]
    )
    assert any(
        agent["name"] == "Northwind Field Enablement Lead"
        for agent in runtime_payload["agents"]
    )
    assert any(
        goal["owner_agent_id"] == "industry-field-enablement-northwind-robotics"
        for goal in runtime_payload["goals"]
    )
    assert any(
        schedule["owner_agent_id"] == "industry-field-enablement-northwind-robotics"
        for schedule in runtime_payload["schedules"]
    )
    assert any(
        schedule["dispatch_channel"] == "console" and schedule["dispatch_mode"] == "stream"
        for schedule in runtime_payload["schedules"]
    )
    bindings = app.state.agent_thread_binding_repository.list_bindings(
        industry_instance_id=instance_id,
        active_only=False,
        limit=None,
    )
    binding_by_thread_id = {binding.thread_id: binding for binding in bindings}
    execution_binding = binding_by_thread_id[f"industry-chat:{instance_id}:execution-core"]
    assert execution_binding.agent_id == "copaw-agent-runner"
    assert execution_binding.session_id == f"industry-chat:{instance_id}:execution-core"
    assert execution_binding.work_context_id is not None
    work_context = app.state.work_context_repository.get_context(
        execution_binding.work_context_id,
    )
    assert work_context is not None
    assert work_context.context_key == (
        f"control-thread:industry-chat:{instance_id}:execution-core"
    )
    assert f"industry-chat:{instance_id}:manager" not in binding_by_thread_id


def test_industry_bootstrap_accepts_standard_full_weekday_range_cron(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    preview_response = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Industrial Equipment",
            "company_name": "Northwind Robotics",
            "product": "factory monitoring copilots",
        },
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    draft = preview_payload["draft"]

    execution_core = next(
        role
        for role in draft["team"]["agents"]
        if role["role_id"] == "execution-core"
    )

    draft["schedules"].append(
        {
            "schedule_id": "daily-control-loop",
            "owner_agent_id": execution_core["agent_id"],
            "title": "Daily Control Loop",
            "summary": "Run the daily execution control loop across the full week.",
            "cron": "0 9 * * 1-7",
            "timezone": "UTC",
            "dispatch_channel": "console",
            "dispatch_mode": "final",
        },
    )

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(
        schedule["schedule_id"].endswith("daily-control-loop")
        for schedule in bootstrap_schedule_summaries(payload)
    )

    instance_id = payload["team"]["team_id"]
    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    assert any(
        schedule["cron"] == "0 9 * * 1-7"
        for schedule in runtime_detail.json()["schedules"]
    )


def test_operating_cycle_assignment_unit_uses_role_scoped_session_ids() -> None:
    service = IndustryService.__new__(IndustryService)
    service._operating_lane_service = None
    service._goal_service = SimpleNamespace()

    record = IndustryInstanceRecord(
        instance_id="buddy:profile-1:industry-1",
        owner_scope="profile-1",
        label="Trader Buddy",
        summary="Trading execution carrier",
        bootstrap_kind="industry-v1",
        profile_payload={"industry": "Trading"},
        team_payload={"agents": []},
        execution_core_identity_payload={"role_id": "execution-core"},
        status="active",
    )
    item = BacklogItemRecord(
        id="backlog-1",
        industry_instance_id=record.instance_id,
        title="Review next moves",
        summary="Split the next operating moves across the specialist team.",
        status="open",
        metadata={},
    )
    cycle = OperatingCycleRecord(
        id="cycle-1",
        industry_instance_id=record.instance_id,
        title="Cycle 1",
        summary="Initial operating cycle",
        cycle_kind="daily",
        status="active",
    )
    researcher_assignment = AssignmentRecord(
        id="assignment-researcher",
        industry_instance_id=record.instance_id,
        cycle_id=cycle.id,
        backlog_item_id=item.id,
        owner_agent_id=f"{record.instance_id}:market-research",
        owner_role_id="market-research",
        title="Research focus strategies",
        summary="Find the next trading setups.",
        status="queued",
    )
    risk_assignment = AssignmentRecord(
        id="assignment-risk",
        industry_instance_id=record.instance_id,
        cycle_id=cycle.id,
        backlog_item_id=item.id,
        owner_agent_id=f"{record.instance_id}:growth-focus",
        owner_role_id="growth-focus",
        title="Set risk boundaries",
        summary="Define the risk boundary for the next cycle.",
        status="queued",
    )

    researcher_unit = service._build_operating_cycle_assignment_unit(
        record=record,
        item=item,
        cycle=cycle,
        assignment=researcher_assignment,
        actor="copaw-agent-runner",
    )
    risk_unit = service._build_operating_cycle_assignment_unit(
        record=record,
        item=item,
        cycle=cycle,
        assignment=risk_assignment,
        actor="copaw-agent-runner",
    )

    control_thread_id = f"industry-chat:{record.instance_id}:execution-core"
    assert researcher_unit.context["control_thread_id"] == control_thread_id
    assert risk_unit.context["control_thread_id"] == control_thread_id
    assert researcher_unit.context["session_id"] != risk_unit.context["session_id"]
    assert researcher_unit.context["session_id"] != control_thread_id
    assert risk_unit.context["session_id"] != control_thread_id
    assert researcher_unit.context["session_id"].endswith(":market-research")
    assert risk_unit.context["session_id"].endswith(":growth-focus")


def test_close_task_execution_closure_continues_next_assignment_step(tmp_path) -> None:
    app = _build_industry_app(tmp_path)

    instance_id = "buddy:profile-1:industry-1"
    cycle = OperatingCycleRecord(
        id="cycle-1",
        industry_instance_id=instance_id,
        title="Cycle 1",
        summary="Initial operating cycle",
        cycle_kind="daily",
        status="active",
    )
    record = IndustryInstanceRecord(
        instance_id=instance_id,
        owner_scope="profile-1",
        label="Trader Buddy",
        summary="Trading execution carrier",
        bootstrap_kind="industry-v1",
        profile_payload={"industry": "Trading"},
        team_payload={"agents": []},
        execution_core_identity_payload={"role_id": "execution-core"},
        current_cycle_id=cycle.id,
        status="active",
    )
    backlog_item = BacklogItemRecord(
        id="backlog-1",
        industry_instance_id=instance_id,
        cycle_id=cycle.id,
        title="Define operating system rules",
        summary="Turn trading rules into a concrete operating checklist.",
        status="open",
        metadata={},
    )
    assignment = AssignmentRecord(
        id="assignment-1",
        industry_instance_id=instance_id,
        cycle_id=cycle.id,
        backlog_item_id=backlog_item.id,
        owner_agent_id=f"{instance_id}:growth-focus",
        owner_role_id="growth-focus",
        title="Define Operating System Rules",
        summary="Create the rule checklist and return the next move.",
        status="running",
        metadata={
            "plan_steps": [
                "Confirm the backlog goal and the expected delivery boundary.",
                "Draft the concrete trading operating rules.",
                "Return the completion summary together with the next recommendation.",
            ],
            "owner_agent_id": f"{instance_id}:growth-focus",
            "industry_role_id": "growth-focus",
            "industry_role_name": "Growth Focus",
            "role_name": "Growth Focus",
            "role_summary": "Own the operating-system design work.",
            "mission": "Turn the trading direction into a concrete operating checklist.",
            "task_mode": "autonomy-cycle",
            "report_back_mode": "summary",
            "control_thread_id": f"industry-chat:{instance_id}:execution-core",
            "session_id": f"industry-chat:{instance_id}:execution-core",
            "environment_ref": f"session:console:industry:{instance_id}",
        },
    )

    app.state.industry_instance_repository.upsert_instance(record)
    app.state.operating_cycle_repository.upsert_cycle(cycle)
    app.state.backlog_item_repository.upsert_item(backlog_item)
    app.state.assignment_repository.upsert_assignment(assignment)

    unit = app.state.industry_service._build_operating_cycle_assignment_unit(
        record=record,
        item=backlog_item,
        cycle=cycle,
        assignment=assignment,
        actor="copaw-agent-runner",
    )
    compiler = app.state.goal_service._compiler
    tasks = compiler.compile_to_kernel_tasks(unit, specs=compiler.compile(unit))
    assert len(tasks) == 1
    step_one_task = tasks[0]

    app.state.task_repository.upsert_task(
        TaskRecord(
            id=step_one_task.id,
            title=step_one_task.title,
            summary=step_one_task.title,
            task_type=step_one_task.capability_ref or "system:dispatch_query",
            status="completed",
            owner_agent_id=step_one_task.owner_agent_id,
            acceptance_criteria=encode_kernel_task_metadata(step_one_task),
            current_risk_level=step_one_task.risk_level,
            industry_instance_id=instance_id,
            assignment_id=assignment.id,
            cycle_id=cycle.id,
            report_back_mode="summary",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id=step_one_task.id,
            runtime_status="terminated",
            current_phase="completed",
            risk_level=step_one_task.risk_level,
            last_result_summary="Step 1 completed.",
            last_owner_agent_id=step_one_task.owner_agent_id,
        ),
    )
    app.state.assignment_repository.upsert_assignment(
        assignment.model_copy(update={"task_id": step_one_task.id}),
    )

    result = app.state.industry_service.close_task_execution_closure(
        industry_instance_id=instance_id,
        cycle_id=cycle.id,
        assignment_id=assignment.id,
        task_id=step_one_task.id,
    )

    assignment_tasks = app.state.task_repository.list_tasks(
        assignment_ids=[assignment.id],
        limit=None,
    )
    assert len(assignment_tasks) == 2
    next_task = max(
        assignment_tasks,
        key=lambda item: item.updated_at or item.created_at,
    )
    assert next_task.id != step_one_task.id
    next_metadata = decode_kernel_task_metadata(next_task.acceptance_criteria)
    assert next_metadata is not None
    assert next_metadata["payload"]["compiler"]["plan_step_number"] == 2
    assert next_metadata["payload"]["request"]["session_id"].endswith(":growth-focus")

    updated_assignment = app.state.assignment_repository.get_assignment(assignment.id)
    assert updated_assignment is not None
    assert updated_assignment.task_id == next_task.id
    assert updated_assignment.status in {"queued", "running"}
    assert result is not None
    assert result["assignment_statuses"][assignment.id] in {"queued", "running"}
    assert (
        app.state.agent_report_repository.list_reports(
            industry_instance_id=instance_id,
            assignment_id=assignment.id,
            limit=None,
        )
        == []
    )


def test_industry_team_update_route_adds_role_to_existing_instance(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    owner_scope = "industry-v1-northwind-robotics"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
        ),
    )
    base_draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)

    first_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": base_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert first_response.status_code == 200
    instance_id = first_response.json()["team"]["team_id"]

    expanded_draft = base_draft.model_copy(deep=True)
    expanded_draft = expanded_draft.model_copy(
        update={
            "team": expanded_draft.team.model_copy(
                update={"team_id": "industry-v1-should-be-ignored"},
            ),
        },
    )
    extra_role = IndustryRoleBlueprint(
        role_id="visual-design",
        agent_id="industry-visual-design-northwind-robotics",
        name="Northwind Visual Design Lead",
        role_name="Visual Design Lead",
        role_summary="Owns image generation, creative refinement, and visual packaging.",
        mission="Turn product and campaign requirements into reusable visual assets.",
        goal_kind="visual-design",
        agent_class="business",
        activation_mode="persistent",
        suspendable=False,
        reports_to=base_draft.team.agents[0].agent_id,
        risk_level="guarded",
        environment_constraints=["workspace draft/edit allowed"],
        allowed_capabilities=["system:dispatch_query", "tool:read_file"],
        evidence_expectations=["design brief", "asset proof"],
    )
    expanded_draft.team.agents.append(extra_role)
    expanded_draft.goals.append(
        IndustryDraftGoal(
            goal_id="visual-design-goal",
            kind="visual-design",
            owner_agent_id=extra_role.agent_id,
            title="Build the first reusable visual asset pack",
            summary="Define how product visuals are generated and reviewed.",
            plan_steps=[
                "Clarify the visual brief and output specs.",
                "Produce the first reusable visual asset set.",
            ],
        ),
    )

    response = client.put(
        f"/industry/v1/instances/{instance_id}/team",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": expanded_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["team"]["team_id"] == instance_id
    assert any(
        agent["agent_id"] == extra_role.agent_id for agent in payload["team"]["agents"]
    )

    stored_instance = app.state.industry_instance_repository.get_instance(instance_id)
    assert stored_instance is not None
    assert extra_role.agent_id in stored_instance.agent_ids
    assert any(
        agent["role_id"] == "visual-design"
        for agent in stored_instance.team_payload["agents"]
    )
    assert (
        app.state.agent_profile_override_repository.get_override(extra_role.agent_id)
        is not None
    )


def test_industry_bootstrap_preserves_explicit_mcp_and_skill_capabilities_in_role_allowlist(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
    draft = preview_payload["draft"]
    business_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["role_id"] not in {"execution-core", "researcher"}
    )
    business_role["allowed_capabilities"] = [
        "system:dispatch_query",
        "tool:browser_use",
        "mcp:desktop_windows",
        "skill:test-skill",
    ]

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    role_payload = next(
        agent
        for agent in payload["team"]["agents"]
        if agent["agent_id"] == business_role["agent_id"]
    )
    assert "mcp:desktop_windows" in role_payload["allowed_capabilities"]
    assert "skill:test-skill" in role_payload["allowed_capabilities"]

    override = app.state.agent_profile_override_repository.get_override(
        business_role["agent_id"],
    )
    assert override is not None
    assert "mcp:desktop_windows" in (override.capabilities or [])
    assert "skill:test-skill" in (override.capabilities or [])


def test_industry_bootstrap_executes_install_plan_and_assigns_capabilities(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=DesktopIndustryDraftGenerator(),
    )
    client = TestClient(app)

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
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config") as mock_save,
    ):
        mock_load.return_value = SimpleNamespace(
            mcp=SimpleNamespace(clients={}),
        )
        response = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": preview_payload["profile"],
                "draft": draft,
                "install_plan": [
                    {
                        "install_kind": "mcp-template",
                        "template_id": "desktop-windows",
                        "client_key": "desktop_windows",
                        "source_kind": "install-template",
                        "capability_assignment_mode": "merge",
                        "target_agent_ids": [target_role["agent_id"]],
                    }
                ],
                "auto_activate": True,
                "auto_dispatch": False,
                "execute": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["install_results"][0]["template_id"] == "desktop-windows"
    assert payload["install_results"][0]["client_key"] == "desktop_windows"
    assert payload["install_results"][0]["status"] == "installed"
    assert payload["install_results"][0]["installed"] is True
    assert payload["install_results"][0]["assignment_results"][0]["agent_id"] == (
        target_role["agent_id"]
    )
    assert payload["install_results"][0]["assignment_results"][0]["status"] == "assigned"
    mock_save.assert_called_once()

    override = app.state.agent_profile_override_repository.get_override(
        target_role["agent_id"],
    )
    assert override is not None
    assert "mcp:desktop_windows" in (override.capabilities or [])


def test_industry_bootstrap_executes_browser_runtime_install_plan(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "browser onboarding workflows",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "install_plan": [
                {
                    "install_kind": "builtin-runtime",
                    "template_id": "browser-local",
                    "client_key": "browser-local-default",
                    "source_kind": "install-template",
                    "capability_assignment_mode": "merge",
                    "target_agent_ids": [target_role["agent_id"]],
                }
            ],
            "auto_activate": True,
            "auto_dispatch": False,
            "execute": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["install_results"][0]["template_id"] == "browser-local"
    assert payload["install_results"][0]["install_kind"] == "builtin-runtime"
    assert payload["install_results"][0]["client_key"] == "browser-local-default"
    assert payload["install_results"][0]["status"] == "installed"
    assert payload["install_results"][0]["installed"] is True
    default_profile = app.state.browser_runtime_service.get_default_profile()
    assert default_profile is not None
    assert default_profile.profile_id == "browser-local-default"


def test_industry_bootstrap_browser_runtime_install_skips_unrelated_installed_catalog_scans(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "browser onboarding workflows",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    with (
        patch.object(
            app.state.industry_service,
            "_list_installed_mcp_client_keys",
            side_effect=AssertionError("browser-local install should not scan MCP client keys"),
        ),
        patch.object(
            app.state.industry_service,
            "_list_installed_mcp_client_configs",
            side_effect=AssertionError("browser-local install should not scan MCP client configs"),
        ),
        patch.object(
            app.state.industry_service,
            "_list_installed_skill_specs",
            side_effect=AssertionError("browser-local install should not scan skill specs"),
        ),
    ):
        response = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": preview_payload["profile"],
                "draft": draft,
                "install_plan": [
                    {
                        "install_kind": "builtin-runtime",
                        "template_id": "browser-local",
                        "client_key": "browser-local-default",
                        "source_kind": "install-template",
                        "capability_assignment_mode": "merge",
                        "target_agent_ids": [target_role["agent_id"]],
                    }
                ],
                "auto_activate": True,
                "auto_dispatch": False,
                "execute": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["install_results"][0]["template_id"] == "browser-local"
    assert payload["install_results"][0]["status"] == "installed"


def test_industry_auto_gap_closure_reuses_installed_capability_and_assigns_target_agent(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=DesktopIndustryDraftGenerator(),
    )
    client = TestClient(app)

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
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    install_item = IndustryBootstrapInstallItem(
        install_kind="mcp-template",
        template_id="desktop-windows",
        client_key="desktop_windows",
        capability_ids=["mcp:desktop_windows"],
    )
    recommendation = IndustryCapabilityRecommendation(
        recommendation_id="desktop-windows-gap",
        install_kind="mcp-template",
        template_id="desktop-windows",
        title="Desktop Windows Runtime",
        default_client_key="desktop_windows",
        capability_ids=["mcp:desktop_windows"],
        target_agent_ids=[target_role["agent_id"]],
        risk_level="auto",
        source_kind="install-template",
        installed=True,
    )

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config") as mock_mcp_load,
        patch("copaw.industry.service_activation.load_config") as mock_industry_load,
    ):
        config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
        mock_load.return_value = config
        mock_mcp_load.return_value = config
        mock_industry_load.return_value = config
        first_results = asyncio.run(
            app.state.industry_service.execute_install_plan_for_instance(
                instance_id,
                [install_item],
            ),
        )
        result = asyncio.run(
            app.state.industry_service.auto_close_capability_gap_for_instance(
                instance_id,
                recommendation,
                target_agent_ids=[target_role["agent_id"]],
                capability_assignment_mode="merge",
            ),
        )

    assert first_results[0].status == "installed"
    assert result.status == "already-installed"
    assert result.assignment_results[0].agent_id == target_role["agent_id"]
    override = app.state.agent_profile_override_repository.get_override(
        target_role["agent_id"],
    )
    assert override is not None
    assert "mcp:desktop_windows" in (override.capabilities or [])
    runtime = app.state.agent_runtime_repository.get_runtime(target_role["agent_id"])
    assert runtime is not None
    capability_layers = runtime.metadata["capability_layers"]
    assert "mcp:desktop_windows" in capability_layers["role_prototype_capability_ids"]
    assert capability_layers["seat_instance_capability_ids"] == []
    assert "mcp:desktop_windows" in capability_layers["effective_capability_ids"]


def test_industry_auto_gap_closure_installs_auto_recommendation_for_target_agent(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "browser onboarding workflows",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    recommendation = IndustryCapabilityRecommendation(
        recommendation_id="browser-local-gap",
        install_kind="builtin-runtime",
        template_id="browser-local",
        title="Browser Local Runtime",
        default_client_key="browser-local-default",
        capability_ids=["tool:browser_use"],
        target_agent_ids=[target_role["agent_id"]],
        risk_level="auto",
        source_kind="install-template",
    )

    result = asyncio.run(
        app.state.industry_service.auto_close_capability_gap_for_instance(
            instance_id,
            recommendation,
            target_agent_ids=[target_role["agent_id"]],
            capability_assignment_mode="merge",
        ),
    )

    assert result.status == "installed"
    assert result.assignment_results[0].agent_id == target_role["agent_id"]
    override = app.state.agent_profile_override_repository.get_override(
        target_role["agent_id"],
    )
    assert override is not None
    assert "tool:browser_use" in (override.capabilities or [])


def test_industry_auto_gap_closure_uses_governed_kernel_tasks_for_mcp_install(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=DesktopIndustryDraftGenerator(),
    )
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Field Operations",
            "company_name": "Northwind Robotics",
            "product": "desktop follow-up workflows",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    recommendation = IndustryCapabilityRecommendation(
        recommendation_id="desktop-windows-governed-gap",
        install_kind="mcp-template",
        template_id="desktop-windows",
        title="Desktop Windows Runtime",
        default_client_key="desktop_windows",
        capability_ids=["mcp:desktop_windows"],
        target_agent_ids=[target_role["agent_id"]],
        risk_level="auto",
        source_kind="install-template",
    )

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config") as mock_mcp_load,
        patch("copaw.industry.service_activation.load_config") as mock_industry_load,
    ):
        config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
        mock_load.return_value = config
        mock_mcp_load.return_value = config
        mock_industry_load.return_value = config
        result = asyncio.run(
            app.state.industry_service.auto_close_capability_gap_for_instance(
                instance_id,
                recommendation,
                target_agent_ids=[target_role["agent_id"]],
                capability_assignment_mode="merge",
            ),
        )

    assert result.status == "installed"
    assert app.state.capability_service.get_mcp_client_info("desktop_windows") is not None
    install_tasks = app.state.task_repository.list_tasks(
        task_type="system:create_mcp_client",
    )
    assignment_tasks = app.state.task_repository.list_tasks(
        task_type="system:apply_capability_lifecycle",
    )
    assert install_tasks
    assert assignment_tasks
    assert any(task.owner_agent_id == "copaw-agent-runner" for task in install_tasks)
    assert any(task.owner_agent_id == "copaw-agent-runner" for task in assignment_tasks)


def test_industry_auto_gap_closure_replace_mode_swaps_seat_delta_capabilities(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "browser onboarding workflows",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    legacy_override = app.state.agent_profile_override_repository.get_override(
        target_role["agent_id"],
    )
    assert legacy_override is not None
    app.state.agent_profile_override_repository.upsert_override(
        legacy_override.model_copy(
            update={
                "capabilities": ["skill:legacy-seat-pack"],
                "reason": "seed legacy seat delta",
            },
        ),
    )
    app.state.industry_service.sync_agent_runtime_capability_override(
        agent_id=target_role["agent_id"],
        capability_ids=["skill:legacy-seat-pack"],
    )

    recommendation = IndustryCapabilityRecommendation(
        recommendation_id="desktop-windows-replace-gap",
        install_kind="mcp-template",
        template_id="desktop-windows",
        title="Desktop Windows Runtime",
        default_client_key="desktop_windows",
        capability_ids=["mcp:desktop_windows"],
        target_agent_ids=[target_role["agent_id"]],
        risk_level="auto",
        source_kind="install-template",
    )

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config") as mock_mcp_load,
        patch("copaw.industry.service_activation.load_config") as mock_industry_load,
    ):
        config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
        mock_load.return_value = config
        mock_mcp_load.return_value = config
        mock_industry_load.return_value = config
        result = asyncio.run(
            app.state.industry_service.auto_close_capability_gap_for_instance(
                instance_id,
                recommendation,
                target_agent_ids=[target_role["agent_id"]],
                capability_assignment_mode="replace",
            ),
        )

    assert result.status == "installed"
    override = app.state.agent_profile_override_repository.get_override(
        target_role["agent_id"],
    )
    assert override is not None
    assert "mcp:desktop_windows" in (override.capabilities or [])
    assert "skill:legacy-seat-pack" not in (override.capabilities or [])
    assert "tool:browser_use" in (override.capabilities or [])
    runtime = app.state.agent_runtime_repository.get_runtime(target_role["agent_id"])
    assert runtime is not None
    capability_layers = runtime.metadata["capability_layers"]
    assert "mcp:desktop_windows" not in capability_layers["role_prototype_capability_ids"]
    assert capability_layers["seat_instance_capability_ids"] == ["mcp:desktop_windows"]
    assert "skill:legacy-seat-pack" not in capability_layers["seat_instance_capability_ids"]
    assert "tool:browser_use" in capability_layers["role_prototype_capability_ids"]


def test_industry_auto_gap_closure_replace_mode_preserves_session_overlay_truth(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "browser onboarding workflows",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    target_agent_id = target_role["agent_id"]

    legacy_override = app.state.agent_profile_override_repository.get_override(target_agent_id)
    assert legacy_override is not None
    app.state.agent_profile_override_repository.upsert_override(
        legacy_override.model_copy(
            update={
                "capabilities": ["skill:legacy-seat-pack"],
                "reason": "seed legacy seat delta",
            },
        ),
    )
    app.state.industry_service.sync_agent_runtime_capability_override(
        agent_id=target_agent_id,
        capability_ids=["skill:legacy-seat-pack"],
    )
    attached = app.state.industry_service.attach_candidate_to_scope(
        target_agent_id=target_agent_id,
        capability_ids=["mcp:browser-temp"],
        selected_scope="session",
        scope_ref="session-browser-temp",
        selected_seat_ref="seat-browser-primary",
        candidate_id="candidate-temp-overlay",
        replacement_target_ids=[],
        rollback_target_ids=[],
        reason="seed session overlay",
    )
    assert attached["success"] is True

    recommendation = IndustryCapabilityRecommendation(
        recommendation_id="desktop-windows-preserve-overlay-gap",
        install_kind="mcp-template",
        template_id="desktop-windows",
        title="Desktop Windows Runtime",
        default_client_key="desktop_windows",
        capability_ids=["mcp:desktop_windows"],
        target_agent_ids=[target_agent_id],
        risk_level="auto",
        source_kind="install-template",
    )

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config") as mock_mcp_load,
        patch("copaw.industry.service_activation.load_config") as mock_industry_load,
    ):
        config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
        mock_load.return_value = config
        mock_mcp_load.return_value = config
        mock_industry_load.return_value = config
        result = asyncio.run(
            app.state.industry_service.auto_close_capability_gap_for_instance(
                instance_id,
                recommendation,
                target_agent_ids=[target_agent_id],
                capability_assignment_mode="replace",
            ),
        )

    assert result.status == "installed"
    runtime = app.state.agent_runtime_repository.get_runtime(target_agent_id)
    assert runtime is not None
    capability_layers = runtime.metadata["capability_layers"]
    assert capability_layers["seat_instance_capability_ids"] == ["mcp:desktop_windows"]
    assert capability_layers["session_overlay_capability_ids"] == ["mcp:browser-temp"]
    assert "mcp:browser-temp" in capability_layers["effective_capability_ids"]


def test_industry_auto_gap_closure_protected_replace_stays_in_governed_waiting_confirm(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "browser onboarding workflows",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    target_agent_id = target_role["agent_id"]

    legacy_override = app.state.agent_profile_override_repository.get_override(target_agent_id)
    assert legacy_override is not None
    app.state.agent_profile_override_repository.upsert_override(
        legacy_override.model_copy(
            update={
                "capabilities": ["skill:legacy-seat-pack"],
                "reason": "seed protected seat delta",
            },
        ),
    )
    app.state.industry_service.sync_agent_runtime_capability_override(
        agent_id=target_agent_id,
        capability_ids=["skill:legacy-seat-pack"],
    )

    recommendation = IndustryCapabilityRecommendation(
        recommendation_id="desktop-windows-protected-replace-gap",
        install_kind="mcp-template",
        template_id="desktop-windows",
        title="Desktop Windows Runtime",
        default_client_key="desktop_windows",
        capability_ids=["mcp:desktop_windows"],
        target_agent_ids=[target_agent_id],
        risk_level="auto",
        source_kind="install-template",
    )

    original_builder = app.state.industry_service._build_capability_lifecycle_assignment_payload
    app.state.industry_service._build_capability_lifecycle_assignment_payload = (
        lambda **kwargs: {
            **original_builder(**kwargs),
            "replacement_relation": "replace_requested",
            "protection_flags": ["protected_from_auto_replace"],
        }
    )
    try:
        with (
            patch("copaw.capabilities.service.load_config") as mock_load,
            patch("copaw.capabilities.service.save_config"),
            patch("copaw.capabilities.sources.mcp.load_config") as mock_mcp_load,
            patch("copaw.industry.service_activation.load_config") as mock_industry_load,
        ):
            config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
            mock_load.return_value = config
            mock_mcp_load.return_value = config
            mock_industry_load.return_value = config
            result = asyncio.run(
                app.state.industry_service.auto_close_capability_gap_for_instance(
                    instance_id,
                    recommendation,
                    target_agent_ids=[target_agent_id],
                    capability_assignment_mode="replace",
                ),
            )
    finally:
        app.state.industry_service._build_capability_lifecycle_assignment_payload = (
            original_builder
        )

    assert result.status == "installed"
    assert result.assignment_results
    assert result.assignment_results[0].status == "failed"
    assert "protection" in result.assignment_results[0].detail.lower()
    runtime = app.state.agent_runtime_repository.get_runtime(target_agent_id)
    assert runtime is not None
    capability_layers = runtime.metadata["capability_layers"]
    assert capability_layers["seat_instance_capability_ids"] == ["skill:legacy-seat-pack"]
    lifecycle_tasks = app.state.task_repository.list_tasks(
        task_type="system:apply_capability_lifecycle",
    )
    assert lifecycle_tasks
    assert any(task.status == "blocked" or task.status == "pending" or task.status == "failed" for task in lifecycle_tasks)


def test_industry_auto_gap_closure_skips_guarded_recommendation(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
    draft = preview_payload["draft"]
    target_role = next(
        agent
        for agent in draft["team"]["agents"]
        if agent["agent_class"] == "business" and agent["role_id"] != "execution-core"
    )

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    recommendation = IndustryCapabilityRecommendation(
        recommendation_id="guarded-skill-gap",
        install_kind="hub-skill",
        template_id="research-pack",
        title="Research Pack",
        capability_ids=["skill:research-pack"],
        target_agent_ids=[target_role["agent_id"]],
        risk_level="guarded",
        source_kind="skillhub-curated",
        source_url="https://example.com/research-pack.zip",
        version="1.0.0",
        review_required=True,
    )

    result = asyncio.run(
        app.state.industry_service.auto_close_capability_gap_for_instance(
            instance_id,
            recommendation,
            target_agent_ids=[target_role["agent_id"]],
            capability_assignment_mode="merge",
        ),
    )

    assert result.status == "skipped"
    assert result.installed is False
    assert result.assignment_results == []
    override = app.state.agent_profile_override_repository.get_override(
        target_role["agent_id"],
    )
    assert override is None or "skill:research-pack" not in (override.capabilities or [])


def test_industry_rebootstrap_prunes_stale_agents_and_archives_superseded_goals(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    owner_scope = "industry-v1-northwind-robotics"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
        ),
    )
    base_draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)
    expanded_draft = base_draft.model_copy(deep=True)
    extra_role = IndustryRoleBlueprint(
        role_id="field-enablement",
        agent_id="industry-field-enablement-northwind-robotics",
        name="Northwind Field Enablement Lead",
        role_name="Field Enablement Lead",
        role_summary="Owns pilot onboarding and field rollout readiness.",
        mission="Make pilot rollout repeatable for frontline operators.",
        goal_kind="field-enablement",
        agent_class="business",
        activation_mode="persistent",
        suspendable=False,
        reports_to=base_draft.team.agents[0].agent_id,
        risk_level="guarded",
        environment_constraints=["workspace draft/edit allowed"],
        allowed_capabilities=["system:dispatch_query", "tool:browser_use"],
        evidence_expectations=["pilot rollout checklist"],
    )
    expanded_draft.team.agents.append(extra_role)
    expanded_draft.goals.append(
        IndustryDraftGoal(
            goal_id="field-enablement-goal",
            kind="field-enablement",
            owner_agent_id=extra_role.agent_id,
            title="Make the first pilot rollout repeatable",
            summary="Define the enablement path for frontline pilot operators.",
            plan_steps=[
                "Map the initial rollout workflow.",
                "Clarify onboarding checkpoints.",
            ],
        ),
    )

    first_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": expanded_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    first_goal_ids = set(bootstrap_goal_ids(first_payload))
    instance_id = first_payload["team"]["team_id"]
    assert app.state.agent_profile_override_repository.get_override(extra_role.agent_id) is not None

    second_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": base_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()
    second_goal_ids = set(bootstrap_goal_ids(second_payload))
    stale_goal_ids = first_goal_ids - second_goal_ids

    assert second_payload["team"]["team_id"] == instance_id
    assert stale_goal_ids
    assert app.state.agent_profile_override_repository.get_override(extra_role.agent_id) is None

    agents_response = client.get("/runtime-center/agents")
    assert agents_response.status_code == 200
    industry_agent_ids = {
        item["agent_id"]
        for item in agents_response.json()
        if item.get("industry_instance_id") == instance_id
    }
    assert industry_agent_ids == {
        agent.agent_id
        for agent in base_draft.team.agents
        if agent.role_id != "execution-core"
    }
    assert extra_role.agent_id not in industry_agent_ids

    goal_status_by_id = {
        goal.id: goal.status
        for goal in app.state.goal_service.list_goals(owner_scope=owner_scope)
    }
    assert all(
        goal_status_by_id[goal_id] in {"active", "paused", "completed"}
        for goal_id in second_goal_ids
    )
    assert all(goal_status_by_id[goal_id] == "archived" for goal_id in stale_goal_ids)
    assert all(
        app.state.goal_override_repository.get_override(goal_id).status == "archived"
        for goal_id in stale_goal_ids
    )


def test_industry_team_update_route_prunes_removed_roles(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    owner_scope = "industry-v1-northwind-robotics"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
        ),
    )
    base_draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)
    expanded_draft = base_draft.model_copy(deep=True)
    extra_role = IndustryRoleBlueprint(
        role_id="visual-design",
        agent_id="industry-visual-design-northwind-robotics",
        name="Northwind Visual Design Lead",
        role_name="Visual Design Lead",
        role_summary="Owns image generation, creative refinement, and visual packaging.",
        mission="Turn product and campaign requirements into reusable visual assets.",
        goal_kind="visual-design",
        agent_class="business",
        activation_mode="persistent",
        suspendable=False,
        reports_to=base_draft.team.agents[0].agent_id,
        risk_level="guarded",
        environment_constraints=["workspace draft/edit allowed"],
        allowed_capabilities=["system:dispatch_query", "tool:read_file"],
        evidence_expectations=["design brief", "asset proof"],
    )
    expanded_draft.team.agents.append(extra_role)
    expanded_draft.goals.append(
        IndustryDraftGoal(
            goal_id="visual-design-goal",
            kind="visual-design",
            owner_agent_id=extra_role.agent_id,
            title="Build the first reusable visual asset pack",
            summary="Define how product visuals are generated and reviewed.",
            plan_steps=[
                "Clarify the visual brief and output specs.",
                "Produce the first reusable visual asset set.",
            ],
        ),
    )

    first_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": expanded_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert first_response.status_code == 200
    instance_id = first_response.json()["team"]["team_id"]
    assert app.state.agent_profile_override_repository.get_override(extra_role.agent_id) is not None

    response = client.put(
        f"/industry/v1/instances/{instance_id}/team",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": base_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["team"]["team_id"] == instance_id
    assert all(
        agent["agent_id"] != extra_role.agent_id for agent in payload["team"]["agents"]
    )
    assert app.state.agent_profile_override_repository.get_override(extra_role.agent_id) is None

    agents_response = client.get("/runtime-center/agents")
    assert agents_response.status_code == 200
    industry_agent_ids = {
        item["agent_id"]
        for item in agents_response.json()
        if item.get("industry_instance_id") == instance_id
    }
    assert extra_role.agent_id not in industry_agent_ids


def test_industry_bootstrap_retire_previous_active_instance_globally(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    first_owner_scope = "industry-v1-northwind-robotics"
    first_profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
        ),
    )
    first_draft = FakeIndustryDraftGenerator().build_draft(
        first_profile,
        first_owner_scope,
    )

    first_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": first_profile.model_dump(mode="json"),
            "draft": first_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    first_instance_id = first_payload["team"]["team_id"]
    first_goal_ids = bootstrap_goal_ids(first_payload)
    first_schedule_ids = bootstrap_schedule_ids(first_payload)
    assert app.state.agent_thread_binding_repository.list_bindings(
        industry_instance_id=first_instance_id,
        active_only=False,
        limit=None,
    )

    second_owner_scope = "industry-v1-harbor-studio"
    second_profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Social Commerce",
            company_name="Harbor Studio",
            product="XHS content growth services",
            goals=["build the first growth pipeline"],
        ),
    )
    second_draft = FakeIndustryDraftGenerator().build_draft(
        second_profile,
        second_owner_scope,
    )

    second_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": second_profile.model_dump(mode="json"),
            "draft": second_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()
    second_instance_id = second_payload["team"]["team_id"]
    second_goal_ids = bootstrap_goal_ids(second_payload)

    assert second_instance_id != first_instance_id

    summaries = client.get("/industry/v1/instances")
    assert summaries.status_code == 200
    assert [item["instance_id"] for item in summaries.json()] == [second_instance_id]

    runtime_summaries = client.get("/runtime-center/industry")
    assert runtime_summaries.status_code == 200
    assert [item["instance_id"] for item in runtime_summaries.json()] == [second_instance_id]

    first_record = app.state.industry_instance_repository.get_instance(first_instance_id)
    second_record = app.state.industry_instance_repository.get_instance(second_instance_id)
    assert first_record is not None
    assert second_record is not None
    assert first_record.status == "retired"
    assert second_record.status == "active"

    goal_status_by_id = {
        goal.id: goal.status
        for goal in app.state.goal_service.list_goals()
    }
    assert all(goal_status_by_id[goal_id] == "archived" for goal_id in first_goal_ids)
    assert all(
        goal_status_by_id[goal_id] in {"active", "paused", "completed"}
        for goal_id in second_goal_ids
    )
    assert all(
        app.state.goal_override_repository.get_override(goal_id).status == "archived"
        for goal_id in first_goal_ids
    )

    for schedule_id in first_schedule_ids:
        schedule = app.state.schedule_repository.get_schedule(schedule_id)
        assert schedule is not None
        assert schedule.status == "paused"
        assert schedule.enabled is False
        assert schedule.spec_payload.get("enabled") is False

    assert app.state.agent_thread_binding_repository.list_bindings(
        industry_instance_id=first_instance_id,
        active_only=False,
        limit=None,
    ) == []

    retired_strategies = app.state.strategy_memory_service.list_strategies(
        industry_instance_id=first_instance_id,
        limit=10,
    )
    assert retired_strategies
    assert retired_strategies[0].status == "retired"
    assert retired_strategies[0].current_focuses == []


def test_public_bootstrap_auto_activate_keeps_instance_active_without_legacy_goal_dispatch(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": preview_payload["draft"],
            "auto_activate": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    instance_id = payload["team"]["team_id"]
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    assert record.status == "active"
    assert record.autonomy_status == "coordinating"
    assert "goals" not in payload
    assert "schedules" not in payload
    assert payload["draft"]["team"]["team_id"] == instance_id
    assert payload["cycle"]["industry_instance_id"] == instance_id
    assert payload["assignments"]
    assert app.state.task_repository.list_tasks(
        industry_instance_id=instance_id,
        limit=None,
    ) == []

    strategies = app.state.strategy_memory_service.list_strategies(
        industry_instance_id=instance_id,
        limit=5,
    )
    assert strategies
    assert isinstance(strategies[0].current_focuses, list)


def test_public_bootstrap_auto_dispatch_materializes_assignment_tasks_without_goal_dispatch(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": preview_payload["draft"],
            "auto_activate": True,
            "auto_dispatch": True,
            "execute": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    instance_id = payload["team"]["team_id"]
    assert "goals" not in payload
    assert "schedules" not in payload
    assert payload["draft"]["goals"]
    assert payload["assignments"]

    created_tasks = app.state.task_repository.list_tasks(
        industry_instance_id=instance_id,
        limit=None,
    )
    assert created_tasks
    assert all(task.assignment_id for task in created_tasks)


def test_public_bootstrap_persists_draft_truth_and_uses_draft_goal_identity(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    owner_scope = "industry-v1-northwind-robotics"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Equipment",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["stabilize the first operating loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": True,
            "auto_dispatch": True,
            "execute": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    instance_id = payload["team"]["team_id"]
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None

    canonicalized_draft = canonicalize_industry_draft(
        profile,
        draft,
        owner_scope=owner_scope,
    )
    draft_goal_ids = [goal.goal_id for goal in canonicalized_draft.goals]
    assert record.draft_payload["team"]["team_id"] == canonicalized_draft.team.team_id
    assert [item["goal_id"] for item in record.draft_payload["goals"]] == draft_goal_ids
    assert [item["goal_id"] for item in payload["draft"]["goals"]] == draft_goal_ids
    assert "goals" not in payload
    assert "schedules" not in payload

    assignments = app.state.assignment_repository.list_assignments(
        industry_instance_id=instance_id,
        limit=None,
    )
    assert assignments
    assert {
        assignment.goal_id
        for assignment in assignments
        if assignment.goal_id is not None
    } == set(draft_goal_ids)

    tasks = app.state.task_repository.list_tasks(
        industry_instance_id=instance_id,
        limit=None,
    )
    assert tasks
    assert {
        task.goal_id
        for task in tasks
        if task.goal_id is not None
    }.issubset(set(draft_goal_ids))


def test_public_bootstrap_hard_cuts_legacy_goal_schedule_response_surface(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": preview_payload["draft"],
            "auto_activate": True,
            "auto_dispatch": False,
            "execute": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "goals" not in payload
    assert "schedules" not in payload
    assert "goals" not in payload["routes"]
    assert "schedules" not in payload["routes"]
    assert payload["draft"]["goals"]
    assert payload["schedule_summaries"]
    assert payload["backlog"]
    assert payload["assignments"]
    assert payload["cycle"] is not None


def test_public_bootstrap_seeds_backlog_from_canonical_schedule_specs(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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

    backlog_service = app.state.backlog_service
    original = backlog_service.seed_bootstrap_items_from_goal_specs
    observed_schedule_specs: list[dict[str, object]] = []

    def _capture_seed(*args, **kwargs):
        assert "schedule_specs" in kwargs
        assert "schedules" not in kwargs
        schedule_specs = kwargs["schedule_specs"]
        assert isinstance(schedule_specs, list)
        assert schedule_specs
        assert all(isinstance(item, dict) for item in schedule_specs)
        assert all(item.get("schedule_id") for item in schedule_specs)
        observed_schedule_specs.extend(schedule_specs)
        return original(*args, **kwargs)

    with patch.object(
        backlog_service,
        "seed_bootstrap_items_from_goal_specs",
        side_effect=_capture_seed,
    ):
        response = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": preview_payload["profile"],
                "draft": preview_payload["draft"],
                "auto_activate": True,
                "auto_dispatch": False,
                "execute": False,
            },
        )

    assert response.status_code == 200
    assert observed_schedule_specs


def test_kickoff_execution_from_chat_dispatches_bootstrap_assignments_without_goal_dispatch(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
            "auto_activate": False,
            "auto_dispatch": False,
            "execute": False,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    kickoff = asyncio.run(
        app.state.industry_service.kickoff_execution_from_chat(
            industry_instance_id=instance_id,
            message_text="Start the first execution cycle for today.",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry:{instance_id}",
            channel="console",
        ),
    )

    assert kickoff is not None
    assert kickoff["started_assignment_ids"]
    assert kickoff["started_task_ids"]
    assert kickoff["assignment_dispatches"]
    assert "goal_dispatches" not in kickoff
    assert "started_goal_ids" not in kickoff
    assert "started_goal_titles" not in kickoff
    assert "resumed_schedule_ids" not in kickoff
    assert "resumed_schedule_titles" not in kickoff

    started_assignment_ids = set(kickoff["started_assignment_ids"])
    created_tasks = [
        task
        for task in app.state.task_repository.list_tasks()
        if task.assignment_id in started_assignment_ids
    ]
    assert created_tasks
    assert set(kickoff["started_task_ids"]) <= {task.id for task in created_tasks}
    task_by_id = {task.id: task for task in created_tasks}
    dispatch_by_assignment_id = {
        item["assignment_id"]: item
        for item in kickoff["assignment_dispatches"]
        if item.get("assignment_id") in started_assignment_ids and item.get("task_id")
    }
    assignment_id = kickoff["started_assignment_ids"][0]
    assignment = app.state.assignment_repository.get_assignment(assignment_id)
    assert assignment is not None
    assert assignment_id in dispatch_by_assignment_id
    dispatched_task_id = dispatch_by_assignment_id[assignment_id]["task_id"]
    assert dispatched_task_id in task_by_id
    assert assignment.task_id in task_by_id
    current_task = task_by_id[assignment.task_id]
    expected_assignment_status = {
        "created": "queued",
        "queued": "queued",
        "running": "running",
        "completed": "waiting-report",
        "failed": "failed",
        "cancelled": "failed",
    }.get(current_task.status, assignment.status)
    assert assignment.status == expected_assignment_status
    assert all(task.assignment_id in started_assignment_ids for task in created_tasks)


def test_kickoff_execution_from_chat_recovers_ownerless_assignments_from_lane_binding(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
            "auto_activate": False,
            "auto_dispatch": False,
            "execute": False,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    original_assignments = app.state.assignment_repository.list_assignments(
        industry_instance_id=instance_id,
        limit=None,
    )
    assert original_assignments
    for assignment in original_assignments:
        metadata = dict(assignment.metadata or {})
        metadata.pop("owner_agent_id", None)
        metadata.pop("industry_role_id", None)
        app.state.assignment_repository.upsert_assignment(
            assignment.model_copy(
                update={
                    "owner_agent_id": None,
                    "owner_role_id": None,
                    "metadata": metadata,
                },
            ),
        )

    kickoff = asyncio.run(
        app.state.industry_service.kickoff_execution_from_chat(
            industry_instance_id=instance_id,
            message_text="Start the first execution cycle for today.",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry:{instance_id}",
            channel="console",
        ),
    )

    assert kickoff is not None
    assert kickoff["started_assignment_ids"]

    recovered = [
        app.state.assignment_repository.get_assignment(assignment_id)
        for assignment_id in kickoff["started_assignment_ids"]
    ]
    assert all(item is not None for item in recovered)
    assert all(item.owner_agent_id for item in recovered if item is not None)
    assert all(item.owner_role_id for item in recovered if item is not None)


def test_kickoff_execution_from_chat_repairs_stale_completed_assignment_closure(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
            "auto_activate": False,
            "auto_dispatch": False,
            "execute": False,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"

    assignment = app.state.assignment_repository.list_assignments(
        industry_instance_id=instance_id,
        limit=1,
    )[0]
    repaired_assignment = app.state.assignment_repository.upsert_assignment(
        assignment.model_copy(
            update={
                "status": "queued",
                "task_id": "task-kickoff-stale",
                "last_report_id": None,
                "metadata": {
                    **dict(assignment.metadata or {}),
                    "control_thread_id": control_thread_id,
                    "session_id": control_thread_id,
                },
            },
        ),
    )

    app.state.task_repository.upsert_task(
        TaskRecord(
            id="task-kickoff-stale",
            title=repaired_assignment.title,
            summary=repaired_assignment.summary,
            task_type="system:dispatch_query",
            status="completed",
            owner_agent_id=repaired_assignment.owner_agent_id,
            work_context_id="work-context-kickoff-stale",
            current_risk_level="guarded",
            industry_instance_id=instance_id,
            assignment_id=repaired_assignment.id,
            lane_id=repaired_assignment.lane_id,
            cycle_id=repaired_assignment.cycle_id,
            report_back_mode="summary",
        ),
    )
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-kickoff-stale",
            runtime_status="terminated",
            current_phase="completed",
            risk_level="guarded",
            last_result_summary="Recovered stale kickoff closure.",
            last_owner_agent_id=repaired_assignment.owner_agent_id,
        ),
    )

    kickoff = asyncio.run(
        app.state.industry_service.kickoff_execution_from_chat(
            industry_instance_id=instance_id,
            message_text="Resume the first execution cycle for today.",
            owner_agent_id="copaw-agent-runner",
            session_id=control_thread_id,
            channel="console",
        ),
    )

    assert kickoff is not None
    reports = app.state.agent_report_repository.list_reports(
        industry_instance_id=instance_id,
        assignment_id=repaired_assignment.id,
        limit=None,
    )
    assert reports
    assert any(report.task_id == "task-kickoff-stale" for report in reports)
    refreshed_assignment = app.state.assignment_repository.get_assignment(
        repaired_assignment.id,
    )
    assert refreshed_assignment is not None
    assert refreshed_assignment.status == "completed"
    assert refreshed_assignment.last_report_id is not None


def test_kickoff_execution_from_chat_does_not_block_on_learning_acquisition_cycle_by_default(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
            "auto_activate": False,
            "auto_dispatch": False,
            "execute": False,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    captured_calls: list[dict[str, object]] = []

    async def _record_acquisition_cycle(**kwargs):
        captured_calls.append(dict(kwargs))
        return {
            "success": True,
            "industry_instance_id": instance_id,
            "summary": "background acquisition queued",
            "proposals": [],
            "plans": [],
            "onboarding_runs": [],
            "warnings": [],
        }

    with patch.object(
        app.state.learning_service,
        "run_industry_acquisition_cycle",
        side_effect=_record_acquisition_cycle,
    ):
        kickoff = asyncio.run(
            app.state.industry_service.kickoff_execution_from_chat(
                industry_instance_id=instance_id,
                message_text="Start the first execution cycle for today.",
                owner_agent_id="copaw-agent-runner",
                session_id=f"industry:{instance_id}",
                channel="console",
            ),
        )
        assert _wait_until(lambda: len(captured_calls) == 1)

    assert kickoff is not None
    assert kickoff["kickoff_stage"] == "learning"
    assert kickoff["started_assignment_ids"]
    assert kickoff["acquisition_cycle"] is None
    assert captured_calls == [
        {
            "industry_instance_id": instance_id,
            "actor": "copaw-agent-runner",
            "rerun_existing": False,
            "providers": ["install-template"],
        },
    ]


def test_kickoff_execution_from_chat_publishes_background_acquisition_failure_event(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
            "auto_activate": False,
            "auto_dispatch": False,
            "execute": False,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    captured_events: list[dict[str, object]] = []

    async def _failed_acquisition_cycle(**kwargs):
        _ = kwargs
        return {
            "success": False,
            "industry_instance_id": instance_id,
            "summary": "background acquisition failed",
            "proposals": [],
            "plans": [],
            "onboarding_runs": [],
            "warnings": ["discovery-unavailable"],
        }

    def _capture_event(*, topic: str, action: str, payload: dict[str, object]) -> None:
        captured_events.append(
            {
                "topic": topic,
                "action": action,
                "payload": dict(payload),
            },
        )

    with patch.object(
        app.state.learning_service,
        "run_industry_acquisition_cycle",
        side_effect=_failed_acquisition_cycle,
    ), patch.object(
        app.state.learning_service,
        "_publish_runtime_event",
        side_effect=_capture_event,
    ):
        kickoff = asyncio.run(
            app.state.industry_service.kickoff_execution_from_chat(
                industry_instance_id=instance_id,
                message_text="Start the first execution cycle for today.",
                owner_agent_id="copaw-agent-runner",
                session_id=f"industry:{instance_id}",
                channel="console",
            ),
        )
        assert _wait_until(
            lambda: any(
                event["action"] == "background-cycle-failed"
                and event["payload"]["industry_instance_id"] == instance_id
                for event in captured_events
            ),
        )

    assert kickoff is not None
    assert kickoff["kickoff_stage"] == "learning"
    assert any(
        event["action"] == "background-cycle-queued"
        and event["payload"]["industry_instance_id"] == instance_id
        for event in captured_events
    )
    assert any(
        event["action"] == "background-cycle-failed"
        and event["payload"]["industry_instance_id"] == instance_id
        and event["payload"]["warnings"] == ["discovery-unavailable"]
        for event in captured_events
    )


def test_chat_writeback_schedule_creation_does_not_expand_instance_schedule_truth(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    baseline = app.state.industry_instance_repository.get_instance(instance_id)
    assert baseline is not None
    baseline_schedule_ids = app.state.industry_service._list_schedule_ids_for_instance(
        instance_id,
    )

    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text="Create a weekly researcher follow-up cadence for this team.",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                "Create a weekly researcher follow-up cadence for this team.",
                approved_classifications=["schedule"],
                schedule_title="Researcher Weekly Follow-Up",
                schedule_summary="Run the weekly researcher follow-up cadence.",
                schedule_cron="0 9 * * 1",
                schedule_prompt="Review the latest signals and publish the next operator-ready follow-up.",
            ),
        ),
    )

    assert result is not None
    assert result["created_schedule_ids"]
    updated = app.state.industry_instance_repository.get_instance(instance_id)
    assert updated is not None
    assert set(app.state.industry_service._list_schedule_ids_for_instance(instance_id)) == (
        set(baseline_schedule_ids).union(result["created_schedule_ids"])
    )



def _build_team_capability_facade(app: FastAPI) -> SystemTeamCapabilityFacade:
    return SystemTeamCapabilityFacade(
        get_capability_fn=lambda capability_id: None,
        resolve_agent_profile_fn=lambda agent_id: None,
        industry_service=app.state.industry_service,
    )


def _build_support_role(
    execution_core_agent_id: str,
    *,
    employment_mode: str = "career",
) -> IndustryRoleBlueprint:
    return IndustryRoleBlueprint(
        role_id="support-analyst",
        agent_id="industry-support-analyst-northwind-robotics",
        name="Northwind Support Analyst",
        role_name="Support Analyst",
        role_summary="Handles scoped support research and packaging.",
        mission="Finish support work packages and report back to the main brain.",
        goal_kind="support-analyst",
        agent_class="business",
        employment_mode=employment_mode,
        activation_mode="persistent",
        suspendable=False,
        reports_to=execution_core_agent_id,
        risk_level="guarded",
        environment_constraints=["workspace draft/edit allowed"],
        allowed_capabilities=["system:dispatch_query"],
        evidence_expectations=["support completion note"],
    )


class _FakePlanningActivationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def activate_for_query(self, **kwargs: object) -> ActivationResult:
        self.calls.append(dict(kwargs))
        return ActivationResult(
            query=str(kwargs.get("query") or ""),
            scope_type="industry",
            scope_id=str(kwargs.get("industry_instance_id") or "industry-1"),
            top_entities=["weekend-variance", "inventory"],
            top_opinions=["staffing:caution:premature-change"],
            top_relations=["weekend variance contradicts staffing expansion readiness"],
            top_relation_kinds=["contradicts"],
            top_relation_evidence=[
                {
                    "relation_id": "relation-weekend-variance",
                    "relation_kind": "contradicts",
                    "summary": "Weekend variance evidence contradicts immediate staffing expansion.",
                    "source_refs": ["memory:weekend-variance-gap"],
                    "source_node_id": "entity:weekend-variance",
                    "target_node_id": "opinion:staffing-expansion-readiness",
                },
            ],
            top_constraints=["Do not expand staffing before the variance is explained."],
            top_next_actions=["Review the weekend variance evidence before launching the next move."],
        )


class _EmptyPlanningActivationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def activate_for_query(self, **kwargs: object) -> ActivationResult:
        self.calls.append(dict(kwargs))
        return ActivationResult(
            query=str(kwargs.get("query") or ""),
            scope_type="industry",
            scope_id=str(kwargs.get("industry_instance_id") or "industry-1"),
        )


class _FakePlanningSubgraphActivationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def activate_for_query(self, **kwargs: object) -> TaskSubgraph:
        self.calls.append(dict(kwargs))
        scope = KnowledgeGraphScope(
            scope_type="industry",
            scope_id=str(kwargs.get("industry_instance_id") or "industry-1"),
            owner_agent_id="copaw-agent-runner",
            industry_instance_id=str(kwargs.get("industry_instance_id") or "industry-1"),
        )
        return TaskSubgraph(
            scope=scope,
            query_text=str(kwargs.get("query") or ""),
            seed_refs=["memory:weekend-variance-gap"],
            top_constraint_refs=["Do not publish until the approval contradiction is resolved."],
            top_evidence_refs=["memory:weekend-variance-gap"],
            dependency_paths=[
                KnowledgeGraphPath(
                    path_type="dependency",
                    score=0.94,
                    summary="Refresh approval evidence before drafting the partner update.",
                    relation_ids=["relation-dependency-1"],
                    relation_kinds=["depends_on"],
                    source_refs=["memory:approval-refresh"],
                    evidence_refs=["memory:approval-refresh"],
                ),
            ],
            blocker_paths=[
                KnowledgeGraphPath(
                    path_type="blocker",
                    score=0.88,
                    summary="Do not publish until the approval contradiction is resolved.",
                    relation_ids=["relation-blocker-1"],
                    relation_kinds=["blocks"],
                    source_refs=["memory:weekend-variance-gap"],
                    evidence_refs=["memory:weekend-variance-gap"],
                ),
            ],
            recovery_paths=[
                KnowledgeGraphPath(
                    path_type="recovery",
                    score=0.79,
                    summary="If blocked, rerun the governed approval refresh and verify the cache state.",
                    relation_ids=["relation-recovery-1"],
                    relation_kinds=["recovers_with"],
                    source_refs=["memory:approval-recovery"],
                    evidence_refs=["memory:approval-recovery"],
                ),
            ],
            nodes=[
                KnowledgeGraphNode(
                    node_id="capability:browser:partner-portal",
                    node_type="capability",
                    scope=scope,
                    title="Partner portal browser capability",
                    summary="Needed to inspect and update the governed partner portal.",
                    source_refs=["capability:browser:partner-portal"],
                ),
                KnowledgeGraphNode(
                    node_id="environment:browser-session",
                    node_type="environment",
                    scope=scope,
                    title="Partner portal browser session",
                    summary="Governed browser session for partner portal work.",
                    source_refs=["environment:browser:partner-portal"],
                ),
                KnowledgeGraphNode(
                    node_id="failure:stale-approval-cache",
                    node_type="failure_pattern",
                    scope=scope,
                    title="Stale approval cache",
                    summary="Stale approval cache can block a correct publish.",
                    source_refs=["failure-pattern:stale-approval-cache"],
                ),
            ],
            relations=[
                KnowledgeGraphRelation(
                    relation_id="relation-weekend-variance",
                    relation_type="contradicts",
                    source_id="entity:weekend-variance",
                    target_id="opinion:publish-readiness",
                    scope=scope,
                    source_refs=["memory:weekend-variance-gap"],
                    evidence_refs=["memory:weekend-variance-gap"],
                    metadata={
                        "summary": "Weekend variance contradicts publish readiness until approval evidence is refreshed.",
                    },
                )
            ],
            metadata={
                "top_entities": ["weekend-variance", "inventory"],
                "top_opinions": ["approval:caution:contradiction"],
                "top_relations": ["weekend variance contradicts publish readiness"],
                "top_relation_kinds": ["contradicts"],
            },
        )


def test_run_operating_cycle_dispatches_materialized_execution_assignment(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.lanes
    app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=str(detail.lanes[0]["lane_id"]),
        title="Prepare the support execution brief",
        summary="Review the outstanding support items and queue the next execution packet.",
        priority=5,
        source_ref="test:assignment-runtime-sync",
        metadata={
            "owner_agent_id": support_role.agent_id,
            "industry_role_id": support_role.role_id,
            "industry_role_name": support_role.role_name,
            "role_name": support_role.role_name,
            "role_summary": support_role.role_summary,
            "mission": support_role.mission,
            "goal_kind": support_role.goal_kind,
            "task_mode": "autonomy-cycle",
            "report_back_mode": "summary",
            "plan_steps": ["Review the support backlog and package the next action plan."],
        },
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:assignment-runtime-sync",
            force=True,
            auto_dispatch_materialized_goals=True,
        ),
    )
    assert cycle_result["count"] == 1
    processed_instance = cycle_result["processed_instances"][0]
    assert processed_instance["created_assignment_ids"]
    assert "created_goal_ids" not in processed_instance
    assert "materialized_goal_ids" not in processed_instance
    assert "auto_dispatched_goal_ids" not in processed_instance
    assert "goal_dispatches" not in processed_instance
    assert processed_instance["created_task_ids"]

    created_tasks = [
        task
        for task in app.state.task_repository.list_tasks()
        if task.assignment_id in processed_instance["created_assignment_ids"]
    ]
    assert created_tasks
    target_task = next(
        task
        for task in created_tasks
        if task.title == "Prepare the support execution brief"
    )
    assert target_task.goal_id is None

    assignment_id = next(
        assignment_id
        for assignment_id in processed_instance["created_assignment_ids"]
        if any(
            getattr(assignment, "task_id", None) == target_task.id
            for assignment in [app.state.assignment_repository.get_assignment(assignment_id)]
            if assignment is not None
        )
    )
    assignment = app.state.assignment_repository.get_assignment(assignment_id)
    assert assignment is not None
    assert assignment.goal_id is None
    assert assignment.task_id == target_task.id
    runtime = app.state.agent_runtime_repository.get_runtime(support_role.agent_id)
    assert runtime is not None
    assert runtime.runtime_status in {"idle", "assigned", "queued", "claimed", "executing"}
    if (
        runtime.current_task_id is None
        and runtime.current_mailbox_id is None
        and int(runtime.queue_depth or 0) == 0
        and "current_assignment_id" not in runtime.metadata
    ):
        assert runtime.runtime_status == "idle"
        assert "current_assignment_status" not in runtime.metadata
        assert runtime.metadata.get("current_focus_id") != assignment_id
    else:
        assert runtime.metadata["current_assignment_id"] == assignment_id
        assert runtime.metadata["current_assignment_status"] in {
            "planned",
            "queued",
            "running",
            "waiting-report",
        }
        assert runtime.metadata["current_assignment_title"] == "Prepare the support execution brief"
        assert runtime.metadata["current_focus_kind"] == "assignment"
        assert runtime.metadata["current_focus_id"] == assignment_id
        assert runtime.metadata["current_focus"] == "Prepare the support execution brief"
    assert "goal_id" not in runtime.metadata
    assert "goal_title" not in runtime.metadata

    override = app.state.agent_profile_override_repository.get_override(
        support_role.agent_id,
    )
    assert override is not None
    profile = app.state.agent_profile_service.get_agent(support_role.agent_id)
    assert profile is not None
    if "current_assignment_id" not in runtime.metadata:
        assert profile.current_focus_id != assignment_id
    else:
        assert profile.status in {"waiting", "blocked", "running", "idle", "needs-confirm", "degraded", "executing"}
        assert profile.current_focus_kind == "assignment"
        assert profile.current_focus_id == assignment_id
        assert profile.current_focus == "Prepare the support execution brief"


def test_run_operating_cycle_persists_graph_focus_into_formal_planning_sidecar(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)
    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    activation_service = _FakePlanningActivationService()
    app.state.industry_service._memory_activation_service = activation_service

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.lanes
    app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=str(detail.lanes[0]["lane_id"]),
        title="Investigate weekend inventory variance",
        summary="Review the variance evidence before changing support staffing.",
        priority=5,
        source_ref="test:formal-planning-graph-focus",
        metadata={
            "owner_agent_id": support_role.agent_id,
            "industry_role_id": support_role.role_id,
            "industry_role_name": support_role.role_name,
            "role_name": support_role.role_name,
            "role_summary": support_role.role_summary,
            "mission": support_role.mission,
            "goal_kind": support_role.goal_kind,
            "task_mode": "autonomy-cycle",
            "report_back_mode": "summary",
            "plan_steps": ["Review the variance evidence before changing support staffing."],
        },
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:formal-planning-graph-focus",
            force=True,
        ),
    )
    assert cycle_result["count"] == 1
    processed_instance = cycle_result["processed_instances"][0]
    started_cycle_id = processed_instance["started_cycle_id"]
    assert started_cycle_id is not None
    assert activation_service.calls
    assert activation_service.calls[0]["industry_instance_id"] == instance_id
    assert activation_service.calls[0]["current_phase"] == "operating-cycle-planning"

    cycle = app.state.operating_cycle_repository.get_cycle(started_cycle_id)
    assert cycle is not None
    formal_planning = dict((cycle.metadata or {}).get("formal_planning") or {})
    strategy_constraints = dict(formal_planning.get("strategy_constraints") or {})
    cycle_decision = dict(formal_planning.get("cycle_decision") or {})

    assert strategy_constraints["graph_focus_entities"] == [
        "weekend-variance",
        "inventory",
    ]
    assert strategy_constraints["graph_focus_opinions"] == [
        "staffing:caution:premature-change",
    ]
    assert strategy_constraints["graph_focus_relations"] == [
        "weekend variance contradicts staffing expansion readiness",
    ]
    assert strategy_constraints["graph_relation_evidence"] == [
        {
            "confidence": 0.0,
            "relation_id": "relation-weekend-variance",
            "relation_kind": "contradicts",
            "source_node_id": "entity:weekend-variance",
            "source_refs": ["memory:weekend-variance-gap"],
            "summary": "Weekend variance evidence contradicts immediate staffing expansion.",
            "target_node_id": "opinion:staffing-expansion-readiness",
        },
    ]
    assert cycle_decision["metadata"]["graph_focus_entities"] == [
        "weekend-variance",
        "inventory",
    ]
    assert cycle_decision["metadata"]["graph_focus_opinions"] == [
        "staffing:caution:premature-change",
    ]
    assert cycle_decision["affected_relation_ids"] == ["relation-weekend-variance"]
    assert cycle_decision["affected_relation_kinds"] == ["contradicts"]


def test_run_operating_cycle_passes_task_subgraph_into_cycle_and_assignment_planners(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)
    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    activation_service = _EmptyPlanningActivationService()
    subgraph_service = _FakePlanningSubgraphActivationService()
    app.state.industry_service._memory_activation_service = activation_service
    app.state.industry_service._subgraph_activation_service = subgraph_service
    app.state.state_query_service._memory_activation_service = activation_service
    app.state.state_query_service.set_knowledge_graph_service(
        KnowledgeGraphService(
            memory_activation_service=activation_service,
            subgraph_activation_service=subgraph_service,
        ),
    )

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.lanes
    app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=str(detail.lanes[0]["lane_id"]),
        title="Review weekend variance approval contradiction",
        summary="Resolve the approval contradiction before any partner portal publish move.",
        priority=5,
        source_ref="test:formal-planning-task-subgraph",
        metadata={
            "owner_agent_id": support_role.agent_id,
            "industry_role_id": support_role.role_id,
            "industry_role_name": support_role.role_name,
            "role_name": support_role.role_name,
            "role_summary": support_role.role_summary,
            "mission": support_role.mission,
            "goal_kind": support_role.goal_kind,
            "task_mode": "autonomy-cycle",
            "report_back_mode": "summary",
            "plan_steps": [
                "Review the latest approval evidence.",
                "Publish the governed partner update.",
            ],
        },
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:formal-planning-task-subgraph",
            force=True,
        ),
    )
    assert cycle_result["count"] == 1
    processed_instance = cycle_result["processed_instances"][0]
    started_cycle_id = processed_instance["started_cycle_id"]
    created_assignment_ids = list(processed_instance["created_assignment_ids"] or [])

    assert started_cycle_id is not None
    assert created_assignment_ids
    assert activation_service.calls
    assert subgraph_service.calls
    assert activation_service.calls[0]["industry_instance_id"] == instance_id
    assert subgraph_service.calls[0]["industry_instance_id"] == instance_id

    cycle = app.state.operating_cycle_repository.get_cycle(started_cycle_id)
    assert cycle is not None
    formal_planning = dict((cycle.metadata or {}).get("formal_planning") or {})
    strategy_constraints = dict(formal_planning.get("strategy_constraints") or {})
    cycle_decision = dict(formal_planning.get("cycle_decision") or {})

    assert strategy_constraints["graph_focus_entities"] == []
    assert strategy_constraints["graph_focus_relations"] == []
    assert cycle_decision["affected_relation_ids"] == [
        "relation-weekend-variance",
        "relation-dependency-1",
        "relation-blocker-1",
        "relation-recovery-1",
    ]
    assert cycle_decision["affected_relation_kinds"] == [
        "contradicts",
        "depends_on",
        "blocks",
        "recovers_with",
    ]

    assignment = app.state.assignment_repository.get_assignment(created_assignment_ids[0])
    assert assignment is not None
    assignment_plan = dict(
        ((assignment.metadata or {}).get("formal_planning") or {}).get("assignment_plan") or {}
    )
    knowledge_subgraph = dict((assignment_plan.get("sidecar_plan") or {}).get("knowledge_subgraph") or {})

    assert knowledge_subgraph["capability_refs"] == ["capability:browser:partner-portal"]
    assert knowledge_subgraph["environment_refs"] == ["environment:browser:partner-portal"]
    assert knowledge_subgraph["failure_patterns"] == ["Stale approval cache"]
    assert knowledge_subgraph["relation_ids"] == ["relation-weekend-variance"]
    assert knowledge_subgraph["top_relation_kinds"] == ["contradicts"]
    assert knowledge_subgraph["dependency_paths"][0]["summary"] == (
        "Refresh approval evidence before drafting the partner update."
    )
    assert knowledge_subgraph["blocker_paths"][0]["summary"] == (
        "Do not publish until the approval contradiction is resolved."
    )
    assert knowledge_subgraph["recovery_paths"][0]["summary"] == (
        "If blocked, rerun the governed approval refresh and verify the cache state."
    )


def test_bootstrap_initial_assignments_persist_formal_planning_sidecar(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    app.state.industry_service._memory_activation_service = _EmptyPlanningActivationService()
    subgraph_service = _FakePlanningSubgraphActivationService()
    app.state.industry_service._subgraph_activation_service = subgraph_service
    client = TestClient(app)

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
    instance_id = bootstrap.json()["team"]["team_id"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.current_cycle is not None
    cycle = app.state.operating_cycle_repository.get_cycle(detail.current_cycle["cycle_id"])
    assert cycle is not None

    cycle_formal_planning = dict((cycle.metadata or {}).get("formal_planning") or {})
    assert cycle_formal_planning["cycle_decision"]["reason"] == "bootstrap-seeded-cycle"

    assignments = app.state.assignment_repository.list_assignments(
        industry_instance_id=instance_id,
        cycle_id=cycle.id,
        limit=None,
    )
    assert assignments

    assignment = assignments[0]
    assignment_formal_planning = dict((assignment.metadata or {}).get("formal_planning") or {})
    assignment_plan = dict(assignment_formal_planning.get("assignment_plan") or {})

    assert assignment_plan["assignment_id"] == assignment.id
    assert subgraph_service.calls
    assert (
        assignment_plan["sidecar_plan"]["knowledge_subgraph"]["dependency_paths"][0]["summary"]
        == "Refresh approval evidence before drafting the partner update."
    )


def test_run_operating_cycle_skips_unresolved_chat_writeback_gap_backlog(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.lanes

    gap_backlog = app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=str(detail.lanes[0]["lane_id"]),
        title="整理桌面 text 文件",
        summary="把电脑桌面的 text 文件整理到一个文件夹",
        priority=5,
        source_ref="chat-writeback:legacy-gap-reopened",
        metadata={
            "source": "chat-writeback",
            "owner_agent_id": "copaw-agent-runner",
            "industry_role_id": "execution-core",
            "industry_role_name": "Spider Mesh 执行中枢",
            "role_name": "Spider Mesh 执行中枢",
            "goal_kind": "execution-core",
            "task_mode": "chat-writeback-followup",
            "report_back_mode": "summary",
            "chat_writeback_instruction": "请把电脑桌面的text文件整理到一个文件夹",
            "chat_writeback_classes": [
                "strategy",
                "backlog",
                "lane",
                "routing-pending",
                "capability-gap",
            ],
            "chat_writeback_requested_surfaces": ["file", "desktop"],
            "chat_writeback_gap_kind": "capability-gap",
            "chat_writeback_target_match_signals": [
                "recovered legacy execution-core routing gap for requested execution surface: file,desktop",
            ],
        },
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:skip-chat-writeback-gap",
            force=False,
            backlog_item_ids=[gap_backlog.id],
            auto_dispatch_materialized_goals=True,
        ),
    )

    assert cycle_result["count"] == 1
    processed_instance = cycle_result["processed_instances"][0]
    assert processed_instance["started_cycle_id"] is None
    assert "created_goal_ids" not in processed_instance
    assert "materialized_goal_ids" not in processed_instance
    assert processed_instance["created_assignment_ids"] == []

    refreshed_backlog = app.state.backlog_item_repository.get_item(gap_backlog.id)
    assert refreshed_backlog is not None
    assert refreshed_backlog.status == "open"
    assert refreshed_backlog.goal_id is None
    assert refreshed_backlog.assignment_id is None


def test_update_industry_team_reuses_existing_career_role_without_duplication(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    first = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert first["success"] is True
    assert first["employment_mode"] == "career"

    second = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert second["success"] is True
    assert second["no_op"] is True
    assert second["employment_mode"] == "career"

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    matching_roles = [agent for agent in detail.team.agents if agent.role_id == support_role.role_id]
    assert len(matching_roles) == 1
    assert matching_roles[0].employment_mode == "career"


def test_career_role_can_be_force_retired_from_instance_team(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    retired = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "retire-role",
                "role_id": support_role.role_id,
                "force": True,
            },
        ),
    )
    assert retired["success"] is True
    assert retired["employment_mode"] == "career"

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert all(agent.role_id != support_role.role_id for agent in detail.team.agents)


def test_processed_report_keeps_completed_career_role_in_team(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)
    asyncio.run(take_all())

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Support cleanup",
        summary="Finish the support package and report back.",
        status="completed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)
    report = AgentReportRecord(
        industry_instance_id=instance_id,
        assignment_id=assignment.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Support cleanup completed",
        summary="All support work is done.",
        status="recorded",
        result="completed",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=None,
    )
    assert len(processed) == 1
    assert processed[0].processed is True
    session_snapshot = app.state.session_backend.load_session_snapshot(
        session_id=f"industry-chat:{instance_id}:execution-core",
        user_id="copaw-agent-runner",
    )
    assert session_snapshot is not None
    message_buffer = session_snapshot["agent"]["memory"]
    if isinstance(message_buffer, dict):
        message_buffer = message_buffer.get("content") or []
    report_message = next(
        message
        for message in message_buffer
        if message["id"] == f"agent-report:{report.id}"
    )
    assert report_message["metadata"]["message_kind"] == "agent-report-writeback"
    text = report_message["content"][0]["text"]
    assert "我刚完成一项任务：Support cleanup completed" in text
    assert "结论：All support work is done." in text
    push_messages = asyncio.run(take_all())
    assert any(
        "Support cleanup completed" in item["text"]
        for item in push_messages
    )

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert any(agent.role_id == support_role.role_id for agent in detail.team.agents)


def test_agent_report_writeback_honors_control_thread_override_in_report_metadata(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)
    asyncio.run(take_all())

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Support follow-up writeback",
        summary="Write back to the preserved control thread, not the canonical one.",
        status="completed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)

    control_thread_id = f"industry-chat:{instance_id}:support-followup"
    report = AgentReportRecord(
        industry_instance_id=instance_id,
        assignment_id=assignment.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Support follow-up completed",
        summary="Writeback should land in the support-followup control thread.",
        status="recorded",
        result="completed",
        processed=False,
        metadata={
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": f"session:console:industry:{instance_id}",
        },
    )
    app.state.agent_report_repository.upsert_report(report)
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=None,
    )
    assert len(processed) == 1
    assert processed[0].processed is True

    session_snapshot = app.state.session_backend.load_session_snapshot(
        session_id=control_thread_id,
        user_id="copaw-agent-runner",
    )
    assert session_snapshot is not None
    message_buffer = session_snapshot["agent"]["memory"]
    if isinstance(message_buffer, dict):
        message_buffer = message_buffer.get("content") or []
    report_message = next(
        message
        for message in message_buffer
        if message["id"] == f"agent-report:{report.id}"
    )
    assert report_message["metadata"]["message_kind"] == "agent-report-writeback"


def test_agent_report_processing_preserves_cognitive_fields(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Support evidence follow-up",
        summary="Collect evidence and return a formal cognitive report.",
        status="completed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)
    report = AgentReportRecord(
        industry_instance_id=instance_id,
        assignment_id=assignment.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Support evidence follow-up completed",
        summary="The support review is complete but follow-up is required.",
        status="recorded",
        result="completed",
        findings=["Escalation queue stayed stable after the support patch."],
        uncertainties=["No validated explanation for the weekend variance."],
        recommendation="Run a weekend deep-dive before changing staffing.",
        needs_followup=True,
        followup_reason="Weekend variance remains unresolved.",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=None,
    )
    assert len(processed) == 1
    processed_report = processed[0]
    assert processed_report.processed is True
    assert processed_report.findings == [
        "Escalation queue stayed stable after the support patch.",
    ]
    assert processed_report.uncertainties == [
        "No validated explanation for the weekend variance.",
    ]
    assert (
        processed_report.recommendation
        == "Run a weekend deep-dive before changing staffing."
    )
    assert processed_report.needs_followup is True
    assert processed_report.followup_reason == "Weekend variance remains unresolved."

    stored_report = app.state.agent_report_repository.get_report(report.id)
    assert stored_report is not None
    assert stored_report.processed is True
    assert stored_report.findings == processed_report.findings
    assert stored_report.uncertainties == processed_report.uncertainties
    assert stored_report.recommendation == processed_report.recommendation
    assert stored_report.needs_followup is True
    assert stored_report.followup_reason == processed_report.followup_reason


def test_run_operating_cycle_surfaces_report_synthesis_and_followup_backlog(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=record.current_cycle_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Weekend variance review",
        summary="Review the variance and return a structured report.",
        status="completed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)
    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=record.current_cycle_id,
        assignment_id=assignment.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Weekend variance review completed",
        summary="Weekday response time stayed stable, but the weekend cause is unresolved.",
        status="recorded",
        result="completed",
        findings=["Weekday response time stayed inside target."],
        uncertainties=["Weekend variance still lacks a validated cause."],
        recommendation="Run a weekend deep-dive before changing staffing.",
        needs_followup=True,
        followup_reason="Weekend variance still lacks a validated cause.",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:report-synthesis",
            force=True,
        ),
    )

    assert cycle_result["count"] == 1
    assert report.id in cycle_result["processed_instances"][0]["processed_report_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.current_cycle is not None
    assert detail.current_cycle["synthesis"]["needs_replan"] is True
    matching_finding = next(
        item
        for item in detail.current_cycle["synthesis"]["latest_findings"]
        if item["report_id"] == report.id
    )
    assert matching_finding["needs_followup"] is True

    followup_backlog = next(
        item
        for item in detail.backlog
        if item["title"] == "Follow up: Weekend variance review completed"
    )
    assert followup_backlog["metadata"]["source_report_id"] == report.id
    assert followup_backlog["metadata"]["synthesis_kind"] == "followup-needed"


def test_report_synthesis_conflict_backlog_stays_handled_across_replay(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    cycle_id = record.current_cycle_id
    assert cycle_id is not None

    assignment_a = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Warehouse issue review A",
        summary="Review whether the warehouse issue is resolved.",
        status="completed",
    )
    assignment_b = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Warehouse issue review B",
        summary="Review whether the warehouse issue is still blocked.",
        status="failed",
    )
    app.state.assignment_repository.upsert_assignment(assignment_a)
    app.state.assignment_repository.upsert_assignment(assignment_b)

    report_a = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_a.id,
        goal_id="goal-shared",
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Warehouse issue resolved",
        summary="The warehouse issue is resolved.",
        status="recorded",
        result="completed",
        findings=["The warehouse issue is resolved."],
        processed=False,
    )
    report_b = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_b.id,
        goal_id="goal-shared",
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Warehouse issue still blocked",
        summary="The warehouse issue is still blocked by missing approvals.",
        status="recorded",
        result="failed",
        findings=["The warehouse issue is still blocked by missing approvals."],
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report_a)
    app.state.agent_report_repository.upsert_report(report_b)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=cycle_id,
    )
    assert {item.id for item in processed} == {report_a.id, report_b.id}

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.current_cycle is not None
    assert detail.current_cycle["synthesis"]["needs_replan"] is True
    assert len(detail.current_cycle["synthesis"]["conflicts"]) == 1
    conflict = detail.current_cycle["synthesis"]["conflicts"][0]
    conflict_backlog = next(
        item
        for item in detail.backlog
        if item["title"] == "Resolve report conflict"
        and item["metadata"].get("synthesis_kind") == "conflict"
    )
    assert conflict_backlog["metadata"]["source_report_ids"] == conflict["report_ids"]

    app.state.backlog_item_repository.upsert_item(
        app.state.backlog_item_repository.get_item(conflict_backlog["backlog_item_id"]).model_copy(
            update={
                "cycle_id": "cycle-linked",
                "goal_id": "goal-linked",
                "assignment_id": "assignment-linked",
                "status": "completed",
            },
        ),
    )

    replay_report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_a.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Warehouse replay trigger",
        summary="Replay the synthesis path without changing the handled conflict item.",
        status="recorded",
        result="completed",
        findings=["The main-brain replay path ran again."],
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(replay_report)

    replay_processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=cycle_id,
    )
    assert [item.id for item in replay_processed] == [replay_report.id]

    stored_conflict_backlog = app.state.backlog_item_repository.get_item(
        conflict_backlog["backlog_item_id"]
    )
    assert stored_conflict_backlog is not None
    assert stored_conflict_backlog.status == "completed"
    assert stored_conflict_backlog.cycle_id == "cycle-linked"
    assert stored_conflict_backlog.goal_id == "goal-linked"
    assert stored_conflict_backlog.assignment_id == "assignment-linked"


def test_report_synthesis_deduplicates_same_topic_followups_into_one_backlog_item(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    cycle_id = record.current_cycle_id
    assert cycle_id is not None

    assignment_a = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Warehouse variance review A",
        summary="Review whether the warehouse variance still lacks a validated cause.",
        status="completed",
    )
    assignment_b = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Warehouse variance review B",
        summary="Review the same warehouse variance claim from a second pass.",
        status="completed",
    )
    app.state.assignment_repository.upsert_assignment(assignment_a)
    app.state.assignment_repository.upsert_assignment(assignment_b)

    report_a = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_a.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Warehouse variance review A",
        summary="Warehouse variance still lacks a validated cause.",
        status="recorded",
        result="completed",
        findings=["Warehouse variance still lacks a validated cause."],
        needs_followup=True,
        followup_reason="Warehouse variance still lacks a validated cause.",
        metadata={"claim_key": "warehouse-variance"},
        processed=False,
    )
    report_b = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_b.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Warehouse variance review B",
        summary="Warehouse variance still lacks a validated cause.",
        status="recorded",
        result="completed",
        findings=["Warehouse variance still lacks a validated cause."],
        needs_followup=True,
        followup_reason="Warehouse variance still lacks a validated cause.",
        metadata={"claim_key": "warehouse-variance"},
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report_a)
    app.state.agent_report_repository.upsert_report(report_b)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=cycle_id,
    )
    assert {item.id for item in processed} == {report_a.id, report_b.id}

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.current_cycle is not None
    assert detail.current_cycle["synthesis"]["needs_replan"] is True
    assert len(detail.current_cycle["synthesis"]["holes"]) == 1
    assert len(detail.current_cycle["synthesis"]["recommended_actions"]) == 1

    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("synthesis_kind") == "followup-needed"
    )
    source_report_ids = followup_backlog["metadata"]["source_report_ids"]
    assert len(source_report_ids) == 2
    assert set(source_report_ids) == {report_a.id, report_b.id}


def test_failed_assignment_report_completes_original_backlog_after_followup_is_recorded(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    cycle_id = record.current_cycle_id
    assert cycle_id is not None

    backlog_item = app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=None,
        title="Support evidence collection",
        summary="Collect the missing evidence before the next staffing review.",
        priority=3,
        source_ref="chat-writeback:test-failed-followup",
        metadata={
            "owner_agent_id": support_role.agent_id,
            "industry_role_id": support_role.role_id,
            "source": "chat-writeback",
        },
    )
    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        backlog_item_id=backlog_item.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Support evidence collection",
        summary="Collect the missing evidence before the next staffing review.",
        status="failed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)
    app.state.backlog_item_repository.upsert_item(
        backlog_item.model_copy(
            update={
                "cycle_id": cycle_id,
                "assignment_id": assignment.id,
                "status": "materialized",
            },
        ),
    )
    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Support evidence collection failed",
        summary="The evidence package is still missing the external audit trail.",
        status="recorded",
        result="failed",
        findings=["The external audit trail is still missing."],
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=cycle_id,
    )
    assert [item.id for item in processed] == [report.id]

    stored_original_backlog = app.state.backlog_item_repository.get_item(backlog_item.id)
    assert stored_original_backlog is not None
    assert stored_original_backlog.status == "completed"

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )
    assert followup_backlog["status"] == "open"

    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    runtime_payload = runtime_detail.json()
    assert runtime_payload["execution"]["current_focus_id"] is None
    assert runtime_payload["main_chain"]["current_focus_id"] is None
    assert runtime_payload["execution"]["current_focus"] is None
    assert runtime_payload["main_chain"]["current_focus"] is None

    focused_backlog_detail = client.get(
        f"/runtime-center/industry/{instance_id}?backlog_item_id={quote(followup_backlog['backlog_item_id'])}"
    )
    assert focused_backlog_detail.status_code == 200
    focused_backlog_payload = focused_backlog_detail.json()
    assert focused_backlog_payload["focus_selection"]["selection_kind"] == "backlog"
    assert focused_backlog_payload["focus_selection"]["backlog_item_id"] == followup_backlog["backlog_item_id"]
    assert focused_backlog_payload["focus_selection"]["route"] == (
        f"/api/runtime-center/industry/{instance_id}?backlog_item_id={quote(followup_backlog['backlog_item_id'])}"
    )
    assert focused_backlog_payload["execution"]["current_focus_id"] is None
    assert focused_backlog_payload["main_chain"]["current_focus_id"] is None
    assert focused_backlog_payload["execution"]["current_focus"] is None
    assert focused_backlog_payload["main_chain"]["current_focus"] is None


def test_runtime_center_industry_detail_only_accepts_canonical_focus_queries(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.lanes
    assert detail.current_cycle is not None

    backlog_item = app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=str(detail.lanes[0]["lane_id"]),
        title="Prepare runtime-center follow-up packet",
        summary="Keep the follow-up work on the canonical backlog surface only.",
        priority=3,
        source_ref="test:runtime-center-canonical-focus",
        metadata={"source": "chat-writeback"},
    )

    supported_response = client.get(
        (
            f"/runtime-center/industry/{instance_id}"
            f"?focus_kind=backlog&focus_id={quote(backlog_item.id)}"
        )
    )
    assert supported_response.status_code == 200
    supported_payload = supported_response.json()
    assert supported_payload["focus_selection"]["selection_kind"] == "backlog"
    assert supported_payload["focus_selection"]["backlog_item_id"] == backlog_item.id
    assert supported_payload["focus_selection"]["route"] == (
        f"/api/runtime-center/industry/{instance_id}?backlog_item_id={quote(backlog_item.id)}"
    )
    missing_focus_response = client.get(
        (
            f"/runtime-center/industry/{instance_id}"
            "?focus_kind=backlog&focus_id=backlog-not-real"
        )
    )
    assert missing_focus_response.status_code == 200
    assert missing_focus_response.json()["focus_selection"] is None

    unsupported_routes = [
        f"/runtime-center/industry/{instance_id}?lane_id={quote(str(detail.lanes[0]['lane_id']))}",
        f"/runtime-center/industry/{instance_id}?cycle_id={quote(str(detail.current_cycle['cycle_id']))}",
        f"/runtime-center/industry/{instance_id}?focus_kind=agent_report&focus_id=report-unsupported",
        f"/runtime-center/industry/{instance_id}?focus_kind=invalid&focus_id=non-canonical",
        (
            f"/runtime-center/industry/{instance_id}"
            f"?focus_kind=lane&focus_id={quote(str(detail.lanes[0]['lane_id']))}"
        ),
        (
            f"/runtime-center/industry/{instance_id}"
            f"?focus_kind=cycle&focus_id={quote(str(detail.current_cycle['cycle_id']))}"
        ),
    ]
    for route in unsupported_routes:
        response = client.get(route)
        assert response.status_code == 400
        assert response.json() == {
            "detail": (
                "Unsupported runtime-center industry focus; "
                "only assignment/backlog/report focus is supported."
            )
        }

    missing_report_response = client.get(
        f"/runtime-center/industry/{instance_id}?report_id=report-unsupported"
    )
    assert missing_report_response.status_code == 404
    assert missing_report_response.json() == {
        "detail": (
            "Industry report 'report-unsupported' not found "
            f"in instance '{instance_id}'"
        )
    }

    focus_id_only = client.get(
        f"/runtime-center/industry/{instance_id}?focus_id={quote(backlog_item.id)}"
    )
    assert focus_id_only.status_code == 400
    assert focus_id_only.json() == {
        "detail": "focus_kind is required when focus_id is provided."
    }

    focus_kind_only = client.get(
        f"/runtime-center/industry/{instance_id}?focus_kind=backlog"
    )
    assert focus_kind_only.status_code == 400
    assert focus_kind_only.json() == {
        "detail": "focus_id is required when focus_kind is provided."
    }


def test_failed_report_followup_carries_control_thread_and_surface_pressure_without_backlog_assignment(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    cycle_id = record.current_cycle_id
    assert cycle_id is not None
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"
    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Browser follow-up handoff",
        summary="Recover the governed browser workflow after handoff returns.",
        status="failed",
        metadata={
            "chat_writeback_requested_surfaces": ["browser", "desktop", "document"],
            "seat_requested_surfaces": ["browser", "desktop", "document"],
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": environment_ref,
            "report_back_mode": "summary",
        },
    )
    app.state.assignment_repository.upsert_assignment(assignment)
    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Browser follow-up handoff failed",
        summary="Browser and desktop actions are still blocked until human return completes.",
        status="recorded",
        result="failed",
        findings=["Handoff checkpoint was not returned yet."],
        work_context_id="work-context:test-failed-followup",
        metadata={
            "chat_writeback_requested_surfaces": ["browser", "desktop", "document"],
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": environment_ref,
            "recommended_scheduler_action": "handoff",
        },
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=cycle_id,
    )
    assert [item.id for item in processed] == [report.id]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )
    assert "browser" in followup_backlog["metadata"]["seat_requested_surfaces"]
    assert "desktop" in followup_backlog["metadata"]["seat_requested_surfaces"]
    assert "document" in followup_backlog["metadata"]["seat_requested_surfaces"]
    assert followup_backlog["metadata"]["control_thread_id"] == control_thread_id
    assert followup_backlog["metadata"]["session_id"] == control_thread_id
    assert followup_backlog["metadata"]["environment_ref"] == environment_ref
    assert followup_backlog["metadata"]["work_context_id"] == report.work_context_id
    assert followup_backlog["metadata"]["recommended_scheduler_action"] == "handoff"

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    for agent in runtime_payload.get("agents") or []:
        assert "current_goal_id" not in agent
        assert "current_goal" not in agent
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert "browser" in replan_node["metrics"]["followup_pressure_surfaces"]
    assert "desktop" in replan_node["metrics"]["followup_pressure_surfaces"]
    assert "document" in replan_node["metrics"]["followup_pressure_surfaces"]


def test_activation_followup_backlog_carries_activation_metadata(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None

    app.state.industry_service._record_report_synthesis_backlog(
        record=record,
        synthesis={
            "activation": {
                "top_entities": ["weekend-variance", "staffing"],
                "top_opinions": ["staffing:caution:premature-change"],
                "top_relations": [
                    "weekend variance contradicts immediate staffing expansion",
                ],
                "top_relation_kinds": ["contradicts"],
                "top_relation_evidence": [
                    {
                        "relation_id": "relation-weekend-variance",
                        "relation_kind": "contradicts",
                        "summary": "Weekend variance evidence contradicts immediate staffing expansion.",
                        "source_refs": ["memory:weekend-audit-gap"],
                        "source_node_id": "entity:weekend-variance",
                        "target_node_id": "opinion:staffing-expansion-readiness",
                    },
                ],
                "top_constraints": [
                    "Weekend escalation root cause is still unvalidated.",
                ],
                "top_next_actions": [
                    "Pull the weekend audit trail before changing staffing.",
                ],
                "support_refs": [
                    "memory:weekend-audit-gap",
                    "report:weekend-variance-review",
                ],
            },
            "recommended_actions": [
                {
                    "action_id": "follow-up:activation-weekend-gap",
                    "action_type": "follow-up-backlog",
                    "title": "Activation follow-up: weekend variance",
                    "summary": "Carry activation-derived pressure into main-brain follow-up.",
                    "priority": 4,
                    "source_ref": "report-synthesis:activation-weekend-gap",
                    "metadata": {
                        "source_report_id": "report-activation-weekend-gap",
                        "source_report_ids": ["report-activation-weekend-gap"],
                        "owner_agent_id": execution_core_agent_id,
                        "industry_role_id": "execution-core",
                        "synthesis_kind": "followup-needed",
                    },
                },
            ],
        },
    )

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    activation_followup = next(
        item
        for item in detail.backlog
        if item["title"] == "Activation follow-up: weekend variance"
    )
    assert activation_followup["metadata"]["activation_top_constraints"] == [
        "Weekend escalation root cause is still unvalidated.",
    ]
    assert activation_followup["metadata"]["activation_top_entities"] == [
        "weekend-variance",
        "staffing",
    ]
    assert activation_followup["metadata"]["activation_top_opinions"] == [
        "staffing:caution:premature-change",
    ]
    assert activation_followup["metadata"]["activation_top_relations"] == [
        "weekend variance contradicts immediate staffing expansion",
    ]
    assert activation_followup["metadata"]["activation_top_relation_kinds"] == [
        "contradicts",
    ]
    assert activation_followup["metadata"]["activation_top_relation_ids"] == [
        "relation-weekend-variance",
    ]
    assert activation_followup["metadata"]["activation_relation_source_refs"] == [
        "memory:weekend-audit-gap",
    ]
    assert activation_followup["metadata"]["activation_top_next_actions"] == [
        "Pull the weekend audit trail before changing staffing.",
    ]
    assert activation_followup["metadata"]["activation_support_refs"] == [
        "memory:weekend-audit-gap",
        "report:weekend-variance-review",
    ]


def test_activation_followup_materialized_assignment_keeps_activation_metadata(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    app.state.industry_service._record_report_synthesis_backlog(
        record=record,
        synthesis={
            "activation": {
                "top_entities": ["weekend-variance", "staffing"],
                "top_opinions": ["staffing:caution:premature-change"],
                "top_relations": [
                    "weekend variance contradicts immediate staffing expansion",
                ],
                "top_relation_kinds": ["contradicts"],
                "top_relation_evidence": [
                    {
                        "relation_id": "relation-weekend-variance",
                        "relation_kind": "contradicts",
                        "summary": "Weekend variance evidence contradicts immediate staffing expansion.",
                        "source_refs": ["memory:weekend-audit-gap"],
                        "source_node_id": "entity:weekend-variance",
                        "target_node_id": "opinion:staffing-expansion-readiness",
                    },
                ],
                "top_constraints": [
                    "Weekend escalation root cause is still unvalidated.",
                ],
                "top_next_actions": [
                    "Pull the weekend audit trail before changing staffing.",
                ],
                "support_refs": [
                    "memory:weekend-audit-gap",
                ],
            },
            "recommended_actions": [
                {
                    "action_id": "follow-up:activation-weekend-gap",
                    "action_type": "follow-up-backlog",
                    "title": "Activation follow-up: weekend variance",
                    "summary": "Carry activation-derived pressure into main-brain follow-up.",
                    "priority": 4,
                    "source_ref": "report-synthesis:activation-weekend-gap",
                    "metadata": {
                        "source_report_id": "report-activation-weekend-gap",
                        "source_report_ids": ["report-activation-weekend-gap"],
                        "owner_agent_id": execution_core_agent_id,
                        "industry_role_id": "execution-core",
                        "synthesis_kind": "followup-needed",
                    },
                },
            ],
        },
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:activation-followup-materialization",
            force=True,
        ),
    )
    assert cycle_result["count"] == 1
    assignment_id = cycle_result["processed_instances"][0]["created_assignment_ids"][0]
    assignment = app.state.assignment_repository.get_assignment(assignment_id)
    assert assignment is not None
    assert assignment.metadata["activation_top_constraints"] == [
        "Weekend escalation root cause is still unvalidated.",
    ]
    assert assignment.metadata["activation_top_entities"] == [
        "weekend-variance",
        "staffing",
    ]
    assert assignment.metadata["activation_top_opinions"] == [
        "staffing:caution:premature-change",
    ]
    assert assignment.metadata["activation_top_relations"] == [
        "weekend variance contradicts immediate staffing expansion",
    ]
    assert assignment.metadata["activation_top_relation_kinds"] == [
        "contradicts",
    ]
    assert assignment.metadata["activation_top_relation_ids"] == [
        "relation-weekend-variance",
    ]
    assert assignment.metadata["activation_relation_source_refs"] == [
        "memory:weekend-audit-gap",
    ]
    assert assignment.metadata["activation_top_next_actions"] == [
        "Pull the weekend audit trail before changing staffing.",
    ]
    assert assignment.metadata["activation_support_refs"] == [
        "memory:weekend-audit-gap",
    ]


def test_run_operating_cycle_auto_dispatch_keeps_assignment_formal_planning_in_compiled_task(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(execution_core_agent_id)
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True

    activation_service = _EmptyPlanningActivationService()
    subgraph_service = _FakePlanningSubgraphActivationService()
    app.state.industry_service._memory_activation_service = activation_service
    app.state.industry_service._subgraph_activation_service = subgraph_service
    app.state.state_query_service._memory_activation_service = activation_service
    app.state.state_query_service.set_knowledge_graph_service(
        KnowledgeGraphService(
            memory_activation_service=activation_service,
            subgraph_activation_service=subgraph_service,
        ),
    )

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.lanes
    app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=str(detail.lanes[0]["lane_id"]),
        title="Carry the formal assignment plan into dispatch",
        summary="Dispatch the assignment with the same formal planning shell that was materialized.",
        priority=5,
        source_ref="test:auto-dispatch-assignment-formal-planning",
        metadata={
            "owner_agent_id": support_role.agent_id,
            "industry_role_id": support_role.role_id,
            "industry_role_name": support_role.role_name,
            "role_name": support_role.role_name,
            "role_summary": support_role.role_summary,
            "mission": support_role.mission,
            "goal_kind": support_role.goal_kind,
            "task_mode": "autonomy-cycle",
            "report_back_mode": "summary",
            "plan_steps": [
                "Clarify the governed move.",
                "Verify the result and evidence.",
            ],
        },
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:auto-dispatch-assignment-formal-planning",
            force=True,
            auto_dispatch_materialized_goals=True,
        ),
    )
    assert cycle_result["count"] == 1
    processed_instance = cycle_result["processed_instances"][0]
    assert processed_instance["created_assignment_ids"]
    assert processed_instance["created_task_ids"]

    assignment_id = processed_instance["created_assignment_ids"][0]
    assignment = app.state.assignment_repository.get_assignment(assignment_id)
    assert assignment is not None
    formal_planning = dict((assignment.metadata or {}).get("formal_planning") or {})
    assignment_plan = dict(formal_planning.get("assignment_plan") or {})
    assert assignment_plan["assignment_id"] == assignment.id

    task = app.state.task_repository.get_task(assignment.task_id or "")
    assert task is not None
    kernel_metadata = decode_kernel_task_metadata(task.acceptance_criteria)
    assert kernel_metadata is not None
    payload = dict(kernel_metadata.get("payload") or {})
    compiler_meta = dict(payload.get("compiler") or {})
    task_seed = dict(payload.get("task_seed") or {})

    assert compiler_meta["assignment_plan_envelope"] == assignment_plan
    assert task_seed["assignment_plan_envelope"] == assignment_plan
    assert compiler_meta["assignment_sidecar_plan"] == assignment_plan.get("sidecar_plan", {})
    assert task_seed["assignment_sidecar_plan"] == assignment_plan.get("sidecar_plan", {})
    assert subgraph_service.calls
    assert compiler_meta["assignment_sidecar_plan"]["execution_ordering_hints"] == [
        "Refresh approval evidence before drafting the partner update.",
        "Do not publish until the approval contradiction is resolved.",
        "If blocked, rerun the governed approval refresh and verify the cache state.",
    ]
    assert (
        compiler_meta["assignment_sidecar_plan"]["knowledge_subgraph"]["dependency_paths"][0]["summary"]
        == "Refresh approval evidence before drafting the partner update."
    )
    assert (
        compiler_meta["prompt_text"]
        and "Execution path guidance for this assignment:" in compiler_meta["prompt_text"]
    )
    assert "Refresh approval evidence before drafting the partner update." in compiler_meta["prompt_text"]

    runtime_task_detail = client.get(f"/runtime-center/tasks/{task.id}")
    assert runtime_task_detail.status_code == 200
    runtime_task_payload = runtime_task_detail.json()
    assert runtime_task_payload["task_subgraph"]["dependency_paths"] == [
        "Refresh approval evidence before drafting the partner update.",
    ]
    assert runtime_task_payload["task_subgraph"]["blocker_paths"] == [
        "Do not publish until the approval contradiction is resolved.",
    ]
    assert runtime_task_payload["task_subgraph"]["recovery_paths"] == [
        "If blocked, rerun the governed approval refresh and verify the cache state.",
    ]

    runtime_tasks = client.get("/runtime-center/tasks")
    assert runtime_tasks.status_code == 200
    runtime_task_entry = next(
        item for item in runtime_tasks.json() if item["id"] == task.id
    )
    assert runtime_task_entry["task_subgraph"]["dependency_paths"] == [
        "Refresh approval evidence before drafting the partner update.",
    ]


def test_run_operating_cycle_auto_dispatch_uses_assignment_checklist_instead_of_generic_steps(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    service = app.state.industry_service

    record = IndustryInstanceRecord(
        instance_id="industry-v1-checklist-priority",
        label="Checklist Priority Industry",
        owner_scope="industry-v1-checklist-priority",
    )
    item = BacklogItemRecord(
        id="backlog-checklist-priority",
        industry_instance_id=record.instance_id,
        lane_id=None,
        title="Continue the verified browser remediation move",
        summary="Keep execution on the concrete remediation checklist instead of falling back to generic reporting steps.",
        source_kind="operator",
        source_ref="test:assignment-checklist-overrides-generic-steps",
        metadata={
            "owner_agent_id": "industry-support-specialist-checklist",
            "industry_role_id": "support-specialist",
            "industry_role_name": "Support Specialist",
            "role_name": "Support Specialist",
            "role_summary": "Owns the browser remediation path.",
            "mission": "Complete the remediation move with evidence.",
            "goal_kind": "support-specialist",
            "task_mode": "autonomy-cycle",
            "report_back_mode": "summary",
            "plan_steps": [
                "Confirm the backlog goal and the expected delivery boundary.",
                "Return the completion summary together with the next recommendation.",
            ],
        },
    )
    cycle = OperatingCycleRecord(
        id="cycle-checklist-priority",
        industry_instance_id=record.instance_id,
        cycle_kind="daily",
        title="Checklist priority cycle",
        status="active",
    )
    checklist = [
        "Open the verified browser session and inspect the current remediation state.",
        "Apply the remediation step, capture evidence, and verify the browser result.",
        "Report the concrete outcome and next move based on the verified browser state.",
    ]
    assignment = AssignmentRecord(
        id="assignment-checklist-priority",
        industry_instance_id=record.instance_id,
        cycle_id=cycle.id,
        backlog_item_id=item.id,
        owner_agent_id="industry-support-specialist-checklist",
        owner_role_id="support-specialist",
        title=item.title,
        summary=item.summary,
        report_back_mode="summary",
        metadata={
            "formal_planning": {
                "assignment_plan": {
                    "assignment_id": "assignment-checklist-priority",
                    "report_back_mode": "summary",
                    "sidecar_plan": {
                        "checklist": list(checklist),
                    },
                },
            },
        },
    )

    unit = service._build_operating_cycle_assignment_unit(
        record=record,
        item=item,
        cycle=cycle,
        assignment=assignment,
        actor="test:assignment-checklist-overrides-generic-steps",
    )

    assert unit.context["steps"] == checklist
    assert unit.context["steps"][0] == checklist[0]
    assert "Confirm the backlog goal and the expected delivery boundary." not in unit.context["steps"]
    assert "Return the completion summary together with the next recommendation." not in unit.context["steps"]
    assert unit.context["assignment_sidecar_plan"]["checklist"] == checklist
    assert unit.context["assignment_plan_envelope"]["sidecar_plan"]["checklist"] == checklist


def test_runtime_detail_exposes_first_class_main_brain_cognitive_surface_with_continuity_refs(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    cycle_id = record.current_cycle_id
    assert cycle_id is not None

    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"
    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        title="Browser follow-up handoff",
        summary="Try the browser handoff path and report back to execution-core.",
        status="failed",
        metadata={
            "supervisor_owner_agent_id": "copaw-agent-runner",
            "supervisor_industry_role_id": "execution-core",
            "supervisor_role_name": "Execution Core",
            "chat_writeback_requested_surfaces": ["browser", "desktop", "document"],
            "seat_requested_surfaces": ["browser", "desktop", "document"],
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": environment_ref,
            "recommended_scheduler_action": "handoff",
        },
    )
    app.state.assignment_repository.upsert_assignment(assignment)

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment.id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        headline="Browser follow-up handoff failed",
        summary="The browser handoff is still blocked and needs governed supervisor follow-up.",
        status="recorded",
        result="failed",
        findings=["Browser handoff is still blocked and must return to execution-core supervision."],
        recommendation="Escalate this to the execution-core queue with the same control thread.",
        processed=False,
        work_context_id="work-context:test-cognitive-surface",
    )
    app.state.agent_report_repository.upsert_report(report)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=cycle_id,
    )
    assert [item.id for item in processed] == [report.id]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.current_cycle is not None
    cognitive_surface = detail.current_cycle["main_brain_cognitive_surface"]
    assert cognitive_surface["latest_reports"][0]["report_id"] == report.id
    assert cognitive_surface["synthesis"]["needs_replan"] is True
    assert cognitive_surface["needs_replan"] is True
    assert any(
        "requires main-brain follow-up" in reason
        for reason in cognitive_surface["replan_reasons"]
    )
    assert cognitive_surface["judgment"]["status"] == "replan-required"
    assert cognitive_surface["next_action"]["kind"] == "dispatch-followup"
    assert cognitive_surface["followup_backlog"][0]["metadata"]["source_report_id"] == report.id
    assert cognitive_surface["continuity"]["work_context_ids"] == [report.work_context_id]
    assert cognitive_surface["continuity"]["control_thread_ids"] == [control_thread_id]
    assert cognitive_surface["continuity"]["environment_refs"] == [environment_ref]
    planning_surface = detail.main_brain_planning.model_dump(mode="json")
    assert planning_surface["replan"]["status"] == "needs-replan"
    assert planning_surface["replan"]["source_report_ids"] == [report.id]
    assert detail.current_cycle["main_brain_planning"] == planning_surface

    assert detail.strategy_memory is not None
    strategy_surface = detail.strategy_memory.metadata["main_brain_cognitive_surface"]
    assert strategy_surface["needs_replan"] is True
    assert strategy_surface["judgment"]["status"] == "replan-required"
    assert strategy_surface["continuity"]["control_thread_ids"] == [control_thread_id]


def test_completed_temporary_role_auto_retires_after_report_processing(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    execution_core_agent_id = preview_payload["draft"]["team"]["agents"][0]["agent_id"]
    support_role = _build_support_role(
        execution_core_agent_id,
        employment_mode="temporary",
    )
    facade = _build_team_capability_facade(app)

    created = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": instance_id,
                "operation": "add-role",
                "role": support_role.model_dump(mode="json"),
            },
        ),
    )
    assert created["success"] is True
    assert created["employment_mode"] == "temporary"
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    current_cycle_id = record.current_cycle_id

    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=current_cycle_id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        title="Temporary support cleanup",
        summary="Finish the scoped support package and retire.",
        status="completed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)
    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=current_cycle_id,
        assignment_id=assignment.id,
        owner_agent_id=support_role.agent_id,
        owner_role_id=support_role.role_id,
        headline="Temporary support cleanup completed",
        summary="All scoped support work is done.",
        status="recorded",
        result="completed",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:temporary-retire",
            force=True,
        ),
    )
    assert cycle_result["count"] == 1
    assert report.id in cycle_result["processed_instances"][0]["processed_report_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert all(agent.role_id != support_role.role_id for agent in detail.team.agents)
    assert (
        app.state.agent_profile_override_repository.get_override(support_role.agent_id)
        is None
    )


def test_industry_execute_install_plan_supports_mcp_registry_upgrade(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "filesystem-based onboarding sync",
            "goals": ["sync onboarding files through the official MCP server"],
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
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    target_agent_id = next(
        role["agent_id"]
        for role in preview_payload["draft"]["team"]["agents"]
        if role["role_id"] != "execution-core"
    )

    config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
    registry_catalog = FakeMcpRegistryCatalog()
    app.state.capability_service.get_discovery_service().set_mcp_registry_catalog(
        registry_catalog,
    )
    plan_item = IndustryBootstrapInstallItem(
        install_kind="mcp-registry",
        template_id="io.github/example-filesystem",
        install_option_key="package:test",
        client_key="io_github_example_filesystem",
        enabled=True,
        capability_ids=["mcp:io_github_example_filesystem"],
        target_agent_ids=[target_agent_id],
        capability_assignment_mode="merge",
    )

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
        patch("copaw.industry.service_activation.load_config", return_value=config),
    ):
        first_results = asyncio.run(
            app.state.industry_service.execute_install_plan_for_instance(
                instance_id,
                [plan_item],
            ),
        )
        registry_catalog.catalog_version = "1.1.0"
        registry_catalog.upgrade_version = "1.1.0"
        second_results = asyncio.run(
            app.state.industry_service.execute_install_plan_for_instance(
                instance_id,
                [plan_item],
            ),
        )

    assert first_results[0].status == "installed"
    assert first_results[0].client_key == "io_github_example_filesystem"
    assert second_results[0].status == "updated-existing"
    assert second_results[0].routes["market_catalog"].endswith(
        "io.github%2Fexample-filesystem",
    )
    installed_client = config.mcp.clients["io_github_example_filesystem"]
    assert installed_client.registry is not None
    assert installed_client.registry.version == "1.1.0"
