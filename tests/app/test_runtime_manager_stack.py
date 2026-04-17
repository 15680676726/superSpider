# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from copaw.app import runtime_manager_stack as runtime_manager_stack_module


def test_start_runtime_manager_stack_passes_research_session_service_to_cron_manager(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeChannelManager:
        async def start_all(self) -> None:
            captured["channel_started"] = True

    class _FakeCronManager:
        def __init__(self, **kwargs) -> None:
            captured["cron_kwargs"] = kwargs

        async def start(self) -> None:
            captured["cron_started"] = True

    class _FakeConfigWatcher:
        def __init__(self, **kwargs) -> None:
            captured["config_watcher_kwargs"] = kwargs

        async def start(self) -> None:
            captured["config_started"] = True

    monkeypatch.setattr(
        runtime_manager_stack_module.ChannelManager,
        "from_config",
        staticmethod(lambda **kwargs: _FakeChannelManager()),
    )
    monkeypatch.setattr(
        runtime_manager_stack_module,
        "StateBackedJobRepository",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        runtime_manager_stack_module,
        "CronManager",
        _FakeCronManager,
    )
    monkeypatch.setattr(
        runtime_manager_stack_module,
        "ConfigWatcher",
        _FakeConfigWatcher,
    )

    class _CapabilityService:
        def set_channel_manager(self, value) -> None:
            captured["channel_manager"] = value

        def set_cron_manager(self, value) -> None:
            captured["capability_cron_manager"] = value

    class _GovernanceService:
        def set_runtime_managers(self, **kwargs) -> None:
            captured["runtime_managers"] = kwargs

        async def reconcile_runtime_state(self) -> None:
            captured["reconciled"] = True

    async def run() -> None:
        await runtime_manager_stack_module.start_runtime_manager_stack(
            config=SimpleNamespace(),
            kernel_dispatcher=object(),
            capability_service=_CapabilityService(),
            governance_service=_GovernanceService(),
            schedule_repository=object(),
            mcp_manager=object(),
            memory_sleep_service=object(),
            research_session_service="research-service",
            logger=logging.getLogger("test"),
            strict_mcp_watcher=True,
        )

    asyncio.run(run())

    assert captured["cron_kwargs"]["research_session_service"] == "research-service"
