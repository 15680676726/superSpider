# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from .main_brain_environment_coordinator import MainBrainEnvironmentBinding
from .main_brain_execution_planner import MainBrainExecutionPlan
from .main_brain_intake import MainBrainIntakeContract
from .main_brain_recovery_coordinator import MainBrainRecoveryState

logger = logging.getLogger(__name__)


class MainBrainResultCommitter:
    def commit_request_runtime_context(
        self,
        *,
        request: Any,
        intake_contract: MainBrainIntakeContract | None,
        execution_plan: MainBrainExecutionPlan,
        environment_binding: MainBrainEnvironmentBinding,
        recovery_state: MainBrainRecoveryState,
        kernel_task_id: str | None,
    ) -> None:
        runtime_context = {
            "intake_contract": intake_contract,
            "source_intent_kind": execution_plan.source_intent_kind,
            "execution_intent": execution_plan.intent_kind,
            "execution_mode": execution_plan.execution_mode,
            "environment_ref": environment_binding.environment_ref,
            "environment_binding_kind": environment_binding.binding_kind,
            "environment_kind": environment_binding.environment_kind,
            "environment_session_id": environment_binding.environment_session_id,
            "environment_lease_token": environment_binding.environment_lease_token,
            "environment_continuity_token": environment_binding.continuity_token,
            "environment_continuity_source": environment_binding.continuity_source,
            "environment_live_session_bound": environment_binding.live_session_bound,
            "environment_resume_ready": environment_binding.resume_ready,
            "writeback_requested": bool(getattr(intake_contract, "writeback_requested", False)),
            "should_kickoff": bool(getattr(intake_contract, "should_kickoff", False)),
            "recovery_mode": recovery_state.recovery_mode,
            "recovery_reason": recovery_state.recovery_reason,
            "resume_checkpoint_id": recovery_state.resume_checkpoint_id,
            "resume_mailbox_id": recovery_state.resume_mailbox_id,
            "resume_kernel_task_id": recovery_state.resume_kernel_task_id,
            "resume_environment_session_id": recovery_state.resume_environment_session_id,
            "recovery_continuity_token": recovery_state.continuity_token,
            "kernel_task_id": kernel_task_id,
        }
        self._set_request_runtime_value(
            request,
            "_copaw_main_brain_runtime_context",
            runtime_context,
        )
        self._set_request_runtime_value(request, "_copaw_main_brain_intake_contract", intake_contract)
        if kernel_task_id is not None:
            self._set_request_runtime_value(request, "_copaw_kernel_task_id", kernel_task_id)

    @staticmethod
    def _set_request_runtime_value(request: Any, name: str, value: Any) -> None:
        try:
            object.__setattr__(request, name, value)
            return
        except Exception:
            pass
        try:
            setattr(request, name, value)
        except Exception:
            logger.debug("Failed to set runtime request attribute '%s'", name)


__all__ = ["MainBrainResultCommitter"]
