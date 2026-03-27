# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.state import GoalRecord, SQLiteStateStore, TaskRecord, TaskRuntimeRecord
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def _build_client(tmp_path) -> TestClient:
    app = FastAPI()
    store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    schedule_repository = SqliteScheduleRepository(store)
    goal_repository = SqliteGoalRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    goal_repository.upsert_goal(
        GoalRecord(
            id="goal-1",
            title="Delegated execution",
            summary="Track parent-child task relationships.",
            status="active",
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-parent",
            goal_id="goal-1",
            title="Execution core task",
            summary="Split the work.",
            task_type="analysis",
            status="running",
            owner_agent_id="execution-core-agent",
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-child",
            goal_id="goal-1",
            title="Worker task",
            summary="Do the delegated work.",
            task_type="analysis",
            status="queued",
            owner_agent_id="worker",
            parent_task_id="task-parent",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-parent",
            runtime_status="active",
            current_phase="delegating",
            last_owner_agent_id="execution-core-agent",
        ),
    )
    app.state.state_query_service = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        schedule_repository=schedule_repository,
        goal_repository=goal_repository,
        decision_request_repository=decision_repository,
    )
    app.include_router(runtime_center_router)
    return TestClient(app)


def test_runtime_center_task_detail_exposes_parent_child_relationships(tmp_path) -> None:
    client = _build_client(tmp_path)

    listing = client.get("/runtime-center/tasks")
    assert listing.status_code == 200
    items = {item["id"]: item for item in listing.json()}
    assert items["task-parent"]["child_task_count"] == 1
    assert items["task-parent"]["parent_task_id"] is None
    assert items["task-child"]["parent_task_id"] == "task-parent"
    assert items["task-child"]["child_task_count"] == 0

    response = client.get("/runtime-center/tasks/task-parent")
    assert response.status_code == 200
    payload = response.json()
    assert payload["parent_task"] is None
    assert payload["stats"]["child_task_count"] == 1
    assert payload["child_tasks"][0]["id"] == "task-child"
    assert payload["child_tasks"][0]["route"] == "/api/runtime-center/tasks/task-child"
