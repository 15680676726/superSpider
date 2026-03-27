# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import copaw.routines.service as routine_service_module
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.learning import LearningService
from copaw.routines import (
    RoutineCreateFromEvidenceRequest,
    RoutineCreateRequest,
    RoutineReplayRequest,
    RoutineService,
)
from copaw.state import SQLiteStateStore
from copaw.state.agent_experience_service import AgentExperienceMemoryService
from copaw.state.repositories import (
    SqliteExecutionRoutineRepository,
    SqliteRoutineRunRepository,
)


class FakeBrowserRuntimeService:
    def __init__(self) -> None:
        self.start_calls = []
        self.stop_calls = []

    async def start_session(self, options):
        self.start_calls.append(options)
        return {"result": {"ok": True, "session_id": options.session_id}}

    async def stop_session(self, session_id: str):
        self.stop_calls.append(session_id)
        return {"ok": True}


class FakeKernelDispatcher:
    def __init__(self) -> None:
        self.tasks = []

    def submit(self, task):
        self.tasks.append(task)
        return SimpleNamespace(task_id=f"ktask:{len(self.tasks)}")


class FakeKnowledgeService:
    def __init__(self) -> None:
        self.calls = []

    def remember_fact(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


def build_routine_service(tmp_path, *, learning_service=None):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    routine_repo = SqliteExecutionRoutineRepository(store)
    run_repo = SqliteRoutineRunRepository(store)
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repo)
    ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    browser_runtime = FakeBrowserRuntimeService()
    kernel_dispatcher = FakeKernelDispatcher()
    service = RoutineService(
        routine_repository=routine_repo,
        routine_run_repository=run_repo,
        evidence_ledger=ledger,
        environment_service=environment_service,
        kernel_dispatcher=kernel_dispatcher,
        browser_runtime_service=browser_runtime,
        state_store=store,
        learning_service=learning_service,
    )
    return SimpleNamespace(
        service=service,
        ledger=ledger,
        environment_service=environment_service,
        browser_runtime=browser_runtime,
        kernel_dispatcher=kernel_dispatcher,
    )


def make_browser_tool_response(payload: dict[str, object]):
    return SimpleNamespace(content=[{"text": json.dumps(payload)}])


@pytest.mark.asyncio
async def test_routine_service_replay_success_captures_evidence(tmp_path, monkeypatch) -> None:
    harness = build_routine_service(tmp_path)
    screenshot_path = tmp_path / "artifacts" / "login.png"

    async def fake_browser_use(**kwargs):
        action = kwargs["action"]
        if action == "screenshot":
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot_path.write_bytes(b"fake-image")
            return make_browser_tool_response(
                {
                    "ok": True,
                    "message": f"{action} ok",
                    "path": str(screenshot_path),
                },
            )
        return make_browser_tool_response(
            {"ok": True, "message": f"{kwargs['action']} ok", "url": kwargs.get("url")},
        )

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="jd-login-capture",
            name="JD Login Capture",
                summary="Replay fixed browser steps.",
                session_requirements={"profile_id": "profile-1"},
                action_contract=[
                    {"action": "open", "page_id": "page-1", "url": "https://example.com/login"},
                    {
                        "action": "screenshot",
                        "page_id": "page-1",
                        "path": str(screenshot_path),
                    },
                ],
                evidence_expectations=["open", "screenshot"],
            ),
        )

    response = await harness.service.replay_routine(
        routine.id,
        RoutineReplayRequest(
            request_context={
                "channel": "console",
                "user_id": "ops-user",
                "session_id": "sess-1",
                "query_preview": "Replay JD login routine",
            },
        ),
    )

    assert response.run.status == "completed"
    assert response.run.deterministic_result == "replay-complete"
    records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert len(records) == 2
    assert all(record.task_id == f"routine-run:{response.run.id}" for record in records)
    assert {record.metadata["action"] for record in records} == {"open", "screenshot"}
    assert harness.browser_runtime.start_calls[0].profile_id == "profile-1"


@pytest.mark.asyncio
async def test_routine_service_execution_core_run_records_growth_and_experience(
    tmp_path,
    monkeypatch,
) -> None:
    knowledge = FakeKnowledgeService()
    learning_service = LearningService(evidence_ledger=EvidenceLedger())
    learning_service.set_experience_memory_service(
        AgentExperienceMemoryService(knowledge_service=knowledge),
    )
    harness = build_routine_service(tmp_path, learning_service=learning_service)

    async def fake_browser_use(**kwargs):
        return make_browser_tool_response(
            {"ok": True, "message": f"{kwargs['action']} ok", "url": kwargs.get("url")},
        )

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="exec-core-browser-routine",
            name="Execution Core Browser Routine",
            owner_agent_id="copaw-agent-runner",
            owner_scope="industry",
            source_capability_id="system:replay_routine",
            action_contract=[
                {"action": "open", "page_id": "page-1", "url": "https://example.com"},
            ],
            metadata={"industry_instance_id": "industry-v1-acme"},
        ),
    )

    response = await harness.service.replay_routine(
        routine.id,
        RoutineReplayRequest(
            owner_agent_id="copaw-agent-runner",
            request_context={
                "industry_instance_id": "industry-v1-acme",
                "industry_role_id": "execution-core",
            },
        ),
    )

    growth = learning_service.list_growth(
        agent_id="copaw-agent-runner",
        task_id=response.run.id,
    )
    assert response.run.status == "completed"
    assert growth
    assert growth[0].task_id == response.run.id
    assert growth[0].change_type == "routine_completed"
    assert any(
        call["scope_type"] == "agent" and call["scope_id"] == "copaw-agent-runner"
        for call in knowledge.calls
    )


