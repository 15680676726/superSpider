# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Iterable

from fastapi import FastAPI

from ..capabilities import CapabilityService
from ..config import load_config
from ..config.utils import get_config_path
from ..kernel import KernelDispatcher, KernelTask
from ..state import AutomationLoopRuntimeRecord
from .runtime_launch_contract import build_runtime_launch_contract
from .runtime_bootstrap import (
    RuntimeBootstrap,
    attach_runtime_state,
    initialize_mcp_manager,
    runtime_manager_stack_from_app_state,
    start_runtime_manager_stack,
    stop_runtime_manager_stack,
)
from .startup_recovery import run_startup_recovery

logger = logging.getLogger(__name__)

AUTOMATION_COORDINATOR_CONTRACT = "automation-coordinator/v1"


@dataclass
class _AutomationLoopState:
    task_name: str
    capability_ref: str
    owner_agent_id: str
    interval_seconds: int
    automation_task_id: str
    coordinator_contract: str = AUTOMATION_COORDINATOR_CONTRACT
    loop_phase: str = "idle"
    health_status: str = "idle"
    last_gate_reason: str = "not-yet-evaluated"
    last_result_phase: str | None = None
    last_result_summary: str | None = None
    last_error_summary: str | None = None
    last_task_id: str | None = None
    last_evidence_id: str | None = None
    submit_count: int = 0
    consecutive_failures: int = 0
    automation_loop_runtime_repository: object | None = None
    created_at: object | None = None

    def with_contract_payload(self, payload: dict[str, object]) -> dict[str, object]:
        enriched = dict(payload)
        enriched.setdefault("automation_task_id", self.automation_task_id)
        enriched.setdefault("coordinator_contract", self.coordinator_contract)
        enriched.setdefault("automation_loop_name", self.task_name)
        enriched.update(
            {
                key: value
                for key, value in build_runtime_launch_contract(
                    entry_source="automation-loop",
                    coordinator_id=self.automation_task_id,
                    durable_field_prefix="durable_",
                ).items()
                if key not in enriched
            },
        )
        return enriched

    @classmethod
    def from_record(
        cls,
        record: AutomationLoopRuntimeRecord,
        *,
        automation_loop_runtime_repository: object | None = None,
    ) -> "_AutomationLoopState":
        return cls(
            task_name=record.task_name,
            capability_ref=record.capability_ref,
            owner_agent_id=record.owner_agent_id,
            interval_seconds=record.interval_seconds,
            automation_task_id=record.automation_task_id,
            coordinator_contract=record.coordinator_contract,
            loop_phase=record.loop_phase,
            health_status=record.health_status,
            last_gate_reason=record.last_gate_reason or "not-yet-evaluated",
            last_result_phase=record.last_result_phase,
            last_result_summary=record.last_result_summary,
            last_error_summary=record.last_error_summary,
            last_task_id=record.last_task_id,
            last_evidence_id=record.last_evidence_id,
            submit_count=record.submit_count,
            consecutive_failures=record.consecutive_failures,
            automation_loop_runtime_repository=automation_loop_runtime_repository,
            created_at=record.created_at,
        )

    def to_record(self) -> AutomationLoopRuntimeRecord:
        payload: dict[str, object] = {
            "automation_task_id": self.automation_task_id,
            "task_name": self.task_name,
            "capability_ref": self.capability_ref,
            "owner_agent_id": self.owner_agent_id,
            "interval_seconds": self.interval_seconds,
            "coordinator_contract": self.coordinator_contract,
            "loop_phase": self.loop_phase,
            "health_status": self.health_status,
            "last_gate_reason": self.last_gate_reason,
            "last_result_phase": self.last_result_phase,
            "last_result_summary": self.last_result_summary,
            "last_error_summary": self.last_error_summary,
            "last_task_id": self.last_task_id,
            "last_evidence_id": self.last_evidence_id,
            "submit_count": self.submit_count,
            "consecutive_failures": self.consecutive_failures,
        }
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        return AutomationLoopRuntimeRecord(
            **payload,
        )

    def persist(self) -> None:
        repository = self.automation_loop_runtime_repository
        if repository is None:
            return
        upsert_loop = getattr(repository, "upsert_loop", None)
        if not callable(upsert_loop):
            return
        record = upsert_loop(self.to_record())
        self.created_at = getattr(record, "created_at", None) or self.created_at

    def mark_blocked(self, reason: str) -> None:
        self.loop_phase = "blocked"
        self.health_status = "idle"
        self.last_gate_reason = reason
        self.last_result_summary = None
        self.last_error_summary = None
        self.persist()

    def mark_submitting(self, reason: str) -> None:
        self.loop_phase = "submitting"
        self.health_status = "active"
        self.last_gate_reason = reason
        self.last_result_summary = None
        self.last_error_summary = None
        self.submit_count += 1
        self.persist()

    def record_result(self, result: object) -> None:
        phase = str(getattr(result, "phase", "") or "").strip() or "unknown"
        self.last_result_phase = phase
        self.last_result_summary = str(getattr(result, "summary", "") or "").strip() or None
        self.last_error_summary = None
        self.last_task_id = str(getattr(result, "task_id", "") or "").strip() or None
        self.last_evidence_id = (
            str(getattr(result, "evidence_id", "") or "").strip() or None
        )
        if phase == "completed":
            self.loop_phase = "completed"
            self.health_status = "healthy"
            self.consecutive_failures = 0
        elif phase == "skipped":
            self.loop_phase = "skipped"
            self.health_status = "idle"
        elif phase in {"waiting-confirm", "risk-check"}:
            self.loop_phase = phase
            self.health_status = "guarded"
        else:
            self.loop_phase = phase
            self.health_status = "degraded"
        self.persist()

    def record_failure(self, exc: Exception) -> None:
        self.loop_phase = "failed"
        self.health_status = "degraded"
        self.last_result_phase = "failed"
        self.last_result_summary = None
        summary = str(exc).strip()
        self.last_error_summary = summary or exc.__class__.__name__
        self.consecutive_failures += 1
        self.persist()

    def mark_stopped(self) -> None:
        self.loop_phase = "stopped"
        self.health_status = "stopped"
        self.persist()

    def snapshot(self) -> dict[str, object]:
        return {
            "task_name": self.task_name,
            "capability_ref": self.capability_ref,
            "owner_agent_id": self.owner_agent_id,
            "interval_seconds": self.interval_seconds,
            "automation_task_id": self.automation_task_id,
            "coordinator_contract": self.coordinator_contract,
            "loop_phase": self.loop_phase,
            "health_status": self.health_status,
            "last_gate_reason": self.last_gate_reason,
            "last_result_phase": self.last_result_phase,
            "last_result_summary": self.last_result_summary,
            "last_error_summary": self.last_error_summary,
            "last_task_id": self.last_task_id,
            "last_evidence_id": self.last_evidence_id,
            "submit_count": self.submit_count,
            "consecutive_failures": self.consecutive_failures,
        }


