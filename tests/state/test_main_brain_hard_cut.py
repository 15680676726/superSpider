# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from copaw.industry import IndustryPreviewRequest, normalize_industry_profile
from copaw.state import IndustryInstanceRecord, OperatingCycleRecord
from tests.app.industry_api_parts.runtime_updates import _build_test_chat_writeback_plan
from tests.app.industry_api_parts.shared import FakeIndustryDraftGenerator, _build_industry_app


def test_apply_execution_chat_writeback_keeps_matched_work_in_backlog_until_cycle(
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
    assert result["created_goal_ids"] == []
    assert result["goal_dispatches"] == []
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
    assert backlog_item.assignment_id is None
    assert backlog_item.status == "open"


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
