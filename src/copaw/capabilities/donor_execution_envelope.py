# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, Awaitable, Callable

from ..kernel.runtime_outcome import (
    is_blocked_runtime_error,
    is_cancellation_runtime_error,
    is_timeout_runtime_error,
)


def _normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _classify_error_type(error: str | None) -> str:
    if is_timeout_runtime_error(error):
        return "timeout_error"
    if is_cancellation_runtime_error(error):
        return "cancellation_error"
    if is_blocked_runtime_error(error):
        return "compatibility_error"
    return "runtime_error"


def _timeout_summary(label: str, action_timeout_sec: float | None) -> str:
    timeout_display = (
        f"{float(action_timeout_sec):g}s"
        if isinstance(action_timeout_sec, (int, float)) and action_timeout_sec > 0
        else "the configured timeout"
    )
    return f"{label} timed out after {timeout_display}."


async def run_donor_execution_envelope(
    *,
    label: str,
    awaitable_factory: Callable[[], Awaitable[Any]],
    action_timeout_sec: float | None,
    heartbeat_interval_sec: float | None = None,
    heartbeat_snapshot_factory: Callable[[], dict[str, Any] | None] | None = None,
    cancel_grace_sec: float | None = None,
) -> dict[str, Any]:
    heartbeat_snapshots: list[dict[str, Any]] = []
    heartbeat_task: asyncio.Task[None] | None = None
    action_task: asyncio.Task[Any] | None = None
    stop_heartbeat = asyncio.Event()

    async def _heartbeat_loop() -> None:
        if heartbeat_snapshot_factory is None:
            return
        snapshot = heartbeat_snapshot_factory()
        if isinstance(snapshot, dict) and snapshot:
            heartbeat_snapshots.append(dict(snapshot))
        while not stop_heartbeat.is_set():
            await asyncio.sleep(max(float(heartbeat_interval_sec or 0), 0.001))
            if stop_heartbeat.is_set():
                break
            snapshot = heartbeat_snapshot_factory()
            if isinstance(snapshot, dict) and snapshot:
                heartbeat_snapshots.append(dict(snapshot))

    try:
        action_task = asyncio.create_task(awaitable_factory())
        if heartbeat_snapshot_factory is not None and (heartbeat_interval_sec or 0) > 0:
            heartbeat_task = asyncio.create_task(_heartbeat_loop())
        output = await asyncio.wait_for(
            action_task,
            timeout=action_timeout_sec if (action_timeout_sec or 0) > 0 else None,
        )
        return {
            "success": True,
            "outcome": "succeeded",
            "summary": "",
            "error": None,
            "error_type": None,
            "output": output,
            "heartbeat_count": len(heartbeat_snapshots),
            "heartbeat_snapshots": heartbeat_snapshots,
        }
    except asyncio.TimeoutError:
        summary = _timeout_summary(label, action_timeout_sec)
        if action_task is not None and not action_task.done():
            action_task.cancel()
            with suppress(asyncio.TimeoutError, asyncio.CancelledError, Exception):
                await asyncio.wait_for(
                    action_task,
                    timeout=cancel_grace_sec if (cancel_grace_sec or 0) > 0 else 0.1,
                )
        return {
            "success": False,
            "outcome": "timeout",
            "summary": summary,
            "error": summary,
            "error_type": "timeout_error",
            "output": None,
            "heartbeat_count": len(heartbeat_snapshots),
            "heartbeat_snapshots": heartbeat_snapshots,
        }
    except asyncio.CancelledError:
        summary = f"{label} was cancelled."
        return {
            "success": False,
            "outcome": "cancelled",
            "summary": summary,
            "error": summary,
            "error_type": "cancellation_error",
            "output": None,
            "heartbeat_count": len(heartbeat_snapshots),
            "heartbeat_snapshots": heartbeat_snapshots,
        }
    except Exception as exc:
        summary = _normalize_text(exc) or f"{label} failed."
        return {
            "success": False,
            "outcome": "failed",
            "summary": summary,
            "error": summary,
            "error_type": _classify_error_type(summary),
            "output": None,
            "heartbeat_count": len(heartbeat_snapshots),
            "heartbeat_snapshots": heartbeat_snapshots,
        }
    finally:
        stop_heartbeat.set()
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task


__all__ = ["run_donor_execution_envelope"]
