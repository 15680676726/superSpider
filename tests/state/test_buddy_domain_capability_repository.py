# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import BuddyDomainCapabilityRecord, HumanProfile, SQLiteStateStore
from copaw.state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteHumanProfileRepository,
)


def _repository(tmp_path) -> SqliteBuddyDomainCapabilityRepository:
    store = SQLiteStateStore(tmp_path / "buddy-domain-capability.sqlite3")
    SqliteHumanProfileRepository(store).upsert_profile(
        HumanProfile(
            profile_id="profile-1",
            display_name="Alex",
            profession="Writer",
            current_stage="building",
            interests=["writing"],
            strengths=["clarity"],
            constraints=["time"],
            goal_intention="Build a durable writing direction",
        )
    )
    return SqliteBuddyDomainCapabilityRepository(store)


def test_repository_round_trips_active_domain_capability(tmp_path) -> None:
    repository = _repository(tmp_path)
    record = BuddyDomainCapabilityRecord(
        domain_id="domain-writing",
        profile_id="profile-1",
        domain_key="writing",
        domain_label="写作",
        status="active",
        capability_score=48,
        evolution_stage="capable",
    )

    repository.upsert_domain_capability(record)
    loaded = repository.get_active_domain_capability("profile-1")

    assert loaded is not None
    assert loaded.domain_id == "domain-writing"
    assert loaded.domain_label == "写作"
    assert loaded.capability_score == 48


def test_repository_archives_previous_active_records_except_selected_one(tmp_path) -> None:
    repository = _repository(tmp_path)
    first = BuddyDomainCapabilityRecord(
        domain_id="domain-stock",
        profile_id="profile-1",
        domain_key="stocks",
        domain_label="股票",
        status="active",
        capability_score=72,
        evolution_stage="seasoned",
    )
    second = BuddyDomainCapabilityRecord(
        domain_id="domain-writing",
        profile_id="profile-1",
        domain_key="writing",
        domain_label="写作",
        status="active",
        capability_score=38,
        evolution_stage="bonded",
    )

    repository.upsert_domain_capability(first)
    repository.upsert_domain_capability(second)
    repository.archive_active_domain_capabilities(
        "profile-1",
        except_domain_id="domain-writing",
    )
    records = repository.list_domain_capabilities("profile-1")

    archived = next(record for record in records if record.domain_id == "domain-stock")
    preserved = next(record for record in records if record.domain_id == "domain-writing")
    assert archived.status == "archived"
    assert archived.capability_score == 72
    assert preserved.status == "active"


def test_repository_finds_archived_domains_by_key_for_restore(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_domain_capability(
        BuddyDomainCapabilityRecord(
            domain_id="domain-writing",
            profile_id="profile-1",
            domain_key="writing",
            domain_label="写作",
            status="archived",
            capability_score=52,
            evolution_stage="capable",
        )
    )
    repository.upsert_domain_capability(
        BuddyDomainCapabilityRecord(
            domain_id="domain-fitness",
            profile_id="profile-1",
            domain_key="fitness",
            domain_label="健身",
            status="archived",
            capability_score=16,
            evolution_stage="seed",
        )
    )

    matches = repository.find_domain_capabilities_by_key("profile-1", "writing")

    assert [record.domain_id for record in matches] == ["domain-writing"]