class AutomationTaskGroup(list[asyncio.Task[None]]):
    def loop_snapshots(self) -> dict[str, dict[str, object]]:
        snapshots: dict[str, dict[str, object]] = {}
        for task in self:
            state = getattr(task, "copaw_automation_state", None)
            if isinstance(state, _AutomationLoopState):
                snapshots[state.task_name] = state.snapshot()
        return snapshots

    def overview_snapshot(self) -> list[dict[str, object]]:
        snapshots = self.loop_snapshots()
        payloads: list[dict[str, object]] = []
        for index, task in enumerate(self, start=1):
            task_name = task.get_name() if callable(getattr(task, "get_name", None)) else None
            if not isinstance(task_name, str) or not task_name:
                task_name = f"automation-loop-{index}"
            snapshot = snapshots.get(task_name.removeprefix("copaw-automation-"), {})
            if task.cancelled():
                status = "cancelled"
            elif task.done():
                status = "completed"
            else:
                status = "running"
            payloads.append(
                {
                    "name": task_name,
                    "status": status,
                    **snapshot,
                }
            )
        return payloads


def _automation_task_id(
    *,
    task_name: str,
    capability_ref: str,
    owner_agent_id: str,
) -> str:
    return f"{owner_agent_id}:{task_name}:{capability_ref}"


