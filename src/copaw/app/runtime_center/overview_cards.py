# -*- coding: utf-8 -*-
"""Runtime Center overview card builder."""
from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from ...config import get_heartbeat_config
from ...kernel.runtime_outcome import build_execution_diagnostics
from ...utils.runtime_action_links import build_decision_actions, build_patch_actions
from .overview_helpers import build_runtime_surface
from .overview_main_brain import RuntimeCenterMainBrainAssembly
from .task_review_projection import (
    build_host_twin_summary,
    derive_host_twin_continuity_state,
    host_twin_summary_ready,
)
from .models import (
    RuntimeMainBrainResponse,
    RuntimeMainBrainSection,
    RuntimeOverviewCard,
    RuntimeOverviewEntry,
)

logger = logging.getLogger(__name__)

_MISSING = object()


class _RuntimeCenterOverviewCardsSupport:
    """Shared Runtime Center overview card construction helpers."""

    def __init__(self, *, item_limit: int = 5) -> None:
        self._item_limit = item_limit
        self._missing_sentinel = _MISSING
        self._main_brain_assembly = RuntimeCenterMainBrainAssembly(self)

    async def build_cards(self, app_state: Any) -> list[RuntimeOverviewCard]:
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

    async def _build_tasks_card(self, app_state: Any) -> RuntimeOverviewCard:
        return await self._state_card(
            app_state=app_state,
            key="tasks",
            title="任务",
            summary="统一状态库中的运行任务。",
            methods=("list_tasks", "get_tasks", "list_runtime_tasks"),
            mapper=self._map_task_entries,
        )

    async def _build_work_contexts_card(self, app_state: Any) -> RuntimeOverviewCard:
        return await self._state_card(
            app_state=app_state,
            key="work-contexts",
            title="工作上下文",
            summary="正式连续工作单元，不再只靠线程 alias 猜测当前到底是哪件事。",
            methods=("list_work_contexts",),
            count_methods=("count_work_contexts",),
            mapper=self._map_work_context_entries,
        )

    async def _build_routines_card(self, app_state: Any) -> RuntimeOverviewCard:
        routine_service = getattr(app_state, "routine_service", None)
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
        return await self._service_card(
            target=getattr(app_state, "agent_profile_service", None),
            key="agents",
            title="智能体",
            source="agent_profile_service",
            summary="由默认配置、覆盖配置与运行态汇总出的可见智能体画像。",
            methods=("list_agents",),
            mapper=self._map_agent_entries,
        )

    async def _build_industry_card(self, app_state: Any) -> RuntimeOverviewCard:
        return await self._service_card(
            target=getattr(app_state, "industry_service", None),
            key="industry",
            title="行业团队",
            source="industry_service",
            summary="正式行业实例、团队蓝图与其关联运行对象。",
            methods=("list_instances",),
            count_methods=("count_instances",),
            mapper=self._map_industry_entries,
        )

    async def _build_main_brain_card(self, app_state: Any) -> RuntimeOverviewCard:
        return await self._main_brain_assembly.build_main_brain_card(app_state)

    async def _build_capabilities_card(self, app_state: Any) -> RuntimeOverviewCard:
        capability_service = getattr(app_state, "capability_service", None)
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

    async def _build_predictions_card(self, app_state: Any) -> RuntimeOverviewCard:
        return await self._service_card(
            target=getattr(app_state, "prediction_service", None),
            key="predictions",
            title="预测",
            source="prediction_service",
            summary="结构化预测案例、受治理建议与自动优化结果。",
            methods=("list_cases",),
            mapper=self._map_prediction_entries,
        )

    async def _build_governance_card(self, app_state: Any) -> RuntimeOverviewCard:
        service = getattr(app_state, "governance_service", None)
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
        sidecar_memory = self._resolve_runtime_contract_sidecar_memory(app_state)
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
                "sidecar_memory": sidecar_memory,
                "failure_source": diagnostics["failure_source"],
                "blocked_next_step": diagnostics["blocked_next_step"],
                "remediation_summary": diagnostics["remediation_summary"],
            },
        )

    def _resolve_runtime_contract_sidecar_memory(self, app_state: Any) -> dict[str, Any] | None:
        for attr_name in ("actor_worker", "actor_supervisor"):
            target = getattr(app_state, attr_name, None)
            runtime_contract = self._mapping(getattr(target, "runtime_contract", None))
            if not runtime_contract:
                continue
            sidecar_memory = self._mapping(runtime_contract.get("sidecar_memory"))
            if sidecar_memory:
                return sidecar_memory
        return None

    async def _build_evidence_card(self, app_state: Any) -> RuntimeOverviewCard:
        target = getattr(app_state, "evidence_query_service", None)
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

    async def _build_decisions_card(self, app_state: Any) -> RuntimeOverviewCard:
        return await self._state_card(
            app_state=app_state,
            key="decisions",
            title="决策",
            summary="DecisionRequestRecord 中的待处理与已解决治理决策。",
            methods=("list_decision_requests", "list_decisions", "get_decision_requests"),
            mapper=self._map_decision_entries,
        )

    async def _build_patches_card(self, app_state: Any) -> RuntimeOverviewCard:
        return await self._service_card(
            target=self._learning_source(app_state),
            key="patches",
            title="补丁",
            source="learning_service",
            summary="学习层产出的补丁提案与应用记录。",
            methods=("list_patches",),
            mapper=self._map_patch_entries,
        )

    async def _build_growth_card(self, app_state: Any) -> RuntimeOverviewCard:
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
        app_state: Any,
        key: str,
        title: str,
        summary: str,
        methods: tuple[str, ...],
        count_methods: tuple[str, ...] = (),
        mapper,
    ) -> RuntimeOverviewCard:
        return await self._service_card(
            target=getattr(app_state, "state_query_service", None),
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

    def _map_task_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "updated_at",
            "created_at",
            builder=self._build_task_entry,
        )

    def _build_task_entry(self, item: Any) -> RuntimeOverviewEntry:
        task_id = self._string(self._get_field(item, "id", "task_id")) or "unknown-task"
        work_context = self._mapping(self._get_field(item, "work_context")) or {}
        return RuntimeOverviewEntry(
            id=task_id,
            title=self._string(self._get_field(item, "title", "name")) or task_id,
            kind=self._string(self._get_field(item, "kind", "task_type")) or "task",
            status=self._string(self._get_field(item, "status")) or "created",
            owner=self._string(self._get_field(item, "owner_agent_id", "owner_role", "owner")),
            summary=self._string(self._get_field(item, "summary", "current_progress_summary", "last_result_summary")),
            updated_at=self._dt(self._get_field(item, "updated_at", "created_at")),
            route=self._string(self._get_field(item, "route")),
            meta={
                "parent_task_id": self._string(self._get_field(item, "parent_task_id")),
                "child_task_count": self._int(
                    self._get_field(item, "child_task_count"),
                    0,
                ),
                "work_context_id": self._string(
                    self._get_field(item, "work_context_id"),
                ),
                "work_context_title": self._string(work_context.get("title")),
                "work_context_key": self._string(
                    work_context.get("context_key"),
                ),
            },
        )

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
            },
        )

    def _map_industry_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "updated_at",
            "created_at",
            builder=self._build_industry_entry,
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

    def _build_main_brain_entry_from_strategy(
        self,
        strategy: Any,
        *,
        industry_by_instance_id: Mapping[str, Any],
    ) -> RuntimeOverviewEntry:
        return self._main_brain_assembly.build_main_brain_entry_from_strategy(
            strategy,
            industry_by_instance_id=industry_by_instance_id,
        )

    def _build_main_brain_entry_from_industry(
        self,
        industry: Any,
    ) -> RuntimeOverviewEntry:
        return self._main_brain_assembly.build_main_brain_entry_from_industry(industry)

    def _main_brain_entry_meta(
        self,
        *,
        strategy_id: str | None,
        industry_instance_id: str | None,
        stats: Mapping[str, Any],
        carrier: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._main_brain_assembly.main_brain_entry_meta(
            strategy_id=strategy_id,
            industry_instance_id=industry_instance_id,
            stats=stats,
            carrier=carrier,
        )

    def _main_brain_card_meta(
        self,
        first_entry: RuntimeOverviewEntry,
        *,
        total: int,
    ) -> dict[str, Any]:
        return self._main_brain_assembly.main_brain_card_meta(first_entry, total=total)

    def _summarize_main_brain_card(self, first_entry: RuntimeOverviewEntry) -> str:
        return self._main_brain_assembly.summarize_main_brain_card(first_entry)

    async def build_main_brain_payload(self, app_state: Any) -> RuntimeMainBrainResponse:
        main_brain_card = await self._build_main_brain_card(app_state)
        evidence_card = await self._build_evidence_card(app_state)
        decisions_card = await self._build_decisions_card(app_state)
        patches_card = await self._build_patches_card(app_state)
        governance_card = await self._build_governance_card(app_state)
        governance = self._build_main_brain_governance_payload(governance_card)
        recovery = self._build_main_brain_recovery_payload(app_state)
        automation = await self._build_main_brain_automation_payload(app_state)
        signals = dict(main_brain_card.meta.get("signals") or {})
        signals.update(
            {
                "governance": self._build_main_brain_operator_signal(
                    "governance",
                    governance,
                    count=self._int(governance.get("pending_patches"), 0)
                    + self._int(governance.get("pending_decisions"), 0)
                    + (1 if governance.get("handoff_active") else 0),
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
            getattr(app_state, "industry_service", None),
            industry_instance_id,
        )
        strategy = await self._resolve_main_brain_strategy_payload(
            getattr(app_state, "strategy_memory_service", None),
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
        signals["report_cognition"] = self._build_main_brain_report_cognition_signal(
            report_cognition,
        )
        signal_map["report_cognition"] = signals["report_cognition"]
        control_chain = [
            signal_map[key]
            for key in control_chain_order + ["report_cognition"]
            if isinstance(signal_map.get(key), dict)
        ]
        return RuntimeMainBrainResponse(
            surface=build_runtime_surface(cards),
            strategy=strategy,
            carrier=carrier,
            lanes=self._normalize_list(industry_detail.get("lanes")),
            cycles=self._normalize_list(industry_detail.get("cycles")),
            backlog=normalized_backlog,
            current_cycle=self._mapping(industry_detail.get("current_cycle")),
            assignments=self._normalize_list(industry_detail.get("assignments")),
            reports=normalized_reports,
            report_cognition=report_cognition,
            environment=self._build_main_brain_environment_payload(governance_card),
            governance=governance,
            recovery=recovery,
            automation=automation,
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
                "governance_summary": governance,
                "recovery_summary": recovery,
                "automation_summary": automation,
            },
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

    def _build_main_brain_governance_payload(
        self,
        governance_card: RuntimeOverviewCard,
    ) -> dict[str, Any]:
        entry = governance_card.entries[0] if governance_card.entries else None
        meta = dict(governance_card.meta or {})
        handoff = self._mapping(meta.get("handoff")) or {}
        staffing = self._mapping(meta.get("staffing")) or {}
        human_assist = self._mapping(meta.get("human_assist")) or {}
        return {
            "status": entry.status if entry is not None else governance_card.status,
            "summary": governance_card.summary,
            "route": (entry.route if entry is not None else None)
            or "/api/runtime-center/governance/status",
            "pending_decisions": self._int(meta.get("pending_decisions"), 0),
            "pending_patches": self._int(meta.get("pending_patches"), 0),
            "proposed_patches": self._int(meta.get("proposed_patches"), 0),
            "paused_schedule_count": len(list(meta.get("paused_schedule_ids") or [])),
            "emergency_stop_active": bool(meta.get("emergency_stop_active")),
            "handoff_active": bool(handoff.get("active")),
            "staffing_pending_count": self._int(
                staffing.get("pending_confirmation_count"),
                0,
            ),
            "human_assist_blocked_count": self._int(
                human_assist.get("blocked_count"),
                0,
            ),
            "host_twin_summary": self._mapping(meta.get("host_twin_summary")) or {},
        }

    def _build_main_brain_recovery_payload(self, app_state: Any) -> dict[str, Any]:
        summary = getattr(app_state, "startup_recovery_summary", None)
        route = "/api/runtime-center/recovery/latest"
        if summary is None:
            return {
                "available": False,
                "status": "unavailable",
                "summary": "Startup recovery summary is not available.",
                "route": route,
                "notes": [],
            }
        payload = self._model_dump(summary)
        return {
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
            "notes": list(payload.get("notes") or []),
        }

    async def _build_main_brain_automation_payload(
        self,
        app_state: Any,
    ) -> dict[str, Any]:
        schedules = await self._call_list_method(
            getattr(app_state, "state_query_service", None),
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
        manager = getattr(app_state, "cron_manager", None)
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
        supervisor = self._build_actor_supervisor_payload(app_state)
        automation_status = "idle"
        if self._string(supervisor.get("status")) == "degraded":
            automation_status = "degraded"
        elif schedule_count > 0 or active_loop_count > 0 or bool(supervisor.get("running")):
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

    def _runtime_task_name(self, task: Any, *, fallback: str) -> str:
        getter = getattr(task, "get_name", None)
        if callable(getter):
            resolved = self._string(getter())
            if resolved is not None:
                return resolved
        return self._string(getattr(task, "name", None)) or fallback

    def _runtime_task_done(self, task: Any) -> bool:
        checker = getattr(task, "done", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                logger.debug("runtime_center task.done() failed", exc_info=True)
        return bool(getattr(task, "done", False))

    def _runtime_task_cancelled(self, task: Any) -> bool:
        checker = getattr(task, "cancelled", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                logger.debug("runtime_center task.cancelled() failed", exc_info=True)
        return bool(getattr(task, "cancelled", False))

    def _runtime_task_status(self, task: Any) -> str:
        if self._runtime_task_cancelled(task):
            return "cancelled"
        if self._runtime_task_done(task):
            return "completed"
        return "running"

    def _build_automation_loop_payloads(self, app_state: Any) -> list[dict[str, Any]]:
        tasks = list(getattr(app_state, "automation_tasks", []) or [])
        snapshot_map: dict[str, dict[str, Any]] = {}
        loop_snapshots = getattr(getattr(app_state, "automation_tasks", None), "loop_snapshots", None)
        if callable(loop_snapshots):
            try:
                raw_snapshots = loop_snapshots()
            except Exception:
                logger.debug("runtime_center automation snapshot read failed", exc_info=True)
                raw_snapshots = {}
            if isinstance(raw_snapshots, Mapping):
                for key, value in raw_snapshots.items():
                    if not isinstance(value, Mapping):
                        continue
                    payload = dict(value)
                    task_name = self._string(payload.get("task_name"))
                    if task_name is not None:
                        snapshot_map[task_name] = payload
                    key_text = self._string(key)
                    if key_text is not None:
                        snapshot_map[key_text] = payload
        payloads: list[dict[str, Any]] = []
        for index, task in enumerate(tasks, start=1):
            name = self._runtime_task_name(
                task,
                fallback=f"automation-loop-{index}",
            )
            lookup_keys = [
                name,
                name.removeprefix("copaw-automation-"),
            ]
            snapshot: dict[str, Any] = {}
            for key in lookup_keys:
                if key in snapshot_map:
                    snapshot = dict(snapshot_map[key])
                    break
            payloads.append(
                {
                    "name": name,
                    "status": self._runtime_task_status(task),
                    **snapshot,
                },
            )
        return payloads

    def _build_actor_supervisor_payload(self, app_state: Any) -> dict[str, Any]:
        supervisor = getattr(app_state, "actor_supervisor", None)
        if supervisor is None:
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

        loop_task = getattr(supervisor, "_loop_task", None)
        running = loop_task is not None and self._runtime_task_status(loop_task) == "running"
        agent_tasks = getattr(supervisor, "_agent_tasks", None)
        active_agent_run_count = 0
        if isinstance(agent_tasks, dict):
            active_agent_run_count = sum(
                1
                for task in agent_tasks.values()
                if self._runtime_task_status(task) == "running"
            )
        blocked_runtime_count = 0
        recent_failure_count = 0
        last_failure_at: str | None = None
        last_failure_type: str | None = None
        runtime_repository = getattr(supervisor, "_runtime_repository", None)
        list_runtimes = getattr(runtime_repository, "list_runtimes", None)
        if callable(list_runtimes):
            try:
                runtimes = list(list_runtimes(limit=None))
            except Exception:
                logger.debug("runtime_center actor supervisor runtime scan failed", exc_info=True)
                runtimes = []
            for runtime in runtimes:
                if self._string(getattr(runtime, "runtime_status", None)) == "blocked":
                    blocked_runtime_count += 1
                metadata = self._mapping(getattr(runtime, "metadata", None))
                failure_at = self._string(metadata.get("supervisor_last_failure_at"))
                if failure_at is not None:
                    recent_failure_count += 1
                    if last_failure_at is None or failure_at > last_failure_at:
                        last_failure_at = failure_at
                        last_failure_type = self._string(
                            metadata.get("supervisor_last_failure_type"),
                        )

        status = "idle"
        if recent_failure_count > 0 or blocked_runtime_count > 0:
            status = "degraded"
        elif running or active_agent_run_count > 0:
            status = "active"

        return {
            "available": True,
            "status": status,
            "running": running,
            "poll_interval_seconds": getattr(supervisor, "_poll_interval_seconds", None),
            "loop_task_name": (
                self._runtime_task_name(loop_task, fallback="copaw-actor-supervisor")
                if loop_task is not None
                else None
            ),
            "active_agent_run_count": active_agent_run_count,
            "blocked_runtime_count": blocked_runtime_count,
            "recent_failure_count": recent_failure_count,
            "last_failure_at": last_failure_at,
            "last_failure_type": last_failure_type,
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
        payload = self._model_dump(strategy)
        if not payload and entry is not None:
            payload = {
                "strategy_id": entry_meta.get("strategy_id"),
                "title": entry.title,
                "summary": entry.summary,
                "status": entry.status,
                "owner_agent_id": entry.owner,
                "route": entry.route,
            }
        else:
            payload.setdefault("strategy_id", entry_meta.get("strategy_id"))
            payload.setdefault("route", entry.route if entry is not None else None)
        return payload

    def _resolve_main_brain_carrier_payload(
        self,
        *,
        entry: RuntimeOverviewEntry | None,
        entry_meta: Mapping[str, Any],
        industry_detail: Mapping[str, Any],
    ) -> dict[str, Any]:
        if industry_detail:
            routes = self._mapping(industry_detail.get("routes")) or {}
            return {
                "industry_instance_id": self._string(
                    industry_detail.get("instance_id") or entry_meta.get("industry_instance_id"),
                ),
                "label": self._string(industry_detail.get("label"))
                or self._string(entry_meta.get("carrier_label")),
                "summary": self._string(industry_detail.get("summary"))
                or (entry.summary if entry is not None else None),
                "status": self._string(industry_detail.get("status"))
                or self._string(entry_meta.get("carrier_status"))
                or (entry.status if entry is not None else None),
                "owner_scope": self._string(industry_detail.get("owner_scope"))
                or (entry.owner if entry is not None else None),
                "route": self._string(routes.get("runtime_detail"))
                or self._string(entry_meta.get("industry_route"))
                or (entry.route if entry is not None else None),
            }
        return {
            "industry_instance_id": self._string(entry_meta.get("industry_instance_id")),
            "label": self._string(entry_meta.get("carrier_label")),
            "summary": entry.summary if entry is not None else None,
            "status": self._string(entry_meta.get("carrier_status"))
            or (entry.status if entry is not None else None),
            "owner_scope": entry.owner if entry is not None else None,
            "route": self._string(entry_meta.get("industry_route"))
            or (entry.route if entry is not None else None),
        }

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

    def _build_industry_entry(self, item: Any) -> RuntimeOverviewEntry:
        instance_id = (
            self._string(self._get_field(item, "instance_id", "id"))
            or "unknown-industry"
        )
        routes = self._mapping(self._get_field(item, "routes")) or {}
        route = self._string(routes.get("runtime_detail")) or f"/api/runtime-center/industry/{instance_id}"
        stats = self._mapping(self._get_field(item, "stats")) or {}
        return RuntimeOverviewEntry(
            id=instance_id,
            title=self._string(self._get_field(item, "label", "title")) or instance_id,
            kind="industry",
            status=self._string(self._get_field(item, "status")) or "draft",
            owner=self._string(self._get_field(item, "owner_scope")),
            summary=self._string(self._get_field(item, "summary")),
            updated_at=self._dt(self._get_field(item, "updated_at", "created_at")),
            route=route,
            meta={
                "lane_count": self._int(stats.get("lane_count"), 0),
                "backlog_count": self._int(stats.get("backlog_count"), 0),
                "cycle_count": self._int(stats.get("cycle_count"), 0),
                "assignment_count": self._int(stats.get("assignment_count"), 0),
                "report_count": self._int(stats.get("report_count"), 0),
                "agent_count": self._int(stats.get("agent_count"), 0),
                "schedule_count": self._int(stats.get("schedule_count"), 0),
            },
        )

    def _map_capability_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "updated_at",
            "created_at",
            builder=self._build_capability_entry,
        )

    def _build_capability_entry(self, item: Any) -> RuntimeOverviewEntry:
        capability_id = self._string(self._get_field(item, "id")) or "unknown-capability"
        return RuntimeOverviewEntry(
            id=capability_id,
            title=self._string(self._get_field(item, "name", "title")) or capability_id,
            kind=self._string(self._get_field(item, "kind")) or "capability",
            status="enabled" if bool(self._get_field(item, "enabled")) else "disabled",
            owner=self._string(self._get_field(item, "provider_ref", "executor_ref")),
            summary=self._string(self._get_field(item, "summary")),
            route=f"/api/capabilities/{capability_id}",
            meta={"risk_level": self._string(self._get_field(item, "risk_level"))},
        )

    def _map_prediction_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return [
            self._build_prediction_entry(item)
            for item in list(items)[: self._item_limit]
        ]

    def _build_prediction_entry(self, item: Any) -> RuntimeOverviewEntry:
        payload = self._mapping(item) or {}
        case = self._mapping(payload.get("case")) or payload
        case_id = self._string(case.get("case_id") or case.get("id")) or "unknown-prediction"
        routes = self._mapping(payload.get("routes")) or {}
        route = self._string(routes.get("detail")) or f"/api/predictions/{case_id}"
        return RuntimeOverviewEntry(
            id=case_id,
            title=self._string(case.get("title")) or case_id,
            kind="prediction",
            status=self._string(case.get("status")) or "open",
            owner=self._string(case.get("owner_agent_id") or case.get("owner_scope")),
            summary=self._string(case.get("summary") or case.get("question")),
            updated_at=self._dt(case.get("updated_at") or case.get("created_at")),
            route=route,
            meta={
                "confidence": case.get("overall_confidence"),
                "recommendations": payload.get("recommendation_count"),
                "reviews": payload.get("review_count"),
                "pending_decisions": payload.get("pending_decision_count"),
            },
        )

    def _map_evidence_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "created_at",
            "updated_at",
            builder=self._build_evidence_entry,
        )

    def _build_evidence_entry(self, item: Any) -> RuntimeOverviewEntry:
        record_id = self._string(self._get_field(item, "id")) or "unknown-evidence"
        capability_ref = self._string(self._get_field(item, "capability_ref"))
        return RuntimeOverviewEntry(
            id=record_id,
            title=self._string(self._get_field(item, "action_summary", "summary", "title")) or record_id,
            kind=self._classify_evidence_kind(capability_ref),
            status=self._string(self._get_field(item, "status", "risk_level")) or "recorded",
            owner=self._string(self._get_field(item, "actor_ref", "actor", "owner")),
            summary=self._string(self._get_field(item, "result_summary", "description")),
            updated_at=self._dt(self._get_field(item, "created_at", "updated_at")),
            route=f"/api/runtime-center/evidence/{record_id}",
            meta={
                "capability_ref": capability_ref,
                "environment_ref": self._string(self._get_field(item, "environment_ref")),
            },
        )

    def _map_decision_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "resolved_at",
            "created_at",
            builder=self._build_decision_entry,
        )

    def _build_decision_entry(self, item: Any) -> RuntimeOverviewEntry:
        decision_id = self._string(self._get_field(item, "id")) or "unknown-decision"
        governance_route = self._string(self._get_field(item, "governance_route", "route")) or (
            f"/api/runtime-center/decisions/{decision_id}"
        )
        route = self._string(self._get_field(item, "preferred_route")) or governance_route
        status = self._string(self._get_field(item, "status")) or "open"
        actions = self._string_map(self._get_field(item, "actions"))
        if status in {"open", "reviewing"}:
            actions = {
                **build_decision_actions(decision_id, status=status),
                **actions,
            }
        return RuntimeOverviewEntry(
            id=decision_id,
            title=self._string(self._get_field(item, "summary", "title", "decision_type")) or decision_id,
            kind="decision",
            status=status,
            owner=self._string(self._get_field(item, "requested_by", "owner")),
            summary=self._string(self._get_field(item, "resolution", "risk_level")),
            updated_at=self._dt(self._get_field(item, "resolved_at", "created_at")),
            route=route,
            actions=actions,
            meta={
                "risk_level": self._string(self._get_field(item, "risk_level")),
                "governance_route": governance_route,
                "chat_route": self._string(self._get_field(item, "chat_route")),
                "requires_human_confirmation": bool(
                    self._get_field(item, "requires_human_confirmation"),
                ),
            },
        )

    def _map_patch_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "applied_at",
            "created_at",
            builder=self._build_patch_entry,
        )

    def _build_patch_entry(self, item: Any) -> RuntimeOverviewEntry:
        patch_id = self._string(self._get_field(item, "id")) or "unknown-patch"
        status = self._string(self._get_field(item, "status")) or "proposed"
        risk_level = self._string(self._get_field(item, "risk_level")) or "auto"
        return RuntimeOverviewEntry(
            id=patch_id,
            title=self._string(self._get_field(item, "title")) or patch_id,
            kind=self._string(self._get_field(item, "kind")) or "patch",
            status=status,
            owner=self._string(self._get_field(item, "applied_by", "proposal_id")),
            summary=self._string(self._get_field(item, "description", "diff_summary")),
            updated_at=self._dt(self._get_field(item, "applied_at", "created_at")),
            route=f"/api/runtime-center/learning/patches/{patch_id}",
            actions=self._patch_actions(patch_id, status, risk_level),
            meta={
                "risk_level": risk_level,
                "goal_id": self._string(self._get_field(item, "goal_id")),
                "task_id": self._string(self._get_field(item, "task_id")),
                "agent_id": self._string(self._get_field(item, "agent_id")),
            },
        )

    def _map_growth_entries(self, items: list[Any]) -> list[RuntimeOverviewEntry]:
        return self._build_mapped_entries(
            items,
            "created_at",
            builder=self._build_growth_entry,
        )

    def _build_growth_entry(self, item: Any) -> RuntimeOverviewEntry:
        event_id = self._string(self._get_field(item, "id")) or "unknown-growth"
        agent_id = self._string(self._get_field(item, "agent_id"))
        return RuntimeOverviewEntry(
            id=event_id,
            title=self._string(self._get_field(item, "description")) or event_id,
            kind=self._string(self._get_field(item, "change_type")) or "growth",
            status=self._string(self._get_field(item, "result")) or "recorded",
            owner=agent_id,
            summary=self._string(self._get_field(item, "source_patch_id", "source_evidence_id")),
            updated_at=self._dt(self._get_field(item, "created_at")),
            route=f"/api/runtime-center/learning/growth/{event_id}",
            meta={
                "agent_id": agent_id,
                "goal_id": self._string(self._get_field(item, "goal_id")),
                "task_id": self._string(self._get_field(item, "task_id")),
                "source_patch_id": self._string(self._get_field(item, "source_patch_id")),
            },
        )

    def _learning_source(self, app_state: Any) -> Any:
        return getattr(app_state, "learning_service", None) or getattr(app_state, "learning_engine", None)

    def _sorted(self, items: list[Any], *field_names: str) -> list[Any]:
        return sorted(
            items,
            key=lambda item: self._dt(self._get_field(item, *field_names)) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[: self._item_limit]

    def _counter_meta(self, items: list[Any], field_name: str, *, classifier=None) -> dict[str, int]:
        from collections import Counter

        counter = Counter()
        for item in items:
            raw = self._get_field(item, field_name)
            key = classifier(raw) if classifier is not None else self._string(raw)
            counter[key or "unknown"] += 1
        return dict(sorted(counter.items()))

    def _classify_evidence_kind(self, capability_ref: Any) -> str:
        lowered = (self._string(capability_ref) or "").lower()
        if not lowered:
            return "evidence"
        if lowered.startswith("tool:execute_shell_command") or "shell" in lowered:
            return "shell"
        if lowered.startswith("tool:browser_use") or "browser" in lowered:
            return "browser"
        if lowered.startswith(("tool:read_file", "tool:write_file", "tool:edit_file")) or "file" in lowered:
            return "file"
        if lowered.startswith("mcp:"):
            return "mcp"
        if lowered.startswith("learning:"):
            return "learning"
        return "evidence"

    def _normalize_capability_summary(self, summary: Any, mounts: list[Any]) -> dict[str, Any]:
        payload = self._mapping(summary)
        if payload is not None:
            return {
                "total": self._int(payload.get("total"), len(mounts)),
                "enabled": self._int(payload.get("enabled"), self._enabled_count(mounts)),
                "by_kind": self._normalize_int_map(payload.get("by_kind")) or self._counter_meta(mounts, "kind"),
            }
        return {
            "total": len(mounts),
            "enabled": self._enabled_count(mounts),
            "by_kind": self._counter_meta(mounts, "kind"),
        }

    def _capability_summary_text(self, summary: Mapping[str, Any]) -> str:
        total = self._int(summary.get("total"), 0)
        enabled = self._int(summary.get("enabled"), 0)
        if total == 0:
            return "能力服务已接入，但当前还没有可见的能力挂载。"
        kinds = ", ".join(f"{kind} {count}" for kind, count in self._normalize_int_map(summary.get("by_kind")).items())
        return f"统一能力图谱中当前已启用 {enabled}/{total} 个能力挂载。" + (f" 类型分布：{kinds}。" if kinds else "")

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

    def _patch_actions(self, patch_id: str, status: str, risk_level: str) -> dict[str, str]:
        return build_patch_actions(
            patch_id,
            status=status,
            risk_level=risk_level,
        )

    def _enabled_count(self, mounts: list[Any]) -> int:
        return sum(1 for mount in mounts if bool(self._get_field(mount, "enabled")))

    def _get_field(self, item: Any, *names: str) -> Any:
        mapping = self._mapping(item)
        if mapping is not None:
            for name in names:
                value = mapping.get(name)
                if value is not None:
                    return value
            return None
        for name in names:
            value = getattr(item, name, None)
            if value is not None:
                return value
        return None

    def _mapping(self, item: Any) -> Mapping[str, Any] | None:
        if isinstance(item, Mapping):
            return item
        if hasattr(item, "model_dump"):
            try:
                dumped = item.model_dump(mode="python")
            except TypeError:
                dumped = item.model_dump()
            if isinstance(dumped, Mapping):
                return dumped
        if isinstance(item, SimpleNamespace):
            return vars(item)
        return None

    def _dt(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None

    def _string(self, value: Any) -> str | None:
        if value is None:
            return None
        return value if isinstance(value, str) else str(value)

    def _strings(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if not isinstance(value, Sequence):
            return []
        return [text for text in (self._string(item) for item in value) if text is not None]

    def _string_map(self, value: Any) -> dict[str, str]:
        if not isinstance(value, Mapping):
            return {}
        return {str(key): str(raw) for key, raw in value.items() if raw is not None}

    def _int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _normalize_int_map(self, value: Any) -> dict[str, int]:
        if not isinstance(value, Mapping):
            return {}
        normalized: dict[str, int] = {}
        for key, raw in value.items():
            try:
                normalized[str(key)] = int(raw)
            except (TypeError, ValueError):
                continue
        return dict(sorted(normalized.items()))

class RuntimeCenterOverviewBuilder:
    """Thin orchestrator that composes grouped Runtime Center card builders."""

    def __init__(self, *, item_limit: int = 5) -> None:
        self._item_limit = item_limit

    async def build_cards(self, app_state: Any) -> list[RuntimeOverviewCard]:
        from .overview_groups import (
            RuntimeCenterControlCardsBuilder,
            RuntimeCenterLearningCardsBuilder,
            RuntimeCenterOperationsCardsBuilder,
        )

        support = _RuntimeCenterOverviewCardsSupport(item_limit=self._item_limit)
        builders = (
            RuntimeCenterOperationsCardsBuilder(item_limit=self._item_limit),
            RuntimeCenterControlCardsBuilder(item_limit=self._item_limit),
            RuntimeCenterLearningCardsBuilder(item_limit=self._item_limit),
        )
        cards: list[RuntimeOverviewCard] = [await support._build_main_brain_card(app_state)]
        for builder in builders:
            cards.extend(await builder.build_cards(app_state))
        return cards

    async def build_main_brain_card(self, app_state: Any) -> RuntimeOverviewCard:
        support = _RuntimeCenterOverviewCardsSupport(item_limit=self._item_limit)
        return await support._build_main_brain_card(app_state)

    async def build_main_brain_payload(self, app_state: Any) -> RuntimeMainBrainResponse:
        support = _RuntimeCenterOverviewCardsSupport(item_limit=self._item_limit)
        return await support.build_main_brain_payload(app_state)


__all__ = ["RuntimeCenterOverviewBuilder"]
