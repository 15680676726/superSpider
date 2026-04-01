# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import dataclass

from click.testing import CliRunner

import copaw.cli.capabilities_cmd as capabilities_cmd_module
import copaw.cli.main as cli_main_module


@dataclass
class FakeResponse:
    payload: object
    status_code: int = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, sink: list[dict[str, object]], response_payload: object) -> None:
        self._sink = sink
        self._response_payload = response_payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, path: str, params=None):
        self._sink.append({"method": "GET", "path": path, "params": params})
        return FakeResponse(self._response_payload)

    def post(self, path: str, json=None):
        self._sink.append({"method": "POST", "path": path, "json": json})
        return FakeResponse(self._response_payload)


def test_capabilities_cli_execute_acceptance_matrix(monkeypatch) -> None:
    runner = CliRunner()
    cases = [
        ("skill:test-skill", {"action": "describe"}),
        ("mcp:browser", {"tool_name": "open_page", "tool_args": {"url": "https://example.com"}}),
        (
            "system:dispatch_query",
            {
                "request": {
                    "input": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "hello"}],
                        },
                    ],
                    "session_id": "goal-1",
                    "user_id": "ops-agent",
                    "channel": "goal",
                },
                "mode": "final",
                "dispatch_events": False,
            },
        ),
    ]

    for capability_id, payload in cases:
        calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            capabilities_cmd_module,
            "client",
            lambda base_url, _calls=calls, _cid=capability_id: FakeHttpClient(
                _calls,
                {"capability_id": _cid, "ok": True},
            ),
        )
        result = runner.invoke(
            capabilities_cmd_module.capabilities_group,
            ["execute", capability_id, "--payload-json", json.dumps(payload)],
        )

        assert result.exit_code != 0
        assert "capabilities execute" in result.output
        assert "主脑聊天窗口" in result.output
        assert calls == []


def test_main_cli_help_no_longer_lists_goals_group() -> None:
    result = CliRunner().invoke(cli_main_module.cli, ["--help"])

    assert result.exit_code == 0
    assert "goals" not in result.output


def test_main_cli_no_longer_registers_goals_group() -> None:
    result = CliRunner().invoke(cli_main_module.cli, ["goals", "--help"])

    assert result.exit_code != 0
    assert "No such command 'goals'" in result.output