def _automation_loop_state_from_task(
    task: asyncio.Task[Any],
) -> _AutomationLoopState | None:
    state = getattr(task, "copaw_automation_state", None)
    return state if isinstance(state, _AutomationLoopState) else None


def _mark_automation_tasks_stopped(tasks: Iterable[asyncio.Task[Any]]) -> None:
    for task in tasks:
        state = _automation_loop_state_from_task(task)
        if state is not None:
            state.mark_stopped()


def _consume_current_task_cancellation() -> int:
    current = asyncio.current_task()
    if current is None:
        return 0
    uncancel = getattr(current, "uncancel", None)
    if not callable(uncancel):
        return 0
    cleared = 0
    while current.cancelling():
        uncancel()
        cleared += 1
    return cleared


def automation_interval_seconds(env_name: str, default: int) -> int:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r is invalid; using default=%s", env_name, raw, default)
        return default
    return max(30, value)


async def submit_kernel_automation_task(
    dispatcher: KernelDispatcher,
    capability_service: CapabilityService,
    *,
    capability_ref: str,
    title: str,
    owner_agent_id: str,
    payload: dict[str, object],
) -> object:
    if _automation_task_inflight(
        dispatcher,
        capability_ref=capability_ref,
        owner_agent_id=owner_agent_id,
        payload=payload,
    ):
        logger.info(
            "Skipping duplicate automation task for %s owned by %s",
            capability_ref,
            owner_agent_id,
        )
        return SimpleNamespace(
            phase="skipped",
            summary="Duplicate automation task already in flight.",
        )
    mount = capability_service.get_capability(capability_ref)
    task = KernelTask(
        title=title,
        capability_ref=capability_ref,
        owner_agent_id=owner_agent_id,
        risk_level=mount.risk_level if mount is not None else "guarded",
        payload=payload,
    )
    admitted = dispatcher.submit(task)
    if admitted.phase != "executing":
        if admitted.phase == "waiting-confirm":
            logger.warning(
                "Automation task %s (%s) is waiting for confirmation (%s)",
                task.id,
                capability_ref,
                admitted.decision_request_id,
            )
        else:
            logger.warning(
                "Automation task %s (%s) was not admitted for execution: phase=%s summary=%s",
                task.id,
                capability_ref,
                admitted.phase,
                admitted.summary,
            )
        return admitted
    return await dispatcher.execute_task(task.id)


def _automation_task_inflight(
    dispatcher: KernelDispatcher,
    *,
    capability_ref: str,
    owner_agent_id: str,
    payload: dict[str, object],
) -> bool:
    task_store = getattr(dispatcher, "task_store", None)
    if task_store is None:
        return False
    payload_signature = _stable_payload_signature(payload)
    for phase in ("executing", "waiting-confirm", "risk-check"):
        for task in task_store.list_tasks(phase=phase, owner_agent_id=owner_agent_id):
            if getattr(task, "capability_ref", None) != capability_ref:
                continue
            task_payload = task.payload if isinstance(task.payload, dict) else {}
            if _stable_payload_signature(task_payload) != payload_signature:
                continue
            return True
    return False


