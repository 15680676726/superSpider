# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import IndustryMemorySlotPreferenceRecord, SQLiteStateStore
from copaw.state.repositories import SqliteMemorySleepRepository

from copaw.memory.structure_enhancement_service import StructureEnhancementService


def test_structure_enhancement_service_promotes_repeated_dynamic_slots(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteMemorySleepRepository(store)
    service = StructureEnhancementService(repository=repository, promotion_threshold=2)

    result = service.evaluate_dynamic_slots(
        industry_instance_id="industry-1",
        candidate_slots=["character_state", "character_state", "foreshadow"],
    )

    assert "character_state" in result.promoted_slots
    active_preferences = repository.list_slot_preferences(
        industry_instance_id="industry-1",
        status="active",
    )
    assert [item.slot_key for item in active_preferences] == ["character_state"]


def test_structure_enhancement_service_demotes_stale_slots(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteMemorySleepRepository(store)
    repository.upsert_slot_preference(
        IndustryMemorySlotPreferenceRecord(
            preference_id="pref:industry-1:camera-rhythm",
            industry_instance_id="industry-1",
            slot_key="camera_rhythm",
            slot_label="Camera Rhythm",
            scope_level="industry",
            scope_id="industry-1",
            source_kind="sleep",
            promotion_count=2,
            status="active",
        )
    )
    service = StructureEnhancementService(repository=repository, promotion_threshold=2)

    result = service.evaluate_dynamic_slots(
        industry_instance_id="industry-1",
        candidate_slots=[],
        existing_slots=["camera_rhythm"],
    )

    assert "camera_rhythm" in result.demoted_slots
    inactive_preferences = repository.list_slot_preferences(
        industry_instance_id="industry-1",
        status="inactive",
    )
    assert [item.slot_key for item in inactive_preferences] == ["camera_rhythm"]
