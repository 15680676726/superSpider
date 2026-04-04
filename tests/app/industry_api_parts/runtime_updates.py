# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403
from copaw.industry.chat_writeback import build_chat_writeback_plan
from copaw.kernel.governance import GovernanceService
from copaw.kernel.models import KernelTask
from copaw.state import AgentReportRecord, AssignmentRecord, SQLiteStateStore
from copaw.state.repositories import SqliteGovernanceControlRepository
from copaw.state.human_assist_task_service import HumanAssistTaskService
from copaw.state.repositories import SqliteHumanAssistTaskRepository


def test_industry_service_facade_reads_runtime_detail_from_view_service() -> None:
    service = IndustryService.__new__(IndustryService)
    detail = {"current_cycle": {"cycle_id": "cycle-1"}, "backlog": [{"id": "b-1"}]}
    service._view_service = SimpleNamespace(
        get_instance_detail=lambda instance_id: detail if instance_id == "industry-1" else None,
    )

    assert service.get_instance_detail("industry-1") is detail


def test_report_closure_helper_merge_keeps_surface_and_source_report_continuity() -> None:
    from copaw.industry.service_report_closure import merge_report_followup_metadata

    merged = merge_report_followup_metadata(
        base={
            "owner_agent_id": "",
            "seat_requested_surfaces": ["browser"],
            "chat_writeback_requested_surfaces": ["browser"],
            "source_report_ids": ["report-1"],
            "source_report_id": "report-1",
        },
        extra={
            "owner_agent_id": "copaw-agent-runner",
            "seat_requested_surfaces": ["desktop", "document", "browser"],
            "chat_writeback_requested_surfaces": ["desktop"],
            "source_report_ids": ["report-2", "report-1"],
        },
    )

    assert merged["owner_agent_id"] == "copaw-agent-runner"
    assert merged["seat_requested_surfaces"] == ["browser", "desktop", "document"]
    assert merged["chat_writeback_requested_surfaces"] == ["browser", "desktop", "document"]
    assert merged["source_report_ids"] == ["report-1", "report-2"]
    assert merged["source_report_id"] == "report-1"


def _build_test_chat_writeback_plan(message_text: str):
    lowered = message_text.lower()
    if "must include" in lowered and "weekly" in lowered:
        return build_chat_writeback_plan(
            message_text,
            approved_classifications=["backlog", "schedule"],
            operator_requirements=[message_text],
            switch_to_operator_guided=True,
            goal_title="市场调研主线",
            goal_summary=message_text,
            goal_plan_steps=[
                "Clarify the market research scope and owners.",
                "Persist competitor monitoring as a governed follow-up loop.",
                "Review evidence weekly and update the main loop.",
            ],
            schedule_title="weekly competitor review",
            schedule_summary=f"Run the formal weekly review loop: {message_text}",
            schedule_cron="0 9 * * 1",
            schedule_prompt=(
                "Execute the weekly market research and competitor monitoring loop: "
                f"{message_text}."
            ),
        )
    if "每月复盘" in message_text:
        return build_chat_writeback_plan(
            message_text,
            approved_classifications=["backlog", "schedule"],
            operator_requirements=[message_text],
            goal_title="整体经营节奏主线",
            goal_summary=message_text,
            goal_plan_steps=[
                "Bring the full operating cadence into the governed main loop.",
                "Track monthly review evidence and operating exceptions.",
                "Use each review to adjust the next operating cycle.",
            ],
            schedule_title="monthly operating review",
            schedule_summary=f"Run the monthly operating review loop: {message_text}",
            schedule_cron="0 9 1 * *",
            schedule_prompt=(
                "Run the monthly operating review against the formal instruction: "
                f"{message_text}."
            ),
        )
    if "工作日执行一次" in message_text:
        return build_chat_writeback_plan(
            message_text,
            approved_classifications=["backlog", "schedule"],
            operator_requirements=[message_text],
            goal_title="现场巡检主线",
            goal_summary=message_text,
            goal_plan_steps=[
                "Keep the field inspection loop on the main operating path.",
                "Track the weekday execution cadence and evidence trail.",
                "Escalate exceptions into the next governed step.",
            ],
            schedule_title="workday field inspection cadence",
            schedule_summary=f"Run the workday field inspection loop: {message_text}",
            schedule_cron="0 9 * * 1-5",
            schedule_prompt=(
                "Run the field inspection cadence on workdays: "
                f"{message_text}."
            ),
        )
    if "改成先做现场验证再做规模复制" in message_text:
        return build_chat_writeback_plan(
            message_text,
            approved_classifications=["strategy"],
            operator_requirements=[message_text],
            priority_order=["先做现场验证", "再做规模复制"],
            switch_to_operator_guided=True,
        )
    raise AssertionError(f"Missing test writeback plan fixture for: {message_text}")


def test_compile_industry_schedule_seeds_injects_rich_runtime_request_context() -> None:
    owner_scope = "industry-v1-northwind-robotics"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)

    seeds = compile_industry_schedule_seeds(
        profile,
        draft=draft,
        owner_scope=owner_scope,
    )

    assert seeds
    request = seeds[0].request_payload
    assert request["industry_instance_id"] == draft.team.team_id
    assert request["industry_label"] == draft.team.label
    assert request["owner_scope"] == owner_scope
    assert request["session_kind"] == "industry-control-thread"
    assert request["control_thread_id"] == request["session_id"]
    assert request["task_mode"] == "recurring-review"
    assert request["industry_role_name"]
    prompt_text = request["input"][0]["content"][0]["text"]
    assert "Task mode: recurring review." in prompt_text
    assert "Role contract:" in prompt_text
    assert "Evidence contract:" in prompt_text


def test_industry_bootstrap_goal_compile_regression_keeps_specialist_runtime_contract(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    owner_scope = "industry-v1-northwind-robotics"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": True,
            "auto_dispatch": False,
            "execute": False,
        },
    )

    assert response.status_code == 200
    bootstrap_payload = response.json()
    specialist_goal = next(
        item for item in bootstrap_payload["goals"] if item["owner_agent_id"] != "copaw-agent-runner"
    )
    specialist_goal_id = specialist_goal["goal"]["id"]
    specialist_goal_record = app.state.goal_service.get_goal(specialist_goal_id)
    assert specialist_goal_record is not None
    assert specialist_goal_record.industry_instance_id == bootstrap_payload["team"]["team_id"]
    assert specialist_goal_record.lane_id
    specialist_lane = app.state.operating_lane_service.get_lane(
        specialist_goal_record.lane_id,
    )
    assert specialist_lane is not None
    assert specialist_lane.owner_agent_id == specialist_goal["owner_agent_id"]
    specialist_override = app.state.goal_override_repository.get_override(
        specialist_goal_id,
    )
    assert specialist_override is not None
    app.state.goal_override_repository.upsert_override(
        specialist_override.model_copy(
            update={
                "compiler_context": {
                    "bootstrap_kind": "industry-v1",
                    "report_back_mode": (
                        specialist_override.compiler_context.get("report_back_mode")
                        if isinstance(specialist_override.compiler_context, dict)
                        else None
                    )
                    or "summary",
                },
            },
        ),
    )

    compiled = [
        spec.model_dump(mode="json")
        for spec in app.state.goal_service.compile_goal(
            specialist_goal_id,
            context={},
        )
    ]

    payload = compiled[0]["payload"]
    assert payload["request"]["agent_id"] == specialist_goal["owner_agent_id"]
    assert payload["request"]["industry_instance_id"] == bootstrap_payload["team"]["team_id"]
    assert payload["request"]["lane_id"] == specialist_goal_record.lane_id
    assert payload["request"]["industry_role_id"] == specialist_lane.owner_role_id
    assert payload["request"]["owner_scope"] == owner_scope
    assert payload["request"]["session_kind"] == "industry-agent-chat"
    assert payload["request"]["task_mode"]
    assert payload["request_context"]["industry_label"] == bootstrap_payload["team"]["label"]
    assert payload["request_context"]["industry_role_name"]
    assert payload["request_context"]["task_mode"] == payload["request"]["task_mode"]
    assert payload["meta"]["request_context"]["industry_role_id"]
    assert payload["task_seed"]["request_context"]["industry_instance_id"] == (
        bootstrap_payload["team"]["team_id"]
    )
    assert payload["compiler"]["request_context"]["industry_role_name"] == (
        payload["request_context"]["industry_role_name"]
    )
    assert payload["compiler"]["request_context"]["task_mode"] == payload["request"]["task_mode"]
    prompt_text = payload["compiler"]["prompt_text"]
    assert "Runtime role framing for this execution:" in prompt_text
    assert f"- Industry team: {bootstrap_payload['team']['label']}" in prompt_text
    assert "- Evidence expectations:" in prompt_text


def test_industry_bootstrap_specialist_runtime_metadata_only_persists_current_focus(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    owner_scope = "industry-v1-focus-dual-write"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": True,
            "auto_dispatch": False,
            "execute": False,
        },
    )

    assert response.status_code == 200
    bootstrap_payload = response.json()
    specialist_goal = next(
        item for item in bootstrap_payload["goals"] if item["owner_agent_id"] != "copaw-agent-runner"
    )

    runtime = app.state.agent_runtime_repository.get_runtime(specialist_goal["owner_agent_id"])

    assert runtime is not None
    metadata = runtime.metadata
    assert "goal_id" not in metadata
    assert "goal_title" not in metadata
    assert metadata["current_focus_kind"] == "goal"
    assert metadata["current_focus_id"] == specialist_goal["goal"]["id"]
    assert metadata["current_focus"] == specialist_goal["goal"]["title"]


def test_industry_runtime_sync_preserves_assignment_focus_without_goal(tmp_path) -> None:
    app = _build_industry_app(tmp_path)

    owner_scope = "industry-v1-assignment-focus"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["stabilize the assignment relay"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)
    specialist = next(agent for agent in draft.team.agents if agent.agent_id != "copaw-agent-runner")

    app.state.industry_service._sync_actor_runtime_surface(  # pylint: disable=protected-access
        agent=specialist,
        instance_id=draft.team.team_id,
        owner_scope=owner_scope,
        goal_id=None,
        goal_title=None,
        status="waiting",
        assignment_id="assignment-ops-1",
        assignment_title="Review assignment relay",
        assignment_summary="Keep the specialist focused on the active assignment.",
        assignment_status="running",
    )

    runtime = app.state.agent_runtime_repository.get_runtime(specialist.agent_id)

    assert runtime is not None
    metadata = runtime.metadata
    assert "goal_id" not in metadata
    assert "goal_title" not in metadata
    assert metadata["current_focus_kind"] == "assignment"
    assert metadata["current_focus_id"] == "assignment-ops-1"
    assert metadata["current_focus"] == "Review assignment relay"