def _stable_payload_signature(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return repr(sorted(payload.items(), key=lambda item: str(item[0])))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_since(value: object | None) -> float | None:
    if not isinstance(value, datetime):
        return None
    target = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return (_utc_now() - target).total_seconds()


def _reap_stale_kernel_tasks(
    dispatcher: KernelDispatcher,
    *,
    logger: logging.Logger,
) -> list[str]:
    timeout_seconds = getattr(getattr(dispatcher, "_config", None), "execution_timeout_seconds", None)
    if timeout_seconds is None:
        return []
    task_store = getattr(dispatcher, "task_store", None)
    if task_store is None:
        return []
    list_tasks = getattr(task_store, "list_tasks", None)
    get_runtime_record = getattr(task_store, "get_runtime_record", None)
    fail_task = getattr(dispatcher, "fail_task", None)
    if not callable(list_tasks) or not callable(get_runtime_record) or not callable(fail_task):
        return []

    reaped: list[str] = []
    for task in list_tasks(phase="executing", limit=200):
        task_id = str(getattr(task, "id", "") or "").strip()
        if not task_id:
            continue
        runtime = get_runtime_record(task_id)
        runtime_age_seconds = _seconds_since(getattr(runtime, "updated_at", None))
        leaf_progress_age_seconds = _seconds_since(getattr(task, "updated_at", None))
        has_leaf_progress = bool(getattr(runtime, "last_evidence_id", None)) or bool(
            getattr(runtime, "last_result_summary", None)
            or getattr(runtime, "last_error_summary", None)
        )
        timed_out_without_runtime_progress = (
            runtime_age_seconds is not None
            and runtime_age_seconds >= float(timeout_seconds)
        )
        timed_out_without_leaf_progress = (
            not has_leaf_progress
            and leaf_progress_age_seconds is not None
            and leaf_progress_age_seconds >= float(timeout_seconds)
        )
        if not (
            timed_out_without_runtime_progress or timed_out_without_leaf_progress
        ):
            continue
        timeout_label = f"{float(timeout_seconds):g}"
        reason = "without runtime progress"
        if timed_out_without_leaf_progress and not timed_out_without_runtime_progress:
            reason = "without leaf progress"
        logger.warning(
            "Reaping stale executing task %s after %ss %s",
            task_id,
            timeout_label,
            reason,
        )
        fail_task(
            task_id,
            error=f"Execution timed out after {timeout_label} seconds.",
            append_kernel_evidence=True,
        )
        reaped.append(task_id)
    return reaped


async def _automation_loop(
    *,
    task_name: str,
    interval_seconds: int,
    capability_ref: str,
    owner_agent_id: str,
    loop_state: _AutomationLoopState,
    payload_factory: Callable[[], dict[str, object]],
    should_run: Callable[[], object] | None,
    kernel_dispatcher: KernelDispatcher,
    capability_service: CapabilityService,
    logger: logging.Logger,
) -> None:
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            _reap_stale_kernel_tasks(kernel_dispatcher, logger=logger)
            allowed, reason = _resolve_automation_gate(should_run)
            if not allowed:
                loop_state.mark_blocked(reason)
                logger.debug(
                    "Automation cycle '%s' skipped before submit: %s",
                    task_name,
                    reason,
                )
                continue
            payload = loop_state.with_contract_payload(payload_factory())
            loop_state.mark_submitting(reason)
            result = await submit_kernel_automation_task(
                kernel_dispatcher,
                capability_service,
                capability_ref=capability_ref,
                title=f"Automation: {task_name}",
                owner_agent_id=owner_agent_id,
                payload=payload,
            )
            loop_state.record_result(result)
            logger.info(
                "Automation cycle '%s' completed: capability=%s result=%s",
                task_name,
                capability_ref,
                getattr(result, "phase", None) or getattr(result, "summary", None),
            )
        except asyncio.CancelledError:
            loop_state.mark_stopped()
            raise
        except Exception as exc:
            loop_state.record_failure(exc)
            logger.exception("Automation cycle '%s' failed", task_name)


def start_automation_tasks(
    *,
    kernel_dispatcher: KernelDispatcher,
    capability_service: CapabilityService,
    environment_service: Any | None = None,
    industry_service: Any | None = None,
    learning_service: Any | None = None,
    automation_loop_runtime_repository: object | None = None,
    logger: logging.Logger,
) -> AutomationTaskGroup:
    host_recovery_interval = automation_interval_seconds(
        "COPAW_HOST_RECOVERY_INTERVAL_SECONDS",
        120,
    )
    operating_cycle_interval = automation_interval_seconds(
        "COPAW_OPERATING_CYCLE_INTERVAL_SECONDS",
        180,
    )
    learning_daemon_interval = automation_interval_seconds(
        "COPAW_LEARNING_DAEMON_INTERVAL_SECONDS",
        900,
    )
    tasks: list[asyncio.Task[None]] = []
    for task_name, interval_seconds, capability_ref, owner_agent_id, payload_factory, should_run in (
        (
            "host-recovery",
            host_recovery_interval,
            "system:run_host_recovery",
            "copaw-main-brain",
            lambda: {
                "actor": "system:automation",
                "source": "automation:host_recovery",
                "limit": 25,
                "allow_cross_process_recovery": True,
            },
            (
                (lambda: _should_run_host_recovery(environment_service))
                if environment_service is not None
                else None
            ),
        ),
        (
            "operating-cycle",
            operating_cycle_interval,
            "system:run_operating_cycle",
            "copaw-main-brain",
            lambda: {
                "actor": "system:automation",
                "source": "automation:operating_cycle",
                "force": False,
            },
            (
                (lambda: _should_run_operating_cycle(industry_service))
                if industry_service is not None
                else None
            ),
        ),
        (
            "learning-strategy",
            learning_daemon_interval,
            "system:run_learning_strategy",
            "copaw-main-brain",
            lambda: {
                "actor": "copaw-main-brain",
                "auto_apply": True,
                "auto_rollback": False,
                "failure_threshold": 2,
                "confirm_threshold": 6,
                "max_proposals": 5,
            },
            (
                (lambda: _should_run_learning_strategy(learning_service))
                if learning_service is not None
                else None
            ),
        ),
    ):
        automation_task_id = _automation_task_id(
            task_name=task_name,
            capability_ref=capability_ref,
            owner_agent_id=owner_agent_id,
        )
        loop_state = None
        if automation_loop_runtime_repository is not None:
            get_loop = getattr(automation_loop_runtime_repository, "get_loop", None)
            if callable(get_loop):
                record = get_loop(automation_task_id)
                if isinstance(record, AutomationLoopRuntimeRecord):
                    loop_state = _AutomationLoopState.from_record(
                        record,
                        automation_loop_runtime_repository=automation_loop_runtime_repository,
                    )
        if loop_state is None:
            loop_state = _AutomationLoopState(
                task_name=task_name,
                capability_ref=capability_ref,
                owner_agent_id=owner_agent_id,
                interval_seconds=interval_seconds,
                automation_task_id=automation_task_id,
                automation_loop_runtime_repository=automation_loop_runtime_repository,
            )
        loop_state.persist()
        task = asyncio.create_task(
            _automation_loop(
                task_name=task_name,
                interval_seconds=interval_seconds,
                capability_ref=capability_ref,
                owner_agent_id=owner_agent_id,
                loop_state=loop_state,
                payload_factory=payload_factory,
                should_run=should_run,
                kernel_dispatcher=kernel_dispatcher,
                capability_service=capability_service,
                logger=logger,
            ),
            name=f"copaw-automation-{task_name}",
        )
        setattr(task, "copaw_automation_state", loop_state)
        tasks.append(task)
    return AutomationTaskGroup(tasks)


def _resolve_automation_gate(
    gate: Callable[[], object] | None,
) -> tuple[bool, str]:
    if gate is None:
        return (True, "ready")
    result = gate()
    if isinstance(result, tuple):
        allowed = bool(result[0])
        reason = str(result[1]).strip() if len(result) > 1 else ""
        return (allowed, reason or ("ready" if allowed else "preflight-blocked"))
    allowed = bool(result)
    return (allowed, "ready" if allowed else "preflight-blocked")

def _should_run_operating_cycle(industry_service: Any | None) -> tuple[bool, str]:
    if industry_service is None:
        return (True, "industry-service-unavailable")
    checker = getattr(industry_service, "should_run_operating_cycle", None)
    if callable(checker):
        try:
            result = checker()
        except Exception:
            logger.exception("Automation preflight 'operating-cycle' failed")
            return (True, "operating-cycle-preflight-error")
        return _resolve_automation_gate(lambda: result)
    list_instances = getattr(industry_service, "list_instances", None)
    if not callable(list_instances):
        return (True, "industry-service-without-preflight")
    try:
        instances = list_instances(status="active", limit=1)
    except Exception:
        logger.exception("Automation preflight 'operating-cycle' failed")
        return (True, "operating-cycle-preflight-error")
    return (bool(instances), "active-industry" if instances else "no-active-industry")


def _should_run_learning_strategy(learning_service: Any | None) -> tuple[bool, str]:
    if learning_service is None:
        return (True, "learning-service-unavailable")
    checker = getattr(learning_service, "should_run_strategy_cycle", None)
    if not callable(checker):
        return (True, "learning-service-without-preflight")
    try:
        result = checker(limit=50, failure_threshold=2)
    except Exception:
        logger.exception("Automation preflight 'learning-strategy' failed")
        return (True, "learning-preflight-error")
    return _resolve_automation_gate(lambda: result)


def _should_run_host_recovery(environment_service: Any | None) -> tuple[bool, str]:
    if environment_service is None:
        return (True, "environment-service-unavailable")
    checker = getattr(environment_service, "should_run_host_recovery", None)
    if not callable(checker):
        return (True, "environment-service-without-preflight")
    try:
        result = checker(limit=25, allow_cross_process_recovery=True)
    except Exception:
        logger.exception("Automation preflight 'host-recovery' failed")
        return (True, "host-recovery-preflight-error")
    return _resolve_automation_gate(lambda: result)


async def stop_automation_tasks(tasks: Iterable[asyncio.Task[Any]]) -> None:
    task_list = [task for task in tasks if task is not None]
    for task in task_list:
        task.cancel()
    if not task_list:
        return
    retried_after_cancel = False
    while True:
        try:
            await asyncio.gather(*task_list, return_exceptions=True)
            _mark_automation_tasks_stopped(task_list)
            return
        except asyncio.CancelledError:
            cleared = _consume_current_task_cancellation()
            if retried_after_cancel or cleared <= 0:
                raise
            retried_after_cancel = True
            logger.debug(
                "stop_automation_tasks consumed %s shutdown cancellation(s) while waiting for automation loops to stop",
                cleared,
            )


class RuntimeRestartCoordinator:
    def __init__(
        self,
        *,
        app: FastAPI,
        agent_runtime_app: FastAPI,
        bootstrap: RuntimeBootstrap,
        runtime_host: object,
        logger: logging.Logger,
    ) -> None:
        self._app = app
        self._agent_runtime_app = agent_runtime_app
        self._bootstrap = bootstrap
        self._runtime_host = runtime_host
        self._logger = logger
        self._restart_task: asyncio.Task[None] | None = None

    async def restart_services(self) -> None:
        restart_requester_task = asyncio.current_task()

        async def _run_then_clear() -> None:
            try:
                await self._do_restart_services(
                    restart_requester_task=restart_requester_task,
                )
            finally:
                self._restart_task = None

        if self._restart_task is not None and not self._restart_task.done():
            self._logger.info(
                "_restart_services: waiting for in-progress restart to finish",
            )
            await asyncio.shield(self._restart_task)
            return
        if self._restart_task is not None and self._restart_task.done():
            self._restart_task = None
        self._logger.info("_restart_services: starting restart")
        self._restart_task = asyncio.create_task(
            _run_then_clear(),
            name="copaw-runtime-restart",
        )
        await asyncio.shield(self._restart_task)

    async def _do_restart_services(
        self,
        *,
        restart_requester_task: asyncio.Task[Any] | None,
    ) -> None:
        try:
            config = load_config(get_config_path())
        except Exception:
            self._logger.exception("restart_services: load_config failed")
            return

        local_tasks = getattr(self._agent_runtime_app.state, "_local_tasks", None)
        if local_tasks:
            to_cancel = [
                task
                for task in list(local_tasks.values())
                if task is not restart_requester_task and not task.done()
            ]
            for task in to_cancel:
                task.cancel()
            if to_cancel:
                self._logger.info(
                    "restart: cancelled %s in-flight task(s), not waiting",
                    len(to_cancel),
                )

        try:
            await stop_runtime_manager_stack(
                runtime_manager_stack_from_app_state(self._app.state),
                logger=self._logger,
                error_mode="exception",
                context="restart_services",
            )
        except Exception:
            self._logger.exception("restart_services: old stack stop failed")

        try:
            new_mcp_manager = await initialize_mcp_manager(
                config=config,
                logger=self._logger,
                strict=True,
            )
        except Exception:
            self._logger.exception("restart_services: mcp init_from_config failed")
            return

        schedule_repository = getattr(self._app.state, "schedule_repository", None)
        if schedule_repository is None:
            self._logger.error("restart_services: schedule_repository is missing")
            return

        try:
            new_manager_stack = await start_runtime_manager_stack(
                config=config,
                kernel_dispatcher=self._bootstrap.kernel_dispatcher,
                capability_service=self._bootstrap.capability_service,
                governance_service=self._bootstrap.governance_service,
                schedule_repository=schedule_repository,
                mcp_manager=new_mcp_manager,
                memory_sleep_service=self._bootstrap.memory_sleep_service,
                research_session_service=self._bootstrap.research_session_service,
                logger=self._logger,
                strict_mcp_watcher=True,
            )
        except Exception:
            self._logger.exception("restart_services: runtime manager rebuild failed")
            return

        self._bootstrap.industry_service.set_schedule_runtime(
            schedule_writer=new_manager_stack.job_repository,
            cron_manager=new_manager_stack.cron_manager,
        )
        self._bootstrap.workflow_template_service.set_schedule_runtime(
            schedule_writer=new_manager_stack.job_repository,
            cron_manager=new_manager_stack.cron_manager,
        )
        if hasattr(config, "mcp"):
            self._bootstrap.capability_service.set_mcp_manager(new_mcp_manager)
            self._bootstrap.turn_executor.set_mcp_manager(new_mcp_manager)
        else:
            self._bootstrap.capability_service.set_mcp_manager(None)
            self._bootstrap.turn_executor.set_mcp_manager(None)

        resolve_exception_absorption_service = getattr(
            self._bootstrap.actor_supervisor,
            "exception_absorption_service",
            None,
        )
        startup_recovery_summary = run_startup_recovery(
            environment_service=getattr(self._app.state, "environment_service", None),
            actor_mailbox_service=getattr(self._app.state, "actor_mailbox_service", None),
            decision_request_repository=getattr(
                self._app.state,
                "decision_request_repository",
                None,
            ),
            kernel_dispatcher=self._bootstrap.kernel_dispatcher,
            kernel_task_store=getattr(self._app.state, "kernel_task_store", None),
            schedule_repository=getattr(self._app.state, "schedule_repository", None),
            runtime_repository=getattr(self._app.state, "agent_runtime_repository", None),
            exception_absorption_service=(
                resolve_exception_absorption_service()
                if callable(resolve_exception_absorption_service)
                else None
            ),
            human_assist_task_service=getattr(self._app.state, "human_assist_task_service", None),
            backlog_item_repository=getattr(self._app.state, "backlog_item_repository", None),
            assignment_repository=getattr(self._app.state, "assignment_repository", None),
            goal_repository=getattr(self._app.state, "goal_repository", None),
            goal_override_repository=getattr(self._app.state, "goal_override_repository", None),
            task_repository=getattr(self._app.state, "task_repository", None),
            task_runtime_repository=getattr(self._app.state, "task_runtime_repository", None),
            runtime_event_bus=getattr(self._app.state, "runtime_event_bus", None),
            reason="restart",
        )
        attach_runtime_state(
            self._app,
            runtime_host=self._runtime_host,
            bootstrap=self._bootstrap,
            manager_stack=new_manager_stack,
            startup_recovery_summary=startup_recovery_summary,
            automation_tasks=list(getattr(self._app.state, "automation_tasks", []) or []),
        )
        self._logger.info("Daemon restart (in-process) completed: managers rebuilt")
