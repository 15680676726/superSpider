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
        )

    def mark_dirty(
        self,
        *,
        work_context_id: str | None = None,
        industry_instance_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        candidate_keys = {
            str(work_context_id or "").strip(),
            f"industry:{str(industry_instance_id or '').strip()}",
            f"agent:{str(agent_id or '').strip()}",
            "global:runtime",
        }
        for key in candidate_keys:
            if not key:
                continue
            entry = self._scope_snapshot_cache.get(key)
            if entry is not None:
                entry.dirty = True

    def _call_builder(self, builder: Callable[..., str], **kwargs: Any) -> str:
        if self._owner is not None:
            try:
                return builder(self._owner, **kwargs)
            except TypeError:
                pass
        return builder(**kwargs)


__all__ = ["MainBrainPromptContext", "MainBrainScopeSnapshotService"]
