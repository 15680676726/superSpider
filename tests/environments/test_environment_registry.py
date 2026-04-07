# -*- coding: utf-8 -*-
"""Tests for the environments module: registry, service, and classification."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import copaw.environments.health_service as environment_health_service
from copaw.app.runtime_events import RuntimeEventBus
from copaw.environments import (
    ActionReplayStore,
    EnvironmentMount,
    EnvironmentRegistry,
    EnvironmentService,
    EnvironmentSummary,
    ObservationCache,
    SessionMountRepository,
    EnvironmentRepository,
)
from copaw.evidence import EvidenceLedger, EvidenceRecord, ReplayPointer
from copaw.state import SQLiteStateStore


# ── Classification tests ────────────────────────────────────────────


class TestClassification:
    """Test EnvironmentRegistry._classify for different ref formats."""

    def test_http_url_is_browser(self):
        assert EnvironmentRegistry._classify("https://example.com/page") == "browser"

    def test_https_url_is_browser(self):
        assert EnvironmentRegistry._classify("http://localhost:3000") == "browser"

    def test_unix_path_is_workspace(self):
        assert EnvironmentRegistry._classify("/home/user/project") == "workspace"

    def test_windows_path_is_workspace(self):
        assert EnvironmentRegistry._classify("D:\\word\\copaw") == "workspace"

    def test_session_ref_is_session(self):
        assert EnvironmentRegistry._classify("legacy:console:user123") == "session"

    def test_channel_session_is_session(self):
        assert EnvironmentRegistry._classify("feishu:session-abc") == "session"


# ── Registry collect tests ──────────────────────────────────────────


class FakeRecord:
    """Minimal evidence record for testing."""

    def __init__(self, env_ref: str | None, created_at: datetime | None = None):
        self.environment_ref = env_ref
        self.created_at = created_at


class FakeLedger:
    """Fake EvidenceLedger that returns canned records."""

    def __init__(self, records: list[FakeRecord]):
        self._records = records

    def list_recent(self, limit: int = 500):
        return self._records[:limit]


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _string_list(value):
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if not isinstance(value, list):
        return []
    result = []
    seen = set()
    for item in value:
        if isinstance(item, str):
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
    return result


def _first_string(*values):
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _workspace_graph_lock_view(detail):
    graph = _mapping(detail.get("workspace_graph"))
    host_contract = _mapping(detail.get("host_contract"))
    desktop_contract = _mapping(detail.get("desktop_app_contract"))
    fallback_lock_refs = _string_list(graph.get("lock_refs"))
    fallback_writer_lock_scope = _first_string(desktop_contract.get("writer_lock_scope"))
    fallback_lock_ref = _first_string(
        fallback_lock_refs[0] if fallback_lock_refs else None,
        fallback_writer_lock_scope,
    )
    fallback_summary = _first_string(
        graph.get("active_lock_summary"),
        fallback_lock_ref,
    )
    fallback_owner_ref = _first_string(host_contract.get("lease_owner"))
    fallback_surface_kind = (
        "desktop-app"
        if _first_string(desktop_contract.get("app_identity")) or fallback_writer_lock_scope
        else None
    )
    raw_locks = graph.get("locks")
    if isinstance(raw_locks, list):
        normalized = []
        for item in raw_locks:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "lock_ref": _first_string(
                        item.get("lock_ref"),
                        item.get("resource_ref"),
                        item.get("ref"),
                        item.get("id"),
                        item.get("scope_ref"),
                        _mapping(item.get("writer_lock")).get("scope"),
                        fallback_lock_ref,
                    ),
                    "summary": _first_string(
                        item.get("summary"),
                        item.get("label"),
                        item.get("lock_summary"),
                        item.get("lock_ref"),
                        item.get("ref"),
                        fallback_summary,
                    ),
                    "scope_ref": _first_string(
                        item.get("scope_ref"),
                        item.get("lock_scope_ref"),
                        item.get("writer_lock_scope"),
                        _mapping(item.get("writer_lock")).get("scope"),
                        fallback_writer_lock_scope,
                    ),
                    "owner_ref": _first_string(
                        item.get("owner_ref"),
                        item.get("lease_owner_ref"),
                        item.get("active_owner_ref"),
                        _mapping(item.get("writer_lock")).get("owner_agent_id"),
                        fallback_owner_ref,
                    ),
                    "surface_kind": _first_string(
                        item.get("surface_kind"),
                        item.get("kind"),
                        item.get("surface"),
                        (
                            "desktop-app"
                            if _first_string(item.get("surface_ref"), item.get("window_ref"))
                            else None
                        ),
                        fallback_surface_kind,
                    ),
                    "status": _first_string(
                        item.get("status"),
                        item.get("lock_status"),
                        _mapping(item.get("writer_lock")).get("status"),
                        "active",
                    ),
                }
            )
        if normalized:
            return normalized
    lock_refs = list(fallback_lock_refs)
    writer_lock_scope = fallback_writer_lock_scope
    if not lock_refs and writer_lock_scope:
        lock_refs = [writer_lock_scope]
    return [
        {
            "lock_ref": lock_ref,
            "summary": fallback_summary or lock_ref,
            "scope_ref": writer_lock_scope,
            "owner_ref": fallback_owner_ref,
            "surface_kind": fallback_surface_kind,
            "status": "active",
        }
        for lock_ref in lock_refs
    ]


def _workspace_graph_surface_view(detail):
    graph = _mapping(detail.get("workspace_graph"))
    host_contract = _mapping(detail.get("host_contract"))
    browser_contract = _mapping(detail.get("browser_site_contract"))
    desktop_contract = _mapping(detail.get("desktop_app_contract"))

    def build_surface(surface_kind, refs, *, active_ref=None, contract_status=None):
        refs = _string_list(refs)
        if not refs:
            return None
        primary_ref = refs[0]
        return {
            "surface_kind": surface_kind,
            "primary_ref": primary_ref,
            "refs": refs,
            "active_ref": _first_string(active_ref, primary_ref),
            "owner_ref": _first_string(host_contract.get("lease_owner")),
            "account_scope_ref": _first_string(host_contract.get("account_scope_ref")),
            "contract_status": _first_string(contract_status),
        }

    surfaces = [
        build_surface(
            "browser",
            graph.get("browser_context_refs"),
            active_ref=browser_contract.get("active_tab_ref"),
            contract_status=browser_contract.get("site_contract_status"),
        ),
        build_surface(
            "desktop-app",
            graph.get("app_window_refs"),
            active_ref=desktop_contract.get("active_window_ref"),
            contract_status=desktop_contract.get("app_contract_status"),
        ),
        build_surface("file-doc", graph.get("file_doc_refs")),
        build_surface("clipboard", graph.get("clipboard_refs")),
        build_surface("download-bucket", graph.get("download_bucket_refs")),
    ]
    fallback_surfaces = [item for item in surfaces if item is not None]
    fallback_by_kind = {
        item["surface_kind"]: item for item in fallback_surfaces if item["surface_kind"] is not None
    }

    raw_surfaces = graph.get("surfaces")
    raw_by_kind = {}
    if isinstance(raw_surfaces, dict):
        browser = _mapping(raw_surfaces.get("browser"))
        browser_active = _mapping(browser.get("active_tab"))
        browser_refs = _string_list(browser.get("context_refs"))
        desktop = _mapping(raw_surfaces.get("desktop"))
        desktop_active = _mapping(desktop.get("active_window"))
        desktop_refs = _string_list(desktop.get("window_refs"))
        file_docs = _mapping(raw_surfaces.get("file_docs"))
        clipboard = _mapping(raw_surfaces.get("clipboard"))
        downloads = _mapping(raw_surfaces.get("downloads"))
        downloads_active = _mapping(downloads.get("active_bucket"))
        raw_by_kind = {
            "browser": {
                "surface_kind": "browser",
                "primary_ref": _first_string(
                    browser_refs[0] if browser_refs else None,
                    browser_active.get("tab_id"),
                    _mapping(fallback_by_kind.get("browser")).get("primary_ref"),
                ),
                "refs": browser_refs
                or _string_list(_mapping(fallback_by_kind.get("browser")).get("refs")),
                "active_ref": _first_string(
                    browser_active.get("tab_id"),
                    _mapping(fallback_by_kind.get("browser")).get("active_ref"),
                ),
                "owner_ref": _first_string(
                    graph.get("owner_agent_id"),
                    _mapping(fallback_by_kind.get("browser")).get("owner_ref"),
                ),
                "account_scope_ref": _first_string(
                    browser_active.get("account_scope_ref"),
                    graph.get("account_scope_ref"),
                    _mapping(fallback_by_kind.get("browser")).get("account_scope_ref"),
                ),
                "contract_status": _first_string(
                    browser.get("site_contract_status"),
                    _mapping(fallback_by_kind.get("browser")).get("contract_status"),
                ),
            },
            "desktop-app": {
                "surface_kind": "desktop-app",
                "primary_ref": _first_string(
                    desktop_refs[0] if desktop_refs else None,
                    desktop_active.get("window_ref"),
                    _mapping(fallback_by_kind.get("desktop-app")).get("primary_ref"),
                ),
                "refs": (
                    desktop_refs
                    or _string_list([desktop_active.get("window_ref")])
                    or _string_list(_mapping(fallback_by_kind.get("desktop-app")).get("refs"))
                ),
                "active_ref": _first_string(
                    desktop_active.get("window_ref"),
                    _mapping(fallback_by_kind.get("desktop-app")).get("active_ref"),
                ),
                "owner_ref": _first_string(
                    graph.get("owner_agent_id"),
                    _mapping(fallback_by_kind.get("desktop-app")).get("owner_ref"),
                ),
                "account_scope_ref": _first_string(
                    desktop_active.get("account_scope_ref"),
                    graph.get("account_scope_ref"),
                    _mapping(fallback_by_kind.get("desktop-app")).get("account_scope_ref"),
                ),
                "contract_status": _first_string(
                    desktop.get("app_contract_status"),
                    _mapping(fallback_by_kind.get("desktop-app")).get("contract_status"),
                ),
            },
            "file-doc": {
                "surface_kind": "file-doc",
                "primary_ref": _first_string(
                    file_docs.get("active_doc_ref"),
                    _mapping(fallback_by_kind.get("file-doc")).get("primary_ref"),
                ),
                "refs": _string_list(file_docs.get("refs"))
                or _string_list(_mapping(fallback_by_kind.get("file-doc")).get("refs")),
                "active_ref": _first_string(
                    file_docs.get("active_doc_ref"),
                    _mapping(fallback_by_kind.get("file-doc")).get("active_ref"),
                ),
                "owner_ref": _first_string(
                    graph.get("owner_agent_id"),
                    _mapping(fallback_by_kind.get("file-doc")).get("owner_ref"),
                ),
                "account_scope_ref": _first_string(
                    graph.get("account_scope_ref"),
                    _mapping(fallback_by_kind.get("file-doc")).get("account_scope_ref"),
                ),
                "contract_status": None,
            },
            "clipboard": {
                "surface_kind": "clipboard",
                "primary_ref": _first_string(
                    clipboard.get("active_clipboard_ref"),
                    _mapping(fallback_by_kind.get("clipboard")).get("primary_ref"),
                ),
                "refs": _string_list(clipboard.get("refs"))
                or _string_list(_mapping(fallback_by_kind.get("clipboard")).get("refs")),
                "active_ref": _first_string(
                    clipboard.get("active_clipboard_ref"),
                    _mapping(fallback_by_kind.get("clipboard")).get("active_ref"),
                ),
                "owner_ref": _first_string(
                    graph.get("owner_agent_id"),
                    _mapping(fallback_by_kind.get("clipboard")).get("owner_ref"),
                ),
                "account_scope_ref": _first_string(
                    graph.get("account_scope_ref"),
                    _mapping(fallback_by_kind.get("clipboard")).get("account_scope_ref"),
                ),
                "contract_status": None,
            },
            "download-bucket": {
                "surface_kind": "download-bucket",
                "primary_ref": _first_string(
                    downloads_active.get("bucket_ref"),
                    _mapping(fallback_by_kind.get("download-bucket")).get("primary_ref"),
                ),
                "refs": _string_list(downloads.get("bucket_refs"))
                or _string_list(
                    _mapping(fallback_by_kind.get("download-bucket")).get("refs"),
                ),
                "active_ref": _first_string(
                    downloads_active.get("bucket_ref"),
                    _mapping(fallback_by_kind.get("download-bucket")).get("active_ref"),
                ),
                "owner_ref": _first_string(
                    graph.get("owner_agent_id"),
                    _mapping(fallback_by_kind.get("download-bucket")).get("owner_ref"),
                ),
                "account_scope_ref": _first_string(
                    graph.get("account_scope_ref"),
                    _mapping(fallback_by_kind.get("download-bucket")).get("account_scope_ref"),
                ),
                "contract_status": None,
            },
        }
    if isinstance(raw_surfaces, list):
        for item in raw_surfaces:
            if not isinstance(item, dict):
                continue
            surface_kind = _first_string(
                item.get("surface_kind"),
                item.get("kind"),
                item.get("type"),
            )
            fallback = _mapping(fallback_by_kind.get(surface_kind))
            primary_ref = _first_string(
                item.get("primary_ref"),
                item.get("surface_ref"),
                item.get("ref"),
                fallback.get("primary_ref"),
            )
            refs = _string_list(item.get("refs")) or _string_list(item.get("surface_refs"))
            if not refs:
                refs = _string_list(fallback.get("refs"))
            if primary_ref and primary_ref not in refs:
                refs = [primary_ref, *refs]
            raw_by_kind[surface_kind] = {
                "surface_kind": surface_kind,
                "primary_ref": primary_ref,
                "refs": refs,
                "active_ref": _first_string(
                    item.get("active_ref"),
                    item.get("active_surface_ref"),
                    item.get("active_context_ref"),
                    fallback.get("active_ref"),
                    primary_ref,
                ),
                "owner_ref": _first_string(
                    item.get("owner_ref"),
                    item.get("lease_owner_ref"),
                    item.get("active_owner_ref"),
                    fallback.get("owner_ref"),
                ),
                "account_scope_ref": _first_string(
                    item.get("account_scope_ref"),
                    item.get("owner_account_scope_ref"),
                    fallback.get("account_scope_ref"),
                ),
                "contract_status": _first_string(
                    item.get("contract_status"),
                    item.get("site_contract_status"),
                    item.get("app_contract_status"),
                    item.get("status"),
                    fallback.get("contract_status"),
                ),
            }

    ordered_kinds = [
        "browser",
        "desktop-app",
        "file-doc",
        "clipboard",
        "download-bucket",
    ]
    merged = []
    for surface_kind in ordered_kinds:
        merged_item = raw_by_kind.get(surface_kind) or fallback_by_kind.get(surface_kind)
        if merged_item is not None and (
            _first_string(merged_item.get("primary_ref")) is not None
            or _string_list(merged_item.get("refs"))
        ):
            merged.append(merged_item)
    return merged


def _workspace_graph_ownership_collision_view(detail):
    graph = _mapping(detail.get("workspace_graph"))
    host_contract = _mapping(detail.get("host_contract"))
    ownership = _mapping(
        graph.get("ownership_facts")
        or graph.get("ownership")
        or graph.get("active_surface_ownership")
    )
    collisions = _mapping(
        graph.get("collision_facts")
        or graph.get("collisions")
        or graph.get("collision_summary")
    )
    handoff = _mapping(graph.get("handoff_checkpoint"))
    surfaces = _workspace_graph_surface_view(detail)
    locks = _workspace_graph_lock_view(detail)
    active_surface_owner_ref = _first_string(
        ownership.get("active_surface_owner_ref"),
        ownership.get("owner_ref"),
        collisions.get("shared_surface_owner"),
    )
    if active_surface_owner_ref is None and surfaces:
        active_surface_owner_ref = _first_string(surfaces[0].get("owner_ref"))
    shared_account_scope_refs = (
        _string_list(collisions.get("shared_account_scope_refs"))
        or _string_list(collisions.get("account_scope_refs"))
    )
    account_scope_ref = _first_string(
        ownership.get("account_scope_ref"),
        host_contract.get("account_scope_ref"),
    )
    if not shared_account_scope_refs and account_scope_ref is not None:
        shared_account_scope_refs = [account_scope_ref]
    writer_conflict_scope_refs = (
        _string_list(collisions.get("writer_conflict_scope_refs"))
        or _string_list(collisions.get("lock_scope_refs"))
        or _string_list(collisions.get("writer_lock_scope"))
        or [
            item["scope_ref"]
            for item in locks
            if _first_string(item.get("scope_ref")) is not None
        ]
    )
    writer_conflict_refs = (
        _string_list(collisions.get("writer_conflict_refs"))
        or _string_list(collisions.get("active_lock_refs"))
        or _string_list(graph.get("collision_summary"))
        or [
            item["lock_ref"]
            for item in locks
            if _first_string(item.get("lock_ref")) is not None
        ]
    )
    return {
        "seat_owner_ref": _first_string(
            ownership.get("seat_owner_ref"),
            ownership.get("owner_agent_id"),
            ownership.get("owner_ref"),
            host_contract.get("lease_owner"),
        ),
        "active_surface_owner_ref": active_surface_owner_ref,
        "account_scope_ref": account_scope_ref,
        "handoff_owner_ref": _first_string(
            ownership.get("handoff_owner_ref"),
            handoff.get("owner_ref"),
        ),
        "shared_account_scope_refs": shared_account_scope_refs,
        "writer_conflict_refs": writer_conflict_refs,
        "writer_conflict_scope_refs": writer_conflict_scope_refs,
    }


def _host_twin_contract_view(detail):
    twin = _mapping(detail.get("host_twin"))
    summary = _mapping(detail.get("host_twin_summary")) or _mapping(
        twin.get("host_twin_summary"),
    )
    seat = _mapping(twin.get("seat"))
    ownership = _mapping(twin.get("ownership"))
    app_family_twins = _mapping(twin.get("app_family_twins"))
    coordination = _mapping(twin.get("coordination"))
    continuity = _mapping(twin.get("continuity"))
    host_companion_session = _mapping(detail.get("host_companion_session"))
    companion_summary = (
        _mapping(summary.get("host_companion_session"))
        if summary is not None
        else {}
    )
    multi_seat = _mapping(summary.get("multi_seat_coordination")) if summary is not None else {}
    app_family_readiness = _mapping(summary.get("app_family_readiness")) if summary is not None else {}
    legal_recovery_path = _mapping(
        twin.get("legal_recovery_path") or twin.get("legal_recovery"),
    )
    scheduler_inputs = _mapping(twin.get("scheduler_inputs"))
    recovery_inputs = _mapping(twin.get("recovery_inputs"))
    raw_anchors = twin.get("trusted_evidence_anchors") or twin.get("trusted_anchors")
    anchor_refs = []
    if isinstance(raw_anchors, list):
        seen_anchor_refs = set()
        for item in raw_anchors:
            anchor_ref = None
            if isinstance(item, dict):
                anchor_ref = _first_string(
                    item.get("anchor_ref"),
                    item.get("ref"),
                    item.get("value"),
                    item.get("checkpoint_ref"),
                )
            elif isinstance(item, str):
                anchor_ref = _first_string(item)
            if anchor_ref is not None and anchor_ref not in seen_anchor_refs:
                seen_anchor_refs.add(anchor_ref)
                anchor_refs.append(anchor_ref)
    return {
        "seat_owner_ref": _first_string(
            seat.get("owner_ref"),
            ownership.get("seat_owner_agent_id"),
            twin.get("seat_owner_ref"),
        ),
        "ownership_source": _first_string(
            seat.get("ownership_source"),
            ownership.get("ownership_source"),
            twin.get("ownership_source"),
        ),
        "writable_surface_kinds": sorted(
            _string_list(
                twin.get("writable_surface_kinds"),
            )
            or sorted(
                surface_kind
                for surface_kind, is_ready in _mapping(
                    twin.get("execution_mutation_ready"),
                ).items()
                if is_ready is True
            ),
        ),
        "continuity_valid": continuity.get("is_valid", continuity.get("valid")),
        "continuity_source": _first_string(
            continuity.get("source"),
            continuity.get("continuity_source"),
        ),
        "trusted_anchor_refs": sorted(anchor_refs),
        "recovery_decision": _first_string(
            legal_recovery_path.get("decision"),
            legal_recovery_path.get("mode"),
            legal_recovery_path.get("path"),
        ),
        "recovery_resume_kind": _first_string(
            legal_recovery_path.get("resume_kind"),
        ),
        "recovery_checkpoint_ref": _first_string(
            legal_recovery_path.get("checkpoint_ref"),
        ),
        "recovery_return_condition": _first_string(
            legal_recovery_path.get("return_condition"),
        ),
        "active_blocker_families": sorted(
            _string_list(
                twin.get("active_blocker_families"),
            ),
        ),
        "scheduler_blocking_family": _first_string(
            scheduler_inputs.get("active_blocking_family"),
            scheduler_inputs.get("active_blocker_family"),
            scheduler_inputs.get("blocking_family"),
        ),
        "scheduler_recovery_family": _first_string(
            scheduler_inputs.get("active_recovery_family"),
            scheduler_inputs.get("recovery_family"),
        ),
        "scheduler_requires_human_return": scheduler_inputs.get(
            "requires_human_return",
            continuity.get("requires_human_return"),
        ),
        "pending_recovery_families": sorted(
            _string_list(
                recovery_inputs.get("pending_recovery_families"),
            ),
        ),
        "app_family_keys": sorted(app_family_twins.keys()),
        "active_app_families": sorted(
            family
            for family, payload in app_family_twins.items()
            if _mapping(payload).get("active") is True
        ),
        "browser_backoffice_contract_status": _mapping(
            app_family_twins.get("browser_backoffice"),
        ).get("contract_status"),
        "office_document_writer_lock_scope": _mapping(
            app_family_twins.get("office_document"),
        ).get("writer_lock_scope"),
        "coordination_selected_seat_ref": _first_string(
            coordination.get("selected_seat_ref"),
        ),
        "coordination_seat_policy": _first_string(
            coordination.get("seat_selection_policy"),
        ),
        "coordination_scheduler_action": _first_string(
            coordination.get("recommended_scheduler_action"),
        ),
        "coordination_contention_severity": _mapping(
            coordination.get("contention_forecast"),
        ).get("severity"),
        "host_companion_status": _first_string(
            summary.get("host_companion_status"),
            companion_summary.get("continuity_status"),
            host_companion_session.get("continuity_status"),
        ),
        "host_companion_source": _first_string(
            summary.get("host_companion_source"),
            companion_summary.get("continuity_source"),
            host_companion_session.get("continuity_source"),
        ),
        "host_companion_session_mount_id": _first_string(
            summary.get("host_companion_session_mount_id"),
            companion_summary.get("session_mount_id"),
            host_companion_session.get("session_mount_id"),
        ),
        "seat_count": summary.get("seat_count"),
        "candidate_seat_refs": sorted(
            _string_list(summary.get("candidate_seat_refs"))
            or _string_list(multi_seat.get("candidate_seat_refs"))
            or _string_list(coordination.get("candidate_seat_refs")),
        ),
        "ready_app_family_keys": sorted(
            _string_list(summary.get("ready_app_family_keys"))
            or _string_list(app_family_readiness.get("ready_family_keys")),
        ),
        "blocked_app_family_keys": sorted(
            _string_list(summary.get("blocked_app_family_keys"))
            or _string_list(app_family_readiness.get("blocked_family_keys")),
        ),
    }


def test_registry_collect_deduplicates():
    """Same environment_ref appears twice, should produce one mount with count=2."""
    ledger = FakeLedger([
        FakeRecord("/home/user/project", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        FakeRecord("/home/user/project", datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ])
    registry = EnvironmentRegistry(ledger=ledger)
    mounts = registry.collect()
    assert len(mounts) == 1
    assert mounts[0].evidence_count == 2
    assert mounts[0].kind == "workspace"
    assert mounts[0].last_active_at == datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_registry_collect_classifies_mixed_types():
    """Different refs produce different kinds."""
    ledger = FakeLedger([
        FakeRecord("https://example.com"),
        FakeRecord("/tmp/workspace"),
        FakeRecord("legacy:console:user1"),
    ])
    registry = EnvironmentRegistry(ledger=ledger)
    mounts = registry.collect()
    kinds = {m.kind for m in mounts}
    assert kinds == {"browser", "workspace", "session"}


def test_registry_collect_skips_none_refs():
    """Records with None environment_ref should be ignored."""
    ledger = FakeLedger([
        FakeRecord(None),
        FakeRecord(""),
        FakeRecord("/valid/path"),
    ])
    registry = EnvironmentRegistry(ledger=ledger)
    mounts = registry.collect()
    assert len(mounts) == 1
    assert mounts[0].ref == "/valid/path"


def test_registry_collect_empty_ledger():
    """Empty ledger returns empty list."""
    ledger = FakeLedger([])
    registry = EnvironmentRegistry(ledger=ledger)
    assert registry.collect() == []


def test_registry_collect_none_ledger():
    """No ledger returns empty list."""
    registry = EnvironmentRegistry(ledger=None)
    assert registry.collect() == []


# ── Service tests ───────────────────────────────────────────────────


def test_service_list_environments_filters_by_kind():
    ledger = FakeLedger([
        FakeRecord("https://example.com"),
        FakeRecord("/tmp/workspace"),
    ])
    registry = EnvironmentRegistry(ledger=ledger)
    service = EnvironmentService(registry=registry)

    all_envs = service.list_environments()
    assert len(all_envs) == 2

    browsers = service.list_environments(kind="browser")
    assert len(browsers) == 1
    assert browsers[0].kind == "browser"


def test_service_summarize():
    ledger = FakeLedger([
        FakeRecord("https://a.com"),
        FakeRecord("https://b.com"),
        FakeRecord("/tmp/work"),
    ])
    registry = EnvironmentRegistry(ledger=ledger)
    service = EnvironmentService(registry=registry)

    summary = service.summarize()
    assert summary.total == 3
    assert summary.active == 3
    assert summary.by_kind == {"browser": 2, "workspace": 1}


def test_service_get_environment():
    ledger = FakeLedger([FakeRecord("https://example.com")])
    registry = EnvironmentRegistry(ledger=ledger)
    service = EnvironmentService(registry=registry)

    mount = service.get_environment("env:browser:https://example.com")
    assert mount is not None
    assert mount.kind == "browser"

    missing = service.get_environment("env:workspace:/nonexistent")
    assert missing is None


def test_registry_registers_session_mount(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    registry.register(
        ref="session:console:sess-1",
        kind="session",
        metadata={"channel": "console", "session_id": "sess-1", "user_id": "u1"},
    )
    session = session_repo.get_session("session:console:sess-1")
    assert session is not None
    assert session.channel == "console"
    assert session.session_id == "sess-1"
    assert session.user_id == "u1"


def test_observation_cache_lists_environment_evidence(tmp_path):
    ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    ledger.append(
        EvidenceRecord(
            task_id="task-1",
            actor_ref="tester",
            environment_ref="session:console:sess-1",
            capability_ref="tool:execute_shell_command",
            risk_level="auto",
            action_summary="test action",
            result_summary="ok",
        ),
    )
    cache = ObservationCache(ledger=ledger)
    observations = cache.list_recent(
        environment_ref="session:console:sess-1",
        limit=5,
    )
    assert len(observations) == 1
    assert observations[0].environment_ref == "session:console:sess-1"


def test_environment_service_session_lease_lifecycle(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="console",
        session_id="sess-1",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=30,
        handle={"browser": "tab-1"},
        metadata={"chat_id": "chat-1"},
    )

    assert lease.lease_status == "leased"
    assert lease.lease_owner == "worker-1"
    assert lease.live_handle_ref is not None
    assert registry.get_live_handle(lease.environment_id) == {"browser": "tab-1"}

    heartbeated = service.heartbeat_session_lease(
        lease.id,
        lease_token=lease.lease_token or "",
        ttl_seconds=45,
        handle={"browser": "tab-2"},
    )
    assert heartbeated.lease_status == "leased"
    assert heartbeated.lease_expires_at > lease.lease_expires_at
    assert registry.get_live_handle(lease.environment_id) == {"browser": "tab-2"}

    released = service.release_session_lease(
        lease.id,
        lease_token=lease.lease_token,
        reason="done",
    )
    assert released is not None
    assert released.lease_status == "released"
    assert released.live_handle_ref is None
    assert registry.get_live_handle(lease.environment_id) is None

    mount = env_repo.get_environment(lease.environment_id)
    assert mount is not None
    assert mount.lease_status == "released"
    assert mount.live_handle_ref is None


def test_environment_service_resource_slot_lease_lifecycle(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_resource_slot_lease(
        scope_type="browser-profile",
        scope_value="profile-1",
        owner="routine-1",
        ttl_seconds=30,
        metadata={"routine_id": "routine-1"},
    )

    assert lease.channel == "resource-slot:browser-profile"
    assert lease.session_id == "profile-1"
    assert lease.lease_status == "leased"
    assert lease.metadata["environment_ref"] == "resource-slot:browser-profile:profile-1"
    assert service.get_resource_slot_lease(
        scope_type="browser-profile",
        scope_value="profile-1",
    ) == lease
    assert [item.id for item in service.list_resource_slot_leases()] == [lease.id]

    heartbeated = service.heartbeat_resource_slot_lease(
        lease.id,
        lease_token=lease.lease_token or "",
        ttl_seconds=45,
    )
    assert heartbeated.lease_expires_at > lease.lease_expires_at

    released = service.release_resource_slot_lease(
        lease_id=lease.id,
        lease_token=lease.lease_token,
        reason="done",
    )
    assert released is not None
    assert released.lease_status == "released"
    assert service.get_resource_slot_lease(
        scope_type="browser-profile",
        scope_value="profile-1",
    ).lease_status == "released"


def test_environment_service_resource_slot_lease_conflict(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_resource_slot_lease(
        scope_type="browser-profile",
        scope_value="profile-1",
        owner="routine-1",
    )

    with pytest.raises(RuntimeError):
        service.acquire_resource_slot_lease(
            scope_type="browser-profile",
            scope_value="profile-1",
            owner="routine-2",
        )

    released = service.release_resource_slot_lease(
        lease_id=lease.id,
        lease_token=lease.lease_token,
        reason="released for reuse",
    )
    assert released is not None
    reacquired = service.acquire_resource_slot_lease(
        scope_type="browser-profile",
        scope_value="profile-1",
        owner="routine-2",
    )
    assert reacquired.lease_owner == "routine-2"


def test_environment_service_shared_writer_lease_lifecycle_and_conflict(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_shared_writer_lease(
        writer_lock_scope="workbook:weekly-report",
        owner="agent-1",
        metadata={"environment_ref": "desktop-app:excel:weekly-report"},
    )

    assert lease.channel == "resource-slot:shared-writer"
    assert lease.session_id == "workbook:weekly-report"
    assert lease.lease_status == "leased"
    assert lease.metadata["access_mode"] == "writer"
    assert lease.metadata["lease_class"] == "exclusive-writer"
    assert lease.metadata["writer_lock_scope"] == "workbook:weekly-report"
    assert service.get_shared_writer_lease(
        writer_lock_scope="workbook:weekly-report",
    ) == lease

    with pytest.raises(RuntimeError):
        service.acquire_shared_writer_lease(
            writer_lock_scope="workbook:weekly-report",
            owner="agent-2",
        )

    heartbeated = service.heartbeat_shared_writer_lease(
        lease.id,
        lease_token=lease.lease_token or "",
        ttl_seconds=240,
    )
    assert heartbeated.lease_expires_at > lease.lease_expires_at

    released = service.release_shared_writer_lease(
        lease_id=lease.id,
        lease_token=lease.lease_token,
        reason="writer step completed",
    )
    assert released is not None
    assert released.lease_status == "released"
    assert service.get_shared_writer_lease(
        writer_lock_scope="workbook:weekly-report",
    ).lease_status == "released"


def test_environment_service_reaps_expired_leases(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=30)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="console",
        session_id="sess-expired",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=5,
        handle={"browser": "tab-expired"},
    )

    reaped = service.reap_expired_leases(
        now=(lease.lease_expires_at or datetime.now(timezone.utc)) + timedelta(seconds=1),
    )

    assert reaped == 1
    expired_session = session_repo.get_session(lease.id)
    assert expired_session is not None
    assert expired_session.lease_status == "expired"
    assert expired_session.live_handle_ref is None
    assert registry.get_live_handle(lease.environment_id) is None


def test_environment_service_recovers_orphaned_leases_after_restart(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="console",
        session_id="sess-restart",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=60,
        handle={"browser": "tab-restart"},
    )

    assert registry.get_live_handle(lease.environment_id) == {"browser": "tab-restart"}

    recovered_registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    recovered_service = EnvironmentService(
        registry=recovered_registry,
        lease_ttl_seconds=120,
    )
    recovered_service.set_session_repository(session_repo)

    recovered = recovered_service.recover_orphaned_leases(
        now=(lease.lease_acquired_at or datetime.now(timezone.utc)) + timedelta(seconds=1),
    )

    assert recovered == 1

    recovered_session = session_repo.get_session(lease.id)
    assert recovered_session is not None
    assert recovered_session.lease_status == "expired"
    assert recovered_session.live_handle_ref is None
    assert recovered_session.metadata["lease_release_reason"] == (
        "live handle unavailable during runtime recovery"
    )

    recovered_mount = env_repo.get_environment(lease.environment_id)
    assert recovered_mount is not None
    assert recovered_mount.lease_status == "expired"
    assert recovered_mount.live_handle_ref is None


def test_orphaned_browser_attach_lease_recovery_clears_stale_attach_continuity(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="host-a",
        process_id=101,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="browser",
        session_id="sess-attach-restart",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=60,
        handle={"browser": "tab-restart"},
        metadata={
            "host_mode": "attach-existing-session",
            "lease_class": "exclusive-writer",
            "access_mode": "writer",
            "session_scope": "browser-user-session",
        },
    )
    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="chrome-native-host:default",
        status="attached",
        browser_session_ref="chrome-session:alice-default",
        browser_scope_ref="chrome-profile:alice",
        reconnect_token="reconnect-token-1",
    )

    recovered_registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="host-a",
        process_id=202,
    )
    recovered_service = EnvironmentService(
        registry=recovered_registry,
        lease_ttl_seconds=120,
    )
    recovered_service.set_session_repository(session_repo)

    recovered = recovered_service.recover_orphaned_leases(
        now=(lease.lease_acquired_at or datetime.now(timezone.utc)) + timedelta(seconds=1),
        allow_cross_process_recovery=True,
    )

    assert recovered == 1
    recovered_session = session_repo.get_session(lease.id)
    assert recovered_session is not None
    recovered_mount = env_repo.get_environment(lease.environment_id)
    assert recovered_mount is not None

    assert recovered_session.lease_status == "expired"
    assert recovered_session.metadata["browser_attach_transport_ref"] is None
    assert recovered_session.metadata["browser_attach_session_ref"] is None
    assert recovered_session.metadata["browser_attach_scope_ref"] is None
    assert recovered_session.metadata["browser_attach_reconnect_token"] is None
    assert recovered_mount.lease_status == "expired"
    assert recovered_mount.metadata["browser_attach_transport_ref"] is None
    assert recovered_mount.metadata["browser_attach_session_ref"] is None
    assert recovered_mount.metadata["browser_attach_scope_ref"] is None
    assert recovered_mount.metadata["browser_attach_reconnect_token"] is None


def test_environment_service_restores_orphaned_leases_with_registered_restorer(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="host-a",
        process_id=101,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="console",
        session_id="sess-restore",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=60,
        handle={"browser": "tab-restore"},
    )

    recovered_registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="host-a",
        process_id=202,
    )
    recovered_service = EnvironmentService(
        registry=recovered_registry,
        lease_ttl_seconds=120,
    )
    recovered_service.set_session_repository(session_repo)
    recovered_service.register_session_handle_restorer(
        "console",
        lambda context: {
            "handle": {"browser": "tab-restored"},
            "descriptor": {"restored_by": "test-restorer"},
            "metadata": {"restore_source": context["channel"]},
        },
    )

    recovered = recovered_service.recover_orphaned_leases(
        now=(lease.lease_acquired_at or datetime.now(timezone.utc)) + timedelta(seconds=1),
        allow_cross_process_recovery=True,
    )

    assert recovered == 1
    restored_session = session_repo.get_session(lease.id)
    assert restored_session is not None
    assert restored_session.lease_status == "leased"
    assert restored_session.live_handle_ref is not None
    assert restored_session.metadata["restore_source"] == "console"
    assert restored_session.metadata["lease_restore_status"] == "restored"
    assert recovered_registry.get_live_handle(lease.environment_id) == {
        "browser": "tab-restored"
    }


def test_environment_service_does_not_take_over_same_host_other_process_lease_during_reads(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="host-a",
        process_id=101,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="console",
        session_id="sess-other-process",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=60,
        handle={"browser": "tab-live"},
    )

    other_process_registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="host-a",
        process_id=202,
    )
    other_process_service = EnvironmentService(
        registry=other_process_registry,
        lease_ttl_seconds=120,
    )
    other_process_service.set_session_repository(session_repo)
    other_process_service.register_session_handle_restorer(
        "console",
        lambda _context: {"handle": {"browser": "tab-should-not-be-restored"}},
    )

    recovered = other_process_service.recover_orphaned_leases(
        now=(lease.lease_acquired_at or datetime.now(timezone.utc)) + timedelta(seconds=1),
    )

    assert recovered == 0
    untouched_session = session_repo.get_session(lease.id)
    assert untouched_session is not None
    assert untouched_session.lease_status == "leased"
    assert untouched_session.live_handle_ref == lease.live_handle_ref

    detail = other_process_service.get_session_detail(lease.id)
    assert detail is not None
    assert detail["recovery"]["status"] == "same-host-other-process"
    assert detail["recovery"]["same_host"] is True
    assert detail["recovery"]["same_process"] is False
    assert detail["recovery"]["startup_recovery_required"] is True


def test_environment_service_host_recovery_respects_cross_process_recovery_flag(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="host-a",
        process_id=101,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="sess-host-recovery",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=60,
        handle={"window": "excel-live"},
        metadata={
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
        },
    )

    other_process_registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="host-a",
        process_id=202,
    )
    other_process_service = EnvironmentService(
        registry=other_process_registry,
        lease_ttl_seconds=120,
    )
    other_process_service.set_session_repository(session_repo)
    other_process_service.set_runtime_event_bus(RuntimeEventBus(max_events=20))
    other_process_service.register_session_handle_restorer(
        "desktop",
        lambda _context: {"handle": {"window": "excel-restored"}},
    )
    other_process_service._runtime_event_bus.publish(
        topic="host",
        action="human-return-ready",
        payload={
            "session_mount_id": lease.id,
            "environment_id": lease.environment_id,
            "checkpoint_ref": "checkpoint:captcha",
            "verification_channel": "runtime-center-self-check",
            "return_condition": "captcha-cleared",
            "handoff_owner_ref": "human-operator:alice",
        },
    )

    blocked_allowed, blocked_reason = other_process_service.should_run_host_recovery(
        limit=10,
    )
    allowed_allowed, allowed_reason = other_process_service.should_run_host_recovery(
        limit=10,
        allow_cross_process_recovery=True,
    )
    blocked_result = other_process_service.run_host_recovery_cycle(limit=10)
    allowed_result = other_process_service.run_host_recovery_cycle(
        limit=10,
        allow_cross_process_recovery=True,
    )

    assert blocked_allowed is False
    assert blocked_reason == "cross-process-recovery-disabled"
    assert allowed_allowed is True
    assert allowed_reason == "actionable-host-events"
    assert blocked_result["executed"] == 0
    assert blocked_result["skipped"] == 1
    assert allowed_result["executed"] == 1
    assert allowed_result["decisions"]["recover"] == 1

    restored_session = session_repo.get_session(lease.id)
    assert restored_session is not None
    assert restored_session.lease_status == "leased"
    assert restored_session.metadata["lease_restore_status"] == "restored"


def test_environment_service_execute_replay_prefers_registered_executor(tmp_path):
    ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    stored = ledger.append(
        EvidenceRecord(
            task_id="task-1",
            actor_ref="tester",
            environment_ref="session:console:sess-1",
            capability_ref="tool:read_file",
            risk_level="guarded",
            action_summary="capture replay",
            result_summary="stored direct replay",
        ),
        replay_pointers=[
            ReplayPointer(
                replay_type="shell",
                storage_uri="replay://session/1",
                summary="shell replay",
                metadata={
                    "capability_ref": "tool:read_file",
                    "payload": {"path": "README.md"},
                    "environment_ref": "session:console:sess-1",
                },
            ),
        ],
    )
    replay_id = stored.replay_pointers[0].id
    assert replay_id is not None

    service = EnvironmentService()
    service.set_action_replay(ActionReplayStore(ledger=ledger))
    service.register_replay_executor(
        "shell",
        lambda replay, context: {
            "mode": "direct",
            "summary": replay.summary,
            "actor": context["actor"],
            "environment_ref": context["environment_ref"],
        },
    )

    result = asyncio.run(service.execute_replay(replay_id, actor="runtime-center"))

    assert result["mode"] == "direct"
    assert result["result"]["mode"] == "direct"
    assert result["result"]["actor"] == "runtime-center"
    assert result["result"]["environment_ref"] == "session:console:sess-1"


def test_environment_detail_exposes_host_runtime_baseline_projections(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)
    event_bus = RuntimeEventBus(max_events=50)
    service.set_runtime_event_bus(event_bus)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-1",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab-1",
            "page_id": "page-1",
            "cwd": "D:/word/copaw",
            "task_id": "task-1",
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "writer",
            "session_scope": "task",
            "handoff_state": "active",
            "resume_kind": "resume-environment",
            "verification_channel": "dom-anchor",
            "current_gap_or_blocker": "captcha pending",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "active_surface_mix": ["browser", "desktop"],
            "browser_context_refs": ["ctx-1"],
            "app_window_refs": ["window-1"],
            "file_doc_refs": ["doc-1"],
            "clipboard_refs": ["clipboard-1"],
            "download_bucket_refs": ["download-bucket-1"],
            "active_lock_summary": "writer lock on app window",
            "handoff_checkpoint_ref": "checkpoint:captcha",
            "handoff_return_condition": "manual-resume",
            "pending_handoff_summary": "operator finishing captcha",
        },
    )
    base_payload = {
        "session_mount_id": lease.id,
        "environment_id": lease.environment_id,
    }
    event_bus.publish(
        topic="window",
        action="focus-changed",
        payload={
            **base_payload,
            "window_ref": "window-1",
        },
    )
    event_bus.publish(
        topic="desktop",
        action="captcha-required",
        payload={
            **base_payload,
            "prompt_kind": "captcha",
        },
    )
    event_bus.publish(
        topic="download",
        action="download-completed",
        payload={
            **base_payload,
            "download_ref": "download-bucket-1",
            "status": "completed",
        },
    )
    event_bus.publish(
        topic="process",
        action="process-restarted",
        payload={
            **base_payload,
            "process_ref": "process:4242",
        },
    )
    event_bus.publish(
        topic="host",
        action="desktop-unlocked",
        payload={
            **base_payload,
            "locked": False,
        },
    )
    event_bus.publish(
        topic="network",
        action="connectivity-changed",
        payload={
            **base_payload,
            "network_state": "online",
        },
    )

    detail = service.get_environment_detail(lease.environment_id, limit=10)

    assert detail is not None
    assert detail["host_contract"]["host_mode"] == "local-managed"
    assert detail["host_contract"]["lease_class"] == "exclusive-writer"
    assert detail["host_contract"]["access_mode"] == "writer"
    assert detail["host_contract"]["session_scope"] == "task"
    assert detail["host_contract"]["handoff_state"] == "active"
    assert detail["host_contract"]["resume_kind"] == "resume-environment"
    assert detail["host_contract"]["verification_channel"] == "dom-anchor"
    assert detail["host_contract"]["current_gap_or_blocker"] == "captcha pending"
    assert detail["seat_runtime"]["projection_kind"] == "seat_runtime_projection"
    assert detail["seat_runtime"]["is_projection"] is True
    assert detail["seat_runtime"]["status"] == "active"
    assert detail["seat_runtime"]["occupancy_state"] == "occupied"
    assert detail["seat_runtime"]["candidate_seat_refs"] == [lease.environment_id]
    assert detail["seat_runtime"]["selected_seat_ref"] == lease.environment_id
    assert detail["seat_runtime"]["seat_selection_policy"] == "sticky-active-seat"
    assert detail["host_companion_session"]["session_mount_id"] == lease.id
    assert detail["workspace_graph"]["projection_kind"] == "workspace_graph_projection"
    assert detail["workspace_graph"]["is_projection"] is True
    assert detail["workspace_graph"]["workspace_id"] == "workspace-main"
    assert detail["workspace_graph"]["clipboard_refs"] == ["clipboard-1"]
    assert detail["workspace_graph"]["download_bucket_refs"] == ["download-bucket-1"]
    assert detail["workspace_graph"]["lock_refs"] == ["writer lock on app window"]
    assert detail["workspace_graph"]["active_surface_refs"] == [
        "ctx-1",
        "window-1",
        "doc-1",
        "clipboard-1",
        "download-bucket-1",
    ]
    assert detail["workspace_graph"]["workspace_components"] == {
        "browser_context_count": 1,
        "app_window_count": 1,
        "file_doc_count": 1,
        "clipboard_count": 1,
        "download_bucket_count": 1,
        "lock_count": 1,
    }
    assert detail["workspace_graph"]["handoff_checkpoint"] == {
        "state": "active",
        "reason": None,
        "owner_ref": None,
        "resume_kind": "resume-environment",
        "verification_channel": "dom-anchor",
        "checkpoint_ref": "checkpoint:captcha",
        "return_condition": "manual-resume",
        "summary": "operator finishing captcha",
    }
    assert detail["host_event_summary"]["is_truth_store"] is False
    assert detail["host_event_summary"]["runtime_mechanism"] == "runtime_event_bus"
    assert detail["host_event_summary"]["supported_families"] == [
        "active-window",
        "modal-uac-login",
        "download-completed",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    ]
    family_counts = detail["host_event_summary"]["family_counts"]
    assert family_counts["active-window"] == 1
    assert family_counts["modal-uac-login"] == 1
    assert family_counts["download-completed"] == 1
    assert family_counts["process-exit-restart"] == 1
    assert family_counts["lock-unlock"] == 1
    assert family_counts["network-power"] == 1
    modal_latest = detail["host_event_summary"]["latest_event_by_family"]["modal-uac-login"]
    assert modal_latest["event_name"] == "desktop.captcha-required"
    assert modal_latest["topic"] == "desktop"
    assert modal_latest["action"] == "captcha-required"
    assert modal_latest["severity"] == "high"
    assert modal_latest["recommended_runtime_response"] == "handoff"
    network_latest = detail["host_event_summary"]["latest_event_by_family"]["network-power"]
    assert network_latest["event_name"] == "network.connectivity-changed"
    assert network_latest["topic"] == "network"
    assert network_latest["action"] == "connectivity-changed"
    assert network_latest["severity"] == "medium"
    assert network_latest["recommended_runtime_response"] == "retry"
    assert detail["host_event_summary"]["active_alert_families"] == [
        "modal-uac-login",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    ]
    assert len(detail["host_events"]) == 7
    assert all(
        event["topic"]
        in {"session", "window", "desktop", "download", "process", "host", "network"}
        for event in detail["host_events"]
    )
    assert all("event_family" in event for event in detail["host_events"])
    assert all("recommended_runtime_response" in event for event in detail["host_events"])
    assert all("severity" in event for event in detail["host_events"])
    assert detail["host_events"][0]["event_family"] == "runtime-generic"
    assert detail["host_events"][1]["event_family"] == "active-window"
    assert detail["host_events"][2]["event_family"] == "modal-uac-login"
    assert detail["host_events"][3]["event_family"] == "download-completed"
    assert detail["host_events"][4]["event_family"] == "process-exit-restart"
    assert detail["host_events"][5]["event_family"] == "lock-unlock"
    assert detail["host_events"][6]["event_family"] == "network-power"


def test_environment_detail_surfaces_bridge_registration_contract_from_metadata(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-bridge",
        user_id="u1",
        owner="worker-bridge",
        ttl_seconds=60,
        handle={
            "browser": "tab-bridge",
            "page_id": "page-bridge",
            "cwd": "D:/word/copaw",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "worker_type": "cowork",
            "max_sessions": 4,
            "spawn_mode": "same-dir",
            "reuse_environment_id": "env:bridge:prior",
        },
    )

    detail = service.get_environment_detail(lease.environment_id, limit=5)
    session_detail = service.get_session_detail(lease.id, limit=5)

    assert detail is not None
    assert session_detail is not None
    assert detail["seat_runtime"]["bridge_registration"] == {
        "worker_type": "cowork",
        "max_sessions": 4,
        "spawn_mode": "same-dir",
        "reuse_environment_id": "env:bridge:prior",
    }
    assert detail["host_companion_session"]["bridge_registration"] == {
        "worker_type": "cowork",
        "max_sessions": 4,
        "spawn_mode": "same-dir",
        "reuse_environment_id": "env:bridge:prior",
    }
    assert session_detail["seat_runtime"]["bridge_registration"]["worker_type"] == "cowork"
    assert (
        session_detail["host_companion_session"]["bridge_registration"]["max_sessions"] == 4
    )


def test_environment_detail_surfaces_bridge_lifecycle_and_trust_metadata(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-bridge-lifecycle",
        user_id="u1",
        owner="worker-bridge",
        ttl_seconds=60,
        handle={
            "browser": "tab-bridge",
            "page_id": "page-bridge",
            "cwd": "D:/word/copaw",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "worker_type": "cowork",
            "bridge_work_id": "work-bridge-1",
            "bridge_work_status": "leased",
            "bridge_heartbeat_at": "2026-04-02T13:00:00Z",
            "bridge_session_id": "bridge-session-1",
            "workspace_trusted": True,
            "elevated_auth_state": "trusted-device",
        },
    )

    detail = service.get_environment_detail(lease.environment_id, limit=5)
    session_detail = service.get_session_detail(lease.id, limit=5)

    assert detail is not None
    assert session_detail is not None
    assert detail["seat_runtime"]["bridge_registration"] == {
        "worker_type": "cowork",
        "max_sessions": None,
        "spawn_mode": None,
        "reuse_environment_id": None,
        "bridge_work_id": "work-bridge-1",
        "bridge_work_status": "leased",
        "bridge_heartbeat_at": "2026-04-02T13:00:00Z",
        "bridge_session_id": "bridge-session-1",
        "workspace_trusted": True,
        "elevated_auth_state": "trusted-device",
    }
    assert detail["host_companion_session"]["bridge_registration"] == {
        "worker_type": "cowork",
        "max_sessions": None,
        "spawn_mode": None,
        "reuse_environment_id": None,
        "bridge_work_id": "work-bridge-1",
        "bridge_work_status": "leased",
        "bridge_heartbeat_at": "2026-04-02T13:00:00Z",
        "bridge_session_id": "bridge-session-1",
        "workspace_trusted": True,
        "elevated_auth_state": "trusted-device",
    }
    assert (
        session_detail["seat_runtime"]["bridge_registration"]["bridge_work_status"]
        == "leased"
    )
    assert (
        session_detail["host_companion_session"]["bridge_registration"]["workspace_trusted"]
        is True
    )


def test_bridge_session_work_contract_reuses_same_session_truth_and_updates_lifecycle(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-bridge-runtime",
        user_id="u1",
        owner="worker-bridge",
        ttl_seconds=60,
        handle={"process_id": 4242},
        metadata={"worker_type": "cowork"},
    )
    assert lease.lease_token is not None
    original_expires_at = lease.lease_expires_at

    acked = service.ack_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="work-1",
        bridge_session_id="bridge-session-1",
        workspace_trusted=True,
        elevated_auth_state="trusted-device",
    )
    heartbeated = service.heartbeat_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="work-1",
    )
    reconnected = service.reconnect_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="work-1",
    )
    stopped = service.stop_bridge_session_work(
        lease.id,
        work_id="work-1",
        force=True,
        reason="bridge supervisor stop",
    )

    sessions = service.list_sessions(environment_id=lease.environment_id, limit=10)
    assert len(sessions) == 1
    assert acked.id == lease.id
    assert heartbeated.id == lease.id
    assert reconnected.id == lease.id
    assert stopped.id == lease.id
    assert acked.metadata["bridge_work_id"] == "work-1"
    assert acked.metadata["bridge_work_status"] == "acknowledged"
    assert acked.metadata["bridge_session_id"] == "bridge-session-1"
    assert acked.metadata["workspace_trusted"] is True
    assert acked.metadata["elevated_auth_state"] == "trusted-device"
    assert heartbeated.metadata["bridge_work_status"] == "running"
    assert isinstance(heartbeated.metadata.get("bridge_heartbeat_at"), str)
    assert reconnected.metadata["bridge_work_status"] == "reconnecting"
    assert isinstance(reconnected.metadata.get("bridge_reconnected_at"), str)
    assert stopped.metadata["bridge_work_status"] == "stopped"
    assert stopped.metadata["bridge_stop_mode"] == "force"
    assert stopped.metadata["bridge_stop_reason"] == "bridge supervisor stop"
    assert isinstance(stopped.metadata.get("bridge_stopped_at"), str)
    assert reconnected.lease_status == "leased"
    assert reconnected.lease_expires_at is not None
    assert original_expires_at is not None
    assert reconnected.lease_expires_at > original_expires_at


def test_bridge_archive_and_deregister_update_session_and_environment_contracts(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-bridge-close",
        user_id="u1",
        owner="worker-bridge",
        ttl_seconds=60,
        handle={"process_id": 4242},
        metadata={"worker_type": "cowork"},
    )
    assert lease.lease_token is not None
    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="transport:cdp:bridge-close",
        status="attached",
        browser_session_ref="browser-session:bridge-close",
        browser_scope_ref="site:jd:seller-center",
        reconnect_token="reconnect-token-close",
    )

    archived = service.archive_bridge_session(
        lease.id,
        lease_token=lease.lease_token,
        reason="bridge archive",
    )
    assert archived is not None
    assert archived.status == "archived"
    assert archived.lease_status == "released"
    assert archived.metadata["bridge_work_status"] == "archived"
    assert archived.metadata["browser_attach_transport_ref"] is None
    assert isinstance(archived.metadata.get("bridge_archived_at"), str)

    deregistered = service.deregister_bridge_environment(
        lease.environment_id,
        reason="bridge shutdown",
    )
    assert deregistered is not None
    assert deregistered.status == "deregistered"
    assert deregistered.metadata["bridge_environment_status"] == "deregistered"
    assert isinstance(deregistered.metadata.get("bridge_deregistered_at"), str)

    session_detail = service.get_session(lease.id)
    assert session_detail is not None
    assert session_detail.status == "deregistered"
    assert session_detail.metadata["bridge_work_status"] == "deregistered"
    assert session_detail.metadata["browser_attach_transport_ref"] is None
    assert session_detail.metadata["browser_attach_session_ref"] is None
    assert session_detail.metadata["browser_attach_scope_ref"] is None
    assert session_detail.metadata["browser_attach_reconnect_token"] is None
    assert isinstance(session_detail.metadata.get("bridge_deregistered_at"), str)


def test_operator_abort_state_reuses_same_truth_and_surfaces_projection(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-operator-abort",
        user_id="u1",
        owner="worker-bridge",
        ttl_seconds=60,
        handle={"process_id": 4242},
    )
    service.register_windows_app_adapter(
        session_mount_id=lease.id,
        adapter_refs=["app-adapter:excel"],
        app_identity="excel",
        control_channel="accessibility-tree",
        execution_guardrails={
            "operator_abort_channel": "global-esc",
        },
    )

    updated = service.set_shared_operator_abort_state(
        session_mount_id=lease.id,
        channel="global-esc",
        reason="esc hotkey",
    )

    environment = env_repo.get_environment(lease.environment_id)
    assert environment is not None
    assert updated.metadata["operator_abort_state"] == {
        "channel": "global-esc",
        "requested": True,
        "reason": "esc hotkey",
        "requested_at": updated.metadata["operator_abort_state"]["requested_at"],
    }
    assert environment.metadata["operator_abort_state"] == {
        "channel": "global-esc",
        "requested": True,
        "reason": "esc hotkey",
        "requested_at": environment.metadata["operator_abort_state"]["requested_at"],
    }

    detail = service.get_session_detail(lease.id, limit=20)
    assert detail is not None
    assert detail["cooperative_adapter_availability"]["operator_abort_state"] == {
        "channel": "global-esc",
        "requested": True,
        "reason": "esc hotkey",
        "requested_at": detail["cooperative_adapter_availability"]["operator_abort_state"][
            "requested_at"
        ],
    }
    assert (
        detail["cooperative_adapter_availability"]["windows_app_adapters"][
            "execution_guardrails"
        ]["operator_abort_requested"]
        is True
    )

    cleared = service.clear_shared_operator_abort_state(
        session_mount_id=lease.id,
        channel="global-esc",
        reason="resume",
    )
    refreshed_environment = env_repo.get_environment(lease.environment_id)
    assert refreshed_environment is not None
    assert cleared.metadata["operator_abort_state"]["requested"] is False
    assert cleared.metadata["operator_abort_state"]["channel"] == "global-esc"
    assert cleared.metadata["operator_abort_state"]["reason"] == "resume"
    assert refreshed_environment.metadata["operator_abort_state"]["requested"] is False


def test_host_abort_producer_reuses_shared_operator_abort_truth(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-host-abort",
        user_id="u1",
        owner="worker-bridge",
        ttl_seconds=60,
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "session_ref": "desktop-runtime:seat-host-abort",
        },
    )

    requested = service.publish_host_operator_abort(
        runtime_session_ref="desktop-runtime:seat-host-abort",
        channel="global-esc",
        reason="esc hotkey",
    )
    session = session_repo.get_session(lease.id)
    environment = env_repo.get_environment(lease.environment_id)

    assert requested is not None
    assert requested.id == lease.id
    assert session is not None
    assert environment is not None
    assert session.metadata["operator_abort_state"]["requested"] is True
    assert session.metadata["operator_abort_state"]["channel"] == "global-esc"
    assert session.metadata["operator_abort_state"]["reason"] == "esc hotkey"
    assert environment.metadata["operator_abort_state"]["requested"] is True
    assert environment.metadata["operator_abort_state"]["channel"] == "global-esc"


def test_environment_and_session_detail_expose_execution_contract_projections(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-1",
        user_id="u1",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab:web:jd:seller-center:main",
            "page_id": "page:jd:seller-center:home",
            "active_window_ref": "window:excel:main",
            "window_scope": "window:excel:main",
            "process_id": 4242,
            "cwd": "D:/word/copaw",
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "handoff_state": "agent-attached",
            "resume_kind": "host-companion-session",
            "verification_channel": "runtime-center-self-check",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "account_scope_ref": "windows:user:alice",
            "browser_mode": "tab-attached",
            "login_state": "authenticated",
            "tab_scope": "single-tab",
            "active_tab_ref": "page:jd:seller-center:home",
            "profile_ref": "profile:copaw:main",
            "attach_transport_ref": "transport:cdp:local",
            "provider_kind": "local-managed-browser",
            "provider_session_ref": "browser-session:web:main",
            "download_policy": "workspace-bucket",
            "storage_scope": "profile+workspace",
            "site_contract_ref": "site-contract:jd:seller-center:writer",
            "site_contract_status": "verified-writer",
            "site_risk_contract_ref": "site-risk:jd:seller-center",
            "last_verified_url": "https://seller.jd.com/home",
            "last_verified_dom_anchor": "#shop-header",
            "navigation": True,
            "dom_interaction": True,
            "multi_tab": False,
            "uploads": True,
            "downloads": True,
            "pdf_export": True,
            "storage_access": True,
            "locale_timezone_override": False,
            "browser_companion_transport_ref": "transport:cdp:local",
            "browser_companion_status": "attached",
            "document_bridge_ref": "document-bridge:office",
            "document_bridge_status": "ready",
            "document_bridge_supported_families": ["spreadsheets", "documents"],
            "filesystem_watcher_status": "ready",
            "download_watcher_status": "healthy",
            "notification_watcher_status": "disabled",
            "windows_app_adapter_refs": ["app-adapter:excel", "app-adapter:file-explorer"],
            "preferred_execution_path": "cooperative-native-first",
            "ui_fallback_mode": "ui-fallback-last",
            "app_identity": "excel",
            "window_scope": "window:excel:main",
            "active_window_ref": "window:excel:main",
            "active_process_ref": "process:4242",
            "app_contract_ref": "app-contract:excel:writer",
            "app_contract_status": "verified-writer",
            "control_channel": "accessibility-tree",
            "writer_lock_scope": "workbook:weekly-report",
            "window_anchor_summary": "Excel > Weekly Report.xlsx > Sheet1!A1",
            "download_verification": True,
            "save_reopen_verification": True,
        },
    )

    environment_detail = service.get_environment_detail(lease.environment_id, limit=5)
    session_detail = service.get_session_detail(lease.id, limit=5)

    assert environment_detail is not None
    assert session_detail is not None
    assert (
        environment_detail["browser_site_contract"]["browser_mode"]
        == "attach-existing-session"
    )
    assert (
        environment_detail["browser_site_contract"]["active_tab_ref"]
        == "page:jd:seller-center:home"
    )
    assert environment_detail["browser_site_contract"]["tab_scope"] == "single-tab"
    assert (
        environment_detail["browser_site_contract"]["site_contract_status"]
        == "verified-writer"
    )
    assert (
        environment_detail["browser_site_contract"]["last_verified_dom_anchor"]
        == "#shop-header"
    )
    assert environment_detail["browser_site_contract"]["authenticated_continuation"] is True
    assert environment_detail["browser_site_contract"]["download_verification"] is True
    assert environment_detail["browser_site_contract"]["save_reopen_verification"] is True
    assert (
        environment_detail["browser_site_contract"]["download_bucket_refs"]
        == ["workspace-bucket"]
    )
    assert environment_detail["browser_site_contract"]["active_site"] == "jd:seller-center"
    assert environment_detail["browser_site_contract"]["last_verified_url"] == (
        "https://seller.jd.com/home"
    )
    assert environment_detail["desktop_app_contract"]["app_identity"] == "excel"
    assert environment_detail["desktop_app_contract"]["window_scope"] == "window:excel:main"
    assert (
        environment_detail["desktop_app_contract"]["active_process_ref"]
        == "process:4242"
    )
    assert (
        environment_detail["desktop_app_contract"]["app_contract_status"]
        == "verified-writer"
    )
    assert (
        environment_detail["desktop_app_contract"]["control_channel"]
        == "accessibility-tree"
    )
    assert (
        environment_detail["desktop_app_contract"]["window_anchor_summary"]
        == "Excel > Weekly Report.xlsx > Sheet1!A1"
    )
    assert environment_detail["desktop_app_contract"]["save_reopen_verification"] is True
    assert environment_detail["desktop_app_contract"]["recovery_mode"] == "resume-environment"
    assert (
        environment_detail["cooperative_adapter_availability"]["projection_kind"]
        == "cooperative_adapter_availability_projection"
    )
    assert environment_detail["cooperative_adapter_availability"]["is_projection"] is True
    assert (
        environment_detail["cooperative_adapter_availability"]["browser_companion"]["available"]
        is True
    )
    assert (
        environment_detail["cooperative_adapter_availability"]["document_bridge"]["bridge_ref"]
        == "document-bridge:office"
    )
    assert (
        environment_detail["cooperative_adapter_availability"]["watchers"]["filesystem"]["status"]
        == "ready"
    )
    assert (
        environment_detail["cooperative_adapter_availability"]["windows_app_adapters"]["adapter_refs"]
        == ["app-adapter:excel", "app-adapter:file-explorer"]
    )
    assert session_detail["browser_site_contract"]["site_contract_ref"] == (
        "site-contract:jd:seller-center:writer"
    )
    assert session_detail["browser_site_contract"]["resume_kind"] == "host-companion-session"
    assert session_detail["browser_site_contract"]["authenticated_continuation"] is True
    assert session_detail["browser_site_contract"]["download_verification"] is True
    assert session_detail["desktop_app_contract"]["active_window_ref"] == "window:excel:main"
    assert session_detail["desktop_app_contract"]["writer_lock_scope"] == "workbook:weekly-report"
    assert session_detail["desktop_app_contract"]["save_reopen_verification"] is True
    assert (
        session_detail["cooperative_adapter_availability"]["preferred_execution_path"]
        == "cooperative-native-first"
    )
    assert (
        session_detail["cooperative_adapter_availability"]["watchers"]["downloads"]["download_policy"]
        == "workspace-bucket"
    )
    assert (
        session_detail["cooperative_adapter_availability"]["windows_app_adapters"]["control_channel"]
        == "accessibility-tree"
    )
    assert _workspace_graph_lock_view(environment_detail) == [
        {
            "lock_ref": "workbook:weekly-report",
            "summary": "workbook:weekly-report",
            "scope_ref": "workbook:weekly-report",
            "owner_ref": "worker-1",
            "surface_kind": "desktop-app",
            "status": "held",
        },
    ]
    assert _workspace_graph_surface_view(environment_detail) == [
        {
            "surface_kind": "browser",
            "primary_ref": "tab:web:jd:seller-center:main",
            "refs": [
                "tab:web:jd:seller-center:main",
                "page:jd:seller-center:home",
            ],
            "active_ref": "page:jd:seller-center:home",
            "owner_ref": "worker-1",
            "account_scope_ref": "windows:user:alice",
            "contract_status": "verified-writer",
        },
        {
            "surface_kind": "desktop-app",
            "primary_ref": "window:excel:main",
            "refs": ["window:excel:main"],
            "active_ref": "window:excel:main",
            "owner_ref": "worker-1",
            "account_scope_ref": "windows:user:alice",
            "contract_status": "verified-writer",
        },
        {
            "surface_kind": "file-doc",
            "primary_ref": "D:/word/copaw",
            "refs": ["D:/word/copaw"],
            "active_ref": "D:/word/copaw",
            "owner_ref": "worker-1",
            "account_scope_ref": "windows:user:alice",
            "contract_status": None,
        },
        {
            "surface_kind": "download-bucket",
            "primary_ref": "workspace-bucket",
            "refs": ["workspace-bucket"],
            "active_ref": "workspace-bucket",
            "owner_ref": "worker-1",
            "account_scope_ref": "windows:user:alice",
            "contract_status": None,
        },
    ]
    assert _workspace_graph_surface_view(session_detail) == _workspace_graph_surface_view(
        environment_detail,
    )
    assert _workspace_graph_ownership_collision_view(environment_detail) == {
        "seat_owner_ref": "worker-1",
        "active_surface_owner_ref": "worker-1",
        "account_scope_ref": "windows:user:alice",
        "handoff_owner_ref": None,
        "shared_account_scope_refs": ["windows:user:alice"],
        "writer_conflict_refs": ["workbook:weekly-report"],
        "writer_conflict_scope_refs": ["workbook:weekly-report"],
    }
    assert _workspace_graph_ownership_collision_view(session_detail) == (
        _workspace_graph_ownership_collision_view(environment_detail)
    )


def test_environment_detail_projects_phase1_acceptance_visibility(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)
    event_bus = RuntimeEventBus(max_events=50)
    service.set_runtime_event_bus(event_bus)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-acceptance-1",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab:web:jd:seller-center:main",
            "page_id": "page:jd:seller-center:home",
            "active_window_ref": "window:excel:main",
            "window_scope": "window:excel:main",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "writer",
            "session_scope": "desktop-user-session",
            "verification_channel": "runtime-center-self-check",
            "workspace_id": "workspace-main",
            "account_scope_ref": "windows:user:alice",
            "browser_context_refs": [
                "browser:web:jd:seller-center",
                "page:jd:seller-center:home",
            ],
            "download_bucket_refs": ["download-bucket:workspace-main"],
            "login_state": "authenticated",
            "active_tab_ref": "page:jd:seller-center:home",
            "tab_scope": "session-tabs",
            "site_contract_ref": "site-contract:jd:seller-center:writer",
            "site_contract_status": "verified-writer",
            "download_policy": "download-bucket:workspace-main",
            "downloads": True,
            "last_verified_url": "https://seller.jd.com/home",
            "last_verified_dom_anchor": "#shop-header",
            "app_identity": "excel",
            "app_contract_status": "writer-ready",
            "control_channel": "accessibility-tree",
            "writer_lock_scope": "workbook:weekly-report",
            "window_anchor_summary": "Excel > Weekly Report.xlsx > Sheet1!A1",
            "active_window_ref": "window:excel:main",
            "window_scope": "window:excel:main",
        },
    )
    base_payload = {
        "session_mount_id": lease.id,
        "environment_id": lease.environment_id,
    }
    event_bus.publish(
        topic="desktop",
        action="uac-prompt",
        payload={
            **base_payload,
            "prompt_kind": "uac",
            "window_title": "User Account Control",
        },
    )
    event_bus.publish(
        topic="download",
        action="download-completed",
        payload={
            **base_payload,
            "download_ref": "download-bucket:workspace-main",
            "status": "completed",
            "checkpoint_ref": "checkpoint:download:weekly-report",
        },
    )

    detail = service.get_environment_detail(lease.environment_id, limit=10)

    assert detail is not None
    assert detail["host_contract"]["current_gap_or_blocker"] == "uac-prompt"
    assert detail["host_contract"]["handoff_state"] == "handoff-required"
    assert detail["host_contract"]["handoff_reason"] == "uac-prompt"
    assert detail["host_contract"]["verification_channel"] == "runtime-center-self-check"
    assert detail["browser_site_contract"]["authenticated_continuation"] is True
    assert detail["browser_site_contract"]["cross_tab_continuation"] is True
    assert detail["browser_site_contract"]["download_verification"] is True
    assert detail["browser_site_contract"]["save_reopen_verification"] is True
    assert detail["browser_site_contract"]["download_bucket_refs"] == [
        "download-bucket:workspace-main",
    ]
    assert detail["browser_site_contract"]["active_site"] == "jd:seller-center"
    assert detail["desktop_app_contract"]["current_gap_or_blocker"] == "uac-prompt"
    assert detail["desktop_app_contract"]["blocker_event_family"] == "modal-uac-login"
    assert detail["desktop_app_contract"]["recovery_mode"] == "resume-environment"
    assert detail["desktop_app_contract"]["save_reopen_verification"] is True
    assert detail["workspace_graph"]["download_status"] == {
        "bucket_refs": ["download-bucket:workspace-main"],
        "active_bucket_ref": "download-bucket:workspace-main",
        "download_policy": "download-bucket:workspace-main",
        "download_verification": True,
        "latest_download_event": {
            "event_id": 3,
            "event_name": "download.download-completed",
            "topic": "download",
            "action": "download-completed",
            "created_at": detail["host_event_summary"]["latest_event_by_family"][
                "download-completed"
            ]["created_at"],
            "severity": "low",
            "recommended_runtime_response": "re-observe",
        },
    }
    assert detail["workspace_graph"]["surface_contracts"] == {
        "browser_active_site": "jd:seller-center",
        "browser_site_contract_status": "verified-writer",
        "desktop_app_identity": "excel",
        "desktop_app_contract_status": "writer-ready",
    }
    assert detail["host_event_summary"]["last_event"] == "download.download-completed"
    assert detail["host_event_summary"]["counts_by_topic"] == {
        "session": 1,
        "desktop": 1,
        "download": 1,
    }
    assert detail["host_event_summary"]["pending_recovery_events"] == [
        {
            "event_id": 2,
            "event_name": "desktop.uac-prompt",
            "topic": "desktop",
            "action": "uac-prompt",
            "event_family": "modal-uac-login",
            "severity": "high",
            "recommended_runtime_response": "handoff",
            "created_at": detail["host_events"][1]["created_at"],
            "payload": {
                "session_mount_id": lease.id,
                "environment_id": lease.environment_id,
                "prompt_kind": "uac",
                "window_title": "User Account Control",
            },
            "checkpoint": {
                "resume_kind": "resume-environment",
                "checkpoint_ref": None,
                "verification_channel": "runtime-center-self-check",
            },
        },
    ]


def test_environment_detail_keeps_host_events_as_formal_runtime_mechanism_for_handoff_and_return(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)
    event_bus = RuntimeEventBus(max_events=50)
    service.set_runtime_event_bus(event_bus)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-phase45-events",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab:web:jd:seller-center:main",
            "page_id": "page:jd:seller-center:home",
            "active_window_ref": "window:excel:main",
            "window_scope": "window:excel:main",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "writer",
            "session_scope": "desktop-user-session",
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
            "workspace_id": "workspace-main",
            "handoff_owner_ref": "human-operator:alice",
            "handoff_checkpoint_ref": "checkpoint:captcha",
            "handoff_return_condition": "captcha-cleared",
        },
    )
    base_payload = {
        "session_mount_id": lease.id,
        "environment_id": lease.environment_id,
        "checkpoint_ref": "checkpoint:captcha",
        "verification_channel": "runtime-center-self-check",
        "return_condition": "captcha-cleared",
        "handoff_owner_ref": "human-operator:alice",
    }
    event_bus.publish(
        topic="desktop",
        action="uac-prompt",
        payload={
            **base_payload,
            "prompt_kind": "uac",
            "window_title": "User Account Control",
        },
    )
    event_bus.publish(
        topic="process",
        action="process-restarted",
        payload={
            **base_payload,
            "process_ref": "process:4242",
        },
    )
    event_bus.publish(
        topic="host",
        action="human-takeover",
        payload={
            **base_payload,
            "summary": "operator taking over for captcha",
        },
    )
    event_bus.publish(
        topic="host",
        action="human-return-ready",
        payload={
            **base_payload,
            "summary": "operator returned seat after captcha",
        },
    )

    detail = service.get_environment_detail(lease.environment_id, limit=10)

    assert detail is not None
    assert detail["host_event_summary"]["runtime_mechanism"] == "runtime_event_bus"
    assert detail["host_event_summary"]["is_truth_store"] is False
    assert detail["host_event_summary"]["scheduler_inputs"]["active_blocker_family"] == (
        "modal-uac-login"
    )
    assert detail["host_event_summary"]["scheduler_inputs"]["human_handoff_active"] is True
    host_events_by_name = {
        item["event_name"]: item
        for item in detail["host_events"]
    }
    assert host_events_by_name["host.human-takeover"]["event_family"] == (
        "human-handoff-return"
    )
    assert host_events_by_name["host.human-takeover"][
        "recommended_runtime_response"
    ] == "handoff"
    assert host_events_by_name["host.human-return-ready"]["event_family"] == (
        "human-handoff-return"
    )
    assert host_events_by_name["host.human-return-ready"][
        "recommended_runtime_response"
    ] == "recover"
    pending_by_name = {
        item["event_name"]: item
        for item in detail["host_event_summary"]["pending_recovery_events"]
    }
    assert pending_by_name["host.human-takeover"]["legal_recovery_path"] == {
        "decision": "handoff",
        "resume_kind": "resume-environment",
        "checkpoint_ref": "checkpoint:captcha",
        "verification_channel": "runtime-center-self-check",
        "return_condition": "captcha-cleared",
    }
    assert pending_by_name["host.human-return-ready"]["legal_recovery_path"] == {
        "decision": "recover",
        "resume_kind": "resume-environment",
        "checkpoint_ref": "checkpoint:captcha",
        "verification_channel": "runtime-center-self-check",
        "return_condition": "captcha-cleared",
    }


def test_session_detail_host_runtime_projection_handles_partial_metadata(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=5151,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="console",
        session_id="minimal",
        owner="worker-1",
        ttl_seconds=60,
    )
    session = session_repo.get_session(lease.id)
    assert session is not None
    session_repo.upsert_session(
        session.model_copy(
            update={
                "metadata": {},
            },
        ),
    )
    mount = env_repo.get_environment(lease.environment_id)
    assert mount is not None
    env_repo.upsert_environment(
        mount.model_copy(
            update={
                "metadata": {},
            },
        ),
    )

    detail = service.get_session_detail(lease.id, limit=5)

    assert detail is not None
    assert detail["host_contract"]["host_mode"] is None
    assert detail["host_contract"]["lease_class"] is None
    assert detail["host_contract"]["access_mode"] is None
    assert detail["seat_runtime"]["is_projection"] is True
    assert detail["host_companion_session"]["is_projection"] is True
    assert detail["cooperative_adapter_availability"]["is_projection"] is True
    assert detail["cooperative_adapter_availability"]["browser_companion"]["available"] is False
    assert detail["cooperative_adapter_availability"]["document_bridge"]["available"] is False
    assert detail["cooperative_adapter_availability"]["windows_app_adapters"]["available"] is False
    assert detail["workspace_graph"]["is_projection"] is True
    assert detail["workspace_graph"]["clipboard_refs"] == []
    assert detail["workspace_graph"]["download_bucket_refs"] == []
    assert detail["workspace_graph"]["lock_refs"] == []
    assert detail["workspace_graph"]["active_surface_refs"] == []
    assert detail["workspace_graph"]["workspace_components"] == {
        "browser_context_count": 0,
        "app_window_count": 0,
        "file_doc_count": 0,
        "clipboard_count": 0,
        "download_bucket_count": 0,
        "lock_count": 0,
    }
    assert detail["workspace_graph"]["handoff_checkpoint"] == {
        "state": None,
        "reason": None,
        "owner_ref": None,
        "resume_kind": "resume-environment",
        "verification_channel": None,
        "checkpoint_ref": None,
        "return_condition": None,
        "summary": None,
    }
    assert _workspace_graph_lock_view(detail) == []
    assert _workspace_graph_surface_view(detail) == []
    assert _workspace_graph_ownership_collision_view(detail) == {
        "seat_owner_ref": "worker-1",
        "active_surface_owner_ref": "worker-1",
        "account_scope_ref": None,
        "handoff_owner_ref": None,
        "shared_account_scope_refs": [],
        "writer_conflict_refs": [],
        "writer_conflict_scope_refs": [],
    }
    assert detail["host_event_summary"]["runtime_mechanism"] == "runtime_event_bus"
    assert detail["host_event_summary"]["is_truth_store"] is False
    assert detail["host_event_summary"]["supported_families"] == [
        "active-window",
        "modal-uac-login",
        "download-completed",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    ]
    assert detail["host_event_summary"]["family_counts"] == {}
    assert detail["host_event_summary"]["latest_event_by_family"] == {}
    assert detail["host_event_summary"]["active_alert_families"] == []
    assert detail["host_events"] == []


def test_environment_and_session_detail_expose_execution_grade_host_twin_projection(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)
    event_bus = RuntimeEventBus(max_events=50)
    service.set_runtime_event_bus(event_bus)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-phase45-host-twin",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab:web:jd:seller-center:main",
            "page_id": "page:jd:seller-center:home",
            "active_window_ref": "window:excel:main",
            "window_scope": "window:excel:main",
            "process_id": 4242,
            "cwd": "D:/word/copaw",
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "handoff_state": "agent-attached",
            "handoff_reason": "captcha-required",
            "handoff_owner_ref": "human-operator:alice",
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "account_scope_ref": "windows:user:alice",
            "browser_mode": "tab-attached",
            "login_state": "authenticated",
            "tab_scope": "single-tab",
            "active_tab_ref": "page:jd:seller-center:home",
            "site_contract_ref": "site-contract:jd:seller-center:writer",
            "site_contract_status": "verified-writer",
            "download_policy": "workspace-bucket",
            "downloads": True,
            "last_verified_url": "https://seller.jd.com/home",
            "last_verified_dom_anchor": "#shop-header",
            "app_identity": "excel",
            "active_process_ref": "process:4242",
            "app_contract_ref": "app-contract:excel:writer",
            "app_contract_status": "verified-writer",
            "control_channel": "accessibility-tree",
            "writer_lock_scope": "workbook:weekly-report",
            "window_anchor_summary": "Excel > Weekly Report.xlsx > Sheet1!A1",
            "download_verification": True,
            "save_reopen_verification": True,
            "handoff_checkpoint_ref": "checkpoint:captcha",
            "handoff_return_condition": "captcha-cleared",
            "pending_handoff_summary": "agent-attached",
        },
    )
    base_payload = {
        "session_mount_id": lease.id,
        "environment_id": lease.environment_id,
        "checkpoint_ref": "checkpoint:captcha",
        "verification_channel": "runtime-center-self-check",
    }
    event_bus.publish(
        topic="desktop",
        action="uac-prompt",
        payload={
            **base_payload,
            "prompt_kind": "uac",
            "window_title": "User Account Control",
        },
    )
    event_bus.publish(
        topic="process",
        action="process-restarted",
        payload={
            **base_payload,
            "process_ref": "process:4242",
        },
    )

    environment_detail = service.get_environment_detail(lease.environment_id, limit=10)
    session_detail = service.get_session_detail(lease.id, limit=10)

    assert environment_detail is not None
    assert session_detail is not None
    assert environment_detail["host_twin"]["projection_kind"] == "host_twin_projection"
    assert environment_detail["host_twin"]["is_projection"] is True
    assert environment_detail["host_twin"]["is_truth_store"] is False
    assert session_detail["host_twin"]["projection_kind"] == "host_twin_projection"
    assert session_detail["host_twin"]["is_projection"] is True
    assert session_detail["host_twin"]["is_truth_store"] is False
    assert environment_detail["host_twin_summary"]["host_companion_status"] == "attached"
    assert session_detail["host_twin_summary"]["host_companion_status"] == "attached"
    expected_host_twin = {
        "seat_owner_ref": "worker-1",
        "ownership_source": "workspace_graph.ownership",
        "writable_surface_kinds": [],
        "continuity_valid": True,
        "continuity_source": "live-handle",
        "trusted_anchor_refs": [
            "#shop-header",
            "Excel > Weekly Report.xlsx > Sheet1!A1",
            "checkpoint:captcha",
        ],
        "recovery_decision": "handoff",
        "recovery_resume_kind": "resume-environment",
        "recovery_checkpoint_ref": "checkpoint:captcha",
        "recovery_return_condition": "captcha-cleared",
        "active_blocker_families": ["modal-uac-login"],
        "scheduler_blocking_family": "modal-uac-login",
        "scheduler_recovery_family": "process-exit-restart",
        "scheduler_requires_human_return": True,
        "pending_recovery_families": [
            "modal-uac-login",
            "process-exit-restart",
        ],
        "app_family_keys": [
            "browser_backoffice",
            "desktop_specialized",
            "messaging_workspace",
            "office_document",
        ],
        "active_app_families": [
            "browser_backoffice",
            "office_document",
        ],
        "browser_backoffice_contract_status": "verified-writer",
        "office_document_writer_lock_scope": "workbook:weekly-report",
        "coordination_selected_seat_ref": lease.environment_id,
        "coordination_seat_policy": "sticky-active-seat",
        "coordination_scheduler_action": "handoff",
        "coordination_contention_severity": "blocked",
        "host_companion_status": "attached",
        "host_companion_source": "live-handle",
        "host_companion_session_mount_id": lease.id,
        "seat_count": 1,
        "candidate_seat_refs": [lease.environment_id],
        "ready_app_family_keys": [
            "browser_backoffice",
            "office_document",
        ],
        "blocked_app_family_keys": [
            "desktop_specialized",
            "messaging_workspace",
        ],
    }
    assert _host_twin_contract_view(environment_detail) == expected_host_twin
    assert _host_twin_contract_view(session_detail) == expected_host_twin


def test_host_twin_recovery_handoff_long_run_prefers_current_host_truth_over_stale_blocker_history(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)
    event_bus = RuntimeEventBus(max_events=50)
    service.set_runtime_event_bus(event_bus)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-phase6-long-run",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab:web:jd:seller-center:main",
            "page_id": "page:jd:seller-center:home",
            "active_window_ref": "window:excel:orders",
            "window_scope": "window:excel:orders",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "handoff_state": "agent-attached",
            "handoff_reason": "captcha-required",
            "handoff_owner_ref": "human-operator:alice",
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "account_scope_ref": "windows:user:alice",
            "browser_mode": "tab-attached",
            "login_state": "authenticated",
            "tab_scope": "single-tab",
            "active_tab_ref": "page:jd:seller-center:home",
            "site_contract_ref": "site-contract:jd:seller-center:writer",
            "site_contract_status": "verified-writer",
            "download_policy": "workspace-bucket",
            "downloads": True,
            "last_verified_url": "https://seller.jd.com/home",
            "last_verified_dom_anchor": "#shop-header",
            "app_identity": "excel",
            "active_process_ref": "process:4242",
            "app_contract_ref": "app-contract:excel:writer",
            "app_contract_status": "verified-writer",
            "control_channel": "accessibility-tree",
            "writer_lock_scope": "workbook:orders",
            "window_anchor_summary": "Excel > Orders.xlsx > Sheet1!A1",
            "handoff_checkpoint_ref": "checkpoint:captcha",
            "handoff_return_condition": "captcha-cleared",
            "pending_handoff_summary": "operator finishing captcha",
        },
    )
    base_payload = {
        "session_mount_id": lease.id,
        "environment_id": lease.environment_id,
        "checkpoint_ref": "checkpoint:captcha",
        "verification_channel": "runtime-center-self-check",
        "return_condition": "captcha-cleared",
        "handoff_owner_ref": "human-operator:alice",
    }
    event_bus.publish(
        topic="desktop",
        action="uac-prompt",
        payload={
            **base_payload,
            "prompt_kind": "uac",
            "window_title": "User Account Control",
        },
    )
    event_bus.publish(
        topic="process",
        action="process-restarted",
        payload={
            **base_payload,
            "process_ref": "process:4242",
        },
    )
    event_bus.publish(
        topic="host",
        action="human-takeover",
        payload={
            **base_payload,
            "summary": "operator taking over for captcha",
        },
    )
    event_bus.publish(
        topic="host",
        action="human-return-ready",
        payload={
            **base_payload,
            "summary": "operator returned seat after captcha",
        },
    )

    session = session_repo.get_session(lease.id)
    assert session is not None
    resumed_metadata = dict(session.metadata)
    resumed_metadata.update(
        {
            "handoff_state": None,
            "handoff_reason": None,
            "handoff_owner_ref": None,
            "current_gap_or_blocker": None,
            "pending_handoff_summary": None,
        },
    )
    session_repo.upsert_session(
        session.model_copy(update={"metadata": resumed_metadata}),
    )
    mount = env_repo.get_environment(lease.environment_id)
    assert mount is not None
    resumed_mount_metadata = dict(mount.metadata)
    resumed_mount_metadata.update(
        {
            "handoff_state": None,
            "handoff_reason": None,
            "handoff_owner_ref": None,
            "current_gap_or_blocker": None,
            "pending_handoff_summary": None,
        },
    )
    env_repo.upsert_environment(
        mount.model_copy(update={"metadata": resumed_mount_metadata}),
    )

    detail = service.get_environment_detail(lease.environment_id, limit=10)

    assert detail is not None
    assert detail["recovery"]["status"] == "attached"
    assert detail["host_event_summary"]["latest_handoff_event"]["event_name"] == (
        "host.human-return-ready"
    )
    assert {
        item["event_family"]
        for item in detail["host_event_summary"]["pending_recovery_events"]
    } >= {"modal-uac-login", "process-exit-restart", "human-handoff-return"}
    assert detail["host_twin"]["blocked_surfaces"] == []
    assert "browser" in detail["host_twin"]["writable_surface_kinds"]
    assert detail["host_twin"]["app_family_twins"]["browser_backoffice"]["active"] is True
    assert detail["host_twin"]["app_family_twins"]["office_document"]["active"] is True
    assert detail["host_twin"]["continuity"]["requires_human_return"] is False
    assert detail["host_twin"]["legal_recovery"]["path"] == "resume-environment"
    assert detail["host_twin"]["latest_blocking_event"]["event_family"] is None
    assert detail["host_twin"]["scheduler_inputs"]["active_blocker_family"] is None
    assert detail["host_twin"]["scheduler_inputs"]["active_recovery_family"] is None
    assert detail["host_twin"]["coordination"]["recommended_scheduler_action"] == (
        "proceed"
    )
    assert (
        detail["host_twin"]["coordination"]["contention_forecast"]["severity"] == "clear"
    )


def test_host_twin_summary_treats_return_ready_as_non_blocking_even_if_stale_handoff_metadata_still_exists(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)
    event_bus = RuntimeEventBus(max_events=50)
    service.set_runtime_event_bus(event_bus)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-phase6-return-ready-stale-metadata",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab:web:jd:seller-center:main",
            "page_id": "page:jd:seller-center:home",
            "active_window_ref": "window:excel:orders",
            "window_scope": "window:excel:orders",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "handoff_state": "agent-attached",
            "handoff_reason": "captcha-required",
            "handoff_owner_ref": "human-operator:alice",
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "account_scope_ref": "windows:user:alice",
            "browser_mode": "tab-attached",
            "login_state": "authenticated",
            "tab_scope": "single-tab",
            "active_tab_ref": "page:jd:seller-center:home",
            "site_contract_ref": "site-contract:jd:seller-center:writer",
            "site_contract_status": "verified-writer",
            "download_policy": "workspace-bucket",
            "downloads": True,
            "last_verified_url": "https://seller.jd.com/home",
            "last_verified_dom_anchor": "#shop-header",
            "app_identity": "excel",
            "active_process_ref": "process:4242",
            "app_contract_ref": "app-contract:excel:writer",
            "app_contract_status": "verified-writer",
            "control_channel": "accessibility-tree",
            "writer_lock_scope": "workbook:orders",
            "window_anchor_summary": "Excel > Orders.xlsx > Sheet1!A1",
            "handoff_checkpoint_ref": "checkpoint:captcha",
            "handoff_return_condition": "captcha-cleared",
            "pending_handoff_summary": "operator finishing captcha",
        },
    )
    base_payload = {
        "session_mount_id": lease.id,
        "environment_id": lease.environment_id,
        "checkpoint_ref": "checkpoint:captcha",
        "verification_channel": "runtime-center-self-check",
        "return_condition": "captcha-cleared",
        "handoff_owner_ref": "human-operator:alice",
    }
    event_bus.publish(
        topic="desktop",
        action="uac-prompt",
        payload={
            **base_payload,
            "prompt_kind": "uac",
            "window_title": "User Account Control",
        },
    )
    event_bus.publish(
        topic="process",
        action="process-restarted",
        payload={
            **base_payload,
            "process_ref": "process:4242",
        },
    )
    event_bus.publish(
        topic="host",
        action="human-return-ready",
        payload={
            **base_payload,
            "summary": "operator returned seat after captcha",
        },
    )

    detail = service.get_environment_detail(lease.environment_id, limit=10)

    assert detail is not None
    summary = _mapping(detail.get("host_twin_summary"))
    assert detail["host_event_summary"]["latest_handoff_event"]["event_name"] == (
        "host.human-return-ready"
    )
    assert detail["host_twin"]["coordination"]["recommended_scheduler_action"] == "proceed"
    assert detail["host_twin"]["coordination"]["contention_forecast"]["severity"] == "clear"
    assert detail["host_twin"]["blocked_surfaces"] == []
    assert detail["host_twin"]["continuity"]["requires_human_return"] is False
    assert detail["host_twin"]["scheduler_inputs"]["active_blocker_family"] is None
    assert detail["host_twin"]["scheduler_inputs"]["active_recovery_family"] is None
    assert summary["recommended_scheduler_action"] == "proceed"
    assert summary["blocked_surface_count"] == 0
    assert summary["legal_recovery_mode"] == "resume-environment"


def test_host_twin_multi_seat_selects_alternate_ready_seat_for_same_owner(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    blocked_seat = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-phase-next-a",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "active_window_ref": "window:excel:blocked",
            "window_scope": "window:excel:blocked",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "account_scope_ref": "windows:user:alice",
            "app_identity": "excel",
            "app_contract_status": "verified-writer",
            "writer_lock_scope": "workbook:weekly-report",
            "handoff_state": "active",
            "handoff_reason": "captcha-required",
            "handoff_owner_ref": "human-operator:alice",
            "pending_handoff_summary": "operator is resolving captcha",
            "current_gap_or_blocker": "writer path is waiting for human return",
            "active_surface_mix": ["desktop", "document"],
        },
    )
    alternate_seat = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-phase-next-b",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "active_window_ref": "window:excel:ready",
            "window_scope": "window:excel:ready",
            "process_id": 4343,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "account_scope_ref": "windows:user:alice",
            "app_identity": "excel",
            "app_contract_status": "verified-writer",
            "writer_lock_scope": "workbook:weekly-report",
            "handoff_state": "agent-attached",
            "active_surface_mix": ["desktop", "document"],
        },
    )

    detail = service.get_environment_detail(blocked_seat.environment_id, limit=20)

    assert detail is not None
    assert sorted(detail["seat_runtime"]["candidate_seat_refs"]) == sorted(
        [blocked_seat.environment_id, alternate_seat.environment_id],
    )
    assert detail["seat_runtime"]["selected_seat_ref"] == alternate_seat.environment_id
    assert detail["seat_runtime"]["selected_session_mount_id"] == alternate_seat.id
    assert detail["host_twin"]["coordination"]["selected_seat_ref"] == (
        alternate_seat.environment_id
    )
    assert detail["host_twin"]["coordination"]["selected_session_mount_id"] == (
        alternate_seat.id
    )
    assert detail["host_twin_summary"]["seat_count"] == 2
    assert sorted(detail["host_twin_summary"]["candidate_seat_refs"]) == sorted(
        [blocked_seat.environment_id, alternate_seat.environment_id],
    )
    assert detail["host_twin_summary"]["selected_seat_ref"] == alternate_seat.environment_id
    assert detail["host_twin_summary"]["selected_session_mount_id"] == alternate_seat.id


def test_host_twin_multi_agent_contention_blocks_shared_writer_scope_across_seats(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    seat_a = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-phase-next-contention-a",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "active_window_ref": "window:excel:a",
            "window_scope": "window:excel:a",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "account_scope_ref": "windows:user:alice",
            "app_identity": "excel",
            "app_contract_status": "verified-writer",
            "writer_lock_scope": "workbook:weekly-report",
            "handoff_state": "agent-attached",
            "active_surface_mix": ["desktop", "document"],
        },
    )
    seat_b = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-phase-next-contention-b",
        user_id="alice",
        owner="worker-2",
        ttl_seconds=60,
        handle={
            "active_window_ref": "window:excel:b",
            "window_scope": "window:excel:b",
            "process_id": 4343,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "account_scope_ref": "windows:user:alice",
            "app_identity": "excel",
            "app_contract_status": "verified-writer",
            "writer_lock_scope": "workbook:weekly-report",
            "handoff_state": "agent-attached",
            "active_surface_mix": ["desktop", "document"],
        },
    )

    detail = service.get_environment_detail(seat_a.environment_id, limit=20)

    assert detail is not None
    assert sorted(detail["host_twin_summary"]["candidate_seat_refs"]) == sorted(
        [seat_a.environment_id, seat_b.environment_id],
    )
    assert detail["host_twin_summary"]["seat_count"] == 2
    assert detail["host_twin"]["coordination"]["recommended_scheduler_action"] == "handoff"
    assert detail["host_twin"]["coordination"]["contention_forecast"]["severity"] == (
        "blocked"
    )
    assert "worker-2" in str(
        detail["host_twin"]["coordination"]["contention_forecast"]["reason"],
    )


def test_host_twin_multi_seat_prefers_same_work_context_over_shared_workspace_scope(
    tmp_path,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    current_seat = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-work-context-a",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "active_window_ref": "window:excel:a",
            "window_scope": "window:excel:a",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "work_context_id": "ctx-seat-a",
            "account_scope_ref": "windows:user:alice",
            "app_identity": "excel",
            "app_contract_status": "verified-writer",
            "writer_lock_scope": "workbook:weekly-report",
            "handoff_state": "active",
            "handoff_reason": "waiting-human",
            "handoff_owner_ref": "human-operator:alice",
            "current_gap_or_blocker": "awaiting operator return",
            "active_surface_mix": ["desktop", "document"],
        },
    )
    other_context_seat = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-work-context-b",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "active_window_ref": "window:excel:b",
            "window_scope": "window:excel:b",
            "process_id": 4343,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "work_context_id": "ctx-seat-b",
            "account_scope_ref": "windows:user:alice",
            "app_identity": "excel",
            "app_contract_status": "verified-writer",
            "writer_lock_scope": "workbook:weekly-report",
            "handoff_state": "agent-attached",
            "active_surface_mix": ["desktop", "document"],
        },
    )

    detail = service.get_environment_detail(current_seat.environment_id, limit=20)

    assert detail is not None
    assert detail["seat_runtime"]["selected_seat_ref"] == current_seat.environment_id
    assert detail["seat_runtime"]["selected_session_mount_id"] == current_seat.id
    assert sorted(detail["seat_runtime"]["candidate_seat_refs"]) == sorted(
        [current_seat.environment_id],
    )
    assert other_context_seat.environment_id not in detail["seat_runtime"]["candidate_seat_refs"]


def test_environment_detail_projects_work_context_from_mount_session_truth(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-work-context-detail",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab:web:jd:seller-center:main",
            "page_id": "page:jd:seller-center:home",
            "active_window_ref": "window:excel:main",
            "window_scope": "window:excel:main",
            "process_id": 4242,
            "cwd": "D:/word/copaw",
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "work_context_id": "ctx-browser-desktop-1",
            "account_scope_ref": "windows:user:alice",
            "browser_mode": "tab-attached",
            "profile_ref": "profile:copaw:main",
            "attach_transport_ref": "transport:cdp:local",
            "provider_session_ref": "browser-session:web:main",
            "browser_companion_transport_ref": "transport:cdp:local",
            "browser_companion_status": "attached",
            "app_identity": "excel",
            "app_contract_status": "verified-writer",
            "writer_lock_scope": "workbook:weekly-report",
            "handoff_state": "agent-attached",
            "active_surface_mix": ["browser", "desktop", "document"],
        },
    )

    detail = service.get_environment_detail(lease.environment_id, limit=20)

    assert detail is not None
    assert detail["host_contract"]["work_context_id"] == "ctx-browser-desktop-1"
    assert detail["seat_runtime"]["work_context_id"] == "ctx-browser-desktop-1"
    assert detail["workspace_graph"]["work_context_id"] == "ctx-browser-desktop-1"
    assert (
        detail["workspace_graph"]["ownership"]["work_context_id"]
        == "ctx-browser-desktop-1"
    )


def test_environment_detail_projects_browser_attach_runtime_truth(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-browser-attach-detail",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={
            "browser": "tab:web:jd:seller-center:main",
            "page_id": "page:jd:seller-center:home",
            "process_id": 4242,
        },
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "browser",
            "session_scope": "desktop-user-session",
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
            "work_context_id": "ctx-browser-attach",
            "browser_mode": "tab-attached",
            "profile_ref": "profile:copaw:main",
            "navigation_guard": {
                "allowed_hosts": ["seller.jd.com"],
                "blocked_hosts": ["ads.jd.com"],
            },
            "action_timeout_seconds": 12.5,
            "handoff_state": "agent-attached",
        },
    )
    service.register_browser_companion(
        session_mount_id=lease.id,
        transport_ref="transport:browser-companion:localhost",
        status="attached",
        available=True,
        provider_session_ref="browser-session:web:main",
    )
    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="transport:cdp:local",
        status="attached",
        browser_session_ref="browser-session:web:main",
        browser_scope_ref="site:jd:seller-center",
        reconnect_token="reconnect-token-1",
    )

    detail = service.get_environment_detail(lease.environment_id, limit=20)

    assert detail is not None
    assert detail["browser_site_contract"]["attach_transport_ref"] == "transport:cdp:local"
    assert detail["browser_site_contract"]["attach_session_ref"] == "browser-session:web:main"
    assert detail["browser_site_contract"]["attach_scope_ref"] == "site:jd:seller-center"
    assert detail["browser_site_contract"]["attach_reconnect_token"] == "reconnect-token-1"
    assert detail["browser_site_contract"]["navigation_guard"] == {
        "allowed_hosts": ["seller.jd.com"],
        "blocked_hosts": ["ads.jd.com"],
    }
    assert detail["browser_site_contract"]["action_timeout_seconds"] == 12.5
    assert detail["browser_site_contract"]["browser_channel"] == "browser-mcp"
    assert detail["browser_site_contract"]["browser_channel_status"] == "ready"
    assert detail["browser_site_contract"]["browser_channel_health"] == "healthy"
    assert (
        detail["browser_site_contract"]["browser_channel_resolution"]["selected_channel"]
        == "browser-mcp"
    )


def test_shared_operator_abort_state_uses_same_session_environment_truth(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)

    lease = service.acquire_session_lease(
        channel="desktop",
        session_id="seat-operator-abort",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
        },
    )

    requested = service.set_shared_operator_abort_state(
        session_mount_id=lease.id,
        channel="browser",
        reason="operator emergency stop",
    )
    session = session_repo.get_session(lease.id)
    environment = env_repo.get_environment(lease.environment_id)
    assert requested is not None
    assert session is not None
    assert environment is not None
    assert session.metadata["operator_abort_state"]["requested"] is True
    assert session.metadata["operator_abort_state"]["channel"] == "browser"
    assert session.metadata["operator_abort_state"]["reason"] == "operator emergency stop"
    assert isinstance(session.metadata["operator_abort_state"]["requested_at"], str)
    assert environment.metadata["operator_abort_state"]["requested"] is True
    assert environment.metadata["operator_abort_state"]["channel"] == "browser"

    cleared = service.clear_shared_operator_abort_state(session_mount_id=lease.id)
    session = session_repo.get_session(lease.id)
    environment = env_repo.get_environment(lease.environment_id)
    assert cleared is not None
    assert session is not None
    assert environment is not None
    assert session.metadata["operator_abort_state"]["requested"] is False
    assert session.metadata["operator_abort_state"]["channel"] == "browser"
    assert session.metadata["operator_abort_state"]["reason"] == "operator abort cleared"
    assert isinstance(session.metadata["operator_abort_state"]["requested_at"], str)
    assert environment.metadata["operator_abort_state"]["requested"] is False
