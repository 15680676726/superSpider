# -*- coding: utf-8 -*-
"""Runtime Center overview card builder."""
from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from ...utils.runtime_action_links import build_decision_actions, build_patch_actions
from .task_review_projection import build_host_twin_summary
from .models import RuntimeOverviewCard, RuntimeOverviewEntry

logger = logging.getLogger(__name__)

_MISSING = object()


class _RuntimeCenterOverviewCardsSupport:
    """Shared Runtime Center overview card construction helpers."""

    def __init__(self, *, item_limit: int = 5) -> None:
        self._item_limit = item_limit

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
        return RuntimeOverviewCard(
            key="routines",
            title="例行",
            source="routine_service",
            status="state-service",
            count=total,
            summary=self._summarize_routines_card(overview, total),
            entries=entries,
            meta={
                "active": self._int(overview.get("active"), 0),
                "degraded": self._int(overview.get("degraded"), 0),
                "recent_success_rate": overview.get("recent_success_rate"),
                "last_verified_at": self._string(overview.get("last_verified_at")),
                "last_failure_class": self._string(overview.get("last_failure_class")),
                "last_fallback": self._string(overview.get("last_fallback")),
                "resource_conflicts": self._int(overview.get("resource_conflicts"), 0),
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
        strategy_items = await self._call_list_method(
            getattr(app_state, "strategy_memory_service", None),
            "list_strategies",
        )
        strategies = [] if strategy_items is _MISSING else list(strategy_items)
        strategies = [
            item
            for item in strategies
            if (self._string(self._get_field(item, "status")) or "active") in {"active", "reviewing"}
        ] or strategies

        industry_items = await self._call_list_method(
            getattr(app_state, "industry_service", None),
            "list_instances",
        )
        industries = [] if industry_items is _MISSING else list(industry_items)
        industry_by_instance_id = self._index_industry_by_instance_id(industries)

        decision_items = await self._call_list_method(
            getattr(app_state, "state_query_service", None),
            "list_decision_requests",
            "list_decisions",
            "get_decision_requests",
        )
        decisions = [] if decision_items is _MISSING else list(decision_items)

        patch_items = await self._call_list_method(
            self._learning_source(app_state),
            "list_patches",
        )
        patches = [] if patch_items is _MISSING else list(patch_items)

        evidence_items = await self._call_list_method(
            getattr(app_state, "evidence_query_service", None),
            "list_recent_records",
            "list_recent_evidence",
            "list_evidence",
            "list_records",
        )
        evidence = [] if evidence_items is _MISSING else list(evidence_items)

        entries = self._map_main_brain_entries(
            strategies=strategies,
            industries=industries,
            industry_by_instance_id=industry_by_instance_id,
            decision_count=len(decisions),
            patch_count=len(patches),
            evidence_count=len(evidence),
        )
        if not entries:
            return self._unavailable_card(
                "main-brain",
                "Main Brain",
                "Main-brain cockpit is not connected yet.",
            )
        total = len(entries)
        return RuntimeOverviewCard(
            key="main-brain",
            title="Main Brain",
            source="strategy_memory_service",
            status="state-service",
            count=total,
            summary=self._summarize_main_brain_card(entries[0]),
            entries=entries,
            meta=self._main_brain_card_meta(entries[0], total=total),
        )

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
            host_twin_blocked = bool(
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
        current_status = "active" if emergency_active else ("blocked" if runtime_blocked else "idle")
        summary = payload.get("emergency_reason")
        if not summary and handoff.get("active"):
            summary = "Human handoff is active and runtime dispatch is temporarily gated."
        if not summary and int(staffing.get("pending_confirmation_count") or 0) > 0:
            summary = "Staffing confirmation is still pending for active runtime work."
        if not summary and int(human_assist.get("blocked_count") or 0) > 0:
            summary = "Human assist tasks are still blocking automatic continuation."
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
            if normalized_scheduler_action in {"proceed", "ready", "clear", "none"}:
                summary = "Host twin ready"
                if selected_seat_ref:
                    summary += f" on {selected_seat_ref}"
                if seat_selection_policy:
                    summary += f" via {seat_selection_policy}"
                if active_family_keys:
                    summary += "; active app families: " + ", ".join(active_family_keys)
                summary += "."
            else:
                active_count = int(host_twin_summary_payload.get("active_app_family_count") or 0)
                summary = (
                    "Host twin coordination recommends "
                    f"{coordination_action} "
                    f"with {active_count} active app family twin(s)."
                )
        summary = summary or "运行时正在接收新工作。"
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
                "handoff": handoff,
                "staffing": staffing,
                "human_assist": human_assist,
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
            meta={**payload, "host_twin_summary": host_twin_summary_payload},
        )

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
        decision_count: int,
        patch_count: int,
        evidence_count: int,
    ) -> list[RuntimeOverviewEntry]:
        if strategies:
            return self._build_mapped_entries(
                strategies,
                "updated_at",
                "created_at",
                builder=lambda item: self._build_main_brain_entry_from_strategy(
                    item,
                    industry_by_instance_id=industry_by_instance_id,
                    decision_count=decision_count,
                    patch_count=patch_count,
                    evidence_count=evidence_count,
                ),
            )
        if not industries:
            return []
        return self._build_mapped_entries(
            industries,
            "updated_at",
            "created_at",
            builder=lambda item: self._build_main_brain_entry_from_industry(
                item,
                decision_count=decision_count,
                patch_count=patch_count,
                evidence_count=evidence_count,
            ),
        )

    def _build_main_brain_entry_from_strategy(
        self,
        strategy: Any,
        *,
        industry_by_instance_id: Mapping[str, Any],
        decision_count: int,
        patch_count: int,
        evidence_count: int,
    ) -> RuntimeOverviewEntry:
        strategy_id = self._string(self._get_field(strategy, "strategy_id", "id")) or "main-brain"
        industry_instance_id = self._string(
            self._get_field(strategy, "industry_instance_id", "scope_id"),
        )
        industry = industry_by_instance_id.get(industry_instance_id or "")
        stats = self._mapping(self._get_field(industry, "stats")) or {}
        route = "/api/runtime-center/strategy-memory"
        if industry_instance_id:
            route += f"?industry_instance_id={industry_instance_id}"
        return RuntimeOverviewEntry(
            id=strategy_id,
            title=self._string(self._get_field(strategy, "title")) or strategy_id,
            kind="main-brain",
            status=self._string(self._get_field(strategy, "status")) or "active",
            owner=self._string(self._get_field(strategy, "owner_agent_id", "owner_scope")),
            summary=self._string(self._get_field(strategy, "summary", "mission")),
            updated_at=self._dt(self._get_field(strategy, "updated_at", "created_at")),
            route=route,
            meta=self._main_brain_entry_meta(
                strategy_id=strategy_id,
                industry_instance_id=industry_instance_id,
                stats=stats,
                decision_count=decision_count,
                patch_count=patch_count,
                evidence_count=evidence_count,
            ),
        )

    def _build_main_brain_entry_from_industry(
        self,
        industry: Any,
        *,
        decision_count: int,
        patch_count: int,
        evidence_count: int,
    ) -> RuntimeOverviewEntry:
        instance_id = self._string(self._get_field(industry, "instance_id", "id")) or "unknown-industry"
        stats = self._mapping(self._get_field(industry, "stats")) or {}
        routes = self._mapping(self._get_field(industry, "routes")) or {}
        route = self._string(routes.get("runtime_detail")) or f"/api/runtime-center/industry/{instance_id}"
        return RuntimeOverviewEntry(
            id=f"main-brain:{instance_id}",
            title=self._string(self._get_field(industry, "label", "title")) or instance_id,
            kind="main-brain",
            status=self._string(self._get_field(industry, "status")) or "active",
            owner=self._string(self._get_field(industry, "owner_scope")),
            summary=self._string(self._get_field(industry, "summary")),
            updated_at=self._dt(self._get_field(industry, "updated_at", "created_at")),
            route=route,
            meta=self._main_brain_entry_meta(
                strategy_id=None,
                industry_instance_id=instance_id,
                stats=stats,
                decision_count=decision_count,
                patch_count=patch_count,
                evidence_count=evidence_count,
            ),
        )

    def _main_brain_entry_meta(
        self,
        *,
        strategy_id: str | None,
        industry_instance_id: str | None,
        stats: Mapping[str, Any],
        decision_count: int,
        patch_count: int,
        evidence_count: int,
    ) -> dict[str, Any]:
        lane_count = self._int(stats.get("lane_count"), 0)
        backlog_count = self._int(stats.get("backlog_count"), 0)
        cycle_count = self._int(stats.get("cycle_count"), 0)
        assignment_count = self._int(stats.get("assignment_count"), 0)
        report_count = self._int(stats.get("report_count"), 0)
        return {
            "strategy_id": strategy_id,
            "industry_instance_id": industry_instance_id,
            "lane_count": lane_count,
            "backlog_count": backlog_count,
            "cycle_count": cycle_count,
            "assignment_count": assignment_count,
            "report_count": report_count,
            "decision_count": decision_count,
            "patch_count": patch_count,
            "evidence_count": evidence_count,
        }

    def _main_brain_card_meta(
        self,
        first_entry: RuntimeOverviewEntry,
        *,
        total: int,
    ) -> dict[str, Any]:
        entry_meta = dict(first_entry.meta or {})
        return {
            "strategy": {
                "value": first_entry.title,
                "detail": first_entry.summary,
                "route": first_entry.route,
            },
            "lanes": entry_meta.get("lane_count"),
            "current_cycle": entry_meta.get("cycle_count"),
            "assignments": entry_meta.get("assignment_count"),
            "agent_reports": entry_meta.get("report_count"),
            "evidence": entry_meta.get("evidence_count"),
            "decisions": entry_meta.get("decision_count"),
            "patches": entry_meta.get("patch_count"),
            "strategy_id": entry_meta.get("strategy_id"),
            "industry_instance_id": entry_meta.get("industry_instance_id"),
            "visible_count": 1 if total > 0 else 0,
            "truncated": total > 1,
        }

    def _summarize_main_brain_card(self, first_entry: RuntimeOverviewEntry) -> str:
        meta = dict(first_entry.meta or {})
        lane_count = self._int(meta.get("lane_count"), 0)
        assignment_count = self._int(meta.get("assignment_count"), 0)
        report_count = self._int(meta.get("report_count"), 0)
        decision_count = self._int(meta.get("decision_count"), 0)
        patch_count = self._int(meta.get("patch_count"), 0)
        return (
            "Main-brain cockpit tracks "
            f"{lane_count} lane(s), {assignment_count} assignment(s), {report_count} report(s), "
            f"{decision_count} decision(s), and {patch_count} patch(es)."
        )

    def _index_industry_by_instance_id(self, items: list[Any]) -> dict[str, Any]:
        indexed: dict[str, Any] = {}
        for item in items:
            instance_id = self._string(self._get_field(item, "instance_id", "id"))
            if instance_id:
                indexed[instance_id] = item
        return indexed

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


__all__ = ["RuntimeCenterOverviewBuilder"]
