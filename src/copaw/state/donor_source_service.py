# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from ..discovery.models import (
    DiscoveryHit,
    DiscoverySnapshot,
    DiscoverySourceProfile,
    DiscoverySourceSpec,
    _utc_now,
)
from .models_capability_evolution import CapabilitySourceProfileRecord
from .store import SQLiteStateStore


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_load_dict(value: object | None) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_DISCOVERY_PROFILE_TYPE = "discovery-source"


def _env_url(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def _default_discovery_source_profiles() -> dict[str, tuple[DiscoverySourceSpec, ...]]:
    github_endpoint = _env_url(
        "COPAW_DISCOVERY_GITHUB_SEARCH_URL",
        "https://api.github.com/search/repositories",
    )
    skillhub_endpoint = _env_url(
        "COPAW_DISCOVERY_SKILLHUB_SEARCH_URL",
        "https://lightmake.site/api/v1/search",
    )
    mcp_registry_endpoint = _env_url(
        "COPAW_DISCOVERY_MCP_REGISTRY_URL",
        "https://registry.modelcontextprotocol.io",
    )
    china_github_endpoint = _env_url(
        "COPAW_DISCOVERY_CHINA_GITHUB_SEARCH_URL",
        github_endpoint,
    )
    china_skillhub_endpoint = _env_url(
        "COPAW_DISCOVERY_CHINA_SKILLHUB_SEARCH_URL",
        skillhub_endpoint,
    )
    china_mcp_endpoint = _env_url(
        "COPAW_DISCOVERY_CHINA_MCP_REGISTRY_URL",
        mcp_registry_endpoint,
    )
    return {
        "global": (
            DiscoverySourceSpec(
                source_id="global-skillhub",
                chain_role="primary",
                source_kind="catalog",
                display_name="SkillHub",
                endpoint=skillhub_endpoint,
                trust_posture="trusted",
                priority=0,
                metadata={"provider": "skillhub-catalog"},
            ),
            DiscoverySourceSpec(
                source_id="global-github",
                chain_role="mirror",
                source_kind="catalog",
                display_name="GitHub",
                endpoint=github_endpoint,
                trust_posture="trusted",
                priority=1,
                metadata={"provider": "github-repo"},
            ),
            DiscoverySourceSpec(
                source_id="global-mcp-registry",
                chain_role="fallback",
                source_kind="catalog",
                display_name="Official MCP Registry",
                endpoint=mcp_registry_endpoint,
                trust_posture="trusted",
                priority=2,
                metadata={"provider": "mcp-registry"},
            ),
            DiscoverySourceSpec(
                source_id="global-snapshot",
                chain_role="fallback",
                source_kind="snapshot",
                display_name="Last Known Good Snapshot",
                trust_posture="local",
                priority=3,
                metadata={"provider": "snapshot"},
            ),
        ),
        "china-mainland": (
            DiscoverySourceSpec(
                source_id="china-skillhub",
                chain_role="primary",
                source_kind="catalog",
                display_name="SkillHub",
                endpoint=china_skillhub_endpoint,
                trust_posture="trusted",
                priority=0,
                metadata={"provider": "skillhub-catalog"},
            ),
            DiscoverySourceSpec(
                source_id="china-github",
                chain_role="mirror",
                source_kind="catalog",
                display_name="GitHub",
                endpoint=china_github_endpoint,
                trust_posture="watchlist",
                priority=1,
                metadata={"provider": "github-repo"},
            ),
            DiscoverySourceSpec(
                source_id="china-mcp-registry",
                chain_role="fallback",
                source_kind="catalog",
                display_name="Official MCP Registry",
                endpoint=china_mcp_endpoint,
                trust_posture="trusted",
                priority=2,
                metadata={"provider": "mcp-registry"},
            ),
            DiscoverySourceSpec(
                source_id="china-snapshot",
                chain_role="fallback",
                source_kind="snapshot",
                display_name="Regional Snapshot",
                trust_posture="local",
                priority=3,
                metadata={"provider": "snapshot"},
            ),
        ),
        "hybrid": (
            DiscoverySourceSpec(
                source_id="hybrid-github",
                chain_role="primary",
                source_kind="catalog",
                display_name="GitHub",
                endpoint=github_endpoint,
                trust_posture="trusted",
                priority=0,
                metadata={"provider": "github-repo"},
            ),
            DiscoverySourceSpec(
                source_id="hybrid-skillhub",
                chain_role="mirror",
                source_kind="catalog",
                display_name="SkillHub",
                endpoint=skillhub_endpoint,
                trust_posture="trusted",
                priority=1,
                metadata={"provider": "skillhub-catalog"},
            ),
            DiscoverySourceSpec(
                source_id="hybrid-mcp-registry",
                chain_role="fallback",
                source_kind="catalog",
                display_name="Official MCP Registry",
                endpoint=mcp_registry_endpoint,
                trust_posture="watchlist",
                priority=2,
                metadata={"provider": "mcp-registry"},
            ),
            DiscoverySourceSpec(
                source_id="hybrid-snapshot",
                chain_role="fallback",
                source_kind="snapshot",
                display_name="Hybrid Snapshot",
                trust_posture="local",
                priority=3,
                metadata={"provider": "snapshot"},
            ),
        ),
        "offline-private": (
            DiscoverySourceSpec(
                source_id="offline-cache",
                chain_role="primary",
                source_kind="catalog",
                display_name="Offline Cache",
                endpoint="file://cache",
                trust_posture="local",
                priority=0,
                metadata={"provider": "offline-cache"},
            ),
            DiscoverySourceSpec(
                source_id="offline-snapshot",
                chain_role="fallback",
                source_kind="snapshot",
                display_name="Offline Snapshot",
                trust_posture="local",
                priority=1,
                metadata={"provider": "snapshot"},
            ),
        ),
    }


def _source_key(profile_name: str, source_id: str) -> str:
    return f"discovery:{profile_name}:{source_id}"


class DonorSourceService:
    def __init__(self, *, state_store: SQLiteStateStore) -> None:
        self._state_store = state_store
        self._state_store.initialize()
        self._ensure_default_profiles()

    def list_profile_names(self) -> list[str]:
        return sorted(_default_discovery_source_profiles().keys())

    def resolve_source_profile(self, profile_name: str) -> DiscoverySourceProfile:
        self._ensure_default_profiles()
        normalized_name = _string(profile_name) or "global"
        rows = self._list_profile_rows(normalized_name)
        if not rows and normalized_name != "global":
            normalized_name = "global"
            rows = self._list_profile_rows(normalized_name)
        sources = tuple(
            sorted(
                (self._row_to_spec(row) for row in rows),
                key=lambda item: item.priority,
            ),
        )
        return DiscoverySourceProfile(
            profile_name=normalized_name,
            display_name=normalized_name,
            sources=sources,
        )

    def resolve_source_profile_for_request(
        self,
        profile_name: str,
        request: object | None,
    ) -> DiscoverySourceProfile:
        profile = self.resolve_source_profile(profile_name)
        preferred_providers = self._preferred_provider_order(request)
        if not preferred_providers:
            return profile
        ranking = {provider: index for index, provider in enumerate(preferred_providers)}
        ordered = tuple(
            sorted(
                profile.sources,
                key=lambda item: (
                    ranking.get(_string(item.metadata.get("provider")) or "", len(ranking) + item.priority),
                    item.priority,
                ),
            ),
        )
        return DiscoverySourceProfile(
            profile_name=profile.profile_name,
            display_name=profile.display_name,
            sources=ordered,
            metadata=dict(profile.metadata),
        )

    def record_source_success(
        self,
        *,
        profile_name: str,
        source_id: str,
        discovery_hits: tuple[DiscoveryHit, ...] | list[DiscoveryHit],
    ) -> None:
        record = self._get_profile_record(profile_name=profile_name, source_id=source_id)
        if record is None:
            return
        metadata = dict(record.metadata or {})
        metadata["last_status"] = "succeeded"
        metadata["last_error"] = None
        metadata["success_count"] = int(metadata.get("success_count") or 0) + 1
        metadata["last_success_at"] = _utc_now().isoformat()
        metadata["last_known_good_at"] = metadata["last_success_at"]
        metadata["last_known_good_snapshot"] = [
            hit.to_payload()
            for hit in list(discovery_hits)
        ]
        self._write_source_profile(record.model_copy(update={"metadata": metadata}))

    def record_source_failure(
        self,
        *,
        profile_name: str,
        source_id: str,
        error: str | None,
    ) -> None:
        record = self._get_profile_record(profile_name=profile_name, source_id=source_id)
        if record is None:
            return
        metadata = dict(record.metadata or {})
        metadata["last_status"] = "failed"
        metadata["last_error"] = _string(error)
        metadata["failure_count"] = int(metadata.get("failure_count") or 0) + 1
        metadata["last_failure_at"] = _utc_now().isoformat()
        self._write_source_profile(record.model_copy(update={"metadata": metadata}))

    def record_source_empty(
        self,
        *,
        profile_name: str,
        source_id: str,
    ) -> None:
        record = self._get_profile_record(profile_name=profile_name, source_id=source_id)
        if record is None:
            return
        metadata = dict(record.metadata or {})
        metadata["last_status"] = "empty"
        metadata["last_error"] = None
        metadata["empty_count"] = int(metadata.get("empty_count") or 0) + 1
        metadata["last_empty_at"] = _utc_now().isoformat()
        self._write_source_profile(record.model_copy(update={"metadata": metadata}))

    def get_source_health(
        self,
        *,
        profile_name: str,
        source_id: str,
    ) -> dict[str, Any]:
        record = self._get_profile_record(profile_name=profile_name, source_id=source_id)
        metadata = dict(record.metadata or {}) if record is not None else {}
        return {
            "last_status": _string(metadata.get("last_status")) or "unknown",
            "last_error": _string(metadata.get("last_error")),
            "success_count": int(metadata.get("success_count") or 0),
            "failure_count": int(metadata.get("failure_count") or 0),
            "empty_count": int(metadata.get("empty_count") or 0),
            "last_success_at": _string(metadata.get("last_success_at")),
            "last_failure_at": _string(metadata.get("last_failure_at")),
            "last_empty_at": _string(metadata.get("last_empty_at")),
            "last_known_good_at": _string(metadata.get("last_known_good_at")),
        }

    def get_last_known_good_snapshot(
        self,
        profile_name: str,
    ) -> DiscoverySnapshot | None:
        latest_record: CapabilitySourceProfileRecord | None = None
        latest_marker: str | None = None
        for row in self._list_profile_rows(profile_name):
            record = self._row_to_source_profile(row)
            marker = _string(record.metadata.get("last_known_good_at"))
            if marker is None:
                continue
            if latest_marker is None or marker > latest_marker:
                latest_marker = marker
                latest_record = record
        if latest_record is None or latest_marker is None:
            return None
        snapshot_payload = list(latest_record.metadata.get("last_known_good_snapshot") or [])
        return DiscoverySnapshot(
            profile_name=_string(latest_record.metadata.get("profile_name")) or profile_name,
            source_id=_string(latest_record.metadata.get("source_id")) or "unknown-source",
            captured_at=datetime.fromisoformat(latest_marker),
            discovery_hits=tuple(
                DiscoveryHit.from_payload(item)
                for item in snapshot_payload
                if isinstance(item, dict)
            ),
        )

    def _ensure_default_profiles(self) -> None:
        for profile_name, sources in _default_discovery_source_profiles().items():
            for source in sources:
                record = self._get_profile_record(
                    profile_name=profile_name,
                    source_id=source.source_id,
                )
                metadata = dict(record.metadata or {}) if record is not None else {}
                metadata.update(
                    {
                        "source_profile_type": _DISCOVERY_PROFILE_TYPE,
                        "profile_name": profile_name,
                        "source_id": source.source_id,
                        "chain_role": source.chain_role,
                        "priority": source.priority,
                        "endpoint": source.endpoint,
                        "display_name": source.display_name,
                        "source_metadata": dict(source.metadata),
                    },
                )
                record = (
                    record
                    if record is not None
                    else CapabilitySourceProfileRecord(
                        source_kind=source.source_kind,
                        source_key=_source_key(profile_name, source.source_id),
                        display_name=source.display_name,
                        trust_posture=source.trust_posture,
                        active=True,
                        metadata=metadata,
                    )
                )
                self._write_source_profile(
                    record.model_copy(
                        update={
                            "source_kind": source.source_kind,
                            "source_key": _source_key(profile_name, source.source_id),
                            "display_name": source.display_name,
                            "trust_posture": source.trust_posture,
                            "active": True,
                            "metadata": metadata,
                        },
                    ),
                )

    def _preferred_provider_order(
        self,
        request: object | None,
    ) -> tuple[str, ...]:
        query = _string(getattr(request, "query", None)) or ""
        query_lower = query.lower()
        metadata = getattr(request, "metadata", None)
        preferred_provider = (
            _string(metadata.get("preferred_provider"))
            if isinstance(metadata, dict)
            else None
        )
        if preferred_provider:
            normalized = preferred_provider.lower()
            return (normalized, "skillhub-catalog", "github-repo", "mcp-registry")
        if any(keyword in query_lower for keyword in ("mcp", "registry", "modelcontextprotocol")):
            return ("mcp-registry", "github-repo", "skillhub-catalog", "snapshot")
        if any(
            keyword in query_lower
            for keyword in ("github", "repo", "repository", "open source", "opensource", "project", "release")
        ):
            return ("github-repo", "skillhub-catalog", "mcp-registry", "snapshot")
        if any(keyword in query_lower for keyword in ("curated", "skill", "automation", "browser")):
            return ("skillhub-catalog", "github-repo", "mcp-registry", "snapshot")
        return ("skillhub-catalog", "github-repo", "mcp-registry", "snapshot")

    def _list_profile_rows(self, profile_name: str):
        with self._state_store.connection() as conn:
            return conn.execute(
                """
                SELECT *
                FROM capability_source_profiles
                WHERE source_key LIKE ?
                ORDER BY updated_at DESC, source_profile_id DESC
                """,
                (f"discovery:{profile_name}:%",),
            ).fetchall()

    def _get_profile_record(
        self,
        *,
        profile_name: str,
        source_id: str,
    ) -> CapabilitySourceProfileRecord | None:
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_source_profiles
                WHERE source_key = ?
                ORDER BY updated_at DESC, source_profile_id DESC
                LIMIT 1
                """,
                (_source_key(profile_name, source_id),),
            ).fetchone()
        return self._row_to_source_profile(row) if row is not None else None

    def _row_to_spec(self, row) -> DiscoverySourceSpec:
        metadata = _json_load_dict(row["metadata_json"])
        return DiscoverySourceSpec(
            source_id=_string(metadata.get("source_id")) or "unknown-source",
            chain_role=_string(metadata.get("chain_role")) or "primary",
            source_kind=row["source_kind"],
            display_name=row["display_name"],
            endpoint=_string(metadata.get("endpoint")),
            trust_posture=row["trust_posture"],
            priority=int(metadata.get("priority") or 0),
            metadata=dict(metadata.get("source_metadata") or {}),
        )

    def _write_source_profile(self, record: CapabilitySourceProfileRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO capability_source_profiles (
                    source_profile_id,
                    source_kind,
                    source_key,
                    display_name,
                    trust_posture,
                    active,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :source_profile_id,
                    :source_kind,
                    :source_key,
                    :display_name,
                    :trust_posture,
                    :active,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(source_profile_id) DO UPDATE SET
                    source_kind = excluded.source_kind,
                    source_key = excluded.source_key,
                    display_name = excluded.display_name,
                    trust_posture = excluded.trust_posture,
                    active = excluded.active,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "source_profile_id": record.source_profile_id,
                    "source_kind": record.source_kind,
                    "source_key": record.source_key,
                    "display_name": record.display_name,
                    "trust_posture": record.trust_posture,
                    "active": 1 if record.active else 0,
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _row_to_source_profile(self, row) -> CapabilitySourceProfileRecord:
        return CapabilitySourceProfileRecord(
            source_profile_id=row["source_profile_id"],
            source_kind=row["source_kind"],
            source_key=row["source_key"],
            display_name=row["display_name"],
            trust_posture=row["trust_posture"],
            active=bool(row["active"]),
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
