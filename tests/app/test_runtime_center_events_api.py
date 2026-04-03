# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from copaw.app.runtime_events import RuntimeEventBus
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.startup_recovery import StartupRecoverySummary
from copaw.memory.conversation_compaction_service import ConversationCompactionService


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
        reaped_expired_leases=2,
        recovered_orphaned_mailbox_items=3,
        pending_decisions=2,
        hydrated_waiting_confirm_tasks=1,
        active_schedules=3,
    )

    client = TestClient(app)
    response = client.get("/runtime-center/recovery/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reason"] == "startup"
    assert payload["source"] == "startup"
    assert payload["pending_decisions"] == 2
    assert payload["hydrated_waiting_confirm_tasks"] == 1
    assert payload["active_schedules"] == 3
    assert payload["detail"]["leases"]["reaped_expired_leases"] == 2
    assert payload["detail"]["mailbox"]["recovered_orphaned_mailbox_items"] == 3
    assert payload["detail"]["decisions"]["pending_decisions"] == 2
    assert payload["detail"]["automation"]["active_schedules"] == 3


def test_runtime_center_recovery_latest_endpoint_prefers_canonical_latest_report() -> None:
    app = _build_app()
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="startup",
        pending_decisions=2,
        hydrated_waiting_confirm_tasks=1,
        active_schedules=3,
    )
    app.state.latest_recovery_report = {
        "reason": "runtime-recovery",
        "pending_decisions": 1,
        "active_schedules": 4,
        "latest_scope": "runtime",
    }

    client = TestClient(app)
    response = client.get("/runtime-center/recovery/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reason"] == "runtime-recovery"
    assert payload["source"] == "latest"
    assert payload["pending_decisions"] == 1
    assert payload["active_schedules"] == 4
    assert payload["latest_scope"] == "runtime"
    assert payload["detail"]["decisions"]["pending_decisions"] == 1
    assert payload["detail"]["automation"]["active_schedules"] == 4
def test_conversation_compaction_service_builds_visibility_payload() -> None:
    payload = ConversationCompactionService.build_visibility_payload(
        {
            "compaction_state": {
                "mode": "microcompact",
                "summary": "Compacted 2 oversized tool results.",
                "spill_count": 1,
                "replacement_count": 2,
            },
            "tool_result_budget": {
                "message_budget": 2400,
                "used_budget": 1800,
                "remaining_budget": 600,
            },
            "tool_use_summary": {
                "summary": "2 tool results compacted into artifact previews.",
                "artifact_refs": ["artifact://tool-result-1"],
            },
        }
    )

    assert payload["compaction_state"] == {
        "mode": "microcompact",
        "summary": "Compacted 2 oversized tool results.",
        "spill_count": 1,
        "replacement_count": 2,
    }
    assert payload["tool_result_budget"] == {
        "message_budget": 2400,
        "used_budget": 1800,
        "remaining_budget": 600,
    }
    assert payload["tool_use_summary"] == {
        "summary": "2 tool results compacted into artifact previews.",
        "artifact_refs": ["artifact://tool-result-1"],
    }
