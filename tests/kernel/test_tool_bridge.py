# -*- coding: utf-8 -*-
from __future__ import annotations

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
