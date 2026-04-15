# -*- coding: utf-8 -*-
from __future__ import annotations

from .derived_index_service import source_route_for_entry, tokenize
from .models import (
    MemoryBackendDescriptor,
    MemoryRecallHit,
    MemoryRecallResponse,
    MemoryScopeSelector,
)
from .profile_service import MemoryProfileService
from .retrieval_budget import (
    activation_fetch_limit,
    clamp_recall_hit_limit,
    ordered_scope_chain,
    scope_priority_boost,
)
from ..state import MemoryFactIndexRecord


def _age_days(entry: MemoryFactIndexRecord) -> float:
    timestamp = entry.source_updated_at or entry.updated_at or entry.created_at
    if timestamp is None:
        return 9999.0
    return max(0.0, (timestamp.now(tz=timestamp.tzinfo) - timestamp).total_seconds() / 86400.0)


def _recency_score(entry: MemoryFactIndexRecord) -> float:
    age_days = _age_days(entry)
    return 1.0 / (1.0 + age_days / 30.0)


def _role_matches(entry: MemoryFactIndexRecord, role: str | None) -> bool:
    normalized_role = str(role or "").strip().lower()
    if not normalized_role or not entry.role_bindings:
        return True
    return normalized_role in {item.lower() for item in entry.role_bindings}


def _resolve_scope(selector: MemoryScopeSelector) -> tuple[str, str]:
    if selector.scope_type and selector.scope_id:
        return str(selector.scope_type).strip(), str(selector.scope_id).strip()
    for scope_type, scope_id in (
        ("work_context", selector.work_context_id),
        ("task", selector.task_id),
        ("agent", selector.agent_id),
        ("industry", selector.industry_instance_id),
        ("global", selector.global_scope_id),
    ):
        normalized_scope_id = str(scope_id or "").strip()
        if normalized_scope_id:
            return scope_type, normalized_scope_id
    return "global", "runtime"


