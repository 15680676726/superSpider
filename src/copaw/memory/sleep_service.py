# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from ..state import (
    IndustryMemoryProfileRecord,
    MemoryAliasMapRecord,
    MemoryConflictProposalRecord,
    MemoryMergeResultRecord,
    MemoryScopeDigestRecord,
    MemorySleepJobRecord,
    MemorySleepScopeStateRecord,
    MemoryStructureProposalRecord,
    MemorySoftRuleRecord,
    WorkContextMemoryOverlayRecord,
)
from .sleep_inference_service import (
    _normalize_conflict_status,
    _normalize_soft_rule_state,
)
from .activation_service import MemoryActivationService
from .continuity_detail_service import ContinuityDetailService
from .knowledge_graph_service import KnowledgeGraphService
from .structure_enhancement_service import StructureEnhancementService
from .structure_proposal_executor import StructureProposalExecutor

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def _first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _slug(value: str, *, fallback: str) -> str:
    normalized = _SLUG_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return normalized or fallback


def _normalize_sleep_job_trigger_kind(trigger_kind: object) -> tuple[str, str | None]:
    normalized = str(trigger_kind or "").strip().lower()
    if normalized in {"scheduled", "idle", "manual"}:
        return normalized, None
    return "manual", normalized or None


def _industry_instance_id_from_source_ref(source_ref: object) -> str | None:
    text = str(source_ref or "").strip()
    if not text.startswith("industry:"):
        return None
    remainder = text.split(":", 1)[1].strip()
    if not remainder:
        return None
    industry_instance_id = remainder.split(":", 1)[0].strip()
    return industry_instance_id or None


