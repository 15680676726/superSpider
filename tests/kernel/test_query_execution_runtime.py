# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.agents.react_agent import (
    bind_reasoning_tool_choice_resolver,
    bind_tool_preflight,
)
from copaw.agents.tools.evidence_runtime import (
    bind_browser_evidence_sink,
    bind_file_evidence_sink,
    bind_shell_evidence_sink,
)


async def _yield_once_with_runtime_bindings() -> None:
    with bind_reasoning_tool_choice_resolver(lambda: "required"):
        with bind_tool_preflight(lambda *_args, **_kwargs: None):
            with bind_shell_evidence_sink(lambda _payload: None):
                with bind_file_evidence_sink(lambda _payload: None):
                    with bind_browser_evidence_sink(lambda _payload: None):
                        yield


def test_runtime_context_bindings_survive_cross_task_generator_close() -> None:
    async def _scenario() -> None:
        stream = _yield_once_with_runtime_bindings()
        await anext(stream)

        async def _close_in_another_task() -> None:
            await stream.aclose()

        await asyncio.create_task(_close_in_another_task())

    asyncio.run(_scenario())