def test_industry_preview_returns_service_unavailable_when_chat_model_missing(
    tmp_path,
) -> None:
    def _missing_chat_model():
        raise ValueError("No active or fallback model configured.")

    app = _build_industry_app(
        tmp_path,
        draft_generator=IndustryDraftGenerator(model_factory=_missing_chat_model),
    )
    client = TestClient(app)

    response = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Industrial Equipment",
            "company_name": "Northwind Robotics",
        },
    )

    assert response.status_code == 503
    payload = response.json()
    assert "available active chat model" in payload["detail"]
    assert "No active or fallback model configured." in payload["detail"]


def test_industry_list_instances_hides_empty_placeholder_records(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-empty-placeholder",
            label="Empty Placeholder",
            summary="Should not appear in recent industry teams.",
            owner_scope="industry-v1-empty-placeholder",
            status="active",
            profile_payload={"industry": "Placeholder"},
            team_payload={
                "schema_version": "industry-team-blueprint-v1",
                "team_id": "industry-v1-empty-placeholder",
                "label": "Empty Placeholder",
                "summary": "placeholder",
                "agents": [],
            },
            goal_ids=["goal-placeholder"],
            agent_ids=[],
            schedule_ids=[],
        ),
    )

    response = client.get("/industry/v1/instances")
    assert response.status_code == 200
    assert response.json() == []



def test_industry_list_instances_uses_lightweight_summary_without_detail_build(
    tmp_path,
    monkeypatch,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-lightweight",
            label="Lightweight Summary",
            summary="Summary should not materialize full detail.",
            owner_scope="industry-v1-lightweight",
            status="active",
            profile_payload={"industry": "Industrial Automation"},
            team_payload={
                "schema_version": "industry-team-blueprint-v1",
                "team_id": "industry-v1-lightweight",
                "label": "Lightweight Summary",
                "summary": "summary",
                "agents": [
                    {
                        "schema_version": "industry-role-blueprint-v1",
                        "role_id": "execution-core",
                        "agent_id": "copaw-agent-runner",
                        "name": "Execution Core",
                        "role_name": "Execution Core",
                        "role_summary": "Owns the execution loop.",
                        "mission": "Drive the next operating move.",
                        "goal_kind": "execution-core",
                        "agent_class": "business",
                        "activation_mode": "persistent",
                        "suspendable": False,
                        "risk_level": "guarded",
                        "environment_constraints": [],
                        "allowed_capabilities": ["system:dispatch_query"],
                        "evidence_expectations": ["next recommendation"],
                    }
                ],
            },
            execution_core_identity_payload={
                "schema_version": "industry-execution-core-identity-v1",
                "binding_id": "industry-v1-lightweight:execution-core",
                "agent_id": "copaw-agent-runner",
                "role_id": "execution-core",
                "industry_instance_id": "industry-v1-lightweight",
                "identity_label": "Lightweight Summary / Execution Core",
                "industry_label": "Lightweight Summary",
                "industry_summary": "summary",
                "role_name": "Execution Core",
                "role_summary": "Owns the execution loop.",
                "mission": "Drive the next operating move.",
                "thinking_axes": ["Industry focus: Industrial Automation"],
                "environment_constraints": [],
                "allowed_capabilities": ["system:dispatch_query"],
                "evidence_expectations": ["next recommendation"],
            },
            goal_ids=[],
            agent_ids=["copaw-agent-runner"],
            schedule_ids=["schedule-1"],
        ),
    )

    def _raise_if_called(record):
        raise AssertionError(
            "_build_instance_detail should not be called for instance summaries"
        )

    monkeypatch.setattr(
        app.state.industry_service,
        "_build_instance_detail",
        _raise_if_called,
    )

    response = client.get("/industry/v1/instances")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["instance_id"] == "industry-v1-lightweight"
    assert "goal_count" not in payload[0]["stats"]
    assert "active_goal_count" not in payload[0]["stats"]
    assert payload[0]["stats"]["schedule_count"] == 1


def test_industry_bootstrap_response_uses_lightweight_instance_summary(
    tmp_path,
    monkeypatch,
) -> None:
    app = _build_industry_app(tmp_path)
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            business_model="B2B software and implementation services",
            channels=["industry events", "integrator partners"],
            goals=["launch two pilot deployments"],
            experience_mode="operator-guided",
            experience_notes="Review the last 7 days of lead quality before scaling spend.",
            operator_requirements=["must include customer-service chat loop", "must keep weekly competitor monitoring"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )

    def _raise_if_called(record):
        raise AssertionError(
            "_build_instance_detail should not be called for bootstrap instance summaries"
        )

    monkeypatch.setattr(
        app.state.industry_service,
        "_build_instance_detail",
        _raise_if_called,
    )

    with TestClient(app) as client:
        response = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": profile.model_dump(mode="json"),
                "draft": draft.model_dump(mode="json"),
                "auto_dispatch": True,
                "execute": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    summary = payload["routes"]["instance_summary"]
    assert summary["instance_id"] == draft.team.team_id
    assert "goals" not in summary
    assert summary["strategy_memory"]["scope_type"] == "industry"
    assert summary["strategy_memory"]["owner_agent_id"] == "copaw-agent-runner"
    assert summary["strategy_memory"]["active_goal_ids"]
    assert summary["strategy_memory"]["teammate_contracts"]
    assert summary["strategy_memory"]["metadata"]["experience_mode"] == "operator-guided"
    assert any(
        "must include customer-service chat loop" in item
        for item in summary["strategy_memory"]["metadata"]["operator_requirements"]
    )
    assert "Review the last 7 days of lead quality before scaling spend." in summary["strategy_memory"]["execution_constraints"][0] or any(
        "Review the last 7 days of lead quality before scaling spend." in item
        for item in summary["strategy_memory"]["execution_constraints"]
    )
    assert "tasks" not in summary


def test_industry_chat_writeback_routes_matching_specialist_goal_schedule_and_strategy(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)
    owner_scope = "industry-v1-northwind-robotics"

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        owner_scope,
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]
    baseline_record = app.state.industry_instance_repository.get_instance(instance_id)
    assert baseline_record is not None
    initial_goal_count = len(baseline_record.goal_ids or [])
    initial_schedule_count = len(baseline_record.schedule_ids or [])

    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text="must include market research and competitor monitoring in the main loop, weekly review",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=_build_test_chat_writeback_plan(
                "must include market research and competitor monitoring in the main loop, weekly review"
            ),
        ),
    )

    assert result is not None
    assert result["applied"] is True
    assert result["strategy_updated"] is True
    assert result["created_goal_ids"] == []
    assert len(result["created_schedule_ids"]) == 1
    assert result["goal_dispatches"] == []
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert result["target_owner_agent_id"] != "copaw-agent-runner"
    assert result["target_industry_role_id"] == "researcher"
    assert result["target_match_signals"]
    assert result["target_lane_id"]
    assert result["target_lane_title"]
    assert {"strategy", "backlog", "lane", "schedule"}.issubset(
        set(result["classification"]),
    )
    assert "goal" not in result["classification"]
    assert "immediate-goal" not in result["classification"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    assert len(record.goal_ids or []) == initial_goal_count
    assert len(record.schedule_ids or []) == initial_schedule_count + 1
    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    backlog_item = next(
        item
        for item in detail.backlog
        if item["backlog_item_id"] == result["created_backlog_ids"][0]
    )
    assert backlog_item["lane_id"] == result["target_lane_id"]
    assert backlog_item["goal_id"] is None

    updated_profile = IndustryProfile.model_validate(record.profile_payload)
    assert updated_profile.operator_requirements

    strategy = app.state.strategy_memory_service.get_active_strategy(
        scope_type="industry",
        scope_id=instance_id,
        owner_agent_id="copaw-agent-runner",
    )
    assert strategy is not None
    assert strategy.metadata["operator_requirements"]
    history_item = next(
        item
        for item in strategy.metadata["chat_writeback_history"]
        if item["fingerprint"] == result["fingerprint"]
    )
    assert history_item["instruction"] in updated_profile.operator_requirements
    assert history_item["instruction"] in strategy.metadata["operator_requirements"]
    assert {"strategy", "backlog", "lane", "schedule"}.issubset(
        set(history_item["classification"]),
    )
    assert "goal" not in history_item["classification"]
    assert "immediate-goal" not in history_item["classification"]

    schedule = app.state.schedule_repository.get_schedule(
        result["created_schedule_ids"][0],
    )
    assert schedule is not None
    assert schedule.lane_id == result["target_lane_id"]
    assert schedule.schedule_kind == "cadence"
    assert schedule.spec_payload["meta"]["source"] == "chat-writeback"
    assert schedule.spec_payload["meta"]["industry_instance_id"] == instance_id
    assert schedule.spec_payload["meta"]["owner_agent_id"] == result["target_owner_agent_id"]
    assert schedule.spec_payload["request"]["industry_role_id"] == "researcher"
    assert schedule.spec_payload["request"]["owner_scope"] == owner_scope
    assert schedule.spec_payload["request"]["industry_label"]
    assert schedule.spec_payload["request"]["task_mode"] == "chat-writeback-followup"
    prompt_text = schedule.spec_payload["request"]["input"][0]["content"][0]["text"]
    assert "Task mode: chat writeback follow-up." in prompt_text
    assert history_item["instruction"] in prompt_text
    selected_override = app.state.agent_profile_override_repository.get_override(
        result["target_owner_agent_id"],
    )
    assert selected_override is not None
    assert selected_override.current_focus_kind == "goal"
    assert selected_override.current_focus_id in set(record.goal_ids or [])
    assert selected_override.current_focus

    duplicate = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=history_item["instruction"],
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=_build_test_chat_writeback_plan(history_item["instruction"]),
        ),
    )
    assert duplicate is not None
    assert duplicate["applied"] is False
    assert duplicate["deduplicated"] is True
    strategy_after_duplicate = app.state.strategy_memory_service.get_active_strategy(
        scope_type="industry",
        scope_id=instance_id,
        owner_agent_id="copaw-agent-runner",
    )
    assert strategy_after_duplicate is not None
    duplicate_history_item = next(
        item
        for item in strategy_after_duplicate.metadata["chat_writeback_history"]
        if item["fingerprint"] == result["fingerprint"]
    )
    assert {"strategy", "backlog", "lane", "schedule"}.issubset(
        set(duplicate_history_item["classification"]),
    )


