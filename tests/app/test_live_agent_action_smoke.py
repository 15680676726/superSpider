# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient

import copaw.kernel.query_execution_runtime as query_execution_runtime_module
import copaw.kernel.query_execution_writeback as query_execution_writeback_module
from copaw.app.runtime_session import SafeJSONSession
from copaw.agents.tools.browser_control_shared import get_browser_runtime_snapshot
from copaw.capabilities import CapabilityService
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.kernel import (
    AgentProfileService,
    KernelDispatcher,
    KernelQueryExecutionService,
    KernelTaskStore,
    KernelToolBridge,
    KernelTurnExecutor,
    MainBrainChatService,
    MainBrainOrchestrator,
)
from copaw.providers.provider_manager import ProviderManager
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)
from tests.app.industry_api_parts.shared import BrowserIndustryDraftGenerator, _build_industry_app


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


LIVE_AGENT_ACTION_SMOKE_SKIP_REASON = (
    "Set COPAW_RUN_LIVE_AGENT_ACTION_SMOKE=1 to run live professional-agent "
    "browser action smoke coverage (opt-in; not part of default regression coverage)."
)


def _ensure_live_chat_writeback_model_ready_or_skip() -> None:
    query_execution_writeback_module.clear_chat_writeback_decision_cache()
    try:
        decision = query_execution_writeback_module.resolve_chat_writeback_model_decision_sync(
            text=(
                "Use the mounted browser capability right now. "
                "Open https://example.com and save a screenshot to C:\\temp\\probe.png."
            ),
        )
    except (
        query_execution_writeback_module.ChatWritebackDecisionModelUnavailableError,
        query_execution_writeback_module.ChatWritebackDecisionModelTimeoutError,
    ) as exc:
        pytest.skip(f"Live chat writeback decision model is unavailable: {exc}")
    if decision is None or decision.intent_kind != "execute-task" or not decision.kickoff_allowed:
        pytest.skip(
            "Live chat writeback decision model did not resolve execute-task readiness.",
        )


def _parse_sse_events(raw_text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for chunk in raw_text.strip().split("\n\n"):
        if not chunk:
            continue
        data_lines: list[str] = []
        for line in chunk.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].lstrip()
            if payload:
                data_lines.append(payload)
        if not data_lines:
            continue
        events.append(json.loads("\n".join(data_lines)))
    return events


def _industry_role_agent_id(client: TestClient, instance_id: str, role_id: str) -> str:
    record = client.app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    for agent in list((record.team_payload or {}).get("agents") or []):
        if not isinstance(agent, dict):
            continue
        if agent.get("role_id") == role_id and str(agent.get("agent_id") or "").strip():
            return str(agent["agent_id"])
    raise AssertionError(f"role '{role_id}' was not found in industry team")


def _patch_live_runtime_iteration_budget(monkeypatch, *, max_iters: int) -> None:
    original_load_config = query_execution_runtime_module.load_config
    config = original_load_config().model_copy(deep=True)
    config.agents.running.max_iters = max_iters
    monkeypatch.setattr(
        query_execution_runtime_module,
        "load_config",
        lambda *args, **kwargs: config,
    )


def _close_live_agent_app(app) -> None:
    browser_runtime_service = getattr(app.state, "browser_runtime_service", None)
    if browser_runtime_service is not None:
        runtime = get_browser_runtime_snapshot()
        for item in list(runtime.get("sessions") or []):
            session_id = str(item.get("session_id") or "").strip()
            if not session_id:
                continue
            try:
                asyncio.run(browser_runtime_service.stop_session(session_id))
            except Exception:
                pass

    close_ledger = getattr(getattr(app.state, "evidence_ledger", None), "close", None)
    if callable(close_ledger):
        close_ledger()


