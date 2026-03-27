# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .main_brain_environment_coordinator import MainBrainEnvironmentBinding


def _non_empty_str(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


def _resolve_resume_kernel_task_id(request: Any) -> str | None:
    return (
        _non_empty_str(getattr(request, "resume_kernel_task_id", None))
        or _non_empty_str(getattr(request, "resume_task_id", None))
        or _non_empty_str(getattr(request, "continue_kernel_task_id", None))
    )


def _resolve_resume_environment_requested(request: Any) -> bool:
    raw_value = (
        _non_empty_str(getattr(request, "resume_mode", None))
        or _non_empty_str(getattr(request, "recovery_preference", None))
        or _non_empty_str(getattr(request, "recovery_mode", None))
    )
    if raw_value is not None:
        normalized = raw_value.strip().lower()
        if normalized in {"resume-environment", "resume_environment"}:
            return True
    return bool(getattr(request, "resume_environment", False))


@dataclass(slots=True)
class MainBrainRecoveryState:
    recovery_mode: str
    recovery_reason: str
    resume_checkpoint_id: str | None
    resume_mailbox_id: str | None
    resume_kernel_task_id: str | None
    resume_environment_session_id: str | None
    continuity_token: str | None


class MainBrainRecoveryCoordinator:
    def coordinate(
        self,
        *,
        request: Any,
        environment_binding: MainBrainEnvironmentBinding,
    ) -> MainBrainRecoveryState:
        resume_checkpoint_id = (
            _non_empty_str(getattr(request, "checkpoint_id", None))
            or _non_empty_str(getattr(request, "resume_checkpoint_id", None))
        )
        resume_mailbox_id = _non_empty_str(getattr(request, "current_mailbox_id", None))
        resume_kernel_task_id = _resolve_resume_kernel_task_id(request)
        resume_environment_session_id = environment_binding.environment_session_id
        resume_environment_requested = _resolve_resume_environment_requested(request)
        continuity_token = (
            resume_checkpoint_id
            or resume_mailbox_id
            or environment_binding.continuity_token
            or resume_kernel_task_id
        )
        if resume_checkpoint_id is not None or resume_mailbox_id is not None:
            recovery_mode = "resume-runtime"
            recovery_reason = (
                "runtime-checkpoint"
                if resume_checkpoint_id is not None
                else "runtime-mailbox"
            )
        elif resume_environment_session_id is not None and environment_binding.resume_ready:
            recovery_mode = "resume-environment"
            recovery_reason = environment_binding.continuity_source
        elif resume_environment_session_id is not None and resume_environment_requested:
            recovery_mode = "rebind-environment"
            recovery_reason = "resume-request-without-continuity-proof"
        elif resume_environment_session_id is not None:
            recovery_mode = "attach-environment"
            recovery_reason = "environment-session-without-continuity-proof"
        elif environment_binding.environment_ref is not None:
            recovery_mode = "attach-environment"
            recovery_reason = "environment-ref-attached"
        elif resume_kernel_task_id is not None:
            recovery_mode = "resume-task"
            recovery_reason = "explicit-resume-kernel-task"
        else:
            recovery_mode = "fresh"
            recovery_reason = "fresh-turn"
        return MainBrainRecoveryState(
            recovery_mode=recovery_mode,
            recovery_reason=recovery_reason,
            resume_checkpoint_id=resume_checkpoint_id,
            resume_mailbox_id=resume_mailbox_id,
            resume_kernel_task_id=resume_kernel_task_id,
            resume_environment_session_id=resume_environment_session_id,
            continuity_token=continuity_token,
        )


__all__ = [
    "MainBrainRecoveryCoordinator",
    "MainBrainRecoveryState",
]
