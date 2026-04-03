# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel import KernelTask, KernelToolBridge


def test_shell_replay_pointer_sanitizes_windows_unsafe_task_id(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("copaw.kernel.tool_bridge.WORKING_DIR", tmp_path)
    bridge = KernelToolBridge(task_store=object())

    pointer = bridge._build_shell_replay_pointer(
        task=KernelTask(
            id="ctask:cu:20260312070211912789-1d103753:1",
            title="Replay shell command",
            capability_ref="tool:execute_shell_command",
            owner_agent_id="ops-agent",
            risk_level="guarded",
        ),
        payload={"cwd": "D:/word/copaw", "timeout": 30},
        environment_ref="D:/word/copaw",
        command="echo hello",
    )

    assert pointer is not None
    replay_files = list((tmp_path / "evidence" / "replays").glob("*.json"))
    assert len(replay_files) == 1
    assert ":" not in replay_files[0].name


def test_tool_bridge_preserves_blocked_status_and_contract_metadata() -> None:
    class _FakeTaskStore:
        def __init__(self) -> None:
            self.task = KernelTask(
                id="ktask:blocked-shell",
                title="Blocked shell evidence",
                capability_ref="tool:execute_shell_command",
                owner_agent_id="ops-agent",
                risk_level="guarded",
            )
            self.appended: list[dict[str, object]] = []
            self.upserts: list[dict[str, object]] = []

        def get(self, task_id: str) -> KernelTask | None:
            return self.task if task_id == self.task.id else None

        def append_evidence(self, task: KernelTask, **kwargs):
            self.appended.append(kwargs)
            return SimpleNamespace(id="evidence-1")

        def upsert(self, task: KernelTask, **kwargs) -> None:
            self.upserts.append(kwargs)

    store = _FakeTaskStore()
    bridge = KernelToolBridge(task_store=store)

    bridge.record_shell_event(
        "ktask:blocked-shell",
        {
            "status": "blocked",
            "command": "git reset --hard HEAD",
            "stderr": "Blocked by shell safety policy: git reset --hard HEAD",
            "tool_contract": "tool:execute_shell_command",
            "concurrency_class": "serial-write",
            "preflight_policy": "shell-safety",
            "outcome_kind": "blocked",
            "read_only": False,
        },
    )

    assert store.appended
    appended = store.appended[0]
    assert appended["status"] == "blocked"
    assert appended["metadata"]["tool_contract"] == "tool:execute_shell_command"
    assert appended["metadata"]["concurrency_class"] == "serial-write"
    assert appended["metadata"]["preflight_policy"] == "shell-safety"
    assert appended["metadata"]["outcome_kind"] == "blocked"
    assert store.upserts[0]["last_error_summary"].startswith("Shell command blocked")
