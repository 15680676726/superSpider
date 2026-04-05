# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Callable, Iterable

from .models import (
    DiscoveryActionRequest,
    DiscoveryHit,
    DiscoverySourceAttempt,
    DiscoverySourceChainResult,
    DiscoverySourceSpec,
)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_provider(source: DiscoverySourceSpec) -> str:
    metadata = getattr(source, "metadata", None)
    if isinstance(metadata, dict):
        return (_string(metadata.get("provider")) or "").lower()
    return ""


def _bind_hit_to_source(
    *,
    source: DiscoverySourceSpec,
    hit: DiscoveryHit,
) -> DiscoveryHit:
    payload = hit.to_payload()
    payload["source_id"] = _string(hit.source_id) or source.source_id
    payload["source_kind"] = _string(hit.source_kind) or source.source_kind
    payload["source_alias"] = _string(hit.source_alias) or source.source_id
    return DiscoveryHit.from_payload(payload)


def execute_discovery_action(
    *,
    request: DiscoveryActionRequest,
    source_service: object,
    executor: Callable[[DiscoverySourceSpec, DiscoveryActionRequest], Iterable[DiscoveryHit]],
) -> DiscoverySourceChainResult:
    resolver = getattr(source_service, "resolve_source_profile_for_request", None)
    if callable(resolver):
        profile = resolver(request.source_profile, request)
    else:
        profile = getattr(source_service, "resolve_source_profile")(request.source_profile)
    attempts: list[DiscoverySourceAttempt] = []
    last_error: str | None = None
    saw_empty = False

    for source in profile.sources:
        try:
            provider = _source_provider(source)
            if provider == "offline-cache":
                offline_loader = getattr(source_service, "search_offline_cache", None)
                if callable(offline_loader):
                    raw_hits = list(
                        offline_loader(
                            request=request,
                            source=source,
                        )
                        or []
                    )
                else:
                    raw_hits = []
            else:
                raw_hits = list(executor(source, request) or [])
        except Exception as exc:  # pragma: no cover - exercised by tests
            last_error = _string(exc) or exc.__class__.__name__
            record_failure = getattr(source_service, "record_source_failure", None)
            if callable(record_failure):
                record_failure(
                    profile_name=profile.profile_name,
                    source_id=source.source_id,
                    error=last_error,
                )
            attempts.append(
                DiscoverySourceAttempt(
                    source_id=source.source_id,
                    chain_role=source.chain_role,
                    status="failed",
                    error=last_error,
                ),
            )
            continue

        if not raw_hits:
            saw_empty = True
            record_empty = getattr(source_service, "record_source_empty", None)
            if callable(record_empty):
                record_empty(
                    profile_name=profile.profile_name,
                    source_id=source.source_id,
                )
            attempts.append(
                DiscoverySourceAttempt(
                    source_id=source.source_id,
                    chain_role=source.chain_role,
                    status="empty",
                ),
            )
            continue

        discovery_hits = tuple(
            _bind_hit_to_source(source=source, hit=hit)
            for hit in raw_hits
        )
        record_success = getattr(source_service, "record_source_success", None)
        if callable(record_success):
            record_success(
                profile_name=profile.profile_name,
                source_id=source.source_id,
                discovery_hits=discovery_hits,
            )
        attempts.append(
            DiscoverySourceAttempt(
                source_id=source.source_id,
                chain_role=source.chain_role,
                status="succeeded",
            ),
        )
        return DiscoverySourceChainResult(
            action_id=request.action_id,
            source_profile=profile.profile_name,
            status="ok",
            active_source_id=source.source_id,
            discovery_hits=discovery_hits,
            attempts=tuple(attempts),
            used_snapshot=False,
        )

    get_snapshot = getattr(source_service, "get_last_known_good_snapshot", None)
    snapshot = get_snapshot(profile.profile_name) if callable(get_snapshot) else None
    return DiscoverySourceChainResult(
        action_id=request.action_id,
        source_profile=profile.profile_name,
        status="degraded" if snapshot is not None or last_error is not None else "empty" if saw_empty else "degraded",
        active_source_id=getattr(snapshot, "source_id", None),
        discovery_hits=tuple(getattr(snapshot, "discovery_hits", ()) or ()),
        attempts=tuple(attempts),
        used_snapshot=snapshot is not None,
        error_summary=last_error,
    )
