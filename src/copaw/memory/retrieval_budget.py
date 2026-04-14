# -*- coding: utf-8 -*-
from __future__ import annotations

from .models import MemoryScopeSelector

_MAX_RECALL_HITS = 8
_MIN_FETCH_LIMIT = 4
_MAX_FETCH_LIMIT = 8
_MAX_SURFACE_LIMIT = 8


def clamp_recall_hit_limit(limit: int) -> int:
    requested = int(limit or 0)
    if requested <= 0:
        return 1
    return min(requested, _MAX_RECALL_HITS)


def activation_fetch_limit(limit: int) -> int:
    requested = int(limit or 0)
    if requested <= 0:
        return _MIN_FETCH_LIMIT
    return min(max(requested * 2, _MIN_FETCH_LIMIT), _MAX_FETCH_LIMIT)


def surface_snapshot_limit(limit: int) -> int:
    requested = int(limit or 0)
    if requested <= 0:
        return _MIN_FETCH_LIMIT
    return min(max(requested, 1), _MAX_SURFACE_LIMIT)


def ordered_scope_chain(selector: MemoryScopeSelector) -> list[tuple[str, str]]:
    chain: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(scope_type: str | None, scope_id: str | None) -> None:
        normalized_scope_type = str(scope_type or "").strip().lower()
        normalized_scope_id = str(scope_id or "").strip()
        if not normalized_scope_type or not normalized_scope_id:
            return
        scope_ref = (normalized_scope_type, normalized_scope_id)
        if scope_ref in seen:
            return
        seen.add(scope_ref)
        chain.append(scope_ref)

    if selector.scope_type and selector.scope_id:
        _add(selector.scope_type, selector.scope_id)
        if not selector.include_related_scopes:
            return chain
    elif not selector.include_related_scopes:
        return chain

    if selector.include_related_scopes:
        for scope_type, scope_id in (
            ("work_context", selector.work_context_id),
            ("task", selector.task_id),
            ("agent", selector.agent_id),
            ("industry", selector.industry_instance_id),
            ("global", selector.global_scope_id or "runtime"),
        ):
            _add(scope_type, scope_id)

    if not chain:
        _add("global", selector.global_scope_id or "runtime")
    return chain


def scope_priority_boost(
    *,
    selector: MemoryScopeSelector,
    scope_type: str,
    scope_id: str,
) -> float:
    chain = ordered_scope_chain(selector)
    for index, scope_ref in enumerate(chain):
        if scope_ref == (str(scope_type or "").strip().lower(), str(scope_id or "").strip()):
            return float(max(len(chain) - index, 1) * 6)
    return 0.0
