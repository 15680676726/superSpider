# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.runtime_events import RuntimeEventBus
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.startup_recovery import StartupRecoverySummary


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(runtime_center_router)
    return app


def test_runtime_center_events_endpoint_streams_published_events() -> None:
    app = _build_app()
    bus = RuntimeEventBus()
    bus.publish(
        topic="task",
        action="completed",
        payload={"task_id": "task-1", "phase": "completed"},
    )
    app.state.runtime_event_bus = bus

    client = TestClient(app)
    response = client.get("/runtime-center/events", params={"once": True})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: runtime" in response.text
    assert '"event_name": "task.completed"' in response.text
    assert '"task_id": "task-1"' in response.text


def test_runtime_center_recovery_latest_endpoint_returns_summary() -> None:
    app = _build_app()
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="startup",
        pending_decisions=2,
        hydrated_waiting_confirm_tasks=1,
        active_schedules=3,
    )

    client = TestClient(app)
    response = client.get("/runtime-center/recovery/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reason"] == "startup"
    assert payload["pending_decisions"] == 2
    assert payload["hydrated_waiting_confirm_tasks"] == 1
    assert payload["active_schedules"] == 3
