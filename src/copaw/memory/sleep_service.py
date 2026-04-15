# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from ..state import (
    MemoryAliasMapRecord,
    MemoryConflictProposalRecord,
    MemoryMergeResultRecord,
    MemoryScopeDigestRecord,
    MemorySleepJobRecord,
    MemorySleepScopeStateRecord,
    MemorySoftRuleRecord,
)
from .sleep_inference_service import (
    _normalize_conflict_status,
    _normalize_soft_rule_state,
)

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


def _slug(value: str, *, fallback: str) -> str:
    normalized = _SLUG_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return normalized or fallback


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
    ) -> None:
        self._repository = repository
        self._knowledge_service = knowledge_service
        self._strategy_memory_service = strategy_memory_service
        self._derived_index_service = derived_index_service
        self._reflection_service = reflection_service
        self._inference_service = inference_service

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

    def run_sleep(
        self,
        *,
        scope_type: str,
        scope_id: str,
        trigger_kind: str = "manual",
    ) -> MemorySleepJobRecord:
        now = _utc_now()
        running_job = self._repository.upsert_sleep_job(
            MemorySleepJobRecord(
                scope_type=scope_type,
                scope_id=scope_id,
                trigger_kind=trigger_kind,
                status="running",
                started_at=now,
                metadata={"mode": "b-plus"},
            ),
        )
        try:
            knowledge_chunks = self._load_knowledge_chunks(scope_type=scope_type, scope_id=scope_id)
            strategies = self._load_strategies(scope_type=scope_type, scope_id=scope_id)
            self._refresh_graph_projection(scope_type=scope_type, scope_id=scope_id)
            fact_entries = list(self._derived_index_service.list_fact_entries(scope_type=scope_type, scope_id=scope_id, limit=None))
            entity_views = list(self._derived_index_service.list_entity_views(scope_type=scope_type, scope_id=scope_id, limit=None))
            relation_views = list(self._derived_index_service.list_relation_views(scope_type=scope_type, scope_id=scope_id, limit=None))
            inferred = self._inference_service.infer(
                scope_type=scope_type,
                scope_id=scope_id,
                knowledge_chunks=knowledge_chunks,
                strategies=strategies,
                fact_entries=fact_entries,
                entity_views=entity_views,
                relation_views=relation_views,
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
            self._repository.upsert_scope_state(
                MemorySleepScopeStateRecord(
                    scope_key=f"{scope_type}:{scope_id}",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    owner_agent_id=scope_state.owner_agent_id if scope_state else None,
                    industry_instance_id=scope_state.industry_instance_id if scope_state else None,
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
        return {
            "digest": self.get_active_digest(scope_type, scope_id),
            "aliases": self.list_alias_maps(scope_type=scope_type, scope_id=scope_id, status="active", limit=None),
            "merges": self.list_merge_results(scope_type=scope_type, scope_id=scope_id, status="active", limit=None),
            "soft_rules": self.list_soft_rules(scope_type=scope_type, scope_id=scope_id, limit=None),
            "conflicts": self.list_conflict_proposals(scope_type=scope_type, scope_id=scope_id, status="pending", limit=None),
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
