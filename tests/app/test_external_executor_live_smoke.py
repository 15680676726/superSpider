# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentscope.message import Msg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.adapters.executors.codex_app_server_adapter import CodexAppServerAdapter
from copaw.adapters.executors.codex_app_server_transport import CodexAppServerTransport
from copaw.app.routers.capability_market import router as capability_market_router
from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination
from copaw.app.runtime_events import RuntimeEventBus
from copaw.evidence import EvidenceLedger
from copaw.kernel.executor_event_writeback_service import ExecutorEventWritebackService
from copaw.state import SQLiteStateStore
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state.external_runtime_service import ExternalCapabilityRuntimeService
from copaw.state.repositories import SqliteExternalCapabilityRuntimeRepository


LIVE_EXTERNAL_EXECUTOR_SMOKE_SKIP_REASON = (
    "Set COPAW_RUN_EXTERNAL_EXECUTOR_LIVE_SMOKE=1 to run live external-executor "
    "provider intake smoke coverage (opt-in; not part of default regression coverage)."
)
_SMOKE_TOKEN = "COPAW_APP_SERVER_SMOKE"


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _timeout_seconds() -> float:
    raw = os.getenv("COPAW_EXTERNAL_EXECUTOR_LIVE_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 240.0
    try:
        value = float(raw)
    except ValueError:
        return 240.0
    return value if value > 0 else 240.0


def _build_executor_runtime_service(state_store: SQLiteStateStore) -> ExecutorRuntimeService:
    runtime_repository = SqliteExternalCapabilityRuntimeRepository(state_store)
    external_runtime_service = ExternalCapabilityRuntimeService(repository=runtime_repository)
    return ExecutorRuntimeService(
        external_runtime_service=external_runtime_service,
        state_store=state_store,
    )


def _build_market_client(
    tmp_path: Path,
) -> tuple[TestClient, ExecutorRuntimeService]:
    app = FastAPI()
    app.include_router(capability_market_router)
    state_store = SQLiteStateStore(tmp_path / "state.db")
    executor_runtime_service = _build_executor_runtime_service(state_store)
    app.state.executor_runtime_service = executor_runtime_service
    return TestClient(app), executor_runtime_service


class _AssignmentService:
    def __init__(self, assignment: SimpleNamespace) -> None:
        self._assignment = assignment
        self.attached_evidence_ids: list[str] = []

    def get_assignment(self, assignment_id: str) -> SimpleNamespace | None:
        if assignment_id != self._assignment.id:
            return None
        return self._assignment

    def attach_evidence_ids(self, assignment_id: str, *, evidence_ids: list[str]) -> None:
        if assignment_id == self._assignment.id:
            self.attached_evidence_ids.extend(list(evidence_ids))


def _wait_for_terminal_runtime(
    service: ExecutorRuntimeService,
    *,
    runtime_id: str,
    thread_id: str,
    timeout_seconds: float,
) -> tuple[list[object], object]:
    deadline = time.monotonic() + timeout_seconds
    latest_events: list[object] = []
    latest_runtime = None
    while time.monotonic() < deadline:
        latest_runtime = service.get_runtime(runtime_id)
        latest_events = service.list_event_records(thread_id=thread_id)
        terminal_event = next(
            (
                event
                for event in latest_events
                if event.event_type in {"task_completed", "task_failed"}
            ),
            None,
        )
        if terminal_event is not None and latest_runtime is not None:
            return latest_events, latest_runtime
        time.sleep(0.5)
    raise AssertionError(
        f"Timed out waiting for executor runtime '{runtime_id}' to finish live smoke.",
    )


def test_live_external_executor_smoke_skip_reason_declares_opt_in_boundary() -> None:
    reason = LIVE_EXTERNAL_EXECUTOR_SMOKE_SKIP_REASON.lower()
    assert "opt-in" in reason
    assert "not part of default regression coverage" in reason


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_EXTERNAL_EXECUTOR_LIVE_SMOKE"),
    reason=LIVE_EXTERNAL_EXECUTOR_SMOKE_SKIP_REASON,
)
def test_live_external_executor_provider_intake_and_runtime_writeback(
    tmp_path: Path,
) -> None:
    codex_binary = shutil.which("codex.cmd") or shutil.which("codex")
    if codex_binary is None:
        pytest.skip("Codex CLI is not available on PATH.")

    client, executor_runtime_service = _build_market_client(tmp_path)
    runtime_event_bus = RuntimeEventBus()
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    adapter = CodexAppServerAdapter(transport=CodexAppServerTransport())

    assignment = SimpleNamespace(
        id="assignment-live-executor",
        owner_role_id="execution-core",
        owner_agent_id="agent-live-executor",
        title="Live external executor smoke",
        summary="Verify formal provider intake can launch a real Codex turn.",
        task_id="task-live-executor",
        industry_instance_id="industry-live-executor",
        metadata={
            "project_profile_id": "copaw-main",
            "task_id": "task-live-executor",
            "industry_instance_id": "industry-live-executor",
        },
    )
    assignment_service = _AssignmentService(assignment)

    try:
        install_response = client.post(
            "/capability-market/executor-providers/install",
            json={
                "provider_id": "codex-app-server",
                "runtime_family": "codex",
                "control_surface_kind": "app_server",
                "default_protocol_kind": "app_server",
                "install_source_kind": "catalog",
                "source_ref": "codex://app-server",
                "role_id": "execution-core",
                "selection_mode": "role-routed",
                "model_policy_id": "codex-default",
                "default_model_ref": "gpt-5.4",
            },
        )
        assert install_response.status_code == 201
        search_response = client.get(
            "/capability-market/executor-providers/search",
            params={"q": "codex", "limit": 5},
        )
        assert search_response.status_code == 200
        assert any(
            item["provider_id"] == "codex-app-server"
            for item in search_response.json()
        )

        _service, coordinator = build_executor_runtime_coordination(
            assignment_service=assignment_service,
            external_runtime_service=executor_runtime_service._external_runtime_service,
            project_root=str(Path(__file__).resolve().parents[2]),
            executor_runtime_port=adapter,
            default_executor_provider_id="codex-app-server",
            default_model_policy_id="codex-default",
        )
        coordinator.set_executor_runtime_service(executor_runtime_service)
        coordinator.set_executor_event_writeback_service(
            ExecutorEventWritebackService(
                evidence_ledger=evidence_ledger,
                assignment_service=assignment_service,
                agent_report_service=None,
                runtime_event_bus=runtime_event_bus,
                executor_runtime_service=executor_runtime_service,
            ),
        )

        request = SimpleNamespace(
            assignment_id=assignment.id,
            session_id="industry-chat:industry-live-executor:execution-core",
            control_thread_id="industry-chat:industry-live-executor:execution-core",
            work_context_id="ctx-live-executor",
        )
        payload = coordinator.coordinate_assignment_runtime(
            request=request,
            msgs=[
                Msg(
                    name="user",
                    role="user",
                    content=f"Reply with exactly: {_SMOKE_TOKEN}",
                ),
            ],
            intake_contract=SimpleNamespace(
                message_text=f"Reply with exactly: {_SMOKE_TOKEN}",
                should_kickoff=True,
                writeback_requested=False,
            ),
        )

        assert payload is not None
        assert payload["status"] == "ready"
        runtime_payload = payload["executor_runtime"]
        runtime_id = runtime_payload["runtime_id"]
        thread_id = runtime_payload["thread_id"]
        assert runtime_id
        assert thread_id

        stored_events, stored_runtime = _wait_for_terminal_runtime(
            executor_runtime_service,
            runtime_id=runtime_id,
            thread_id=thread_id,
            timeout_seconds=_timeout_seconds(),
        )
        message_events = [
            event
            for event in stored_events
            if event.event_type == "message_emitted" and event.source_type == "agentMessage"
        ]
        assert any(
            _SMOKE_TOKEN in str(event.payload.get("message") or "")
            for event in message_events
        )
        assert any(event.event_type == "task_completed" for event in stored_events)
        assert stored_runtime.runtime_status == "completed"
        turn_records = executor_runtime_service.list_turn_records(thread_id=thread_id)
        assert turn_records
        assert turn_records[0].turn_status == "completed"
    finally:
        adapter.close()
        client.close()
