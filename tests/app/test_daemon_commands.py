# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from copaw.app.daemon_commands import DaemonCommandHandlerMixin, DaemonContext


class _FakeExecutorRuntimeCoordinator:
    def __init__(self) -> None:
        self.restart_calls = 0
        self.interrupt_calls: list[dict[str, object]] = []
        self.approval_calls: list[dict[str, object]] = []

    def describe_sidecar_control_state(self) -> dict[str, object]:
        return {
            "sidecar": {
                "transport_kind": "stdio",
                "connected": True,
                "restart_count": self.restart_calls,
            },
            "pending_approvals": [
                {
                    "request_id": "approval-1",
                    "status": "pending",
                    "risk_level": "confirm",
                    "summary": "Approve guarded command execution",
                }
            ],
            "active_runtime": {
                "runtime_id": "runtime-1",
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "runtime_status": "restarting",
            },
        }

    def restart_sidecar(self) -> dict[str, object]:
        self.restart_calls += 1
        return {
            "transport_kind": "stdio",
            "connected": False,
            "restart_count": self.restart_calls,
        }

    def interrupt_active_turn(
        self,
        *,
        thread_id: str | None = None,
        turn_id: str | None = None,
        assignment_id: str | None = None,
    ) -> dict[str, object]:
        payload = {
            "thread_id": thread_id,
            "turn_id": turn_id,
            "assignment_id": assignment_id,
        }
        self.interrupt_calls.append(payload)
        return {
            "status": "interrupted",
            **payload,
        }

    def respond_to_sidecar_approval(
        self,
        request_id: str,
        *,
        decision: str,
        reason: str | None = None,
    ) -> dict[str, object]:
        payload = {
            "request_id": request_id,
            "decision": decision,
            "reason": reason,
        }
        self.approval_calls.append(payload)
        return {
            "status": decision,
            **payload,
        }


@pytest.mark.asyncio
async def test_daemon_sidecar_status_reports_recovery_state_and_pending_approval() -> None:
    handler = DaemonCommandHandlerMixin()
    coordinator = _FakeExecutorRuntimeCoordinator()
    context = DaemonContext(executor_runtime_coordinator=coordinator)

    message = await handler.handle_daemon_command("/daemon sidecar-status", context)
    text = message.get_text_content()

    assert "Sidecar Status" in text
    assert "Connected: yes" in text
    assert "Runtime status: restarting" in text
    assert "Pending approvals: 1" in text


@pytest.mark.asyncio
async def test_daemon_sidecar_restart_and_approval_commands_dispatch_to_coordinator() -> None:
    handler = DaemonCommandHandlerMixin()
    coordinator = _FakeExecutorRuntimeCoordinator()
    context = DaemonContext(executor_runtime_coordinator=coordinator)

    restart_message = await handler.handle_daemon_command("/daemon sidecar-restart", context)
    approve_message = await handler.handle_daemon_command(
        "/daemon sidecar-approve approval-1 operator-approved",
        context,
    )
    reject_message = await handler.handle_daemon_command(
        "/daemon sidecar-reject approval-2 operator-rejected",
        context,
    )
    interrupt_message = await handler.handle_daemon_command(
        "/daemon sidecar-interrupt thread-1 turn-1",
        context,
    )

    assert "restart count: 1" in restart_message.get_text_content().lower()
    assert "approved" in approve_message.get_text_content().lower()
    assert "rejected" in reject_message.get_text_content().lower()
    assert "interrupted" in interrupt_message.get_text_content().lower()
    assert coordinator.restart_calls == 1
    assert coordinator.approval_calls == [
        {
            "request_id": "approval-1",
            "decision": "approved",
            "reason": "operator-approved",
        },
        {
            "request_id": "approval-2",
            "decision": "rejected",
            "reason": "operator-rejected",
        },
    ]
    assert coordinator.interrupt_calls == [
        {
            "thread_id": "thread-1",
            "turn_id": "turn-1",
            "assignment_id": None,
        }
    ]