def test_industry_chat_writeback_keeps_unmatched_work_in_backlog_when_no_specialist_matches(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text="\u628a\u6574\u4f53\u7ecf\u8425\u8282\u594f\u7eb3\u5165\u4e3b\u7ebf\uff0c\u5e76\u4e14\u6bcf\u6708\u590d\u76d8\u4e00\u6b21",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=_build_test_chat_writeback_plan(
                "\u628a\u6574\u4f53\u7ecf\u8425\u8282\u594f\u7eb3\u5165\u4e3b\u7ebf\uff0c\u5e76\u4e14\u6bcf\u6708\u590d\u76d8\u4e00\u6b21"
            ),
        ),
    )

    assert result is not None
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert result["target_owner_agent_id"] is None
    assert result["target_industry_role_id"] is None
    assert result["supervisor_owner_agent_id"] == "copaw-agent-runner"
    assert result["supervisor_industry_role_id"] == "execution-core"
    assert result["created_goal_ids"] == []
    assert result["goal_dispatches"] == []
    assert result["created_backlog_ids"]
    assert "routing-pending" in result["classification"]

    backlog_item = app.state.backlog_item_repository.get_item(result["created_backlog_ids"][0])
    assert backlog_item is not None
    assert backlog_item.assignment_id is None
    assert backlog_item.goal_id is None
    assert backlog_item.metadata.get("owner_agent_id") is None
    assert backlog_item.metadata.get("industry_role_id") is None
    assert backlog_item.metadata.get("supervisor_owner_agent_id") == "copaw-agent-runner"
    assert backlog_item.metadata.get("supervisor_industry_role_id") == "execution-core"

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:routing-gap",
            force=True,
            backlog_item_ids=result["created_backlog_ids"],
            auto_dispatch_materialized_goals=False,
        ),
    )
    assert cycle_result["processed_instances"][0]["created_assignment_ids"] == []

    schedule = app.state.schedule_repository.get_schedule(
        result["created_schedule_ids"][0],
    )
    assert schedule is not None
    assert schedule.spec_payload["request"]["industry_role_id"] == "execution-core"


def test_industry_chat_writeback_auto_creates_temporary_seat_for_low_risk_local_gap(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]
    baseline_detail = app.state.industry_service.get_instance_detail(instance_id)
    assert baseline_detail is not None
    initial_assignment_count = len(baseline_detail.assignments)

    message_text = "请在 Windows 桌面客户端里跟进客户，并把 Excel 清单更新好"
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
                goal_title="桌面文件整理",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Open the relevant desktop workspace and inspect the current file set.",
                    "Move the target text files into the expected folder structure.",
                    "Update the tracking sheet with the result and blockers.",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert "temporary-seat-auto" in result["classification"]
    assert result["created_goal_ids"] == []
    assert result["goal_dispatches"] == []

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert any(agent.employment_mode == "temporary" for agent in detail.team.agents)
    backlog_item = app.state.backlog_item_repository.get_item(result["created_backlog_ids"][0])
    assert backlog_item is not None
    assert backlog_item.goal_id is None
    assert backlog_item.assignment_id is None


def test_industry_chat_writeback_auto_creates_temporary_local_ops_for_desktop_file_request(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "我需要你把电脑桌面的text文件整理到一个文件夹"
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
                goal_title="桌面 text 文件整理",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Open the desktop workspace and inspect the current text files.",
                    "Move the target text files into the destination folder.",
                    "Write back the organization result and any blocker.",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert "temporary-seat-auto" in result["classification"]
    assert result["seat_requested_surfaces"] == ["file", "desktop"]
    assert result["target_owner_agent_id"] != "copaw-agent-runner"

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    temp_local_ops = next(
        agent
        for agent in detail.team.agents
        if agent.employment_mode == "temporary"
        and agent.role_id == "temporary-local-ops-worker"
    )
    assert "mcp:desktop_windows" in list(temp_local_ops.allowed_capabilities)


def test_industry_chat_writeback_auto_closes_temporary_seat_desktop_gap_via_governed_install(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "我需要你把电脑桌面的text文件整理到一个文件夹"
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
            app.state.industry_service.apply_execution_chat_writeback(
                industry_instance_id=instance_id,
                message_text=message_text,
                owner_agent_id="copaw-agent-runner",
                session_id=f"industry-chat:{instance_id}:execution-core",
                channel="console",
                writeback_plan=build_chat_writeback_plan(
                    message_text,
                    approved_classifications=["backlog"],
                    goal_title="桌面 text 文件整理",
                    goal_summary=message_text,
                    goal_plan_steps=[
                        "Open the desktop workspace and inspect the current text files.",
                        "Move the target text files into the destination folder.",
                        "Write back the organization result and any blocker.",
                    ],
                ),
            ),
        )

    assert result is not None
    assert "temporary-seat-auto" in result["classification"]
    assert app.state.capability_service.get_mcp_client_info("desktop_windows") is not None
    install_tasks = app.state.task_repository.list_tasks(
        task_type="system:create_mcp_client",
    )
    assignment_tasks = app.state.task_repository.list_tasks(
        task_type="system:apply_role",
    )
    assert install_tasks
    assert assignment_tasks
    assert any(task.owner_agent_id == "copaw-agent-runner" for task in install_tasks)
    assert any(task.owner_agent_id == "copaw-agent-runner" for task in assignment_tasks)


def test_industry_chat_writeback_routes_unknown_desktop_app_by_surface_plan_instead_of_app_name(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "打开文末天机把这批资料归档"
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
                goal_title="资料归档",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Open the target desktop client and inspect the current material batch.",
                    "Archive the materials into the governed folder structure.",
                    "Write back the archive result and any blocker.",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert "temporary-seat-auto" in result["classification"]
    assert result["seat_requested_surfaces"] == ["file", "desktop"]
    assert result["target_owner_agent_id"] != "copaw-agent-runner"
    assert result["target_industry_role_id"] == "temporary-local-ops-worker"


def test_industry_instance_detail_exposes_supervision_chain_nodes(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "请在 Windows 桌面客户端跟进客户，并更新 Excel 交付清单"
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
                goal_title="桌面客户跟进",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Open the target desktop client.",
                    "Send the next governed follow-up message.",
                    "Update the delivery checklist and report back.",
                ],
            ),
        ),
    )

    assert result is not None
    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.main_chain is not None
    node_ids = [node.node_id for node in detail.main_chain.nodes]
    assert "goal" not in node_ids
    assert "task" not in node_ids
    assert node_ids.index("writeback") < node_ids.index("backlog")
    assert node_ids.index("backlog") < node_ids.index("cycle")
    assert node_ids.index("cycle") < node_ids.index("assignment")
    assert node_ids.index("assignment") < node_ids.index("report")
    assert node_ids.index("report") < node_ids.index("replan")


def test_industry_chat_writeback_creates_governed_seat_proposal_for_high_risk_gap(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "以后长期负责平台投放并直接下单执行"
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
                goal_title="平台投放执行席位",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Define the governed browser execution scope and platform constraints.",
                    "Create the long-term specialist seat only after approval.",
                    "Require structured reports and evidence after each execution loop.",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert "career-seat-proposal" in result["classification"]
    assert result["created_goal_ids"] == []
    assert result["goal_dispatches"] == []
    assert result["created_backlog_ids"]
    assert result["decision_request_id"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.staffing["active_gap"]["requires_confirmation"] is True
    assert detail.staffing["active_gap"]["decision_request_id"] == result["decision_request_id"]

    backlog_item = app.state.backlog_item_repository.get_item(result["created_backlog_ids"][0])
    assert backlog_item is not None
    assert backlog_item.status == "open"
    assert backlog_item.goal_id is None
    assert backlog_item.assignment_id is None


def test_industry_chat_writeback_routes_local_file_request_to_file_capable_specialist(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "请把工作目录里的 text 文件整理到一个文件夹，并写一个整理说明"
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
                goal_title="工作目录文件整理",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Inspect the workspace files and define the folder structure.",
                    "Move the target text files into the destination folder.",
                    "Write a short organization summary and return the result.",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert result["target_industry_role_id"] == "solution-lead"
    assert result["target_owner_agent_id"] != "copaw-agent-runner"
    assert "file capability match" in result["target_match_signals"]


def test_industry_chat_writeback_routes_desktop_request_to_desktop_specialist(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=DesktopIndustryDraftGenerator(),
    )
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = DesktopIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "请在 Windows 桌面客户端跟进客户，并更新 Excel 交付清单"
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
                goal_title="桌面客户跟进",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Open the target conversation in the desktop client.",
                    "Send the next governed follow-up message.",
                    "Update the Excel delivery checklist with the outcome.",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert result["target_industry_role_id"] == "solution-lead"
    assert result["target_owner_agent_id"] != "copaw-agent-runner"
    assert "desktop capability match" in result["target_match_signals"]


def test_industry_chat_writeback_surfaces_browser_seat_proposal_in_runtime_detail(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "Please publish the customer notice in the browser and keep the handoff governed."
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
                goal_title="Browser publish handoff",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Define the governed browser execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence.",
                ],
            ),
        ),
    )

    assert result is not None
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True
    assert "temporary-seat-proposal" in result["classification"]
    assert result["decision_request_id"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.staffing["active_gap"]["kind"] == "temporary-seat-proposal"
    assert detail.staffing["active_gap"]["requires_confirmation"] is True
    assert "browser" in detail.staffing["active_gap"]["requested_surfaces"]
    assert detail.staffing["pending_proposals"]
    pending = detail.staffing["pending_proposals"][0]
    assert pending["kind"] == "temporary-seat-proposal"
    assert pending["requires_confirmation"] is True
    assert "browser" in pending["requested_surfaces"]


def test_industry_chat_writeback_approved_staffing_proposal_unblocks_materialization(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    message_text = "Please publish the customer notice in the browser and keep the handoff governed."
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
                goal_title="Browser publish handoff",
                goal_summary=message_text,
                goal_plan_steps=[
                    "Define the governed browser execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence.",
                ],
            ),
        ),
    )

    assert result is not None
    decision_id = result["decision_request_id"]
    backlog_id = result["created_backlog_ids"][0]
    assert decision_id

    pending_detail = app.state.industry_service.get_instance_detail(instance_id)
    assert pending_detail is not None
    assert pending_detail.staffing["active_gap"] is not None
    assert pending_detail.staffing["pending_proposals"]

    approved = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Approve the governed browser staffing seat.", "execute": True},
    )
    assert approved.status_code == 200
    approved_payload = approved.json()
    assert approved_payload["phase"] == "completed"
    assert approved_payload["decision_request_id"] == decision_id

    approved_detail = app.state.industry_service.get_instance_detail(instance_id)
    assert approved_detail is not None
    assert approved_detail.staffing["active_gap"] is None
    assert approved_detail.staffing["pending_proposals"] == []
    assert any(
        item["role_id"] == result["target_industry_role_id"]
        for item in approved_detail.staffing["temporary_seats"]
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:approved-seat-proposal",
            force=True,
            backlog_item_ids=[backlog_id],
            auto_dispatch_materialized_goals=False,
        ),
    )
    assert cycle_result["count"] == 1
    assert cycle_result["processed_instances"][0]["created_assignment_ids"]

    backlog_item = app.state.backlog_item_repository.get_item(backlog_id)
    assert backlog_item is not None
    assert backlog_item.status == "materialized"
    assert backlog_item.assignment_id is not None


