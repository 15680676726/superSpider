# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
import os
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Iterable

from fastapi import FastAPI

from ..capabilities import CapabilityService
from ..config import load_config
from ..config.utils import get_config_path
from ..kernel import KernelDispatcher, KernelTask
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


async def _automation_loop(
    *,
    task_name: str,
    interval_seconds: int,
    capability_ref: str,
    owner_agent_id: str,
    payload_factory: Callable[[], dict[str, object]],
    should_run: Callable[[], object] | None,
    kernel_dispatcher: KernelDispatcher,
    capability_service: CapabilityService,
    logger: logging.Logger,
) -> None:
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            allowed, reason = _resolve_automation_gate(should_run)
            if not allowed:
                logger.debug(
                    "Automation cycle '%s' skipped before submit: %s",
                    task_name,
                    reason,
                )
                continue
            payload = payload_factory()
            result = await submit_kernel_automation_task(
                kernel_dispatcher,
                capability_service,
                capability_ref=capability_ref,
                title=f"Automation: {task_name}",
                owner_agent_id=owner_agent_id,
                payload=payload,
            )
            logger.info(
                "Automation cycle '%s' completed: capability=%s result=%s",
                task_name,
                capability_ref,
                getattr(result, "phase", None) or getattr(result, "summary", None),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automation cycle '%s' failed", task_name)


def start_automation_tasks(
    *,
    kernel_dispatcher: KernelDispatcher,
    capability_service: CapabilityService,
    industry_service: Any | None = None,
    learning_service: Any | None = None,
    logger: logging.Logger,
) -> list[asyncio.Task[None]]:
    operating_cycle_interval = automation_interval_seconds(
        "COPAW_OPERATING_CYCLE_INTERVAL_SECONDS",
        180,
    )
    learning_daemon_interval = automation_interval_seconds(
        "COPAW_LEARNING_DAEMON_INTERVAL_SECONDS",
        900,
    )
    return [
        asyncio.create_task(
            _automation_loop(
                task_name="operating-cycle",
                interval_seconds=operating_cycle_interval,
                capability_ref="system:run_operating_cycle",
                owner_agent_id="copaw-main-brain",
                payload_factory=lambda: {
                    "actor": "system:automation",
                    "source": "automation:operating_cycle",
                    "force": False,
                },
                should_run=(
                    (lambda: _should_run_operating_cycle(industry_service))
                    if industry_service is not None
                    else None
                ),
                kernel_dispatcher=kernel_dispatcher,
                capability_service=capability_service,
                logger=logger,
            ),
            name="copaw-automation-operating-cycle",
        ),
        asyncio.create_task(
            _automation_loop(
                task_name="learning-strategy",
                interval_seconds=learning_daemon_interval,
                capability_ref="system:run_learning_strategy",
                owner_agent_id="copaw-main-brain",
                payload_factory=lambda: {
                    "actor": "copaw-main-brain",
                    "auto_apply": True,
                    "auto_rollback": False,
                    "failure_threshold": 2,
                    "confirm_threshold": 6,
                    "max_proposals": 5,
                },
                should_run=(
                    (lambda: _should_run_learning_strategy(learning_service))
                    if learning_service is not None
                    else None
                ),
                kernel_dispatcher=kernel_dispatcher,
                capability_service=capability_service,
                logger=logger,
            ),
            name="copaw-automation-learning-strategy",
        ),
    ]


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
