# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .derived_index_service import slugify, truncate_text
from .models import MemoryReflectionSummary, utc_now
from ..state import (
    MemoryEntityViewRecord,
    MemoryFactIndexRecord,
    MemoryOpinionViewRecord,
    MemoryReflectionRunRecord,
)


def _entity_view_id(scope_type: str, scope_id: str, entity_key: str) -> str:
    return f"memory-entity:{scope_type}:{slugify(scope_id)}:{slugify(entity_key)}"


def _opinion_view_id(scope_type: str, scope_id: str, opinion_key: str) -> str:
    return f"memory-opinion:{scope_type}:{slugify(scope_id)}:{slugify(opinion_key)}"


def _parse_opinion_key(opinion_key: str) -> tuple[str, str, str]:
    subject_key, first_sep, remainder = opinion_key.partition(":")
    if not first_sep:
        return "general", "neutral", opinion_key
    stance, second_sep, label = remainder.partition(":")
    if not second_sep:
        return subject_key or "general", stance or "neutral", remainder
    return subject_key or "general", stance or "neutral", label or opinion_key


class MemoryReflectionService:
    """Compile entity/opinion/confidence views from derived fact index entries."""

    def __init__(
        self,
        *,
        derived_index_service,
        entity_view_repository,
        opinion_view_repository,
        reflection_run_repository,
        learning_service: object | None = None,
    ) -> None:
        self._derived_index_service = derived_index_service
        self._entity_view_repository = entity_view_repository
        self._opinion_view_repository = opinion_view_repository
        self._reflection_run_repository = reflection_run_repository
        self._learning_service = learning_service

    def set_learning_service(self, learning_service: object | None) -> None:
        self._learning_service = learning_service

    def list_runs(self, **kwargs: Any) -> list[MemoryReflectionRunRecord]:
        return self._reflection_run_repository.list_runs(**kwargs)

    def reflect(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        trigger_kind: str = "manual",
        create_learning_proposals: bool = True,
    ) -> MemoryReflectionSummary:
        started_at = utc_now()
        run = MemoryReflectionRunRecord(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            trigger_kind=trigger_kind,
            status="running",
            started_at=started_at,
            created_at=started_at,
            updated_at=started_at,
        )
        run = self._reflection_run_repository.upsert_run(run)
        entries = self._derived_index_service.list_fact_entries(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            limit=None,
        )
        self._entity_view_repository.clear(scope_type=scope_type, scope_id=scope_id)
        self._opinion_view_repository.clear(scope_type=scope_type, scope_id=scope_id)

        entity_views = self._build_entity_views(
            entries=entries,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
        )
        for entity_view in entity_views:
            self._entity_view_repository.upsert_view(entity_view)

        opinion_views = self._build_opinion_views(
            entries=entries,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
        )
        for opinion_view in opinion_views:
            self._opinion_view_repository.upsert_view(opinion_view)

        proposal_ids = self._emit_learning_proposals(
            opinion_views=opinion_views,
            create_learning_proposals=create_learning_proposals,
        )
        summary_text = (
            f"Reflected {len(entries)} fact entries into "
            f"{len(entity_views)} entities and {len(opinion_views)} opinions."
        )
        completed_at = utc_now()
        finished_run = self._reflection_run_repository.upsert_run(
            run.model_copy(
                update={
                    "status": "completed",
                    "summary": summary_text,
                    "source_refs": [entry.source_ref for entry in entries],
                    "generated_entity_ids": [view.entity_id for view in entity_views],
                    "generated_opinion_ids": [view.opinion_id for view in opinion_views],
                    "metadata": {
                        "proposal_ids": proposal_ids,
                        "entity_count": len(entity_views),
                        "opinion_count": len(opinion_views),
                    },
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                },
            ),
        )
        return MemoryReflectionSummary(
            run_id=finished_run.run_id,
            scope_type=scope_type,
            scope_id=scope_id,
            status=finished_run.status,
            entity_count=len(entity_views),
            opinion_count=len(opinion_views),
            proposal_ids=proposal_ids,
            summary=summary_text,
            metadata=dict(finished_run.metadata or {}),
        )

    def _build_entity_views(
        self,
        *,
        entries: list[MemoryFactIndexRecord],
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None,
        industry_instance_id: str | None,
    ) -> list[MemoryEntityViewRecord]:
        entries_by_entity: dict[str, list[MemoryFactIndexRecord]] = defaultdict(list)
        for entry in entries:
            for entity_key in entry.entity_keys:
                entries_by_entity[entity_key].append(entry)
        views: list[MemoryEntityViewRecord] = []
        now = utc_now()
        for entity_key, entity_entries in entries_by_entity.items():
            related_entities = [
                other_key
                for other_key, _count in defaultdict(int, {
                    key: sum(key in entry.entity_keys for entry in entity_entries)
                    for key in {item for entry in entity_entries for item in entry.entity_keys}
                    if key != entity_key
                }).items()
            ]
            display_name = self._entity_display_name(entity_key, entity_entries)
            view = MemoryEntityViewRecord(
                entity_id=_entity_view_id(scope_type, scope_id, entity_key),
                entity_key=entity_key,
                scope_type=scope_type,
                scope_id=scope_id,
                owner_agent_id=owner_agent_id,
                industry_instance_id=industry_instance_id,
                display_name=display_name,
                entity_type="concept",
                summary=self._entity_summary(display_name, entity_entries),
                confidence=sum(entry.confidence for entry in entity_entries) / max(1, len(entity_entries)),
                supporting_refs=[entry.source_ref for entry in entity_entries[:8]],
                contradicting_refs=[
                    entry.source_ref
                    for entry in entity_entries
                    if any(":caution:" in key for key in entry.opinion_keys)
                ][:6],
                related_entities=list(dict.fromkeys(related_entities))[:8],
                source_refs=[entry.source_ref for entry in entity_entries[:12]],
                metadata={
                    "source_types": list(dict.fromkeys(entry.source_type for entry in entity_entries)),
                    "entry_count": len(entity_entries),
                },
                created_at=now,
                updated_at=now,
            )
            views.append(view)
        views.sort(key=lambda item: (item.confidence, item.updated_at), reverse=True)
        return views

    def _build_opinion_views(
        self,
        *,
        entries: list[MemoryFactIndexRecord],
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None,
        industry_instance_id: str | None,
    ) -> list[MemoryOpinionViewRecord]:
        entries_by_opinion: dict[str, list[MemoryFactIndexRecord]] = defaultdict(list)
        for entry in entries:
            for opinion_key in entry.opinion_keys:
                entries_by_opinion[opinion_key].append(entry)
        views: list[MemoryOpinionViewRecord] = []
        now = utc_now()
        for opinion_key, opinion_entries in entries_by_opinion.items():
            subject_key, stance, label = _parse_opinion_key(opinion_key)
            contradicting_refs = [
                entry.source_ref
                for entry in entries
                if subject_key in entry.entity_keys
                and any(
                    _parse_opinion_key(candidate)[1] != stance
                    for candidate in entry.opinion_keys
                )
            ][:8]
            summary = truncate_text(
                " / ".join(
                    part
                    for part in (
                        label.replace("-", " "),
                        *(entry.summary or entry.title for entry in opinion_entries[:3]),
                    )
                    if part
                ),
                max_length=320,
            )
            view = MemoryOpinionViewRecord(
                opinion_id=_opinion_view_id(scope_type, scope_id, opinion_key),
                subject_key=subject_key,
                scope_type=scope_type,
                scope_id=scope_id,
                owner_agent_id=owner_agent_id,
                industry_instance_id=industry_instance_id,
                opinion_key=opinion_key,
                stance=stance,
                summary=summary,
                confidence=sum(entry.confidence for entry in opinion_entries) / max(1, len(opinion_entries)),
                supporting_refs=[entry.source_ref for entry in opinion_entries[:8]],
                contradicting_refs=list(dict.fromkeys(contradicting_refs))[:8],
                entity_keys=[subject_key, *list(dict.fromkeys(
                    item for entry in opinion_entries for item in entry.entity_keys if item != subject_key
                ))[:6]],
                source_refs=[entry.source_ref for entry in opinion_entries[:12]],
                last_reflected_at=now,
                metadata={
                    "label": label,
                    "entry_count": len(opinion_entries),
                },
                created_at=now,
                updated_at=now,
            )
            views.append(view)
        views.sort(key=lambda item: (item.confidence, item.updated_at), reverse=True)
        return views

    def _emit_learning_proposals(
        self,
        *,
        opinion_views: list[MemoryOpinionViewRecord],
        create_learning_proposals: bool,
    ) -> list[str]:
        if not create_learning_proposals:
            return []
        service = self._learning_service
        creator = getattr(service, "create_proposal", None)
        if not callable(creator):
            return []
        proposals: list[str] = []
        by_subject: dict[str, list[MemoryOpinionViewRecord]] = defaultdict(list)
        for view in opinion_views:
            by_subject[view.subject_key].append(view)
        for subject_key, subject_views in by_subject.items():
            stances = {view.stance for view in subject_views}
            if len(stances) < 2:
                continue
            summary = "; ".join(
                f"{view.stance}: {view.summary}"
                for view in subject_views[:3]
            )
            try:
                proposal = creator(
                    title=f"Resolve memory conflict for {subject_key}",
                    description=summary,
                    target_layer="memory-reflection",
                    evidence_refs=[
                        source_ref
                        for view in subject_views
                        for source_ref in view.supporting_refs[:2]
                    ][:6],
                )
            except Exception:
                continue
            proposal_id = str(getattr(proposal, "id", "") or "").strip()
            if proposal_id:
                proposals.append(proposal_id)
        return proposals

    def _entity_display_name(
        self,
        entity_key: str,
        entries: list[MemoryFactIndexRecord],
    ) -> str:
        for entry in entries:
            labels = entry.metadata.get("entity_labels") if isinstance(entry.metadata, dict) else None
            if isinstance(labels, dict):
                label = labels.get(entity_key)
                if isinstance(label, str) and label.strip():
                    return label.strip()
        return entity_key.replace("-", " ")

    def _entity_summary(
        self,
        display_name: str,
        entries: list[MemoryFactIndexRecord],
    ) -> str:
        fragments = [
            entry.summary or entry.title
            for entry in entries[:3]
            if (entry.summary or entry.title)
        ]
        summary = " / ".join(fragment for fragment in fragments if fragment)
        return truncate_text(f"{display_name}: {summary}", max_length=320)
