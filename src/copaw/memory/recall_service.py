# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Sequence

from .derived_index_service import (
    build_scope_candidates,
    cosine_similarity,
    hashed_vector,
    selector_matches_scope,
    source_route_for_entry,
    tokenize,
)
from .models import (
    MemoryBackendDescriptor,
    MemoryRecallHit,
    MemoryRecallResponse,
    MemoryScopeSelector,
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


def _scope_score(entry: MemoryFactIndexRecord, selector: MemoryScopeSelector) -> float:
    candidates = build_scope_candidates(selector)
    if not candidates:
        return 0.0
    entry_scope = (entry.scope_type, entry.scope_id)
    if entry_scope not in candidates:
        return -0.2
    if selector.scope_type and selector.scope_id and entry_scope == (
        selector.scope_type,
        selector.scope_id,
    ):
        return 0.35
    return 0.18


def _role_matches(entry: MemoryFactIndexRecord, role: str | None) -> bool:
    normalized_role = str(role or "").strip().lower()
    if not normalized_role or not entry.role_bindings:
        return True
    return normalized_role in {item.lower() for item in entry.role_bindings}


def _entity_query_keys(
    *,
    query_tokens: set[str],
    entity_views: list[Any],
) -> set[str]:
    matched: set[str] = set()
    for view in entity_views:
        entity_key = str(getattr(view, "entity_key", "") or "").strip()
        display_name = str(getattr(view, "display_name", "") or "").strip()
        summary = str(getattr(view, "summary", "") or "").strip()
        haystack = set(tokenize(" ".join(part for part in (entity_key, display_name, summary) if part)))
        if haystack and query_tokens.intersection(haystack):
            matched.add(entity_key)
    return matched


def _opinion_query_keys(
    *,
    query_tokens: set[str],
    opinion_views: list[Any],
) -> set[str]:
    matched: set[str] = set()
    for view in opinion_views:
        opinion_key = str(getattr(view, "opinion_key", "") or "").strip()
        summary = str(getattr(view, "summary", "") or "").strip()
        haystack = set(tokenize(" ".join(part for part in (opinion_key, summary) if part)))
        if haystack and query_tokens.intersection(haystack):
            matched.add(opinion_key)
    return matched


def _lexical_score(
    entry: MemoryFactIndexRecord,
    *,
    query_tokens: set[str],
    query_entity_keys: set[str],
    query_opinion_keys: set[str],
    selector: MemoryScopeSelector,
) -> float:
    if not query_tokens:
        return (
            0.45 * _recency_score(entry)
            + 0.35 * entry.confidence
            + 0.2 * entry.quality_score
            + _scope_score(entry, selector)
        )
    title_tokens = set(tokenize(entry.title))
    summary_tokens = set(tokenize(entry.summary))
    content_tokens = set(tokenize(entry.content_text))
    tag_tokens = set(tokenize(" ".join(entry.tags)))
    entity_tokens = set(entry.entity_keys)
    opinion_tokens = set(entry.opinion_keys)
    score = 0.0
    score += 1.6 * len(query_tokens.intersection(title_tokens))
    score += 1.2 * len(query_tokens.intersection(summary_tokens))
    score += 0.55 * len(query_tokens.intersection(content_tokens))
    score += 0.9 * len(query_tokens.intersection(tag_tokens))
    score += 1.1 * len(query_entity_keys.intersection(entity_tokens))
    score += 1.0 * len(query_opinion_keys.intersection(opinion_tokens))
    score += 0.35 * _recency_score(entry)
    score += 0.28 * entry.confidence
    score += 0.18 * entry.quality_score
    score += _scope_score(entry, selector)
    return score


def _vector_score(
    entry: MemoryFactIndexRecord,
    *,
    query_vector: list[float],
    query_entity_keys: set[str],
    query_opinion_keys: set[str],
    selector: MemoryScopeSelector,
) -> float:
    entry_vector = hashed_vector(
        "\n".join(part for part in (entry.title, entry.summary, entry.content_text) if part),
    )
    score = 2.2 * cosine_similarity(query_vector, entry_vector)
    score += 0.4 * len(query_entity_keys.intersection(set(entry.entity_keys)))
    score += 0.3 * len(query_opinion_keys.intersection(set(entry.opinion_keys)))
    score += 0.3 * _recency_score(entry)
    score += 0.2 * entry.confidence
    score += 0.1 * entry.quality_score
    score += _scope_score(entry, selector)
    return score


@dataclass(slots=True)
class _BackendSelection:
    backend_id: str
    label: str
    available: bool
    reason: str | None = None


class MemoryRecallService:
    """Unified Recall facade over the derived memory index."""

    def __init__(
        self,
        *,
        derived_index_service,
        default_backend: str = "hybrid-local",
        sidecar_backends: Sequence[object] | None = None,
    ) -> None:
        self._derived_index_service = derived_index_service
        self._default_backend = default_backend
        self._local_backends: dict[str, _BackendSelection] = {
            "lexical": _BackendSelection(
                backend_id="lexical",
                label="Lexical",
                available=True,
            ),
            "hybrid-local": _BackendSelection(
                backend_id="hybrid-local",
                label="Hybrid Local",
                available=True,
            ),
            "local-vector": _BackendSelection(
                backend_id="local-vector",
                label="Local Vector",
                available=True,
            ),
        }
        self._sidecar_backends: dict[str, object] = {}
        for backend in list(sidecar_backends or []):
            backend_id = str(getattr(backend, "backend_id", "") or "").strip()
            if backend_id:
                self._sidecar_backends[backend_id] = backend

    def list_backends(self) -> list[MemoryBackendDescriptor]:
        local_descriptors = [
            MemoryBackendDescriptor(
                backend_id=backend.backend_id,
                label=backend.label,
                available=backend.available,
                is_default=backend.backend_id == self._default_backend,
                reason=backend.reason,
            )
            for backend in self._local_backends.values()
        ]
        sidecar_descriptors: list[MemoryBackendDescriptor] = []
        for backend_id, backend in self._sidecar_backends.items():
            descriptor_builder = getattr(backend, "descriptor", None)
            if callable(descriptor_builder):
                descriptor = descriptor_builder(is_default=backend_id == self._default_backend)
                if isinstance(descriptor, MemoryBackendDescriptor):
                    sidecar_descriptors.append(descriptor)
                    continue
            sidecar_descriptors.append(
                MemoryBackendDescriptor(
                    backend_id=backend_id,
                    label=str(getattr(backend, "label", backend_id) or backend_id),
                    available=False,
                    is_default=backend_id == self._default_backend,
                    reason="Sidecar backend does not expose a descriptor",
                ),
            )
        if "qmd" not in self._sidecar_backends:
            sidecar_descriptors.append(
                MemoryBackendDescriptor(
                    backend_id="qmd",
                    label="QMD Sidecar",
                    available=False,
                    is_default=self._default_backend == "qmd",
                    reason="QMD sidecar backend is not configured",
                ),
            )
        if "lancedb" not in self._sidecar_backends:
            sidecar_descriptors.append(
                MemoryBackendDescriptor(
                    backend_id="lancedb",
                    label="LanceDB Sidecar",
                    available=False,
                    is_default=self._default_backend == "lancedb",
                    reason="LanceDB sidecar backend is not configured",
                ),
            )
        return [*local_descriptors, *sidecar_descriptors]

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
        entries = [
            entry
            for entry in self._derived_index_service.list_fact_entries(limit=None)
            if selector_matches_scope(
                selector=selector,
                scope_type=entry.scope_type,
                scope_id=entry.scope_id,
            )
            and _role_matches(entry, role)
        ]
        selected_backend_id = requested_backend or self._default_backend
        fallback_reason: str | None = None

        local_backend = self._local_backends.get(selected_backend_id)
        if local_backend is not None and not local_backend.available:
            fallback_reason = local_backend.reason or (
                f"Backend '{local_backend.backend_id}' is unavailable"
            )
            local_backend = self._local_backends["hybrid-local"]

        if local_backend is None and selected_backend_id in self._sidecar_backends:
            sidecar_backend = self._sidecar_backends[selected_backend_id]
            descriptor = self._describe_sidecar_backend(selected_backend_id)
            if not descriptor.available:
                fallback_reason = descriptor.reason or (
                    f"Backend '{selected_backend_id}' is unavailable"
                )
            else:
                try:
                    recall_call = getattr(sidecar_backend, "recall", None)
                    if callable(recall_call):
                        result = recall_call(
                            query=query,
                            selector=selector,
                            role=role,
                            limit=limit,
                            entries=entries,
                        )
                        if isinstance(result, MemoryRecallResponse):
                            if result.hits:
                                result.backend_requested = requested_backend
                                return result
                            fallback_reason = (
                                f"Backend '{selected_backend_id}' returned no hits, "
                                "falling back to hybrid-local"
                            )
                        else:
                            fallback_reason = (
                                f"Backend '{selected_backend_id}' does not expose a recall method"
                            )
                    else:
                        fallback_reason = (
                            f"Backend '{selected_backend_id}' does not expose a recall method"
                        )
                except Exception as exc:
                    fallback_reason = (
                        f"Backend '{selected_backend_id}' failed: {exc}"
                    )
            local_backend = self._local_backends["hybrid-local"]
        elif local_backend is None:
            if requested_backend:
                fallback_reason = (
                    f"Unknown backend '{requested_backend}', falling back to hybrid-local"
                )
            local_backend = self._local_backends["hybrid-local"]

        query_tokens = set(tokenize(query))
        entity_views = self._derived_index_service.list_entity_views(
            scope_type=scope_type,
            scope_id=scope_id,
            limit=None,
        )
        opinion_views = self._derived_index_service.list_opinion_views(
            scope_type=scope_type,
            scope_id=scope_id,
            limit=None,
        )
        query_entity_keys = _entity_query_keys(
            query_tokens=query_tokens,
            entity_views=entity_views,
        )
        query_opinion_keys = _opinion_query_keys(
            query_tokens=query_tokens,
            opinion_views=opinion_views,
        )
        query_vector = hashed_vector(query) if query_tokens else []

        scored: list[tuple[float, MemoryFactIndexRecord]] = []
        for entry in entries:
            if local_backend.backend_id == "lexical":
                score = _lexical_score(
                    entry,
                    query_tokens=query_tokens,
                    query_entity_keys=query_entity_keys,
                    query_opinion_keys=query_opinion_keys,
                    selector=selector,
                )
            elif local_backend.backend_id == "local-vector":
                score = _vector_score(
                    entry,
                    query_vector=query_vector,
                    query_entity_keys=query_entity_keys,
                    query_opinion_keys=query_opinion_keys,
                    selector=selector,
                )
            else:
                lexical = _lexical_score(
                    entry,
                    query_tokens=query_tokens,
                    query_entity_keys=query_entity_keys,
                    query_opinion_keys=query_opinion_keys,
                    selector=selector,
                )
                vector = _vector_score(
                    entry,
                    query_vector=query_vector,
                    query_entity_keys=query_entity_keys,
                    query_opinion_keys=query_opinion_keys,
                    selector=selector,
                )
                score = 0.58 * lexical + 0.42 * vector
            if score <= 0:
                continue
            scored.append((score, entry))

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].source_updated_at or item[1].updated_at or item[1].created_at,
            ),
            reverse=True,
        )
        hits = [
            self._entry_to_hit(entry=entry, score=score, backend_id=local_backend.backend_id)
            for score, entry in scored[: max(1, int(limit))]
        ]
        return MemoryRecallResponse(
            query=query,
            backend_requested=requested_backend,
            backend_used=local_backend.backend_id,
            fallback_reason=fallback_reason,
            hits=hits,
        )

    def prepare_sidecar_backends(
        self,
        *,
        prewarm_backend_ids: Sequence[str] | None = None,
    ) -> dict[str, str]:
        requested = {
            str(item or "").strip().lower()
            for item in list(prewarm_backend_ids or [])
            if str(item or "").strip()
        }
        results: dict[str, str] = {}
        for backend_id, backend in self._sidecar_backends.items():
            descriptor = self._describe_sidecar_backend(backend_id)
            results[backend_id] = "available" if descriptor.available else "unavailable"
            if backend_id not in requested:
                continue
            warmup = getattr(backend, "warmup", None)
            if not callable(warmup):
                results[backend_id] = "no-warmup"
                continue
            try:
                warmup()
            except Exception:
                results[backend_id] = "failed"
            else:
                results[backend_id] = "ready"
        return results

    def close_sidecar_backends(self) -> None:
        for backend in self._sidecar_backends.values():
            closer = getattr(backend, "close", None)
            if not callable(closer):
                continue
            try:
                closer()
            except Exception:
                continue

    def _describe_sidecar_backend(self, backend_id: str) -> MemoryBackendDescriptor:
        backend = self._sidecar_backends.get(backend_id)
        if backend is None:
            return MemoryBackendDescriptor(
                backend_id=backend_id,
                label=backend_id,
                available=False,
                reason="Sidecar backend is not configured",
            )
        descriptor_builder = getattr(backend, "descriptor", None)
        if callable(descriptor_builder):
            descriptor = descriptor_builder(is_default=backend_id == self._default_backend)
            if isinstance(descriptor, MemoryBackendDescriptor):
                return descriptor
        return MemoryBackendDescriptor(
            backend_id=backend_id,
            label=str(getattr(backend, "label", backend_id) or backend_id),
            available=False,
            is_default=backend_id == self._default_backend,
            reason="Sidecar backend does not expose a descriptor",
        )

    def _entry_to_hit(
        self,
        *,
        entry: MemoryFactIndexRecord,
        score: float,
        backend_id: str,
    ) -> MemoryRecallHit:
        metadata = dict(entry.metadata or {})
        source_ref = metadata.get("source_ref")
        if not isinstance(source_ref, str) or not source_ref.strip():
            source_ref = entry.source_ref
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
            backend=backend_id,
            source_updated_at=entry.source_updated_at,
            metadata=metadata,
        )
