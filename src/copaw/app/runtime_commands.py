# -*- coding: utf-8 -*-
"""Kernel-side command dispatch helpers for interactive turns."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from agentscope.message import Msg, TextBlock
from reme.memory.file_based.reme_in_memory_memory import ReMeInMemoryMemory

from ..agents.command_handler import CommandHandler
from ..agents.utils.token_counting import _get_token_counter
from ..config import load_config
from .daemon_commands import (
    DaemonCommandHandlerMixin,
    DaemonContext,
    parse_daemon_query,
)

logger = logging.getLogger(__name__)


def get_last_user_text(msgs) -> str | None:
    """Extract last user message text from runtime messages."""
    if not msgs:
        return None
    last = msgs[-1]
    if hasattr(last, "get_text_content"):
        return last.get_text_content()
    if isinstance(last, dict):
        content = last.get("content") or last.get("text")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text")
    return None


def is_conversation_command(query: str | None) -> bool:
    """True when query is a conversation command such as `/compact`."""
    if not query or not query.startswith("/"):
        return False
    command = query.strip().lstrip("/").split()[0] if query.strip() else ""
    return command in CommandHandler.SYSTEM_COMMANDS


def is_command(query: str | None) -> bool:
    """True when query is any supported daemon or conversation command."""
    if not query or not query.startswith("/"):
        return False
    if parse_daemon_query(query) is not None:
        return True
    return is_conversation_command(query)


def infer_turn_capability_and_risk(query: str | None) -> tuple[str, str]:
    """Infer the kernel capability and risk level for one user turn."""
    if not is_command(query):
        return "system:dispatch_query", "auto"

    parsed = parse_daemon_query(query or "")
    if parsed is None:
        return "system:dispatch_command", "auto"

    subcommand = parsed[0]
    if subcommand in {
        "restart",
        "reload-config",
        "sidecar-restart",
        "sidecar-interrupt",
        "sidecar-approve",
        "sidecar-reject",
    }:
        return "system:dispatch_command", "confirm"
    if subcommand in {"logs", "status", "version", "sidecar-status"}:
        return "system:dispatch_command", "guarded"
    return "system:dispatch_command", "guarded"


class _LightweightSessionAgent:
    """Minimal agent-like object for session load/save during command turns."""

    def __init__(self, memory: ReMeInMemoryMemory) -> None:
        self.memory = memory

    def state_dict(self) -> dict:
        return {"memory": self.memory.state_dict()}

    def load_state_dict(self, state_dict: dict, strict: bool = True) -> None:
        memory_state = state_dict.get("memory", state_dict)
        self.memory.load_state_dict(memory_state, strict=strict)


async def run_command_path(
    *,
    request,
    msgs,
    session_backend,
    conversation_compaction_service,
    restart_callback,
    executor_runtime_coordinator=None,
) -> AsyncIterator[tuple]:
    """Run daemon/conversation commands without entering the full query path."""
    query = get_last_user_text(msgs)
    if not query:
        return

    session_id = getattr(request, "session_id", "") or ""
    user_id = getattr(request, "user_id", "") or ""

    parsed = parse_daemon_query(query)
    if parsed is not None:
        handler = DaemonCommandHandlerMixin()
        if parsed[0] == "restart":
            logger.info(
                "run_command_path: daemon restart, callback=%s",
                "set" if restart_callback is not None else "None",
            )
            yield (
                Msg(
                    name="Spider Mesh",
                    role="assistant",
                    content=[
                        TextBlock(
                            type="text",
                            text=(
                                "**Restart in progress**\n\n"
                                "- The service may be unresponsive for a while. "
                                "Please wait."
                            ),
                        ),
                    ],
                ),
                True,
            )
        context = DaemonContext(
            load_config_fn=load_config,
            conversation_compaction_service=conversation_compaction_service,
            restart_callback=restart_callback,
            executor_runtime_coordinator=executor_runtime_coordinator,
        )
        message = await handler.handle_daemon_command(query, context)
        yield message, True
        logger.info("handle_daemon_command %s completed", query)
        return

    memory = ReMeInMemoryMemory(token_counter=_get_token_counter())
    lightweight_agent = _LightweightSessionAgent(memory=memory)
    if session_id and user_id:
        try:
            await session_backend.load_session_state(
                session_id=session_id,
                user_id=user_id,
                agent=lightweight_agent,
            )
        except ValueError:
            pass

    conversation_handler = CommandHandler(
        agent_name="Spider Mesh",
        memory=lightweight_agent.memory,
        conversation_compaction_service=conversation_compaction_service,
        enable_memory_compaction=conversation_compaction_service is not None,
    )
    try:
        response_msg = await conversation_handler.handle_conversation_command(query)
    except RuntimeError as exc:
        response_msg = Msg(
            name="Spider Mesh",
            role="assistant",
            content=[TextBlock(type="text", text=str(exc))],
        )
    yield response_msg, True

    if session_id and user_id:
        await session_backend.save_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=lightweight_agent,
        )


__all__ = [
    "get_last_user_text",
    "infer_turn_capability_and_risk",
    "is_command",
    "is_conversation_command",
    "run_command_path",
]