class MemorySleepService:
    """Manage dirty scopes and compile B+ sleep-layer overlays."""

    def __init__(
        self,
        *,
        repository,
        knowledge_service: object | None,
        strategy_memory_service: object | None,
        derived_index_service,
        reflection_service: object | None = None,
        inference_service,
        activation_service: object | None = None,
        knowledge_graph_service: object | None = None,
        structure_enhancement_service: object | None = None,
        continuity_detail_service: object | None = None,
        structure_proposal_executor: object | None = None,
    ) -> None:
        self._repository = repository
        self._knowledge_service = knowledge_service
        self._strategy_memory_service = strategy_memory_service
        self._derived_index_service = derived_index_service
        self._reflection_service = reflection_service
        self._inference_service = inference_service
        self._activation_service = activation_service or MemoryActivationService(
            derived_index_service=derived_index_service,
            strategy_memory_service=strategy_memory_service,
        )
        self._knowledge_graph_service = knowledge_graph_service or KnowledgeGraphService(
            knowledge_service=knowledge_service,
            derived_index_service=derived_index_service,
            strategy_memory_service=strategy_memory_service,
            memory_activation_service=self._activation_service,
        )
        self._structure_enhancement_service = structure_enhancement_service or StructureEnhancementService(
            repository=repository,
        )
        self._continuity_detail_service = continuity_detail_service or ContinuityDetailService(
            repository=repository,
        )
        self._structure_proposal_executor = structure_proposal_executor or StructureProposalExecutor(
            repository=repository,
        )

    def mark_scope_dirty(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        reason: str | None = None,
        source_ref: str | None = None,
    ) -> MemorySleepScopeStateRecord:
        now = _utc_now()
        existing = self.get_scope_state(scope_type=scope_type, scope_id=scope_id)
        dirty_reasons = _unique([*(existing.dirty_reasons if existing else []), str(reason or "").strip()])
        dirty_source_refs = _unique([*(existing.dirty_source_refs if existing else []), str(source_ref or "").strip()])
        record = MemorySleepScopeStateRecord(
            scope_key=f"{scope_type}:{scope_id}",
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id or (existing.owner_agent_id if existing else None),
            industry_instance_id=industry_instance_id or (existing.industry_instance_id if existing else None),
            is_dirty=True,
            dirty_reasons=dirty_reasons,
            dirty_source_refs=dirty_source_refs,
            dirty_count=int(getattr(existing, "dirty_count", 0) or 0) + 1,
            first_dirtied_at=existing.first_dirtied_at if existing and existing.first_dirtied_at else now,
            last_dirtied_at=now,
            last_sleep_job_id=existing.last_sleep_job_id if existing else None,
            last_sleep_at=existing.last_sleep_at if existing else None,
            metadata=dict(getattr(existing, "metadata", {}) or {}),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        return self._repository.upsert_scope_state(record)

    def get_scope_state(self, *, scope_type: str, scope_id: str) -> MemorySleepScopeStateRecord | None:
        return self._repository.get_scope_state(scope_type=scope_type, scope_id=scope_id)

    def list_scope_states(self, **kwargs: Any) -> list[MemorySleepScopeStateRecord]:
        return self._repository.list_scope_states(**kwargs)

    def get_active_digest(self, scope_type: str, scope_id: str) -> MemoryScopeDigestRecord | None:
        return self._repository.get_active_digest(scope_type, scope_id)

    def list_digests(self, **kwargs: Any) -> list[MemoryScopeDigestRecord]:
        return self._repository.list_digests(**kwargs)

    def list_sleep_jobs(self, **kwargs: Any) -> list[MemorySleepJobRecord]:
        return self._repository.list_sleep_jobs(**kwargs)

    def list_alias_maps(self, **kwargs: Any) -> list[MemoryAliasMapRecord]:
        return self._repository.list_alias_maps(**kwargs)

    def list_merge_results(self, **kwargs: Any) -> list[MemoryMergeResultRecord]:
        return self._repository.list_merge_results(**kwargs)

    def list_soft_rules(self, **kwargs: Any) -> list[MemorySoftRuleRecord]:
        return self._repository.list_soft_rules(**kwargs)

    def list_conflict_proposals(self, **kwargs: Any) -> list[MemoryConflictProposalRecord]:
        return self._repository.list_conflict_proposals(**kwargs)

    def get_active_industry_profile(self, industry_instance_id: str) -> IndustryMemoryProfileRecord | None:
        return self._repository.get_active_industry_profile(industry_instance_id)

    def list_industry_profiles(self, **kwargs: Any) -> list[IndustryMemoryProfileRecord]:
        return self._repository.list_industry_profiles(**kwargs)

    def get_active_work_context_overlay(self, work_context_id: str) -> WorkContextMemoryOverlayRecord | None:
        return self._repository.get_active_work_context_overlay(work_context_id)

    def list_work_context_overlays(self, **kwargs: Any) -> list[WorkContextMemoryOverlayRecord]:
        return self._repository.list_work_context_overlays(**kwargs)

    def list_structure_proposals(self, **kwargs: Any) -> list[MemoryStructureProposalRecord]:
        return self._repository.list_structure_proposals(**kwargs)

    def list_slot_preferences(self, **kwargs: Any) -> list[object]:
        return self._repository.list_slot_preferences(**kwargs)

    def list_continuity_details(self, **kwargs: Any) -> list[object]:
        return self._repository.list_continuity_details(**kwargs)

    def upsert_manual_pin(
        self,
        *,
        scope_type: str,
        scope_id: str,
        detail_key: str,
        detail_text: str,
        industry_instance_id: str | None = None,
        work_context_id: str | None = None,
        pinned_until_phase: str | None = None,
        detail_label: str | None = None,
    ) -> object:
        record = self._continuity_detail_service.upsert_manual_pin(
            scope_type=scope_type,
            scope_id=scope_id,
            detail_key=detail_key,
            detail_text=detail_text,
            industry_instance_id=industry_instance_id,
            work_context_id=work_context_id,
            pinned_until_phase=pinned_until_phase,
            detail_label=detail_label,
        )
        if scope_type in {"industry", "work_context"}:
            self.refresh_scope_projection(
                scope_type=scope_type,
                scope_id=scope_id,
                trigger_kind="manual-pin",
            )
        return record

    def refresh_scope_projection(
        self,
        *,
        scope_type: str,
        scope_id: str,
        trigger_kind: str = "daytime",
    ) -> dict[str, object]:
        if scope_type not in {"industry", "work_context"}:
            return {}
        knowledge_chunks = self._load_knowledge_chunks(scope_type=scope_type, scope_id=scope_id)
        strategies = self._load_strategies(scope_type=scope_type, scope_id=scope_id)
        fact_entries = list(
            self._derived_index_service.list_fact_entries(
                scope_type=scope_type,
                scope_id=scope_id,
                limit=None,
            ),
        )
        relation_views = self._load_relation_views(scope_type=scope_type, scope_id=scope_id)
        scope_state = self.get_scope_state(scope_type=scope_type, scope_id=scope_id)
        industry_instance_id = self._resolve_scope_industry_instance_id(
            scope_type=scope_type,
            scope_id=scope_id,
            scope_state=scope_state,
            fact_entries=fact_entries,
            knowledge_chunks=knowledge_chunks,
        )
        result: dict[str, object] = {}
        profile = None
        if scope_type == "industry":
            profile = self._refresh_daytime_industry_profile(
                industry_instance_id=scope_id,
                knowledge_chunks=knowledge_chunks,
                strategies=strategies,
                fact_entries=fact_entries,
                relation_views=relation_views,
                trigger_kind=trigger_kind,
            )
            if profile is not None:
                result["industry_profile"] = profile
        if scope_type == "work_context":
            if industry_instance_id:
                profile = self._refresh_daytime_industry_profile(
                    industry_instance_id=industry_instance_id,
                    knowledge_chunks=self._load_knowledge_chunks(scope_type="industry", scope_id=industry_instance_id),
                    strategies=self._load_strategies(scope_type="industry", scope_id=industry_instance_id),
                    fact_entries=list(
                        self._derived_index_service.list_fact_entries(
                            scope_type="industry",
                            scope_id=industry_instance_id,
                            limit=None,
                        ),
                    ),
                    relation_views=self._load_relation_views(scope_type="industry", scope_id=industry_instance_id),
                    trigger_kind=trigger_kind,
                )
                if profile is not None:
                    result["industry_profile"] = profile
            overlay = self._refresh_daytime_work_context_overlay(
                work_context_id=scope_id,
                industry_instance_id=industry_instance_id,
                base_profile=profile or (self.get_active_industry_profile(industry_instance_id) if industry_instance_id else None),
                knowledge_chunks=knowledge_chunks,
                fact_entries=fact_entries,
                relation_views=relation_views,
                trigger_kind=trigger_kind,
            )
            if overlay is not None:
                result["work_context_overlay"] = overlay
        return result

    def get_structure_proposal(self, proposal_id: str) -> MemoryStructureProposalRecord | None:
        normalized = str(proposal_id or "").strip()
        if not normalized:
            return None
        for item in self.list_structure_proposals(limit=None):
            if str(getattr(item, "proposal_id", "") or "").strip() == normalized:
                return item
        return None

    def decide_structure_proposal(
        self,
        *,
        proposal_id: str,
        decision: str,
        decided_by: str | None = None,
        note: str | None = None,
    ) -> MemoryStructureProposalRecord:
        record = self.get_structure_proposal(proposal_id)
        if record is None:
            raise KeyError(proposal_id)
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"accepted", "rejected"}:
            raise ValueError(f"unsupported structure proposal decision: {decision}")
        metadata = dict(record.metadata or {})
        metadata["decision"] = normalized_decision
        metadata["decided_by"] = str(decided_by or "").strip() or None
        metadata["decision_note"] = str(note or "").strip() or None
        metadata["decided_at"] = _utc_now().isoformat()
        if normalized_decision == "accepted":
            execution = self._structure_proposal_executor.apply(
                record.model_copy(update={"metadata": metadata}),
                decided_by=decided_by,
                note=note,
            )
            return execution.proposal
        return self._repository.upsert_structure_proposal(
            record.model_copy(
                update={
                    "status": normalized_decision,
                    "metadata": metadata,
                    "updated_at": _utc_now(),
                },
            ),
        )

    def get_industry_profile_version(
        self,
        *,
        industry_instance_id: str,
        version: int,
    ) -> IndustryMemoryProfileRecord | None:
        for item in self.list_industry_profiles(industry_instance_id=industry_instance_id, limit=None):
            if int(getattr(item, "version", 0) or 0) == int(version):
                return item
        return None

    def get_work_context_overlay_version(
        self,
        *,
        work_context_id: str,
        version: int,
    ) -> WorkContextMemoryOverlayRecord | None:
        for item in self.list_work_context_overlays(work_context_id=work_context_id, limit=None):
            if int(getattr(item, "version", 0) or 0) == int(version):
                return item
        return None

    def diff_industry_profile_versions(
        self,
        *,
        industry_instance_id: str,
        from_version: int,
        to_version: int,
    ) -> dict[str, object]:
        left = self.get_industry_profile_version(industry_instance_id=industry_instance_id, version=from_version)
        right = self.get_industry_profile_version(industry_instance_id=industry_instance_id, version=to_version)
        if left is None or right is None:
            raise KeyError(f"industry profile version not found: {industry_instance_id} {from_version}->{to_version}")
        return {
            "scope_type": "industry",
            "scope_id": industry_instance_id,
            "from_version": from_version,
            "to_version": to_version,
            "changes": self._field_changes(
                left=left,
                right=right,
                fields=[
                    "headline",
                    "summary",
                    "strategic_direction",
                    "active_constraints",
                    "active_focuses",
                    "key_entities",
                    "key_relations",
                    "evidence_refs",
                    "status",
                ],
            ),
        }

    def diff_work_context_overlay_versions(
        self,
        *,
        work_context_id: str,
        from_version: int,
        to_version: int,
    ) -> dict[str, object]:
        left = self.get_work_context_overlay_version(work_context_id=work_context_id, version=from_version)
        right = self.get_work_context_overlay_version(work_context_id=work_context_id, version=to_version)
        if left is None or right is None:
            raise KeyError(f"work context overlay version not found: {work_context_id} {from_version}->{to_version}")
        return {
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "from_version": from_version,
            "to_version": to_version,
            "changes": self._field_changes(
                left=left,
                right=right,
                fields=[
                    "headline",
                    "summary",
                    "focus_summary",
                    "active_constraints",
                    "active_focuses",
                    "active_entities",
                    "active_relations",
                    "evidence_refs",
                    "status",
                ],
            ),
        }

    def rollback_industry_profile(
        self,
        *,
        industry_instance_id: str,
        version: int,
        decided_by: str | None = None,
    ) -> IndustryMemoryProfileRecord:
        target = self.get_industry_profile_version(industry_instance_id=industry_instance_id, version=version)
        if target is None:
            raise KeyError(f"industry profile version not found: {industry_instance_id}@v{version}")
        now = _utc_now()
        next_version = len(self.list_industry_profiles(industry_instance_id=industry_instance_id, limit=None)) + 1
        metadata = dict(target.metadata or {})
        metadata["rollback_source_profile_id"] = target.profile_id
        metadata["rollback_source_version"] = version
        metadata["rollback_decided_by"] = str(decided_by or "").strip() or None
        metadata["rollback_applied_at"] = now.isoformat()
        return self._repository.upsert_industry_profile(
            target.model_copy(
                update={
                    "profile_id": f"industry-profile:{industry_instance_id}:v{next_version}",
                    "version": next_version,
                    "status": "active",
                    "metadata": metadata,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        )

    def rollback_work_context_overlay(
        self,
        *,
        work_context_id: str,
        version: int,
        decided_by: str | None = None,
    ) -> WorkContextMemoryOverlayRecord:
        target = self.get_work_context_overlay_version(work_context_id=work_context_id, version=version)
        if target is None:
            raise KeyError(f"work context overlay version not found: {work_context_id}@v{version}")
        now = _utc_now()
        next_version = len(self.list_work_context_overlays(work_context_id=work_context_id, limit=None)) + 1
        metadata = dict(target.metadata or {})
        metadata["rollback_source_overlay_id"] = target.overlay_id
        metadata["rollback_source_version"] = version
        metadata["rollback_decided_by"] = str(decided_by or "").strip() or None
        metadata["rollback_applied_at"] = now.isoformat()
        return self._repository.upsert_work_context_overlay(
            target.model_copy(
                update={
                    "overlay_id": f"overlay:{work_context_id}:v{next_version}",
                    "version": next_version,
                    "status": "active",
                    "metadata": metadata,
                    "created_at": now,
                    "updated_at": now,
                },
            ),
        )

    def rebuild_scope_memory(
        self,
        *,
        scope_type: str,
        scope_id: str,
        trigger_kind: str = "rebuild",
    ) -> dict[str, object]:
        projection = self.refresh_scope_projection(
            scope_type=scope_type,
            scope_id=scope_id,
            trigger_kind=trigger_kind,
        )
        job = None
        if scope_type in {"industry", "work_context"}:
            job = self.run_sleep(
                scope_type=scope_type,
                scope_id=scope_id,
                trigger_kind=trigger_kind,
            )
        return {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "projection": projection,
            "sleep_job": job.model_dump(mode="json") if job is not None else None,
            "industry_profile": (
                self.get_active_industry_profile(scope_id)
                if scope_type == "industry"
                else projection.get("industry_profile")
            ),
            "work_context_overlay": (
                self.get_active_work_context_overlay(scope_id)
                if scope_type == "work_context"
                else projection.get("work_context_overlay")
            ),
            "structure_proposals": self.list_structure_proposals(
                scope_type=scope_type,
                scope_id=scope_id,
                limit=None,
            ),
        }

    def run_sleep(
        self,
        *,
        scope_type: str,
        scope_id: str,
        trigger_kind: str = "manual",
    ) -> MemorySleepJobRecord:
        now = _utc_now()
        normalized_trigger_kind, requested_trigger_kind = _normalize_sleep_job_trigger_kind(trigger_kind)
        running_metadata: dict[str, object] = {"mode": "b-plus"}
        if requested_trigger_kind and requested_trigger_kind != normalized_trigger_kind:
            running_metadata["requested_trigger_kind"] = requested_trigger_kind
        running_job = self._repository.upsert_sleep_job(
            MemorySleepJobRecord(
                scope_type=scope_type,
                scope_id=scope_id,
                trigger_kind=normalized_trigger_kind,
                status="running",
                started_at=now,
                metadata=running_metadata,
            ),
        )
        try:
            knowledge_chunks = self._load_knowledge_chunks(scope_type=scope_type, scope_id=scope_id)
            strategies = self._load_strategies(scope_type=scope_type, scope_id=scope_id)
            self._refresh_graph_projection(scope_type=scope_type, scope_id=scope_id)
            fact_entries = list(self._derived_index_service.list_fact_entries(scope_type=scope_type, scope_id=scope_id, limit=None))
            entity_views = list(self._derived_index_service.list_entity_views(scope_type=scope_type, scope_id=scope_id, limit=None))
            relation_views = list(self._derived_index_service.list_relation_views(scope_type=scope_type, scope_id=scope_id, limit=None))
            scope_state = self.get_scope_state(scope_type=scope_type, scope_id=scope_id)
            resolved_industry_instance_id = self._resolve_scope_industry_instance_id(
                scope_type=scope_type,
                scope_id=scope_id,
                scope_state=scope_state,
                fact_entries=fact_entries,
                knowledge_chunks=knowledge_chunks,
            )
            sleep_query = self._build_sleep_query(
                scope_type=scope_type,
                scope_id=scope_id,
                knowledge_chunks=knowledge_chunks,
                strategies=strategies,
                fact_entries=fact_entries,
            )
            activation_summary = self._build_activation_summary(
                query=sleep_query,
                scope_type=scope_type,
                scope_id=scope_id,
                industry_instance_id=resolved_industry_instance_id,
            )
            graph_focus = self._build_graph_focus(
                query=sleep_query,
                scope_type=scope_type,
                scope_id=scope_id,
                industry_instance_id=resolved_industry_instance_id,
            )
            inferred = self._inference_service.infer(
                scope_type=scope_type,
                scope_id=scope_id,
                knowledge_chunks=knowledge_chunks,
                strategies=strategies,
                fact_entries=fact_entries,
                entity_views=entity_views,
                relation_views=relation_views,
                graph_focus=graph_focus,
                activation_summary=activation_summary,
            )
            self._supersede_existing(scope_type=scope_type, scope_id=scope_id, now=now)
            version = len(self._repository.list_digests(scope_type=scope_type, scope_id=scope_id, limit=None)) + 1
            output_refs: list[str] = []
            digest_payload = dict(inferred.get("digest") or {})
            digest = self._repository.upsert_digest(
                MemoryScopeDigestRecord(
                    digest_id=f"digest:{scope_type}:{scope_id}:v{version}",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    headline=str(digest_payload.get("headline") or f"Memory digest for {scope_type}:{scope_id}"),
                    summary=str(digest_payload.get("summary") or ""),
                    current_constraints=list(digest_payload.get("current_constraints") or []),
                    current_focus=list(digest_payload.get("current_focus") or []),
                    top_entities=list(digest_payload.get("top_entities") or []),
                    top_relations=list(digest_payload.get("top_relations") or []),
                    evidence_refs=list(digest_payload.get("evidence_refs") or []),
                    source_job_id=running_job.job_id,
                    version=version,
                    status="active",
                ),
            )
            output_refs.append(digest.digest_id)
            for index, payload in enumerate(list(inferred.get("alias_maps") or []), start=1):
                record = self._repository.upsert_alias_map(
                    MemoryAliasMapRecord(
                        alias_id=f"alias:{scope_type}:{scope_id}:{_slug(str(payload.get('canonical_term') or index), fallback=str(index))}",
                        scope_type=scope_type,
                        scope_id=scope_id,
                        canonical_term=str(payload.get("canonical_term") or digest.headline),
                        aliases=list(payload.get("aliases") or []),
                        confidence=float(payload.get("confidence", 0.8) or 0.8),
                        evidence_refs=list(digest.evidence_refs or []),
                        source_job_id=running_job.job_id,
                        status="active",
                    ),
                )
                output_refs.append(record.alias_id)
            for index, payload in enumerate(list(inferred.get("merge_results") or []), start=1):
                record = self._repository.upsert_merge_result(
                    MemoryMergeResultRecord(
                        merge_id=f"merge:{scope_type}:{scope_id}:{index}",
                        scope_type=scope_type,
                        scope_id=scope_id,
                        merged_title=str(payload.get("merged_title") or digest.headline),
                        merged_summary=str(payload.get("merged_summary") or digest.summary),
                        merged_source_refs=list(payload.get("merged_source_refs") or []),
                        evidence_refs=list(digest.evidence_refs or []),
                        source_job_id=running_job.job_id,
                        status="active",
                    ),
                )
                output_refs.append(record.merge_id)
            for index, payload in enumerate(list(inferred.get("soft_rules") or []), start=1):
                record = self._repository.upsert_soft_rule(
                    MemorySoftRuleRecord(
                        rule_id=f"rule:{scope_type}:{scope_id}:{_slug(str(payload.get('rule_text') or index), fallback=str(index))}",
                        scope_type=scope_type,
                        scope_id=scope_id,
                        rule_text=str(payload.get("rule_text") or digest.headline),
                        rule_kind=str(payload.get("rule_kind") or "guidance"),
                        evidence_refs=list(digest.evidence_refs or []),
                        hit_count=int(payload.get("hit_count", 1) or 1),
                        day_span=int(payload.get("day_span", 1) or 1),
                        conflict_count=int(payload.get("conflict_count", 0) or 0),
                        risk_level=str(payload.get("risk_level") or "low"),
                        state=_normalize_soft_rule_state(payload.get("state")),
                        source_job_id=running_job.job_id,
                    ),
                )
                output_refs.append(record.rule_id)
            for index, payload in enumerate(list(inferred.get("conflict_proposals") or []), start=1):
                record = self._repository.upsert_conflict_proposal(
                    MemoryConflictProposalRecord(
                        proposal_id=f"proposal:{scope_type}:{scope_id}:{index}",
                        scope_type=scope_type,
                        scope_id=scope_id,
                        proposal_kind=str(payload.get("proposal_kind") or "conflict"),
                        title=str(payload.get("title") or "Memory conflict"),
                        summary=str(payload.get("summary") or ""),
                        conflicting_refs=list(payload.get("conflicting_refs") or []),
                        supporting_refs=list(payload.get("supporting_refs") or []),
                        recommended_action=str(payload.get("recommended_action") or ""),
                        risk_level=str(payload.get("risk_level") or "high"),
                        status=_normalize_conflict_status(payload.get("status")),
                        source_job_id=running_job.job_id,
                    ),
                )
                output_refs.append(record.proposal_id)
            target_industry_instance_id = scope_id if scope_type == "industry" else resolved_industry_instance_id
            slot_candidates = self._dynamic_slot_candidates(
                inferred=inferred,
                scope_type=scope_type,
            )
            if target_industry_instance_id and slot_candidates:
                self._structure_enhancement_service.evaluate_dynamic_slots(
                    industry_instance_id=target_industry_instance_id,
                    candidate_slots=slot_candidates,
                )
            slot_layout = self._structure_enhancement_service.build_slot_layout(
                industry_instance_id=target_industry_instance_id,
                scope_type=scope_type,
                scope_id=scope_id,
                candidate_slots=slot_candidates,
            )
            if scope_type == "industry":
                profile = self._repository.upsert_industry_profile(
                    IndustryMemoryProfileRecord(
                        profile_id=f"industry-profile:{scope_id}:v{len(self.list_industry_profiles(industry_instance_id=scope_id, limit=None)) + 1}",
                        industry_instance_id=scope_id,
                        headline=str(
                            inferred.get("industry_profile", {}).get("headline")
                            or digest.headline
                            or f"Industry profile {scope_id}"
                        ),
                        summary=str(
                            inferred.get("industry_profile", {}).get("summary")
                            or digest.summary
                            or ""
                        ),
                        strategic_direction=str(
                            inferred.get("industry_profile", {}).get("strategic_direction")
                            or digest.current_focus[0]
                            if digest.current_focus
                            else digest.headline
                        ),
                        active_constraints=list(
                            inferred.get("industry_profile", {}).get("active_constraints")
                            or digest.current_constraints
                            or []
                        ),
                        active_focuses=list(
                            inferred.get("industry_profile", {}).get("active_focuses")
                            or digest.current_focus
                            or []
                        ),
                        key_entities=list(
                            inferred.get("industry_profile", {}).get("key_entities")
                            or digest.top_entities
                            or []
                        ),
                        key_relations=list(
                            inferred.get("industry_profile", {}).get("key_relations")
                            or digest.top_relations
                            or []
                        ),
                        evidence_refs=list(digest.evidence_refs or []),
                        source_job_id=running_job.job_id,
                        source_digest_id=digest.digest_id,
                        version=len(self.list_industry_profiles(industry_instance_id=scope_id, limit=None)) + 1,
                        status="active",
                        metadata={
                            "read_order": ["industry_profile", "graph", "evidence"],
                            "graph_focus": graph_focus,
                            "activation_summary": activation_summary,
                            "slot_layout": slot_layout,
                        },
                    ),
                )
                output_refs.append(profile.profile_id)
            else:
                profile = (
                    self.get_active_industry_profile(resolved_industry_instance_id)
                    if resolved_industry_instance_id
                    else None
                )
            overlay = None
            if scope_type == "work_context":
                continuity_candidates = list(inferred.get("continuity_details") or [])
                continuity_candidates.extend(
                    {"detail_key": f"constraint-{index + 1}", "detail_text": text}
                    for index, text in enumerate(list(digest.current_constraints or [])[:4])
                    if str(text or "").strip()
                )
                continuity_candidates.extend(
                    {"detail_key": f"relation-{index + 1}", "detail_text": text}
                    for index, text in enumerate(list(digest.top_relations or [])[:4])
                    if str(text or "").strip()
                )
                continuity_candidates.extend(
                    {"detail_key": f"focus-{index + 1}", "detail_text": text}
                    for index, text in enumerate(list(inferred.get("work_context_overlay", {}).get("active_focuses") or [])[:3])
                    if str(text or "").strip()
                )
                continuity_selection = self._continuity_detail_service.select_strong_details(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    graph_signals={
                        **dict(graph_focus or {}),
                        **dict(activation_summary or {}),
                    },
                    candidate_details=continuity_candidates,
                    industry_instance_id=resolved_industry_instance_id,
                    work_context_id=scope_id,
                    persist=True,
                    source_kind="sleep",
                )
                continuity_anchors = self._continuity_anchor_texts(
                    list(getattr(continuity_selection, "selected_details", []) or []),
                )
                for detail in list(getattr(continuity_selection, "selected_details", []) or []):
                    detail_id = str(getattr(detail, "detail_id", "") or "").strip()
                    if detail_id and detail_id not in output_refs:
                        output_refs.append(detail_id)
                overlay = self._repository.upsert_work_context_overlay(
                    WorkContextMemoryOverlayRecord(
                        overlay_id=f"overlay:{scope_id}:v{len(self.list_work_context_overlays(work_context_id=scope_id, limit=None)) + 1}",
                        work_context_id=scope_id,
                        industry_instance_id=resolved_industry_instance_id,
                        base_profile_id=profile.profile_id if profile is not None else None,
                        headline=str(
                            inferred.get("work_context_overlay", {}).get("headline")
                            or digest.headline
                            or f"Work overlay {scope_id}"
                        ),
                        summary=str(
                            inferred.get("work_context_overlay", {}).get("summary")
                            or digest.summary
                            or ""
                        ),
                        focus_summary=str(
                            inferred.get("work_context_overlay", {}).get("focus_summary")
                            or " / ".join(
                                self._unique_text(
                                    [
                                        *(list(profile.active_constraints[:1]) if profile is not None else []),
                                        *(list(digest.current_constraints or [])[:2]),
                                        *(list(digest.current_focus or [])[:2]),
                                        str(digest.summary or "").strip(),
                                    ],
                                )[:3]
                            ).strip(" /")
                            or digest.summary
                        ),
                        active_constraints=self._unique_text(
                            list(inferred.get("work_context_overlay", {}).get("active_constraints") or [])
                            + list(digest.current_constraints or [])
                            + list(profile.active_constraints if profile is not None else []),
                        ),
                        active_focuses=self._unique_text(
                            list(inferred.get("work_context_overlay", {}).get("active_focuses") or [])
                            + list(digest.current_focus or [])
                            + list(profile.active_focuses if profile is not None else []),
                        ),
                        active_entities=self._unique_text(
                            list(inferred.get("work_context_overlay", {}).get("active_entities") or [])
                            + list(digest.top_entities or []),
                        ),
                        active_relations=self._unique_text(
                            list(inferred.get("work_context_overlay", {}).get("active_relations") or [])
                            + list(digest.top_relations or []),
                        ),
                        evidence_refs=list(digest.evidence_refs or []),
                        source_job_id=running_job.job_id,
                        source_digest_id=digest.digest_id,
                        version=len(self.list_work_context_overlays(work_context_id=scope_id, limit=None)) + 1,
                        status="active",
                        metadata={
                            "read_order": ["work_context_overlay", "industry_profile", "graph", "evidence"],
                            "graph_focus": graph_focus,
                            "activation_summary": activation_summary,
                            "continuity_anchors": continuity_anchors,
                            "slot_layout": slot_layout,
                        },
                    ),
                )
                output_refs.append(overlay.overlay_id)
                self._align_structure_proposals_to_active_truth(
                    scope_id=scope_id,
                    industry_instance_id=resolved_industry_instance_id,
                    profile=profile,
                    overlay=overlay,
                    source_job_id=running_job.job_id,
                    evidence_refs=list(digest.evidence_refs or []),
                    create_if_missing=False,
                )
                structure_payloads = list(inferred.get("structure_proposals") or [])
                if not structure_payloads and overlay.focus_summary:
                    structure_payloads = [
                        {
                            "proposal_kind": "read-order-optimization",
                            "title": f"把{overlay.active_focuses[0] if overlay.active_focuses else '当前焦点'}提升为工作记忆首条",
                            "summary": "当前工作上下文已经形成稳定焦点，建议只调整 overlay 的默认读顺序，不改原始事实。",
                            "recommended_action": "保持事实不变，只调整 overlay 的默认读顺序。",
                            "risk_level": "medium",
                        }
                    ]
                for index, payload in enumerate(structure_payloads, start=1):
                    proposal = self._repository.upsert_structure_proposal(
                        MemoryStructureProposalRecord(
                            proposal_id=f"structure:{scope_type}:{scope_id}:{index}",
                            scope_type=scope_type,
                            scope_id=scope_id,
                            industry_instance_id=resolved_industry_instance_id,
                            work_context_id=scope_id,
                            proposal_kind=str(payload.get("proposal_kind") or "structure"),
                            title=str(payload.get("title") or "Memory structure proposal"),
                            summary=str(payload.get("summary") or ""),
                            recommended_action=str(payload.get("recommended_action") or ""),
                            candidate_profile_id=profile.profile_id if profile is not None else None,
                            candidate_overlay_id=overlay.overlay_id,
                            source_job_id=running_job.job_id,
                            evidence_refs=list(digest.evidence_refs or []),
                            risk_level=str(payload.get("risk_level") or "medium"),
                            status=_normalize_conflict_status(payload.get("status")),
                        ),
                    )
                    output_refs.append(proposal.proposal_id)
                aligned_proposals = self._align_structure_proposals_to_active_truth(
                    scope_id=scope_id,
                    industry_instance_id=resolved_industry_instance_id,
                    profile=profile,
                    overlay=overlay,
                    source_job_id=running_job.job_id,
                    evidence_refs=list(digest.evidence_refs or []),
                )
                for proposal in aligned_proposals:
                    if proposal.proposal_id not in output_refs:
                        output_refs.append(proposal.proposal_id)
            completed_at = _utc_now()
            completed_job = self._repository.upsert_sleep_job(
                running_job.model_copy(
                    update={
                        "status": "completed",
                        "output_refs": output_refs,
                        "completed_at": completed_at,
                        "updated_at": completed_at,
                    },
                ),
            )
            scope_state = self.get_scope_state(scope_type=scope_type, scope_id=scope_id)
            resolved_scope_industry_instance_id = (
                resolved_industry_instance_id
                or (overlay.industry_instance_id if overlay is not None else None)
                or (scope_id if scope_type == "industry" else None)
                or (scope_state.industry_instance_id if scope_state else None)
            )
            self._repository.upsert_scope_state(
                MemorySleepScopeStateRecord(
                    scope_key=f"{scope_type}:{scope_id}",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    owner_agent_id=scope_state.owner_agent_id if scope_state else None,
                    industry_instance_id=resolved_scope_industry_instance_id,
                    is_dirty=False,
                    dirty_reasons=[],
                    dirty_source_refs=[],
                    dirty_count=int(getattr(scope_state, "dirty_count", 0) or 0),
                    first_dirtied_at=scope_state.first_dirtied_at if scope_state else completed_at,
                    last_dirtied_at=scope_state.last_dirtied_at if scope_state else None,
                    last_sleep_job_id=completed_job.job_id,
                    last_sleep_at=completed_at,
                    metadata=dict(getattr(scope_state, "metadata", {}) or {}),
                    created_at=scope_state.created_at if scope_state else completed_at,
                    updated_at=completed_at,
                ),
            )
            return completed_job
        except Exception as exc:
            failed_at = _utc_now()
            failed_metadata = dict(getattr(running_job, "metadata", {}) or {})
            failed_metadata["error"] = str(exc)
            failed_job = self._repository.upsert_sleep_job(
                running_job.model_copy(
                    update={
                        "status": "failed",
                        "completed_at": failed_at,
                        "updated_at": failed_at,
                        "metadata": failed_metadata,
                    },
                ),
            )
            scope_state = self.get_scope_state(scope_type=scope_type, scope_id=scope_id)
            if scope_state is None:
                self._repository.upsert_scope_state(
                    MemorySleepScopeStateRecord(
                        scope_key=f"{scope_type}:{scope_id}",
                        scope_type=scope_type,
                        scope_id=scope_id,
                        is_dirty=True,
                        last_sleep_job_id=failed_job.job_id,
                        created_at=failed_at,
                        updated_at=failed_at,
                    ),
                )
            else:
                self._repository.upsert_scope_state(
                    scope_state.model_copy(
                        update={
                            "is_dirty": True,
                            "last_sleep_job_id": failed_job.job_id,
                            "updated_at": failed_at,
                        },
                    ),
                )
            return failed_job

    def run_due_sleep_jobs(self, *, limit: int | None = None) -> list[MemorySleepJobRecord]:
        return [
            self.run_sleep(scope_type=item.scope_type, scope_id=item.scope_id, trigger_kind="scheduled")
            for item in self._repository.list_scope_states(dirty_only=True, limit=limit)
        ]

    def run_idle_catchup(self, *, limit: int | None = 5) -> list[MemorySleepJobRecord]:
            return [
            self.run_sleep(scope_type=item.scope_type, scope_id=item.scope_id, trigger_kind="idle")
            for item in self._repository.list_scope_states(dirty_only=True, limit=limit)
        ]

    def resolve_scope_overlay(self, *, scope_type: str, scope_id: str) -> dict[str, Any]:
        scope_state = self.get_scope_state(scope_type=scope_type, scope_id=scope_id)
        active_overlay = (
            self.get_active_work_context_overlay(scope_id)
            if scope_type == "work_context"
            else None
        )
        resolved_industry_instance_id = self._resolve_scope_industry_instance_id(
            scope_type=scope_type,
            scope_id=scope_id,
            scope_state=scope_state,
            fact_entries=[],
            knowledge_chunks=[],
        )
        if resolved_industry_instance_id is None and active_overlay is not None:
            resolved_industry_instance_id = str(active_overlay.industry_instance_id or "").strip() or None
        return {
            "digest": self.get_active_digest(scope_type, scope_id),
            "aliases": self.list_alias_maps(scope_type=scope_type, scope_id=scope_id, status="active", limit=None),
            "merges": self.list_merge_results(scope_type=scope_type, scope_id=scope_id, status="active", limit=None),
            "soft_rules": self.list_soft_rules(scope_type=scope_type, scope_id=scope_id, limit=None),
            "conflicts": self.list_conflict_proposals(scope_type=scope_type, scope_id=scope_id, status="pending", limit=None),
            "slot_preferences": (
                self.list_slot_preferences(
                    industry_instance_id=resolved_industry_instance_id or (scope_id if scope_type == "industry" else None),
                    status="active",
                    limit=None,
                )
                if (resolved_industry_instance_id or scope_type == "industry")
                else []
            ),
            "continuity_details": self.list_continuity_details(
                scope_type=scope_type,
                scope_id=scope_id,
                status="active",
                limit=None,
            ),
            "industry_profile": (
                self.get_active_industry_profile(scope_id)
                if scope_type == "industry"
                else (
                    self.get_active_industry_profile(resolved_industry_instance_id)
                    if resolved_industry_instance_id
                    else None
                )
            ),
            "work_context_overlay": (
                active_overlay
                if scope_type == "work_context"
                else None
            ),
            "structure_proposals": self.list_structure_proposals(
                scope_type=scope_type,
                scope_id=scope_id,
                status="pending",
                limit=None,
            ),
        }

    def expand_alias_terms(self, *, scope_type: str, scope_id: str, query: str) -> list[str]:
        terms = [str(query or "").strip()]
        lowered = terms[0].lower()
        for alias_map in self.list_alias_maps(scope_type=scope_type, scope_id=scope_id, status="active", limit=None):
            candidates = [alias_map.canonical_term, *list(alias_map.aliases or [])]
            if any(term.lower() in lowered for term in candidates):
                terms.extend(candidates)
        return _unique(terms)

    def _load_knowledge_chunks(self, *, scope_type: str, scope_id: str) -> list[object]:
        service = self._knowledge_service
        lister = getattr(service, "list_chunks", None)
        if not callable(lister):
            return []
        return list(lister(document_id=f"memory:{scope_type}:{scope_id}", limit=None) or [])

    def _load_strategies(self, *, scope_type: str, scope_id: str) -> list[object]:
        service = self._strategy_memory_service
        lister = getattr(service, "list_strategies", None)
        if not callable(lister):
            return []
        if scope_type not in {"global", "industry"}:
            return []
        return list(lister(scope_type=scope_type, scope_id=scope_id, status="active", limit=None) or [])

    def _load_relation_views(self, *, scope_type: str, scope_id: str) -> list[object]:
        lister = getattr(self._derived_index_service, "list_relation_views", None)
        if not callable(lister):
            return []
        return list(lister(scope_type=scope_type, scope_id=scope_id, limit=None) or [])

    def _build_sleep_query(
        self,
        *,
        scope_type: str,
        scope_id: str,
        knowledge_chunks: list[object],
        strategies: list[object],
        fact_entries: list[object],
    ) -> str:
        return _first_text(
            *[getattr(item, "title", None) for item in strategies[:2]],
            *[
                value
                for item in strategies[:2]
                for value in list(getattr(item, "current_focuses", []) or [])[:2]
            ],
            *[getattr(item, "title", None) for item in knowledge_chunks[:2]],
            *[getattr(item, "title", None) for item in fact_entries[:2]],
            *[getattr(item, "summary", None) for item in fact_entries[:2]],
            f"memory sleep {scope_type} {scope_id}",
        )

    def _build_activation_summary(
        self,
        *,
        query: str,
        scope_type: str,
        scope_id: str,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        activate = getattr(self._knowledge_graph_service, "activate_for_query", None)
        if not callable(activate):
            return {}
        try:
            result = activate(
                query=query,
                scope_type=scope_type,
                scope_id=scope_id,
                industry_instance_id=industry_instance_id,
                current_phase="memory-sleep",
                limit=8,
            )
        except Exception:
            return {}
        if result is None:
            return {}
        return {
            "top_entities": list(getattr(result, "top_entities", []) or []),
            "top_opinions": list(getattr(result, "top_opinions", []) or []),
            "top_relations": list(getattr(result, "top_relations", []) or []),
            "top_constraints": list(getattr(result, "top_constraints", []) or []),
            "top_next_actions": list(getattr(result, "top_next_actions", []) or []),
            "support_refs": list(getattr(result, "support_refs", []) or []),
            "evidence_refs": list(getattr(result, "evidence_refs", []) or []),
            "dependency_paths": self._path_summaries(getattr(result, "dependency_paths", None)),
            "blocker_paths": self._path_summaries(getattr(result, "blocker_paths", None)),
            "recovery_paths": self._path_summaries(getattr(result, "recovery_paths", None)),
        }

    def _build_graph_focus(
        self,
        *,
        query: str,
        scope_type: str,
        scope_id: str,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        activate = getattr(self._knowledge_graph_service, "activate_task_subgraph", None)
        summarize = getattr(self._knowledge_graph_service, "summarize_task_subgraph", None)
        if not callable(activate) or not callable(summarize):
            return {}
        try:
            subgraph = activate(
                query=query,
                scope_type=scope_type,
                scope_id=scope_id,
                industry_instance_id=industry_instance_id,
                current_phase="memory-sleep",
                limit=8,
            )
        except Exception:
            return {}
        summary = summarize(subgraph)
        return dict(summary or {}) if isinstance(summary, dict) else {}

    def _path_summaries(self, paths: object | None) -> list[str]:
        results: list[str] = []
        for item in list(paths or []) if isinstance(paths, list) else []:
            summary = getattr(item, "summary", None)
            if summary is None and isinstance(item, dict):
                summary = item.get("summary")
            text = str(summary or "").strip()
            if text:
                results.append(text)
        return self._unique_text(results)

    def _dynamic_slot_candidates(self, *, inferred: dict[str, Any], scope_type: str) -> list[str]:
        industry_payload = dict(inferred.get("industry_profile") or {})
        overlay_payload = dict(inferred.get("work_context_overlay") or {})
        if scope_type == "industry":
            return self._unique_text(list(industry_payload.get("dynamic_slots") or []))
        return self._unique_text(
            list(overlay_payload.get("dynamic_slots") or [])
            + list(industry_payload.get("dynamic_slots") or []),
        )

    def _continuity_anchor_texts(self, details: list[object]) -> list[str]:
        return self._unique_text(
            [
                _first_text(
                    getattr(item, "detail_text", None),
                    getattr(item, "detail_label", None),
                    getattr(item, "detail_key", None),
                )
                for item in details
            ],
        )

    def _refresh_graph_projection(self, *, scope_type: str, scope_id: str) -> None:
        reflector = getattr(self._reflection_service, "reflect", None)
        if callable(reflector):
            try:
                reflector(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    trigger_kind="memory-sleep",
                    create_learning_proposals=False,
                )
            except Exception:
                pass
        rebuilder = getattr(self._derived_index_service, "rebuild_relation_views", None)
        if callable(rebuilder):
            try:
                rebuilder(scope_type=scope_type, scope_id=scope_id)
            except Exception:
                pass

    def _supersede_existing(self, *, scope_type: str, scope_id: str, now: datetime) -> None:
        for record in self.list_alias_maps(scope_type=scope_type, scope_id=scope_id, status="active", limit=None):
            self._repository.upsert_alias_map(record.model_copy(update={"status": "superseded", "updated_at": now}))
        for record in self.list_merge_results(scope_type=scope_type, scope_id=scope_id, status="active", limit=None):
            self._repository.upsert_merge_result(record.model_copy(update={"status": "superseded", "updated_at": now}))
        for record in self.list_soft_rules(scope_type=scope_type, scope_id=scope_id, limit=None):
            if record.state in {"rejected", "expired"}:
                continue
            self._repository.upsert_soft_rule(record.model_copy(update={"state": "expired", "updated_at": now}))
        for record in self.list_conflict_proposals(scope_type=scope_type, scope_id=scope_id, status="pending", limit=None):
            self._repository.upsert_conflict_proposal(record.model_copy(update={"status": "expired", "updated_at": now}))
        for record in self.list_structure_proposals(scope_type=scope_type, scope_id=scope_id, status="pending", limit=None):
            self._repository.upsert_structure_proposal(record.model_copy(update={"status": "expired", "updated_at": now}))

    def _resolve_scope_industry_instance_id(
        self,
        *,
        scope_type: str,
        scope_id: str,
        scope_state: object | None,
        fact_entries: list[object],
        knowledge_chunks: list[object],
    ) -> str | None:
        if scope_type == "industry":
            return scope_id
        if str(getattr(scope_state, "industry_instance_id", "") or "").strip():
            return str(getattr(scope_state, "industry_instance_id", "") or "").strip()
        for entry in fact_entries:
            value = str(getattr(entry, "industry_instance_id", "") or "").strip()
            if value:
                return value
        for chunk in knowledge_chunks:
            industry_instance_id = _industry_instance_id_from_source_ref(getattr(chunk, "source_ref", None))
            if industry_instance_id:
                return industry_instance_id
        return None

    def _align_structure_proposals_to_active_truth(
        self,
        *,
        scope_id: str,
        industry_instance_id: str | None,
        profile: IndustryMemoryProfileRecord | None,
        overlay: WorkContextMemoryOverlayRecord | None,
        source_job_id: str | None,
        evidence_refs: list[str],
        create_if_missing: bool = True,
    ) -> list[MemoryStructureProposalRecord]:
        active_overlay = self.get_active_work_context_overlay(scope_id) or overlay
        if active_overlay is None:
            return []
        resolved_industry_instance_id = (
            str(active_overlay.industry_instance_id or "").strip()
            or str(industry_instance_id or "").strip()
            or None
        )
        active_profile = (
            self.get_active_industry_profile(resolved_industry_instance_id)
            if resolved_industry_instance_id
            else profile
        )
        desired_profile_id = active_profile.profile_id if active_profile is not None else None
        desired_overlay_id = active_overlay.overlay_id
        pending_proposals = self.list_structure_proposals(
            scope_type="work_context",
            scope_id=scope_id,
            status="pending",
            limit=None,
        )
        if not pending_proposals:
            if not create_if_missing:
                return []
            if not str(active_overlay.focus_summary or "").strip():
                return []
            fallback_proposal = self._repository.upsert_structure_proposal(
                MemoryStructureProposalRecord(
                    proposal_id=f"structure:work_context:{scope_id}:1",
                    scope_type="work_context",
                    scope_id=scope_id,
                    industry_instance_id=resolved_industry_instance_id,
                    work_context_id=scope_id,
                    proposal_kind="read-order-optimization",
                    title="Prefer the active work overlay in recall",
                    summary="Keep the pending structure proposal aligned with the latest active work overlay and profile.",
                    recommended_action="Read the latest active work overlay before older derived candidates.",
                    candidate_profile_id=desired_profile_id,
                    candidate_overlay_id=desired_overlay_id,
                    source_job_id=source_job_id,
                    evidence_refs=list(evidence_refs or active_overlay.evidence_refs or []),
                    risk_level="medium",
                    status="pending",
                    metadata={"alignment_fallback": True},
                ),
            )
            return [fallback_proposal]
        now = _utc_now()
        aligned: list[MemoryStructureProposalRecord] = []
        for proposal in pending_proposals:
            desired_industry_id = (
                resolved_industry_instance_id
                or str(proposal.industry_instance_id or "").strip()
                or None
            )
            if (
                proposal.candidate_overlay_id == desired_overlay_id
                and proposal.candidate_profile_id == desired_profile_id
                and proposal.industry_instance_id == desired_industry_id
            ):
                continue
            metadata = dict(proposal.metadata or {})
            metadata["aligned_to_active_overlay_id"] = desired_overlay_id
            metadata["alignment_source_job_id"] = source_job_id
            if desired_profile_id:
                metadata["aligned_to_active_profile_id"] = desired_profile_id
            aligned.append(
                self._repository.upsert_structure_proposal(
                    proposal.model_copy(
                        update={
                            "industry_instance_id": desired_industry_id,
                            "work_context_id": scope_id,
                            "candidate_profile_id": desired_profile_id,
                            "candidate_overlay_id": desired_overlay_id,
                            "source_job_id": source_job_id or proposal.source_job_id,
                            "evidence_refs": list(proposal.evidence_refs or evidence_refs or active_overlay.evidence_refs or []),
                            "metadata": metadata,
                            "updated_at": now,
                        },
                    ),
                ),
            )
        return aligned

    def _refresh_daytime_industry_profile(
        self,
        *,
        industry_instance_id: str,
        knowledge_chunks: list[object],
        strategies: list[object],
        fact_entries: list[object],
        relation_views: list[object],
        trigger_kind: str,
    ) -> IndustryMemoryProfileRecord | None:
        summary_candidates = self._summary_candidates(
            knowledge_chunks=knowledge_chunks,
            fact_entries=fact_entries,
        )
        title_candidates = self._title_candidates(
            knowledge_chunks=knowledge_chunks,
            fact_entries=fact_entries,
        )
        strategy = strategies[0] if strategies else None
        headline = _first_text(
            getattr(strategy, "title", None),
            title_candidates[0] if title_candidates else None,
            f"Industry baseline for {industry_instance_id}",
        )
        summary = _first_text(
            getattr(strategy, "summary", None),
            " ".join(summary_candidates[:2]),
        )
        strategic_direction = _first_text(
            getattr(strategy, "north_star", None),
            getattr(strategy, "mission", None),
            getattr(strategy, "summary", None),
            summary,
        )
        active_constraints = _unique(
            [
                *list(getattr(strategy, "execution_constraints", []) or []),
                *self._rule_like_relations(relation_views),
                *summary_candidates[:2],
            ],
        )[:6]
        active_focuses = _unique(
            [
                *list(getattr(strategy, "current_focuses", []) or []),
                *title_candidates[:2],
                *summary_candidates[:2],
            ],
        )[:6]
        key_entities = _unique(
            [
                str(getattr(item, "entity_key", "") or "").strip()
                for item in self._load_entity_views(scope_type="industry", scope_id=industry_instance_id)
            ]
            + title_candidates,
        )[:6]
        key_relations = _unique(
            [
                str(getattr(item, "summary", "") or "").strip()
                for item in relation_views
            ]
            + self._rule_like_relations(relation_views),
        )[:6]
        evidence_refs = self._evidence_refs(fact_entries=fact_entries, knowledge_chunks=knowledge_chunks)
        if not any([summary, strategic_direction, active_constraints, active_focuses, key_entities, key_relations, evidence_refs]):
            return self.get_active_industry_profile(industry_instance_id)
        current = self.get_active_industry_profile(industry_instance_id)
        candidate_payload = {
            "industry_instance_id": industry_instance_id,
            "headline": headline,
            "summary": summary,
            "strategic_direction": strategic_direction,
            "active_constraints": active_constraints,
            "active_focuses": active_focuses,
            "key_entities": key_entities,
            "key_relations": key_relations,
            "evidence_refs": evidence_refs,
            "metadata": {
                "projection_kind": "daytime",
                "trigger_kind": trigger_kind,
            },
        }
        if self._industry_profile_matches(current, candidate_payload):
            return current
        version = len(self.list_industry_profiles(industry_instance_id=industry_instance_id, limit=None)) + 1
        return self._repository.upsert_industry_profile(
            IndustryMemoryProfileRecord(
                profile_id=f"industry-profile:{industry_instance_id}:v{version}",
                source_job_id=None,
                source_digest_id=None,
                version=version,
                status="active",
                **candidate_payload,
            ),
        )

    def _refresh_daytime_work_context_overlay(
        self,
        *,
        work_context_id: str,
        industry_instance_id: str | None,
        base_profile: IndustryMemoryProfileRecord | None,
        knowledge_chunks: list[object],
        fact_entries: list[object],
        relation_views: list[object],
        trigger_kind: str,
    ) -> WorkContextMemoryOverlayRecord | None:
        summary_candidates = self._summary_candidates(
            knowledge_chunks=knowledge_chunks,
            fact_entries=fact_entries,
        )
        title_candidates = self._title_candidates(
            knowledge_chunks=knowledge_chunks,
            fact_entries=fact_entries,
        )
        headline = _first_text(
            title_candidates[0] if title_candidates else None,
            summary_candidates[0] if summary_candidates else None,
            f"Work context overlay for {work_context_id}",
        )
        summary = _first_text(
            " ".join(summary_candidates[:2]),
            getattr(base_profile, "summary", None),
        )
        active_constraints = _unique(
            [
                *list(getattr(base_profile, "active_constraints", []) or []),
                *self._rule_like_relations(relation_views),
                *summary_candidates[:2],
            ],
        )[:6]
        active_focuses = _unique(
            [
                *summary_candidates[:3],
                *title_candidates[:2],
                *list(getattr(base_profile, "active_focuses", []) or [])[:2],
            ],
        )[:6]
        focus_summary = _first_text(
            active_focuses[0] if active_focuses else None,
            summary,
            getattr(base_profile, "strategic_direction", None),
        )
        active_entities = _unique(
            [
                str(getattr(item, "entity_key", "") or "").strip()
                for item in self._load_entity_views(scope_type="work_context", scope_id=work_context_id)
            ]
            + title_candidates,
        )[:6]
        active_relations = _unique(
            [
                str(getattr(item, "summary", "") or "").strip()
                for item in relation_views
            ]
            + self._rule_like_relations(relation_views),
        )[:6]
        evidence_refs = self._evidence_refs(fact_entries=fact_entries, knowledge_chunks=knowledge_chunks)
        if not any([summary, focus_summary, active_constraints, active_focuses, active_entities, active_relations, evidence_refs]):
            return self.get_active_work_context_overlay(work_context_id)
        current = self.get_active_work_context_overlay(work_context_id)
        candidate_payload = {
            "work_context_id": work_context_id,
            "industry_instance_id": industry_instance_id,
            "base_profile_id": getattr(base_profile, "profile_id", None),
            "headline": headline,
            "summary": summary,
            "focus_summary": focus_summary,
            "active_constraints": active_constraints,
            "active_focuses": active_focuses,
            "active_entities": active_entities,
            "active_relations": active_relations,
            "evidence_refs": evidence_refs,
            "metadata": {
                "projection_kind": "daytime",
                "trigger_kind": trigger_kind,
            },
        }
        if self._work_context_overlay_matches(current, candidate_payload):
            return current
        version = len(self.list_work_context_overlays(work_context_id=work_context_id, limit=None)) + 1
        return self._repository.upsert_work_context_overlay(
            WorkContextMemoryOverlayRecord(
                overlay_id=f"overlay:{work_context_id}:v{version}",
                source_job_id=None,
                source_digest_id=None,
                version=version,
                status="active",
                **candidate_payload,
            ),
        )

    def _load_entity_views(self, *, scope_type: str, scope_id: str) -> list[object]:
        lister = getattr(self._derived_index_service, "list_entity_views", None)
        if not callable(lister):
            return []
        return list(lister(scope_type=scope_type, scope_id=scope_id, limit=None) or [])

    def _summary_candidates(self, *, knowledge_chunks: list[object], fact_entries: list[object]) -> list[str]:
        ranked: list[tuple[int, str]] = []
        for item in fact_entries:
            text = _first_text(
                getattr(item, "summary", None),
                getattr(item, "content_excerpt", None),
                getattr(item, "content_text", None),
                getattr(item, "content", None),
                getattr(item, "title", None),
            )
            if not text:
                continue
            ranked.append((self._memory_text_priority(item), text))
        for item in knowledge_chunks:
            text = _first_text(
                getattr(item, "summary", None),
                getattr(item, "content", None),
                getattr(item, "title", None),
            )
            if not text:
                continue
            ranked.append((4, text))
        ranked.sort(key=lambda item: (item[0], -len(item[1])))
        return _unique([text for _priority, text in ranked])[:8]

    def _title_candidates(self, *, knowledge_chunks: list[object], fact_entries: list[object]) -> list[str]:
        ranked: list[tuple[int, str]] = []
        for item in fact_entries:
            text = _first_text(
                getattr(item, "title", None),
                getattr(item, "summary", None),
            )
            if not text:
                continue
            ranked.append((self._memory_text_priority(item), text))
        for item in knowledge_chunks:
            text = _first_text(
                getattr(item, "title", None),
                getattr(item, "summary", None),
            )
            if not text:
                continue
            ranked.append((4, text))
        ranked.sort(key=lambda item: (item[0], -len(item[1])))
        return _unique([text for _priority, text in ranked])[:8]

    def _rule_like_relations(self, relation_views: list[object]) -> list[str]:
        return _unique(
            [
                str(getattr(item, "summary", "") or "").strip()
                for item in relation_views
                if str(getattr(item, "summary", "") or "").strip()
            ],
        )[:6]

    def _evidence_refs(self, *, fact_entries: list[object], knowledge_chunks: list[object]) -> list[str]:
        return _unique(
            [
                str(getattr(item, "source_ref", "") or "").strip()
                for item in fact_entries
            ]
            + [
                str(getattr(item, "source_ref", "") or "").strip()
                for item in knowledge_chunks
            ],
        )[:8]

    def _memory_text_priority(self, item: object) -> int:
        metadata = dict(getattr(item, "metadata", {}) or {})
        node_type = str(metadata.get("knowledge_graph_node_type", "") or "").strip().lower()
        title = str(getattr(item, "title", "") or "").strip().lower()
        summary = str(getattr(item, "summary", "") or "").strip().lower()
        if node_type in {"fact", "opinion", "failure_pattern", "recovery_pattern"}:
            return 0
        if node_type in {"report", "runtime_outcome", "event"}:
            return 1
        if "anchor" in title or "anchor" in summary:
            return 3
        if node_type in {"work_context", "assignment", "backlog", "cycle", "evidence"}:
            return 3
        return 2

    def _industry_profile_matches(
        self,
        current: IndustryMemoryProfileRecord | None,
        candidate_payload: dict[str, object],
    ) -> bool:
        if current is None:
            return False
        return (
            current.headline == candidate_payload["headline"]
            and current.summary == candidate_payload["summary"]
            and current.strategic_direction == candidate_payload["strategic_direction"]
            and list(current.active_constraints) == list(candidate_payload["active_constraints"])
            and list(current.active_focuses) == list(candidate_payload["active_focuses"])
            and list(current.key_entities) == list(candidate_payload["key_entities"])
            and list(current.key_relations) == list(candidate_payload["key_relations"])
            and list(current.evidence_refs) == list(candidate_payload["evidence_refs"])
        )

    def _work_context_overlay_matches(
        self,
        current: WorkContextMemoryOverlayRecord | None,
        candidate_payload: dict[str, object],
    ) -> bool:
        if current is None:
            return False
        return (
            current.industry_instance_id == candidate_payload["industry_instance_id"]
            and current.base_profile_id == candidate_payload["base_profile_id"]
            and current.headline == candidate_payload["headline"]
            and current.summary == candidate_payload["summary"]
            and current.focus_summary == candidate_payload["focus_summary"]
            and list(current.active_constraints) == list(candidate_payload["active_constraints"])
            and list(current.active_focuses) == list(candidate_payload["active_focuses"])
            and list(current.active_entities) == list(candidate_payload["active_entities"])
            and list(current.active_relations) == list(candidate_payload["active_relations"])
            and list(current.evidence_refs) == list(candidate_payload["evidence_refs"])
        )

    def _field_changes(
        self,
        *,
        left: object,
        right: object,
        fields: list[str],
    ) -> list[dict[str, object]]:
        changes: list[dict[str, object]] = []
        for field_name in fields:
            left_value = getattr(left, field_name, None)
            right_value = getattr(right, field_name, None)
            if left_value == right_value:
                continue
            changes.append(
                {
                    "field": field_name,
                    "from": left_value,
                    "to": right_value,
                },
            )
        return changes

    def _unique_text(self, values: list[str]) -> list[str]:
        return _unique(values)
