# -*- coding: utf-8 -*-
"""Shared Runtime Center overview entry builders."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from ...utils.runtime_action_links import build_decision_actions, build_patch_actions
from .models import RuntimeOverviewEntry


class _RuntimeCenterOverviewEntryBuildersMixin:
    """Entry-level builders and scalar normalization helpers for overview cards."""

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
        namespace = getattr(item, "__dict__", None)
        if isinstance(namespace, Mapping):
            return namespace
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