def test_routine_service_create_from_evidence_extracts_supported_browser_actions(tmp_path) -> None:
    harness = build_routine_service(tmp_path)
    open_record = harness.ledger.append(
        EvidenceRecord(
            task_id="task-1",
            actor_ref="tool:browser_use",
            environment_ref="https://example.com/login",
            capability_ref="tool:browser_use",
            risk_level="guarded",
            action_summary="browser open success",
            result_summary="Opened login page",
            status="recorded",
            metadata={
                "action": "open",
                "page_id": "page-1",
                "url": "https://example.com/login",
                "session_id": "browser-session-1",
            },
        ),
    )
    click_record = harness.ledger.append(
        EvidenceRecord(
            task_id="task-1",
            actor_ref="tool:browser_use",
            environment_ref="https://example.com/login",
            capability_ref="tool:browser_use",
            risk_level="guarded",
            action_summary="browser click success",
            result_summary="Clicked submit button",
            status="recorded",
            metadata={
                "action": "click",
                "page_id": "page-1",
                "selector": "#submit",
                "button": "left",
                "session_id": "browser-session-1",
            },
        ),
    )

    routine = harness.service.create_routine_from_evidence(
        RoutineCreateFromEvidenceRequest(
            evidence_ids=[open_record.id, click_record.id],
            name="Extracted routine",
        ),
    )

    assert [step["action"] for step in routine.action_contract] == ["open", "click"]
    assert routine.session_requirements["session_id"] == "browser-session-1"
    assert routine.source_evidence_ids == [open_record.id, click_record.id]


@pytest.mark.asyncio
async def test_routine_service_replay_failure_classifies_page_drift(tmp_path, monkeypatch) -> None:
    harness = build_routine_service(tmp_path)

    async def fake_browser_use(**kwargs):
        _ = kwargs
        return make_browser_tool_response({"ok": False, "error": "element not found"})

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="jd-click",
            name="JD Click",
            action_contract=[
                {"action": "click", "page_id": "page-1", "selector": "#submit"},
            ],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "failed"
    assert response.run.failure_class == "page-drift"
    assert response.run.fallback_mode == "hard-fail"
    assert "Missing fallback context" in (response.run.output_summary or "")


@pytest.mark.asyncio
async def test_routine_service_replay_creates_kernel_fallback(tmp_path, monkeypatch) -> None:
    harness = build_routine_service(tmp_path)

    async def fake_browser_use(**kwargs):
        _ = kwargs
        return make_browser_tool_response({"ok": False, "error": "element not found"})

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="jd-fallback",
            name="JD Fallback",
            action_contract=[
                {"action": "click", "page_id": "page-1", "selector": "#submit"},
            ],
            metadata={
                "fallback_request_context": {
                    "channel": "console",
                    "user_id": "ops-user",
                    "session_id": "sess-1",
                    "query_preview": "继续处理京东后台登录流程",
                    "request": {"query": "继续处理京东后台登录流程"},
                    "request_context": {"industry_instance_id": "industry-v1-ops"},
                },
            },
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "fallback"
    assert response.run.fallback_mode == "return-to-llm-replan"
    assert response.run.fallback_task_id == "ktask:1"
    assert len(harness.kernel_dispatcher.tasks) == 1
    assert harness.kernel_dispatcher.tasks[0].capability_ref == "system:dispatch_query"
    assert harness.kernel_dispatcher.tasks[0].payload["query_preview"] == "继续处理京东后台登录流程"


@pytest.mark.asyncio
async def test_routine_service_replay_reports_lock_conflict(tmp_path, monkeypatch) -> None:
    harness = build_routine_service(tmp_path)

    async def fake_browser_use(**kwargs):
        return make_browser_tool_response({"ok": True, "message": f"{kwargs['action']} ok"})

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="jd-lock",
            name="JD Lock",
            session_requirements={"profile_id": "profile-1"},
            action_contract=[
                {"action": "open", "page_id": "page-1", "url": "https://example.com/login"},
            ],
        ),
    )
    held_lease = harness.environment_service.acquire_resource_slot_lease(
        scope_type="browser-profile",
        scope_value="profile-1",
        owner="other-owner",
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "failed"
    assert response.run.failure_class == "lock-conflict"
    assert response.diagnosis.lock_health == "contended"
    harness.environment_service.release_resource_slot_lease(
        lease_id=held_lease.id,
        lease_token=held_lease.lease_token,
        reason="test cleanup",
    )


@pytest.mark.asyncio
async def test_routine_service_desktop_host_unsupported(tmp_path, monkeypatch) -> None:
    harness = build_routine_service(tmp_path)
    monkeypatch.setattr(routine_service_module.sys, "platform", "linux")
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="desktop-routine",
            name="Desktop Routine",
            engine_kind="desktop",
            environment_kind="desktop",
            action_contract=[{"action": "list_windows"}],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "failed"
    assert response.run.failure_class == "host-unsupported"
    assert response.run.fallback_mode == "hard-fail"
