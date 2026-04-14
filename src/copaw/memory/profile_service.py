# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field

from .derived_index_service import selector_matches_scope
from .models import MemoryScopeSelector
from .precedence import MemoryEntryPartition, MemoryPrecedenceService
from ..state import MemoryFactIndexRecord


def _role_matches(entry: MemoryFactIndexRecord, role: str | None) -> bool:
    normalized_role = str(role or "").strip().lower()
    if not normalized_role or not entry.role_bindings:
        return True
    return normalized_role in {item.lower() for item in entry.role_bindings}


@dataclass(slots=True)
class MemoryProfile:
    scope_type: str
    scope_id: str
    static_profile: list[str] = field(default_factory=list)
    dynamic_profile: list[str] = field(default_factory=list)
    active_preferences: list[str] = field(default_factory=list)
    active_constraints: list[str] = field(default_factory=list)
    current_focus_summary: str = ""
    current_operating_context: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        parts = [
            *self.static_profile,
            *self.dynamic_profile,
            *self.active_preferences,
            *self.active_constraints,
            self.current_focus_summary,
            *self.current_operating_context,
        ]
        return "\n".join(part for part in parts if part).strip()


@dataclass(slots=True)
class SharedMemoryViews:
    profile: MemoryProfile
    latest: list[MemoryFactIndexRecord]
    history: list[MemoryFactIndexRecord]


class MemoryProfileService:
    """Build shared profile/latest/history views from the rebuildable fact index."""

    def __init__(
        self,
        *,
        derived_index_service,
        precedence_service: MemoryPrecedenceService | None = None,
    ) -> None:
        self._derived_index_service = derived_index_service
        self._precedence_service = precedence_service or MemoryPrecedenceService()

    def build_views(
        self,
        *,
        scope_type: str,
        scope_id: str,
        role: str | None = None,
        selector: MemoryScopeSelector | None = None,
        entries: list[MemoryFactIndexRecord] | None = None,
    ) -> SharedMemoryViews:
        effective_selector = selector or MemoryScopeSelector(
            scope_type=scope_type,
            scope_id=scope_id,
            include_related_scopes=True,
        )
        selected_entries = self._collect_entries(
            selector=effective_selector,
            entries=entries,
            role=role,
        )
        partition = self._precedence_service.partition_entries(selected_entries)
        profile = self._build_profile(
            scope_type=scope_type,
            scope_id=scope_id,
            entries=selected_entries,
            partition=partition,
        )
        return SharedMemoryViews(
            profile=profile,
            latest=partition.latest,
            history=partition.history,
        )

    def _collect_entries(
        self,
        *,
        selector: MemoryScopeSelector,
        entries: list[MemoryFactIndexRecord] | None,
        role: str | None,
    ) -> list[MemoryFactIndexRecord]:
        all_entries = list(entries or self._derived_index_service.list_fact_entries(limit=None))
        selected = [
            entry
            for entry in all_entries
            if selector_matches_scope(
                selector=selector,
                scope_type=entry.scope_type,
                scope_id=entry.scope_id,
            )
            and _role_matches(entry, role)
        ]
        if selector.scope_type == "work_context" and not selector.industry_instance_id:
            industry_ids = {
                str(entry.industry_instance_id or "").strip()
                for entry in selected
                if str(entry.industry_instance_id or "").strip()
            }
            if len(industry_ids) == 1:
                enriched_selector = MemoryScopeSelector(
                    scope_type=selector.scope_type,
                    scope_id=selector.scope_id,
                    work_context_id=selector.scope_id,
                    industry_instance_id=next(iter(industry_ids)),
                    include_related_scopes=True,
                )
                selected = [
                    entry
                    for entry in all_entries
                    if selector_matches_scope(
                        selector=enriched_selector,
                        scope_type=entry.scope_type,
                        scope_id=entry.scope_id,
                    )
                    and _role_matches(entry, role)
                ]
        return selected

    def _build_profile(
        self,
        *,
        scope_type: str,
        scope_id: str,
        entries: list[MemoryFactIndexRecord],
        partition: MemoryEntryPartition,
    ) -> MemoryProfile:
        profile = MemoryProfile(scope_type=scope_type, scope_id=scope_id)
        seen_refs: set[str] = set()
        focus_parts: list[str] = []

        for entry in partition.latest:
            metadata = dict(entry.metadata or {})
            source_ref = str(metadata.get("source_ref") or entry.source_ref or "").strip()
            if source_ref and source_ref not in seen_refs:
                seen_refs.add(source_ref)
                profile.source_refs.append(source_ref)

            if entry.source_type == "strategy_memory":
                mission = str(metadata.get("mission") or "").strip()
                if entry.summary:
                    profile.static_profile.append(entry.summary)
                if mission:
                    profile.static_profile.append(mission)
                profile.active_constraints.extend(
                    [
                        item
                        for item in list(metadata.get("execution_constraints") or [])
                        if str(item or "").strip()
                    ],
                )
                profile.active_constraints.extend(
                    [
                        item
                        for item in list(metadata.get("evidence_requirements") or [])
                        if str(item or "").strip()
                    ],
                )
                focus_parts.extend(
                    [
                        str(item).strip()
                        for item in list(metadata.get("current_focuses") or [])
                        if str(item or "").strip()
                    ],
                )
                continue

            memory_type = str(metadata.get("memory_type") or "").strip().lower()
            if memory_type == "preference":
                if entry.summary:
                    profile.active_preferences.append(entry.summary)
                continue

            if entry.scope_type == "work_context":
                text = entry.summary or entry.content_excerpt or entry.title
                if text:
                    profile.current_operating_context.append(text)

            if entry.source_type in {"agent_report", "evidence", "report_snapshot", "routine_run"}:
                text = entry.summary or entry.content_excerpt or entry.title
                if text:
                    profile.dynamic_profile.append(text)
                continue

            if entry.scope_type == scope_type and entry.scope_id == scope_id and entry.summary:
                profile.dynamic_profile.append(entry.summary)

        profile.static_profile = list(dict.fromkeys(profile.static_profile))
        profile.dynamic_profile = list(dict.fromkeys(profile.dynamic_profile))
        profile.active_preferences = list(dict.fromkeys(profile.active_preferences))
        profile.active_constraints = list(dict.fromkeys(profile.active_constraints))
        profile.current_operating_context = list(dict.fromkeys(profile.current_operating_context))
        profile.current_focus_summary = " ".join(
            part
            for part in dict.fromkeys(
                [
                    *focus_parts,
                    *profile.active_constraints,
                    *(profile.dynamic_profile[:1] if profile.dynamic_profile else []),
                ],
            )
            if part
        ).strip()
        if not profile.current_focus_summary and profile.dynamic_profile:
            profile.current_focus_summary = profile.dynamic_profile[0]
        if not profile.current_focus_summary and profile.current_operating_context:
            profile.current_focus_summary = profile.current_operating_context[0]
        return profile


__all__ = [
    "MemoryProfile",
    "MemoryProfileService",
    "SharedMemoryViews",
]
