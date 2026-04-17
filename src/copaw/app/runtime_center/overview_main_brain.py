# -*- coding: utf-8 -*-
"""Runtime Center main-brain card and cognition assembly helpers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

from .models import RuntimeOverviewCard, RuntimeOverviewEntry

class RuntimeCenterMainBrainAssembly:
    """Extracted main-brain/card-cognition assembly that delegates to overview support helpers."""

    def __init__(self, support: Any) -> None:
        self._support = support

    def __getattr__(self, name: str) -> Any:
        return getattr(self._support, name)

    def _is_missing(self, value: Any) -> bool:
        return value is getattr(self._support, "_missing_sentinel", None)

    def _latest_timed_mapping(
        self,
        items: Sequence[Any] | None,
    ) -> dict[str, Any]:
        latest_item: dict[str, Any] = {}
        latest_sort_key = ""
        for raw in list(items or []):
            payload = self._mapping(raw)
            if not payload:
                continue
            sort_key = self._string(
                payload.get("updated_at")
                or payload.get("created_at")
                or payload.get("recorded_at")
                or payload.get("generated_at")
            ) or ""
            if not latest_item or sort_key > latest_sort_key:
                latest_item = dict(payload)
                latest_sort_key = sort_key
        return latest_item

    async def build_main_brain_card(self, app_state: Any) -> RuntimeOverviewCard:
        exception_absorption = self.resolve_exception_absorption_meta(app_state)
        strategy_items = await self._call_list_method(
            getattr(app_state, "strategy_memory_service", None),
            "list_strategies",
        )
        strategies = [] if self._is_missing(strategy_items) else list(strategy_items)
        strategies = [
            item
            for item in strategies
            if (self._string(self._get_field(item, "status")) or "active") in {"active", "reviewing"}
        ] or strategies

        industry_items = await self._call_list_method(
            getattr(app_state, "industry_service", None),
            "list_instances",
        )
        industries = [] if self._is_missing(industry_items) else list(industry_items)
        industry_by_instance_id = self.index_industry_by_instance_id(industries)

        entries = self.map_main_brain_entries(
            strategies=strategies,
            industries=industries,
            industry_by_instance_id=industry_by_instance_id,
            exception_absorption=exception_absorption,
        )
        if not entries:
            return self._unavailable_card(
                "main-brain",
                "主脑",
                "主脑驾驶舱暂未接入。",
            )
        total = len(entries)
        source_values: list[str] = []
        if not self._is_missing(strategy_items):
            source_values.append("strategy_memory_service")
        if not self._is_missing(industry_items):
            source_values.append("industry_service")
        combined_source = ",".join(dict.fromkeys(source_values)) or "unavailable"
        return RuntimeOverviewCard(
            key="main-brain",
            title="主脑",
            source=combined_source,
            status="state-service",
            count=total,
            summary=self.summarize_main_brain_card(entries[0]),
            entries=entries,
            meta=self.main_brain_card_meta(entries[0], total=total),
        )

    def map_main_brain_entries(
        self,
        *,
        strategies: list[Any],
        industries: list[Any],
        industry_by_instance_id: Mapping[str, Any],
        exception_absorption: Mapping[str, Any] | None = None,
    ) -> list[RuntimeOverviewEntry]:
        if strategies:
            return self._build_mapped_entries(
                strategies,
                "updated_at",
                "created_at",
                builder=lambda item: self.build_main_brain_entry_from_strategy(
                    item,
                    industry_by_instance_id=industry_by_instance_id,
                    exception_absorption=exception_absorption,
                ),
            )
        if not industries:
            return []
        return self._build_mapped_entries(
            industries,
            "updated_at",
            "created_at",
            builder=lambda item: self.build_main_brain_entry_from_industry(
                item,
                exception_absorption=exception_absorption,
            ),
        )

    def build_main_brain_entry_from_strategy(
        self,
        strategy: Any,
        *,
        industry_by_instance_id: Mapping[str, Any],
        exception_absorption: Mapping[str, Any] | None = None,
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
            meta=self.main_brain_entry_meta(
                strategy_id=strategy_id,
                industry_instance_id=industry_instance_id,
                stats=stats,
                carrier=self._mapping(industry) or {},
                exception_absorption=exception_absorption,
            ),
        )

    def build_main_brain_entry_from_industry(
        self,
        industry: Any,
        *,
        exception_absorption: Mapping[str, Any] | None = None,
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
            meta=self.main_brain_entry_meta(
                strategy_id=None,
                industry_instance_id=instance_id,
                stats=stats,
                carrier=self._mapping(industry) or {},
                exception_absorption=exception_absorption,
            ),
        )

    def main_brain_entry_meta(
        self,
        *,
        strategy_id: str | None,
        industry_instance_id: str | None,
        stats: Mapping[str, Any],
        carrier: Mapping[str, Any],
        exception_absorption: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        lane_count = self._int(stats.get("lane_count"), 0)
        backlog_count = self._int(stats.get("backlog_count"), 0)
        cycle_count = self._int(stats.get("cycle_count"), 0)
        assignment_count = self._int(stats.get("assignment_count"), 0)
        report_count = self._int(stats.get("report_count"), 0)
        decision_count = self._int(stats.get("decision_count"), 0)
        patch_count = self._int(stats.get("patch_count"), 0)
        evidence_count = self._int(stats.get("evidence_count"), 0)
        carrier_route = self._string((self._mapping(carrier.get("routes")) or {}).get("runtime_detail"))
        unconsumed_report_count = self._int(
            stats.get("unconsumed_report_count")
            or stats.get("pending_report_count")
            or stats.get("report_unconsumed_count"),
            0,
        )
        payload = {
            "strategy_id": strategy_id,
            "industry_instance_id": industry_instance_id,
            "industry_route": carrier_route
            or (f"/api/runtime-center/industry/{industry_instance_id}" if industry_instance_id else None),
            "carrier_label": self._string(carrier.get("label") or carrier.get("title") or industry_instance_id),
            "carrier_status": self._string(carrier.get("status")),
            "lane_count": lane_count,
            "backlog_count": backlog_count,
            "cycle_count": cycle_count,
            "assignment_count": assignment_count,
            "report_count": report_count,
            "unconsumed_report_count": unconsumed_report_count,
            "decision_count": decision_count,
            "patch_count": patch_count,
            "evidence_count": evidence_count,
            "current_cycle_title": self._string(stats.get("current_cycle_title")),
            "current_cycle_status": self._string(stats.get("current_cycle_status")),
            "current_focus_count": self._int(stats.get("current_focus_count"), 0),
            "next_cycle_due_at": self._string(stats.get("next_cycle_due_at")),
        }
        normalized_exception_absorption = self._mapping(exception_absorption) or {}
        if normalized_exception_absorption:
            payload["exception_absorption"] = normalized_exception_absorption
        return payload

    def resolve_exception_absorption_meta(self, app_state: Any) -> dict[str, Any]:
        snapshot_getter = getattr(app_state, "actor_supervisor_snapshot", None)
        snapshot = snapshot_getter() if callable(snapshot_getter) else None
        if snapshot is None:
            actor_supervisor = getattr(app_state, "actor_supervisor", None)
            supervisor_snapshot = getattr(actor_supervisor, "snapshot", None)
            snapshot = supervisor_snapshot() if callable(supervisor_snapshot) else None
        payload = self._mapping(snapshot) or {}
        if not payload:
            return {}
        case_count = self._int(payload.get("absorption_case_count"), 0)
        human_required_case_count = self._int(payload.get("human_required_case_count"), 0)
        summary = self._string(payload.get("absorption_summary"))
        status = "clear"
        if human_required_case_count > 0:
            status = "human-required"
        elif case_count > 0:
            status = "absorbing"
        return {
            "status": status,
            "case_count": case_count,
            "human_required_case_count": human_required_case_count,
            "summary": summary,
            "case_counts": self._mapping(payload.get("absorption_case_counts")) or {},
            "recovery_counts": self._mapping(payload.get("absorption_recovery_counts")) or {},
        }

    def main_brain_card_meta(
        self,
        first_entry: RuntimeOverviewEntry,
        *,
        total: int,
    ) -> dict[str, Any]:
        entry_meta = dict(first_entry.meta or {})
        industry_route = self._string(entry_meta.get("industry_route"))
        lane_count = self._int(entry_meta.get("lane_count"), 0)
        backlog_count = self._int(entry_meta.get("backlog_count"), 0)
        cycle_count = self._int(entry_meta.get("cycle_count"), 0)
        assignment_count = self._int(entry_meta.get("assignment_count"), 0)
        report_count = self._int(entry_meta.get("report_count"), 0)
        unconsumed_report_count = self._int(entry_meta.get("unconsumed_report_count"), 0)
        evidence_count = self._int(entry_meta.get("evidence_count"), 0)
        decision_count = self._int(entry_meta.get("decision_count"), 0)
        patch_count = self._int(entry_meta.get("patch_count"), 0)
        exception_absorption = self._mapping(entry_meta.get("exception_absorption")) or {}
        cycle_title = self._string(entry_meta.get("current_cycle_title"))
        cycle_status = self._string(entry_meta.get("current_cycle_status")) or "active"
        cycle_focus_count = self._int(entry_meta.get("current_focus_count"), 0)
        next_cycle_due_at = self._string(entry_meta.get("next_cycle_due_at"))
        strategy_signal = {
            "value": first_entry.title,
            "detail": first_entry.summary,
            "route": first_entry.route,
            "status": first_entry.status,
        }
        signals = {
            "carrier": {
                "key": "carrier",
                "value": self._string(entry_meta.get("carrier_label")) or self._string(first_entry.owner) or "主脑载体",
                "detail": self._string(first_entry.owner) or first_entry.summary,
                "route": industry_route or first_entry.route,
                "status": self._string(entry_meta.get("carrier_status")) or first_entry.status,
            },
            "strategy": {"key": "strategy", **strategy_signal},
            "lanes": {
                "key": "lanes",
                "count": lane_count,
                "detail": f"当前运行驾驶舱里可见 {lane_count} 条车道。",
                "route": industry_route,
            },
            "backlog": {
                "key": "backlog",
                "count": backlog_count,
                "detail": f"当前有 {backlog_count} 条待办正在等待排入执行周期。",
                "route": industry_route,
            },
            "current_cycle": {
                "key": "current_cycle",
                "count": cycle_count,
                "title": cycle_title,
                "status": cycle_status,
                "focus_count": cycle_focus_count if cycle_focus_count > 0 else None,
                "next_cycle_due_at": next_cycle_due_at,
                "detail": f"当前关联 {cycle_count} 个周期。"
                + (f"当前周期：{cycle_title}。" if cycle_title else ""),
                "route": industry_route,
            },
            "assignments": {
                "key": "assignments",
                "count": assignment_count,
                "detail": f"当前有 {assignment_count} 条派工正在运行包络内推进。",
                "route": industry_route,
            },
            "agent_reports": {
                "key": "agent_reports",
                "count": report_count,
                "unconsumed_count": unconsumed_report_count,
                "detail": f"当前可见 {report_count} 条汇报"
                + (f"，其中 {unconsumed_report_count} 条尚未消化。" if unconsumed_report_count > 0 else "。"),
                "route": industry_route,
            },
            "environment": {
                "key": "environment",
                "summary": "打开治理宿主镜像与环境连续性读面。",
                "route": "/api/runtime-center/governance/status",
            },
            "evidence": {
                "key": "evidence",
                "count": evidence_count,
                "detail": f"当前有 {evidence_count} 条证据可用于回放运行链路。",
                "route": "/api/runtime-center/evidence",
            },
            "decisions": {
                "key": "decisions",
                "count": decision_count,
                "detail": f"当前有 {decision_count} 条治理决策待处理或已记录。",
                "route": "/api/runtime-center/decisions",
            },
            "patches": {
                "key": "patches",
                "count": patch_count,
                "detail": f"当前运行中心已跟踪 {patch_count} 条学习补丁。",
                "route": "/api/runtime-center/learning/patches",
            },
        }
        if exception_absorption:
            case_count = self._int(exception_absorption.get("case_count"), 0)
            human_required_case_count = self._int(
                exception_absorption.get("human_required_case_count"),
                0,
            )
            signals["exception_absorption"] = {
                "key": "exception_absorption",
                "count": case_count,
                "human_required_case_count": human_required_case_count,
                "detail": self._string(exception_absorption.get("summary"))
                or "主脑当前正在处理中枢内部执行压力。",
                "route": industry_route or first_entry.route,
                "status": self._string(exception_absorption.get("status")) or "clear",
            }
        return {
            "carrier": signals["carrier"],
            "strategy": signals["strategy"],
            "signals": signals,
            "control_chain": [
                signals["carrier"],
                signals["strategy"],
                signals["lanes"],
                signals["backlog"],
                signals["current_cycle"],
                signals["assignments"],
                *([signals["exception_absorption"]] if isinstance(signals.get("exception_absorption"), dict) else []),
                signals["agent_reports"],
                signals["environment"],
                signals["evidence"],
                signals["decisions"],
                signals["patches"],
            ],
            "lanes": lane_count,
            "backlog": backlog_count,
            "current_cycle": cycle_count,
            "assignments": assignment_count,
            "agent_reports": report_count,
            "evidence": evidence_count,
            "decisions": decision_count,
            "patches": patch_count,
            "strategy_id": entry_meta.get("strategy_id"),
            "industry_instance_id": entry_meta.get("industry_instance_id"),
            "industry_route": industry_route,
            "exception_absorption": exception_absorption,
            "visible_count": 1 if total > 0 else 0,
            "truncated": total > 1,
        }

    def summarize_main_brain_card(self, first_entry: RuntimeOverviewEntry) -> str:
        meta = dict(first_entry.meta or {})
        lane_count = self._int(meta.get("lane_count"), 0)
        backlog_count = self._int(meta.get("backlog_count"), 0)
        assignment_count = self._int(meta.get("assignment_count"), 0)
        report_count = self._int(meta.get("report_count"), 0)
        evidence_count = self._int(meta.get("evidence_count"), 0)
        decision_count = self._int(meta.get("decision_count"), 0)
        patch_count = self._int(meta.get("patch_count"), 0)
        summary = (
            "主脑驾驶舱当前跟踪 "
            f"{lane_count} 条车道、{backlog_count} 条待办、{assignment_count} 条派工、"
            f"{report_count} 条汇报、{evidence_count} 条证据、"
            f"{decision_count} 条决策与 {patch_count} 条补丁。"
        )
        exception_absorption = self._mapping(meta.get("exception_absorption")) or {}
        case_count = self._int(exception_absorption.get("case_count"), 0)
        human_required_case_count = self._int(
            exception_absorption.get("human_required_case_count"),
            0,
        )
        exception_summary = self._string(exception_absorption.get("summary"))
        if exception_summary and (case_count > 0 or human_required_case_count > 0):
            return f"{exception_summary} {summary}"
        return summary

    def index_industry_by_instance_id(self, items: list[Any]) -> dict[str, Any]:
        indexed: dict[str, Any] = {}
        for item in items:
            instance_id = self._string(self._get_field(item, "instance_id", "id"))
            if instance_id:
                indexed[instance_id] = item
        return indexed

    def build_main_brain_industry_route(self, industry_instance_id: str | None) -> str | None:
        normalized_instance_id = self._string(industry_instance_id)
        if normalized_instance_id is None:
            return None
        return f"/api/runtime-center/industry/{quote(normalized_instance_id)}"

    def build_main_brain_report_route(
        self,
        *,
        industry_instance_id: str | None,
        report_id: str | None,
    ) -> str | None:
        industry_route = self.build_main_brain_industry_route(industry_instance_id)
        normalized_report_id = self._string(report_id)
        if industry_route is None or normalized_report_id is None:
            return industry_route
        return f"{industry_route}?report_id={quote(normalized_report_id)}"

    def build_main_brain_backlog_route(
        self,
        *,
        industry_instance_id: str | None,
        backlog_item_id: str | None,
    ) -> str | None:
        industry_route = self.build_main_brain_industry_route(industry_instance_id)
        normalized_backlog_item_id = self._string(backlog_item_id)
        if industry_route is None or normalized_backlog_item_id is None:
            return industry_route
        return f"{industry_route}?backlog_item_id={quote(normalized_backlog_item_id)}"

    def normalize_main_brain_reports(
        self,
        reports: Sequence[Any],
        *,
        industry_instance_id: str | None,
    ) -> list[dict[str, Any]]:
        normalized_reports: list[dict[str, Any]] = []
        for report in reports:
            payload = dict(self._mapping(report) or {})
            if not payload:
                continue
            report_id = self._string(payload.get("report_id") or payload.get("id"))
            metadata = self._mapping(payload.get("metadata")) or {}
            if payload.get("route") is None:
                payload["route"] = self.build_main_brain_report_route(
                    industry_instance_id=industry_instance_id,
                    report_id=report_id,
                )
            if "report_consumed" not in payload:
                if isinstance(metadata.get("report_consumed"), bool):
                    payload["report_consumed"] = bool(metadata.get("report_consumed"))
                elif isinstance(payload.get("processed"), bool):
                    payload["report_consumed"] = bool(payload.get("processed"))
            normalized_reports.append(payload)
        return normalized_reports

    def normalize_main_brain_cognition_finding(
        self,
        payload: Mapping[str, Any],
        *,
        industry_instance_id: str | None,
        report_lookup: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        report_id = self._string(payload.get("report_id"))
        report_payload = report_lookup.get(report_id or "", {})
        return {
            **dict(payload),
            "title": self._string(payload.get("title"))
            or self._string(payload.get("headline"))
            or self._string(report_payload.get("headline"))
            or report_id,
            "summary": self._string(payload.get("summary")) or self._string(report_payload.get("summary")),
            "route": self._string(payload.get("route"))
            or self._string(report_payload.get("route"))
            or self.build_main_brain_report_route(
                industry_instance_id=industry_instance_id,
                report_id=report_id,
            ),
            "needs_followup": bool(
                payload.get("needs_followup")
                if payload.get("needs_followup") is not None
                else report_payload.get("needs_followup")
            ),
            "report_consumed": bool(report_payload.get("report_consumed"))
            if report_payload.get("report_consumed") is not None
            else None,
        }

    def normalize_main_brain_cognition_conflict(
        self,
        payload: Mapping[str, Any],
        *,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        return {
            **dict(payload),
            "title": self._string(payload.get("title")) or "汇报冲突",
            "summary": self._string(payload.get("summary")) or "多条汇报之间仍存在冲突。",
            "route": self._string(payload.get("route"))
            or self.build_main_brain_industry_route(industry_instance_id),
        }

    def normalize_main_brain_cognition_hole(
        self,
        payload: Mapping[str, Any],
        *,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        report_id = self._string(payload.get("report_id"))
        if report_id is None:
            report_ids = payload.get("report_ids")
            if isinstance(report_ids, list):
                report_id = self._string(report_ids[0] if report_ids else None)
        kind = self._string(payload.get("kind")) or "hole"
        return {
            **dict(payload),
            "title": self._string(payload.get("title"))
            or ("跟进缺口" if kind == "followup-needed" else "汇报缺口"),
            "summary": self._string(payload.get("summary")) or "当前仍有一条汇报缺口尚未补齐。",
            "route": self._string(payload.get("route"))
            or self.build_main_brain_report_route(
                industry_instance_id=industry_instance_id,
                report_id=report_id,
            )
            or self.build_main_brain_industry_route(industry_instance_id),
        }

    def normalize_main_brain_cognition_backlog(
        self,
        payload: Mapping[str, Any],
        *,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        backlog_item_id = self._string(payload.get("backlog_item_id") or payload.get("id"))
        return {
            **dict(payload),
            "title": self._string(payload.get("title")) or backlog_item_id,
            "summary": self._string(payload.get("summary")),
            "route": self._string(payload.get("route"))
            or self.build_main_brain_backlog_route(
                industry_instance_id=industry_instance_id,
                backlog_item_id=backlog_item_id,
            ),
        }

    def _unique_cognition_strings(self, *values: object) -> list[str]:
        seen: set[str] = set()
        items: list[str] = []
        for value in values:
            if not isinstance(value, list):
                continue
            for raw in value:
                text = self._string(raw)
                if text is None or text in seen:
                    continue
                seen.add(text)
                items.append(text)
        return items

    def _resolve_main_brain_replan_payload(
        self,
        *,
        industry_detail: Mapping[str, Any],
        current_cycle: Mapping[str, Any],
        current_cycle_synthesis: Mapping[str, Any],
    ) -> dict[str, Any]:
        planning = self._mapping(industry_detail.get("main_brain_planning")) or {}
        persisted = self._mapping(planning.get("replan")) or {}
        if not persisted:
            formal_planning = (
                self._mapping(current_cycle.get("formal_planning"))
                or self._mapping((self._mapping(current_cycle.get("metadata")) or {}).get("formal_planning"))
                or {}
            )
            persisted = self._mapping(formal_planning.get("report_replan")) or {}
        raw_decision = self._mapping(current_cycle_synthesis.get("replan_decision")) or {}
        activation = self._mapping(current_cycle_synthesis.get("activation")) or {}
        strategy_change = self._mapping(activation.get("strategy_change")) or {}
        trigger_families = self._unique_cognition_strings(
            persisted.get("trigger_families"),
            raw_decision.get("trigger_families"),
            strategy_change.get("trigger_families"),
        )
        trigger_rule_ids = self._unique_cognition_strings(
            persisted.get("trigger_rule_ids"),
            raw_decision.get("trigger_rule_ids"),
            strategy_change.get("trigger_rule_ids"),
        )
        affected_lane_ids = self._unique_cognition_strings(
            persisted.get("affected_lane_ids"),
            raw_decision.get("affected_lane_ids"),
            strategy_change.get("affected_lane_ids"),
        )
        affected_uncertainty_ids = self._unique_cognition_strings(
            persisted.get("affected_uncertainty_ids"),
            raw_decision.get("affected_uncertainty_ids"),
            strategy_change.get("affected_uncertainty_ids"),
        )
        has_synthesis_pressure = bool(
            current_cycle_synthesis.get("needs_replan")
            or list(current_cycle_synthesis.get("conflicts") or [])
            or list(current_cycle_synthesis.get("holes") or [])
            or list(current_cycle_synthesis.get("replan_reasons") or [])
            or list(current_cycle_synthesis.get("recommended_actions") or [])
        )
        decision_kind = (
            self._string(persisted.get("decision_kind"))
            or self._string(raw_decision.get("decision_kind"))
            or self._string(strategy_change.get("decision_kind"))
            or ("follow_up_backlog" if has_synthesis_pressure else "clear")
        )
        status = (
            self._string(persisted.get("status"))
            or self._string(raw_decision.get("status"))
            or ("needs-replan" if decision_kind != "clear" else "clear")
        )
        return {
            **dict(persisted),
            "status": status,
            "decision_kind": decision_kind,
            "summary": (
                self._string(persisted.get("summary"))
                or self._string(raw_decision.get("summary"))
                or (
                    "当前没有未解决的汇报综合重排压力。"
                    if decision_kind == "clear"
                    else "汇报综合结果要求主脑执行重规划。"
                )
            ),
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

    def build_main_brain_report_cognition_payload(
        self,
        *,
        industry_detail: Mapping[str, Any],
        industry_instance_id: str | None,
        normalized_reports: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        report_lookup = {
            self._string(payload.get("report_id") or payload.get("id")) or f"report:{index}": payload
            for index, payload in enumerate(normalized_reports)
        }
        current_cycle = self._mapping(industry_detail.get("current_cycle")) or {}
        current_cycle_route = self.build_main_brain_industry_route(industry_instance_id)
        current_cycle_synthesis = (
            self._mapping(current_cycle.get("synthesis"))
            or self._mapping((self._mapping(current_cycle.get("metadata")) or {}).get("report_synthesis"))
            or {}
        )
        latest_findings = [
            self.normalize_main_brain_cognition_finding(
                self._mapping(item) or {},
                industry_instance_id=industry_instance_id,
                report_lookup=report_lookup,
            )
            for item in list(current_cycle_synthesis.get("latest_findings") or [])
            if self._mapping(item)
        ]
        conflicts = [
            self.normalize_main_brain_cognition_conflict(
                self._mapping(item) or {},
                industry_instance_id=industry_instance_id,
            )
            for item in list(current_cycle_synthesis.get("conflicts") or [])
            if self._mapping(item)
        ]
        holes = [
            self.normalize_main_brain_cognition_hole(
                self._mapping(item) or {},
                industry_instance_id=industry_instance_id,
            )
            for item in list(current_cycle_synthesis.get("holes") or [])
            if self._mapping(item)
        ]
        followup_backlog = [
            self.normalize_main_brain_cognition_backlog(
                self._mapping(item) or {},
                industry_instance_id=industry_instance_id,
            )
            for item in self._normalize_list(industry_detail.get("backlog"))
            if self._string((self._mapping(item.get("metadata")) or {}).get("source_report_id"))
            or self._string((self._mapping(item.get("metadata")) or {}).get("synthesis_kind"))
        ]
        unconsumed_reports = [dict(report) for report in normalized_reports if report.get("report_consumed") is False]
        needs_followup_reports = [dict(report) for report in normalized_reports if report.get("needs_followup") is True]
        replan_reasons = [
            reason
            for reason in (self._string(item) for item in list(current_cycle_synthesis.get("replan_reasons") or []))
            if reason is not None
        ]
        replan = self._resolve_main_brain_replan_payload(
            industry_detail=industry_detail,
            current_cycle=current_cycle,
            current_cycle_synthesis=current_cycle_synthesis,
        )
        needs_replan = bool(current_cycle_synthesis.get("needs_replan")) or bool(
            self._string(replan.get("status")) == "needs-replan"
            or self._string(replan.get("decision_kind")) not in {None, "", "clear"}
            or conflicts
            or holes
            or followup_backlog
        )
        unresolved_count = len(conflicts) + len(holes) + len(unconsumed_reports) + len(followup_backlog)
        latest_followup_backlog = self._latest_timed_mapping(followup_backlog)
        latest_unconsumed_report = self._latest_timed_mapping(unconsumed_reports)
        if needs_replan:
            judgment_status = "attention"
            judgment_summary = (
                "主脑需要比对还没收口的汇报，并决定是否继续派发跟进任务。"
            )
        elif unconsumed_reports:
            judgment_status = "review"
            judgment_summary = (
                "主脑还有未消化的汇报，需要先综合后再结束当前周期。"
            )
        else:
            judgment_status = "clear"
            judgment_summary = "最新汇报已经消化完毕，当前没有明确的重排压力。"
        if latest_followup_backlog:
            next_action = {
                "kind": "followup-backlog",
                "decision_kind": self._string(replan.get("decision_kind")) or "follow_up_backlog",
                "title": self._string(latest_followup_backlog.get("title")) or "查看跟进待办",
                "summary": self._string(latest_followup_backlog.get("summary"))
                or "先处理当前汇报综合后形成的正式跟进待办。",
                "route": self._string(latest_followup_backlog.get("route")) or current_cycle_route,
            }
        elif latest_unconsumed_report:
            next_action = {
                "kind": "consume-report",
                "decision_kind": self._string(replan.get("decision_kind")) or "clear",
                "title": self._string(latest_unconsumed_report.get("headline"))
                or self._string(latest_unconsumed_report.get("title"))
                or "先处理最新汇报",
                "summary": "先消化最新一条未处理汇报，再决定是否继续派工。",
                "route": self._string(latest_unconsumed_report.get("route")) or current_cycle_route,
            }
        elif self._string(replan.get("decision_kind")) == "strategy_review_required":
            next_action = {
                "kind": "strategy-review",
                "decision_kind": "strategy_review_required",
                "title": "发起策略复核",
                "summary": self._string(replan.get("summary"))
                or "把这轮周期压力上提到策略复核。",
                "route": current_cycle_route,
            }
        elif self._string(replan.get("decision_kind")) == "cycle_rebalance":
            next_action = {
                "kind": "cycle-rebalance",
                "decision_kind": "cycle_rebalance",
                "title": "重排当前周期",
                "summary": self._string(replan.get("summary"))
                or "先重排当前周期，再继续派工。",
                "route": current_cycle_route,
            }
        elif self._string(replan.get("decision_kind")) == "lane_reweight":
            next_action = {
                "kind": "lane-reweight",
                "decision_kind": "lane_reweight",
                "title": "调整车道优先级",
                "summary": self._string(replan.get("summary"))
                or "先调整车道优先级，再规划下一轮任务。",
                "route": current_cycle_route,
            }
        else:
            latest_followup_backlog = self._latest_timed_mapping(followup_backlog)
            latest_unconsumed_report = self._latest_timed_mapping(unconsumed_reports)
            next_action = {
                "kind": "review-cycle-synthesis" if needs_replan else "continue-cycle",
                "decision_kind": self._string(replan.get("decision_kind")) or "clear",
                "title": "复核周期综合" if needs_replan else "继续当前周期",
                "summary": (
                    self._string(replan.get("summary"))
                    or "先复核周期综合结果，再决定下一步动作。"
                    if needs_replan
                    else "当前没有明确的汇报综合阻塞，可以继续推进本轮周期。"
                ),
                "route": current_cycle_route,
            }
        return {
            "latest_findings": latest_findings,
            "conflicts": conflicts,
            "holes": holes,
            "judgment": {
                "status": judgment_status,
                "summary": judgment_summary,
                "route": current_cycle_route,
                "decision_kind": self._string(replan.get("decision_kind")) or "clear",
            },
            "replan": replan,
            "decision_kind": self._string(replan.get("decision_kind")) or "clear",
            "next_action": next_action,
            "needs_replan": needs_replan,
            "replan_reasons": replan_reasons,
            "followup_backlog": followup_backlog,
            "unconsumed_reports": unconsumed_reports,
            "needs_followup_reports": needs_followup_reports,
            "current_cycle_id": self._string(current_cycle.get("cycle_id")),
            "route": current_cycle_route,
            "count": unresolved_count,
        }

    def build_main_brain_report_cognition_signal(self, cognition: Mapping[str, Any]) -> dict[str, Any]:
        needs_replan = bool(cognition.get("needs_replan"))
        decision_kind = self._string(cognition.get("decision_kind")) or "clear"
        return {
            "key": "report_cognition",
            "count": self._int(cognition.get("count"), 0),
            "value": "attention" if needs_replan or decision_kind != "clear" else "clear",
            "detail": self._string(self._mapping(cognition.get("judgment")).get("summary")),
            "route": self._string(self._mapping(cognition.get("next_action")).get("route"))
            or self._string(cognition.get("route")),
            "status": self._string(self._mapping(cognition.get("judgment")).get("status"))
            or ("attention" if needs_replan or decision_kind != "clear" else "clear"),
            "decision_kind": decision_kind,
            "needs_replan": needs_replan,
            "replan_reason_count": len(list(cognition.get("replan_reasons") or [])),
            "unconsumed_count": len(list(cognition.get("unconsumed_reports") or [])),
            "followup_count": len(list(cognition.get("followup_backlog") or [])),
        }
