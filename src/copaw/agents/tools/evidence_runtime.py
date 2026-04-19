# -*- coding: utf-8 -*-
"""Runtime-local evidence hooks for tool execution.

This module keeps evidence injection optional and decoupled from app state.
Tools can emit normalized event payloads when a sink is bound in the current
execution context; otherwise they keep their original behavior.
"""
from __future__ import annotations

import inspect
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator, Literal

logger = logging.getLogger(__name__)

ShellEvidenceStatus = Literal["success", "error", "timeout", "blocked"]
ShellEvidenceSink = Callable[[dict[str, Any]], Any]
BrowserEvidenceStatus = Literal["success", "error"]
BrowserEvidenceSink = Callable[[dict[str, Any]], Any]
DesktopEvidenceStatus = Literal["success", "error"]
DesktopEvidenceSink = Callable[[dict[str, Any]], Any]
FileEvidenceStatus = Literal["success", "error"]
FileEvidenceSink = Callable[[dict[str, Any]], Any]

_shell_evidence_sink: ContextVar[ShellEvidenceSink | None] = ContextVar(
    "shell_evidence_sink",
    default=None,
)
_browser_evidence_sink: ContextVar[BrowserEvidenceSink | None] = ContextVar(
    "browser_evidence_sink",
    default=None,
)
_desktop_evidence_sink: ContextVar[DesktopEvidenceSink | None] = ContextVar(
    "desktop_evidence_sink",
    default=None,
)
_file_evidence_sink: ContextVar[FileEvidenceSink | None] = ContextVar(
    "file_evidence_sink",
    default=None,
)


@dataclass(frozen=True)
class ShellEvidenceEvent:
    """Normalized shell execution event payload."""

    command: str
    cwd: str
    timeout_seconds: int
    status: ShellEvidenceStatus
    returncode: int
    stdout: str
    stderr: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    timed_out: bool = False
    rule_id: str | None = None
    tool_name: str = "execute_shell_command"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Convert event to a JSON-friendly payload."""
        return {
            "tool_name": self.tool_name,
            "command": self.command,
            "cwd": self.cwd,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
            "rule_id": self.rule_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrowserEvidenceEvent:
    """Normalized browser action event payload."""

    action: str
    page_id: str
    status: BrowserEvidenceStatus
    result_summary: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    url: str | None = None
    tool_name: str = "browser_use"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Convert event to a JSON-friendly payload."""
        return {
            "tool_name": self.tool_name,
            "action": self.action,
            "page_id": self.page_id,
            "status": self.status,
            "result_summary": self.result_summary,
            "url": self.url,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_ms": self.duration_ms,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DesktopEvidenceEvent:
    """Normalized desktop action event payload."""

    action: str
    app_identity: str
    status: DesktopEvidenceStatus
    result_summary: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    selector: str | None = None
    session_mount_id: str | None = None
    tool_name: str = "desktop_actuation"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "action": self.action,
            "app_identity": self.app_identity,
            "status": self.status,
            "result_summary": self.result_summary,
            "selector": self.selector,
            "session_mount_id": self.session_mount_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_ms": self.duration_ms,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class FileEvidenceEvent:
    """Normalized file tool execution event payload."""

    action: Literal["write", "edit", "append"]
    file_path: str
    resolved_path: str
    status: FileEvidenceStatus
    result_summary: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    bytes_written: int = 0
    tool_name: str = "file_io"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Convert event to a JSON-friendly payload."""
        return {
            "tool_name": self.tool_name,
            "action": self.action,
            "file_path": self.file_path,
            "resolved_path": self.resolved_path,
            "status": self.status,
            "result_summary": self.result_summary,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_ms": self.duration_ms,
            "bytes_written": self.bytes_written,
            "metadata": dict(self.metadata),
        }


@contextmanager
def bind_shell_evidence_sink(
    sink: ShellEvidenceSink | None,
) -> Iterator[None]:
    """Bind a shell evidence sink for the current async context."""
    previous = _shell_evidence_sink.get()
    _shell_evidence_sink.set(sink)
    try:
        yield
    finally:
        _shell_evidence_sink.set(previous)


def get_shell_evidence_sink() -> ShellEvidenceSink | None:
    """Return the currently bound shell evidence sink, if any."""
    return _shell_evidence_sink.get()


@contextmanager
def bind_browser_evidence_sink(
    sink: BrowserEvidenceSink | None,
) -> Iterator[None]:
    """Bind a browser evidence sink for the current async context."""
    previous = _browser_evidence_sink.get()
    _browser_evidence_sink.set(sink)
    try:
        yield
    finally:
        _browser_evidence_sink.set(previous)


def get_browser_evidence_sink() -> BrowserEvidenceSink | None:
    """Return the currently bound browser evidence sink, if any."""
    return _browser_evidence_sink.get()


@contextmanager
def bind_desktop_evidence_sink(
    sink: DesktopEvidenceSink | None,
) -> Iterator[None]:
    """Bind a desktop evidence sink for the current async context."""
    previous = _desktop_evidence_sink.get()
    _desktop_evidence_sink.set(sink)
    try:
        yield
    finally:
        _desktop_evidence_sink.set(previous)


def get_desktop_evidence_sink() -> DesktopEvidenceSink | None:
    """Return the currently bound desktop evidence sink, if any."""
    return _desktop_evidence_sink.get()


@contextmanager
def bind_file_evidence_sink(
    sink: FileEvidenceSink | None,
) -> Iterator[None]:
    """Bind a file evidence sink for the current async context."""
    previous = _file_evidence_sink.get()
    _file_evidence_sink.set(sink)
    try:
        yield
    finally:
        _file_evidence_sink.set(previous)


def get_file_evidence_sink() -> FileEvidenceSink | None:
    """Return the currently bound file evidence sink, if any."""
    return _file_evidence_sink.get()


async def emit_shell_evidence(event: ShellEvidenceEvent) -> None:
    """Best-effort emit for shell evidence.

    Sink failures are swallowed so tool behavior stays unchanged.
    """
    sink = get_shell_evidence_sink()
    if sink is None:
        return

    try:
        result = sink(event.to_payload())
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.warning(
            "shell evidence sink failed; keeping tool response unchanged",
            exc_info=True,
        )


async def emit_browser_evidence(event: BrowserEvidenceEvent) -> None:
    """Best-effort emit for browser evidence.

    Sink failures are swallowed so tool behavior stays unchanged.
    """
    sink = get_browser_evidence_sink()
    if sink is None:
        return

    try:
        result = sink(event.to_payload())
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.warning(
            "browser evidence sink failed; keeping tool response unchanged",
            exc_info=True,
        )


async def emit_desktop_evidence(event: DesktopEvidenceEvent) -> None:
    """Best-effort emit for desktop evidence."""
    sink = get_desktop_evidence_sink()
    if sink is None:
        return

    try:
        result = sink(event.to_payload())
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.warning(
            "desktop evidence sink failed; keeping tool response unchanged",
            exc_info=True,
        )


async def emit_file_evidence(event: FileEvidenceEvent) -> None:
    """Best-effort emit for file tool evidence.

    Sink failures are swallowed so tool behavior stays unchanged.
    """
    sink = get_file_evidence_sink()
    if sink is None:
        return

    try:
        result = sink(event.to_payload())
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.warning(
            "file evidence sink failed; keeping tool response unchanged",
            exc_info=True,
        )
