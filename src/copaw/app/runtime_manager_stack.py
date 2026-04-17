# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Literal

from ..capabilities import CapabilityService
from ..config import ConfigWatcher, load_config, update_last_dispatch
from ..kernel import GovernanceService, KernelDispatcher
from ..state.repositories import SqliteScheduleRepository
from .channels import ChannelManager
from .channels.utils import make_process_from_kernel
from .crons.manager import CronManager
from .crons.repo import StateBackedJobRepository
from .mcp import MCPClientManager, MCPConfigWatcher
from .runtime_bootstrap_models import RuntimeManagerStack


def _log_stop_error(
    logger: logging.Logger,
    *,
    error_mode: Literal["ignore", "debug", "exception"],
    context: str,
    target: str,
) -> None:
    if error_mode == "ignore":
        return
    if error_mode == "debug":
        logger.debug("%s: %s failed", context, target, exc_info=True)
        return
    logger.exception("%s: %s failed", context, target)


async def start_runtime_manager_stack(
    *,
    config: Any,
    kernel_dispatcher: KernelDispatcher,
    capability_service: CapabilityService,
    governance_service: GovernanceService,
    schedule_repository: SqliteScheduleRepository,
    mcp_manager: MCPClientManager,
    memory_sleep_service: object | None,
    research_session_service: object | None,
    logger: logging.Logger,
    strict_mcp_watcher: bool,
) -> RuntimeManagerStack:
    stack = RuntimeManagerStack(mcp_manager=mcp_manager)
    stack.channel_manager = ChannelManager.from_config(
        process=make_process_from_kernel(kernel_dispatcher),
        config=config,
        on_last_dispatch=update_last_dispatch,
    )
    capability_service.set_channel_manager(stack.channel_manager)
    try:
        await stack.channel_manager.start_all()
        stack.job_repository = StateBackedJobRepository(
            schedule_repository=schedule_repository,
        )
        stack.cron_manager = CronManager(
            repo=stack.job_repository,
            timezone="UTC",
            kernel_dispatcher=kernel_dispatcher,
            memory_sleep_service=memory_sleep_service,
            research_session_service=research_session_service,
        )
        await stack.cron_manager.start()
        capability_service.set_cron_manager(stack.cron_manager)
        governance_service.set_runtime_managers(
            cron_manager=stack.cron_manager,
            channel_manager=stack.channel_manager,
        )
        await governance_service.reconcile_runtime_state()
        stack.config_watcher = ConfigWatcher(
            channel_manager=stack.channel_manager,
            cron_manager=stack.cron_manager,
        )
        await stack.config_watcher.start()
    except Exception:
        await stop_runtime_manager_stack(
            stack,
            logger=logger,
            error_mode="debug",
            context="runtime manager rollback",
        )
        raise

    if hasattr(config, "mcp"):
        try:
            from ..config.utils import get_config_path

            stack.mcp_watcher = MCPConfigWatcher(
                mcp_manager=mcp_manager,
                config_loader=load_config,
                config_path=get_config_path(),
            )
            await stack.mcp_watcher.start()
            logger.debug("MCP config watcher started")
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            if strict_mcp_watcher:
                await stop_runtime_manager_stack(
                    stack,
                    logger=logger,
                    error_mode="debug",
                    context="runtime manager rollback",
                )
                raise
            logger.exception("Failed to start MCP watcher")
            stack.mcp_watcher = None

    return stack


def runtime_manager_stack_from_app_state(app_state: Any) -> RuntimeManagerStack:
    return RuntimeManagerStack(
        mcp_manager=getattr(app_state, "mcp_manager", None),
        channel_manager=getattr(app_state, "channel_manager", None),
        cron_manager=getattr(app_state, "cron_manager", None),
        job_repository=getattr(app_state, "job_repository", None),
        config_watcher=getattr(app_state, "config_watcher", None),
        mcp_watcher=getattr(app_state, "mcp_watcher", None),
        browser_runtime_service=getattr(app_state, "browser_runtime_service", None),
    )


async def stop_runtime_manager_stack(
    stack: RuntimeManagerStack,
    *,
    logger: logging.Logger,
    error_mode: Literal["ignore", "debug", "exception"],
    context: str,
) -> None:
    if stack.config_watcher is not None:
        try:
            await stack.config_watcher.stop()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _log_stop_error(
                logger,
                error_mode=error_mode,
                context=context,
                target="config_watcher.stop",
            )
    if stack.mcp_watcher is not None:
        try:
            await stack.mcp_watcher.stop()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _log_stop_error(
                logger,
                error_mode=error_mode,
                context=context,
                target="mcp_watcher.stop",
            )
    if stack.cron_manager is not None:
        try:
            await stack.cron_manager.stop()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _log_stop_error(
                logger,
                error_mode=error_mode,
                context=context,
                target="cron_manager.stop",
            )
    if stack.channel_manager is not None:
        try:
            await stack.channel_manager.stop_all()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _log_stop_error(
                logger,
                error_mode=error_mode,
                context=context,
                target="channel_manager.stop_all",
            )
    if stack.browser_runtime_service is not None:
        try:
            await stack.browser_runtime_service.shutdown()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _log_stop_error(
                logger,
                error_mode=error_mode,
                context=context,
                target="browser_runtime_service.shutdown",
            )
    if stack.mcp_manager is not None:
        try:
            await stack.mcp_manager.close_all()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _log_stop_error(
                logger,
                error_mode=error_mode,
                context=context,
                target="mcp_manager.close_all",
            )
