# -*- coding: utf-8 -*-
"""Runtime Center overview card builder."""
from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from ...config import get_heartbeat_config
from ...industry.models import IndustrySeatCapabilityLayers
from ...kernel.runtime_outcome import build_execution_diagnostics
from .overview_capability_governance import build_capability_governance_projection
from .overview_entry_builders import _RuntimeCenterOverviewEntryBuildersMixin
from .overview_helpers import build_runtime_surface
from .overview_main_brain import RuntimeCenterMainBrainAssembly
from .recovery_projection import project_latest_recovery_summary
from .execution_runtime_projection import (
    build_host_twin_summary,
    derive_host_twin_continuity_state,
    host_twin_summary_ready,
)
from .models import (
    RuntimeCenterAppStateView,
    RuntimeCenterSurfaceInfo,
    RuntimeCenterSurfaceResponse,
    RuntimeHumanCockpitAgent,
    RuntimeHumanCockpitApproval,
    RuntimeHumanCockpitCard,
    RuntimeHumanCockpitMainBrain,
    RuntimeHumanCockpitPayload,
    RuntimeHumanCockpitReportBlock,
    RuntimeHumanCockpitStageSummary,
    RuntimeHumanCockpitSummaryField,
    RuntimeHumanCockpitTraceEntry,
    RuntimeHumanCockpitTrendPoint,
    RuntimeMainBrainGovernancePayload,
    RuntimeMainBrainPlanningPayload,
    RuntimeMainBrainResponse,
    RuntimeQueryRuntimeEntropyPayload,
    RuntimeMainBrainSection,
    RuntimeOverviewCard,
    RuntimeOverviewEntry,
)

logger = logging.getLogger(__name__)

_MISSING = object()