def _attach_live_runtime_turn_executor(app, tmp_path: Path) -> None:
    state_store = SQLiteStateStore(tmp_path / "live-agent-runtime.sqlite3")
    session_backend = SafeJSONSession(database_path=tmp_path / "live-agent-session.sqlite3")
    environment_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=environment_repository,
            session_repository=session_repository,
        ),
        lease_ttl_seconds=120,
    )
    environment_service.set_session_repository(session_repository)

    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    work_context_repository = SqliteWorkContextRepository(state_store)
    work_context_service = app.state.work_context_service
    if work_context_service is None:
        work_context_service = work_context_repository
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=app.state.evidence_ledger,
        work_context_service=work_context_service,
    )
    tool_bridge = KernelToolBridge(
        task_store=task_store,
        environment_service=environment_service,
    )
    provider_manager = ProviderManager()
    query_execution_service = KernelQueryExecutionService(
        session_backend=session_backend,
        tool_bridge=tool_bridge,
        environment_service=environment_service,
        capability_service=app.state.capability_service,
        kernel_dispatcher=app.state.kernel_dispatcher,
        agent_profile_service=app.state.agent_profile_service,
        industry_service=app.state.industry_service,
        strategy_memory_service=app.state.strategy_memory_service,
        prediction_service=app.state.prediction_service,
        task_repository=app.state.task_repository,
        task_runtime_repository=app.state.task_runtime_repository,
        evidence_ledger=app.state.evidence_ledger,
        provider_manager=provider_manager,
    )
    main_brain_chat_service = MainBrainChatService(
        session_backend=session_backend,
        industry_service=app.state.industry_service,
        agent_profile_service=app.state.agent_profile_service,
        model_factory=provider_manager.get_active_chat_model,
    )
    main_brain_orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        session_backend=session_backend,
        environment_service=environment_service,
    )
    turn_executor = KernelTurnExecutor(
        session_backend=session_backend,
        kernel_dispatcher=app.state.kernel_dispatcher,
        tool_bridge=tool_bridge,
        environment_service=environment_service,
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    app.state.session_backend = session_backend
    app.state.environment_service = environment_service
    app.state.query_execution_service = query_execution_service
    app.state.main_brain_chat_service = main_brain_chat_service
    app.state.main_brain_orchestrator = main_brain_orchestrator
    app.state.turn_executor = turn_executor
    app.state.kernel_task_store = task_store
    app.state.kernel_tool_bridge = tool_bridge
    app.state.capability_service.set_turn_executor(turn_executor)


def _run_live_python_script(script: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _run_live_agent_action_case(tmp_path: Path) -> dict[str, object]:
    script = textwrap.dedent(
        f"""
        import json
        from pathlib import Path

        from fastapi.testclient import TestClient

        import copaw.kernel.query_execution_runtime as query_execution_runtime_module
        from tests.app.industry_api_parts.shared import BrowserIndustryDraftGenerator, _build_industry_app
        from tests.app.test_live_agent_action_smoke import (
            _attach_live_runtime_turn_executor,
            _close_live_agent_app,
            _industry_role_agent_id,
            _parse_sse_events,
        )

        tmp_path = Path({json.dumps(str(tmp_path))})
        config = query_execution_runtime_module.load_config().model_copy(deep=True)
        config.agents.running.max_iters = 6
        query_execution_runtime_module.load_config = lambda *args, **kwargs: config

        app = _build_industry_app(
            tmp_path,
            draft_generator=BrowserIndustryDraftGenerator(),
        )
        payload = {{}}
        try:
            _attach_live_runtime_turn_executor(app, tmp_path)
            with TestClient(app) as client:
                preview = client.post(
                    "/industry/v1/preview",
                    json={{
                        "industry": "Customer Operations",
                        "company_name": "Northwind Robotics",
                        "product": "browser onboarding workflows",
                        "goals": ["verify live browser execution through the professional seat"],
                    }},
                )
                assert preview.status_code == 200
                preview_payload = preview.json()
                draft = preview_payload["draft"]
                target_agent_id = next(
                    agent["agent_id"]
                    for agent in draft["team"]["agents"]
                    if agent["role_id"] == "solution-lead"
                )

                bootstrap = client.post(
                    "/industry/v1/bootstrap",
                    json={{
                        "profile": preview_payload["profile"],
                        "draft": draft,
                        "install_plan": [
                            {{
                                "install_kind": "builtin-runtime",
                                "template_id": "browser-local",
                                "client_key": "browser-local-default",
                                "source_kind": "install-template",
                                "capability_assignment_mode": "merge",
                                "target_agent_ids": [target_agent_id],
                            }}
                        ],
                        "auto_activate": True,
                        "auto_dispatch": False,
                        "execute": False,
                    }},
                )
                assert bootstrap.status_code == 200
                instance_id = bootstrap.json()["team"]["team_id"]
                solution_lead_id = _industry_role_agent_id(client, instance_id, "solution-lead")
                override = app.state.agent_profile_override_repository.get_override(solution_lead_id)
                assert override is not None
                assert "tool:browser_use" in (override.capabilities or [])

                existing_task_ids = {{
                    task.id
                    for task in app.state.task_repository.list_tasks(owner_agent_id=solution_lead_id)
                }}
                screenshot_path = tmp_path / "live-solution-lead-browser.png"
                response = client.post(
                    "/runtime-center/chat/run",
                    json={{
                        "id": "req-live-solution-lead-browser",
                        "session_id": f"industry-chat:{{instance_id}}:solution-lead",
                        "thread_id": f"industry-chat:{{instance_id}}:solution-lead",
                        "user_id": solution_lead_id,
                        "channel": "console",
                        "agent_id": solution_lead_id,
                        "industry_instance_id": instance_id,
                        "industry_role_id": "solution-lead",
                        "session_kind": "industry-agent-chat",
                        "interaction_mode": "auto",
                        "input": [
                            {{
                                "role": "user",
                                "type": "message",
                                "content": [
                                    {{
                                        "type": "text",
                                        "text": (
                                            "Use the mounted browser capability right now. "
                                            "Open https://example.com and save a screenshot to "
                                            f"{{screenshot_path}}. "
                                            "Do not answer until the screenshot is really saved, "
                                            "then report the final screenshot path."
                                        ),
                                    }}
                                ],
                            }}
                        ],
                    }},
                )

                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                events = _parse_sse_events(response.text)
                assert events
                terminal_payload = json.dumps(events[-1], ensure_ascii=False)
                new_tasks = [
                    task
                    for task in app.state.task_repository.list_tasks(owner_agent_id=solution_lead_id)
                    if task.id not in existing_task_ids
                ]
                browser_evidence = [
                    record
                    for record in app.state.evidence_ledger.list_recent(limit=20)
                    if record.capability_ref == "tool:browser_use"
                ]
                recent_evidence = [
                    {{
                        "capability_ref": record.capability_ref,
                        "actor_ref": record.actor_ref,
                        "action_summary": record.action_summary,
                        "result_summary": record.result_summary,
                    }}
                    for record in app.state.evidence_ledger.list_recent(limit=20)
                ]
                payload = {{
                    "response_status": response.status_code,
                    "event_count": len(events),
                    "terminal_payload": terminal_payload,
                    "response_text": response.text[-8000:],
                    "response_completed": any(
                        event.get("object") == "response"
                        and event.get("status") == "completed"
                        for event in events
                    ),
                    "resolved_orchestrate": {json.dumps('"resolved_interaction_mode":"orchestrate"')}
                    in response.text,
                    "screenshot_path": str(screenshot_path),
                    "screenshot_exists": screenshot_path.exists(),
                    "screenshot_evidence_present": any(
                        screenshot_path.name in str(record.result_summary or "")
                        for record in browser_evidence
                    ),
                    "new_task_count": len(new_tasks),
                    "browser_evidence_count": len(browser_evidence),
                    "recent_evidence": recent_evidence,
                }}
        finally:
            _close_live_agent_app(app)

        print(json.dumps(payload, ensure_ascii=True))
        """,
    )
    return _run_live_python_script(script)


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_LIVE_AGENT_ACTION_SMOKE"),
    reason=LIVE_AGENT_ACTION_SMOKE_SKIP_REASON,
)
def test_live_solution_lead_browser_action_runs_through_runtime_center_chat_front_door(
    tmp_path,
) -> None:
    _ensure_live_chat_writeback_model_ready_or_skip()
    payload = _run_live_agent_action_case(tmp_path)
    assert payload["response_status"] == 200
    assert payload["event_count"] >= 1
    assert payload["screenshot_exists"] is True
    assert payload["new_task_count"] >= 1
    assert payload["browser_evidence_count"] >= 1
    assert payload["response_completed"] is True
    assert payload["resolved_orchestrate"] is True
    assert payload["screenshot_evidence_present"] is True
