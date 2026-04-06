from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from copaw.capabilities.external_runtime_actions import (
    HealthcheckExternalRuntimePayload,
    StopExternalRuntimePayload,
)
from copaw.capabilities.external_runtime_execution import ExternalRuntimeExecution
from copaw.capabilities.models import CapabilityMount
from copaw.state.models_external_runtime import ExternalCapabilityRuntimeInstanceRecord


def test_append_args_uses_windows_safe_quoting_for_paths_with_spaces(
    monkeypatch,
) -> None:
    from copaw.capabilities.external_runtime_execution import _append_args
    from copaw.capabilities import external_runtime_execution as runtime_module

    monkeypatch.setattr(runtime_module.os, "name", "nt")

    command = _append_args(
        '"C:\\tooling\\black.exe"',
        ["C:\\Users\\test user\\bad format.py"],
    )

    assert command.startswith('"C:\\tooling\\black.exe" ')
    assert '"C:\\Users\\test user\\bad format.py"' in command
    assert "'C:\\Users\\test user\\bad format.py'" not in command


class _FakeRuntimeService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.runtime = ExternalCapabilityRuntimeInstanceRecord(
            runtime_id="runtime:openspace",
            capability_id="runtime:openspace",
            runtime_kind="service",
            scope_kind="session",
            session_mount_id="session:test",
            status="starting",
            command="python -m openspace",
            last_started_at=now,
            metadata={},
        )

    def get_runtime(self, runtime_id: str):
        if runtime_id == self.runtime.runtime_id:
            return self.runtime
        return None

    def update_runtime(self, runtime_id: str, **updates):
        assert runtime_id == self.runtime.runtime_id
        self.runtime = self.runtime.model_copy(update=updates)
        return self.runtime

    def mark_runtime_stopped(self, runtime_id: str, **updates):
        return self.update_runtime(runtime_id, **updates)

    def mark_runtime_ready(self, runtime_id: str, **updates):
        return self.update_runtime(runtime_id, **updates)


def test_healthcheck_service_returns_degraded_without_name_error() -> None:
    service = _FakeRuntimeService()
    execution = ExternalRuntimeExecution(runtime_service=service)
    mount = CapabilityMount(
        id="runtime:openspace",
        name="openspace",
        summary="runtime",
        kind="runtime-component",
        source_kind="runtime",
        risk_level="guarded",
        metadata={
            "runtime_contract": {
                "runtime_kind": "service",
                "ready_probe_kind": "http",
                "supported_actions": ["healthcheck"],
            },
        },
    )

    async def _probe(*args, **kwargs):
        return False, "still booting", None

    execution._probe_runtime_readiness = _probe  # type: ignore[method-assign]

    result = asyncio.run(
        execution.healthcheck_service(
            mount,
            HealthcheckExternalRuntimePayload(
                action="healthcheck",
                runtime_id="runtime:openspace",
                session_mount_id="session:test",
            ),
        ),
    )

    assert result["success"] is False
    assert result["status"] == "degraded"
    assert result["summary"] == "still booting"


def test_stop_service_returns_stable_summary_on_windows_success(
    monkeypatch,
) -> None:
    service = _FakeRuntimeService()
    service.runtime = service.runtime.model_copy(
        update={
            "process_id": 12345,
            "status": "ready",
        },
    )
    execution = ExternalRuntimeExecution(runtime_service=service)
    mount = CapabilityMount(
        id="runtime:openspace",
        name="openspace",
        summary="runtime",
        kind="runtime-component",
        source_kind="runtime",
        risk_level="guarded",
        metadata={},
    )

    monkeypatch.setattr(
        "copaw.capabilities.external_runtime_execution._terminate_process",
        lambda pid: (True, "成功: 已终止 PID 12345"),
    )

    result = asyncio.run(
        execution.stop_service(
            mount,
            StopExternalRuntimePayload(
                action="stop",
                runtime_id="runtime:openspace",
                session_mount_id="session:test",
            ),
        ),
    )

    assert result["success"] is True
    assert result["status"] == "stopped"
    assert result["summary"] == "Stopped runtime 'runtime:openspace'."
