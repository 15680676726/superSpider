# -*- coding: utf-8 -*-
"""Shared runtime outcome helpers for actor execution flows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

_CANCELLATION_MARKERS = (
    "task has been cancelled",
    "task has been canceled",
    "query was cancelled before completion",
    "query was canceled before completion",
    "cancelled by actor control",
    "canceled by actor control",
)
_TIMEOUT_MARKERS = (
    "timeout",
    "timed out",
    "exceeded the timeout",
)


@dataclass(frozen=True, slots=True)
class RuntimeCleanupDisposition:
    phase: Literal["completed", "waiting-confirm", "cancelled", "failed"]
    checkpoint_status: Literal["applied", "ready", "abandoned", "failed"]
    mailbox_action: Literal["complete", "block", "cancel", "fail"]


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


def is_timeout_runtime_error(error: str | None) -> bool:
    normalized = normalize_runtime_summary(error)
    if normalized is None:
        return False
    lowered = normalized.casefold()
    return any(marker in lowered for marker in _TIMEOUT_MARKERS)


def classify_runtime_outcome(
    error: str | None,
    *,
    success: bool,
    phase: str | None = None,
    timed_out: bool = False,
) -> Literal["completed", "failed", "cancelled", "timeout", "waiting-confirm", "blocked"]:
    normalized_phase = normalize_runtime_summary(phase)
    if normalized_phase == "waiting-confirm":
        return "waiting-confirm"
    if normalized_phase == "blocked":
        return "blocked"
    if normalized_phase == "cancelled":
        return "cancelled"
    if normalized_phase == "timeout":
        return "timeout"
    if timed_out or is_timeout_runtime_error(error):
        return "timeout"
    if is_cancellation_runtime_error(error):
        return "cancelled"
    if success:
        return "completed"
    return "failed"


def evidence_status_for_outcome(
    outcome: str,
) -> Literal["recorded", "failed", "cancelled", "timeout"]:
    if outcome == "completed":
        return "recorded"
    if outcome == "cancelled":
        return "cancelled"
    if outcome == "timeout":
        return "timeout"
    return "failed"


def resolve_runtime_cleanup_disposition(
    phase: str | None,
) -> RuntimeCleanupDisposition:
    normalized_phase = normalize_runtime_summary(phase)
    if normalized_phase == "completed":
        return RuntimeCleanupDisposition(
            phase="completed",
            checkpoint_status="applied",
            mailbox_action="complete",
        )
    if normalized_phase == "waiting-confirm":
        return RuntimeCleanupDisposition(
            phase="waiting-confirm",
            checkpoint_status="ready",
            mailbox_action="block",
        )
    if normalized_phase == "cancelled":
        return RuntimeCleanupDisposition(
            phase="cancelled",
            checkpoint_status="abandoned",
            mailbox_action="cancel",
        )
    return RuntimeCleanupDisposition(
        phase="failed",
        checkpoint_status="failed",
        mailbox_action="fail",
    )


def should_block_runtime_error(error: str | None) -> bool:
    normalized = normalize_runtime_summary(error)
    return normalized is not None and not (
        is_cancellation_runtime_error(normalized)
        or is_timeout_runtime_error(normalized)
    )


def query_checkpoint_outcome(
    error: str | None,
) -> tuple[str, Literal["applied", "abandoned", "failed"]]:
    if is_cancellation_runtime_error(error):
        return "query-cancelled", "abandoned"
    if is_timeout_runtime_error(error):
        return "query-timeout", "failed"
    if normalize_runtime_summary(error) is not None:
        return "query-error", "failed"
    return "query-complete", "applied"
