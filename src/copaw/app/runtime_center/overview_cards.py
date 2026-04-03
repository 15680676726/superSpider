# -*- coding: utf-8 -*-
"""Runtime Center overview card builder."""
from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from ...config import get_heartbeat_config
from ...kernel.runtime_outcome import build_execution_diagnostics
from .overview_entry_builders import _RuntimeCenterOverviewEntryBuildersMixin
from .overview_helpers import build_runtime_surface
from .overview_main_brain import RuntimeCenterMainBrainAssembly
from .recovery_projection import project_latest_recovery_summary
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


class _RuntimeCenterOverviewCardsSupport(_RuntimeCenterOverviewEntryBuildersMixin):
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
        query_runtime_entropy = self._resolve_query_runtime_entropy(app_state)
        sidecar_memory = self._resolve_governance_sidecar_memory(
            query_runtime_entropy=query_runtime_entropy,
            app_state=app_state,
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
                "query_runtime_entropy": query_runtime_entropy,
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
                "query_runtime_entropy": query_runtime_entropy,
                "sidecar_memory": sidecar_memory,
                "failure_source": diagnostics["failure_source"],
                "blocked_next_step": diagnostics["blocked_next_step"],
                "remediation_summary": diagnostics["remediation_summary"],
            },
        )

    def _resolve_query_runtime_entropy(self, app_state: Any) -> dict[str, Any] | None:
        service = getattr(app_state, "query_execution_service", None)
        getter = getattr(service, "get_query_runtime_entropy_contract", None)
        if not callable(getter):
            return None
        try:
            payload = getter()
        except Exception:
            logger.debug("runtime_center query runtime entropy lookup failed", exc_info=True)
            return None
        entropy = self._mapping(payload)
        return entropy or None

    def _resolve_governance_sidecar_memory(
        self,
        *,
        query_runtime_entropy: dict[str, Any] | None,
        app_state: Any,
    ) -> dict[str, Any] | None:
        sidecar_memory = self._mapping((query_runtime_entropy or {}).get("sidecar_memory"))
        if sidecar_memory:
            return sidecar_memory
        return self._resolve_runtime_contract_sidecar_memory(app_state)

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

    async def build_main_brain_payload(self, app_state: Any) -> RuntimeMainBrainResponse:
        main_brain_card = await self._build_main_brain_card(app_state)
        evidence_card = await self._build_evidence_card(app_state)
        decisions_card = await self._build_decisions_card(app_state)
        patches_card = await self._build_patches_card(app_state)
        governance_card = await self._build_governance_card(app_state)
        governance = await self._build_main_brain_governance_payload(
            governance_card,
            app_state,
        )
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

    async def _build_main_brain_governance_payload(
        self,
        governance_card: RuntimeOverviewCard,
        app_state: Any,
    ) -> dict[str, Any]:
        entry = governance_card.entries[0] if governance_card.entries else None
        meta = dict(governance_card.meta or {})
        handoff = self._mapping(meta.get("handoff")) or {}
        staffing = self._mapping(meta.get("staffing")) or {}
        human_assist = self._mapping(meta.get("human_assist")) or {}
        capability_governance = await self._build_capability_governance_projection(app_state)
        return {
            "status": entry.status if entry is not None else governance_card.status,
            "summary": governance_card.summary,
            "route": (entry.route if entry is not None else None)
            or "/api/runtime-center/governance/status",
            "pending_decisions": self._int(meta.get("pending_decisions"), 0),
            "pending_patches": self._int(meta.get("pending_patches"), 0),
            "proposed_patches": self._int(meta.get("proposed_patches"), 0),
            "decision_provenance": self._mapping(meta.get("decision_provenance")) or {},
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
            "capability_governance": capability_governance,
            "explain": {
                "failure_source": self._string(meta.get("failure_source")),
                "blocked_next_step": self._string(meta.get("blocked_next_step")),
                "remediation_summary": self._string(meta.get("remediation_summary")),
                "decision_provenance": self._mapping(meta.get("decision_provenance")) or {},
                "degraded_components": list(
                    capability_governance.get("degraded_components") or [],
                ),
            },
        }

    def _build_main_brain_recovery_payload(self, app_state: Any) -> dict[str, Any]:
        summary = getattr(app_state, "latest_recovery_report", None)
        source = "latest"
        if summary is None:
            summary = getattr(app_state, "startup_recovery_summary", None)
            source = "startup"
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
            "source": self._string(payload.get("source")),
            "detail": self._mapping(payload.get("detail")) or {},
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
        app_state: Any,
    ) -> dict[str, Any]:
        capability_service = getattr(app_state, "capability_service", None)
        if capability_service is None:
            return {
                "status": "unavailable",
                "degraded": False,
                "degraded_components": [],
                "delta": {},
            }
        mounts = await self._call_list_method(capability_service, "list_capabilities")
        if mounts is _MISSING:
            mounts = []
        summary = self._normalize_capability_summary(
            await self._call_optional_method(capability_service, "summarize"),
            mounts,
        )
        skills = list(
            await self._call_optional_method(
                capability_service,
                "list_skill_specs",
            )
            or []
        )
        mcps = list(
            await self._call_optional_method(
                capability_service,
                "list_mcp_client_infos",
            )
            or []
        )
        prediction_service = getattr(app_state, "prediction_service", None)
        optimization_overview = {}
        get_runtime_capability_optimization_overview = getattr(
            prediction_service,
            "get_runtime_capability_optimization_overview",
            None,
        )
        if callable(get_runtime_capability_optimization_overview):
            optimization_overview = self._mapping(
                get_runtime_capability_optimization_overview(),
            ) or {}
        delta = self._mapping(optimization_overview.get("summary")) or {}
        package_bound_skill_count = sum(
            1
            for item in skills
            if self._string(self._get_field(item, "package_ref"))
        )
        package_bound_mcp_count = sum(
            1
            for item in mcps
            if self._string(self._get_field(item, "package_ref"))
        )
        governance_route = "/api/runtime-center/governance/capability-optimizations"
        degraded_components: list[dict[str, Any]] = []
        missing_capability_count = self._int(delta.get("missing_capability_count"), 0)
        underperforming_capability_count = self._int(
            delta.get("underperforming_capability_count"),
            0,
        )
        waiting_confirm_count = self._int(delta.get("waiting_confirm_count"), 0)
        manual_only_count = self._int(delta.get("manual_only_count"), 0)
        if missing_capability_count > 0:
            degraded_components.append(
                {
                    "component": "capability-coverage",
                    "status": "degraded",
                    "summary": (
                        f"{missing_capability_count} 个 capability gap 仍待补齐或治理决策。"
                    ),
                    "route": governance_route,
                },
            )
        if underperforming_capability_count > 0:
            degraded_components.append(
                {
                    "component": "capability-performance",
                    "status": "degraded",
                    "summary": (
                        f"{underperforming_capability_count} underperforming capability recommendations need operator review."
                    ),
                    "route": governance_route,
                },
            )
        if waiting_confirm_count > 0:
            degraded_components.append(
                {
                    "component": "capability-approval-backlog",
                    "status": "degraded",
                    "summary": (
                        f"{waiting_confirm_count} capability actions are waiting for confirmation."
                    ),
                    "route": governance_route,
                },
            )
        if manual_only_count > 0:
            degraded_components.append(
                {
                    "component": "capability-manual-operations",
                    "status": "degraded",
                    "summary": (
                        f"{manual_only_count} capability actions are still manual-only."
                    ),
                    "route": governance_route,
                },
            )
        return {
            "status": "degraded" if degraded_components else "ready",
            "route": governance_route,
            "total": self._int(summary.get("total"), len(mounts)),
            "enabled": self._int(summary.get("enabled"), self._enabled_count(mounts)),
            "by_kind": self._normalize_int_map(summary.get("by_kind")),
            "by_source": self._normalize_int_map(summary.get("by_source")),
            "skill_count": len(skills),
            "enabled_skill_count": sum(
                1 for item in skills if bool(self._get_field(item, "enabled"))
            ),
            "package_bound_skill_count": package_bound_skill_count,
            "mcp_count": len(mcps),
            "enabled_mcp_count": sum(
                1 for item in mcps if bool(self._get_field(item, "enabled"))
            ),
            "package_bound_mcp_count": package_bound_mcp_count,
            "delta": {
                "total_items": self._int(delta.get("total_items"), 0),
                "history_count": self._int(delta.get("history_count"), 0),
                "case_count": self._int(delta.get("case_count"), 0),
                "missing_capability_count": missing_capability_count,
                "underperforming_capability_count": underperforming_capability_count,
                "trial_count": self._int(delta.get("trial_count"), 0),
                "rollout_count": self._int(delta.get("rollout_count"), 0),
                "retire_count": self._int(delta.get("retire_count"), 0),
                "waiting_confirm_count": waiting_confirm_count,
                "manual_only_count": manual_only_count,
                "executed_count": self._int(delta.get("executed_count"), 0),
                "actionable_count": self._int(delta.get("actionable_count"), 0),
            },
            "degraded": bool(degraded_components),
            "degraded_components": degraded_components,
        }

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


async def build_runtime_capability_governance_projection(
    app_state: Any,
    *,
    item_limit: int = 5,
) -> dict[str, Any]:
    support = _RuntimeCenterOverviewCardsSupport(item_limit=item_limit)
    return await support._build_capability_governance_projection(app_state)


__all__ = [
    "RuntimeCenterOverviewBuilder",
    "build_runtime_capability_governance_projection",
]
