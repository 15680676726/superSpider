# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import SQLiteStateStore
from copaw.state.repositories import SqliteMemorySleepRepository

from copaw.memory.continuity_detail_service import ContinuityDetailService


def test_continuity_detail_service_marks_user_pinned_details_as_must_keep(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteMemorySleepRepository(store)
    service = ContinuityDetailService(repository=repository)

    detail = service.upsert_manual_pin(
        scope_type="work_context",
        scope_id="ctx-1",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        detail_key="risk-boundary",
        detail_text="Do not average down after stop-loss.",
        pinned_until_phase="week-1",
    )

    assert detail.pinned is True
    assert detail.source_kind == "manual"
    assert detail.pinned_until_phase == "week-1"

    stored = repository.list_continuity_details(
        scope_type="work_context",
        scope_id="ctx-1",
        status="active",
        pinned_only=True,
    )
    assert [item.detail_key for item in stored] == ["risk-boundary"]
