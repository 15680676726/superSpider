# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class _StablePrefixCacheEntry:
    signature: str
    prefix: str


@dataclass(slots=True)
class _ScopeSnapshotCacheEntry:
    signature: str
    body: str
    dirty: bool = False


@dataclass(slots=True)
class MainBrainPromptContext:
    stable_prefix: str
    scope_snapshot: str
    scope_key: str
    stable_signature: str
    scope_signature: str
    stable_cache_hit: bool
    scope_cache_hit: bool


class MainBrainScopeSnapshotService:
    def __init__(
        self,
        *,
        stable_prefix_builder: Callable[..., str],
        stable_prefix_signature_builder: Callable[..., str],
        scope_snapshot_builder: Callable[..., str],
        scope_snapshot_signature_builder: Callable[..., str],
        scope_key_resolver: Callable[..., str],
        owner: object | None = None,
    ) -> None:
        self._stable_prefix_builder = stable_prefix_builder
        self._stable_prefix_signature_builder = stable_prefix_signature_builder
        self._scope_snapshot_builder = scope_snapshot_builder
        self._scope_snapshot_signature_builder = scope_snapshot_signature_builder
        self._scope_key_resolver = scope_key_resolver
        self._owner = owner
        self._stable_prefix_cache: dict[tuple[str, str], _StablePrefixCacheEntry] = {}
        self._scope_snapshot_cache: dict[str, _ScopeSnapshotCacheEntry] = {}
        self.calls: list[str] = []

    def set_owner(self, owner: object | None) -> None:
        self._owner = owner

    def resolve_prompt_context(
        self,
        *,
        request: Any,
        detail: object | None,
        owner_agent_id: str | None,
    ) -> MainBrainPromptContext:
        session_id = str(getattr(request, "session_id", "") or "").strip()
        user_id = str(getattr(request, "user_id", "") or "").strip()
        session_key = (session_id, user_id)
        stable_signature = self._call_builder(
            self._stable_prefix_signature_builder,
            request=request,
            detail=detail,
            owner_agent_id=owner_agent_id,
        )
        stable_entry = self._stable_prefix_cache.get(session_key)
        stable_cache_hit = (
            stable_entry is not None and stable_entry.signature == stable_signature
        )
        if stable_entry is None or stable_entry.signature != stable_signature:
            stable_prefix = self._call_builder(
                self._stable_prefix_builder,
                request=request,
                detail=detail,
                owner_agent_id=owner_agent_id,
            )
            self._stable_prefix_cache[session_key] = _StablePrefixCacheEntry(
                signature=stable_signature,
                prefix=stable_prefix,
            )
        else:
            stable_prefix = stable_entry.prefix

        scope_key = self._call_builder(
            self._scope_key_resolver,
            request=request,
            detail=detail,
            owner_agent_id=owner_agent_id,
        )
        scope_signature = self._call_builder(
            self._scope_snapshot_signature_builder,
            request=request,
            detail=detail,
            owner_agent_id=owner_agent_id,
        )
        scope_entry = self._scope_snapshot_cache.get(scope_key)
        scope_cache_hit = (
            scope_entry is not None
            and scope_entry.signature == scope_signature
            and not scope_entry.dirty
        )
        if (
            scope_entry is None
            or scope_entry.signature != scope_signature
            or scope_entry.dirty
        ):
            self.calls.append(scope_key)
            scope_snapshot = self._call_builder(
                self._scope_snapshot_builder,
                request=request,
                detail=detail,
                owner_agent_id=owner_agent_id,
            )
            self._scope_snapshot_cache[scope_key] = _ScopeSnapshotCacheEntry(
                signature=scope_signature,
                body=scope_snapshot,
                dirty=False,
            )
        else:
            scope_snapshot = scope_entry.body
        return MainBrainPromptContext(
            stable_prefix=stable_prefix,
            scope_snapshot=scope_snapshot,
            scope_key=scope_key,
            stable_signature=stable_signature,
            scope_signature=scope_signature,
            stable_cache_hit=stable_cache_hit,
            scope_cache_hit=scope_cache_hit,
        )

    def mark_scope_dirty(
        self,
        *,
        scope_level: str | None = None,
        scope_id: str | None = None,
    ) -> None:
        if not scope_level or not scope_id:
            for entry in self._scope_snapshot_cache.values():
                entry.dirty = True
            return
        normalized_level = str(scope_level).strip().lower()
        normalized_id = str(scope_id).strip()
        if not normalized_id:
            for entry in self._scope_snapshot_cache.values():
                entry.dirty = True
            return
        candidate_keys = {normalized_id}
        if normalized_level in {"industry", "industry_scope"}:
            candidate_keys.add(f"industry:{normalized_id}")
        if normalized_level in {"agent", "role_scope"}:
            candidate_keys.add(f"agent:{normalized_id}")
        if normalized_level in {"global", "runtime"}:
            candidate_keys.add("global:runtime")
        for key in candidate_keys:
            entry = self._scope_snapshot_cache.get(key)
            if entry is not None:
                entry.dirty = True

    def mark_dirty(
        self,
        *,
        work_context_id: str | None = None,
        industry_instance_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        if not any((work_context_id, industry_instance_id, agent_id)):
            self.mark_scope_dirty(scope_level=None, scope_id=None)
            return
        if work_context_id:
            self.mark_scope_dirty(scope_level="work_context", scope_id=work_context_id)
        if industry_instance_id:
            self.mark_scope_dirty(
                scope_level="industry_scope",
                scope_id=industry_instance_id,
            )
        if agent_id:
            self.mark_scope_dirty(scope_level="agent", scope_id=agent_id)

    def _call_builder(self, builder: Callable[..., str], **kwargs: Any) -> str:
        if self._owner is not None:
            try:
                return builder(self._owner, **kwargs)
            except TypeError:
                pass
        return builder(**kwargs)


__all__ = ["MainBrainPromptContext", "MainBrainScopeSnapshotService"]
