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


class _FakeSidecarReleaseService:
    def __init__(self) -> None:
        self.upgrade_calls = 0
        self.rollback_calls = 0

    def describe_version_governance(self, *, runtime_family: str, channel: str | None = None):
        _ = runtime_family, channel
        return {
            "current_install": {"version": "0.9.0", "channel": "stable"},
            "compatibility": {"status": "compatible", "fail_closed": True, "blockers": []},
            "available_upgrade": {"version": "0.10.0", "release_id": "codex-stable-0.10.0"},
        }

    def upgrade_sidecar(self, *, runtime_family: str, channel: str | None = None):
        _ = runtime_family, channel
        self.upgrade_calls += 1
        return {
            "status": "upgraded",
            "target_release_id": "codex-stable-0.10.0",
            "target_version": "0.10.0",
            "rolled_back": False,
        }

    def rollback_sidecar(self, *, runtime_family: str, channel: str | None = None):
        _ = runtime_family, channel
        self.rollback_calls += 1
        return {
            "status": "rolled_back",
            "active_version": "0.9.0",
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


@pytest.mark.asyncio
async def test_daemon_sidecar_version_upgrade_and_rollback_commands() -> None:
    handler = DaemonCommandHandlerMixin()
    release_service = _FakeSidecarReleaseService()
    context = DaemonContext(sidecar_release_service=release_service)

    version_message = await handler.handle_daemon_command("/daemon sidecar-version", context)
    upgrade_message = await handler.handle_daemon_command("/daemon sidecar-upgrade", context)
    rollback_message = await handler.handle_daemon_command("/daemon sidecar-rollback", context)

    assert "Current version: 0.9.0" in version_message.get_text_content()
    assert "Available upgrade: 0.10.0" in version_message.get_text_content()
    assert "0.10.0" in upgrade_message.get_text_content()
    assert "rolled_back" in rollback_message.get_text_content().lower()
    assert release_service.upgrade_calls == 1
    assert release_service.rollback_calls == 1
