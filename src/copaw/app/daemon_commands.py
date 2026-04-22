# -*- coding: utf-8 -*-
"""Daemon command execution layer shared by chat and CLI surfaces."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from agentscope.message import Msg, TextBlock

from ..config import load_config
from ..constant import WORKING_DIR

RestartCallback = Callable[[], Awaitable[None]]
logger = logging.getLogger(__name__)


class RestartInProgressError(Exception):
    """Raised when /daemon restart is invoked while another restart runs."""


DAEMON_PREFIX = "/daemon"
DAEMON_SUBCOMMANDS = frozenset(
    {
        "status",
        "restart",
        "reload-config",
        "version",
        "logs",
        "sidecar-status",
        "sidecar-restart",
        "sidecar-interrupt",
        "sidecar-approve",
        "sidecar-reject",
        "sidecar-version",
        "sidecar-upgrade",
        "sidecar-rollback",
    },
)
DAEMON_SHORT_ALIASES = {
    "restart": "restart",
    "status": "status",
    "reload-config": "reload-config",
    "reload_config": "reload-config",
    "version": "version",
    "logs": "logs",
    "sidecar_status": "sidecar-status",
    "sidecar_restart": "sidecar-restart",
    "sidecar_interrupt": "sidecar-interrupt",
    "sidecar_approve": "sidecar-approve",
    "sidecar_reject": "sidecar-reject",
    "sidecar_version": "sidecar-version",
    "sidecar_upgrade": "sidecar-upgrade",
    "sidecar_rollback": "sidecar-rollback",
}


@dataclass
class DaemonContext:
    """Context for daemon commands injected from the runtime host or CLI."""

    working_dir: Path = WORKING_DIR
    load_config_fn: Callable[[], Any] = load_config
    conversation_compaction_service: Optional[Any] = None
    restart_callback: Optional[RestartCallback] = None
    executor_runtime_coordinator: Optional[Any] = None
    sidecar_release_service: Optional[Any] = None


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _get_last_lines(
    path: Path,
    lines: int = 100,
    max_bytes: int = 512 * 1024,
) -> str:
    """Read the last N lines from a bounded tail of a text file."""
    path = Path(path)
    if not path.exists() or not path.is_file():
        return f"(Log file not found: {path})"
    try:
        size = path.stat().st_size
        if size == 0:
            return "(empty)"
        with open(path, "rb") as handle:
            if size <= max_bytes:
                content = handle.read().decode("utf-8", errors="replace")
            else:
                handle.seek(size - max_bytes)
                content = handle.read().decode("utf-8", errors="replace")
                first_newline = content.find("\n")
                if first_newline != -1:
                    content = content[first_newline + 1 :]
                else:
                    content = ""
        all_lines = content.splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "\n".join(tail) if tail else "(empty)"
    except OSError as exc:
        return f"(Error reading log: {exc})"


def run_daemon_status(context: DaemonContext) -> str:
    """Return current daemon status text."""
    parts = ["**Daemon Status**", ""]
    try:
        config = context.load_config_fn()
        parts.append("- Config loaded: yes")
        if getattr(config, "agents", None) and getattr(config.agents, "running", None):
            max_input_length = getattr(config.agents.running, "max_input_length", "N/A")
            parts.append(f"- Max input length: {max_input_length}")
    except Exception as exc:  # pragma: no cover - defensive formatting
        parts.append(f"- Config loaded: no ({exc})")

    parts.append(f"- Working dir: {context.working_dir}")
    if context.conversation_compaction_service is not None:
        parts.append("- Conversation compaction: running")
    else:
        parts.append("- Conversation compaction: not attached")
    return "\n".join(parts)


async def run_daemon_restart(context: DaemonContext) -> str:
    """Trigger in-process restart when the runtime host provides a callback."""
    if context.restart_callback is not None:
        try:
            await context.restart_callback()
            return (
                "**Restart completed**\n\n"
                "- Channels, cron and MCP reloaded in-process (no exit)."
            )
        except RestartInProgressError:
            return (
                "**Restart skipped**\n\n"
                "- A restart is already in progress. Please wait for it to finish."
            )
        except Exception as exc:  # pragma: no cover - defensive formatting
            return f"**Restart failed**\n\n- {exc}"
    return (
        "**Restart**\n\n"
        "- No restart callback (e.g. not running inside app). "
        "Run the app (e.g. `copaw app`) and use /daemon restart in chat, "
        "or restart the process with systemd/supervisor/docker."
    )


def run_daemon_reload_config(context: DaemonContext) -> str:
    """Reload config without restarting the process."""
    try:
        context.load_config_fn()
        return "**Config reloaded**\n\n- load_config() re-invoked successfully."
    except Exception as exc:  # pragma: no cover - defensive formatting
        return f"**Reload failed**\n\n- {exc}"


def run_daemon_version(context: DaemonContext) -> str:
    """Return daemon version and key paths."""
    try:
        from ..__version__ import __version__ as version
    except ImportError:
        version = "unknown"
    return (
        f"**Daemon version**\n\n"
        f"- Version: {version}\n"
        f"- Working dir: {context.working_dir}\n"
        f"- Log file: {context.working_dir / 'copaw.log'}"
    )


def run_daemon_logs(context: DaemonContext, lines: int = 100) -> str:
    """Tail last N lines from WORKING_DIR/copaw.log."""
    log_path = context.working_dir / "copaw.log"
    content = _get_last_lines(log_path, lines=lines)
    return f"**Console log (last {lines} lines)**\n\n```\n{content}\n```"


def run_daemon_sidecar_status(context: DaemonContext) -> str:
    coordinator = context.executor_runtime_coordinator
    describe = getattr(coordinator, "describe_sidecar_control_state", None)
    if not callable(describe):
        return (
            "**Sidecar Status**\n\n"
            "- Executor runtime coordinator is not attached."
        )
    payload = _mapping(describe())
    sidecar = _mapping(payload.get("sidecar"))
    active_runtime = _mapping(payload.get("active_runtime"))
    pending = list(payload.get("pending_approvals") or [])
    connected = "yes" if bool(sidecar.get("connected")) else "no"
    lines = ["**Sidecar Status**", ""]
    lines.append(f"- Connected: {connected}")
    lines.append(f"- Transport: {_text(sidecar.get('transport_kind')) or 'unknown'}")
    lines.append(f"- Restart count: {int(sidecar.get('restart_count') or 0)}")
    lines.append(f"- Pending approvals: {len(pending)}")
    if active_runtime:
        lines.append(f"- Runtime status: {_text(active_runtime.get('runtime_status')) or 'unknown'}")
        lines.append(f"- Thread id: {_text(active_runtime.get('thread_id')) or 'n/a'}")
        lines.append(f"- Turn id: {_text(active_runtime.get('turn_id')) or 'n/a'}")
    return "\n".join(lines)


def run_daemon_sidecar_restart(context: DaemonContext) -> str:
    coordinator = context.executor_runtime_coordinator
    restart = getattr(coordinator, "restart_sidecar", None)
    if not callable(restart):
        return (
            "**Sidecar Restart**\n\n"
            "- Executor runtime coordinator is not attached."
        )
    payload = _mapping(restart())
    return (
        "**Sidecar Restart**\n\n"
        f"- Connected: {'yes' if bool(payload.get('connected')) else 'no'}\n"
        f"- Restart count: {int(payload.get('restart_count') or 0)}"
    )


def run_daemon_sidecar_interrupt(
    context: DaemonContext,
    *,
    thread_id: str | None = None,
    turn_id: str | None = None,
    assignment_id: str | None = None,
) -> str:
    coordinator = context.executor_runtime_coordinator
    interrupt = getattr(coordinator, "interrupt_active_turn", None)
    if not callable(interrupt):
        return (
            "**Sidecar Interrupt**\n\n"
            "- Executor runtime coordinator is not attached."
        )
    payload = _mapping(
        interrupt(
            thread_id=thread_id,
            turn_id=turn_id,
            assignment_id=assignment_id,
        )
    )
    return (
        "**Sidecar Interrupt**\n\n"
        f"- Status: {_text(payload.get('status')) or 'unknown'}\n"
        f"- Thread id: {_text(payload.get('thread_id')) or 'n/a'}\n"
        f"- Turn id: {_text(payload.get('turn_id')) or 'n/a'}"
    )


def run_daemon_sidecar_approval(
    context: DaemonContext,
    *,
    request_id: str,
    decision: str,
    reason: str | None = None,
) -> str:
    coordinator = context.executor_runtime_coordinator
    responder = getattr(coordinator, "respond_to_sidecar_approval", None)
    if not callable(responder):
        return (
            "**Sidecar Approval**\n\n"
            "- Executor runtime coordinator is not attached."
        )
    payload = _mapping(
        responder(
            request_id,
            decision=decision,
            reason=reason,
        )
    )
    return (
        "**Sidecar Approval**\n\n"
        f"- Request id: {_text(payload.get('request_id')) or request_id}\n"
        f"- Status: {_text(payload.get('status')) or decision}\n"
        f"- Reason: {_text(payload.get('reason')) or 'n/a'}"
    )


def run_daemon_sidecar_version(context: DaemonContext) -> str:
    service = context.sidecar_release_service
    describe = getattr(service, "describe_version_governance", None)
    if not callable(describe):
        return (
            "**Sidecar Version**\n\n"
            "- Sidecar release service is not attached."
        )
    payload = _mapping(describe(runtime_family="codex", channel="stable"))
    current_install = _mapping(payload.get("current_install"))
    compatibility = _mapping(payload.get("compatibility"))
    available_upgrade = _mapping(payload.get("available_upgrade"))
    return (
        "**Sidecar Version**\n\n"
        f"- Current version: {_text(current_install.get('version')) or 'n/a'}\n"
        f"- Compatibility: {_text(compatibility.get('status')) or 'unknown'}\n"
        f"- Available upgrade: {_text(available_upgrade.get('version')) or 'none'}"
    )


def run_daemon_sidecar_upgrade(context: DaemonContext) -> str:
    service = context.sidecar_release_service
    upgrade = getattr(service, "upgrade_sidecar", None)
    if not callable(upgrade):
        return (
            "**Sidecar Upgrade**\n\n"
            "- Sidecar release service is not attached."
        )
    payload = _mapping(upgrade(runtime_family="codex", channel="stable"))
    return (
        "**Sidecar Upgrade**\n\n"
        f"- Status: {_text(payload.get('status')) or 'unknown'}\n"
        f"- Target version: {_text(payload.get('target_version')) or 'n/a'}"
    )


def run_daemon_sidecar_rollback(context: DaemonContext) -> str:
    service = context.sidecar_release_service
    rollback = getattr(service, "rollback_sidecar", None)
    if not callable(rollback):
        return (
            "**Sidecar Rollback**\n\n"
            "- Sidecar release service is not attached."
        )
    payload = _mapping(rollback(runtime_family="codex", channel="stable"))
    return (
        "**Sidecar Rollback**\n\n"
        f"- Status: {_text(payload.get('status')) or 'unknown'}\n"
        f"- Active version: {_text(payload.get('active_version')) or 'n/a'}"
    )


def parse_daemon_query(query: str) -> Optional[tuple[str, list[str]]]:
    """Parse `/daemon <sub>` or `/restart` style aliases."""
    if not query or not isinstance(query, str):
        return None
    raw = query.strip()
    if not raw.startswith("/"):
        return None
    rest = raw.lstrip("/").strip()
    if not rest:
        return None
    parts = rest.split()
    first = parts[0].lower() if parts else ""

    if first == "daemon":
        if len(parts) < 2:
            return ("status", [])
        subcommand = parts[1].lower().replace("_", "-")
        if subcommand not in DAEMON_SUBCOMMANDS and "reload" in subcommand:
            subcommand = "reload-config"
        if subcommand not in DAEMON_SUBCOMMANDS:
            return None
        arguments = parts[2:] if len(parts) > 2 else []
        return (subcommand, arguments)
    if first in DAEMON_SHORT_ALIASES:
        subcommand = DAEMON_SHORT_ALIASES[first]
        return (subcommand, parts[1:] if len(parts) > 1 else [])
    return None


class DaemonCommandHandlerMixin:
    """Handle `/daemon` commands as assistant messages."""

    def is_daemon_command(self, query: str | None) -> bool:
        return parse_daemon_query(query or "") is not None

    async def handle_daemon_command(
        self,
        query: str,
        context: DaemonContext,
    ) -> Msg:
        parsed = parse_daemon_query(query)
        if not parsed:
            return Msg(
                name="Spider Mesh",
                role="assistant",
                content=[TextBlock(type="text", text="Unknown daemon command.")],
            )
        subcommand, args = parsed
        if subcommand == "status":
            text = run_daemon_status(context)
        elif subcommand == "restart":
            text = await run_daemon_restart(context)
        elif subcommand == "reload-config":
            text = run_daemon_reload_config(context)
        elif subcommand == "version":
            text = run_daemon_version(context)
        elif subcommand == "logs":
            line_count = 100
            for arg in args:
                if arg.isdigit():
                    line_count = max(1, min(int(arg), 2000))
                    break
            text = run_daemon_logs(context, lines=line_count)
        elif subcommand == "sidecar-status":
            text = run_daemon_sidecar_status(context)
        elif subcommand == "sidecar-restart":
            text = run_daemon_sidecar_restart(context)
        elif subcommand == "sidecar-interrupt":
            thread_id = args[0] if len(args) > 0 else None
            turn_id = args[1] if len(args) > 1 else None
            assignment_id = args[2] if len(args) > 2 else None
            text = run_daemon_sidecar_interrupt(
                context,
                thread_id=thread_id,
                turn_id=turn_id,
                assignment_id=assignment_id,
            )
        elif subcommand in {"sidecar-approve", "sidecar-reject"}:
            if not args:
                text = "**Sidecar Approval**\n\n- Missing request id."
            else:
                text = run_daemon_sidecar_approval(
                    context,
                    request_id=args[0],
                    decision="approved" if subcommand == "sidecar-approve" else "rejected",
                    reason=" ".join(args[1:]).strip() or None,
                )
        elif subcommand == "sidecar-version":
            text = run_daemon_sidecar_version(context)
        elif subcommand == "sidecar-upgrade":
            text = run_daemon_sidecar_upgrade(context)
        elif subcommand == "sidecar-rollback":
            text = run_daemon_sidecar_rollback(context)
        else:
            text = "Unknown daemon subcommand."
        logger.info("handle_daemon_command %s completed", query)
        return Msg(
            name="Spider Mesh",
            role="assistant",
            content=[TextBlock(type="text", text=text)],
        )


__all__ = [
    "DAEMON_PREFIX",
    "DAEMON_SHORT_ALIASES",
    "DAEMON_SUBCOMMANDS",
    "DaemonCommandHandlerMixin",
    "DaemonContext",
    "RestartInProgressError",
    "parse_daemon_query",
    "run_daemon_logs",
    "run_daemon_reload_config",
    "run_daemon_restart",
    "run_daemon_sidecar_approval",
    "run_daemon_sidecar_interrupt",
    "run_daemon_sidecar_rollback",
    "run_daemon_sidecar_restart",
    "run_daemon_sidecar_status",
    "run_daemon_sidecar_upgrade",
    "run_daemon_sidecar_version",
    "run_daemon_status",
    "run_daemon_version",
]
