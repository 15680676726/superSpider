# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from copaw.industry import IndustryPreviewRequest, normalize_industry_profile
from copaw.state import (
    AssignmentRecord,
    AssignmentService,
    GoalRecord,
    IndustryInstanceRecord,
    OperatingCycleRecord,
    SQLiteStateStore,
)
from copaw.state.repositories import (
    SqliteAssignmentRepository,
    SqliteGoalRepository,
    SqliteIndustryInstanceRepository,
)
from tests.app.industry_api_parts.runtime_updates import _build_test_chat_writeback_plan
from tests.app.industry_api_parts.shared import FakeIndustryDraftGenerator, _build_industry_app


def test_apply_execution_chat_writeback_materializes_matched_work_without_legacy_goal(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="operator copilots",
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

    record_before = app.state.industry_instance_repository.get_instance(instance_id)
    assert record_before is not None
    initial_goal_count = len(
        app.state.goal_service.list_goals(industry_instance_id=instance_id),
    )

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
    assert result["created_backlog_ids"]
    assert "created_goal_ids" not in result
    assert "goal_dispatches" not in result
    assert result["delegated"] is False
    assert result["dispatch_deferred"] is True

    record_after = app.state.industry_instance_repository.get_instance(instance_id)
    assert record_after is not None
    assert len(app.state.goal_service.list_goals(industry_instance_id=instance_id)) == (
        initial_goal_count
    )

    backlog_item = app.state.backlog_item_repository.get_item(result["created_backlog_ids"][0])
    assert backlog_item is not None
    assert backlog_item.goal_id is None
    assert result["materialized_assignment_ids"]
    assert result["delegation_state"] == "materialized"
    assert backlog_item.assignment_id == result["materialized_assignment_ids"][0]
    assert backlog_item.status == "materialized"


def test_runtime_center_delegate_endpoint_is_removed_after_hard_cut(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/runtime-center/tasks/task-1/delegate",
        json={
            "title": "Worker follow-up",
            "owner_agent_id": "worker",
            "prompt_text": "Review the evidence and draft the next step.",
        },
    )

    assert response.status_code == 404


def test_runtime_center_goal_dispatch_endpoint_is_removed_after_hard_cut(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/runtime-center/goals/goal-1/dispatch",
        json={
            "trigger": "manual",
            "source": "runtime-center",
        },
    )

    assert response.status_code == 404


def test_runtime_center_retired_frontdoors_stay_removed_after_hard_cut(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    retired_routes = [
        (
            "/runtime-center/chat/intake",
            {
                "id": "req-intake",
                "session_id": "industry-chat:industry-v1-ops:execution-core",
                "user_id": "ops-user",
                "channel": "console",
                "input": [
                    {
                        "role": "user",
                        "type": "message",
                        "content": [{"type": "text", "text": "开始执行并给我结果"}],
                    }
                ],
            },
        ),
        (
            "/runtime-center/chat/orchestrate",
            {
                "id": "req-orchestrate",
                "session_id": "industry-chat:industry-v1-ops:execution-core",
                "user_id": "ops-user",
                "channel": "console",
                "input": [
                    {
                        "role": "user",
                        "type": "message",
                        "content": [{"type": "text", "text": "开始执行并给我结果"}],
                    }
                ],
                "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
            },
        ),
        (
            "/runtime-center/tasks/task-1/delegate",
            {
                "title": "Worker follow-up",
                "owner_agent_id": "worker",
                "prompt_text": "Review the evidence and draft the next step.",
            },
        ),
        (
            "/runtime-center/goals/goal-1/dispatch",
            {
                "trigger": "manual",
                "source": "runtime-center",
            },
        ),
    ]

    for route, payload in retired_routes:
        response = client.post(route, json=payload)
        assert response.status_code == 404, route


def test_operating_cycle_reconcile_uses_assignment_truth_only_after_hard_cut(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-hard-cut",
            label="Hard Cut Industry",
            summary="Cycle reconcile should no longer depend on legacy goal statuses.",
            owner_scope="industry-hard-cut",
            status="active",
            lifecycle_status="running",
            autonomy_status="coordinating",
            profile_payload={},
            team_payload={},
            agent_ids=[],
        ),
    )

    cycle = app.state.operating_cycle_repository.upsert_cycle(
        OperatingCycleRecord(
            id="cycle:hard-cut:assignment-only",
            industry_instance_id="industry-hard-cut",
            cycle_kind="daily",
            title="Assignment-only cycle",
            summary="Cycle status should reconcile from assignment truth only.",
            status="active",
            focus_lane_ids=[],
            backlog_item_ids=[],
            assignment_ids=["assignment-1"],
            report_ids=[],
        ),
    )

    reconciled = app.state.operating_cycle_service.reconcile_cycle(
        cycle,
        assignment_statuses=["completed"],
        report_ids=[],
    )

    assert reconciled.status == "completed"


def test_assignment_reconcile_does_not_derive_live_status_from_goal_status(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "assignment-reconcile.sqlite3")
    industry_repository = SqliteIndustryInstanceRepository(state_store)
    goal_repository = SqliteGoalRepository(state_store)
    repository = SqliteAssignmentRepository(state_store)
    service = AssignmentService(repository=repository)
    industry_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-hard-cut",
            label="Hard Cut Industry",
            owner_scope="industry-hard-cut",
        ),
    )
    goal_repository.upsert_goal(
        GoalRecord(
            id="goal-legacy-blocked",
            title="Legacy blocked goal",
            summary="Legacy goal status should not drive assignment live status.",
            status="blocked",
            industry_instance_id="industry-hard-cut",
        ),
    )
    repository.upsert_assignment(
        AssignmentRecord(
            id="assignment-goal-decoupled",
            industry_instance_id="industry-hard-cut",
            goal_id="goal-legacy-blocked",
            title="Keep assignment truth independent",
            summary="Assignment status should stay on assignment/task/report truth.",
            status="planned",
        ),
    )

    reconciled = service.reconcile_assignments(
        industry_instance_id="industry-hard-cut",
        cycle_id=None,
        goals_by_id={
            "goal-legacy-blocked": GoalRecord(
                id="goal-legacy-blocked",
                title="Legacy blocked goal",
                summary="Legacy goal status should not drive assignment live status.",
                status="blocked",
            ),
        },
        tasks_by_assignment_id={},
        latest_reports_by_assignment_id={},
    )

    assert len(reconciled) == 1
    assert reconciled[0].status == "planned"
