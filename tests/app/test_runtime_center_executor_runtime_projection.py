# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.state import ExternalCapabilityRuntimeService, SQLiteStateStore
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteExternalCapabilityRuntimeRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def _build_query_service(tmp_path) -> tuple[RuntimeCenterStateQueryService, ExecutorRuntimeService, ExternalCapabilityRuntimeService]:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repository = SqliteExternalCapabilityRuntimeRepository(state_store)
    external_runtime_service = ExternalCapabilityRuntimeService(repository=runtime_repository)
    executor_runtime_service = ExecutorRuntimeService(
        external_runtime_service=external_runtime_service,
    )
    query_service = RuntimeCenterStateQueryService(
        task_repository=SqliteTaskRepository(state_store),
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        runtime_frame_repository=SqliteRuntimeFrameRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        decision_request_repository=SqliteDecisionRequestRepository(state_store),
        external_runtime_service=external_runtime_service,
        executor_runtime_service=executor_runtime_service,
    )
    return query_service, executor_runtime_service, external_runtime_service


def test_runtime_center_list_external_runtimes_prefers_executor_runtime_truth(tmp_path) -> None:
    query_service, executor_runtime_service, external_runtime_service = _build_query_service(tmp_path)
    executor_runtime = executor_runtime_service.create_or_reuse_runtime(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
        role_id="backend-engineer",
        project_profile_id="carrier-main",
    )
    executor_runtime_service.mark_runtime_ready(
        executor_runtime.runtime_id,
        thread_id="thread-1",
        metadata={"turn_id": "turn-1"},
    )
    external_runtime_service.create_or_reuse_service_runtime(
        capability_id="runtime:legacy-flask",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="python -m flask run",
    )

    payload = query_service.list_external_runtimes()

    assert len(payload) == 1
    assert payload[0]["runtime_id"] == executor_runtime.runtime_id
    assert payload[0]["kind"] == "executor-runtime"
    assert payload[0]["executor_id"] == "codex"
    assert payload[0]["status"] == "ready"
    assert payload[0]["route"] == f"/api/runtime-center/external-runtimes/{executor_runtime.runtime_id}"
    assert "capability_id" not in payload[0]


def test_runtime_center_external_runtime_detail_returns_executor_runtime_projection(tmp_path) -> None:
    query_service, executor_runtime_service, _ = _build_query_service(tmp_path)
    executor_runtime = executor_runtime_service.create_or_reuse_runtime(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-1",
        role_id="backend-engineer",
    )
    executor_runtime_service.mark_runtime_ready(
        executor_runtime.runtime_id,
        thread_id="thread-1",
    )

    payload = query_service.get_external_runtime_detail(executor_runtime.runtime_id)

    assert payload is not None
    assert payload["runtime"]["runtime_id"] == executor_runtime.runtime_id
    assert payload["runtime"]["executor_id"] == "codex"
    assert payload["runtime"]["kind"] == "executor-runtime"
    assert payload["runtime"]["status"] == "ready"
    assert payload["runtime"]["summary"] == "app_server / assignment / ready"


def test_runtime_center_external_runtime_projection_keeps_legacy_fallback(tmp_path) -> None:
    query_service, _, external_runtime_service = _build_query_service(tmp_path)
    legacy_runtime = external_runtime_service.create_or_reuse_service_runtime(
        capability_id="runtime:legacy-flask",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="python -m flask run",
    )
    external_runtime_service.mark_runtime_ready(legacy_runtime.runtime_id)

    items = query_service.list_external_runtimes()
    detail = query_service.get_external_runtime_detail(legacy_runtime.runtime_id)

    assert len(items) == 1
    assert items[0]["runtime_id"] == legacy_runtime.runtime_id
    assert items[0]["capability_id"] == "runtime:legacy-flask"
    assert items[0]["route"] == f"/api/runtime-center/external-runtimes/{legacy_runtime.runtime_id}"
    assert "kind" not in items[0]
    assert detail is not None
    assert detail["runtime"]["runtime_id"] == legacy_runtime.runtime_id
    assert detail["runtime"]["capability_id"] == "runtime:legacy-flask"
    assert detail["runtime"]["status"] == "ready"
