# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.capabilities import router as capabilities_router


class _FakeDispatcher:
    def __init__(self) -> None:
        self.submitted: list[object] = []
        self.executed: list[str] = []

    def submit(self, task):
        self.submitted.append(task)
        return SimpleNamespace(phase="executing", model_dump=lambda mode="json": {"phase": "executing"})

    async def execute_task(self, task_id: str):
        self.executed.append(task_id)
        return SimpleNamespace(
            success=True,
            model_dump=lambda mode="json": {"success": True, "phase": "completed"},
        )


class _FakeCapabilityService:
    def get_capability(self, capability_id: str):
        enabled = capability_id != "skill:missing"
        if capability_id in {"skill:research", "system:set_capability_enabled"}:
            return SimpleNamespace(
                id=capability_id,
                enabled=enabled,
                risk_level="guarded",
            )
        return None

    def list_capabilities(self, *, kind=None, enabled_only=False):
        return []

    def summarize(self):
        return SimpleNamespace(total=0, enabled=0, by_kind={})


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(capabilities_router)
    app.state.capability_service = _FakeCapabilityService()
    app.state.kernel_dispatcher = _FakeDispatcher()
    return app


def test_capability_toggle_reuses_shared_governed_mutation_dispatch() -> None:
    from copaw.app.routers.governed_mutations import dispatch_governed_mutation

    client = TestClient(build_app())
    response = client.patch("/capabilities/skill:research/toggle")

    assert callable(dispatch_governed_mutation)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_shared_governed_mutation_helper_translates_dispatcher_errors() -> None:
    from copaw.app.routers.governed_mutations import translate_dispatcher_error

    with pytest.raises(Exception) as exc_info:
        translate_dispatcher_error(KeyError("missing-task"))

    assert "404" in str(exc_info.value) or "missing-task" in str(exc_info.value)
