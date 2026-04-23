# -*- coding: utf-8 -*-
"""Formal task delegation service for V2 multi-agent coordination."""
from __future__ import annotations

from datetime import datetime, timezone
import inspect
from typing import Any

from ..evidence import EvidenceLedger, EvidenceRecord
from ..industry.identity import is_execution_core_agent_id
from ..state.repositories import SqliteTaskRepository, SqliteTaskRuntimeRepository
from .child_run_shell import (
    resolve_child_run_mcp_manager,
    resolve_child_run_mcp_overlay_contract,
    resolve_child_run_writer_contract,
    run_child_task_with_writer_lease,
)
from .dispatcher import KernelDispatcher
from .models import KernelResult, KernelTask, RiskLevel
from .persistence import decode_kernel_task_metadata
from .teammate_resolution import resolve_teammate_target

_TERMINAL_TASK_STATUSES = frozenset({"completed", "failed", "cancelled"})
_ACTIVE_TASK_STATUSES = frozenset(
    {"created", "queued", "running", "waiting", "blocked", "needs-confirm"},
)
_INFLIGHT_TASK_STATUSES = frozenset({"queued", "running", "waiting", "blocked", "needs-confirm"})
_INFLIGHT_RUNTIME_STATUSES = frozenset({"active", "hydrating", "waiting-confirm"})
_INFLIGHT_RUNTIME_PHASES = frozenset({"risk-check", "executing", "waiting-confirm"})
_DELEGATION_COMPAT_EXECUTION_SOURCE = "delegation-compat"
_DELEGATION_COMPATIBILITY_MODE = "delegation-compat"


