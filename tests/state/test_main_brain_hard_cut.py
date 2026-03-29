# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from copaw.industry import IndustryPreviewRequest, normalize_industry_profile
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
    initial_goal_count = len(record_before.goal_ids or [])

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
    assert len(record_after.goal_ids or []) == initial_goal_count

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
