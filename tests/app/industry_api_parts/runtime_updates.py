# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403
from copaw.industry.chat_writeback import build_chat_writeback_plan


def test_industry_service_facade_reads_runtime_detail_from_view_service() -> None:
    service = IndustryService.__new__(IndustryService)
    detail = {"current_cycle": {"cycle_id": "cycle-1"}, "backlog": [{"id": "b-1"}]}
    service._view_service = SimpleNamespace(
        get_instance_detail=lambda instance_id: detail if instance_id == "industry-1" else None,
    )

    assert service.get_instance_detail("industry-1") is detail


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

    compiled = client.post(f"/goals/{specialist_goal_id}/compile", json={})

    assert compiled.status_code == 200
    payload = compiled.json()[0]["payload"]
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
    assert selected_override.current_goal_id in set(record.goal_ids or [])
    assert selected_override.current_goal

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
    assert record.status == "completed"


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
    assert record.status == "completed"

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
    assert any(
        "补位" in item or "临时位" in item or "提案" in item
        for item in detail.execution_core_identity.direct_execution_policy
    )