def test_bootstrap_researcher_schedule_report_keeps_main_brain_continuity(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)
    owner_scope = "industry-v1-northwind-robotics"

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        owner_scope,
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    instance_id = payload["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"

    researcher_schedule_id = next(
        item["schedule_id"]
        for item in payload["schedules"]
        if item["schedule"]["spec_payload"]["request"]["industry_role_id"] == "researcher"
    )
    schedule = app.state.schedule_repository.get_schedule(researcher_schedule_id)
    assert schedule is not None
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    cycle_id = record.current_cycle_id
    assert cycle_id is not None

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=None,
        owner_agent_id=schedule.spec_payload["meta"]["owner_agent_id"],
        owner_role_id=schedule.spec_payload["request"]["industry_role_id"],
        headline="Research signal loop found follow-up pressure",
        summary="Research loop surfaced a governed follow-up that should return to the main brain chain.",
        status="recorded",
        result="failed",
        findings=["Competitor monitoring surfaced a signal that needs main-brain follow-up."],
        recommendation="Route this follow-up back through the same control thread and governed runtime chain.",
        processed=False,
        work_context_id="work-context:researcher-schedule-followup",
        metadata=dict(schedule.spec_payload.get("meta") or {}),
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
    metadata = followup_backlog["metadata"]
    assert metadata["control_thread_id"] == control_thread_id
    assert metadata["session_id"] == control_thread_id
    assert metadata["environment_ref"] == environment_ref
    assert metadata["work_context_id"] == report.work_context_id
    assert metadata["owner_agent_id"] == "copaw-agent-runner"
    assert metadata["industry_role_id"] == "execution-core"

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    cognitive_surface = runtime_payload["current_cycle"]["main_brain_cognitive_surface"]
    assert cognitive_surface["continuity"]["work_context_ids"] == [report.work_context_id]
    assert cognitive_surface["continuity"]["control_thread_ids"] == [control_thread_id]
    assert cognitive_surface["continuity"]["environment_refs"] == [environment_ref]
    assert runtime_payload["execution"]["current_focus_id"] is None
    assert runtime_payload["execution"]["current_focus"] is None
    assert runtime_payload["main_chain"]["current_focus_id"] is None
    assert runtime_payload["main_chain"]["current_focus"] is None
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert replan_node["status"] == "active"
    assert replan_node["metrics"]["needs_replan"] is True
    assert replan_node["metrics"]["replan_reason_count"] >= 1
    assert replan_node["metrics"]["followup_pressure_count"] >= 1
    assert replan_node["metrics"]["recommended_action"] is not None


def test_staffed_assignment_failure_keeps_supervisor_chain_and_replan_truth(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=(
                "Please publish the customer notice in the browser, "
                "keep the handoff governed, and report back."
            ),
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                "Please publish the customer notice in the browser, keep the handoff governed, and report back.",
                approved_classifications=["backlog"],
                goal_title="Browser publish handoff",
                goal_summary="Publish the customer notice with governed browser handoff.",
                goal_plan_steps=[
                    "Define the governed browser execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence.",
                ],
            ),
        ),
    )

    assert result is not None
    decision_id = result["decision_request_id"]
    backlog_id = result["created_backlog_ids"][0]
    approved = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Approve the governed browser staffing seat.", "execute": True},
    )
    assert approved.status_code == 200

    first_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:staffed-followup-cycle",
            force=True,
            backlog_item_ids=[backlog_id],
            auto_dispatch_materialized_goals=False,
        ),
    )
    assert first_cycle["count"] == 1
    processed_instance = first_cycle["processed_instances"][0]
    assignment_id = processed_instance["created_assignment_ids"][0]
    cycle_id = processed_instance["started_cycle_id"]

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_id,
        owner_agent_id=result["target_owner_agent_id"],
        owner_role_id=result["target_industry_role_id"],
        headline="Browser publish handoff failed",
        summary="The browser publish attempt is still blocked by the unresolved platform handoff.",
        status="recorded",
        result="failed",
        findings=["The platform still requires a governed human handoff before publish can continue."],
        recommendation="Resume the staffed browser seat after the human handoff closes.",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:staffed-followup-replan",
            force=True,
        ),
    )
    assert second_cycle["count"] == 1
    assert report.id in second_cycle["processed_instances"][0]["processed_report_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.staffing["active_gap"] is None
    assert any(
        seat["role_id"] == result["target_industry_role_id"]
        for seat in detail.staffing["temporary_seats"]
    )
    assert detail.current_cycle is not None
    assert detail.current_cycle["synthesis"]["needs_replan"] is True
    assert "Browser publish handoff failed requires main-brain follow-up." in (
        detail.current_cycle["synthesis"]["replan_reasons"]
    )

    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )
    assert followup_backlog["metadata"]["synthesis_kind"] == "failed-report"
    assert followup_backlog["metadata"]["supervisor_owner_agent_id"] == "copaw-agent-runner"
    assert followup_backlog["metadata"]["supervisor_industry_role_id"] == "execution-core"
    assert "browser" in followup_backlog["metadata"]["seat_requested_surfaces"]

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    for agent in runtime_payload.get("agents") or []:
        assert "current_goal_id" not in agent
        assert "current_goal" not in agent
    assert runtime_payload["execution"]["current_focus_id"] is None
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert replan_node["status"] == "active"
    assert replan_node["metrics"]["replan_reason_count"] >= 1
    assert "Browser publish handoff failed requires main-brain follow-up." in (
        replan_node["metrics"]["replan_reasons"]
    )
    assert "browser" in replan_node["metrics"]["followup_pressure_surfaces"]
    assert replan_node["metrics"]["followup_pressure_count"] >= 1
    assert replan_node["metrics"]["recommended_action"] is not None


