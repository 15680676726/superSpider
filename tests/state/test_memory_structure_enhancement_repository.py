# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib

from copaw.state import SQLiteStateStore
from copaw.state.repositories import SqliteMemorySleepRepository


def test_slot_preference_repository_round_trip(tmp_path) -> None:
    memory_models = importlib.import_module("copaw.state.models_memory")
    record_type = getattr(memory_models, "IndustryMemorySlotPreferenceRecord", None)

    assert record_type is not None

    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteMemorySleepRepository(store)

    assert hasattr(repository, "upsert_slot_preference")
    assert hasattr(repository, "list_slot_preferences")

    saved = repository.upsert_slot_preference(
        record_type(
            preference_id="pref:novel:characters",
            industry_instance_id="industry-1",
            slot_key="character_state",
            slot_label="Character State",
            scope_level="industry",
            scope_id="industry-1",
            source_kind="sleep",
            status="active",
            promotion_count=3,
            metadata={"origin": "dynamic-slot"},
        )
    )

    assert saved.slot_key == "character_state"
    assert saved.promotion_count == 3

    loaded = repository.list_slot_preferences(
        industry_instance_id="industry-1",
        status="active",
    )
    assert [item.preference_id for item in loaded] == ["pref:novel:characters"]
    assert loaded[0].metadata["origin"] == "dynamic-slot"


def test_continuity_detail_repository_round_trip(tmp_path) -> None:
    memory_models = importlib.import_module("copaw.state.models_memory")
    record_type = getattr(memory_models, "MemoryContinuityDetailRecord", None)

    assert record_type is not None

    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteMemorySleepRepository(store)

    assert hasattr(repository, "upsert_continuity_detail")
    assert hasattr(repository, "list_continuity_details")

    saved = repository.upsert_continuity_detail(
        record_type(
            detail_id="detail:ctx-1:hero-rule",
            scope_type="work_context",
            scope_id="ctx-1",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            detail_key="hero_rule",
            detail_label="Hero Rule",
            detail_text="The hero cannot break the oath before chapter 10.",
            source_kind="model",
            source_ref="sleep-job-1",
            pinned=True,
            pinned_until_phase="chapter-10",
            status="active",
            evidence_refs=["evidence:hero-rule"],
            metadata={"importance": "high"},
        )
    )

    assert saved.pinned_until_phase == "chapter-10"
    assert saved.pinned is True

    loaded = repository.list_continuity_details(
        scope_type="work_context",
        scope_id="ctx-1",
        status="active",
    )
    assert [item.detail_id for item in loaded] == ["detail:ctx-1:hero-rule"]
    assert loaded[0].detail_key == "hero_rule"
    assert loaded[0].metadata["importance"] == "high"
