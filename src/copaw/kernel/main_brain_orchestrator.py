# -*- coding: utf-8 -*-
"""Formal main-brain orchestration entry for durable execution turns."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agentscope.message import Msg

from .main_brain_environment_coordinator import (
    MainBrainEnvironmentCoordinator,
)
from .main_brain_execution_planner import MainBrainExecutionPlanner
from .main_brain_intake import (
    MainBrainIntakeContract,
    resolve_main_brain_intake_contract,
)
from .main_brain_recovery_coordinator import MainBrainRecoveryCoordinator
from .main_brain_result_committer import MainBrainResultCommitter
from .query_execution import KernelQueryExecutionService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MainBrainExecutionEnvelope:
    msgs: list[Any]
    request: Any
    kernel_task_id: str | None
    transient_input_message_ids: set[str] | None
    intake_contract: MainBrainIntakeContract | None
    intent_kind: str | None = None
    execution_mode: str | None = None
    environment_ref: str | None = None
    recovery_mode: str | None = None

    @property
    def execution_kwargs(self) -> dict[str, Any]:
        return {
            "msgs": self.msgs,
            "request": self.request,
            "kernel_task_id": self.kernel_task_id,
            "transient_input_message_ids": self.transient_input_message_ids,
        }


class MainBrainOrchestrator:
    """Own the formal main-brain execution/orchestration path."""

    def __init__(
        self,
        *,
        query_execution_service: KernelQueryExecutionService | Any,
        session_backend: Any | None = None,
        environment_service: Any | None = None,
        intake_contract_resolver: Callable[..., Awaitable[MainBrainIntakeContract | None]] | None = None,
        execution_planner: MainBrainExecutionPlanner | None = None,
        environment_coordinator: MainBrainEnvironmentCoordinator | None = None,
        recovery_coordinator: MainBrainRecoveryCoordinator | None = None,
        result_committer: MainBrainResultCommitter | None = None,
    ) -> None:
        self._query_execution_service = query_execution_service
        self._session_backend = session_backend
        self._environment_service = environment_service
        self._intake_contract_resolver = intake_contract_resolver or resolve_main_brain_intake_contract
        self._execution_planner = execution_planner or MainBrainExecutionPlanner()
        self._environment_coordinator = environment_coordinator or MainBrainEnvironmentCoordinator(
            environment_service=environment_service,
        )
        self._recovery_coordinator = recovery_coordinator or MainBrainRecoveryCoordinator()
        self._result_committer = result_committer or MainBrainResultCommitter()

    def set_query_execution_service(
        self,
        query_execution_service: KernelQueryExecutionService | Any,
    ) -> None:
        self._query_execution_service = query_execution_service

    def set_session_backend(self, session_backend: Any) -> None:
        self._session_backend = session_backend

    def set_environment_service(self, environment_service: Any | None) -> None:
        self._environment_service = environment_service
        coordinator = self._environment_coordinator
        setter = getattr(coordinator, "set_environment_service", None)
        if callable(setter):
            setter(environment_service)

    def set_intake_contract_resolver(
        self,
        resolver: Callable[..., Awaitable[MainBrainIntakeContract | None]] | None,
    ) -> None:
        self._intake_contract_resolver = resolver or resolve_main_brain_intake_contract

    async def execute_stream(
        self,
        *,
        msgs: list[Any],
        request: Any,
        kernel_task_id: str | None = None,
        transient_input_message_ids: set[str] | None = None,
    ) -> AsyncIterator[tuple[Msg, bool]]:
        envelope = await self.ingest_operator_turn(
            msgs=msgs,
            request=request,
            kernel_task_id=kernel_task_id,
            transient_input_message_ids=transient_input_message_ids,
        )
        async for msg, last in self._execute_envelope_stream(envelope):
            yield msg, last

    async def ingest_operator_turn(
        self,
        *,
        msgs: list[Any],
        request: Any,
        kernel_task_id: str | None = None,
        transient_input_message_ids: set[str] | None = None,
    ) -> MainBrainExecutionEnvelope:
        intake_contract = await self._resolve_intake_contract(msgs=msgs)
        execution_plan = self._execution_planner.plan(
            request=request,
            intake_contract=intake_contract,
        )
        environment_binding = self._environment_coordinator.coordinate(
            request=request,
            execution_plan=execution_plan,
        )
        recovery_state = self._recovery_coordinator.coordinate(
            request=request,
            environment_binding=environment_binding,
        )
        self._result_committer.commit_request_runtime_context(
            request=request,
            intake_contract=intake_contract,
            execution_plan=execution_plan,
            environment_binding=environment_binding,
            recovery_state=recovery_state,
            kernel_task_id=kernel_task_id,
        )
        return MainBrainExecutionEnvelope(
            msgs=msgs,
            request=request,
            kernel_task_id=kernel_task_id,
            transient_input_message_ids=transient_input_message_ids,
            intake_contract=intake_contract,
            intent_kind=execution_plan.intent_kind,
            execution_mode=execution_plan.execution_mode,
            environment_ref=environment_binding.environment_ref,
            recovery_mode=recovery_state.recovery_mode,
        )

    async def _build_execution_envelope(
        self,
        *,
        msgs: list[Any],
        request: Any,
        kernel_task_id: str | None,
        transient_input_message_ids: set[str] | None,
    ) -> MainBrainExecutionEnvelope:
        return await self.ingest_operator_turn(
            msgs=msgs,
            request=request,
            kernel_task_id=kernel_task_id,
            transient_input_message_ids=transient_input_message_ids,
        )

    async def _resolve_intake_contract(
        self,
        *,
        msgs: list[Any],
    ) -> MainBrainIntakeContract | None:
        resolver = self._intake_contract_resolver
        if resolver is None:
            return None
        try:
            return await resolver(msgs=msgs)
        except Exception:
            logger.debug("Main-brain intake resolution failed during orchestration", exc_info=True)
            return None

    async def _execute_envelope_stream(
        self,
        envelope: MainBrainExecutionEnvelope,
    ) -> AsyncIterator[tuple[Msg, bool]]:
        service = self._query_execution_service
        if service is None:
            raise RuntimeError("MainBrainOrchestrator requires a query execution service")
        async for msg, last in service.execute_stream(**envelope.execution_kwargs):
            yield msg, last

__all__ = ["MainBrainExecutionEnvelope", "MainBrainOrchestrator"]