def test_runtime_detail_exposes_stable_main_brain_planning_surface_from_formal_sidecars(
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
            "goals": ["keep the operating loop governed and visible"],
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
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    current_cycle_id = record.current_cycle_id
    assert current_cycle_id is not None

    cycle_record = app.state.operating_cycle_repository.get_cycle(current_cycle_id)
    assert cycle_record is not None
    cycle_planning = {
        "strategy_constraints": {
            "mission": "Keep the operating loop governed and visible.",
            "priority_order": ["governed follow-up", "steady execution"],
            "planning_policy": ["prefer-followup-before-net-new"],
            "review_rules": ["repeat-failure-needs-review"],
            "strategic_uncertainties": [
                {
                    "uncertainty_id": "uncertainty-governed-followup",
                    "statement": "Governed follow-up demand may outpace the current lane mix.",
                    "scope": "strategy",
                    "impact_level": "high",
                    "current_confidence": 0.42,
                    "review_by_cycle": "cycle-weekly-1",
                    "escalate_when": ["confidence-drop", "target-miss"],
                }
            ],
            "lane_budgets": [
                {
                    "lane_id": "lane-growth",
                    "budget_window": "next-2-cycles",
                    "target_share": 0.5,
                    "min_share": 0.35,
                    "max_share": 0.65,
                    "review_pressure": "high",
                    "force_include_reason": "Keep governed follow-up visible until uncertainty closes.",
                }
            ],
            "strategy_trigger_rules": [
                {
                    "rule_id": "review-rule:0",
                    "source_type": "review_rule",
                    "trigger_family": "review_rule",
                    "summary": "repeat-failure-needs-review",
                },
                {
                    "rule_id": "uncertainty:uncertainty-governed-followup:confidence-drop",
                    "source_type": "uncertainty_escalation",
                    "source_ref": "uncertainty-governed-followup",
                    "trigger_family": "confidence_collapse",
                    "summary": (
                        "Governed follow-up demand may outpace the current lane mix. "
                        "(confidence drop)"
                    ),
                    "decision_hint": "strategy_review_required",
                },
            ],
            "paused_lane_ids": [],
        },
        "cycle_decision": {
            "should_start": True,
            "reason": "planned-open-backlog",
            "cycle_kind": cycle_record.cycle_kind,
            "selected_backlog_item_ids": list(cycle_record.backlog_item_ids or []),
            "selected_lane_ids": list(cycle_record.focus_lane_ids or []),
            "max_assignment_count": len(list(cycle_record.assignment_ids or [])),
            "summary": "Persisted planning sidecar for runtime exposure.",
            "planning_policy": ["prefer-followup-before-net-new"],
            "metadata": {
                "pending_report_count": 0,
                "open_backlog_count": len(list(cycle_record.backlog_item_ids or [])),
            },
        },
        "report_replan": {
            "decision_id": "report-synthesis:needs-replan:governed-followup",
            "status": "needs-replan",
            "decision_kind": "lane_reweight",
            "summary": "Governed follow-up pressure should rebalance the active lane before more net-new work.",
            "reason_ids": ["failed-report:governed-followup"],
            "source_report_ids": ["report-governed-followup"],
            "topic_keys": ["governed-followup"],
            "trigger_context": {
                "trigger_families": ["repeated-blocker", "confidence-collapse"],
                "strategic_uncertainty_ids": ["uncertainty-governed-followup"],
                "lane_budget_pressure": {
                    "lane-growth": "over-target-share",
                },
            },
            "directives": [{"directive_id": "directive-lane-reweight"}],
            "recommended_actions": [{"action_id": "action-lane-reweight"}],
        },
    }
    app.state.operating_cycle_repository.upsert_cycle(
        cycle_record.model_copy(
            update={
                "metadata": {
                    **dict(cycle_record.metadata or {}),
                    "formal_planning": cycle_planning,
                },
            },
        ),
    )

    assignment_id = list(cycle_record.assignment_ids or [])[0]
    assignment_record = app.state.assignment_repository.get_assignment(assignment_id)
    assert assignment_record is not None
    assignment_planning = {
        "strategy_constraints": cycle_planning["strategy_constraints"],
        "cycle_decision": cycle_planning["cycle_decision"],
        "report_replan": cycle_planning["report_replan"],
        "assignment_plan": {
            "assignment_id": assignment_record.id,
            "backlog_item_id": assignment_record.backlog_item_id,
            "cycle_id": assignment_record.cycle_id,
            "owner_agent_id": assignment_record.owner_agent_id,
            "owner_role_id": assignment_record.owner_role_id,
            "report_back_mode": assignment_record.report_back_mode,
            "checkpoints": [
                {"kind": "plan-step", "label": "Clarify the governed move."},
                {"kind": "verify", "label": "Verify the result and evidence."},
            ],
            "acceptance_criteria": [
                "Capture governed evidence before reporting complete.",
            ],
            "sidecar_plan": {
                "checklist": ["Clarify the governed move.", "Verify the result."],
            },
        },
    }
    app.state.assignment_repository.upsert_assignment(
        assignment_record.model_copy(
            update={
                "metadata": {
                    **dict(assignment_record.metadata or {}),
                    "formal_planning": assignment_planning,
                },
            },
        ),
    )

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.current_cycle is not None
    assert detail.main_brain_planning is not None

    planning_surface = detail.main_brain_planning.model_dump(mode="json")
    assert planning_surface["is_truth_store"] is False
    assert planning_surface["source"] == "industry-runtime-read-model"
    assert planning_surface["strategy_constraints"] == cycle_planning["strategy_constraints"]
    assert planning_surface["strategy_constraints"]["strategic_uncertainties"][0][
        "uncertainty_id"
    ] == "uncertainty-governed-followup"
    assert planning_surface["strategy_constraints"]["lane_budgets"][0]["lane_id"] == (
        "lane-growth"
    )
    assert planning_surface["latest_cycle_decision"]["cycle_id"] == current_cycle_id
    assert planning_surface["latest_cycle_decision"]["selected_backlog_item_ids"] == (
        cycle_planning["cycle_decision"]["selected_backlog_item_ids"]
    )
    assert planning_surface["latest_cycle_decision"]["selected_lane_ids"] == (
        cycle_planning["cycle_decision"]["selected_lane_ids"]
    )
    assert planning_surface["focused_assignment_plan"] == (
        assignment_planning["assignment_plan"]
    )
    assert planning_surface["replan"]["status"] == "needs-replan"
    assert planning_surface["replan"]["decision_kind"] == "lane_reweight"
    assert planning_surface["replan"]["trigger_context"]["strategic_uncertainty_ids"] == [
        "uncertainty-governed-followup"
    ]
    assert [rule["rule_id"] for rule in planning_surface["replan"]["strategy_trigger_rules"]] == [
        "review-rule:0",
        "uncertainty:uncertainty-governed-followup:confidence-drop",
    ]
    uncertainty_register = planning_surface["replan"]["uncertainty_register"]
    assert uncertainty_register["is_truth_store"] is False
    assert uncertainty_register["source"] == "industry-runtime-read-model"
    assert uncertainty_register["durable_source"] == "strategy-memory"
    assert uncertainty_register["summary"]["uncertainty_count"] == 1
    assert uncertainty_register["summary"]["lane_budget_count"] == 1
    assert uncertainty_register["summary"]["trigger_rule_count"] >= 2
    assert uncertainty_register["summary"]["review_cycle_ids"] == ["cycle-weekly-1"]
    assert "confidence_collapse" in uncertainty_register["summary"]["trigger_families"]
    assert "target_miss" in uncertainty_register["summary"]["trigger_families"]
    assert uncertainty_register["items"] == [
        {
            "uncertainty_id": "uncertainty-governed-followup",
            "statement": "Governed follow-up demand may outpace the current lane mix.",
            "scope": "strategy",
            "impact_level": "high",
            "current_confidence": 0.42,
            "review_by_cycle": "cycle-weekly-1",
            "escalate_when": ["confidence-drop", "target-miss"],
            "trigger_rule_ids": [
                "uncertainty:uncertainty-governed-followup:confidence-drop",
                "uncertainty:uncertainty-governed-followup:target-miss",
            ],
            "trigger_families": ["confidence_collapse", "target_miss"],
        },
    ]
    assert detail.current_cycle["main_brain_planning"] == planning_surface

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    assert runtime_payload["main_brain_planning"] == planning_surface
    assert runtime_payload["current_cycle"]["main_brain_planning"] == planning_surface


def test_governance_blocks_dispatch_when_pending_staffing_proposal_is_not_top_active_gap(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text="Please publish the customer notice in the browser and keep the handoff governed.",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                "Please publish the customer notice in the browser and keep the handoff governed.",
                approved_classifications=["backlog"],
                goal_title="Browser publish handoff",
                goal_summary="Publish the customer notice with governed browser handoff.",
                goal_plan_steps=[
                    "Define the governed browser execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence.",
                ],
            ),
        ),
    )
    assert result is not None
    decision_id = result["decision_request_id"]

    app.state.backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=None,
        title="Investigate unmapped desktop routing",
        summary="Keep the unmapped surface request in backlog until routing is clarified.",
        priority=5,
        source_ref="chat-writeback:test-routing-pending",
        metadata={
            "source": "chat-writeback",
            "chat_writeback_gap_kind": "routing-pending",
            "seat_resolution_kind": "routing-pending",
            "chat_writeback_requested_surfaces": ["desktop", "browser"],
            "seat_requested_surfaces": ["desktop", "browser"],
            "chat_writeback_target_role_name": "Pending staffing resolution",
        },
    )

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.staffing["active_gap"]["kind"] == "routing-pending"
    assert any(
        item["decision_request_id"] == decision_id
        for item in detail.staffing["pending_proposals"]
    )

    governance = GovernanceService(
        control_repository=SqliteGovernanceControlRepository(
            SQLiteStateStore(tmp_path / "governance.sqlite3"),
        ),
        industry_service=app.state.industry_service,
    )
    task = KernelTask(
        title="Dispatch governed browser work",
        capability_ref="system:dispatch_command",
        payload={"industry_instance_id": instance_id},
    )

    status = governance.get_status()
    reason = governance.admission_block_reason(task)

    assert status.staffing["active_gap_count"] == 1
    assert status.staffing["pending_confirmation_count"] == 1
    assert decision_id in status.staffing["decision_request_ids"]
    assert reason is not None
    assert "Staffing confirmation is still required" in reason


def test_report_followup_backlog_wins_next_cycle_over_unrelated_open_backlog_when_handoff_and_staffing_are_live(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=(
                "Please publish the customer notice in the browser, "
                "keep the handoff governed, and report back."
            ),
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                "Please publish the customer notice in the browser, keep the handoff governed, and report back.",
                approved_classifications=["backlog"],
                goal_title="Browser publish handoff",
                goal_summary="Publish the customer notice with governed browser handoff.",
                goal_plan_steps=[
                    "Define the governed browser execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence.",
                ],
            ),
        ),
    )
    assert result is not None
    decision_id = result["decision_request_id"]
    assert decision_id is not None
    seed_backlog_id = result["created_backlog_ids"][0]

    unrelated_backlog = app.state.backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=None,
        title="Unrelated urgent cleanup",
        summary="This should not steal the next operating cycle focus from the follow-up item.",
        priority=5,
        source_ref="chat-writeback:unrelated-urgent-cleanup",
        metadata={
            "source": "chat-writeback",
            "report_back_mode": "summary",
        },
    )
    assert unrelated_backlog is not None

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    current_cycle_id = record.current_cycle_id
    assert current_cycle_id is not None

    seed_backlog_record = app.state.backlog_item_repository.get_item(seed_backlog_id)
    assert seed_backlog_record is not None

    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=current_cycle_id,
        backlog_item_id=seed_backlog_id,
        owner_agent_id=result["target_owner_agent_id"],
        owner_role_id=result["target_industry_role_id"],
        title="Browser publish handoff",
        summary="Publish the customer notice with governed browser handoff.",
        status="failed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)
    app.state.backlog_item_repository.upsert_item(
        seed_backlog_record.model_copy(
            update={
                "cycle_id": current_cycle_id,
                "assignment_id": assignment.id,
                "status": "materialized",
            },
        ),
    )

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=current_cycle_id,
        assignment_id=assignment.id,
        owner_agent_id=result["target_owner_agent_id"],
        owner_role_id=result["target_industry_role_id"],
        headline="Browser publish handoff failed",
        summary="The browser publish attempt is still blocked by the unresolved platform handoff.",
        status="recorded",
        result="failed",
        findings=["The platform still requires a governed human handoff before publish can continue."],
        recommendation="Resume the staffed browser seat after the human handoff closes.",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=current_cycle_id,
    )
    assert [item.id for item in processed] == [report.id]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )
    assert followup_backlog["status"] == "open"
    assert followup_backlog["metadata"]["owner_agent_id"] == "copaw-agent-runner"
    assert followup_backlog["metadata"]["industry_role_id"] == "execution-core"
    assert followup_backlog["metadata"]["decision_request_id"] == decision_id
    assert followup_backlog["metadata"]["proposal_status"] == "waiting-confirm"

    class _FakeEnvironmentService:
        def list_sessions(self, limit=200):
            return [
                SimpleNamespace(
                    session_mount_id=f"session:console:industry:{instance_id}",
                ),
            ]

        def get_session_detail(self, session_id, limit=20):
            return {
                "host_twin": {
                    "continuity": {"requires_human_return": True},
                    "ownership": {"handoff_owner_ref": "host-owner"},
                    "coordination": {"recommended_scheduler_action": "handoff"},
                    "legal_recovery": {
                        "path": "handoff",
                        "checkpoint_ref": "host-handoff-checkpoint",
                    },
                },
            }

    human_assist_task_service = HumanAssistTaskService(
        repository=SqliteHumanAssistTaskRepository(app.state.state_store),
        evidence_ledger=app.state.evidence_ledger,
    )
    governance = GovernanceService(
        control_repository=SqliteGovernanceControlRepository(
            SQLiteStateStore(tmp_path / "governance.sqlite3"),
        ),
        industry_service=app.state.industry_service,
        human_assist_task_service=human_assist_task_service,
        environment_service=_FakeEnvironmentService(),
    )
    reason = governance.admission_block_reason(
        KernelTask(
            title="Dispatch governed browser work",
            capability_ref="system:dispatch_command",
            payload={
                "industry_instance_id": instance_id,
                "environment_ref": f"session:console:industry:{instance_id}",
                "chat_thread_id": f"industry-chat:{instance_id}:execution-core",
            },
        ),
    )
    assert reason is not None
    assert "Runtime handoff is active" in reason

    status = governance.get_status()
    assert status.handoff["active"] is True
    assert status.handoff["session_ids"] == [f"session:console:industry:{instance_id}"]
    assert status.human_assist["open_count"] == 1
    assert status.staffing["pending_confirmation_count"] >= 1

    fallback_reason = governance.admission_block_reason(
        KernelTask(
            title="Dispatch governed browser work via control thread fallback",
            capability_ref="system:dispatch_command",
            payload={
                "industry_instance_id": instance_id,
                "session_id": f"industry-chat:{instance_id}:execution-core",
                "control_thread_id": f"industry-chat:{instance_id}:execution-core",
            },
        ),
    )
    assert fallback_reason is not None
    assert "Runtime handoff is active" in fallback_reason

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:followup-priority",
            force=True,
        ),
    )
    assert second_cycle["count"] == 1
    created_assignment_id = second_cycle["processed_instances"][0]["created_assignment_ids"][0]
    created_assignment = app.state.assignment_repository.get_assignment(created_assignment_id)
    assert created_assignment is not None
    assert created_assignment.backlog_item_id == followup_backlog["backlog_item_id"]
    assert created_assignment.owner_agent_id == "copaw-agent-runner"
    assert created_assignment.owner_role_id == "execution-core"

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    assert runtime_payload["execution"]["current_focus_id"] is None
    assert runtime_payload["main_chain"]["current_focus_id"] is None
    assert runtime_payload["execution"]["current_focus"] is None
    assert runtime_payload["main_chain"]["current_focus"] is None
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert "browser" in replan_node["metrics"]["followup_pressure_surfaces"]
    assert replan_node["metrics"]["recommended_action"] is not None


