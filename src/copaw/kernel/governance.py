# -*- coding: utf-8 -*-
"""Governance services for emergency controls and batch runtime actions."""
from __future__ import annotations

import inspect
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..evidence import EvidenceLedger, EvidenceRecord
from ..state import GovernanceControlRecord
from ..state.repositories import BaseGovernanceControlRepository

logger = logging.getLogger(__name__)

_CONTROL_ID = "runtime"
_GOVERNANCE_TASK_ID = "governance:runtime"
_BLOCKED_SYSTEM_CAPABILITIES = frozenset(
    {
        "system:dispatch_query",
        "system:dispatch_command",
        "system:send_channel_text",
        "system:dispatch_goal",
        "system:dispatch_active_goals",
        "system:run_learning_strategy",
        "system:auto_apply_patches",
        "system:apply_patch",
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _mapping_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _batch_action_label(action: str) -> str:
    mapping = {
        "approve": "批准",
        "reject": "驳回",
        "apply": "应用",
        "rollback": "回滚",
    }
    return mapping.get(action, action)


class GovernanceStatus(BaseModel):
    control_id: str = Field(default=_CONTROL_ID)
    emergency_stop_active: bool = False
    emergency_reason: str | None = None
    emergency_actor: str | None = None
    paused_schedule_ids: list[str] = Field(default_factory=list)
    channel_shutdown_applied: bool = False
    blocked_capability_refs: list[str] = Field(default_factory=list)
    pending_decisions: int = 0
    proposed_patches: int = 0
    pending_patches: int = 0
    metadata: dict[str, object] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=_utc_now)


class GovernanceBatchResult(BaseModel):
    action: str
    requested: int
    succeeded: int
    failed: int
    actor: str
    results: list[dict[str, object]] = Field(default_factory=list)
    errors: list[dict[str, object]] = Field(default_factory=list)
    evidence_id: str | None = None


class GovernanceService:
    """Unified governance surface for runtime controls and operator batches."""

    def __init__(
        self,
        *,
        control_repository: BaseGovernanceControlRepository,
        decision_request_repository: Any | None = None,
        learning_service: Any | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        runtime_event_bus: Any | None = None,
        cron_manager: Any | None = None,
        channel_manager: Any | None = None,
        kernel_dispatcher: Any | None = None,
    ) -> None:
        self._control_repository = control_repository
        self._decision_request_repository = decision_request_repository
        self._learning_service = learning_service
        self._evidence_ledger = evidence_ledger
        self._runtime_event_bus = runtime_event_bus
        self._cron_manager = cron_manager
        self._channel_manager = channel_manager
        self._kernel_dispatcher = kernel_dispatcher

    def set_runtime_managers(
        self,
        *,
        cron_manager: Any | None = None,
        channel_manager: Any | None = None,
    ) -> None:
        self._cron_manager = cron_manager
        self._channel_manager = channel_manager

    def set_kernel_dispatcher(self, dispatcher: Any | None) -> None:
        self._kernel_dispatcher = dispatcher

    def get_control(self) -> GovernanceControlRecord:
        control = self._control_repository.get_control(_CONTROL_ID)
        if control is not None:
            return control
        control = GovernanceControlRecord(id=_CONTROL_ID)
        return self._control_repository.upsert_control(control)

    def get_status(self) -> GovernanceStatus:
        control = self.get_control()
        pending_decisions = 0
        if self._decision_request_repository is not None:
            try:
                pending_decisions = sum(
                    1
                    for decision in self._decision_request_repository.list_decision_requests()
                    if getattr(decision, "status", None) in {"open", "reviewing"}
                )
            except Exception:
                logger.exception("Failed to count pending decisions")
        proposed_patches = 0
        pending_patches = 0
        if self._learning_service is not None:
            try:
                patches = list(self._learning_service.list_patches())
                proposed_patches = sum(
                    1
                    for patch in patches
                    if getattr(patch, "status", None) == "proposed"
                )
                pending_patches = sum(
                    1
                    for patch in patches
                    if getattr(patch, "status", None) in {"proposed", "approved"}
                )
            except Exception:
                logger.exception("Failed to summarize learning patches")
        blocked = []
        if control.emergency_stop_active:
            blocked = sorted(
                [*sorted(_BLOCKED_SYSTEM_CAPABILITIES), "skill:*", "mcp:*", "tool:*"]
            )
        return GovernanceStatus(
            control_id=control.id,
            emergency_stop_active=control.emergency_stop_active,
            emergency_reason=control.emergency_reason,
            emergency_actor=control.emergency_actor,
            paused_schedule_ids=list(control.paused_schedule_ids),
            channel_shutdown_applied=control.channel_shutdown_applied,
            blocked_capability_refs=blocked,
            pending_decisions=pending_decisions,
            proposed_patches=proposed_patches,
            pending_patches=pending_patches,
            metadata=dict(control.metadata),
            updated_at=control.updated_at,
        )

    def admission_block_reason(self, task: Any) -> str | None:
        control = self.get_control()
        if not control.emergency_stop_active:
            return None
        capability_ref = str(getattr(task, "capability_ref", "") or "")
        if not self._should_block_capability(capability_ref):
            return None
        reason = control.emergency_reason or "紧急停止已生效。"
        return (
            f"紧急停止已阻断能力“{capability_ref}”。{reason}"
        )

    async def emergency_stop(
        self,
        *,
        actor: str,
        reason: str,
    ) -> GovernanceStatus:
        control = self.get_control()
        if not control.emergency_stop_active:
            control = control.model_copy(
                update={
                    "emergency_stop_active": True,
                    "emergency_reason": reason,
                    "emergency_actor": actor,
                    "metadata": {
                        **dict(control.metadata),
                        "stopped_at": _utc_now().isoformat(),
                    },
                }
            )
        control = await self._apply_emergency_runtime_state(control)
        persisted = self._control_repository.upsert_control(control)
        evidence_id = self._append_evidence(
            actor=actor,
            capability_ref="system:governance_emergency_stop",
            action_summary="运行时紧急停止",
            result_summary="运行时紧急停止已生效。",
            metadata={
                "reason": reason,
                "paused_schedule_ids": list(persisted.paused_schedule_ids),
                "channel_shutdown_applied": persisted.channel_shutdown_applied,
            },
        )
        self._publish_event(
            action="emergency-stop",
            payload={
                "actor": actor,
                "reason": reason,
                "paused_schedule_ids": list(persisted.paused_schedule_ids),
                "channel_shutdown_applied": persisted.channel_shutdown_applied,
                "evidence_id": evidence_id,
            },
        )
        return self.get_status()

    async def resume(
        self,
        *,
        actor: str,
        reason: str | None = None,
    ) -> GovernanceStatus:
        control = self.get_control()
        if control.emergency_stop_active:
            control = await self._restore_runtime_state(control)
        metadata = dict(control.metadata)
        metadata["last_resumed_at"] = _utc_now().isoformat()
        if reason:
            metadata["last_resume_reason"] = reason
        persisted = self._control_repository.upsert_control(
            control.model_copy(
                update={
                    "emergency_stop_active": False,
                    "emergency_reason": None,
                    "emergency_actor": actor,
                    "paused_schedule_ids": [],
                    "channel_shutdown_applied": False,
                    "metadata": metadata,
                }
            )
        )
        evidence_id = self._append_evidence(
            actor=actor,
            capability_ref="system:governance_resume",
            action_summary="运行治理恢复",
            result_summary="运行时操作已恢复。",
            metadata={
                "reason": reason,
                "evidence_control": persisted.model_dump(mode="json"),
            },
        )
        self._publish_event(
            action="resume",
            payload={
                "actor": actor,
                "reason": reason,
                "evidence_id": evidence_id,
            },
        )
        return self.get_status()

    async def reconcile_runtime_state(self) -> GovernanceStatus:
        control = self.get_control()
        if control.emergency_stop_active:
            control = await self._apply_emergency_runtime_state(control)
            self._control_repository.upsert_control(control)
        return self.get_status()

    async def batch_decisions(
        self,
        *,
        decision_ids: list[str],
        action: str,
        actor: str,
        resolution: str | None = None,
        execute: bool | None = None,
    ) -> GovernanceBatchResult:
        dispatcher = self._kernel_dispatcher
        if dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not available")
        normalized_ids = [item.strip() for item in decision_ids if item and item.strip()]
        results: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for decision_id in normalized_ids:
            try:
                if action == "approve":
                    result = await dispatcher.approve_decision(
                        decision_id,
                        resolution=resolution or f"已由 {actor} 批准。",
                        execute=execute,
                    )
                elif action == "reject":
                    result = dispatcher.reject_decision(
                        decision_id,
                        resolution=resolution or f"已由 {actor} 驳回。",
                    )
                else:
                    raise ValueError(f"Unsupported decision batch action: {action}")
                results.append(result.model_dump(mode="json"))
            except Exception as exc:
                errors.append({"decision_id": decision_id, "error": str(exc)})
        evidence_id = self._append_evidence(
            actor=actor,
            capability_ref=f"system:batch_decision_{action}",
            action_summary=f"批量{_batch_action_label(action)}决策",
            result_summary=(
                f"共处理 {len(normalized_ids)} 条决策："
                f"{len(results)} 条成功，{len(errors)} 条失败。"
            ),
            metadata={
                "decision_ids": normalized_ids,
                "results": results,
                "errors": errors,
                "resolution": resolution,
                "execute": execute,
            },
        )
        self._publish_event(
            action=f"batch-decision-{action}",
            payload={
                "actor": actor,
                "requested": len(normalized_ids),
                "succeeded": len(results),
                "failed": len(errors),
                "evidence_id": evidence_id,
            },
        )
        return GovernanceBatchResult(
            action=f"decision:{action}",
            requested=len(normalized_ids),
            succeeded=len(results),
            failed=len(errors),
            actor=actor,
            results=results,
            errors=errors,
            evidence_id=evidence_id,
        )

    def batch_patches(
        self,
        *,
        patch_ids: list[str],
        action: str,
        actor: str,
    ) -> GovernanceBatchResult:
        service = self._learning_service
        if service is None:
            raise RuntimeError("Learning service is not available")
        normalized_ids = [item.strip() for item in patch_ids if item and item.strip()]
        results: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for patch_id in normalized_ids:
            try:
                if action == "approve":
                    patch = service.approve_patch(patch_id, approved_by=actor)
                elif action == "reject":
                    patch = service.reject_patch(patch_id, rejected_by=actor)
                elif action == "apply":
                    patch = service.apply_patch(patch_id, applied_by=actor)
                elif action == "rollback":
                    patch = service.rollback_patch(patch_id, rolled_back_by=actor)
                else:
                    raise ValueError(f"Unsupported patch batch action: {action}")
                results.append(patch.model_dump(mode="json"))
            except Exception as exc:
                errors.append({"patch_id": patch_id, "error": str(exc)})
        evidence_id = self._append_evidence(
            actor=actor,
            capability_ref=f"system:batch_patch_{action}",
            action_summary=f"批量{_batch_action_label(action)}补丁",
            result_summary=(
                f"共处理 {len(normalized_ids)} 个补丁："
                f"{len(results)} 个成功，{len(errors)} 个失败。"
            ),
            metadata={
                "patch_ids": normalized_ids,
                "results": results,
                "errors": errors,
            },
        )
        self._publish_event(
            action=f"batch-patch-{action}",
            payload={
                "actor": actor,
                "requested": len(normalized_ids),
                "succeeded": len(results),
                "failed": len(errors),
                "evidence_id": evidence_id,
            },
        )
        return GovernanceBatchResult(
            action=f"patch:{action}",
            requested=len(normalized_ids),
            succeeded=len(results),
            failed=len(errors),
            actor=actor,
            results=results,
            errors=errors,
            evidence_id=evidence_id,
        )

    async def _apply_emergency_runtime_state(
        self,
        control: GovernanceControlRecord,
    ) -> GovernanceControlRecord:
        paused_schedule_ids = list(control.paused_schedule_ids)
        if self._cron_manager is not None:
            try:
                jobs = await self._maybe_await(self._cron_manager.list_jobs())
            except Exception:
                logger.exception("Failed to list cron jobs during emergency stop")
                jobs = []
            seen = set(paused_schedule_ids)
            for job in jobs or []:
                job_id = str(getattr(job, "id", "") or "")
                enabled = bool(getattr(job, "enabled", False))
                if not job_id or not enabled:
                    continue
                try:
                    await self._maybe_await(self._cron_manager.pause_job(job_id))
                except Exception:
                    logger.exception("Failed to pause schedule %s during emergency stop", job_id)
                    continue
                if job_id not in seen:
                    paused_schedule_ids.append(job_id)
                    seen.add(job_id)
        channel_shutdown_applied = control.channel_shutdown_applied
        if self._channel_manager is not None and not channel_shutdown_applied:
            try:
                await self._maybe_await(self._channel_manager.stop_all())
                channel_shutdown_applied = True
            except Exception:
                logger.exception("Failed to stop channels during emergency stop")
        return control.model_copy(
            update={
                "paused_schedule_ids": paused_schedule_ids,
                "channel_shutdown_applied": channel_shutdown_applied,
            }
        )

    async def _restore_runtime_state(
        self,
        control: GovernanceControlRecord,
    ) -> GovernanceControlRecord:
        if self._channel_manager is not None and control.channel_shutdown_applied:
            try:
                await self._maybe_await(self._channel_manager.start_all())
            except Exception:
                logger.exception("Failed to restart channels during governance resume")
        if self._cron_manager is not None:
            for schedule_id in control.paused_schedule_ids:
                try:
                    await self._maybe_await(self._cron_manager.resume_job(schedule_id))
                except Exception:
                    logger.exception(
                        "Failed to resume schedule %s during governance resume",
                        schedule_id,
                    )
        return control

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _should_block_capability(capability_ref: str) -> bool:
        if not capability_ref:
            return False
        if capability_ref.startswith(("tool:", "skill:", "mcp:")):
            return True
        return capability_ref in _BLOCKED_SYSTEM_CAPABILITIES

    def _append_evidence(
        self,
        *,
        actor: str,
        capability_ref: str,
        action_summary: str,
        result_summary: str,
        metadata: dict[str, object] | None = None,
    ) -> str | None:
        if self._evidence_ledger is None:
            return None
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=_GOVERNANCE_TASK_ID,
                actor_ref=actor,
                environment_ref="config:runtime",
                capability_ref=capability_ref,
                risk_level="guarded",
                action_summary=action_summary,
                result_summary=result_summary,
                metadata=metadata or {},
            )
        )
        return record.id

    def _publish_event(self, *, action: str, payload: dict[str, object]) -> None:
        if self._runtime_event_bus is None:
            return
        try:
            self._runtime_event_bus.publish(topic="governance", action=action, payload=payload)
        except Exception:
            logger.exception("Failed to publish governance event")


__all__ = [
    "GovernanceBatchResult",
    "GovernanceService",
    "GovernanceStatus",
]
