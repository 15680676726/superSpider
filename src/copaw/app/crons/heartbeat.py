# -*- coding: utf-8 -*-
"""Heartbeat: run a scheduled main-brain supervision pulse through the kernel."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, time
from typing import Any, Dict

from ...config import get_heartbeat_config

logger = logging.getLogger(__name__)

_EVERY_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)


def parse_heartbeat_every(every: str) -> int:
    """Parse interval string (for example '30m' or '1h') to total seconds."""
    every = (every or "").strip()
    if not every:
        return 30 * 60
    match = _EVERY_PATTERN.match(every)
    if not match:
        logger.warning("heartbeat every=%r invalid, using 30m", every)
        return 30 * 60
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else 30 * 60


def _in_active_hours(active_hours: Any) -> bool:
    if (
        not active_hours
        or not hasattr(active_hours, "start")
        or not hasattr(active_hours, "end")
    ):
        return True
    try:
        start_parts = active_hours.start.strip().split(":")
        end_parts = active_hours.end.strip().split(":")
        start_t = time(
            int(start_parts[0]),
            int(start_parts[1]) if len(start_parts) > 1 else 0,
        )
        end_t = time(
            int(end_parts[0]),
            int(end_parts[1]) if len(end_parts) > 1 else 0,
        )
    except (ValueError, IndexError, AttributeError):
        return True
    now = datetime.now().time()
    if start_t <= end_t:
        return start_t <= now <= end_t
    return now >= start_t or now <= end_t


async def run_heartbeat_once(
    *,
    kernel_dispatcher: Any | None = None,
    ignore_active_hours: bool = False,
) -> Dict[str, Any]:
    """Run one main-brain supervision pulse over the operating cycle chain."""
    if kernel_dispatcher is None:
        logger.warning("heartbeat skipped: kernel dispatcher is not configured")
        return {
            "status": "skipped",
            "reason": "Kernel dispatcher is not configured.",
            "query_path": "system:run_operating_cycle",
        }
    heartbeat = get_heartbeat_config()
    if not ignore_active_hours and not _in_active_hours(heartbeat.active_hours):
        logger.debug("heartbeat skipped: outside active hours")
        return {
            "status": "skipped",
            "reason": "Heartbeat is outside active hours.",
            "query_path": "system:run_operating_cycle",
        }

    from ...kernel import KernelTask

    payload: Dict[str, Any] = {
        "actor": "system:heartbeat",
        "source": "heartbeat:supervision-pulse",
        "force": False,
        "limit": 10,
    }
    task = KernelTask(
        title="Heartbeat: main-brain supervision pulse",
        capability_ref="system:run_operating_cycle",
        owner_agent_id="copaw-main-brain",
        risk_level="auto",
        payload=payload,
    )
    admitted = kernel_dispatcher.submit(task)
    if admitted.phase != "executing":
        if admitted.phase == "waiting-confirm":
            logger.warning(
                "heartbeat held for confirmation: task_id=%s",
                admitted.task_id,
            )
            return {
                "status": "skipped",
                "reason": "Heartbeat supervision pulse is waiting for confirmation.",
                "task_id": admitted.task_id,
                "query_path": "system:run_operating_cycle",
            }
        logger.warning(
            "heartbeat blocked before execution: task_id=%s phase=%s summary=%s",
            admitted.task_id,
            admitted.phase,
            admitted.summary or admitted.error,
        )
        return {
            "status": "blocked",
            "reason": admitted.error
            or admitted.summary
            or f"Heartbeat admission blocked (phase={admitted.phase}).",
            "task_id": admitted.task_id,
            "query_path": "system:run_operating_cycle",
        }

    try:
        executed = await asyncio.wait_for(
            kernel_dispatcher.execute_task(task.id),
            timeout=120,
        )
    except asyncio.TimeoutError:
        logger.warning("heartbeat run timed out")
        return {
            "status": "error",
            "reason": "Heartbeat execution timed out.",
            "task_id": task.id,
            "query_path": "system:run_operating_cycle",
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("heartbeat run failed: %s", exc)
        return {
            "status": "error",
            "reason": str(exc),
            "task_id": task.id,
            "query_path": "system:run_operating_cycle",
        }

    result_payload = getattr(executed, "result", None)
    processed_count = result_payload.get("count") if isinstance(result_payload, dict) else None
    return {
        "status": "success",
        "task_id": task.id,
        "query_path": "system:run_operating_cycle",
        "query_preview": "main-brain supervision pulse",
        "target": heartbeat.target,
        "dispatch_events": False,
        "processed_instance_count": processed_count,
        "phase": getattr(executed, "phase", None),
        "summary": getattr(executed, "summary", None),
    }