class _RuntimeCenterOverviewCardsSupport(_RuntimeCenterOverviewEntryBuildersMixin):
    """Shared Runtime Center overview card construction helpers."""

    def __init__(self, *, item_limit: int = 5) -> None:
        self._item_limit = item_limit
        self._missing_sentinel = _MISSING
        self._main_brain_assembly = RuntimeCenterMainBrainAssembly(self)

    async def build_cards(self, app_state: RuntimeCenterAppStateView) -> list[RuntimeOverviewCard]:
        return [
            await self._build_tasks_card(app_state),
            await self._build_work_contexts_card(app_state),
            await self._build_routines_card(app_state),
            await self._build_industry_card(app_state),
            await self._build_agents_card(app_state),
            await self._build_predictions_card(app_state),
            await self._build_capabilities_card(app_state),
            await self._build_evidence_card(app_state),
            await self._build_governance_card(app_state),
            await self._build_decisions_card(app_state),
            await self._build_patches_card(app_state),
            await self._build_growth_card(app_state),
        ]

    def _available_card(
        self,
        *,
        key: str,
        title: str,
        source: str,
        count: int,
        summary: str,
        entries: list[RuntimeOverviewEntry],
        meta: Mapping[str, Any] | None = None,
    ) -> RuntimeOverviewCard:
        return RuntimeOverviewCard(
            key=key,
            title=title,
            source=source,
            status="state-service",
            count=count,
            summary=summary,
            entries=entries,
            meta=dict(meta or {}),
        )

    def _apply_automation_surface_status(
        self,
        *,
        surface: RuntimeCenterSurfaceInfo,
        automation: Mapping[str, Any] | None,
    ) -> RuntimeCenterSurfaceInfo:
        automation_status = self._string((automation or {}).get("status"))
        if automation_status != "degraded" or surface.status == "degraded":
            return surface
        return surface.model_copy(update={"status": "degraded"})

    def _unavailable_summary(self, title: str) -> str:
        return f"{title}视图暂未接入。"

    def _build_mapped_entries(
        self,
        items: list[Any],
        *sort_fields: str,
        builder,
    ) -> list[RuntimeOverviewEntry]:
        return [builder(item) for item in self._sorted(items, *sort_fields)]

    def _build_standard_card_meta(
        self,
        items: list[Any],
        total: int,
    ) -> dict[str, Any]:
        return {
            "by_status": self._counter_meta(items, "status"),
            "total": total,
            "visible_count": len(items),
            "truncated": total > len(items),
        }

    async def _build_tasks_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        return await self._state_card(
            app_state=app_state,
            key="tasks",
            title="任务",
            summary="统一状态库中的运行任务。",
            methods=("list_tasks", "get_tasks", "list_runtime_tasks"),
            mapper=self._map_task_entries,
        )

    async def _build_work_contexts_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        return await self._state_card(
            app_state=app_state,
            key="work-contexts",
            title="工作上下文",
            summary="正式连续工作单元，不再只靠线程 alias 猜测当前到底是哪件事。",
            methods=("list_work_contexts",),
            count_methods=("count_work_contexts",),
            mapper=self._map_work_context_entries,
        )

    async def _build_routines_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        routine_service = app_state.routine_service
        getter = getattr(routine_service, "get_runtime_center_overview", None)
        if not callable(getter):
            return self._unavailable_card("routines", "例行", "Routine 视图暂未接入。")
        try:
            payload = await self._maybe_await(getter(limit=self._item_limit))
        except Exception:
            logger.debug("runtime_center routine overview failed", exc_info=True)
            return self._unavailable_card("routines", "例行", "Routine 视图暂未接入。")
        overview = self._mapping(payload) or {}
        entries = self._map_routine_entries(
            self._normalize_list(overview.get("entries")),
        )
        total = self._int(overview.get("total"), len(entries))
        degraded = self._int(overview.get("degraded"), 0)
        last_fallback = self._string(overview.get("last_fallback"))
        routine_failure_source = None
        routine_remediation_summary = None
        if degraded > 0:
            if last_fallback and "memory" in last_fallback.lower():
                routine_failure_source = "sidecar-memory"
                routine_remediation_summary = (
                    "Routine execution is continuing on canonical state only because the "
                    "memory sidecar fallback is active."
                )
            else:
                routine_failure_source = "degraded-runtime"
                routine_remediation_summary = (
                    "One or more routines are running in degraded mode and require runtime review."
                )
        routine_diagnostics = build_execution_diagnostics(
            failure_source=routine_failure_source,
            remediation_summary=routine_remediation_summary,
        )
        card_summary = self._summarize_routines_card(overview, total)
        if routine_diagnostics["remediation_summary"]:
            card_summary = f"{routine_diagnostics['remediation_summary']} {card_summary}"
        return RuntimeOverviewCard(
            key="routines",
            title="例行",
            source="routine_service",
            status="state-service",
            count=total,
            summary=card_summary,
            entries=entries,
            meta={
                "active": self._int(overview.get("active"), 0),
                "degraded": degraded,
                "recent_success_rate": overview.get("recent_success_rate"),
                "last_verified_at": self._string(overview.get("last_verified_at")),
                "last_failure_class": self._string(overview.get("last_failure_class")),
                "last_fallback": last_fallback,
                "resource_conflicts": self._int(overview.get("resource_conflicts"), 0),
                "failure_source": routine_diagnostics["failure_source"],
                "blocked_next_step": routine_diagnostics["blocked_next_step"],
                "remediation_summary": routine_diagnostics["remediation_summary"],
                "visible_count": len(entries),
                "truncated": total > len(entries),
            },
        )

    async def _build_agents_card(self, app_state: Any) -> RuntimeOverviewCard:
        service = getattr(app_state, "agent_profile_service", None)
        items = await self._call_list_method(service, "list_agents")
        if items is _MISSING:
            return self._unavailable_card("agents", "智能体", self._unavailable_summary("智能体"))
        total = await self._call_count_method(service)
        if total is None:
            total = len(items)
        enriched_items = await self._enrich_agent_overview_items(items, service)
        return self._available_card(
            key="agents",
            title="智能体",
            source="agent_profile_service",
            count=total,
            summary="由默认配置、覆盖配置与运行态汇总出的可见智能体画像。",
            entries=self._map_agent_entries(enriched_items),
            meta=self._build_standard_card_meta(enriched_items, total),
        )

    async def _build_industry_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        return await self._service_card(
            target=app_state.industry_service,
            key="industry",
            title="行业团队",
            source="industry_service",
            summary="正式行业实例、团队蓝图与其关联运行对象。",
            methods=("list_instances",),
            count_methods=("count_instances",),
            mapper=self._map_industry_entries,
        )

    async def _build_main_brain_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        return await self._main_brain_assembly.build_main_brain_card(app_state)

    async def _build_capabilities_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        capability_service = app_state.capability_service
        if capability_service is None:
            return self._unavailable_card(
                "capabilities",
                "能力",
                "能力图谱暂未接入。",
            )
        mounts = await self._call_list_method(capability_service, "list_capabilities")
        if mounts is _MISSING:
            return self._unavailable_card("capabilities", "能力", "能力图谱暂未接入。")
        summary = self._normalize_capability_summary(
            await self._call_optional_method(capability_service, "summarize"),
            mounts,
        )
        summary.update(await self._build_capability_governance_projection(app_state))
        return RuntimeOverviewCard(
            key="capabilities",
            title="能力",
            source="capability_service",
            status="state-service",
            count=len(mounts),
            summary=self._capability_summary_text(summary),
            entries=self._map_capability_entries(mounts),
            meta=summary,
        )

    async def _build_predictions_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        return await self._service_card(
            target=app_state.prediction_service,
            key="predictions",
            title="预测",
            source="prediction_service",
            summary="结构化预测案例、受治理建议与自动优化结果。",
            methods=("list_cases",),
            mapper=self._map_prediction_entries,
        )

    async def _build_governance_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        service = app_state.governance_service
        status_getter = getattr(service, "get_status", None)
        if not callable(status_getter):
            return self._unavailable_card(
                "governance",
                "运行治理",
                "治理控制暂未接入。",
            )
        try:
            status = status_getter()
        except Exception:
            logger.debug("runtime_center governance status failed", exc_info=True)
            return self._unavailable_card(
                "governance",
                "运行治理",
                "治理控制暂未接入。",
            )
        payload = self._model_dump(status)
        emergency_active = bool(payload.get("emergency_stop_active"))
        handoff = self._mapping(payload.get("handoff")) or {}
        staffing = self._mapping(payload.get("staffing")) or {}
        human_assist = self._mapping(payload.get("human_assist")) or {}
        host_twin = self._mapping(payload.get("host_twin")) or {}
        host_companion_session = self._mapping(payload.get("host_companion_session")) or {}
        host_twin_summary_payload = self._mapping(payload.get("host_twin_summary")) or build_host_twin_summary(
            host_twin,
            host_companion_session=host_companion_session,
        )
        if isinstance(host_twin_summary_payload, dict):
            host_twin_summary_payload["continuity_state"] = self._string(
                host_twin_summary_payload.get("continuity_state"),
            ) or derive_host_twin_continuity_state(host_twin_summary_payload)
        canonical_host_ready = host_twin_summary_ready(host_twin_summary_payload)
        host_twin_blocked = False
        if isinstance(host_twin_summary_payload, dict):
            recommended_scheduler_action = self._string(
                host_twin_summary_payload.get("recommended_scheduler_action"),
            )
            normalized_scheduler_action = (
                recommended_scheduler_action.strip().lower()
                if recommended_scheduler_action is not None
                else ""
            )
            host_twin_blocked = not canonical_host_ready and bool(
                (
                    recommended_scheduler_action
                    and normalized_scheduler_action not in {"proceed", "ready", "clear", "none"}
                )
                or (
                    host_twin_summary_payload.get("contention_severity")
                    and str(host_twin_summary_payload.get("contention_severity")).lower()
                    not in {"clear", "ok", "ready"}
                )
                or int(host_twin_summary_payload.get("blocked_surface_count") or 0) > 0
            )
        runtime_blocked = bool(
            handoff.get("active")
            or int(staffing.get("pending_confirmation_count") or 0) > 0
            or int(human_assist.get("blocked_count") or 0) > 0
            or host_twin_blocked
        )
        query_runtime_entropy = self._resolve_query_runtime_entropy(app_state)
        sidecar_memory = self._resolve_governance_sidecar_memory(
            query_runtime_entropy=query_runtime_entropy,
            app_state=app_state,
        )
        query_runtime_entropy_payload = (
            query_runtime_entropy.model_dump(mode="json")
            if isinstance(query_runtime_entropy, RuntimeQueryRuntimeEntropyPayload)
            else {}
        )
        current_status = "active" if emergency_active else ("blocked" if runtime_blocked else "idle")
        summary = payload.get("emergency_reason")
        failure_source = None
        blocked_next_step = None
        default_summary = "运行时正在接收新工作。"
        if emergency_active:
            failure_source = "emergency-stop"
            blocked_next_step = "Clear the emergency stop before resuming runtime dispatch."
            default_summary = "Emergency stop is active and runtime dispatch remains paused."
        elif handoff.get("active"):
            failure_source = "handoff"
            blocked_next_step = (
                "Confirm the active handoff return condition before resuming runtime dispatch."
            )
            summary = summary or "Human handoff is active and runtime dispatch is temporarily gated."
        elif int(staffing.get("pending_confirmation_count") or 0) > 0:
            failure_source = "staffing"
            blocked_next_step = (
                "Confirm who owns the runtime follow-up before resuming automatic execution."
            )
            summary = summary or "Staffing confirmation is still pending for active runtime work."
        elif int(human_assist.get("blocked_count") or 0) > 0:
            failure_source = "human-assist"
            blocked_next_step = (
                "Review the blocking human assist tasks and resume only after evidence is accepted."
            )
            summary = summary or "Human assist tasks are still blocking automatic continuation."
        if (
            failure_source is None
            and isinstance(sidecar_memory, dict)
            and self._string(sidecar_memory.get("status")) == "degraded"
        ):
            failure_source = self._string(sidecar_memory.get("failure_source")) or "sidecar-memory"
            blocked_next_step = self._string(sidecar_memory.get("blocked_next_step"))
            summary = summary or self._string(sidecar_memory.get("summary"))
            current_status = "blocked"
        if (
            not summary
            and isinstance(host_twin_summary_payload, dict)
            and host_twin_summary_payload.get("recommended_scheduler_action")
        ):
            active_family_keys = [
                str(value).strip()
                for value in list(host_twin_summary_payload.get("active_app_family_keys") or [])
                if str(value).strip()
            ]
            selected_seat_ref = self._string(
                host_twin_summary_payload.get("selected_seat_ref"),
            )
            seat_selection_policy = self._string(
                host_twin_summary_payload.get("seat_selection_policy"),
            )
            coordination_action = self._string(
                host_twin_summary_payload.get("recommended_scheduler_action"),
            )
            normalized_scheduler_action = (
                coordination_action.strip().lower()
                if coordination_action is not None
                else ""
            )
            if canonical_host_ready or normalized_scheduler_action in {"proceed", "ready", "clear", "none"}:
                summary = "Host twin ready"
                if selected_seat_ref:
                    summary += f" on {selected_seat_ref}"
                if seat_selection_policy:
                    summary += f" via {seat_selection_policy}"
                if active_family_keys:
                    summary += "; active app families: " + ", ".join(active_family_keys)
                summary += "."
            else:
                failure_source = failure_source or "host-twin"
                blocked_next_step = blocked_next_step or (
                    f"Follow the host coordination action: {coordination_action}."
                )
                active_count = int(host_twin_summary_payload.get("active_app_family_count") or 0)
                summary = (
                    "Host twin coordination recommends "
                    f"{coordination_action} "
                    f"with {active_count} active app family twin(s)."
                )
        diagnostics = build_execution_diagnostics(
            failure_source=failure_source,
            blocked_next_step=blocked_next_step,
            remediation_summary=self._string(summary),
            default_remediation_summary=default_summary,
        )
        summary = diagnostics["remediation_summary"] or default_summary
        entry = RuntimeOverviewEntry(
            id=str(payload.get("control_id") or "runtime"),
            title="运行治理",
            kind="governance",
            status=current_status,
            owner=self._string(payload.get("emergency_actor")),
            summary=str(summary),
            updated_at=self._dt(payload.get("updated_at")),
            route="/api/runtime-center/governance/status",
            meta={
                "pending_decisions": payload.get("pending_decisions"),
                "pending_patches": payload.get("pending_patches"),
                "paused_schedule_ids": payload.get("paused_schedule_ids"),
                "channel_shutdown_applied": payload.get("channel_shutdown_applied"),
                "host_twin": payload.get("host_twin"),
                "host_companion_session": payload.get("host_companion_session"),
                "host_twin_summary": host_twin_summary_payload,
                "query_runtime_entropy": query_runtime_entropy_payload,
                "sidecar_memory": sidecar_memory,
                "handoff": handoff,
                "staffing": staffing,
                "human_assist": human_assist,
                "failure_source": diagnostics["failure_source"],
                "blocked_next_step": diagnostics["blocked_next_step"],
                "remediation_summary": diagnostics["remediation_summary"],
            },
        )
        return RuntimeOverviewCard(
            key="governance",
            title="运行治理",
            source="governance_service",
            status="state-service",
            count=1,
            summary=str(summary),
            entries=[entry],
            meta={
                **payload,
                "host_twin_summary": host_twin_summary_payload,
                "query_runtime_entropy": query_runtime_entropy_payload,
                "sidecar_memory": sidecar_memory,
                "failure_source": diagnostics["failure_source"],
                "blocked_next_step": diagnostics["blocked_next_step"],
                "remediation_summary": diagnostics["remediation_summary"],
            },
        )

    def _runtime_query_entropy_payload(
        self,
        value: object | None,
    ) -> RuntimeQueryRuntimeEntropyPayload:
        payload = self._mapping(value)
        if not payload:
            return RuntimeQueryRuntimeEntropyPayload()
        return RuntimeQueryRuntimeEntropyPayload.model_validate(payload)

    def _resolve_query_runtime_entropy(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> RuntimeQueryRuntimeEntropyPayload | None:
        service = app_state.query_execution_service
        getter = getattr(service, "get_query_runtime_entropy_contract", None)
        if not callable(getter):
            return None
        try:
            payload = getter()
        except Exception:
            logger.debug("runtime_center query runtime entropy lookup failed", exc_info=True)
            return None
        entropy = self._mapping(payload)
        return self._runtime_query_entropy_payload(entropy) if entropy else None

    def _resolve_governance_sidecar_memory(
        self,
        *,
        query_runtime_entropy: RuntimeQueryRuntimeEntropyPayload | None,
        app_state: RuntimeCenterAppStateView,
    ) -> dict[str, Any] | None:
        sidecar_memory = (
            query_runtime_entropy.sidecar_memory
            if isinstance(query_runtime_entropy, RuntimeQueryRuntimeEntropyPayload)
            else {}
        )
        if sidecar_memory:
            return dict(sidecar_memory)
        return self._resolve_runtime_contract_sidecar_memory(app_state)

    def _resolve_runtime_contract_sidecar_memory(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> dict[str, Any] | None:
        runtime_contracts = (
            app_state.actor_worker_runtime_contract,
            app_state.actor_supervisor_runtime_contract,
        )
        for target in runtime_contracts:
            runtime_contract = self._mapping(target)
            if not runtime_contract:
                continue
            sidecar_memory = self._mapping(runtime_contract.get("sidecar_memory"))
            if sidecar_memory:
                return sidecar_memory
        return None

    async def _build_evidence_card(self, app_state: RuntimeCenterAppStateView) -> RuntimeOverviewCard:
        target = app_state.evidence_query_service
        items = await self._call_list_method(
            target,
            "list_recent_records",
            "list_recent_evidence",
            "list_evidence",
            "list_records",
        )
        if items is _MISSING:
            return self._unavailable_card("evidence", "证据", "证据视图暂未接入。")
        total_count = self._int(
            await self._call_optional_method(target, "count_records"),
            len(items),
        )
        return RuntimeOverviewCard(
            key="evidence",
            title="证据",
            source="evidence_query_service",
            status="state-service",
            count=total_count,
            summary=self._summarize_evidence_card(items, total_count),
            entries=self._map_evidence_entries(items),
            meta={
                "recent_count": len(items),
                "by_kind": self._counter_meta(
                    items,
                    "capability_ref",
                    classifier=self._classify_evidence_kind,
                ),
            },
        )

    async def _build_decisions_card(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> RuntimeOverviewCard:
        card = await self._state_card(
            app_state=app_state,
            key="decisions",
            title="决策",
            summary="DecisionRequestRecord 中的待处理与已解决治理决策。",
            methods=("list_decision_requests", "list_decisions", "get_decision_requests"),
            mapper=self._map_decision_entries,
        )
        meta = dict(card.meta or {})
        meta.setdefault("route", "/api/runtime-center/decisions")
        return card.model_copy(update={"meta": meta})

    async def _build_patches_card(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> RuntimeOverviewCard:
        return await self._service_card(
            target=self._learning_source(app_state),
            key="patches",
            title="补丁",
            source="learning_service",
            summary="学习层产出的补丁提案与应用记录。",
            methods=("list_patches",),
            mapper=self._map_patch_entries,
        )

    async def _build_growth_card(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> RuntimeOverviewCard:
        return await self._service_card(
            target=self._learning_source(app_state),
            key="growth",
            title="成长",
            source="learning_service",
            summary="按智能体归集的学习变更与成长事件。",
            methods=("list_growth", "get_growth_history"),
            mapper=self._map_growth_entries,
        )

    async def _state_card(
        self,
        *,
        app_state: RuntimeCenterAppStateView,
        key: str,
        title: str,
        summary: str,
        methods: tuple[str, ...],
        count_methods: tuple[str, ...] = (),
        mapper,
    ) -> RuntimeOverviewCard:
        return await self._service_card(
            target=app_state.state_query_service,
            key=key,
            title=title,
            source="state_query_service",
            summary=summary,
            methods=methods,
            count_methods=count_methods,
            mapper=mapper,
        )

    async def _service_card(
        self,
        *,
        target: Any,
        key: str,
        title: str,
        source: str,
        summary: str,
        methods: tuple[str, ...],
        count_methods: tuple[str, ...] = (),
        mapper,
    ) -> RuntimeOverviewCard:
        items = await self._call_list_method(target, *methods)
        if items is _MISSING:
            return self._unavailable_card(
                key,
                title,
                self._unavailable_summary(title),
            )
        total = await self._call_count_method(target, *count_methods)
        if total is None:
            total = len(items)
        return self._available_card(
            key=key,
            title=title,
            source=source,
            count=total,
            summary=summary,
            entries=mapper(items),
            meta=self._build_standard_card_meta(items, total),
        )

    def _unavailable_card(self, key: str, title: str, summary: str) -> RuntimeOverviewCard:
        return RuntimeOverviewCard(
            key=key,
            title=title,
            source="unavailable",
            status="unavailable",
            summary=summary,
        )

    async def _call_list_method(self, target: Any, *method_names: str) -> object | list[Any]:
        if target is None:
            return _MISSING
        for method_name in method_names:
            method = getattr(target, method_name, None)
            if method is None:
                continue
            for kwargs in ({"limit": self._item_limit}, {},):
                try:
                    result = method(**kwargs)
                except (AssertionError, TypeError, ValueError):
                    continue
                except Exception:
                    logger.debug("runtime_center list call failed", exc_info=True)
                    return _MISSING
                try:
                    return self._normalize_list(await self._maybe_await(result))
                except (AssertionError, TypeError, ValueError):
                    continue
                except Exception:
                    logger.debug("runtime_center list await failed", exc_info=True)
                    return _MISSING
        return _MISSING

    async def _call_count_method(self, target: Any, *method_names: str) -> int | None:
        if target is None:
            return None
        for method_name in method_names:
            method = getattr(target, method_name, None)
            if method is None:
                continue
            try:
                value = await self._maybe_await(method())
            except Exception:
                logger.debug("runtime_center count call failed", exc_info=True)
                return None
            count = self._int(value, None)
            if count is not None:
                return count
        return None

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def _call_optional_method(self, target: Any, method_name: str) -> Any:
        if target is None:
            return None
        method = getattr(target, method_name, None)
        if method is None:
            return None
        try:
            return await self._maybe_await(method())
        except Exception:
            logger.debug("runtime_center optional call failed", exc_info=True)
            return None

    def _model_dump(self, value: Any) -> dict[str, Any]:
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json")
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def _normalize_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, Mapping):
            for key in ("items", "records", "tasks", "entries", "results"):
                nested = value.get(key)
                if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes)):
                    return list(nested)
            return [value]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return list(value)
        return [value]

    async def _enrich_agent_overview_items(
        self,
        items: list[Any],
        service: Any,
    ) -> list[Any]:
        detail_getter = getattr(service, "get_agent_detail", None)
        if not callable(detail_getter):
            return items
        enriched: list[Any] = []
        for item in items:
            payload = self._model_dump(item)
            agent_id = self._string(payload.get("agent_id") or payload.get("id"))
            if agent_id is None:
                enriched.append(payload or item)
                continue
            try:
                detail = await self._maybe_await(detail_getter(agent_id))
            except Exception:
                logger.debug("runtime_center agent detail enrichment failed", exc_info=True)
                enriched.append(payload or item)
                continue
            governance = self._project_agent_capability_governance_from_detail(
                payload,
                detail,
            )
            if governance is not None:
                payload["capability_governance"] = governance
            enriched.append(payload or item)
        return enriched

    def _project_agent_capability_governance_from_detail(
        self,
        agent_payload: Mapping[str, Any],
        detail: Any,
    ) -> dict[str, Any] | None:
        detail_payload = self._model_dump(detail)
        runtime_payload = self._model_dump(detail_payload.get("runtime"))
        metadata = self._model_dump(runtime_payload.get("metadata"))
        capability_layers = IndustrySeatCapabilityLayers.from_metadata(
            metadata.get("capability_layers"),
        )
        if not capability_layers.merged_capability_ids():
            return None
        layers_payload = capability_layers.to_metadata_payload()
        raw_session_overlay = self._model_dump(metadata.get("current_session_overlay"))
        overlay_capability_ids = self._strings(
            raw_session_overlay.get("capability_ids"),
        ) or self._strings(layers_payload.get("session_overlay_capability_ids"))
        current_session_overlay: dict[str, Any] | None = None
        if raw_session_overlay or overlay_capability_ids:
            current_session_overlay = {
                **raw_session_overlay,
                "overlay_scope": self._string(raw_session_overlay.get("overlay_scope")) or "session",
                "overlay_mode": self._string(raw_session_overlay.get("overlay_mode")) or (
                    "additive" if overlay_capability_ids else None
                ),
                "session_id": self._string(raw_session_overlay.get("session_id")),
                "capability_ids": overlay_capability_ids,
                "status": self._string(raw_session_overlay.get("status")) or (
                    "active" if overlay_capability_ids else None
                ),
            }
        return {
            "is_projection": True,
            "is_truth_store": False,
            "source": "agent_runtime.metadata.capability_layers",
            "layers": layers_payload,
            "counts": {
                "role_prototype": len(self._strings(layers_payload.get("role_prototype_capability_ids"))),
                "seat_instance": len(self._strings(layers_payload.get("seat_instance_capability_ids"))),
                "cycle_delta": len(self._strings(layers_payload.get("cycle_delta_capability_ids"))),
                "session_overlay": len(self._strings(layers_payload.get("session_overlay_capability_ids"))),
                "effective": len(self._strings(layers_payload.get("effective_capability_ids"))),
            },
            "current_session_overlay": current_session_overlay,
            "lifecycle": {
                "employment_mode": self._string(runtime_payload.get("employment_mode"))
                or self._string(agent_payload.get("employment_mode")),
                "activation_mode": self._string(runtime_payload.get("activation_mode"))
                or self._string(agent_payload.get("activation_mode")),
                "desired_state": self._string(runtime_payload.get("desired_state")),
                "runtime_status": self._string(runtime_payload.get("runtime_status")),
                "status": self._string(agent_payload.get("status")),
            },
        }

    def _map_work_context_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "updated_at",
            "created_at",
            builder=self._build_work_context_entry,
        )

    def _build_work_context_entry(self, item: Any) -> RuntimeOverviewEntry:
        context_id = self._string(self._get_field(item, "id")) or "unknown-work-context"
        return RuntimeOverviewEntry(
            id=context_id,
            title=self._string(self._get_field(item, "title")) or context_id,
            kind="work-context",
            status=self._string(self._get_field(item, "status")) or "active",
            owner=self._string(
                self._get_field(item, "owner_scope", "owner_agent_id"),
            ),
            summary=self._string(self._get_field(item, "summary")),
            updated_at=self._dt(self._get_field(item, "updated_at", "created_at")),
            route=self._string(self._get_field(item, "route"))
            or f"/api/runtime-center/work-contexts/{context_id}",
            meta={
                "context_type": self._string(self._get_field(item, "context_type")),
                "context_key": self._string(self._get_field(item, "context_key")),
                "primary_thread_id": self._string(
                    self._get_field(item, "primary_thread_id"),
                ),
                "task_count": self._int(self._get_field(item, "task_count"), 0),
                "active_task_count": self._int(
                    self._get_field(item, "active_task_count"),
                    0,
                ),
            },
        )

    def _map_routine_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        entries = []
        for item in self._sorted(items, "updated_at", "created_at"):
            routine_id = self._string(self._get_field(item, "id", "routine_id")) or "unknown-routine"
            actions = self._string_map(self._get_field(item, "actions"))
            actions.pop("replay", None)
            route = self._string(self._get_field(item, "route")) or f"/api/routines/{routine_id}"
            meta = self._mapping(self._get_field(item, "meta")) or {}
            entries.append(
                RuntimeOverviewEntry(
                    id=routine_id,
                    title=self._string(self._get_field(item, "title", "name")) or routine_id,
                    kind="routine",
                    status=self._string(self._get_field(item, "status")) or "active",
                    owner=self._string(self._get_field(item, "owner_agent_id", "owner_scope", "owner")),
                    summary=self._string(self._get_field(item, "summary")),
                    updated_at=self._dt(self._get_field(item, "updated_at", "created_at")),
                    route=route,
                    actions=actions,
                    meta={
                        "engine_kind": self._string(meta.get("engine_kind") or self._get_field(item, "engine_kind")),
                        "trigger_kind": self._string(meta.get("trigger_kind") or self._get_field(item, "trigger_kind")),
                        "success_rate": meta.get("success_rate") if "success_rate" in meta else self._get_field(item, "success_rate"),
                        "last_verified_at": self._string(meta.get("last_verified_at") or self._get_field(item, "last_verified_at")),
                    },
                ),
            )
        return entries
    def _map_agent_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "updated_at",
            builder=self._build_agent_entry,
        )

    def _build_agent_entry(self, item: Any) -> RuntimeOverviewEntry:
        agent_id = self._string(self._get_field(item, "agent_id", "id")) or "unknown-agent"
        capabilities = self._strings(self._get_field(item, "capabilities"))
        governance = self._model_dump(self._get_field(item, "capability_governance"))
        lifecycle = self._model_dump(governance.get("lifecycle"))
        overlay = self._model_dump(governance.get("current_session_overlay"))
        return RuntimeOverviewEntry(
            id=agent_id,
            title=self._string(self._get_field(item, "name")) or agent_id,
            kind="agent",
            status=self._string(self._get_field(item, "status")) or "idle",
            owner=self._string(self._get_field(item, "role_name")),
            summary=self._string(self._get_field(item, "role_summary", "today_output_summary", "latest_evidence_summary")),
            updated_at=self._dt(self._get_field(item, "updated_at")),
            route=f"/api/runtime-center/agents/{agent_id}",
            meta={
                "risk_level": self._string(self._get_field(item, "risk_level")),
                "current_focus_kind": self._string(self._get_field(item, "current_focus_kind")),
                "current_focus_id": self._string(self._get_field(item, "current_focus_id")),
                "current_focus": self._string(self._get_field(item, "current_focus")),
                "current_task_id": self._string(self._get_field(item, "current_task_id")),
                "environment_summary": self._string(self._get_field(item, "environment_summary")),
                "capability_count": len(capabilities),
                "employment_mode": self._string(lifecycle.get("employment_mode")),
                "activation_mode": self._string(lifecycle.get("activation_mode")),
                "desired_state": self._string(lifecycle.get("desired_state")),
                "runtime_status": self._string(lifecycle.get("runtime_status")),
                "capability_layer_counts": self._normalize_int_map(governance.get("counts")),
                "session_overlay_active": bool(
                    self._strings(overlay.get("capability_ids"))
                    or self._string(overlay.get("status")) == "active"
                ),
            },
        )

    def _map_main_brain_entries(
        self,
        *,
        strategies: list[Any],
        industries: list[Any],
        industry_by_instance_id: Mapping[str, Any],
    ) -> list[RuntimeOverviewEntry]:
        return self._main_brain_assembly.map_main_brain_entries(
            strategies=strategies,
            industries=industries,
            industry_by_instance_id=industry_by_instance_id,
        )

    def _select_prebuilt_card(
        self,
        prebuilt_cards: Sequence[RuntimeOverviewCard] | None,
        key: str,
    ) -> RuntimeOverviewCard | None:
        if not prebuilt_cards:
            return None
        for card in prebuilt_cards:
            if card.key == key:
                return card
        return None

    async def build_main_brain_payload(
        self,
        app_state: RuntimeCenterAppStateView,
        *,
        prebuilt_cards: Sequence[RuntimeOverviewCard] | None = None,
        surface: RuntimeCenterSurfaceInfo | None = None,
        buddy_profile_id: str | None = None,
    ) -> RuntimeMainBrainResponse:
        main_brain_card = self._select_prebuilt_card(prebuilt_cards, "main-brain")
        if main_brain_card is None:
            main_brain_card = await self._build_main_brain_card(app_state)
        evidence_card = self._select_prebuilt_card(prebuilt_cards, "evidence")
        if evidence_card is None:
            evidence_card = await self._build_evidence_card(app_state)
        decisions_card = self._select_prebuilt_card(prebuilt_cards, "decisions")
        if decisions_card is None:
            decisions_card = await self._build_decisions_card(app_state)
        patches_card = self._select_prebuilt_card(prebuilt_cards, "patches")
        if patches_card is None:
            patches_card = await self._build_patches_card(app_state)
        governance_card = self._select_prebuilt_card(prebuilt_cards, "governance")
        if governance_card is None:
            governance_card = await self._build_governance_card(app_state)
        governance = await self._build_main_brain_governance_payload(
            governance_card,
            app_state,
        )
        governance_payload = governance.model_dump(mode="json")
        recovery = self._build_main_brain_recovery_payload(app_state)
        automation = await self._build_main_brain_automation_payload(app_state)
        signals = dict(main_brain_card.meta.get("signals") or {})
        signals.update(
            {
                "governance": self._build_main_brain_operator_signal(
                    "governance",
                    governance_payload,
                    count=self._int(governance.pending_patches, 0)
                    + self._int(governance.pending_decisions, 0)
                    + (1 if governance.handoff_active else 0),
                ),
                "automation": self._build_main_brain_operator_signal(
                    "automation",
                    automation,
                    count=self._int(automation.get("schedule_count"), 0),
                ),
                "recovery": self._build_main_brain_operator_signal(
                    "recovery",
                    recovery,
                    count=1 if recovery.get("available") else 0,
                ),
            },
        )
        signal_map = {
            self._string(value.get("key")) or key: value
            for key, value in signals.items()
            if isinstance(value, dict)
        }
        control_chain_order = [
            "carrier",
            "strategy",
            "lanes",
            "backlog",
            "current_cycle",
            "assignments",
            "agent_reports",
            "environment",
            "governance",
            "automation",
            "recovery",
            "evidence",
            "decisions",
            "patches",
        ]
        control_chain = [
            signal_map[key]
            for key in control_chain_order
            if isinstance(signal_map.get(key), dict)
        ]
        cards = [
            main_brain_card,
            evidence_card,
            decisions_card,
            patches_card,
            governance_card,
        ]
        entry = main_brain_card.entries[0] if main_brain_card.entries else None
        entry_meta = dict(entry.meta or {}) if entry is not None else {}
        industry_instance_id = self._string(entry_meta.get("industry_instance_id"))
        industry_detail = await self._load_industry_detail_payload(
            app_state.industry_service,
            industry_instance_id,
        )
        strategy = await self._resolve_main_brain_strategy_payload(
            app_state.strategy_memory_service,
            industry_instance_id=industry_instance_id,
            entry=entry,
            entry_meta=entry_meta,
        )
        carrier = self._resolve_main_brain_carrier_payload(
            entry=entry,
            entry_meta=entry_meta,
            industry_detail=industry_detail,
        )
        normalized_reports = self._normalize_main_brain_reports(
            self._normalize_list(industry_detail.get("agent_reports")),
            industry_instance_id=industry_instance_id,
        )
        normalized_backlog = [
            self._normalize_main_brain_cognition_backlog(
                self._mapping(item) or {},
                industry_instance_id=industry_instance_id,
            )
            for item in self._normalize_list(industry_detail.get("backlog"))
            if self._mapping(item)
        ]
        report_cognition = self._build_main_brain_report_cognition_payload(
            industry_detail=industry_detail,
            industry_instance_id=industry_instance_id,
            normalized_reports=normalized_reports,
        )
        buddy_summary = None
        buddy_projection_service = app_state.buddy_projection_service
        if callable(getattr(buddy_projection_service, "build_cockpit_summary", None)):
            try:
                buddy_summary = dict(
                    buddy_projection_service.build_cockpit_summary(
                        profile_id=buddy_profile_id,
                    ),
                )
            except ValueError:
                buddy_summary = None
        main_brain_planning = RuntimeMainBrainPlanningPayload.model_validate(
            self._mapping(industry_detail.get("main_brain_planning")) or {},
        )
        signals["report_cognition"] = self._build_main_brain_report_cognition_signal(
            report_cognition,
        )
        signal_map["report_cognition"] = signals["report_cognition"]
        control_chain = [
            signal_map[key]
            for key in control_chain_order + ["report_cognition"]
            if isinstance(signal_map.get(key), dict)
        ]
        surface_cards = list(prebuilt_cards) if prebuilt_cards is not None else cards
        resolved_surface = surface or build_runtime_surface(surface_cards)
        resolved_surface = self._apply_automation_surface_status(
            surface=resolved_surface,
            automation=automation,
        )
        response = RuntimeMainBrainResponse(
            surface=resolved_surface,
            strategy=strategy,
            carrier=carrier,
            lanes=self._normalize_list(industry_detail.get("lanes")),
            cycles=self._normalize_list(industry_detail.get("cycles")),
            backlog=normalized_backlog,
            current_cycle=self._mapping(industry_detail.get("current_cycle")),
            main_brain_planning=main_brain_planning,
            assignments=self._normalize_list(industry_detail.get("assignments")),
            reports=normalized_reports,
            report_cognition=report_cognition,
            environment=self._build_main_brain_environment_payload(governance_card),
            governance=governance,
            recovery=recovery,
            automation=automation,
            buddy_summary=buddy_summary,
            evidence=self._build_main_brain_section(evidence_card),
            decisions=self._build_main_brain_section(decisions_card),
            patches=self._build_main_brain_section(patches_card),
            signals=signals,
            meta={
                **dict(main_brain_card.meta or {}),
                "control_chain": control_chain,
                "overview_entry_count": main_brain_card.count,
                "lane_count": self._int(entry_meta.get("lane_count"), 0),
                "backlog_count": self._int(entry_meta.get("backlog_count"), 0),
                "cycle_count": self._int(entry_meta.get("cycle_count"), 0),
                "assignment_count": self._int(entry_meta.get("assignment_count"), 0),
                "report_count": self._int(entry_meta.get("report_count"), 0),
                "decision_count": self._int(entry_meta.get("decision_count"), 0),
                "patch_count": self._int(entry_meta.get("patch_count"), 0),
                "evidence_count": self._int(entry_meta.get("evidence_count"), 0),
                "agent_reports": signals.get("agent_reports") or {},
                "report_cognition": report_cognition,
                "governance_summary": governance_payload,
                "recovery_summary": recovery,
                "automation_summary": automation,
            },
        )
        response.cockpit = await self._build_human_cockpit_payload(
            app_state,
            response,
        )
        return response

    async def _build_human_cockpit_payload(
        self,
        app_state: RuntimeCenterAppStateView,
        payload: RuntimeMainBrainResponse,
    ) -> RuntimeHumanCockpitPayload:
        approvals = self._build_human_cockpit_approvals(payload)
        main_brain = RuntimeHumanCockpitMainBrain(
            card=self._build_main_brain_human_card(payload, approvals),
            summary_fields=self._build_main_brain_human_summary_fields(
                app_state,
                payload,
                approvals,
            ),
            morning_report=self._build_main_brain_human_morning_report(payload),
            evening_report=self._build_main_brain_human_evening_report(payload),
            trend=self._build_main_brain_human_trend(payload, approvals),
            trace=self._build_main_brain_human_trace(payload, approvals),
            approvals=approvals,
            stage_summary=self._build_main_brain_human_stage_summary(payload),
        )
        agents = await self._build_human_cockpit_agents(app_state, payload)
        return RuntimeHumanCockpitPayload(
            main_brain=main_brain,
            agents=agents,
        )

    async def _build_human_cockpit_agents(
        self,
        app_state: RuntimeCenterAppStateView,
        payload: RuntimeMainBrainResponse,
    ) -> list[RuntimeHumanCockpitAgent]:
        industry_instance_id = self._string(payload.meta.get("industry_instance_id"))
        agent_items = await self._list_human_cockpit_agents(
            app_state.agent_profile_service,
            industry_instance_id=industry_instance_id,
        )
        result: list[RuntimeHumanCockpitAgent] = []
        for item in agent_items:
            agent = dict(self._mapping(item) or {})
            agent_id = self._string(agent.get("agent_id") or agent.get("id"))
            if agent_id is None or self._is_main_brain_agent_payload(agent):
                continue
            related_assignments = [
                record
                for record in payload.assignments
                if self._matches_human_cockpit_agent(record, agent_id)
            ]
            related_reports = [
                record
                for record in payload.reports
                if self._matches_human_cockpit_agent(record, agent_id)
            ]
            result.append(
                RuntimeHumanCockpitAgent(
                    agent_id=agent_id,
                    card=self._build_agent_human_card(
                        agent,
                        related_assignments=related_assignments,
                        related_reports=related_reports,
                    ),
                    summary_fields=self._build_agent_human_summary_fields(
                        agent,
                        related_assignments=related_assignments,
                        related_reports=related_reports,
                    ),
                    morning_report=self._build_agent_human_morning_report(
                        agent,
                        related_assignments=related_assignments,
                    ),
                    evening_report=self._build_agent_human_evening_report(
                        related_reports=related_reports,
                    ),
                    trend=self._build_agent_human_trend(
                        agent,
                        related_assignments=related_assignments,
                        related_reports=related_reports,
                    ),
                    trace=self._build_agent_human_trace(
                        agent,
                        related_assignments=related_assignments,
                        related_reports=related_reports,
                    ),
                )
            )
        return result

    async def _list_human_cockpit_agents(
        self,
        service: Any,
        *,
        industry_instance_id: str | None,
    ) -> list[Any]:
        list_agents = getattr(service, "list_agents", None)
        if not callable(list_agents):
            return []
        attempts: list[dict[str, Any]] = []
        if industry_instance_id is not None:
            attempts.extend(
                [
                    {
                        "limit": None,
                        "view": "business",
                        "industry_instance_id": industry_instance_id,
                    },
                    {
                        "view": "business",
                        "industry_instance_id": industry_instance_id,
                    },
                    {
                        "limit": None,
                        "industry_instance_id": industry_instance_id,
                    },
                    {
                        "industry_instance_id": industry_instance_id,
                    },
                ]
            )
        attempts.extend(
            [
                {"limit": None, "view": "business"},
                {"view": "business"},
                {"limit": None},
                {},
            ]
        )
        for kwargs in attempts:
            try:
                payload = await self._maybe_await(list_agents(**kwargs))
            except TypeError:
                continue
            except Exception:
                logger.debug("runtime_center cockpit agent list failed", exc_info=True)
                return []
            return self._normalize_list(payload)
        return []

    def _build_main_brain_human_card(
        self,
        payload: RuntimeMainBrainResponse,
        approvals: list[RuntimeHumanCockpitApproval],
    ) -> RuntimeHumanCockpitCard:
        status = "idle"
        governance_status = (self._string(payload.governance.status) or "").strip().lower()
        surface_status = (self._string(payload.surface.status) or "").strip().lower()
        if surface_status == "degraded" or governance_status in {"blocked", "degraded"}:
            status = "blocked"
        elif approvals:
            status = "reviewing"
        elif payload.assignments or payload.reports or payload.evidence.count > 0:
            status = "running"
        buddy_summary = self._mapping(payload.buddy_summary) or {}
        return RuntimeHumanCockpitCard(
            id="main-brain",
            name=self._first_human_cockpit_text(buddy_summary.get("buddy_name")) or "伙伴",
            role="主脑",
            status=status,
            progress=(
                min(
                    96,
                    40 + len(payload.reports) * 12 + self._int(payload.evidence.count, 0) * 8,
                )
                if payload.assignments or payload.reports or payload.evidence.count > 0
                else self._human_cockpit_progress_from_status(status)
            ),
            needs_attention=status == "blocked" or bool(approvals),
            is_main_brain=True,
        )

    def _build_main_brain_human_summary_fields(
        self,
        app_state: RuntimeCenterAppStateView,
        payload: RuntimeMainBrainResponse,
        approvals: list[RuntimeHumanCockpitApproval],
    ) -> list[RuntimeHumanCockpitSummaryField]:
        current_cycle = self._mapping(payload.current_cycle) or {}
        report_cognition = self._mapping(payload.report_cognition) or {}
        next_action = self._mapping(report_cognition.get("next_action")) or {}
        fields = [
            RuntimeHumanCockpitSummaryField(
                label="职责",
                value=(
                    self._first_human_cockpit_text(payload.strategy.get("summary"))
                    or "负责统筹安排、跟进进度、收结果、把需要你决定的事情提出来。"
                ),
            ),
            RuntimeHumanCockpitSummaryField(
                label="当前重点",
                value=(
                    self._first_human_cockpit_text(
                        next_action,
                        current_cycle.get("title"),
                        current_cycle.get("summary"),
                    )
                    or "今天还没有新的主脑重点。"
                ),
            ),
            RuntimeHumanCockpitSummaryField(
                label="今日进展",
                value=(
                    f"已派工 {len(payload.assignments)} 项，"
                    f"已回收 {len(payload.reports)} 份汇报，"
                    f"新增 {self._int(payload.evidence.count, 0)} 条证据。"
                ),
            ),
            RuntimeHumanCockpitSummaryField(
                label="需要你决定",
                value=(
                    f"当前有 {len(approvals)} 项待处理。"
                    if approvals
                    else "当前没有必须你立刻决定的事项。"
                ),
            ),
        ]
        return fields + self._build_main_brain_memory_summary_fields(app_state, payload)

    def _build_main_brain_memory_summary_fields(
        self,
        app_state: RuntimeCenterAppStateView,
        payload: RuntimeMainBrainResponse,
    ) -> list[RuntimeHumanCockpitSummaryField]:
        sleep_service = getattr(app_state, "memory_sleep_service", None)
        resolve_scope_overlay = getattr(sleep_service, "resolve_scope_overlay", None)
        if not callable(resolve_scope_overlay):
            return []
        scope_type, scope_id = self._resolve_main_brain_memory_scope(payload)
        if scope_type is None or scope_id is None:
            return []
        try:
            sleep_payload = resolve_scope_overlay(scope_type=scope_type, scope_id=scope_id)
        except Exception:
            logger.debug("runtime_center cockpit memory summary failed", exc_info=True)
            return []
        sleep_mapping = self._mapping(sleep_payload) or {}
        if not sleep_mapping:
            return []
        digest = self._mapping(sleep_mapping.get("digest")) or {}
        industry_profile = self._mapping(sleep_mapping.get("industry_profile")) or {}
        work_context_overlay = self._mapping(sleep_mapping.get("work_context_overlay")) or {}
        overlay_metadata = self._mapping(work_context_overlay.get("metadata")) or {}
        continuity_anchors = self._human_cockpit_text_list(
            *list(overlay_metadata.get("continuity_anchors") or []),
            self._first_human_cockpit_text(work_context_overlay.get("focus_summary")),
            *list(digest.get("current_focus") or []),
            *list(industry_profile.get("active_focuses") or []),
        )
        active_constraints = self._human_cockpit_text_list(
            *list(work_context_overlay.get("active_constraints") or []),
            *list(industry_profile.get("active_constraints") or []),
            *list(digest.get("current_constraints") or []),
        )
        proposal_count = len(list(sleep_mapping.get("structure_proposals") or []))
        conflict_count = len(list(sleep_mapping.get("conflicts") or []))
        digest_summary = self._first_human_cockpit_text(
            digest.get("summary"),
            digest.get("headline"),
            work_context_overlay.get("summary"),
            industry_profile.get("summary"),
            industry_profile.get("headline"),
        )
        if not any([continuity_anchors, active_constraints, proposal_count, conflict_count, digest_summary]):
            return []
        pending_parts = self._human_cockpit_text_list(
            f"{proposal_count} 个结构提案待处理" if proposal_count > 0 else None,
            f"{conflict_count} 个冲突待处理" if conflict_count > 0 else None,
        )
        return [
            RuntimeHumanCockpitSummaryField(
                label="最该记住",
                value=continuity_anchors[0] if continuity_anchors else "当前还没有新的连续性锚点。",
                hint=" / ".join(continuity_anchors[1:3]) or None,
            ),
            RuntimeHumanCockpitSummaryField(
                label="关键约束",
                value=active_constraints[0] if active_constraints else "当前还没有新的关键约束。",
                hint=" / ".join(active_constraints[1:3]) or None,
            ),
            RuntimeHumanCockpitSummaryField(
                label="待处理整理",
                value=" / ".join(pending_parts) if pending_parts else "当前没有待处理的记忆整理项。",
            ),
            RuntimeHumanCockpitSummaryField(
                label="最近记忆整理",
                value=digest_summary or "当前还没有新的记忆整理结果。",
                hint=self._first_human_cockpit_text(digest.get("headline")),
            ),
        ]

    def _resolve_main_brain_memory_scope(
        self,
        payload: RuntimeMainBrainResponse,
    ) -> tuple[str | None, str | None]:
        latest_assignment = self._latest_human_cockpit_record(payload.assignments)
        latest_report = self._latest_human_cockpit_record(payload.reports)
        work_context_id = self._first_human_cockpit_text(
            latest_assignment.get("work_context_id"),
            latest_assignment.get("context_id"),
            latest_assignment.get("work_context_ref"),
            latest_report.get("work_context_id"),
            payload.meta.get("work_context_id"),
        )
        if work_context_id:
            return "work_context", work_context_id
        industry_instance_id = self._string(payload.meta.get("industry_instance_id"))
        if industry_instance_id:
            return "industry", industry_instance_id
        return None, None

    def _build_main_brain_human_morning_report(
        self,
        payload: RuntimeMainBrainResponse,
    ) -> RuntimeHumanCockpitReportBlock | None:
        current_cycle = self._mapping(payload.current_cycle) or {}
        report_cognition = self._mapping(payload.report_cognition) or {}
        next_action = self._mapping(report_cognition.get("next_action")) or {}
        return self._build_human_cockpit_report_block(
            "早报",
            [
                self._first_human_cockpit_text(current_cycle.get("summary"), current_cycle.get("title")),
                self._first_human_cockpit_text(next_action.get("summary"), next_action.get("title")),
                f"今天主脑需要盯住 {len(payload.assignments)} 项执行任务。",
            ],
        )

    def _build_main_brain_human_evening_report(
        self,
        payload: RuntimeMainBrainResponse,
    ) -> RuntimeHumanCockpitReportBlock | None:
        latest_report = self._latest_human_cockpit_record(payload.reports)
        return self._build_human_cockpit_report_block(
            "晚报",
            [
                self._first_human_cockpit_text(
                    latest_report.get("headline"),
                    latest_report.get("summary"),
                ),
                f"今天共收到 {len(payload.reports)} 份汇报。",
                f"今天新增 {self._int(payload.evidence.count, 0)} 条证据。",
                (
                    f"还有 {self._int(payload.decisions.count, 0)} 项待你确认。"
                    if self._int(payload.decisions.count, 0) > 0
                    else None
                ),
            ],
            generated_at=self._first_human_cockpit_text(latest_report.get("updated_at")),
        )

    def _build_main_brain_human_trend(
        self,
        payload: RuntimeMainBrainResponse,
        approvals: list[RuntimeHumanCockpitApproval],
    ) -> list[RuntimeHumanCockpitTrendPoint]:
        approval_pressure = 92 if not approvals else max(30, 100 - len(approvals) * 18)
        return [
            self._build_human_cockpit_trend_point(
                "派工",
                len(payload.assignments),
                78 if payload.assignments else 24,
                82,
            ),
            self._build_human_cockpit_trend_point(
                "汇报",
                len(payload.reports),
                84 if payload.reports else 28,
                80,
            ),
            self._build_human_cockpit_trend_point(
                "证据",
                self._int(payload.evidence.count, 0),
                88 if self._int(payload.evidence.count, 0) > 0 else 20,
                approval_pressure,
            ),
        ]

    def _build_main_brain_human_trace(
        self,
        payload: RuntimeMainBrainResponse,
        approvals: list[RuntimeHumanCockpitApproval],
    ) -> list[RuntimeHumanCockpitTraceEntry]:
        records: list[RuntimeHumanCockpitTraceEntry] = []
        latest_report = self._latest_human_cockpit_record(payload.reports)
        latest_assignment = self._latest_human_cockpit_record(payload.assignments)
        latest_approval = approvals[0] if approvals else None
        current_cycle = self._mapping(payload.current_cycle) or {}

        report_message = self._first_human_cockpit_text(
            latest_report.get("headline"),
            latest_report.get("summary"),
        )
        if report_message:
            records.append(
                self._build_human_cockpit_trace_entry(
                    timestamp=self._first_human_cockpit_text(
                        latest_report.get("updated_at"),
                        latest_report.get("created_at"),
                        latest_report.get("generated_at"),
                        payload.generated_at,
                    ),
                    message=f"收到汇报：{report_message}",
                    kind="report",
                )
            )

        assignment_message = self._first_human_cockpit_text(
            latest_assignment.get("summary"),
            latest_assignment.get("title"),
        )
        if assignment_message:
            records.append(
                self._build_human_cockpit_trace_entry(
                    timestamp=self._first_human_cockpit_text(
                        latest_assignment.get("updated_at"),
                        latest_assignment.get("created_at"),
                        payload.generated_at,
                    ),
                    message=f"派出任务：{assignment_message}",
                    kind="assignment",
                )
            )

        if latest_approval is not None:
            records.append(
                self._build_human_cockpit_trace_entry(
                    timestamp=self._first_human_cockpit_text(
                        latest_approval.created_at,
                        payload.generated_at,
                    ),
                    message=f"等待决定：{latest_approval.title}",
                    kind="approval",
                )
            )

        cycle_message = self._first_human_cockpit_text(
            current_cycle.get("summary"),
            current_cycle.get("title"),
        )
        if cycle_message:
            records.append(
                self._build_human_cockpit_trace_entry(
                    timestamp=self._first_human_cockpit_text(
                        current_cycle.get("updated_at"),
                        current_cycle.get("created_at"),
                        payload.generated_at,
                    ),
                    message=f"阶段判断：{cycle_message}",
                    kind="cycle",
                )
            )

        return self._sort_human_cockpit_trace(records)

    def _build_agent_human_trace(
        self,
        agent: dict[str, Any],
        *,
        related_assignments: list[dict[str, Any]],
        related_reports: list[dict[str, Any]],
    ) -> list[RuntimeHumanCockpitTraceEntry]:
        records: list[RuntimeHumanCockpitTraceEntry] = []
        latest_assignment = self._latest_human_cockpit_record(related_assignments)
        latest_report = self._latest_human_cockpit_record(related_reports)

        assignment_message = self._first_human_cockpit_text(
            latest_assignment.get("summary"),
            latest_assignment.get("title"),
        )
        if assignment_message:
            records.append(
                self._build_human_cockpit_trace_entry(
                    timestamp=self._first_human_cockpit_text(
                        latest_assignment.get("updated_at"),
                        latest_assignment.get("created_at"),
                        agent.get("updated_at"),
                        "now",
                    ),
                    message=f"接到任务：{assignment_message}",
                    kind="assignment",
                )
            )

        report_message = self._first_human_cockpit_text(
            latest_report.get("headline"),
            latest_report.get("summary"),
        )
        if report_message:
            records.append(
                self._build_human_cockpit_trace_entry(
                    timestamp=self._first_human_cockpit_text(
                        latest_report.get("updated_at"),
                        latest_report.get("created_at"),
                        agent.get("updated_at"),
                        "now",
                    ),
                    message=f"回传结果：{report_message}",
                    kind="report",
                )
            )

        if not records:
            focus_message = self._first_human_cockpit_text(
                agent.get("current_focus"),
                agent.get("role_summary"),
            )
            if focus_message:
                records.append(
                    self._build_human_cockpit_trace_entry(
                        timestamp=self._first_human_cockpit_text(
                            agent.get("updated_at"),
                            agent.get("created_at"),
                            "now",
                        ),
                        message=f"当前负责：{focus_message}",
                        kind="focus",
                    )
                )
        return self._sort_human_cockpit_trace(records)

    def _build_human_cockpit_trace_entry(
        self,
        *,
        timestamp: str | None,
        message: str | None,
        kind: str | None,
    ) -> RuntimeHumanCockpitTraceEntry:
        return RuntimeHumanCockpitTraceEntry(
            timestamp=timestamp or "now",
            message=message or "暂无进展记录",
            kind=kind,
        )

    def _sort_human_cockpit_trace(
        self,
        records: Sequence[RuntimeHumanCockpitTraceEntry],
    ) -> list[RuntimeHumanCockpitTraceEntry]:
        return sorted(
            list(records),
            key=lambda item: (self._string(item.timestamp) or "", self._string(item.kind) or ""),
            reverse=True,
        )[:4]

    def _build_main_brain_human_stage_summary(
        self,
        payload: RuntimeMainBrainResponse,
    ) -> RuntimeHumanCockpitStageSummary | None:
        current_cycle = self._mapping(payload.current_cycle) or {}
        report_cognition = self._mapping(payload.report_cognition) or {}
        judgment = self._mapping(report_cognition.get("judgment")) or {}
        bullets = self._human_cockpit_text_list(
            (
                f"当前阶段已经派出 {len(payload.assignments)} 项执行任务。"
                if payload.assignments
                else None
            ),
            (
                f"已回收 {len(payload.reports)} 份执行汇报。"
                if payload.reports
                else None
            ),
            (
                f"已有 {self._int(payload.evidence.count, 0)} 条证据进入系统。"
                if self._int(payload.evidence.count, 0) > 0
                else None
            ),
            self._first_human_cockpit_text(
                report_cognition.get("replan_reasons"),
                judgment.get("summary"),
            ),
        )
        if not bullets:
            return None
        return RuntimeHumanCockpitStageSummary(
            title=self._first_human_cockpit_text(current_cycle.get("title")) or "当前阶段汇总",
            period_label="当前周期",
            summary=(
                self._first_human_cockpit_text(
                    current_cycle.get("summary"),
                    payload.strategy.get("summary"),
                    self._mapping(report_cognition.get("next_action")) or {},
                )
                or "主脑正在持续收口当前阶段结果。"
            ),
            bullets=bullets,
        )

    def _build_human_cockpit_approvals(
        self,
        payload: RuntimeMainBrainResponse,
    ) -> list[RuntimeHumanCockpitApproval]:
        approvals: list[RuntimeHumanCockpitApproval] = []
        for entry in payload.decisions.entries:
            record = self._mapping(entry) or {}
            actions = self._mapping(record.get("actions")) or {}
            status = (self._first_human_cockpit_text(record.get("status")) or "").strip().lower()
            if "approve" not in actions and "reject" not in actions and status not in {
                "open",
                "pending",
                "reviewing",
                "waiting",
                "blocked",
            }:
                continue
            approval_id = self._first_human_cockpit_text(
                record.get("id"),
                record.get("decision_id"),
                record.get("title"),
            )
            if approval_id is None:
                continue
            approvals.append(
                RuntimeHumanCockpitApproval(
                    id=approval_id,
                    kind="decision",
                    title=(
                        self._first_human_cockpit_text(
                            record.get("title"),
                            record.get("headline"),
                        )
                        or "待处理事项"
                    ),
                    reason=(
                        self._first_human_cockpit_text(
                            record.get("summary"),
                            record.get("reason"),
                            record.get("detail"),
                        )
                        or "主脑判断这件事需要你拍板。"
                    ),
                    recommendation="建议先确认是否现在执行这项决定。",
                    risk=(
                        self._first_human_cockpit_text(
                            record.get("risk"),
                            record.get("impact"),
                        )
                        or "如果继续搁置，当前推进会继续往后顺延。"
                    ),
                    initiator=(
                        self._first_human_cockpit_text(
                            record.get("owner"),
                            record.get("initiator"),
                            record.get("requested_by"),
                        )
                        or "主脑"
                    ),
                    created_at=(
                        self._first_human_cockpit_text(
                            record.get("created_at"),
                            record.get("updated_at"),
                        )
                        or "刚刚"
                    ),
                )
            )
        return approvals

    def _build_agent_human_card(
        self,
        agent: dict[str, Any],
        *,
        related_assignments: list[dict[str, Any]],
        related_reports: list[dict[str, Any]],
    ) -> RuntimeHumanCockpitCard:
        agent_id = self._string(agent.get("agent_id") or agent.get("id")) or "agent"
        status = self._string(agent.get("status")) or "idle"
        attention = self._human_cockpit_status_needs_attention(status) or any(
            self._human_cockpit_status_needs_attention(
                self._first_human_cockpit_text(report.get("status")),
            )
            for report in related_reports
        )
        progress = min(
            100,
            self._human_cockpit_progress_from_status(status)
            + min(24, len(related_assignments) * 12 + len(related_reports) * 10),
        )
        return RuntimeHumanCockpitCard(
            id=agent_id,
            name=(
                self._first_human_cockpit_text(agent.get("name"), agent_id)
                or agent_id
            ),
            role=self._first_human_cockpit_text(agent.get("role_name")) or "职业智能体",
            status=status,
            progress=progress,
            needs_attention=attention,
        )

    def _build_agent_human_summary_fields(
        self,
        agent: dict[str, Any],
        *,
        related_assignments: list[dict[str, Any]],
        related_reports: list[dict[str, Any]],
    ) -> list[RuntimeHumanCockpitSummaryField]:
        related_assignment = self._latest_human_cockpit_record(related_assignments)
        related_report = self._latest_human_cockpit_record(related_reports)
        return [
            RuntimeHumanCockpitSummaryField(
                label="职业",
                value=self._first_human_cockpit_text(agent.get("role_name")) or "职业智能体",
            ),
            RuntimeHumanCockpitSummaryField(
                label="职责",
                value=(
                    self._first_human_cockpit_text(agent.get("role_summary"))
                    or "负责对应岗位的执行与结果回传。"
                ),
            ),
            RuntimeHumanCockpitSummaryField(
                label="主要负责工作",
                value=(
                    self._first_human_cockpit_text(
                        agent.get("current_focus"),
                        related_assignment.get("summary"),
                        related_assignment.get("title"),
                        related_report.get("headline"),
                    )
                    or "当前还没有明确展示的工作重点。"
                ),
            ),
            RuntimeHumanCockpitSummaryField(
                label="当前状态",
                value=self._human_cockpit_status_label(agent.get("status")),
            ),
        ]

    def _build_agent_human_morning_report(
        self,
        agent: dict[str, Any],
        *,
        related_assignments: list[dict[str, Any]],
    ) -> RuntimeHumanCockpitReportBlock | None:
        related_assignment = self._latest_human_cockpit_record(related_assignments)
        role_summary = self._first_human_cockpit_text(agent.get("role_summary"))
        return self._build_human_cockpit_report_block(
            "早报",
            [
                self._first_human_cockpit_text(agent.get("current_focus")),
                self._first_human_cockpit_text(
                    related_assignment.get("summary"),
                    related_assignment.get("title"),
                ),
                f"今天继续推进：{role_summary}" if role_summary else None,
            ],
        )

    def _build_agent_human_evening_report(
        self,
        *,
        related_reports: list[dict[str, Any]],
    ) -> RuntimeHumanCockpitReportBlock | None:
        related_report = self._latest_human_cockpit_record(related_reports)
        return self._build_human_cockpit_report_block(
            "晚报",
            [
                self._first_human_cockpit_text(
                    related_report.get("headline"),
                    related_report.get("summary"),
                ),
                (
                    "当前结果状态："
                    + (
                        self._first_human_cockpit_text(
                            related_report.get("result"),
                            related_report.get("status"),
                        )
                        or "推进中"
                    )
                    if related_report
                    else None
                ),
                (
                    "最近回传时间："
                    + (
                        self._first_human_cockpit_text(related_report.get("updated_at"))
                        or ""
                    )
                    if self._first_human_cockpit_text(related_report.get("updated_at"))
                    else None
                ),
            ],
            generated_at=self._first_human_cockpit_text(related_report.get("updated_at")),
        )

    def _build_agent_human_trend(
        self,
        agent: dict[str, Any],
        *,
        related_assignments: list[dict[str, Any]],
        related_reports: list[dict[str, Any]],
    ) -> list[RuntimeHumanCockpitTrendPoint]:
        completed_count = sum(
            1
            for record in related_assignments
            if (self._first_human_cockpit_text(record.get("status")) or "").strip().lower()
            == "completed"
        )
        base_completion = self._human_cockpit_progress_from_status(agent.get("status"))
        feedback_quality = 84 if related_reports else 45
        continuity = 42 if self._human_cockpit_status_needs_attention(agent.get("status")) else 88
        return [
            self._build_human_cockpit_trend_point(
                "任务完成",
                completed_count or len(related_assignments),
                base_completion,
                feedback_quality,
            ),
            self._build_human_cockpit_trend_point(
                "结果回传",
                len(related_reports),
                82 if related_reports else 30,
                feedback_quality,
            ),
            self._build_human_cockpit_trend_point(
                "协作连贯",
                1 if continuity >= 80 else 0,
                continuity,
                continuity,
            ),
        ]

    def _build_human_cockpit_report_block(
        self,
        title: str,
        items: list[str | None],
        *,
        generated_at: str | None = None,
    ) -> RuntimeHumanCockpitReportBlock | None:
        lines = self._human_cockpit_text_list(*items)[:3]
        if not lines:
            return None
        return RuntimeHumanCockpitReportBlock(
            title=title,
            items=lines,
            generated_at=generated_at,
        )

    def _build_human_cockpit_trend_point(
        self,
        label: str,
        completed: int,
        completion_rate: int,
        quality: int,
    ) -> RuntimeHumanCockpitTrendPoint:
        return RuntimeHumanCockpitTrendPoint(
            label=label,
            completed=max(0, int(completed)),
            completion_rate=max(0, min(100, int(round(completion_rate)))),
            quality=max(0, min(100, int(round(quality)))),
        )

    def _human_cockpit_text_list(self, *values: Any) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            text = self._first_human_cockpit_text(value)
            if text is None or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _latest_human_cockpit_record(
        self,
        records: Sequence[Any] | None,
    ) -> dict[str, Any]:
        latest_record: dict[str, Any] = {}
        latest_sort_key = ""
        for raw in list(records or []):
            record = self._mapping(raw) or {}
            if not record:
                continue
            sort_key = self._first_human_cockpit_text(
                record.get("updated_at"),
                record.get("created_at"),
                record.get("recorded_at"),
                record.get("generated_at"),
            ) or ""
            if not latest_record or sort_key > latest_sort_key:
                latest_record = record
                latest_sort_key = sort_key
        return latest_record

    def _first_human_cockpit_text(self, *values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            mapping = self._mapping(value)
            if mapping:
                nested = self._first_human_cockpit_text(
                    mapping.get("title"),
                    mapping.get("headline"),
                    mapping.get("label"),
                    mapping.get("name"),
                    mapping.get("summary"),
                    mapping.get("description"),
                    mapping.get("detail"),
                    mapping.get("reason"),
                    mapping.get("status"),
                    mapping.get("value"),
                )
                if nested is not None:
                    return nested
                continue
            if isinstance(value, str):
                normalized = value.strip()
                if normalized:
                    return normalized
                continue
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                nested = self._first_human_cockpit_text(*list(value))
                if nested is not None:
                    return nested
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return str(int(value)) if float(value).is_integer() else str(value)
        return None

    def _human_cockpit_status_needs_attention(self, status: Any) -> bool:
        normalized = (self._string(status) or "").strip().lower()
        return any(
            token in normalized
            for token in (
                "blocked",
                "error",
                "failed",
                "pending",
                "open",
                "reviewing",
                "waiting",
                "human-required",
                "waiting-confirm",
            )
        )

    def _human_cockpit_progress_from_status(self, status: Any) -> int:
        normalized = (self._string(status) or "").strip().lower()
        if normalized in {"completed", "done", "approved", "applied"}:
            return 100
        if normalized in {"running", "executing", "active", "claimed"}:
            return 72
        if normalized in {"queued", "assigned", "waiting", "open", "pending"}:
            return 36
        if normalized in {"reviewing", "paused"}:
            return 54
        if normalized in {"blocked", "error", "failed"}:
            return 18
        return 48

    def _human_cockpit_status_label(self, status: Any) -> str:
        normalized = (self._string(status) or "").strip().lower()
        label_map = {
            "running": "进行中",
            "executing": "进行中",
            "active": "进行中",
            "claimed": "进行中",
            "queued": "待开始",
            "assigned": "已派工",
            "waiting": "等待中",
            "pending": "等待中",
            "reviewing": "待处理",
            "paused": "已暂停",
            "blocked": "已卡住",
            "error": "异常",
            "failed": "失败",
            "completed": "已完成",
            "done": "已完成",
            "approved": "已同意",
            "rejected": "已拒绝",
            "idle": "空闲",
            "recorded": "已回收",
        }
        return label_map.get(normalized, self._string(status) or "空闲")

    def _matches_human_cockpit_agent(
        self,
        record: Mapping[str, Any],
        agent_id: str,
    ) -> bool:
        return (
            self._first_human_cockpit_text(
                record.get("owner_agent_id"),
                record.get("agent_id"),
                record.get("owner"),
            )
            == agent_id
            or self._first_human_cockpit_text(record.get("owner_agent_name")) == agent_id
        )

    def _is_main_brain_agent_payload(self, payload: Mapping[str, Any]) -> bool:
        agent_id = (self._string(payload.get("agent_id") or payload.get("id")) or "").strip()
        agent_class = (self._string(payload.get("agent_class")) or "").strip().lower()
        industry_role_id = (
            self._string(payload.get("industry_role_id") or payload.get("role_id")) or ""
        ).strip().lower()
        return (
            agent_id == "copaw-agent-runner"
            or agent_class == "system"
            or industry_role_id == "execution-core"
        )

    def _build_main_brain_operator_signal(
        self,
        key: str,
        payload: Mapping[str, Any],
        *,
        count: int,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "count": count,
            "value": self._string(payload.get("status"))
            or self._string(payload.get("summary"))
            or key,
            "detail": self._string(payload.get("summary")),
            "route": self._string(payload.get("route")),
            "status": self._string(payload.get("status")) or "idle",
        }

    async def _build_main_brain_governance_payload(
        self,
        governance_card: RuntimeOverviewCard,
        app_state: RuntimeCenterAppStateView,
    ) -> RuntimeMainBrainGovernancePayload:
        entry = governance_card.entries[0] if governance_card.entries else None
        meta = dict(governance_card.meta or {})
        handoff = self._mapping(meta.get("handoff")) or {}
        staffing = self._mapping(meta.get("staffing")) or {}
        human_assist = self._mapping(meta.get("human_assist")) or {}
        capability_governance = await self._build_capability_governance_projection(app_state)
        query_runtime_entropy = self._runtime_query_entropy_payload(
            meta.get("query_runtime_entropy"),
        )
        sidecar_memory = self._mapping(meta.get("sidecar_memory")) or {}
        return RuntimeMainBrainGovernancePayload(
            status=entry.status if entry is not None else governance_card.status,
            summary=governance_card.summary,
            route=(entry.route if entry is not None else None)
            or "/api/runtime-center/governance/status",
            pending_decisions=self._int(meta.get("pending_decisions"), 0),
            pending_patches=self._int(meta.get("pending_patches"), 0),
            proposed_patches=self._int(meta.get("proposed_patches"), 0),
            decision_provenance=self._mapping(meta.get("decision_provenance")) or {},
            paused_schedule_count=len(list(meta.get("paused_schedule_ids") or [])),
            emergency_stop_active=bool(meta.get("emergency_stop_active")),
            handoff_active=bool(handoff.get("active")),
            staffing_pending_count=self._int(
                staffing.get("pending_confirmation_count"),
                0,
            ),
            human_assist_blocked_count=self._int(
                human_assist.get("blocked_count"),
                0,
            ),
            host_twin_summary=self._mapping(meta.get("host_twin_summary")) or {},
            capability_governance=capability_governance,
            explain={
                "failure_source": self._string(meta.get("failure_source")),
                "blocked_next_step": self._string(meta.get("blocked_next_step")),
                "remediation_summary": self._string(meta.get("remediation_summary")),
                "decision_provenance": self._mapping(meta.get("decision_provenance")) or {},
                "degraded_components": list(
                    capability_governance.get("degraded_components") or [],
                ),
            },
            query_runtime_entropy=query_runtime_entropy,
            sidecar_memory=sidecar_memory,
        )

    def _build_main_brain_recovery_payload(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> dict[str, Any]:
        summary, source = app_state.resolve_recovery_summary()
        route = "/api/runtime-center/recovery/latest"
        if summary is None:
            return {
                "available": False,
                "status": "unavailable",
                "summary": "Startup recovery summary is not available.",
                "route": route,
                "source": None,
                "detail": {
                    "leases": {},
                    "mailbox": {},
                    "decisions": {},
                    "automation": {},
                },
                "notes": [],
            }
        payload = project_latest_recovery_summary(summary, source=source)
        recovery_payload = {
            "available": True,
            "status": "ready",
            "summary": self._string(payload.get("reason"))
            or "Startup recovery summary is available.",
            "route": route,
            "reason": self._string(payload.get("reason")),
            "recovered_at": self._string(payload.get("recovered_at")),
            "active_schedules": self._int(payload.get("active_schedules"), 0),
            "expired_decisions": self._int(payload.get("expired_decisions"), 0),
            "pending_decisions": self._int(payload.get("pending_decisions"), 0),
            "source": self._string(payload.get("source")),
            "detail": self._mapping(payload.get("detail")) or {},
            "notes": list(payload.get("notes") or []),
        }
        absorption_action_kind = self._string(payload.get("absorption_action_kind"))
        absorption_action_summary = self._string(payload.get("absorption_action_summary"))
        absorption_replan_decision_kind = self._string(
            payload.get("absorption_replan_decision_kind"),
        )
        absorption_human_task_id = self._string(payload.get("absorption_human_task_id"))
        absorption_action_materialized = payload.get("absorption_action_materialized")
        if (
            absorption_action_kind is not None
            or absorption_action_summary is not None
            or absorption_replan_decision_kind is not None
            or absorption_human_task_id is not None
            or bool(absorption_action_materialized)
        ):
            recovery_payload["absorption_action_kind"] = absorption_action_kind
            recovery_payload["absorption_action_summary"] = absorption_action_summary
            recovery_payload["absorption_action_materialized"] = bool(
                absorption_action_materialized,
            )
            recovery_payload["absorption_replan_decision_kind"] = (
                absorption_replan_decision_kind
            )
            recovery_payload["absorption_human_task_id"] = absorption_human_task_id
        return recovery_payload

    async def _build_main_brain_automation_payload(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> dict[str, Any]:
        schedules = await self._call_list_method(
            app_state.state_query_service,
            "list_schedules",
        )
        schedule_entries = [] if schedules is _MISSING else list(schedules)
        normalized_schedule_entries = [
            dict(self._mapping(schedule) or {})
            for schedule in schedule_entries
        ]
        schedule_count = len(schedule_entries)
        active_schedule_count = sum(
            1
            for schedule in schedule_entries
            if (self._string(self._get_field(schedule, "status")) or "").lower() not in {"paused", "deleted"}
        )
        paused_schedule_count = sum(
            1
            for schedule in schedule_entries
            if (self._string(self._get_field(schedule, "status")) or "").lower() == "paused"
        )
        heartbeat_config = get_heartbeat_config()
        heartbeat_payload = heartbeat_config.model_dump(mode="json", by_alias=True)
        manager = app_state.cron_manager
        state_getter = getattr(manager, "get_heartbeat_state", None)
        heartbeat_state = state_getter() if callable(state_getter) else None
        last_status = self._string(getattr(heartbeat_state, "last_status", None))
        heartbeat_status = (
            "paused"
            if not getattr(heartbeat_config, "enabled", False)
            else (last_status or "scheduled")
        )
        automation_loops = self._build_automation_loop_payloads(app_state)
        active_loop_count = sum(
            1 for loop in automation_loops if self._string(loop.get("status")) == "running"
        )
        degraded_loop_count = sum(
            1
            for loop in automation_loops
            if self._string(loop.get("health_status")) == "degraded"
            or self._string(loop.get("status")) == "degraded"
            or self._string(loop.get("loop_phase")) in {"failed", "degraded"}
        )
        supervisor = self._build_actor_supervisor_payload(app_state)
        automation_status = "idle"
        if (
            self._string(supervisor.get("status")) == "degraded"
            or degraded_loop_count > 0
            or heartbeat_status == "error"
        ):
            automation_status = "degraded"
        elif (
            active_schedule_count > 0
            or active_loop_count > 0
            or bool(supervisor.get("running"))
        ):
            automation_status = "active"
        return {
            "status": automation_status,
            "summary": (
                f"{schedule_count} schedule(s) visible; "
                f"{active_loop_count}/{len(automation_loops)} automation loops running; "
                f"supervisor {self._string(supervisor.get('status')) or 'unavailable'}; "
                f"heartbeat {heartbeat_status} every {heartbeat_config.every}."
            ),
            "route": "/api/runtime-center/schedules",
            "schedule_count": schedule_count,
            "active_schedule_count": active_schedule_count,
            "paused_schedule_count": paused_schedule_count,
            "schedules": normalized_schedule_entries,
            "loop_count": len(automation_loops),
            "active_loop_count": active_loop_count,
            "degraded_loop_count": degraded_loop_count,
            "loops": automation_loops,
            "supervisor": supervisor,
            "heartbeat": {
                "route": "/api/runtime-center/heartbeat",
                "status": heartbeat_status,
                "enabled": bool(getattr(heartbeat_config, "enabled", False)),
                "every": getattr(heartbeat_config, "every", None),
                "target": getattr(heartbeat_config, "target", None),
                "activeHours": heartbeat_payload.get("activeHours"),
                "last_run_at": self._serialize_timestamp(
                    getattr(heartbeat_state, "last_run_at", None),
                ),
                "next_run_at": self._serialize_timestamp(
                    getattr(heartbeat_state, "next_run_at", None),
                ),
                "last_error": getattr(heartbeat_state, "last_error", None),
                "query_path": "system:run_operating_cycle",
            },
        }

    def _build_automation_loop_payloads(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> list[dict[str, Any]]:
        return app_state.automation_overview_snapshot()

    def _build_actor_supervisor_payload(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> dict[str, Any]:
        snapshot = app_state.actor_supervisor_snapshot()
        if isinstance(snapshot, dict) and snapshot:
            return snapshot
        return {
            "available": False,
            "status": "unavailable",
            "running": False,
            "poll_interval_seconds": None,
            "active_agent_run_count": 0,
            "blocked_runtime_count": 0,
            "recent_failure_count": 0,
            "last_failure_at": None,
            "last_failure_type": None,
        }

    def _serialize_timestamp(self, value: object) -> str | None:
        isoformat = getattr(value, "isoformat", None)
        if callable(isoformat):
            return isoformat()
        return None

    async def _load_industry_detail_payload(
        self,
        industry_service: Any,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        if industry_service is None or industry_instance_id is None:
            return {}
        getter = getattr(industry_service, "get_instance_detail", None)
        if getter is None:
            return {}
        try:
            detail = getter(industry_instance_id)
        except Exception:
            logger.debug("runtime_center main-brain detail failed", exc_info=True)
            return {}
        return self._model_dump(await self._maybe_await(detail))

    async def _resolve_main_brain_strategy_payload(
        self,
        strategy_service: Any,
        *,
        industry_instance_id: str | None,
        entry: RuntimeOverviewEntry | None,
        entry_meta: Mapping[str, Any],
    ) -> dict[str, Any]:
        _ = entry
        _ = entry_meta
        records = await self._call_list_method(strategy_service, "list_strategies")
        strategies = [] if records is _MISSING else list(records)
        if industry_instance_id is not None:
            strategies = [
                item
                for item in strategies
                if self._string(self._get_field(item, "industry_instance_id", "scope_id"))
                == industry_instance_id
            ] or strategies
        strategy = strategies[0] if strategies else None
        return self._model_dump(strategy)

    def _resolve_main_brain_carrier_payload(
        self,
        *,
        entry: RuntimeOverviewEntry | None,
        entry_meta: Mapping[str, Any],
        industry_detail: Mapping[str, Any],
    ) -> dict[str, Any]:
        _ = entry
        _ = entry_meta
        if not industry_detail:
            return {}
        routes = self._mapping(industry_detail.get("routes")) or {}
        payload = {
            "industry_instance_id": self._string(industry_detail.get("instance_id")),
            "label": self._string(industry_detail.get("label")),
            "summary": self._string(industry_detail.get("summary")),
            "status": self._string(industry_detail.get("status")),
            "owner_scope": self._string(industry_detail.get("owner_scope")),
            "route": self._string(routes.get("runtime_detail")),
        }
        return {key: value for key, value in payload.items() if value is not None}

    def _build_main_brain_environment_payload(
        self,
        governance_card: RuntimeOverviewCard,
    ) -> dict[str, Any]:
        meta = dict(governance_card.meta or {})
        return {
            "route": "/api/runtime-center/governance/status",
            "status": governance_card.status,
            "summary": governance_card.summary,
            "host_twin_summary": self._mapping(meta.get("host_twin_summary")) or {},
            "handoff": self._mapping(meta.get("handoff")) or {},
            "staffing": self._mapping(meta.get("staffing")) or {},
            "human_assist": self._mapping(meta.get("human_assist")) or {},
        }

    def _build_main_brain_industry_route(
        self,
        industry_instance_id: str | None,
    ) -> str | None:
        return self._main_brain_assembly.build_main_brain_industry_route(industry_instance_id)

    def _build_main_brain_report_route(
        self,
        *,
        industry_instance_id: str | None,
        report_id: str | None,
    ) -> str | None:
        return self._main_brain_assembly.build_main_brain_report_route(
            industry_instance_id=industry_instance_id,
            report_id=report_id,
        )

    def _build_main_brain_backlog_route(
        self,
        *,
        industry_instance_id: str | None,
        backlog_item_id: str | None,
    ) -> str | None:
        return self._main_brain_assembly.build_main_brain_backlog_route(
            industry_instance_id=industry_instance_id,
            backlog_item_id=backlog_item_id,
        )

    def _normalize_main_brain_reports(
        self,
        reports: Sequence[Any],
        *,
        industry_instance_id: str | None,
    ) -> list[dict[str, Any]]:
        return self._main_brain_assembly.normalize_main_brain_reports(
            reports,
            industry_instance_id=industry_instance_id,
        )

    def _normalize_main_brain_cognition_finding(
        self,
        payload: Mapping[str, Any],
        *,
        industry_instance_id: str | None,
        report_lookup: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        return self._main_brain_assembly.normalize_main_brain_cognition_finding(
            payload,
            industry_instance_id=industry_instance_id,
            report_lookup=report_lookup,
        )

    def _normalize_main_brain_cognition_conflict(
        self,
        payload: Mapping[str, Any],
        *,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        return self._main_brain_assembly.normalize_main_brain_cognition_conflict(
            payload,
            industry_instance_id=industry_instance_id,
        )

    def _normalize_main_brain_cognition_hole(
        self,
        payload: Mapping[str, Any],
        *,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        return self._main_brain_assembly.normalize_main_brain_cognition_hole(
            payload,
            industry_instance_id=industry_instance_id,
        )

    def _normalize_main_brain_cognition_backlog(
        self,
        payload: Mapping[str, Any],
        *,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        return self._main_brain_assembly.normalize_main_brain_cognition_backlog(
            payload,
            industry_instance_id=industry_instance_id,
        )

    def _build_main_brain_report_cognition_payload(
        self,
        *,
        industry_detail: Mapping[str, Any],
        industry_instance_id: str | None,
        normalized_reports: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return self._main_brain_assembly.build_main_brain_report_cognition_payload(
            industry_detail=industry_detail,
            industry_instance_id=industry_instance_id,
            normalized_reports=normalized_reports,
        )

    def _build_main_brain_report_cognition_signal(
        self,
        cognition: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._main_brain_assembly.build_main_brain_report_cognition_signal(cognition)

    def _build_main_brain_section(
        self,
        card: RuntimeOverviewCard,
    ) -> RuntimeMainBrainSection:
        route = None
        if card.entries:
            route = card.entries[0].route
        meta = dict(card.meta or {})
        if route is None:
            route = self._string(meta.get("route"))
        return RuntimeMainBrainSection(
            count=card.count,
            summary=card.summary,
            route=route,
            entries=[entry.model_dump(mode="json") for entry in card.entries],
            meta=meta,
        )

    def _index_industry_by_instance_id(self, items: list[Any]) -> dict[str, Any]:
        return self._main_brain_assembly.index_industry_by_instance_id(items)
    def _capability_summary_text(self, summary: Mapping[str, Any]) -> str:
        total = self._int(summary.get("total"), 0)
        enabled = self._int(summary.get("enabled"), 0)
        if total == 0:
            return "能力服务已接入，但当前还没有可见的能力挂载。"
        kinds = ", ".join(f"{kind} {count}" for kind, count in self._normalize_int_map(summary.get("by_kind")).items())
        degraded = bool(summary.get("degraded"))
        delta = self._mapping(summary.get("delta")) or {}
        missing_count = self._int(delta.get("missing_capability_count"), 0)
        base = f"统一能力图谱中当前已启用 {enabled}/{total} 个能力挂载。"
        if kinds:
            base += f" 类型分布：{kinds}。"
        if degraded and missing_count > 0:
            base += f" 当前仍有 {missing_count} 个 capability gap 处于待收敛状态。"
        return base

    async def _build_capability_governance_projection(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> dict[str, Any]:
        return await build_capability_governance_projection(self, app_state)

    def _summarize_evidence_card(self, records: list[Any], total_count: int) -> str:
        if total_count <= 0:
            return "证据查询服务已接入，但当前还没有沉淀证据记录。"
        spans = self._counter_meta(records[: self._item_limit], "capability_ref", classifier=self._classify_evidence_kind)
        if not spans:
            return f"证据账本中已存储 {total_count} 条证据记录。"
        highlights = ", ".join(f"{kind} {count}" for kind, count in spans.items())
        return f"证据账本中已存储 {total_count} 条证据记录。最近追踪跨度包括：{highlights}。"

    def _summarize_routines_card(self, payload: Mapping[str, Any], total_count: int) -> str:
        if total_count <= 0:
            return "Routine 服务已接入，但当前还没有正式对象化的执行例行。"
        active = self._int(payload.get("active"), 0)
        degraded = self._int(payload.get("degraded"), 0)
        success_rate = payload.get("recent_success_rate")
        conflicts = self._int(payload.get("resource_conflicts"), 0)
        success_text = (
            f"{round(float(success_rate) * 100, 1):g}%"
            if isinstance(success_rate, (int, float))
            else "未知"
        )
        return (
            f"当前共有 {total_count} 个例行，其中 active {active}、degraded {degraded}；"
            f"最近成功率 {success_text}，最近资源冲突 {conflicts} 次。"
        )

class RuntimeCenterOverviewBuilder:
    """Thin orchestrator that composes grouped Runtime Center card builders."""

    def __init__(self, *, item_limit: int = 5) -> None:
        self._item_limit = item_limit

    async def _build_cards_with_support(
        self,
        support: _RuntimeCenterOverviewCardsSupport,
        app_state: RuntimeCenterAppStateView,
    ) -> list[RuntimeOverviewCard]:
        from .overview_groups import (
            RuntimeCenterControlCardsBuilder,
            RuntimeCenterLearningCardsBuilder,
            RuntimeCenterOperationsCardsBuilder,
        )

        builders = (
            RuntimeCenterOperationsCardsBuilder(item_limit=self._item_limit),
            RuntimeCenterControlCardsBuilder(item_limit=self._item_limit),
            RuntimeCenterLearningCardsBuilder(item_limit=self._item_limit),
        )
        cards: list[RuntimeOverviewCard] = [await support._build_main_brain_card(app_state)]
        for builder in builders:
            cards.extend(await builder.build_cards(app_state))
        return cards

    async def build_cards(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> list[RuntimeOverviewCard]:
        support = _RuntimeCenterOverviewCardsSupport(item_limit=self._item_limit)
        return await self._build_cards_with_support(support, app_state)

    async def build_main_brain_card(
        self,
        app_state: RuntimeCenterAppStateView,
    ) -> RuntimeOverviewCard:
        support = _RuntimeCenterOverviewCardsSupport(item_limit=self._item_limit)
        return await support._build_main_brain_card(app_state)

    async def build_main_brain_payload(
        self,
        app_state: RuntimeCenterAppStateView,
        *,
        buddy_profile_id: str | None = None,
    ) -> RuntimeMainBrainResponse:
        support = _RuntimeCenterOverviewCardsSupport(item_limit=self._item_limit)
        return await support.build_main_brain_payload(
            app_state,
            buddy_profile_id=buddy_profile_id,
        )

    async def build_surface_payload(
        self,
        app_state: RuntimeCenterAppStateView,
        *,
        include_cards: bool = True,
        include_main_brain: bool = True,
        buddy_profile_id: str | None = None,
    ) -> RuntimeCenterSurfaceResponse:
        support = _RuntimeCenterOverviewCardsSupport(item_limit=self._item_limit)
        cards: list[RuntimeOverviewCard] = []
        surface = build_runtime_surface(cards)
        main_brain = None
        automation: Mapping[str, Any] | None = None
        if include_cards:
            cards = await self._build_cards_with_support(support, app_state)
            automation = await support._build_main_brain_automation_payload(app_state)
            surface = support._apply_automation_surface_status(
                surface=build_runtime_surface(cards),
                automation=automation,
            )
        if include_main_brain:
            main_brain = await support.build_main_brain_payload(
                app_state,
                prebuilt_cards=cards if include_cards else None,
                surface=surface if include_cards else None,
                buddy_profile_id=buddy_profile_id,
            )
            if not include_cards and main_brain is not None:
                surface = main_brain.surface
        return RuntimeCenterSurfaceResponse(
            surface=surface,
            cards=cards,
            main_brain=main_brain,
        )


async def build_runtime_capability_governance_projection(
    app_state: RuntimeCenterAppStateView,
    *,
    item_limit: int = 5,
) -> dict[str, Any]:
    support = _RuntimeCenterOverviewCardsSupport(item_limit=item_limit)
    return await support._build_capability_governance_projection(app_state)


__all__ = [
    "RuntimeCenterOverviewBuilder",
    "build_runtime_capability_governance_projection",
]
