# -*- coding: utf-8 -*-
"""Shared runtime outcome helpers for actor execution flows."""
from __future__ import annotations

from typing import Literal

_CANCELLATION_MARKERS = (
    "task has been cancelled",
    "task has been canceled",
    "query was cancelled before completion",
    "query was canceled before completion",
    "cancelled by actor control",
    "canceled by actor control",
    "任务已取消",
    "查询已取消",
    "已取消",
)


def normalize_runtime_summary(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    resolved = value.strip()
    return resolved or None


def is_cancellation_runtime_error(error: str | None) -> bool:
    normalized = normalize_runtime_summary(error)
    if normalized is None:
        return False
    lowered = normalized.casefold()
    return any(marker in lowered for marker in _CANCELLATION_MARKERS)


def should_block_runtime_error(error: str | None) -> bool:
    normalized = normalize_runtime_summary(error)
    return normalized is not None and not is_cancellation_runtime_error(normalized)


def query_checkpoint_outcome(
    error: str | None,
) -> tuple[str, Literal["applied", "abandoned", "failed"]]:
    if is_cancellation_runtime_error(error):
        return "query-cancelled", "abandoned"
    if normalize_runtime_summary(error) is not None:
        return "query-error", "failed"
    return "query-complete", "applied"