def test_failed_report_followup_uses_supervisor_metadata_without_original_backlog(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep governed browser/desktop follow-up stable"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

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
        title="Specialist browser handoff attempt",
        summary="Try the specialist handoff path without a persisted backlog anchor.",
        status="failed",
        metadata={
            "supervisor_owner_agent_id": "copaw-agent-runner",
            "supervisor_industry_role_id": "execution-core",
            "supervisor_role_name": "Execution Core",
            "chat_writeback_requested_surfaces": ["browser", "desktop"],
            "seat_requested_surfaces": ["browser", "desktop"],
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": environment_ref,
            "recommended_scheduler_action": "handoff",
            "decision_request_id": "decision:staffing-followup",
            "proposal_status": "waiting-confirm",
        },
    )
    app.state.assignment_repository.upsert_assignment(assignment)

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment.id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        headline="Specialist browser handoff failed",
        summary="The specialist handoff remains blocked and needs governed supervisor follow-up.",
        status="recorded",
        result="failed",
        findings=["Browser handoff is still blocked and must return to execution-core supervision."],
        recommendation="Escalate this to the execution-core queue with the same control thread.",
        processed=False,
        work_context_id="work-context:test-supervisor-followup",
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
    metadata = followup_backlog["metadata"]
    assert metadata["supervisor_owner_agent_id"] == "copaw-agent-runner"
    assert metadata["supervisor_industry_role_id"] == "execution-core"
    assert metadata["owner_agent_id"] == "copaw-agent-runner"
    assert metadata["industry_role_id"] == "execution-core"
    assert metadata["control_thread_id"] == control_thread_id
    assert metadata["session_id"] == control_thread_id
    assert metadata["environment_ref"] == environment_ref
    assert metadata["recommended_scheduler_action"] == "handoff"
    assert metadata["work_context_id"] == report.work_context_id
    assert "browser" in metadata["seat_requested_surfaces"]
    assert "desktop" in metadata["seat_requested_surfaces"]


def test_researcher_followup_assignment_persists_execution_core_continuity_without_backlog_anchor(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep researcher follow-up continuity stable across cycle materialization"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    instance_id = payload["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"

    researcher_schedule_id = next(
        item["schedule_id"]
        for item in payload["schedules"]
        if item["schedule"]["spec_payload"]["request"]["industry_role_id"] == "researcher"
    )
    schedule = app.state.schedule_repository.get_schedule(researcher_schedule_id)
    assert schedule is not None

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    cycle_id = record.current_cycle_id
    assert cycle_id is not None

    first_report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=None,
        owner_agent_id=schedule.spec_payload["meta"]["owner_agent_id"],
        owner_role_id="researcher",
        headline="Researcher schedule found another escalation signal",
        summary="Research cadence surfaced a follow-up that should stay on the main-brain control thread.",
        status="recorded",
        result="failed",
        findings=["A governed follow-up is still required on the execution-core thread."],
        recommendation="Route the next step back through the formal execution-core continuity.",
        processed=False,
        work_context_id="ctx-researcher-followup-assignment-1",
        metadata=dict(schedule.spec_payload.get("meta") or {}),
    )
    app.state.agent_report_repository.upsert_report(first_report)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=cycle_id,
    )
    assert [item.id for item in processed] == [first_report.id]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == first_report.id
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:researcher-followup-materialize",
            force=True,
            backlog_item_ids=[followup_backlog["backlog_item_id"]],
            auto_dispatch_materialized_goals=False,
        ),
    )
    created_assignment_ids = cycle_result["processed_instances"][0]["created_assignment_ids"]
    assert created_assignment_ids
    assignment = app.state.assignment_repository.get_assignment(created_assignment_ids[0])
    assert assignment is not None
    assert assignment.metadata["control_thread_id"] == control_thread_id
    assert assignment.metadata["session_id"] == control_thread_id
    assert assignment.metadata["environment_ref"] == environment_ref
    assert assignment.metadata["work_context_id"] == "ctx-researcher-followup-assignment-1"
    assert assignment.metadata["owner_agent_id"] == "copaw-agent-runner"
    assert assignment.metadata["industry_role_id"] == "execution-core"
    assert assignment.metadata["recommended_scheduler_action"] == "continue"

    app.state.assignment_repository.upsert_assignment(
        assignment.model_copy(update={"backlog_item_id": None}),
    )
    updated_record = app.state.industry_instance_repository.get_instance(instance_id)
    assert updated_record is not None
    updated_cycle_id = updated_record.current_cycle_id
    assert updated_cycle_id is not None

    second_report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=updated_cycle_id,
        assignment_id=assignment.id,
        owner_agent_id=assignment.owner_agent_id,
        owner_role_id=assignment.owner_role_id,
        headline="Researcher follow-up still needs execution-core routing",
        summary="The materialized follow-up assignment still routes back through execution-core.",
        status="recorded",
        result="failed",
        findings=["The second follow-up must keep the same execution-core continuity."],
        recommendation="Keep the follow-up on the same control thread even without the original backlog anchor.",
        processed=False,
        work_context_id="ctx-researcher-followup-assignment-2",
        metadata=dict(assignment.metadata or {}),
    )
    app.state.agent_report_repository.upsert_report(second_report)

    processed_again = app.state.industry_service._process_pending_agent_reports(
        record=updated_record,
        cycle_id=updated_cycle_id,
    )
    assert [item.id for item in processed_again] == [second_report.id]

    refreshed_detail = app.state.industry_service.get_instance_detail(instance_id)
    assert refreshed_detail is not None
    second_followup_backlog = next(
        item
        for item in refreshed_detail.backlog
        if item["metadata"].get("source_report_id") == second_report.id
    )
    metadata = second_followup_backlog["metadata"]
    assert metadata["control_thread_id"] == control_thread_id
    assert metadata["session_id"] == control_thread_id
    assert metadata["environment_ref"] == environment_ref
    assert metadata["work_context_id"] == "ctx-researcher-followup-assignment-2"
    assert metadata["owner_agent_id"] == "copaw-agent-runner"
    assert metadata["industry_role_id"] == "execution-core"
    assert metadata["recommended_scheduler_action"] == "continue"


def test_runtime_replan_node_persists_previous_cycle_synthesis_after_rollover(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep report synthesis continuity after cycle rollover"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    original_cycle_id = record.current_cycle_id
    assert original_cycle_id is not None

    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=original_cycle_id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        title="Rollover synthesis continuity check",
        summary="Create a failed report to seed replan synthesis.",
        status="failed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=original_cycle_id,
        assignment_id=assignment.id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        headline="Rollover synthesis continuity failed",
        summary="The failed report should keep replan visible after cycle rollover.",
        status="recorded",
        result="failed",
        findings=["A governed follow-up is still required."],
        recommendation="Keep replan pressure visible until follow-up is dispatched.",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=original_cycle_id,
    )
    assert [item.id for item in processed] == [report.id]

    original_cycle = app.state.operating_cycle_repository.get_cycle(original_cycle_id)
    assert original_cycle is not None
    assert (original_cycle.metadata or {}).get("report_synthesis", {}).get("needs_replan") is True

    rollover_cycle = app.state.operating_cycle_service.start_cycle(
        industry_instance_id=instance_id,
        label=record.label,
        cycle_kind="daily",
        status="active",
        focus_lane_ids=[],
        backlog_item_ids=[],
        source_ref="test:cycle-rollover",
        summary="Rollover cycle without direct synthesis metadata.",
        metadata={},
    )
    app.state.industry_instance_repository.upsert_instance(
        record.model_copy(
            update={
                "current_cycle_id": rollover_cycle.id,
                "updated_at": rollover_cycle.updated_at,
            },
        ),
    )

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert replan_node["status"] == "active"
    assert replan_node["current_ref"] == original_cycle_id
    assert replan_node["metrics"]["needs_replan"] is True
    assert replan_node["metrics"]["replan_reason_count"] >= 1
    assert any(
        "requires main-brain follow-up" in reason
        for reason in replan_node["metrics"]["replan_reasons"]
    )


