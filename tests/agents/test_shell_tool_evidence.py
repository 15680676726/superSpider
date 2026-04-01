# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.agents.tools.evidence_runtime import bind_shell_evidence_sink
from copaw.agents.tools.shell import execute_shell_command


def test_execute_shell_command_keeps_default_behavior_without_sink(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        lambda cmd, cwd, timeout: (0, "hello world", ""),
    )

    response = asyncio.run(execute_shell_command("echo hello", cwd=tmp_path))

    assert response.content[0]["text"] == "hello world"


def test_execute_shell_command_emits_success_payload(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        lambda cmd, cwd, timeout: (0, "hello world", ""),
    )
    payloads: list[dict[str, object]] = []

    async def run() -> None:
        with bind_shell_evidence_sink(payloads.append):
            response = await execute_shell_command("echo hello", cwd=tmp_path)
        assert response.content[0]["text"] == "hello world"

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["tool_name"] == "execute_shell_command"
    assert payloads[0]["command"] == "echo hello"
    assert payloads[0]["status"] == "success"
    assert payloads[0]["returncode"] == 0
    assert payloads[0]["stdout"] == "hello world"
    assert payloads[0]["stderr"] == ""
    assert payloads[0]["cwd"] == str(tmp_path)
    assert payloads[0]["timed_out"] is False
    assert payloads[0]["started_at"]
    assert payloads[0]["finished_at"]
    assert payloads[0]["duration_ms"] >= 0


def test_execute_shell_command_emits_error_payload(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        lambda cmd, cwd, timeout: (-1, "", "shell exploded"),
    )
    payloads: list[dict[str, object]] = []

    async def run() -> None:
        with bind_shell_evidence_sink(payloads.append):
            response = await execute_shell_command("bad command", cwd=tmp_path)
        assert "Command failed with exit code -1." in response.content[0]["text"]

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["status"] == "error"
    assert payloads[0]["command"] == "bad command"
    assert payloads[0]["stderr"] == "shell exploded"
    assert payloads[0]["timed_out"] is False
    assert payloads[0]["duration_ms"] >= 0


def test_execute_shell_command_emits_timeout_payload_with_async_sink(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        lambda cmd, cwd, timeout: (
            -1,
            "",
            "Command execution exceeded the timeout of 5 seconds.",
        ),
    )
    payloads: list[dict[str, object]] = []

    async def sink(payload: dict[str, object]) -> None:
        payloads.append(payload)

    async def run() -> None:
        with bind_shell_evidence_sink(sink):
            response = await execute_shell_command(
                "sleep 10",
                timeout=5,
                cwd=tmp_path,
            )
        assert "Command failed with exit code -1." in response.content[0]["text"]

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["status"] == "timeout"
    assert payloads[0]["command"] == "sleep 10"
    assert payloads[0]["timed_out"] is True
    assert payloads[0]["timeout_seconds"] == 5
    assert payloads[0]["duration_ms"] >= 0


def test_execute_shell_command_emits_blocked_payload_without_running_subprocess(
    monkeypatch,
    tmp_path,
) -> None:
    calls: list[tuple[str, str, int]] = []

    def _fake_subprocess(cmd: str, cwd: str, timeout: int):
        calls.append((cmd, cwd, timeout))
        return (0, "should not run", "")

    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        _fake_subprocess,
    )
    payloads: list[dict[str, object]] = []

    async def run() -> None:
        with bind_shell_evidence_sink(payloads.append):
            response = await execute_shell_command(
                "git reset --hard HEAD",
                cwd=tmp_path,
            )
        text = response.content[0]["text"]
        assert "blocked" in text.lower()
        assert "git reset --hard head" in text.lower()

    asyncio.run(run())

    assert calls == []
    assert len(payloads) == 1
    assert payloads[0]["status"] == "blocked"
    assert payloads[0]["command"] == "git reset --hard HEAD"
    assert payloads[0]["rule_id"] == "destructive-git"
    assert payloads[0]["timed_out"] is False
