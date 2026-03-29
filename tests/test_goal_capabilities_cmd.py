# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import dataclass

from click.testing import CliRunner

import copaw.cli.capabilities_cmd as capabilities_cmd_module
import copaw.cli.goals_cmd as goals_cmd_module


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


def test_goals_cli_dispatch_command_is_removed(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        goals_cmd_module,
        "client",
        lambda base_url: FakeHttpClient(calls, {"goal": {"id": "goal-1"}, "dispatch_results": []}),
    )

    result = CliRunner().invoke(
        goals_cmd_module.goals_group,
        [
            "dispatch",
            "goal-1",
            "--execute",
            "--owner-agent-id",
            "ops-agent",
            "--context-json",
            '{"source":"cli"}',
        ],
    )

    assert result.exit_code != 0
    assert "No such command 'dispatch'" in result.output
    assert calls == []