def test_runtime_updates_expose_activation_summary_on_current_cycle_surface(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep activation summary visible after cycle rollover"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    original_cycle_id = record.current_cycle_id
    assert original_cycle_id is not None

    original_cycle = app.state.operating_cycle_repository.get_cycle(original_cycle_id)
    assert original_cycle is not None
    activation_summary = {
        "top_constraints": [
            "Keep the failed staffing contradiction visible until the next governed follow-up.",
        ],
        "top_next_actions": [
            "Validate the contradiction before expanding the specialist seat.",
        ],
        "support_refs": ["activation:support:staffing-contradiction"],
        "contradiction_count": 1,
    }
    app.state.operating_cycle_repository.upsert_cycle(
        original_cycle.model_copy(
            update={
                "metadata": {
                    **dict(original_cycle.metadata or {}),
                    "report_synthesis": {
                        "needs_replan": True,
                        "replan_reasons": [
                            "Activation contradiction still requires main-brain follow-up.",
                        ],
                        "activation": activation_summary,
                    },
                },
            },
        ),
    )

    rollover_cycle = app.state.operating_cycle_service.start_cycle(
        industry_instance_id=instance_id,
        label=record.label,
        cycle_kind="daily",
        status="active",
        focus_lane_ids=[],
        backlog_item_ids=[],
        source_ref="test:activation-cycle-rollover",
        summary="Rollover cycle without direct activation summary.",
        metadata={},
    )
    app.state.industry_instance_repository.upsert_instance(
        record.model_copy(
            update={
                "current_cycle_id": rollover_cycle.id,
                "updated_at": rollover_cycle.updated_at,
            },
        ),
    )

    detail = app.state.industry_service.get_instance_detail(instance_id)

    assert detail is not None
    assert detail.current_cycle is not None
    assert detail.current_cycle["cycle_id"] == rollover_cycle.id
    assert detail.current_cycle["synthesis"]["activation"] == activation_summary


def test_runtime_updates_keep_replan_focus_and_activation_summary_together(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep replan focus and activation summary aligned"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    original_cycle_id = record.current_cycle_id
    assert original_cycle_id is not None

    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=original_cycle_id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        title="Activation runtime continuity check",
        summary="Create a failed report to keep replan focused on the prior cycle.",
        status="failed",
    )
    app.state.assignment_repository.upsert_assignment(assignment)

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=original_cycle_id,
        assignment_id=assignment.id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        headline="Activation runtime continuity failed",
        summary="The failed report should keep replan focused on the prior cycle.",
        status="recorded",
        result="failed",
        findings=["A governed follow-up is still required."],
        recommendation="Keep replan pressure visible until follow-up is dispatched.",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=original_cycle_id,
    )
    assert [item.id for item in processed] == [report.id]

    original_cycle = app.state.operating_cycle_repository.get_cycle(original_cycle_id)
    assert original_cycle is not None
    original_synthesis = dict((original_cycle.metadata or {}).get("report_synthesis") or {})
    app.state.operating_cycle_repository.upsert_cycle(
        original_cycle.model_copy(
            update={
                "metadata": {
                    **dict(original_cycle.metadata or {}),
                    "report_synthesis": {
                        **original_synthesis,
                        "activation": {
                            "top_constraints": [
                                "Do not clear the contradiction until the supervised retry runs.",
                            ],
                            "top_next_actions": [
                                "Run the supervised retry before dispatching another seat.",
                            ],
                            "support_refs": [
                                "activation:support:supervised-retry",
                            ],
                            "contradiction_count": 1,
                        },
                    },
                },
            },
        ),
    )

    rollover_cycle = app.state.operating_cycle_service.start_cycle(
        industry_instance_id=instance_id,
        label=record.label,
        cycle_kind="daily",
        status="active",
        focus_lane_ids=[],
        backlog_item_ids=[],
        source_ref="test:activation-runtime-rollover",
        summary="Rollover cycle without direct activation summary.",
        metadata={},
    )
    app.state.industry_instance_repository.upsert_instance(
        record.model_copy(
            update={
                "current_cycle_id": rollover_cycle.id,
                "updated_at": rollover_cycle.updated_at,
            },
        ),
    )

    payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    replan_node = next(
        node for node in payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )

    assert replan_node["current_ref"] == original_cycle_id
    assert payload["main_chain"]["nodes"]
    assert payload["current_cycle"]["synthesis"]["activation"]["contradiction_count"] >= 0
    assert payload["current_cycle"]["synthesis"]["activation"]["top_constraints"] == [
        "Do not clear the contradiction until the supervised retry runs.",
    ]


def test_main_brain_cognitive_surface_persists_across_rollover_and_clears_after_resolved_followup(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep main-brain cognitive closure stable across rollover"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    original_cycle_id = record.current_cycle_id
    assert original_cycle_id is not None

    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"
    assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=original_cycle_id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        title="Rollover cognitive continuity check",
        summary="Create unresolved follow-up pressure before rollover.",
        status="failed",
        metadata={
            "supervisor_owner_agent_id": "copaw-agent-runner",
            "supervisor_industry_role_id": "execution-core",
            "supervisor_role_name": "Execution Core",
            "seat_requested_surfaces": ["browser"],
            "chat_writeback_requested_surfaces": ["browser"],
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": environment_ref,
            "recommended_scheduler_action": "handoff",
        },
    )
    app.state.assignment_repository.upsert_assignment(assignment)

    failed_report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=original_cycle_id,
        assignment_id=assignment.id,
        owner_agent_id="support-specialist-agent",
        owner_role_id="support-specialist",
        headline="Rollover cognitive continuity failed",
        summary="The failed report should keep main-brain pressure visible after rollover.",
        status="recorded",
        result="failed",
        findings=["A governed follow-up is still required."],
        recommendation="Keep replan pressure visible until the governed follow-up closes.",
        processed=False,
        work_context_id="work-context:test-rollover-cognitive-surface",
    )
    app.state.agent_report_repository.upsert_report(failed_report)

    processed = app.state.industry_service._process_pending_agent_reports(
        record=record,
        cycle_id=original_cycle_id,
    )
    assert [item.id for item in processed] == [failed_report.id]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == failed_report.id
    )

    rollover_cycle = app.state.operating_cycle_service.start_cycle(
        industry_instance_id=instance_id,
        label=record.label,
        cycle_kind="daily",
        status="active",
        focus_lane_ids=[],
        backlog_item_ids=[],
        source_ref="test:cognitive-rollover",
        summary="Rollover cycle without direct synthesis metadata.",
        metadata={},
    )
    rolled_record = app.state.industry_instance_repository.upsert_instance(
        record.model_copy(
            update={
                "current_cycle_id": rollover_cycle.id,
                "updated_at": rollover_cycle.updated_at,
            },
        ),
    )

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    cognitive_surface = runtime_payload["current_cycle"]["main_brain_cognitive_surface"]
    planning_surface = runtime_payload["main_brain_planning"]
    assert cognitive_surface["needs_replan"] is True
    assert cognitive_surface["latest_reports"][0]["report_id"] == failed_report.id
    assert cognitive_surface["followup_backlog"][0]["backlog_item_id"] == followup_backlog["backlog_item_id"]
    assert cognitive_surface["judgment"]["status"] == "replan-required"
    assert cognitive_surface["continuity"]["work_context_ids"] == [failed_report.work_context_id]
    assert cognitive_surface["continuity"]["control_thread_ids"] == [control_thread_id]
    assert cognitive_surface["continuity"]["environment_refs"] == [environment_ref]
    assert planning_surface["replan"]["status"] == "needs-replan"
    assert planning_surface["replan"]["source_report_ids"] == [failed_report.id]
    assert runtime_payload["current_cycle"]["main_brain_planning"] == planning_surface

    followup_assignment = AssignmentRecord(
        industry_instance_id=instance_id,
        cycle_id=rollover_cycle.id,
        backlog_item_id=followup_backlog["backlog_item_id"],
        owner_agent_id="copaw-agent-runner",
        owner_role_id="execution-core",
        title=followup_backlog["title"],
        summary=followup_backlog["summary"],
        status="completed",
    )
    app.state.assignment_repository.upsert_assignment(followup_assignment)
    app.state.backlog_item_repository.upsert_item(
        app.state.backlog_item_repository.get_item(followup_backlog["backlog_item_id"]).model_copy(
            update={
                "cycle_id": rollover_cycle.id,
                "assignment_id": followup_assignment.id,
                "status": "materialized",
            },
        ),
    )

    resolved_report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=rollover_cycle.id,
        assignment_id=followup_assignment.id,
        owner_agent_id="copaw-agent-runner",
        owner_role_id="execution-core",
        headline="Rollover cognitive continuity resolved",
        summary="The follow-up closed the prior governed handoff pressure.",
        status="recorded",
        result="completed",
        findings=["The governed follow-up closed the prior handoff pressure."],
        recommendation="Resume the standard operating cycle.",
        processed=False,
        work_context_id=failed_report.work_context_id,
    )
    app.state.agent_report_repository.upsert_report(resolved_report)

    resolved = app.state.industry_service._process_pending_agent_reports(
        record=rolled_record,
        cycle_id=rollover_cycle.id,
    )
    assert [item.id for item in resolved] == [resolved_report.id]

    cleared_runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    cleared_surface = cleared_runtime_payload["current_cycle"]["main_brain_cognitive_surface"]
    cleared_planning = cleared_runtime_payload["main_brain_planning"]
    assert cleared_surface["needs_replan"] is False
    assert cleared_surface["replan_reasons"] == []
    assert cleared_surface["followup_backlog"] == []
    assert cleared_surface["judgment"]["status"] == "stable"
    assert cleared_surface["next_action"]["kind"] == "continue-cycle"
    assert cleared_planning["replan"]["status"] == "clear"
    assert cleared_runtime_payload["current_cycle"]["main_brain_planning"] == cleared_planning

    strategy = app.state.strategy_memory_service.get_active_strategy(
        scope_type="industry",
        scope_id=instance_id,
        owner_agent_id="copaw-agent-runner",
    )
    assert strategy is not None
    strategy_surface = strategy.metadata["main_brain_cognitive_surface"]
    assert strategy_surface["needs_replan"] is False
    assert strategy_surface["followup_backlog"] == []