def _text_score(text: str, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = set(tokenize(text))
    if not text_tokens:
        return 0.0
    return float(len(query_tokens.intersection(text_tokens)))


def _sleep_value(item: object, field_name: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(field_name, default)
    return getattr(item, field_name, default)


class MemoryRecallService:
    """Truth-first recall over shared profile/latest/history memory views."""

    def __init__(
        self,
        *,
        derived_index_service,
        default_backend: str = "truth-first",
        memory_sleep_service: object | None = None,
    ) -> None:
        self._derived_index_service = derived_index_service
        self._default_backend = "truth-first"
        self._profile_service = MemoryProfileService(
            derived_index_service=derived_index_service,
            memory_sleep_service=memory_sleep_service,
        )
        self._memory_sleep_service = memory_sleep_service

    def set_memory_sleep_service(self, memory_sleep_service: object | None) -> None:
        self._memory_sleep_service = memory_sleep_service
        setter = getattr(self._profile_service, "set_memory_sleep_service", None)
        if callable(setter):
            setter(memory_sleep_service)

    def list_backends(self) -> list[MemoryBackendDescriptor]:
        return [
            MemoryBackendDescriptor(
                backend_id=self._default_backend,
                label="Truth-First Shared Memory",
                available=True,
                is_default=True,
                metadata={
                    "order": ["profile", "latest", "history", "lexical"],
                },
            ),
        ]

    def recall(
        self,
        *,
        query: str,
        role: str | None = None,
        backend: str | None = None,
        limit: int = 8,
        scope_type: str | None = None,
        scope_id: str | None = None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        global_scope_id: str | None = None,
        include_related_scopes: bool = True,
    ) -> MemoryRecallResponse:
        selector = MemoryScopeSelector(
            scope_type=scope_type,
            scope_id=scope_id,
            task_id=task_id,
            work_context_id=work_context_id,
            agent_id=agent_id,
            industry_instance_id=industry_instance_id,
            global_scope_id=global_scope_id,
            include_related_scopes=include_related_scopes,
        )
        requested_backend = str(backend or "").strip().lower() or None
        resolved_scope_type, resolved_scope_id = _resolve_scope(selector)
        hit_limit = clamp_recall_hit_limit(limit)
        query_tokens = self._resolve_query_tokens(
            query=query,
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
        )
        entries = self._collect_budgeted_entries(
            selector=selector,
            role=role,
            per_scope_limit=activation_fetch_limit(hit_limit),
        )
        views = self._profile_service.build_views(
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
            role=role,
            selector=selector,
            entries=entries,
        )
        fallback_reason = None
        if requested_backend and requested_backend != self._default_backend:
            fallback_reason = (
                f"Backend '{requested_backend}' is not part of the formal runtime contract; "
                "using truth-first shared memory."
            )

        hits: list[tuple[float, MemoryRecallHit]] = []
        profile_text = views.profile.as_text()
        if profile_text:
            profile_score = 100.0 + _text_score(profile_text, query_tokens)
            profile_score += scope_priority_boost(
                selector=selector,
                scope_type=views.profile.scope_type,
                scope_id=views.profile.scope_id,
            )
            hits.append(
                (
                    profile_score,
                    MemoryRecallHit(
                        entry_id=f"profile:{views.profile.scope_type}:{views.profile.scope_id}",
                        kind="memory_profile",
                        title="Shared Memory Profile",
                        summary=views.profile.current_focus_summary or "Shared truth-derived memory profile.",
                        content_excerpt=profile_text[:320],
                        source_type="memory_profile",
                        source_ref=f"profile:{views.profile.scope_type}:{views.profile.scope_id}",
                        source_route=None,
                        scope_type=views.profile.scope_type,
                        scope_id=views.profile.scope_id,
                        evidence_refs=[],
                        entity_keys=[],
                        opinion_keys=[],
                        confidence=1.0,
                        quality_score=1.0,
                        score=profile_score,
                        backend=self._default_backend,
                        metadata={
                            "static_profile": list(views.profile.static_profile),
                            "dynamic_profile": list(views.profile.dynamic_profile),
                            "active_preferences": list(views.profile.active_preferences),
                            "active_constraints": list(views.profile.active_constraints),
                            "current_operating_context": list(views.profile.current_operating_context),
                            "source_refs": list(views.profile.source_refs),
                            "read_layer": views.profile.read_layer,
                            "overlay_id": views.profile.overlay_id,
                            "industry_profile_id": views.profile.industry_profile_id,
                        },
                    ),
                ),
            )

        self._append_sleep_hits(
            hits=hits,
            query_tokens=query_tokens,
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
        )

        for entry in views.latest:
            if not _role_matches(entry, role):
                continue
            score = 40.0 + _text_score(
                "\n".join(part for part in (entry.title, entry.summary, entry.content_text) if part),
                query_tokens,
            )
            score += 6.0 * _recency_score(entry)
            score += scope_priority_boost(
                selector=selector,
                scope_type=entry.scope_type,
                scope_id=entry.scope_id,
            )
            hits.append((score, self._entry_to_hit(entry=entry, score=score)))

        for entry in views.history:
            if not _role_matches(entry, role):
                continue
            score = 10.0 + _text_score(
                "\n".join(part for part in (entry.title, entry.summary, entry.content_text) if part),
                query_tokens,
            )
            score += 3.0 * _recency_score(entry)
            score += scope_priority_boost(
                selector=selector,
                scope_type=entry.scope_type,
                scope_id=entry.scope_id,
            )
            hits.append((score, self._entry_to_hit(entry=entry, score=score)))

        hits.sort(
            key=lambda item: (
                item[0],
                item[1].source_updated_at,
            ),
            reverse=True,
        )
        limited_hits = [hit for _score, hit in hits[:hit_limit]]
        return MemoryRecallResponse(
            query=query,
            backend_requested=requested_backend,
            backend_used=self._default_backend,
            fallback_reason=fallback_reason,
            hits=limited_hits,
        )

    def _resolve_query_tokens(
        self,
        *,
        query: str,
        scope_type: str,
        scope_id: str,
    ) -> set[str]:
        sleep_service = self._memory_sleep_service
        expand_alias_terms = getattr(sleep_service, "expand_alias_terms", None)
        expanded_query = str(query or "").strip()
        if callable(expand_alias_terms):
            try:
                expanded_terms = expand_alias_terms(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    query=expanded_query,
                )
            except Exception:
                expanded_terms = []
            if expanded_terms:
                expanded_query = " ".join(str(item or "").strip() for item in expanded_terms if str(item or "").strip())
        return set(tokenize(expanded_query))

    def _append_sleep_hits(
        self,
        *,
        hits: list[tuple[float, MemoryRecallHit]],
        query_tokens: set[str],
        scope_type: str,
        scope_id: str,
    ) -> None:
        sleep_service = self._memory_sleep_service
        resolve_scope_overlay = getattr(sleep_service, "resolve_scope_overlay", None)
        if not callable(resolve_scope_overlay):
            return
        try:
            overlay = resolve_scope_overlay(scope_type=scope_type, scope_id=scope_id)
        except Exception:
            return
        if not isinstance(overlay, dict):
            return

        digest = overlay.get("digest")
        if digest is not None:
            title = str(_sleep_value(digest, "headline", "") or "").strip() or "Sleep Digest"
            summary = str(_sleep_value(digest, "summary", "") or "").strip()
            content = "\n".join(
                [
                    title,
                    summary,
                    *list(_sleep_value(digest, "current_constraints", []) or []),
                    *list(_sleep_value(digest, "current_focus", []) or []),
                ],
            )
            score = 90.0 + _text_score(content, query_tokens)
            hits.append(
                (
                    score,
                    MemoryRecallHit(
                        entry_id=str(_sleep_value(digest, "digest_id", f"digest:{scope_type}:{scope_id}") or ""),
                        kind="memory_sleep_digest",
                        title=title,
                        summary=summary,
                        content_excerpt=content[:320],
                        source_type="memory_sleep_digest",
                        source_ref=str(_sleep_value(digest, "digest_id", f"digest:{scope_type}:{scope_id}") or ""),
                        scope_type=scope_type,
                        scope_id=scope_id,
                        evidence_refs=list(_sleep_value(digest, "evidence_refs", []) or []),
                        entity_keys=list(_sleep_value(digest, "top_entities", []) or []),
                        confidence=0.92,
                        quality_score=0.9,
                        score=score,
                        backend=self._default_backend,
                        metadata={"layer": "sleep"},
                    ),
                ),
            )

        for merge in list(overlay.get("merges") or []):
            title = str(_sleep_value(merge, "merged_title", "") or "").strip()
            summary = str(_sleep_value(merge, "merged_summary", "") or "").strip()
            content = "\n".join([title, summary])
            score = 85.0 + _text_score(content, query_tokens)
            hits.append(
                (
                    score,
                    MemoryRecallHit(
                        entry_id=str(_sleep_value(merge, "merge_id", title or "merge") or ""),
                        kind="memory_merge_result",
                        title=title or "Merged Memory Topic",
                        summary=summary,
                        content_excerpt=content[:320],
                        source_type="memory_merge_result",
                        source_ref=str(_sleep_value(merge, "merge_id", title or "merge") or ""),
                        scope_type=scope_type,
                        scope_id=scope_id,
                        evidence_refs=list(_sleep_value(merge, "evidence_refs", []) or []),
                        confidence=0.85,
                        quality_score=0.84,
                        score=score,
                        backend=self._default_backend,
                        metadata={"layer": "sleep"},
                    ),
                ),
            )

        for rule in list(overlay.get("soft_rules") or []):
            title = str(_sleep_value(rule, "rule_text", "") or "").strip()
            score = 82.0 + _text_score(title, query_tokens)
            hits.append(
                (
                    score,
                    MemoryRecallHit(
                        entry_id=str(_sleep_value(rule, "rule_id", title or "rule") or ""),
                        kind="memory_soft_rule",
                        title=title or "Soft Rule",
                        summary=title,
                        content_excerpt=title[:320],
                        source_type="memory_soft_rule",
                        source_ref=str(_sleep_value(rule, "rule_id", title or "rule") or ""),
                        scope_type=scope_type,
                        scope_id=scope_id,
                        evidence_refs=list(_sleep_value(rule, "evidence_refs", []) or []),
                        confidence=0.83,
                        quality_score=0.82,
                        score=score,
                        backend=self._default_backend,
                        metadata={"layer": "sleep", "state": _sleep_value(rule, "state", None)},
                    ),
                ),
            )

        for conflict in list(overlay.get("conflicts") or []):
            title = str(_sleep_value(conflict, "title", "") or "").strip()
            summary = str(_sleep_value(conflict, "summary", "") or "").strip()
            score = 78.0 + _text_score("\n".join([title, summary]), query_tokens)
            hits.append(
                (
                    score,
                    MemoryRecallHit(
                        entry_id=str(_sleep_value(conflict, "proposal_id", title or "conflict") or ""),
                        kind="memory_conflict_proposal",
                        title=title or "Memory Conflict",
                        summary=summary,
                        content_excerpt=summary[:320],
                        source_type="memory_conflict_proposal",
                        source_ref=str(_sleep_value(conflict, "proposal_id", title or "conflict") or ""),
                        scope_type=scope_type,
                        scope_id=scope_id,
                        evidence_refs=list(_sleep_value(conflict, "supporting_refs", []) or []),
                        confidence=0.75,
                        quality_score=0.78,
                        score=score,
                        backend=self._default_backend,
                        metadata={"layer": "sleep", "status": _sleep_value(conflict, "status", None)},
                    ),
                ),
            )

    def _collect_budgeted_entries(
        self,
        *,
        selector: MemoryScopeSelector,
        role: str | None,
        per_scope_limit: int,
    ) -> list[MemoryFactIndexRecord]:
        getter = getattr(self._derived_index_service, "list_fact_entries", None)
        if not callable(getter):
            return []
        entries: list[MemoryFactIndexRecord] = []
        seen_ids: set[str] = set()
        for scope_type, scope_id in ordered_scope_chain(selector):
            scoped_entries = list(
                getter(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    limit=per_scope_limit,
                )
                or [],
            )
            for entry in scoped_entries:
                entry_id = str(getattr(entry, "id", "") or "")
                if entry_id and entry_id in seen_ids:
                    continue
                if not _role_matches(entry, role):
                    continue
                if entry_id:
                    seen_ids.add(entry_id)
                entries.append(entry)
        return entries

    def _entry_to_hit(
        self,
        *,
        entry: MemoryFactIndexRecord,
        score: float,
    ) -> MemoryRecallHit:
        metadata = dict(entry.metadata or {})
        source_ref = metadata.get("source_ref")
        if not isinstance(source_ref, str) or not source_ref.strip():
            source_ref = entry.source_ref
        source_ref = str(source_ref or "").strip() or entry.source_ref
        metadata["source_ref"] = source_ref
        metadata.setdefault("scope_type", entry.scope_type)
        metadata.setdefault("scope_id", entry.scope_id)
        return MemoryRecallHit(
            entry_id=entry.id,
            kind=entry.source_type,
            title=entry.title,
            summary=entry.summary,
            content_excerpt=entry.content_excerpt,
            source_type=entry.source_type,
            source_ref=source_ref,
            source_route=source_route_for_entry(entry),
            scope_type=entry.scope_type,
            scope_id=entry.scope_id,
            owner_agent_id=entry.owner_agent_id,
            owner_scope=entry.owner_scope,
            industry_instance_id=entry.industry_instance_id,
            evidence_refs=list(entry.evidence_refs or []),
            entity_keys=list(entry.entity_keys or []),
            opinion_keys=list(entry.opinion_keys or []),
            confidence=entry.confidence,
            quality_score=entry.quality_score,
            score=max(0.0, score),
            backend=self._default_backend,
            source_updated_at=entry.source_updated_at,
            metadata=metadata,
        )
