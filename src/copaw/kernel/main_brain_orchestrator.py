# -*- coding: utf-8 -*-
"""Formal main-brain orchestration entry for durable execution turns."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from agentscope.message import Msg

from .main_brain_environment_coordinator import (
    MainBrainEnvironmentCoordinator,
)
from .main_brain_execution_planner import MainBrainExecutionPlanner
from .main_brain_intake import (
    MainBrainIntakeContract,
    materialize_requested_actions_main_brain_intake_contract,
    read_attached_main_brain_intake_contract,
    resolve_main_brain_intake_contract,
    resolve_request_main_brain_intake_contract,
)
from .main_brain_recovery_coordinator import MainBrainRecoveryCoordinator
from .main_brain_result_committer import MainBrainResultCommitter
from .query_execution import KernelQueryExecutionService
from .query_execution_writeback import (
    ChatWritebackDecisionModelTimeoutError,
    ChatWritebackDecisionModelUnavailableError,
)
from .runtime_coordination import AssignmentExecutorRuntimeCoordinator

logger = logging.getLogger(__name__)


def _should_propagate_main_brain_intake_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            ChatWritebackDecisionModelTimeoutError,
            ChatWritebackDecisionModelUnavailableError,
        ),
    )


def _safe_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _string_list(value: object, *, limit: int = 4) -> list[str]:
    items: list[str] = []
    for raw in list(value or [])[: max(1, limit)]:
        text = str(raw or "").strip()
        if text:
            items.append(text)
    return items


def _mapping_list(value: object, *, limit: int = 4) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in list(value or [])[: max(1, limit)]:
        payload = _safe_mapping(raw)
        if payload:
            items.append(payload)
    return items


def _unique_strings(value: object, *, limit: int = 8) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for raw in list(value or []):
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
        if len(values) >= max(1, limit):
            break
    return values


def _normalize_cognitive_surface(value: object) -> dict[str, Any] | None:
    payload = _safe_mapping(value)
    if not payload:
        return None
    synthesis = _safe_mapping(payload.get("synthesis"))
    if not synthesis:
        synthesis = payload
    latest_findings = _mapping_list(synthesis.get("latest_findings"))
    conflicts = _mapping_list(synthesis.get("conflicts"))
    holes = _mapping_list(synthesis.get("holes"))
    replan_reasons = _string_list(synthesis.get("replan_reasons"))
    recommended_actions = _mapping_list(synthesis.get("recommended_actions"))
    replan = _safe_mapping(payload.get("replan"))
    if not replan:
        activation = _safe_mapping(synthesis.get("activation"))
        strategy_change = _safe_mapping(activation.get("strategy_change"))
        raw_decision = _safe_mapping(synthesis.get("replan_decision"))
        trigger_families = _unique_strings(
            raw_decision.get("trigger_families") or strategy_change.get("trigger_families"),
        )
        trigger_rule_ids = _unique_strings(
            raw_decision.get("trigger_rule_ids") or strategy_change.get("trigger_rule_ids"),
        )
        affected_lane_ids = _unique_strings(
            raw_decision.get("affected_lane_ids") or strategy_change.get("affected_lane_ids"),
        )
        affected_uncertainty_ids = _unique_strings(
            raw_decision.get("affected_uncertainty_ids")
            or strategy_change.get("affected_uncertainty_ids"),
        )
        has_synthesis_pressure = bool(
            synthesis.get("needs_replan")
            or conflicts
            or holes
            or replan_reasons
            or recommended_actions
        )
        decision_kind = (
            str(
                raw_decision.get("decision_kind")
                or strategy_change.get("decision_kind")
                or ("follow_up_backlog" if (raw_decision or strategy_change or has_synthesis_pressure) else "clear")
            )
            .strip()
        )
        replan = {
            "status": (
                str(raw_decision.get("status") or ("needs-replan" if decision_kind != "clear" else "clear"))
                .strip()
            ),
            "decision_kind": decision_kind or "clear",
            "summary": str(raw_decision.get("summary") or "").strip() or None,
            "trigger_families": trigger_families,
            "trigger_rule_ids": trigger_rule_ids,
            "affected_lane_ids": affected_lane_ids,
            "affected_uncertainty_ids": affected_uncertainty_ids,
            "trigger_context": {
                "trigger_families": trigger_families,
                "trigger_rule_ids": trigger_rule_ids,
                "affected_lane_ids": affected_lane_ids,
                "affected_uncertainty_ids": affected_uncertainty_ids,
            },
        }
    decision_kind = str(replan.get("decision_kind") or payload.get("decision_kind") or "clear").strip() or "clear"
    needs_replan = bool(
        payload.get("needs_replan")
        or synthesis.get("needs_replan")
        or _safe_mapping(replan).get("status") == "needs-replan"
        or decision_kind != "clear"
        or conflicts
        or holes
        or replan_reasons
    )
    normalized_synthesis = {
        "latest_findings": latest_findings,
        "conflicts": conflicts,
        "holes": holes,
        "recommended_actions": recommended_actions,
        "replan_reasons": replan_reasons,
        "needs_replan": needs_replan,
    }
    if not any(normalized_synthesis.values()):
        return None
    return {
        "synthesis": normalized_synthesis,
        "latest_findings": latest_findings,
        "conflicts": conflicts,
        "holes": holes,
        "replan_reasons": replan_reasons,
        "recommended_actions": recommended_actions,
        "replan": replan,
        "decision_kind": decision_kind,
        "needs_replan": needs_replan,
        "has_unresolved_conflicts": bool(conflicts),
        "has_unresolved_holes": bool(holes),
    }


def read_attached_main_brain_cognitive_surface(
    *,
    request: Any,
) -> dict[str, Any] | None:
    direct = _normalize_cognitive_surface(
        getattr(request, "_copaw_main_brain_cognitive_surface", None),
    )
    if direct is not None:
        return direct
    runtime_context = _safe_mapping(
        getattr(request, "_copaw_main_brain_runtime_context", None),
    )
    return _normalize_cognitive_surface(runtime_context.get("cognitive"))


def build_main_brain_cognitive_surface(
    *,
    detail: object | None = None,
    request: Any | None = None,
) -> dict[str, Any] | None:
    if detail is not None:
        detail_payload = _safe_mapping(detail)
        current_cycle = _safe_mapping(getattr(detail, "current_cycle", None))
        if not current_cycle:
            current_cycle = _safe_mapping(detail_payload.get("current_cycle"))
        from_current_surface = _normalize_cognitive_surface(
            current_cycle.get("main_brain_cognitive_surface"),
        )
        if from_current_surface is not None:
            return from_current_surface
        from_cycle = _normalize_cognitive_surface(current_cycle.get("synthesis"))
        if from_cycle is not None:
            planning = _safe_mapping(getattr(detail, "main_brain_planning", None))
            if not planning:
                planning = _safe_mapping(detail_payload.get("main_brain_planning"))
            replan = _safe_mapping(planning.get("replan"))
            if replan:
                return {
                    **from_cycle,
                    "replan": replan,
                    "decision_kind": str(replan.get("decision_kind") or from_cycle.get("decision_kind") or "clear").strip() or "clear",
                    "needs_replan": bool(
                        from_cycle.get("needs_replan")
                        or str(replan.get("status") or "").strip() == "needs-replan"
                        or str(replan.get("decision_kind") or "").strip() not in {"", "clear"}
                    ),
                }
            return from_cycle
    if request is not None:
        return read_attached_main_brain_cognitive_surface(request=request)
    return None


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
        executor_runtime_coordinator: AssignmentExecutorRuntimeCoordinator | None = None,
    ) -> None:
        self._query_execution_service = query_execution_service
        self._session_backend = session_backend
        self._environment_service = environment_service
        self._intake_contract_resolver = intake_contract_resolver or resolve_request_main_brain_intake_contract
        self._execution_planner = execution_planner or MainBrainExecutionPlanner()
        self._environment_coordinator = environment_coordinator or MainBrainEnvironmentCoordinator(
            environment_service=environment_service,
        )
        self._recovery_coordinator = recovery_coordinator or MainBrainRecoveryCoordinator()
        self._result_committer = result_committer or MainBrainResultCommitter()
        self._executor_runtime_coordinator = executor_runtime_coordinator

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
        self._intake_contract_resolver = resolver or resolve_request_main_brain_intake_contract

    def set_executor_runtime_coordinator(
        self,
        coordinator: AssignmentExecutorRuntimeCoordinator | None,
    ) -> None:
        self._executor_runtime_coordinator = coordinator

    def resolve_cognitive_surface(
        self,
        *,
        request: Any,
    ) -> dict[str, Any] | None:
        service = getattr(self._query_execution_service, "_industry_service", None)
        detail = None
        instance_id = str(getattr(request, "industry_instance_id", "") or "").strip()
        getter = getattr(service, "get_instance_detail", None)
        if instance_id and callable(getter):
            try:
                detail = getter(instance_id)
            except Exception:
                logger.debug("Failed to load industry detail for cognitive surface", exc_info=True)
        return build_main_brain_cognitive_surface(detail=detail, request=request)

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
        timings: dict[str, float] = {}
        started_at = perf_counter()

        def _timed(name: str, factory):
            stage_started_at = perf_counter()
            result = factory()
            timings[name] = perf_counter() - stage_started_at
            return result

        stage_started_at = perf_counter()
        intake_contract = await self._resolve_intake_contract(
            request=request,
            msgs=msgs,
        )
        timings["resolve_intake_contract"] = perf_counter() - stage_started_at
        execution_plan = _timed(
            "execution_planner.plan",
            lambda: self._execution_planner.plan(
                request=request,
                intake_contract=intake_contract,
            ),
        )
        environment_binding = _timed(
            "environment_coordinator.coordinate",
            lambda: self._environment_coordinator.coordinate(
                request=request,
                execution_plan=execution_plan,
            ),
        )
        recovery_state = _timed(
            "recovery_coordinator.coordinate",
            lambda: self._recovery_coordinator.coordinate(
                request=request,
                environment_binding=environment_binding,
            ),
        )
        _timed(
            "commit_request_runtime_context",
            lambda: self._result_committer.commit_request_runtime_context(
                request=request,
                intake_contract=intake_contract,
                execution_plan=execution_plan,
                environment_binding=environment_binding,
                recovery_state=recovery_state,
                kernel_task_id=kernel_task_id,
            ),
        )
        runtime_coordination = _timed(
            "executor_runtime.coordinate",
            lambda: self._coordinate_executor_runtime(
                request=request,
                msgs=msgs,
                intake_contract=intake_contract,
            ),
        )
        if runtime_coordination:
            runtime_context = _safe_mapping(
                getattr(request, "_copaw_main_brain_runtime_context", None),
            )
            runtime_context.update(runtime_coordination)
            try:
                setattr(request, "_copaw_main_brain_runtime_context", runtime_context)
            except Exception:
                logger.debug("Failed to attach executor runtime coordination")
            try:
                setattr(request, "_copaw_executor_runtime_coordination", runtime_coordination)
            except Exception:
                logger.debug("Failed to attach executor runtime coordination payload")
        cognitive_surface = _timed(
            "resolve_cognitive_surface",
            lambda: self.resolve_cognitive_surface(request=request),
        )
        if cognitive_surface is not None:
            runtime_context = _safe_mapping(
                getattr(request, "_copaw_main_brain_runtime_context", None),
            )
            runtime_context["cognitive"] = cognitive_surface
            try:
                setattr(request, "_copaw_main_brain_runtime_context", runtime_context)
            except Exception:
                logger.debug("Failed to attach main-brain cognitive runtime context")
            try:
                setattr(request, "_copaw_main_brain_cognitive_surface", cognitive_surface)
            except Exception:
                logger.debug("Failed to attach main-brain cognitive surface")
        timings["total"] = perf_counter() - started_at
        logger.info(
            "Main-brain ingest timings: task=%s session=%s instance=%s %s",
            kernel_task_id or "<none>",
            getattr(request, "session_id", None),
            getattr(request, "industry_instance_id", None),
            " ".join(f"{key}={value:.2f}s" for key, value in timings.items()),
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
        request: Any,
        msgs: list[Any],
    ) -> MainBrainIntakeContract | None:
        timings: dict[str, float] = {}
        started_at = perf_counter()
        branch = "none"

        attached = read_attached_main_brain_intake_contract(request=request)
        timings["attached_lookup"] = perf_counter() - started_at
        if attached is not None:
            branch = "attached"
            timings["total"] = perf_counter() - started_at
            logger.info(
                "Main-brain intake resolution timings: session=%s branch=%s %s",
                getattr(request, "session_id", None),
                branch,
                " ".join(f"{key}={value:.2f}s" for key, value in timings.items()),
            )
            return attached
        resolver = self._intake_contract_resolver
        if resolver is None:
            branch = "resolver-missing"
            timings["total"] = perf_counter() - started_at
            logger.info(
                "Main-brain intake resolution timings: session=%s branch=%s %s",
                getattr(request, "session_id", None),
                branch,
                " ".join(f"{key}={value:.2f}s" for key, value in timings.items()),
            )
            return None
        try:
            resolver_started_at = perf_counter()
            contract = await resolver(request=request, msgs=msgs)
            timings["resolver.request"] = perf_counter() - resolver_started_at
            branch = "resolver.request"
        except TypeError:
            resolver_started_at = perf_counter()
            contract = await resolver(msgs=msgs)
            timings["resolver.msgs"] = perf_counter() - resolver_started_at
            branch = "resolver.msgs"
        except Exception as exc:
            if _should_propagate_main_brain_intake_error(exc):
                raise
            logger.debug("Main-brain intake resolution failed during orchestration", exc_info=True)
            branch = "resolver.error"
            timings["total"] = perf_counter() - started_at
            logger.info(
                "Main-brain intake resolution timings: session=%s branch=%s %s",
                getattr(request, "session_id", None),
                branch,
                " ".join(f"{key}={value:.2f}s" for key, value in timings.items()),
            )
            return None
        if contract is None:
            materialize_started_at = perf_counter()
            contract = materialize_requested_actions_main_brain_intake_contract(
                request=request,
                msgs=msgs,
            )
            timings["materialize_requested_actions"] = (
                perf_counter() - materialize_started_at
            )
            if contract is not None:
                branch = "materialize_requested_actions"
        if contract is None:
            try:
                fallback_started_at = perf_counter()
                contract = await resolve_main_brain_intake_contract(msgs=msgs)
                timings["model_fallback"] = perf_counter() - fallback_started_at
                branch = "model_fallback"
            except Exception as exc:
                if _should_propagate_main_brain_intake_error(exc):
                    raise
                logger.debug("Main-brain model intake fallback failed during orchestration", exc_info=True)
                branch = "model_fallback.error"
                timings["total"] = perf_counter() - started_at
                logger.info(
                    "Main-brain intake resolution timings: session=%s branch=%s %s",
                    getattr(request, "session_id", None),
                    branch,
                    " ".join(f"{key}={value:.2f}s" for key, value in timings.items()),
                )
                return None
        if contract is not None:
            try:
                attach_started_at = perf_counter()
                setattr(request, "_copaw_main_brain_intake_contract", contract)
                timings["attach_to_request"] = perf_counter() - attach_started_at
            except Exception:
                logger.debug("Failed to attach main-brain intake contract to request")
                timings["attach_to_request"] = 0.0
                branch = f"{branch}.attach_failed"
        timings["total"] = perf_counter() - started_at
        logger.info(
            "Main-brain intake resolution timings: session=%s branch=%s %s",
            getattr(request, "session_id", None),
            branch,
            " ".join(f"{key}={value:.2f}s" for key, value in timings.items()),
        )
        return contract

    def _coordinate_executor_runtime(
        self,
        *,
        request: Any,
        msgs: list[Any],
        intake_contract: MainBrainIntakeContract | None,
    ) -> dict[str, Any] | None:
        coordinator = self._executor_runtime_coordinator
        if coordinator is None:
            return None
        try:
            return coordinator.coordinate_assignment_runtime(
                request=request,
                msgs=msgs,
                intake_contract=intake_contract,
            )
        except Exception:
            logger.debug("Executor runtime coordination failed during orchestration", exc_info=True)
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

__all__ = [
    "MainBrainExecutionEnvelope",
    "MainBrainOrchestrator",
    "build_main_brain_cognitive_surface",
    "read_attached_main_brain_cognitive_surface",
]