def test_industry_chat_writeback_updates_priority_without_duplicate_history(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="operator copilots",
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    first = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text="\u6539\u6210\u5148\u505a\u73b0\u573a\u9a8c\u8bc1\u518d\u505a\u89c4\u6a21\u590d\u5236",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=_build_test_chat_writeback_plan(
                "\u6539\u6210\u5148\u505a\u73b0\u573a\u9a8c\u8bc1\u518d\u505a\u89c4\u6a21\u590d\u5236"
            ),
        ),
    )
    second = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text="\u6539\u6210\u5148\u505a\u73b0\u573a\u9a8c\u8bc1\u518d\u505a\u89c4\u6a21\u590d\u5236",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=_build_test_chat_writeback_plan(
                "\u6539\u6210\u5148\u505a\u73b0\u573a\u9a8c\u8bc1\u518d\u505a\u89c4\u6a21\u590d\u5236"
            ),
        ),
    )

    strategy = app.state.strategy_memory_service.get_active_strategy(
        scope_type="industry",
        scope_id=instance_id,
        owner_agent_id="copaw-agent-runner",
    )
    assert first is not None
    assert second is not None
    assert strategy is not None
    assert strategy.priority_order[:2] == ["\u5148\u505a\u73b0\u573a\u9a8c\u8bc1", "\u518d\u505a\u89c4\u6a21\u590d\u5236"]
    assert first["strategy_updated"] is True
    assert second["applied"] is False
    assert strategy.metadata["operator_requirements"].count("\u6539\u6210\u5148\u505a\u73b0\u573a\u9a8c\u8bc1\u518d\u505a\u89c4\u6a21\u590d\u5236") == 1
    assert len(
        [
            item
            for item in strategy.metadata["chat_writeback_history"]
            if item["fingerprint"] == first["fingerprint"]
        ]
    ) == 1


def test_industry_chat_writeback_supports_generic_workday_schedule(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Services",
            company_name="Northwind Robotics",
            product="field coordination",
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text="\u628a\u73b0\u573a\u5de1\u68c0\u7eb3\u5165\u957f\u671f\u8282\u594f\uff0c\u5de5\u4f5c\u65e5\u6267\u884c\u4e00\u6b21",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=_build_test_chat_writeback_plan(
                "\u628a\u73b0\u573a\u5de1\u68c0\u7eb3\u5165\u957f\u671f\u8282\u594f\uff0c\u5de5\u4f5c\u65e5\u6267\u884c\u4e00\u6b21"
            ),
        ),
    )

    assert result is not None
    schedule = app.state.schedule_repository.get_schedule(
        result["created_schedule_ids"][0],
    )
    assert schedule is not None
    assert schedule.cron == "0 9 * * 1-5"


def test_industry_chat_writeback_uses_supplied_plan_without_reparsing(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)
    owner_scope = "industry-v1-northwind-robotics"

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        owner_scope,
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    approved_plan = _build_test_chat_writeback_plan(
        "must include market research and competitor monitoring in the main loop, weekly review"
    )
    assert approved_plan is not None
    assert approved_plan.active is True

    result = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text="hello",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=approved_plan,
        ),
    )

    assert result is not None
    assert result["applied"] is True
    assert result["fingerprint"] == approved_plan.fingerprint
    assert result["created_goal_ids"] == []
    assert len(result["created_schedule_ids"]) == 1


def test_industry_instance_summary_backfills_execution_core_role_from_agent_profiles(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    request = IndustryPreviewRequest(
        industry="Industrial Equipment",
        company_name="Northwind Robotics",
        product="factory monitoring copilots",
        goals=["launch two pilot deployments"],
    )
    profile = normalize_industry_profile(request)
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        owner_scope="industry-v1-northwind-robotics",
    )

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    app.state.industry_instance_repository.upsert_instance(
        record.model_copy(
            update={
                "team_payload": {
                    "schema_version": "industry-team-blueprint-v1",
                    "team_id": instance_id,
                    "label": record.label,
                    "summary": record.summary,
                    "agents": [],
                }
            }
        )
    )

    summaries = client.get("/industry/v1/instances")
    assert summaries.status_code == 200
    summary = summaries.json()[0]
    execution_core = next(
        role
        for role in summary["team"]["agents"]
        if role["role_id"] == "execution-core"
    )
    assert execution_core["agent_id"] == "copaw-agent-runner"
    assert summary["execution_core_identity"]["agent_id"] == "copaw-agent-runner"
    assert summary["execution_core_identity"]["role_id"] == "execution-core"
    assert execution_core["role_name"]


def test_industry_instance_status_reconciles_from_goal_states(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    goal = app.state.goal_service.create_goal(
        title="Completed goal",
        summary="The work is done.",
        status="completed",
        owner_scope="industry-v1-northwind-robotics",
    )
    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-northwind-robotics",
            label="Northwind Robotics",
            summary="Test instance",
            owner_scope="industry-v1-northwind-robotics",
            status="active",
            profile_payload={"industry": "Industrial Equipment"},
            team_payload={},
            goal_ids=[goal.id],
            agent_ids=[],
            schedule_ids=[],
        ),
    )

    record = app.state.industry_service.get_instance_record("industry-v1-northwind-robotics")

    assert record is not None
    assert record.status == "active"

    reconciled = app.state.industry_service.reconcile_instance_status(
        "industry-v1-northwind-robotics",
    )

    assert reconciled is not None
    assert reconciled.status == "completed"
    assert (
        app.state.industry_service.get_instance_record("industry-v1-northwind-robotics").status
        == "completed"
    )


def test_industry_instance_status_completes_with_static_team_membership_only(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    goal = app.state.goal_service.create_goal(
        title="Completed staffed goal",
        summary="The staffed team finished the work.",
        status="completed",
        owner_scope="industry-v1-staffed",
    )
    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-staffed",
            label="Staffed Ops Cell",
            summary="Static team membership should not keep the instance active.",
            owner_scope="industry-v1-staffed",
            status="active",
            profile_payload={"industry": "Operations"},
            team_payload={
                "schema_version": "industry-team-blueprint-v1",
                "team_id": "industry-v1-staffed",
                "label": "Staffed Ops Cell",
                "summary": "Static team membership should not keep the instance active.",
                "agents": [
                    {
                        "role_id": "execution-core",
                        "agent_id": "copaw-agent-runner",
                        "name": "Execution Core",
                        "role_name": "Execution Core",
                    },
                    {
                        "role_id": "researcher",
                        "agent_id": "staffed-researcher",
                        "name": "Research Specialist",
                        "role_name": "Research Specialist",
                    },
                ],
            },
            goal_ids=[goal.id],
            agent_ids=["copaw-agent-runner", "staffed-researcher"],
            schedule_ids=[],
        ),
    )

    record = app.state.industry_service.get_instance_record("industry-v1-staffed")

    assert record is not None
    assert record.status == "active"

    reconciled = app.state.industry_service.reconcile_instance_status("industry-v1-staffed")

    assert reconciled is not None
    assert reconciled.status == "completed"
    assert app.state.industry_service.get_instance_record("industry-v1-staffed").status == (
        "completed"
    )

def test_industry_detail_backfills_execution_core_identity_with_delegation_first_defaults(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)

    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-fallback",
            label="Fallback Ops Cell",
            summary="Fallback identity detail.",
            owner_scope="industry-v1-fallback",
            status="active",
            profile_payload={"industry": "Operations"},
            team_payload={
                "schema_version": "industry-team-blueprint-v1",
                "team_id": "industry-v1-fallback",
                "label": "Fallback Ops Cell",
                "summary": "Fallback identity detail.",
                "agents": [
                    {
                        "schema_version": "industry-role-blueprint-v1",
                        "role_id": "execution-core",
                        "agent_id": "copaw-agent-runner",
                        "name": "Execution Core",
                        "role_name": "Execution Core",
                        "role_summary": "",
                        "mission": "",
                        "goal_kind": "execution-core",
                        "agent_class": "business",
                        "activation_mode": "persistent",
                        "suspendable": False,
                        "risk_level": "guarded",
                        "environment_constraints": [],
                        "allowed_capabilities": ["system:dispatch_query"],
                        "evidence_expectations": [],
                    },
                    {
                        "schema_version": "industry-role-blueprint-v1",
                        "role_id": "solution-lead",
                        "agent_id": "fallback-solution-lead",
                        "name": "Fallback Solution Lead",
                        "role_name": "Solution Lead",
                        "role_summary": "Shapes the next rollout design.",
                        "mission": "Turn the brief into a rollout-ready solution.",
                        "goal_kind": "solution",
                        "agent_class": "business",
                        "activation_mode": "persistent",
                        "suspendable": False,
                        "reports_to": "execution-core",
                        "risk_level": "guarded",
                        "environment_constraints": [],
                        "allowed_capabilities": ["system:dispatch_query"],
                        "evidence_expectations": [],
                    },
                ],
            },
            goal_ids=[],
            agent_ids=["copaw-agent-runner", "fallback-solution-lead"],
            schedule_ids=[],
        ),
    )

    detail = app.state.industry_service.get_instance_detail("industry-v1-fallback")

    assert detail is not None
    assert detail.execution_core_identity.role_summary
    assert detail.execution_core_identity.role_summary == detail.team.agents[0].role_summary
    assert "亲自执行" not in detail.execution_core_identity.role_summary
    assert detail.execution_core_identity.mission
    assert detail.execution_core_identity.mission == detail.team.agents[0].mission
    assert "亲自执行" not in detail.execution_core_identity.mission
    assert detail.execution_core_identity.operating_mode == "control-core"
    assert detail.execution_core_identity.delegation_policy
    assert detail.execution_core_identity.direct_execution_policy
    assert all(
        "亲自执行" not in item
        for item in detail.execution_core_identity.direct_execution_policy
    )


