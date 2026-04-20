# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.main_brain_scope_snapshot_service import MainBrainScopeSnapshotService


def test_mark_scope_dirty_only_invalidates_matching_scope_snapshot() -> None:
    versions = {
        "work-1": 1,
        "work-2": 1,
    }

    def _scope_key_resolver(*, request, detail, owner_agent_id):
        _ = (detail, owner_agent_id)
        return request.scope_key

    def _scope_snapshot_signature_builder(*, request, detail, owner_agent_id):
        _ = (request, detail, owner_agent_id)
        return "stable-signature"

    def _scope_snapshot_builder(*, request, detail, owner_agent_id):
        _ = (detail, owner_agent_id)
        return f"snapshot-v{versions[request.scope_key]}"

    service = MainBrainScopeSnapshotService(
        stable_prefix_builder=lambda **_: "stable",
        stable_prefix_signature_builder=lambda **_: "stable",
        scope_snapshot_builder=_scope_snapshot_builder,
        scope_snapshot_signature_builder=_scope_snapshot_signature_builder,
        scope_key_resolver=_scope_key_resolver,
    )

    work_1_request = SimpleNamespace(session_id="session-1", user_id="user-1", scope_key="work-1")
    work_2_request = SimpleNamespace(session_id="session-1", user_id="user-1", scope_key="work-2")

    first_work_1 = service.resolve_prompt_context(
        request=work_1_request,
        detail=None,
        owner_agent_id=None,
    )
    first_work_2 = service.resolve_prompt_context(
        request=work_2_request,
        detail=None,
        owner_agent_id=None,
    )

    assert first_work_1.scope_snapshot == "snapshot-v1"
    assert first_work_2.scope_snapshot == "snapshot-v1"

    versions["work-1"] = 2
    versions["work-2"] = 99
    service.mark_scope_dirty(scope_level="work_context", scope_id="work-1")

    refreshed_work_1 = service.resolve_prompt_context(
        request=work_1_request,
        detail=None,
        owner_agent_id=None,
    )
    cached_work_2 = service.resolve_prompt_context(
        request=work_2_request,
        detail=None,
        owner_agent_id=None,
    )

    assert refreshed_work_1.scope_snapshot == "snapshot-v2"
    assert refreshed_work_1.scope_cache_hit is False
    assert cached_work_2.scope_snapshot == "snapshot-v1"
    assert cached_work_2.scope_cache_hit is True
