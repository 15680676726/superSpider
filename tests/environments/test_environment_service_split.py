# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.environments import EnvironmentService


def test_environment_service_installs_internal_collaborators() -> None:
    service = EnvironmentService()

    assert hasattr(service, "_session_service")
    assert hasattr(service, "_lease_service")
    assert hasattr(service, "_replay_service")
    assert hasattr(service, "_artifact_service")
    assert hasattr(service, "_health_service")


def test_environment_service_list_sessions_delegates_to_internal_session_service() -> None:
    service = EnvironmentService()

    class StubSessionService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def list_sessions(self, **kwargs):
            self.calls.append(kwargs)
            return ["delegated"]

    stub = StubSessionService()
    service._session_service = stub  # type: ignore[attr-defined]

    result = service.list_sessions(
        environment_id="env-1",
        channel="console",
        user_id="u1",
        status="active",
        limit=5,
    )

    assert result == ["delegated"]
    assert stub.calls == [
        {
            "environment_id": "env-1",
            "channel": "console",
            "user_id": "u1",
            "status": "active",
            "limit": 5,
        },
    ]


def test_environment_service_execute_replay_delegates_to_internal_replay_service() -> None:
    service = EnvironmentService()

    class StubReplayService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def execute_replay(self, replay_id: str, *, actor: str = "runtime-center"):
            self.calls.append((replay_id, actor))
            return {"mode": "delegated", "replay_id": replay_id}

    stub = StubReplayService()
    service._replay_service = stub  # type: ignore[attr-defined]

    result = asyncio.run(service.execute_replay("replay-1", actor="tester"))

    assert result == {"mode": "delegated", "replay_id": "replay-1"}
    assert stub.calls == [("replay-1", "tester")]


def test_environment_service_get_environment_detail_delegates_to_internal_health_service() -> None:
    service = EnvironmentService()

    class StubHealthService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def get_environment_detail(self, env_id: str, *, limit: int = 20):
            self.calls.append((env_id, limit))
            return {"id": env_id, "limit": limit, "delegated": True}

    stub = StubHealthService()
    service._health_service = stub  # type: ignore[attr-defined]

    result = service.get_environment_detail("env:browser:https://example.com", limit=3)

    assert result == {
        "id": "env:browser:https://example.com",
        "limit": 3,
        "delegated": True,
    }
    assert stub.calls == [("env:browser:https://example.com", 3)]
