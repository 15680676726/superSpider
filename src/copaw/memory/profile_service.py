# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
import re

from .derived_index_service import selector_matches_scope
from .models import MemoryScopeSelector
from .precedence import MemoryEntryPartition, MemoryPrecedenceService
from ..state import MemoryFactIndexRecord

_SPACE_RE = re.compile(r"\s+")
_NOISE_TITLE_RE = re.compile(r"^noise(?:[-_\s:]*\d+)?", re.IGNORECASE)


def _role_matches(entry: MemoryFactIndexRecord, role: str | None) -> bool:
    normalized_role = str(role or "").strip().lower()
    if not normalized_role or not entry.role_bindings:
        return True
    return normalized_role in {item.lower() for item in entry.role_bindings}


def _normalize_text(value: object | None) -> str:
    return _SPACE_RE.sub(" ", str(value or "").strip())


def _looks_like_noise_text(value: object | None) -> bool:
    normalized = _normalize_text(value).lower()
    return bool(normalized) and bool(_NOISE_TITLE_RE.match(normalized))


def _is_low_signal_entry(entry: MemoryFactIndexRecord) -> bool:
    metadata = dict(entry.metadata or {})
    tags = {
        str(item or "").strip().lower()
        for item in [*list(entry.tags or []), *list(metadata.get("tags") or [])]
        if str(item or "").strip()
    }
    if "noise" in tags:
        return True
    return any(
        _looks_like_noise_text(value)
        for value in (entry.title, entry.summary, entry.content_excerpt)
    )


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
    read_layer: str = "truth-first"
    overlay_id: str | None = None
    industry_profile_id: str | None = None

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
        memory_sleep_service: object | None = None,
    ) -> None:
        self._derived_index_service = derived_index_service
        self._precedence_service = precedence_service or MemoryPrecedenceService()
        self._memory_sleep_service = memory_sleep_service

    def set_memory_sleep_service(self, memory_sleep_service: object | None) -> None:
        self._memory_sleep_service = memory_sleep_service

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

            if _is_low_signal_entry(entry):
                continue

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
        self._apply_sleep_layers(profile=profile, scope_type=scope_type, scope_id=scope_id)
        return profile

    def _apply_sleep_layers(
        self,
        *,
        profile: MemoryProfile,
        scope_type: str,
        scope_id: str,
    ) -> None:
        sleep_service = self._memory_sleep_service
        if sleep_service is None:
            return
        get_active_industry_profile = getattr(sleep_service, "get_active_industry_profile", None)
        get_active_work_context_overlay = getattr(sleep_service, "get_active_work_context_overlay", None)

        industry_profile = None
        overlay = None
        if scope_type == "industry" and callable(get_active_industry_profile):
            industry_profile = get_active_industry_profile(scope_id)
        elif scope_type == "work_context" and callable(get_active_work_context_overlay):
            overlay = get_active_work_context_overlay(scope_id)
            if overlay is not None and callable(get_active_industry_profile):
                industry_id = str(getattr(overlay, "industry_instance_id", "") or "").strip()
                if industry_id:
                    industry_profile = get_active_industry_profile(industry_id)

        if industry_profile is not None:
            profile.static_profile = list(
                dict.fromkeys(
                    [
                        *profile.static_profile,
                        str(getattr(industry_profile, "headline", "") or "").strip(),
                        str(getattr(industry_profile, "summary", "") or "").strip(),
                        str(getattr(industry_profile, "strategic_direction", "") or "").strip(),
                    ]
                )
            )
            profile.active_constraints = list(
                dict.fromkeys(
                    [
                        *list(getattr(industry_profile, "active_constraints", []) or []),
                        *profile.active_constraints,
                    ]
                )
            )
            if not profile.current_focus_summary:
                profile.current_focus_summary = (
                    str(getattr(industry_profile, "summary", "") or "").strip()
                    or str(getattr(industry_profile, "headline", "") or "").strip()
                )
            profile.industry_profile_id = str(getattr(industry_profile, "profile_id", "") or "").strip() or None
            profile.read_layer = "industry_profile"

        if overlay is not None:
            overlay_summary = str(getattr(overlay, "summary", "") or "").strip()
            focus_summary = str(getattr(overlay, "focus_summary", "") or "").strip()
            headline = str(getattr(overlay, "headline", "") or "").strip()
            profile.dynamic_profile = list(
                dict.fromkeys(
                    [
                        *(item for item in [headline, overlay_summary] if item),
                        *profile.dynamic_profile,
                    ]
                )
            )
            profile.active_constraints = list(
                dict.fromkeys(
                    [
                        *list(getattr(overlay, "active_constraints", []) or []),
                        *profile.active_constraints,
                    ]
                )
            )
            profile.current_operating_context = list(
                dict.fromkeys(
                    [
                        *(item for item in [overlay_summary, focus_summary] if item),
                        *profile.current_operating_context,
                    ]
                )
            )
            profile.current_focus_summary = focus_summary or overlay_summary or headline or profile.current_focus_summary
            profile.overlay_id = str(getattr(overlay, "overlay_id", "") or "").strip() or None
            profile.read_layer = "work_context_overlay"


__all__ = [
    "MemoryProfile",
    "MemoryProfileService",
    "SharedMemoryViews",
]
