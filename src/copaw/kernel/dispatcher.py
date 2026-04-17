# -*- coding: utf-8 -*-
"""Kernel dispatcher: the single entry point for task admission/execution."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from ..industry.identity import is_execution_core_agent_id
from .decision_policy import (
    MAIN_BRAIN_DECISION_ACTOR,
    decision_chat_route,
    decision_chat_thread_id,
    decision_requested_by,
    task_is_main_brain_auto_approvable,
    task_requires_human_confirmation,
)
from .lifecycle import TaskLifecycleManager
from .models import KernelConfig, KernelResult, KernelTask
from .persistence import KernelTaskStore

if TYPE_CHECKING:
    from ..capabilities import CapabilityService
    from ..state import DecisionRequestRecord
    from .governance import GovernanceService

logger = logging.getLogger(__name__)

_DEFERRED_EXPLICIT_CLOSEOUT_KEY = "_copaw_deferred_explicit_closeout"


class KernelDispatcher:
    """Dispatch tasks through risk admission, persistence, and execution."""

    def __init__(
        self,
        *,
        config: KernelConfig | None = None,
        lifecycle: TaskLifecycleManager | None = None,
        task_store: KernelTaskStore | None = None,
        capability_service: "CapabilityService | None" = None,
        governance_service: "GovernanceService | None" = None,
        learning_service: object | None = None,
        industry_service: object | None = None,
    ) -> None:
        self._config = config or KernelConfig()
        self._task_store = task_store
        self._capability_service = capability_service
        self._governance_service = governance_service
        self._learning_service = learning_service
        self._industry_service = industry_service
        self._goal_service: object | None = None
        self._lifecycle = lifecycle or TaskLifecycleManager(
            config=self._config,
            store=task_store,
        )

    def set_goal_service(self, goal_service: object | None) -> None:
        self._goal_service = goal_service

    def set_industry_service(self, industry_service: object | None) -> None:
        self._industry_service = industry_service

    def submit(self, task: KernelTask) -> KernelResult:
        """Accept a task into the kernel and apply risk gating."""
        accepted = self._lifecycle.accept(task)
        parent_block_reason = self._terminal_parent_block_reason(accepted)
        if parent_block_reason:
            return self.cancel_task(accepted.id, resolution=parent_block_reason)
        if self._governance_service is not None:
            block_reason = self._governance_service.admission_block_reason(accepted)
            if block_reason:
                return self.cancel_task(accepted.id, resolution=block_reason)
        gated = self._lifecycle.evaluate_risk(accepted.id)

        if gated.phase == "waiting-confirm":
            expires_at = self._decision_expiry_deadline()
            decision = (
                self._task_store.ensure_decision_request(
                    gated,
                    expires_at=expires_at,
                    requested_by=decision_requested_by(gated),
                )
                if self._task_store is not None
                else None
            )
            if decision is not None and task_is_main_brain_auto_approvable(gated):
                approved = self.confirm_task(
                    gated.id,
                    resolution=self._auto_adjudication_resolution(gated),
                    decision_request_id=decision.id,
                )
                return approved.model_copy(
                    update={
                        "summary": self._auto_adjudication_summary(gated),
                        "decision_request_id": decision.id,
                    },
                )
            if self._task_store is not None:
                chat_thread_id = self._decision_chat_thread_id(gated)
                self._task_store.append_evidence(
                    gated,
                    action_summary="内核等待确认",
                    result_summary=(
                        f"任务“{gated.title}”正在等待人工确认。"
                    ),
                    metadata={
                        "trace_stage": "kernel.waiting-confirm",
                        "trace_component": "kernel.dispatcher",
                        "phase": gated.phase,
                        "decision_request_id": (
                            decision.id if decision is not None else None
                        ),
                        "requested_by": decision.requested_by if decision is not None else None,
                        "requires_human_confirmation": task_requires_human_confirmation(
                            gated,
                        ),
                        "chat_thread_id": chat_thread_id,
                        "chat_route": decision_chat_route(chat_thread_id),
                    },
                )
            return KernelResult(
                task_id=gated.id,
                trace_id=gated.trace_id,
                success=False,
                phase="waiting-confirm",
                summary="任务执行前需要人工确认。",
                decision_request_id=decision.id if decision is not None else None,
            )

        return KernelResult(
            task_id=gated.id,
            trace_id=gated.trace_id,
            success=True,
            phase=gated.phase,
            summary="任务已进入内核，准备执行。",
        )

    def confirm_task(
        self,
        task_id: str,
        *,
        resolution: str | None = None,
        decision_request_id: str | None = None,
    ) -> KernelResult:
        """Approve a held task and release it back to executing."""
        task = self._lifecycle.confirm(task_id)
        resolution_text = resolution or "已通过内核调度器批准。"
        resolved_decision_id = decision_request_id
        if self._task_store is not None:
            if decision_request_id is not None:
                resolved = self._task_store.resolve_decision_request(
                    decision_request_id,
                    status="approved",
                    resolution=resolution_text,
                )
                if resolved is not None:
                    resolved_decision_id = resolved.id
            else:
                resolved = self._task_store.resolve_open_decisions(
                    task_id=task_id,
                    status="approved",
                    resolution=resolution_text,
                )
                if resolved:
                    resolved_decision_id = resolved[0].id
            evidence = self._task_store.append_evidence(
                task,
                action_summary="内核任务已批准",
                result_summary=f"任务“{task.title}”已获批，准备执行。",
                metadata={
                    "trace_stage": "kernel.approved",
                    "trace_component": "kernel.dispatcher",
                    "phase": task.phase,
                    "decision_request_id": resolved_decision_id,
                    "decision_status": "approved",
                },
            )
            if evidence is not None:
                self._task_store.upsert(task, last_evidence_id=evidence.id)
        return KernelResult(
            task_id=task.id,
            trace_id=task.trace_id,
            success=True,
            phase=task.phase,
            summary="任务已批准并释放执行。",
            decision_request_id=resolved_decision_id,
        )

    async def execute_task(self, task_id: str) -> KernelResult:
        """Execute a task through the unified capability service."""
        task = self._lifecycle.get_task(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found in kernel")
        if task.phase != "executing":
            raise ValueError(
                f"Task {task_id} is in phase '{task.phase}', expected 'executing'",
            )
        if self._capability_service is None:
            raise RuntimeError("CapabilityService is not wired to the kernel dispatcher")

        try:
            execution_call = self._capability_service.execute_task(task)
            timeout_seconds = self._config.execution_timeout_seconds
            if timeout_seconds is not None:
                execution = await asyncio.wait_for(execution_call, timeout=timeout_seconds)
            else:
                execution = await execution_call
        except TimeoutError:
            logger.exception("Kernel capability execution timed out for %s", task_id)
            return self.fail_task(
                task_id,
                error=f"Execution timed out after {timeout_seconds:g} seconds.",
            )
        except Exception as exc:
            logger.exception("Kernel capability execution failed for %s", task_id)
            return self.fail_task(task_id, error=str(exc))

        if not execution.get("success", False):
            failure_kind = str(execution.get("error_kind") or "").strip().lower()
            failure_error = str(
                execution.get("error") or execution.get("summary") or "execution failed",
            )
            if failure_kind == "cancelled":
                result = self.cancel_task(
                    task_id,
                    resolution=failure_error,
                ).model_copy(update={"error": failure_error})
            else:
                result = self.fail_task(
                    task_id,
                    error=failure_error,
                    append_kernel_evidence=not bool(execution.get("evidence_emitted")),
                )
            output = execution.get("output") if isinstance(execution, dict) else None
            if isinstance(output, dict):
                result = result.model_copy(update={"output": output})
            decision_request_id = self._latest_decision_request_id(task.id)
            if decision_request_id is not None and result.decision_request_id is None:
                result = result.model_copy(update={"decision_request_id": decision_request_id})
            return result

        result = self.complete_task(
            task_id,
            summary=str(execution.get("summary") or f"任务“{task.title}”已执行。"),
            metadata={
                "trace_stage": "kernel.completed",
                "trace_component": "kernel.dispatcher",
                "execution": execution,
            },
        )
        output = execution.get("output") if isinstance(execution, dict) else None
        if isinstance(output, dict):
            result = result.model_copy(update={"output": output})
        decision_request_id = self._latest_decision_request_id(task.id)
        if decision_request_id is not None and result.decision_request_id is None:
            result = result.model_copy(update={"decision_request_id": decision_request_id})
        return result

    async def confirm_and_execute(self, task_id: str) -> KernelResult:
        """Approve a held task and execute it through the capability graph."""
        self.confirm_task(task_id)
        return await self.execute_task(task_id)

    async def approve_decision(
        self,
        decision_id: str,
        *,
        resolution: str | None = None,
        execute: bool | None = None,
    ) -> KernelResult:
        """Approve a DecisionRequest and continue the held task."""
        decision, task = self._get_pending_decision(decision_id)
        result = self.confirm_task(
            task.id,
            resolution=resolution or f"决策“{decision_id}”已批准。",
            decision_request_id=decision.id,
        )
        should_execute = (
            execute
            if execute is not None
            else bool(task.capability_ref)
        )
        if not should_execute:
            if _auto_complete_on_approval(task):
                completed = self.complete_task(
                    task.id,
                    summary=(
                        _approval_completion_summary(task)
                        or resolution
                        or f"决策“{decision_id}”已批准。"
                    ),
                )
                return completed.model_copy(update={"decision_request_id": decision.id})
            return result
        execution = await self.execute_task(task.id)
        return execution.model_copy(update={"decision_request_id": decision.id})

    def complete_task(
        self,
        task_id: str,
        *,
        summary: str,
        metadata: dict[str, object] | None = None,
    ) -> KernelResult:
        """Complete a task and write kernel evidence."""
        task = self._lifecycle.get_task(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found in kernel")
        if task.phase in {"completed", "failed", "cancelled"}:
            return self._lifecycle.complete(
                task_id,
                summary=summary,
            )
        child_block_summary = self._active_child_block_summary(task_id)
        if child_block_summary is not None:
            if _parent_requires_explicit_terminal_close(task):
                task = self._remember_deferred_explicit_closeout(
                    task,
                    summary=summary,
                )
            if self._task_store is not None:
                self._task_store.append_evidence(
                    task,
                    action_summary="内核任务等待子任务收口",
                    result_summary=child_block_summary,
                    metadata={
                        "trace_stage": "kernel.waiting-children",
                        "trace_component": "kernel.dispatcher",
                        "phase": task.phase,
                    },
                )
            return KernelResult(
                task_id=task_id,
                trace_id=task.trace_id,
                success=True,
                phase=task.phase,
                summary=child_block_summary,
            )
        task = self._clear_deferred_explicit_closeout(task)
        evidence_id: str | None = None
        if self._task_store is not None:
            evidence = self._task_store.append_evidence(
                task,
                action_summary="内核任务已完成",
                result_summary=summary,
                metadata=metadata,
            )
            evidence_id = evidence.id if evidence is not None else None
        result = self._lifecycle.complete(
            task_id,
            summary=summary,
            evidence_id=evidence_id,
        )
        self._after_terminal_transition(task=task, result=result)
        return result

    def fail_task(
        self,
        task_id: str,
        *,
        error: str,
        append_kernel_evidence: bool = True,
    ) -> KernelResult:
        """Fail a task and write kernel evidence / decision resolution."""
        task = self._lifecycle.get_task(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found in kernel")
        if task.phase in {"completed", "failed", "cancelled"}:
            return self._lifecycle.fail(task_id, error=error)
        task = self._clear_deferred_explicit_closeout(task)
        if self._task_store is not None:
            self._task_store.resolve_open_decisions(
                task_id=task_id,
                status="rejected",
                resolution=error,
            )
            if append_kernel_evidence:
                evidence = self._task_store.append_evidence(
                    task,
                    action_summary="内核任务失败",
                    result_summary=error,
                    metadata={
                        "trace_stage": "kernel.failed",
                        "trace_component": "kernel.dispatcher",
                        "phase": task.phase,
                    },
                )
                if evidence is not None:
                    self._task_store.upsert(task, last_evidence_id=evidence.id)
        result = self._lifecycle.fail(task_id, error=error)
        self._after_terminal_transition(task=task, result=result)
        return result

    def cancel_task(
        self,
        task_id: str,
        *,
        resolution: str | None = None,
        decision_request_id: str | None = None,
    ) -> KernelResult:
        task = self._lifecycle.get_task(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found in kernel")
        if task.phase in {"completed", "failed", "cancelled"}:
            return self._lifecycle.cancel(
                task_id,
                summary=resolution or "Task cancelled",
            )
        task = self._clear_deferred_explicit_closeout(task)
        resolution_text = resolution or "任务已取消。"
        resolved_decision_id = decision_request_id
        if self._task_store is not None:
            if decision_request_id is not None:
                resolved = self._task_store.resolve_decision_request(
                    decision_request_id,
                    status="rejected",
                    resolution=resolution_text,
                )
                if resolved is not None:
                    resolved_decision_id = resolved.id
            else:
                resolved = self._task_store.resolve_open_decisions(
                    task_id=task_id,
                    status="rejected",
                    resolution=resolution_text,
                )
                if resolved:
                    resolved_decision_id = resolved[0].id
            evidence = self._task_store.append_evidence(
                task,
                action_summary="内核任务已取消",
                result_summary=resolution_text,
                metadata={
                    "trace_stage": "kernel.cancelled",
                    "trace_component": "kernel.dispatcher",
                    "phase": task.phase,
                    "decision_request_id": resolved_decision_id,
                    "decision_status": "rejected",
                },
            )
            if evidence is not None:
                self._task_store.upsert(task, last_evidence_id=evidence.id)
        result = self._lifecycle.cancel(task_id, summary=resolution_text)
        self._after_terminal_transition(task=task, result=result)
        return result.model_copy(update={"decision_request_id": resolved_decision_id})

    def heartbeat_task(self, task_id: str) -> KernelTask | None:
        task = self._lifecycle.get_task(task_id)
        if task is None:
            return None
        return self._lifecycle.heartbeat(task_id)

    def reject_decision(
        self,
        decision_id: str,
        *,
        resolution: str | None = None,
    ) -> KernelResult:
        """Reject a DecisionRequest and cancel the held task."""
        decision, task = self._get_pending_decision(decision_id)
        return self.cancel_task(
            task.id,
            resolution=resolution or f"决策“{decision_id}”已驳回。",
            decision_request_id=decision.id,
        )

    def expire_decision(
        self,
        decision_id: str,
        *,
        resolution: str | None = None,
    ) -> KernelResult:
        """Expire a DecisionRequest and cancel the held task."""
        decision, task = self._get_pending_decision(decision_id)
        resolution_text = resolution or f"决策“{decision_id}”已过期。"
        resolved_decision_id = decision.id
        if self._task_store is not None:
            resolved = self._task_store.expire_decision_request(
                decision_id,
                resolution=resolution_text,
            )
            if resolved is not None:
                resolved_decision_id = resolved.id
            evidence = self._task_store.append_evidence(
                task,
                action_summary="内核决策已过期",
                result_summary=resolution_text,
                metadata={
                    "trace_stage": "kernel.expired",
                    "trace_component": "kernel.dispatcher",
                    "phase": task.phase,
                    "decision_request_id": resolved_decision_id,
                    "decision_status": "expired",
                },
            )
            if evidence is not None:
                self._task_store.upsert(task, last_evidence_id=evidence.id)
        result = self._lifecycle.cancel(task.id, summary=resolution_text)
        return result.model_copy(update={"decision_request_id": resolved_decision_id})

    @property
    def lifecycle(self) -> TaskLifecycleManager:
        return self._lifecycle

    @property
    def task_store(self) -> KernelTaskStore | None:
        return self._task_store

    def _get_pending_decision(
        self,
        decision_id: str,
    ) -> tuple["DecisionRequestRecord", KernelTask]:
        if self._task_store is None:
            raise RuntimeError("Decision requests are not backed by the unified state store")
        decision = self._task_store.get_decision_request(decision_id)
        if decision is None:
            raise KeyError(f"Decision request '{decision_id}' not found")
        if decision.status not in {"open", "reviewing"}:
            raise ValueError(
                (
                    "Decision request "
                    f"'{decision_id}' is in status '{decision.status}', "
                    "expected 'open' or 'reviewing'"
                ),
            )
        task = self._lifecycle.get_task(decision.task_id)
        if task is None:
            raise KeyError(f"Task '{decision.task_id}' not found in kernel")
        if task.phase != "waiting-confirm":
            raise ValueError(
                f"Task '{task.id}' is in phase '{task.phase}', expected 'waiting-confirm'",
            )
        return decision, task

    def _decision_expiry_deadline(self) -> datetime | None:
        expiry_hours = self._config.decision_expiry_hours
        if expiry_hours is None:
            return None
        if isinstance(expiry_hours, int) and expiry_hours > 0:
            return datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        return None

    def _latest_decision_request_id(self, task_id: str) -> str | None:
        if self._task_store is None:
            return None
        decisions = self._task_store.list_decision_requests(task_id=task_id)
        if not decisions:
            return None
        decisions.sort(
            key=lambda item: (
                (item.resolved_at or item.created_at).isoformat() if (item.resolved_at or item.created_at) is not None else "",
                item.id,
            ),
            reverse=True,
        )
        return decisions[0].id

    @staticmethod
    def _decision_chat_thread_id(task: KernelTask) -> str | None:
        payload = task.payload if isinstance(task.payload, dict) else {}
        return decision_chat_thread_id(payload)

    @staticmethod
    def _auto_adjudication_summary(task: KernelTask) -> str:
        capability_ref = str(task.capability_ref or "kernel-confirmation").strip() or "kernel-confirmation"
        return (
            f"{MAIN_BRAIN_DECISION_ACTOR} auto-approved '{task.title}' "
            f"and released {capability_ref} for execution."
        )

    @staticmethod
    def _auto_adjudication_resolution(task: KernelTask) -> str:
        capability_ref = str(task.capability_ref or "kernel-confirmation").strip() or "kernel-confirmation"
        return (
            f"{MAIN_BRAIN_DECISION_ACTOR} auto-approved "
            f"'{task.title}' for {capability_ref}."
        )

    def _after_terminal_transition(
        self,
        *,
        task: KernelTask,
        result: KernelResult,
    ) -> None:
        self._cancel_live_child_subtree(task=task, result=result)
        self._reconcile_parent_after_child_terminal(task)
        self._notify_goal_service(task)
        self._resume_goal_background_chain(task)
        self._maybe_close_industry_execution_loop(task=task)
        self._record_main_brain_outcome(task=task, result=result)

    def _maybe_close_industry_execution_loop(self, *, task: KernelTask) -> None:
        service = self._industry_service
        if service is None:
            return
        close_loop = getattr(service, "close_task_execution_closure", None)
        if not callable(close_loop):
            return
        payload = task.payload if isinstance(task.payload, dict) else {}
        request_context = payload.get("request_context")
        request = payload.get("request")
        meta = payload.get("meta")
        request_context_mapping = dict(request_context) if isinstance(request_context, dict) else {}
        request_mapping = dict(request) if isinstance(request, dict) else {}
        meta_mapping = dict(meta) if isinstance(meta, dict) else {}
        industry_instance_id = _normalize_optional_str(
            payload.get("industry_instance_id")
            or request_context_mapping.get("industry_instance_id")
            or request_mapping.get("industry_instance_id")
            or meta_mapping.get("industry_instance_id"),
        )
        if industry_instance_id is None:
            return
        try:
            close_loop(
                industry_instance_id=industry_instance_id,
                cycle_id=_normalize_optional_str(
                    payload.get("cycle_id")
                    or request_context_mapping.get("cycle_id")
                    or request_mapping.get("cycle_id")
                    or meta_mapping.get("cycle_id"),
                ),
                assignment_id=_normalize_optional_str(
                    payload.get("assignment_id")
                    or request_context_mapping.get("assignment_id")
                    or request_mapping.get("assignment_id")
                    or meta_mapping.get("assignment_id"),
                ),
                task_id=task.id,
            )
        except Exception:
            logger.exception(
                "Kernel dispatcher failed to close industry execution loop for task %s",
                task.id,
            )

    def _record_main_brain_outcome(
        self,
        *,
        task: KernelTask,
        result: KernelResult,
    ) -> None:
        if not _should_record_main_brain_outcome(task):
            return
        recorder = getattr(self._learning_service, "record_agent_outcome", None)
        if not callable(recorder):
            return
        context = _resolve_task_learning_context(task)
        try:
            recorder(
                agent_id=task.owner_agent_id,
                title=task.title,
                status=result.phase,
                change_type=_task_outcome_change_type(result.phase),
                description=result.summary or result.error or f"Task '{task.title}' finished.",
                capability_ref=task.capability_ref,
                task_id=task.id,
                goal_id=task.goal_id,
                source_evidence_id=result.evidence_id,
                risk_level=task.risk_level,
                source_agent_id=context["source_agent_id"],
                industry_instance_id=context["industry_instance_id"],
                industry_role_id=context["industry_role_id"],
                role_name=context["role_name"],
                owner_scope=context["owner_scope"],
                error_summary=result.error,
                metadata={
                    "trace_id": task.trace_id,
                    "environment_ref": task.environment_ref,
                    "decision_request_id": (
                        result.decision_request_id
                        or self._latest_decision_request_id(task.id)
                    ),
                    "work_context_id": task.work_context_id,
                },
            )
        except Exception:
            logger.exception(
                "Failed to record main-brain outcome for kernel task %s",
                task.id,
            )

    def _notify_goal_service(self, task: KernelTask) -> None:
        if self._goal_service is None or not task.goal_id:
            return
        reconciler = getattr(self._goal_service, "reconcile_goal_status", None)
        if callable(reconciler):
            reconciler(task.goal_id, source="task-terminal")

    def _resume_goal_background_chain(self, task: KernelTask) -> None:
        if self._goal_service is None or not task.goal_id:
            return
        resumer = getattr(self._goal_service, "resume_background_goal_chain_for_task", None)
        if callable(resumer):
            resumer(task.id)

    def _active_child_block_summary(self, task_id: str) -> str | None:
        child_tasks = self._list_child_tasks(task_id)
        if not child_tasks:
            return None
        active_children = [
            child
            for child in child_tasks
            if child.phase not in {"completed", "failed", "cancelled"}
        ]
        if not active_children:
            return None
        return (
            f"Waiting for {len(active_children)} child task(s) to finish before closing "
            f"'{task_id}'."
        )

    def _terminal_parent_block_reason(self, task: KernelTask) -> str | None:
        parent_task_id = str(task.parent_task_id or "").strip()
        if not parent_task_id:
            return None
        parent = self._lifecycle.get_task(parent_task_id)
        if parent is None:
            return None
        if parent.phase not in {"completed", "failed", "cancelled"}:
            return None
        return (
            f"Parent task '{parent_task_id}' is already {parent.phase}; "
            "rejecting child admission fail-closed."
        )

    def _cancel_live_child_subtree(
        self,
        *,
        task: KernelTask,
        result: KernelResult,
    ) -> None:
        if result.phase not in {"failed", "cancelled"}:
            return
        for child in self._list_child_tasks(task.id):
            if child.phase in {"completed", "failed", "cancelled"}:
                continue
            self.cancel_task(
                child.id,
                resolution=(
                    f"Parent task '{task.id}' {result.phase}; closing child fail-closed."
                ),
            )

    def _reconcile_parent_after_child_terminal(self, task: KernelTask) -> None:
        parent_task_id = str(task.parent_task_id or "").strip()
        if not parent_task_id:
            return
        parent = self._lifecycle.get_task(parent_task_id)
        if parent is None or parent.phase != "executing":
            return
        child_tasks = self._list_child_tasks(parent_task_id)
        if not child_tasks:
            return
        if any(child.phase not in {"completed", "failed", "cancelled"} for child in child_tasks):
            return
        summary = self._terminal_child_summary(child_tasks)
        if any(child.phase in {"failed", "cancelled"} for child in child_tasks):
            if _parent_requires_explicit_terminal_close(parent):
                return
            self.fail_task(parent_task_id, error=summary)
            return
        if _parent_requires_explicit_terminal_close(parent):
            deferred_summary = self._deferred_explicit_closeout_summary(parent)
            if deferred_summary is None:
                return
            self.complete_task(
                parent_task_id,
                summary=deferred_summary,
                metadata={"source": "delegation-child-closeout"},
            )
            return
        self.complete_task(
            parent_task_id,
            summary=summary,
            metadata={
                "source": "delegation-child-closure",
                "child_task_ids": [child.id for child in child_tasks],
            },
        )

    def _list_child_tasks(self, parent_task_id: str) -> list[KernelTask]:
        if self._task_store is None:
            return []
        return self._task_store.list_child_tasks(parent_task_id=parent_task_id)

    def _remember_deferred_explicit_closeout(
        self,
        task: KernelTask,
        *,
        summary: str,
    ) -> KernelTask:
        payload = dict(task.payload) if isinstance(task.payload, dict) else {}
        pending = payload.get(_DEFERRED_EXPLICIT_CLOSEOUT_KEY)
        if isinstance(pending, dict) and str(pending.get("summary") or "").strip() == summary.strip():
            return task
        payload[_DEFERRED_EXPLICIT_CLOSEOUT_KEY] = {"summary": summary}
        return self._replace_task_payload(task, payload)

    def _clear_deferred_explicit_closeout(self, task: KernelTask) -> KernelTask:
        payload = dict(task.payload) if isinstance(task.payload, dict) else {}
        if _DEFERRED_EXPLICIT_CLOSEOUT_KEY not in payload:
            return task
        payload.pop(_DEFERRED_EXPLICIT_CLOSEOUT_KEY, None)
        return self._replace_task_payload(task, payload)

    def _deferred_explicit_closeout_summary(self, task: KernelTask) -> str | None:
        payload = dict(task.payload) if isinstance(task.payload, dict) else {}
        pending = payload.get(_DEFERRED_EXPLICIT_CLOSEOUT_KEY)
        if not isinstance(pending, dict):
            return None
        summary = str(pending.get("summary") or "").strip()
        return summary or None

    def _replace_task_payload(
        self,
        task: KernelTask,
        payload: dict[str, object],
    ) -> KernelTask:
        updated_task = task.model_copy(
            update={"payload": payload, "updated_at": datetime.now(timezone.utc)},
        )
        lifecycle_tasks = getattr(self._lifecycle, "_tasks", None)
        if isinstance(lifecycle_tasks, dict):
            lifecycle_tasks[updated_task.id] = updated_task
        if self._task_store is not None:
            self._task_store.upsert(updated_task)
        return updated_task

    @staticmethod
    def _terminal_child_summary(child_tasks: list[KernelTask]) -> str:
        completed = sum(1 for child in child_tasks if child.phase == "completed")
        failed = sum(1 for child in child_tasks if child.phase == "failed")
        cancelled = sum(1 for child in child_tasks if child.phase == "cancelled")
        if failed or cancelled:
            return (
                "Delegated child tasks finished with "
                f"{completed} completed, {failed} failed, {cancelled} cancelled."
            )
        return f"All {completed} delegated child task(s) completed."


def _auto_complete_on_approval(task: KernelTask) -> bool:
    return bool(
        task.capability_ref in {None, ""}
        and isinstance(task.payload, dict)
        and task.payload.get("auto_complete_on_approval") is True
    )


def _approval_completion_summary(task: KernelTask) -> str | None:
    if not isinstance(task.payload, dict):
        return None
    value = task.payload.get("approval_completion_summary")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parent_requires_explicit_terminal_close(task: KernelTask) -> bool:
    capability_ref = str(task.capability_ref or "").strip()
    return capability_ref in {"system:dispatch_query", "system:dispatch_command"}


_MAIN_BRAIN_OUTCOME_CAPABILITY_PREFIXES = ("tool:", "skill:", "mcp:")
_MAIN_BRAIN_OUTCOME_CAPABILITY_REFS = frozenset(
    {
        "system:dispatch_query",
        "system:dispatch_command",
        "system:run_fixed_sop",
    },
)


def _should_record_main_brain_outcome(task: KernelTask) -> bool:
    owner_agent_id = str(task.owner_agent_id or "").strip()
    if not owner_agent_id:
        return False
    if (
        owner_agent_id != MAIN_BRAIN_DECISION_ACTOR
        and not is_execution_core_agent_id(owner_agent_id)
    ):
        return False
    capability_ref = str(task.capability_ref or "").strip()
    if not capability_ref or capability_ref == "system:replay_routine":
        return False
    if capability_ref.startswith(_MAIN_BRAIN_OUTCOME_CAPABILITY_PREFIXES):
        return True
    return capability_ref in _MAIN_BRAIN_OUTCOME_CAPABILITY_REFS


def _task_outcome_change_type(phase: str) -> str:
    if phase == "completed":
        return "capability_completed"
    if phase == "failed":
        return "capability_failed"
    return "capability_cancelled"


def _resolve_task_learning_context(task: KernelTask) -> dict[str, str | None]:
    payload = task.payload if isinstance(task.payload, dict) else {}
    request_context = payload.get("request_context")
    request = payload.get("request")
    meta = payload.get("meta")
    request_context_mapping = (
        dict(request_context) if isinstance(request_context, dict) else {}
    )
    request_mapping = dict(request) if isinstance(request, dict) else {}
    meta_mapping = dict(meta) if isinstance(meta, dict) else {}
    role_name = None
    if is_execution_core_agent_id(task.owner_agent_id):
        role_name = "execution-core"
    elif str(task.owner_agent_id or "").strip() == MAIN_BRAIN_DECISION_ACTOR:
        role_name = "main-brain"
    return {
        "source_agent_id": _normalize_optional_str(
            payload.get("source_agent_id")
            or request_context_mapping.get("source_agent_id")
            or meta_mapping.get("source_agent_id"),
        )
        or (
            MAIN_BRAIN_DECISION_ACTOR
            if is_execution_core_agent_id(task.owner_agent_id)
            else None
        ),
        "industry_instance_id": _normalize_optional_str(
            payload.get("industry_instance_id")
            or request_context_mapping.get("industry_instance_id")
            or request_mapping.get("industry_instance_id")
            or meta_mapping.get("industry_instance_id"),
        ),
        "industry_role_id": _normalize_optional_str(
            payload.get("industry_role_id")
            or request_context_mapping.get("industry_role_id")
            or request_mapping.get("industry_role_id")
            or meta_mapping.get("industry_role_id"),
        ),
        "owner_scope": _normalize_optional_str(
            payload.get("owner_scope")
            or request_context_mapping.get("owner_scope")
            or request_mapping.get("owner_scope")
            or meta_mapping.get("owner_scope"),
        ),
        "role_name": role_name,
    }


def _normalize_optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