class DelegationError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class DelegationTargetNotFound(KeyError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = "target_not_found"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _non_empty_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _canonical_child_result_phase(value: object | None) -> str | None:
    normalized = _non_empty_text(value)
    if normalized is None:
        return None
    phase = normalized.lower()
    if phase == "canceled":
        return "cancelled"
    if phase == "blocked":
        return "waiting-confirm"
    if phase in {"completed", "failed", "cancelled", "waiting-confirm"}:
        return phase
    return None


def _model_dump_payload(value: object) -> dict[str, object]:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


class TaskDelegationService:
    """Create real child tasks and report delegation governance status."""

    def __init__(
        self,
        *,
        task_repository: SqliteTaskRepository,
        task_runtime_repository: SqliteTaskRuntimeRepository,
        kernel_dispatcher: KernelDispatcher | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        agent_profile_service: object | None = None,
        industry_service: object | None = None,
        environment_service: object | None = None,
        mcp_manager: object | None = None,
        actor_mailbox_service: object | None = None,
        actor_supervisor: object | None = None,
        runtime_event_bus: object | None = None,
        experience_memory_service: object | None = None,
        overload_threshold: int = 5,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._kernel_dispatcher = kernel_dispatcher
        self._evidence_ledger = evidence_ledger
        self._agent_profile_service = agent_profile_service
        self._industry_service = industry_service
        self._environment_service = environment_service
        self._mcp_manager = mcp_manager
        self._actor_mailbox_service = actor_mailbox_service
        self._actor_supervisor = actor_supervisor
        self._runtime_event_bus = runtime_event_bus
        self._experience_memory_service = experience_memory_service
        self._overload_threshold = max(1, overload_threshold)

    async def delegate_task(
        self,
        parent_task_id: str,
        *,
        title: str,
        owner_agent_id: str,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        target_role_name: str | None = None,
        prompt_text: str | None = None,
        summary: str | None = None,
        capability_ref: str = "system:dispatch_query",
        risk_level: RiskLevel = "guarded",
        environment_ref: str | None = None,
        channel: str = "console",
        session_id: str | None = None,
        user_id: str | None = None,
        request_payload: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
        actor: str = "runtime-center",
        execute: bool = False,
        force: bool = False,
        industry_instance_id: str | None = None,
        industry_role_id: str | None = None,
        industry_label: str | None = None,
        owner_scope: str | None = None,
        session_kind: str | None = None,
        work_context_id: str | None = None,
        context_key: str | None = None,
        access_mode: str | None = None,
        lease_class: str | None = None,
        writer_lock_scope: str | None = None,
        inherit_environment_ref: bool = True,
    ) -> dict[str, object]:
        parent_task = self._task_repository.get_task(parent_task_id)
        if parent_task is None:
            raise KeyError(f"Task '{parent_task_id}' not found")
        if self._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not available for delegation")

        candidate_agent_id = str(target_agent_id or owner_agent_id).strip()
        if not candidate_agent_id:
            raise DelegationTargetNotFound("Target agent is required for delegation.")
        resolution = resolve_teammate_target(
            candidate_agent_id=candidate_agent_id,
            target_role_id=target_role_id,
            target_role_name=target_role_name,
            industry_instance_id=industry_instance_id,
            industry_service=self._industry_service,
            agent_profile_service=self._agent_profile_service,
        )
        if resolution.error_code == "target_ambiguous":
            raise DelegationError(str(resolution.error), code="target_ambiguous")
        if resolution.error_code:
            raise DelegationTargetNotFound(str(resolution.error))
        resolved_agent_id = resolution.agent_id or candidate_agent_id

        resolved_environment_ref = (
            str(environment_ref).strip()
            if isinstance(environment_ref, str) and environment_ref.strip()
            else (
                self._task_environment_ref(parent_task)
                if inherit_environment_ref
                else None
            )
        )
        if capability_ref == "system:dispatch_query" and self._agent_profile_service is not None:
            getter = getattr(self._agent_profile_service, "get_agent", None)
            profile = getter(resolved_agent_id) if callable(getter) else None
            capabilities = getattr(profile, "capabilities", None) if profile is not None else None
            if isinstance(capabilities, list) and "system:dispatch_query" not in capabilities:
                raise DelegationError(
                    f"Target agent '{resolved_agent_id}' is not authorized for dispatch_query.",
                    code="target_not_authorized",
                )
        governance = self.preview_delegation(
            parent_task_id=parent_task_id,
            owner_agent_id=resolved_agent_id,
            environment_ref=resolved_environment_ref,
            access_mode=access_mode,
            lease_class=lease_class,
            writer_lock_scope=writer_lock_scope,
        )
        if governance["blocked"] and not force:
            error_code = "governance_blocked"
            if governance.get("overloaded"):
                error_code = "target_overloaded"
            elif governance.get("conflict_count") or governance.get("writer_conflict_count"):
                error_code = "environment_conflict"
            raise DelegationError(str(governance["summary"]), code=error_code)

        child_payload = self._build_child_payload(
            parent_task_id=parent_task_id,
            owner_agent_id=resolved_agent_id,
            capability_ref=capability_ref,
            prompt_text=prompt_text,
            channel=channel,
            session_id=session_id,
            user_id=user_id,
            request_payload=request_payload,
            payload=payload,
            industry_instance_id=industry_instance_id,
            industry_role_id=industry_role_id or resolution.role_id,
            industry_label=industry_label,
            owner_scope=owner_scope,
            session_kind=session_kind,
            work_context_id=work_context_id,
            context_key=context_key,
            summary=summary,
            assignment_id=getattr(parent_task, "assignment_id", None),
            lane_id=getattr(parent_task, "lane_id", None),
            cycle_id=getattr(parent_task, "cycle_id", None),
            report_back_mode=getattr(parent_task, "report_back_mode", None),
            environment_ref=resolved_environment_ref,
            access_mode=access_mode,
            lease_class=lease_class,
            writer_lock_scope=writer_lock_scope,
        )
        child_task = KernelTask(
            goal_id=parent_task.goal_id,
            parent_task_id=parent_task.id,
            work_context_id=parent_task.work_context_id,
            title=title.strip(),
            capability_ref=capability_ref,
            environment_ref=resolved_environment_ref,
            owner_agent_id=resolved_agent_id,
            risk_level=risk_level,
            payload=child_payload,
        )

        admitted = self._kernel_dispatcher.submit(child_task)
        mailbox_item = None
        executed: KernelResult | None = None
        if execute and admitted.phase == "executing":
            executed = await self._execute_delegated_child_task(
                child_task,
                mailbox_item=mailbox_item,
            )

        self._append_parent_evidence(
            parent_task_id=parent_task.id,
            child_task=child_task,
            actor=actor,
            governance=governance,
            executed=executed,
        )
        self._publish_runtime_event(
            topic="delegation",
            action="created",
            payload={
                "parent_task_id": parent_task.id,
                "child_task_id": child_task.id,
                "owner_agent_id": resolved_agent_id,
                "execute": execute,
                "blocked": governance["blocked"],
                "mailbox_id": getattr(mailbox_item, "id", None),
            },
        )

        child_record = self._task_repository.get_task(child_task.id)
        child_runtime = self._task_runtime_repository.get_runtime(child_task.id)
        if mailbox_item is not None and self._actor_mailbox_service is not None:
            get_item = getattr(self._actor_mailbox_service, "get_item", None)
            if callable(get_item):
                refreshed_item = get_item(mailbox_item.id)
                if refreshed_item is not None:
                    mailbox_item = refreshed_item
        return {
            "parent_task": self._task_payload(parent_task.id),
            "child_task": (
                self._task_payload(child_task.id)
                if child_record is not None
                else self._kernel_task_payload(child_task, runtime=child_runtime)
            ),
            "dispatch_result": (
                executed.model_dump(mode="json")
                if executed is not None
                else _model_dump_payload(admitted)
            ),
            "governance": governance,
            "target_agent": self._agent_payload(resolved_agent_id),
            "target_agent_id": resolved_agent_id,
            "child_task_id": child_task.id,
            "mailbox_id": getattr(mailbox_item, "id", None),
            "dispatch_status": (
                executed.phase
                if executed is not None
                else (
                    getattr(mailbox_item, "status", None)
                    or ("queued" if mailbox_item is not None else admitted.phase)
                )
            ),
            "latest_result_summary": (
                executed.summary
                if executed is not None
                else (
                    getattr(mailbox_item, "result_summary", None)
                    or getattr(mailbox_item, "error_summary", None)
                    or getattr(admitted, "summary", None)
                    or getattr(mailbox_item, "summary", None)
                    or getattr(admitted, "phase", None)
                )
            ),
            "routes": {
                "parent_task": f"/api/runtime-center/tasks/{parent_task.id}",
                "child_task": f"/api/runtime-center/tasks/{child_task.id}",
                "mailbox": None,
            },
        }

    async def _execute_delegated_child_task(
        self,
        child_task: KernelTask,
        *,
        mailbox_item: object | None,
    ) -> KernelResult | None:
        if mailbox_item is None or self._actor_mailbox_service is None:
            contract = resolve_child_run_writer_contract(
                payload=child_task.payload,
                environment_ref=child_task.environment_ref,
            )
            mcp_overlay_contract = resolve_child_run_mcp_overlay_contract(
                payload=child_task.payload,
            )
            mcp_manager = resolve_child_run_mcp_manager(
                kernel_dispatcher=self._kernel_dispatcher,
                mcp_manager=self._mcp_manager,
            )
            result = await run_child_task_with_writer_lease(
                label=f"delegation:{child_task.owner_agent_id}",
                execute=lambda: self._kernel_dispatcher.execute_task(child_task.id),
                environment_service=self._environment_service,
                owner_agent_id=child_task.owner_agent_id,
                worker_id=None,
                contract=contract,
                mcp_manager=mcp_manager,
                mcp_overlay_contract=mcp_overlay_contract,
                ttl_seconds=180,
                heartbeat_interval_seconds=15.0,
            )
            self._maybe_write_experience(
                child_task=child_task,
                mailbox_item=mailbox_item,
                result=result,
                checkpoint_id=None,
            )
            return result

        if self._actor_supervisor is None:
            return None
        runner = getattr(self._actor_supervisor, "run_agent_once", None)
        if not callable(runner):
            return None
        maybe_result = runner(child_task.owner_agent_id)
        if inspect.isawaitable(maybe_result):
            await maybe_result
        snapshot = self._child_task_result_from_state(
            child_task,
            mailbox_item=mailbox_item,
            fallback_summary="Queued delegated task",
        )
        return snapshot

    def _maybe_write_experience(
        self,
        *,
        child_task: KernelTask,
        mailbox_item: object | None,
        result: KernelResult,
        checkpoint_id: str | None,
    ) -> None:
        remember = getattr(self._experience_memory_service, "remember_outcome", None)
        if (
            not callable(remember)
            or is_execution_core_agent_id(child_task.owner_agent_id)
            or result.phase == "waiting-confirm"
        ):
            return
        profile = None
        getter = getattr(self._agent_profile_service, "get_agent", None)
        if callable(getter):
            profile = getter(child_task.owner_agent_id)
        payload = child_task.payload if isinstance(child_task.payload, dict) else {}
        metadata = dict(getattr(mailbox_item, "metadata", None) or {})
        metadata.update(
            {
                "checkpoint_id": checkpoint_id,
                "trace_id": child_task.trace_id,
                "parent_task_id": child_task.parent_task_id,
                "assignment_id": payload.get("assignment_id"),
                "execution_source": _DELEGATION_COMPAT_EXECUTION_SOURCE,
                "formal_surface": False,
                "compatibility_mode": _DELEGATION_COMPATIBILITY_MODE,
            },
        )
        remember(
            agent_id=child_task.owner_agent_id,
            title=child_task.title,
            status=result.phase,
            summary=result.summary,
            error_summary=result.error,
            capability_ref=child_task.capability_ref,
            mailbox_id=str(getattr(mailbox_item, "id", "") or "").strip() or None,
            task_id=child_task.id,
            source_agent_id=(
                str(getattr(mailbox_item, "source_agent_id", "") or "").strip()
                or str(metadata.get("source_agent_id") or "").strip()
                or None
            ),
            industry_instance_id=str(payload.get("industry_instance_id") or "").strip() or None,
            industry_role_id=str(payload.get("industry_role_id") or "").strip() or None,
            role_name=str(getattr(profile, "role_name", "") or "").strip() or None,
            owner_scope=str(payload.get("owner_scope") or "").strip() or None,
            metadata=metadata,
        )

    def preview_delegation(
        self,
        *,
        parent_task_id: str,
        owner_agent_id: str,
        environment_ref: str | None,
        access_mode: str | None = None,
        lease_class: str | None = None,
        writer_lock_scope: str | None = None,
    ) -> dict[str, object]:
        active_tasks = [
            task
            for task in self._task_repository.list_tasks(owner_agent_id=owner_agent_id)
            if task.id != parent_task_id and self._task_counts_as_inflight(task)
        ]
        conflicting_tasks = [
            self._task_payload(task.id)
            for task in self._task_repository.list_tasks()
            if task.id != parent_task_id
            and self._task_counts_as_inflight(task)
            and environment_ref
            and self._task_environment_ref(task) == environment_ref
            and task.owner_agent_id != owner_agent_id
        ]
        overloaded = len(active_tasks) >= self._overload_threshold
        writer_conflicts: list[dict[str, object]] = []
        normalized_scope = _non_empty_text(writer_lock_scope)
        if (
            access_mode == "writer"
            and normalized_scope is not None
            and self._environment_service is not None
        ):
            getter = getattr(self._environment_service, "get_shared_writer_lease", None)
            if callable(getter):
                lease = getter(writer_lock_scope=normalized_scope)
                if (
                    lease is not None
                    and getattr(lease, "lease_status", None) == "leased"
                    and getattr(lease, "lease_owner", None)
                    and getattr(lease, "lease_owner", None) != owner_agent_id
                ):
                    lease_metadata = (
                        getattr(lease, "metadata", {})
                        if isinstance(getattr(lease, "metadata", None), dict)
                        else {}
                    )
                    writer_conflicts.append(
                        {
                            "lease_id": getattr(lease, "id", None),
                            "lease_owner": getattr(lease, "lease_owner", None),
                            "lease_class": lease_class or lease_metadata.get("lease_class"),
                            "access_mode": access_mode,
                            "writer_lock_scope": normalized_scope,
                            "environment_ref": lease_metadata.get("environment_ref"),
                        },
                    )
        reasons: list[str] = []
        if overloaded:
            reasons.append(
                f"Target agent '{owner_agent_id}' already has {len(active_tasks)} active task(s).",
            )
        if conflicting_tasks:
            reasons.append(
                f"Environment '{environment_ref}' is already in use by {len(conflicting_tasks)} active task(s).",
            )
        if writer_conflicts:
            reasons.append(
                f"Writer scope '{normalized_scope}' is already reserved by '{writer_conflicts[0]['lease_owner']}'.",
            )
        return {
            "blocked": bool(reasons),
            "summary": (
                "Delegation blocked: " + " ".join(reasons)
                if reasons
                else "Delegation can proceed."
            ),
            "active_task_count": len(active_tasks),
            "active_tasks": [self._task_payload(task.id) for task in active_tasks[:10]],
            "overloaded": overloaded,
            "conflict_count": len(conflicting_tasks),
            "conflicting_tasks": conflicting_tasks[:10],
            "writer_conflict_count": len(writer_conflicts),
            "writer_conflicts": writer_conflicts[:10],
            "writer_lock_scope": normalized_scope,
            "target_environment_ref": environment_ref,
            "thresholds": {
                "overload_threshold": self._overload_threshold,
            },
        }

    def _task_counts_as_inflight(self, task: object) -> bool:
        task_id = str(getattr(task, "id", "") or "")
        status = str(getattr(task, "status", "") or "")
        if status in _TERMINAL_TASK_STATUSES:
            return False
        runtime = self._task_runtime_repository.get_runtime(task_id)
        runtime_status = str(getattr(runtime, "runtime_status", "") or "")
        current_phase = str(getattr(runtime, "current_phase", "") or "")
        if (
            runtime_status in _INFLIGHT_RUNTIME_STATUSES
            or current_phase in _INFLIGHT_RUNTIME_PHASES
        ):
            return True
        if runtime_status in {"cold", "terminated"}:
            return False
        return status in _INFLIGHT_TASK_STATUSES

    def _child_task_result_from_state(
        self,
        child_task: KernelTask,
        *,
        mailbox_item: object | None,
        fallback_summary: str,
    ) -> KernelResult | None:
        refreshed_mailbox = self._refresh_mailbox_item(mailbox_item)
        mailbox_status = str(getattr(refreshed_mailbox, "status", "") or "")
        mailbox_phase = self._mailbox_status_to_phase(mailbox_status)
        if mailbox_phase is None:
            return None

        child_record = self._task_repository.get_task(child_task.id)
        child_runtime = self._task_runtime_repository.get_runtime(child_task.id)
        runtime_phase = _canonical_child_result_phase(
            getattr(child_runtime, "current_phase", None),
        )
        checkpoint = self._latest_child_result_checkpoint(
            child_task,
            mailbox_item=refreshed_mailbox,
        )
        checkpoint_result = self._checkpoint_result_payload(checkpoint)
        phase = (
            self._checkpoint_result_phase(checkpoint_result)
            or runtime_phase
            or mailbox_phase
        )
        summary = (
            _non_empty_text(checkpoint_result.get("summary")) if checkpoint_result else None
        ) or (
            _non_empty_text(getattr(checkpoint, "summary", None)) if checkpoint is not None else None
        ) or (
            str(getattr(refreshed_mailbox, "result_summary", "") or "").strip()
            or str(getattr(refreshed_mailbox, "error_summary", "") or "").strip()
            or str(getattr(child_runtime, "last_result_summary", "") or "").strip()
            or str(getattr(child_runtime, "last_error_summary", "") or "").strip()
            or str(getattr(child_record, "summary", "") or "").strip()
            or fallback_summary
        )
        checkpoint_error = (
            _non_empty_text(checkpoint_result.get("error"))
            if checkpoint_result is not None
            else None
        )
        error = (
            None
            if phase == "completed"
            else checkpoint_error
            or str(getattr(refreshed_mailbox, "error_summary", "") or "").strip()
            or str(getattr(child_runtime, "last_error_summary", "") or "").strip()
            or None
        )
        explicit_success = (
            checkpoint_result.get("success")
            if checkpoint_result is not None
            else None
        )
        success = (
            explicit_success
            if isinstance(explicit_success, bool)
            else phase == "completed"
        )
        if phase != "completed":
            success = False
        evidence_id = (
            _non_empty_text(checkpoint_result.get("evidence_id"))
            if checkpoint_result is not None
            else None
        )
        decision_request_id = (
            _non_empty_text(checkpoint_result.get("decision_request_id"))
            if checkpoint_result is not None
            else None
        )
        output_payload = (
            dict(checkpoint_result.get("output"))
            if checkpoint_result is not None
            and isinstance(checkpoint_result.get("output"), dict)
            else None
        )
        return KernelResult(
            task_id=child_task.id,
            trace_id=(
                _non_empty_text(checkpoint_result.get("trace_id"))
                if checkpoint_result is not None
                else None
            )
            or child_task.trace_id,
            success=success,
            phase=phase,  # type: ignore[arg-type]
            summary=summary,
            evidence_id=evidence_id,
            decision_request_id=decision_request_id,
            error=error,
            output=output_payload,
        )

    def _latest_child_result_checkpoint(
        self,
        child_task: KernelTask,
        *,
        mailbox_item: object | None,
    ) -> object | None:
        if self._actor_mailbox_service is None:
            return None
        lister = getattr(self._actor_mailbox_service, "list_checkpoints", None)
        if not callable(lister):
            return None
        mailbox_id = _non_empty_text(getattr(mailbox_item, "id", None))
        checkpoints = lister(
            agent_id=child_task.owner_agent_id,
            mailbox_id=mailbox_id,
            task_id=child_task.id,
            limit=20,
        )
        for checkpoint in checkpoints:
            if str(getattr(checkpoint, "checkpoint_kind", "") or "") == "task-result":
                return checkpoint
        return None

    def _checkpoint_result_payload(
        self,
        checkpoint: object | None,
    ) -> dict[str, object] | None:
        snapshot_payload = getattr(checkpoint, "snapshot_payload", None)
        if not isinstance(snapshot_payload, dict):
            return None
        result = snapshot_payload.get("result")
        if not isinstance(result, dict):
            return None
        return dict(result)

    def _checkpoint_result_phase(
        self,
        checkpoint_result: dict[str, object] | None,
    ) -> str | None:
        if checkpoint_result is None:
            return None
        output_payload = checkpoint_result.get("output")
        if isinstance(output_payload, dict):
            phase = _canonical_child_result_phase(output_payload.get("dispatch_status"))
            if phase is not None:
                return phase
            phase = _canonical_child_result_phase(output_payload.get("phase"))
            if phase is not None:
                return phase
            phase = _canonical_child_result_phase(output_payload.get("status"))
            if phase is not None:
                return phase
        phase = _canonical_child_result_phase(checkpoint_result.get("dispatch_status"))
        if phase is not None:
            return phase
        phase = _canonical_child_result_phase(checkpoint_result.get("phase"))
        if phase is not None:
            return phase
        return _canonical_child_result_phase(checkpoint_result.get("status"))

    def _refresh_mailbox_item(self, mailbox_item: object | None) -> object | None:
        mailbox_id = getattr(mailbox_item, "id", None)
        if not (isinstance(mailbox_id, str) and mailbox_id.strip()):
            return mailbox_item
        getter = getattr(self._actor_mailbox_service, "get_item", None)
        if not callable(getter):
            return mailbox_item
        return getter(mailbox_id) or mailbox_item

    def _mailbox_status_to_phase(self, mailbox_status: str) -> str | None:
        if mailbox_status == "completed":
            return "completed"
        if mailbox_status == "blocked":
            return "waiting-confirm"
        if mailbox_status == "cancelled":
            return "cancelled"
        if mailbox_status == "failed":
            return "failed"
        return None

    def _build_child_payload(
        self,
        *,
        parent_task_id: str,
        owner_agent_id: str,
        capability_ref: str,
        prompt_text: str | None,
        channel: str,
        session_id: str | None,
        user_id: str | None,
        request_payload: dict[str, object] | None,
        payload: dict[str, object] | None,
        industry_instance_id: str | None,
        industry_role_id: str | None,
        industry_label: str | None,
        owner_scope: str | None,
        session_kind: str | None,
        work_context_id: str | None,
        context_key: str | None,
        summary: str | None,
        assignment_id: str | None,
        lane_id: str | None,
        cycle_id: str | None,
        report_back_mode: str | None,
        environment_ref: str | None,
        access_mode: str | None,
        lease_class: str | None,
        writer_lock_scope: str | None,
    ) -> dict[str, object]:
        execution_source = _DELEGATION_COMPAT_EXECUTION_SOURCE

        def _apply_execution_envelope(base_payload: dict[str, object]) -> dict[str, object]:
            payload_meta = dict(base_payload.get("meta") or {})
            payload_meta.update(
                {
                    "source_kind": payload_meta.get("source_kind") or "delegation",
                    "parent_task_id": parent_task_id,
                    "summary": summary,
                    "work_context_id": work_context_id,
                    "context_key": context_key,
                    "assignment_id": assignment_id,
                    "execution_source": execution_source,
                    "formal_surface": False,
                    "compatibility_mode": _DELEGATION_COMPATIBILITY_MODE,
                    "lane_id": lane_id,
                    "cycle_id": cycle_id,
                    "report_back_mode": report_back_mode,
                    "environment_ref": environment_ref,
                    "access_mode": access_mode,
                    "lease_class": lease_class,
                    "writer_lock_scope": writer_lock_scope,
                },
            )
            base_payload["meta"] = {
                key: value
                for key, value in payload_meta.items()
                if value is not None and value != ""
            }
            for key, value in (
                ("assignment_id", assignment_id),
                ("lane_id", lane_id),
                ("cycle_id", cycle_id),
                ("report_back_mode", report_back_mode),
                ("formal_surface", False),
                ("compatibility_mode", _DELEGATION_COMPATIBILITY_MODE),
            ):
                if value is not None and key not in base_payload:
                    base_payload[key] = value
            return base_payload

        if capability_ref != "system:dispatch_query":
            return _apply_execution_envelope(dict(payload or {}))
        if request_payload is not None:
            request = dict(request_payload)
            if work_context_id:
                request.setdefault("work_context_id", work_context_id)
            if context_key:
                request.setdefault("context_key", context_key)
            return _apply_execution_envelope(
                {
                    "dispatch_request": request,
                    "request": request,
                    "request_context": dict(request),
                    "mode": "final",
                    "dispatch_events": False,
                },
            )
        normalized_prompt_text = str(prompt_text or "").strip()
        if not normalized_prompt_text:
            raise ValueError("prompt_text is required for delegated system:dispatch_query")
        resolved_channel = str(channel or "console").strip() or "console"
        resolved_session_id = (
            str(session_id).strip()
            if isinstance(session_id, str) and session_id.strip()
            else f"delegate:{parent_task_id}:{owner_agent_id}"
        )
        resolved_user_id = (
            str(user_id).strip()
            if isinstance(user_id, str) and user_id.strip()
            else owner_agent_id
        )
        request = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": normalized_prompt_text}],
                },
            ],
            "session_id": resolved_session_id,
            "user_id": resolved_user_id,
            "channel": resolved_channel,
        }
        if industry_instance_id:
            request["industry_instance_id"] = industry_instance_id
        if industry_role_id:
            request["industry_role_id"] = industry_role_id
        if industry_label:
            request["industry_label"] = industry_label
        if owner_scope:
            request["owner_scope"] = owner_scope
        if session_kind:
            request["session_kind"] = session_kind
        if work_context_id:
            request["work_context_id"] = work_context_id
        if context_key:
            request["context_key"] = context_key
        return _apply_execution_envelope(
            {
                "dispatch_request": request,
                "request": request,
                "request_context": dict(request),
                "mode": "final",
                "dispatch_events": False,
                "task_seed": {
                    "request_preview": normalized_prompt_text[:280],
                    "parent_task_id": parent_task_id,
                },
            },
        )

    def _append_parent_evidence(
        self,
        *,
        parent_task_id: str,
        child_task: KernelTask,
        actor: str,
        governance: dict[str, object],
        executed: KernelResult | None,
    ) -> None:
        if self._evidence_ledger is None:
            return
        result_summary = (
            f"Delegated '{child_task.title}' to '{child_task.owner_agent_id}'."
        )
        if executed is not None:
            result_summary = f"{result_summary} Latest result: {executed.summary}"
        self._evidence_ledger.append(
            EvidenceRecord(
                task_id=parent_task_id,
                actor_ref=actor,
                capability_ref="system:delegate_task",
                environment_ref=child_task.environment_ref,
                risk_level=child_task.risk_level,
                action_summary="delegate child task",
                result_summary=result_summary,
                metadata={
                    "parent_task_id": parent_task_id,
                    "child_task_id": child_task.id,
                    "child_owner_agent_id": child_task.owner_agent_id,
                    "assignment_id": (
                        child_task.payload.get("assignment_id")
                        if isinstance(child_task.payload, dict)
                        else None
                    ),
                    "governance": governance,
                    "executed": executed.model_dump(mode="json") if executed is not None else None,
                },
            ),
        )

    def _task_environment_ref(self, task: Any) -> str | None:
        runtime = self._task_runtime_repository.get_runtime(task.id)
        if runtime is not None and runtime.active_environment_id:
            return str(runtime.active_environment_id)
        metadata = decode_kernel_task_metadata(getattr(task, "acceptance_criteria", None))
        if metadata is None:
            return None
        value = metadata.get("environment_ref")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _task_payload(self, task_id: str) -> dict[str, object]:
        task = self._task_repository.get_task(task_id)
        if task is None:
            return {"id": task_id, "route": f"/api/runtime-center/tasks/{task_id}"}
        runtime = self._task_runtime_repository.get_runtime(task_id)
        payload = task.model_dump(mode="json")
        payload["route"] = f"/api/runtime-center/tasks/{task_id}"
        payload["environment_ref"] = self._task_environment_ref(task)
        if runtime is not None:
            payload["runtime"] = runtime.model_dump(mode="json")
        return payload

    def _kernel_task_payload(
        self,
        task: KernelTask,
        *,
        runtime: Any | None,
    ) -> dict[str, object]:
        payload = task.model_dump(mode="json")
        payload["route"] = f"/api/runtime-center/tasks/{task.id}"
        if runtime is not None and hasattr(runtime, "model_dump"):
            payload["runtime"] = runtime.model_dump(mode="json")
        return payload

    def _agent_payload(self, agent_id: str) -> dict[str, object] | None:
        service = self._agent_profile_service
        getter = getattr(service, "get_agent", None)
        if not callable(getter):
            return None
        profile = getter(agent_id)
        if profile is None:
            return {"agent_id": agent_id, "route": f"/api/runtime-center/agents/{agent_id}"}
        model_dump = getattr(profile, "model_dump", None)
        if callable(model_dump):
            payload = model_dump(mode="json")
        elif isinstance(profile, dict):
            payload = dict(profile)
        else:
            payload = {"agent_id": agent_id}
        payload["route"] = f"/api/runtime-center/agents/{agent_id}"
        return payload

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._runtime_event_bus is None:
            return
        self._runtime_event_bus.publish(topic=topic, action=action, payload=payload)
