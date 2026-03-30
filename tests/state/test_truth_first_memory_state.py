# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from copaw.state.models_memory import (
    MemoryEpisodeViewRecord,
    MemoryFactIndexRecord,
    MemoryProfileViewRecord,
)
from copaw.state.repositories.sqlite_memory import (
    SqliteMemoryEpisodeViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryProfileViewRepository,
)
from copaw.state.store import SQLiteStateStore


def _utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _make_fact(
    entry_id: str,
    *,
    source_ref: str | None = None,
    scope_type: str = "industry",
    scope_id: str = "industry-1",
    memory_type: str = "fact",
    relation_kind: str = "references",
    supersedes_entry_id: str | None = None,
    is_latest: bool = True,
    valid_from: datetime | None = None,
    expires_at: datetime | None = None,
    confidence_tier: str = "confirmed",
) -> MemoryFactIndexRecord:
    return MemoryFactIndexRecord(
        id=entry_id,
        source_type="agent_report",
        source_ref=source_ref or entry_id,
        scope_type=scope_type,
        scope_id=scope_id,
        owner_agent_id="agent-1",
        industry_instance_id="industry-1",
        title=f"Fact {entry_id}",
        summary=f"Summary for {entry_id}",
        content_text=f"Canonical memory fact {entry_id}.",
        entity_keys=["customer:acme"],
        tags=["memory", "truth-first"],
        evidence_refs=["evidence-1"],
        memory_type=memory_type,
        relation_kind=relation_kind,
        supersedes_entry_id=supersedes_entry_id,
        is_latest=is_latest,
        valid_from=valid_from or _utc("2026-03-30T08:00:00+00:00"),
        expires_at=expires_at,
        confidence_tier=confidence_tier,
    )


def _create_legacy_memory_db(path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE memory_fact_index (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                scope_type TEXT NOT NULL DEFAULT 'global',
                scope_id TEXT NOT NULL,
                owner_agent_id TEXT,
                owner_scope TEXT,
                industry_instance_id TEXT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                content_excerpt TEXT NOT NULL DEFAULT '',
                content_text TEXT NOT NULL DEFAULT '',
                entity_keys_json TEXT NOT NULL DEFAULT '[]',
                opinion_keys_json TEXT NOT NULL DEFAULT '[]',
                tags_json TEXT NOT NULL DEFAULT '[]',
                role_bindings_json TEXT NOT NULL DEFAULT '[]',
                evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                confidence REAL NOT NULL DEFAULT 0.5,
                quality_score REAL NOT NULL DEFAULT 0.5,
                source_updated_at TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX idx_memory_fact_index_source
                ON memory_fact_index(source_type, source_ref);
            """
        )
        conn.execute(
            """
            INSERT INTO memory_fact_index (
                id,
                source_type,
                source_ref,
                scope_type,
                scope_id,
                owner_agent_id,
                owner_scope,
                industry_instance_id,
                title,
                summary,
                content_excerpt,
                content_text,
                entity_keys_json,
                opinion_keys_json,
                tags_json,
                role_bindings_json,
                evidence_refs_json,
                confidence,
                quality_score,
                source_updated_at,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-fact-1",
                "agent_report",
                "report-legacy-1",
                "industry",
                "industry-legacy",
                "agent-legacy",
                "main-brain",
                "industry-legacy",
                "Legacy fact",
                "Legacy summary",
                "Legacy excerpt",
                "Legacy content",
                '["customer:legacy"]',
                "[]",
                '["legacy"]',
                "[]",
                '["evidence-legacy"]',
                0.7,
                0.6,
                None,
                "{}",
                "2026-03-29T09:15:00+00:00",
                "2026-03-29T09:15:00+00:00",
            ),
        )


def test_truth_first_memory_fact_round_trips_evolution_fields(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    fact_repo = SqliteMemoryFactIndexRepository(store)
    fact = _make_fact(
        "memory-fact-1",
        relation_kind="updates",
        supersedes_entry_id="memory-fact-0",
        valid_from=_utc("2026-03-30T09:30:00+00:00"),
        expires_at=_utc("2026-04-02T09:30:00+00:00"),
        confidence_tier="high",
    )

    fact_repo.upsert_entry(fact)
    stored = fact_repo.get_entry(fact.id)

    assert stored is not None
    assert stored.memory_type == "fact"
    assert stored.relation_kind == "updates"
    assert stored.supersedes_entry_id == "memory-fact-0"
    assert stored.is_latest is True
    assert stored.valid_from == _utc("2026-03-30T09:30:00+00:00")
    assert stored.expires_at == _utc("2026-04-02T09:30:00+00:00")
    assert stored.confidence_tier == "high"


def test_truth_first_memory_profile_and_episode_views_round_trip(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    profile_repo = SqliteMemoryProfileViewRepository(store)
    episode_repo = SqliteMemoryEpisodeViewRepository(store)
    profile = MemoryProfileViewRecord(
        profile_id="memory-profile:industry:industry-1",
        scope_type="industry",
        scope_id="industry-1",
        owner_agent_id="agent-1",
        industry_instance_id="industry-1",
        static_profile="CoPaw operates as a truth-first execution carrier.",
        dynamic_profile="Current focus is rebuilding memory around canonical truth.",
        active_preferences=["truth-first", "no-vector"],
        active_constraints=["single truth source", "rebuildable projections"],
        current_focus_summary="Land Task 3 state storage safely.",
        current_operating_context="Schema rollout under active refactor window.",
        source_refs=["strategy-1", "report-1"],
    )
    episode = MemoryEpisodeViewRecord(
        episode_id="memory-episode:industry:industry-1:cycle-1",
        scope_type="industry",
        scope_id="industry-1",
        owner_agent_id="agent-1",
        industry_instance_id="industry-1",
        headline="Truth-first memory schema rollout",
        summary="Migrated fact storage and materialized derived views.",
        source_refs=["report-1"],
        evidence_refs=["evidence-1", "evidence-2"],
        work_context_id="work-ctx-1",
        control_thread_id="thread-1",
        started_at=_utc("2026-03-30T10:00:00+00:00"),
        ended_at=_utc("2026-03-30T11:00:00+00:00"),
    )

    profile_repo.upsert_view(profile)
    episode_repo.upsert_view(episode)

    stored_profile = profile_repo.get_view(profile.profile_id)
    stored_episode = episode_repo.get_view(episode.episode_id)

    assert stored_profile is not None
    assert stored_profile.dynamic_profile.startswith("Current focus")
    assert stored_profile.active_constraints == [
        "single truth source",
        "rebuildable projections",
    ]
    assert stored_episode is not None
    assert stored_episode.work_context_id == "work-ctx-1"
    assert stored_episode.evidence_refs == ["evidence-1", "evidence-2"]


def test_truth_first_memory_repository_demotes_superseded_latest_entry(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    fact_repo = SqliteMemoryFactIndexRepository(store)
    older = _make_fact(
        "memory-fact-older",
        source_ref="report-older",
        relation_kind="references",
    )
    newer = _make_fact(
        "memory-fact-newer",
        source_ref="report-newer",
        relation_kind="supersedes",
        supersedes_entry_id=older.id,
        valid_from=_utc("2026-03-30T12:00:00+00:00"),
    )

    fact_repo.upsert_entry(older)
    fact_repo.upsert_entry(newer)

    stored_older = fact_repo.get_entry(older.id)
    stored_newer = fact_repo.get_entry(newer.id)

    assert stored_older is not None
    assert stored_newer is not None
    assert stored_older.is_latest is False
    assert stored_newer.is_latest is True


def test_truth_first_memory_store_upgrades_legacy_rows_with_safe_defaults(tmp_path) -> None:
    db_path = tmp_path / "legacy-state.db"
    _create_legacy_memory_db(db_path)
    store = SQLiteStateStore(db_path)

    store.initialize()
    fact_repo = SqliteMemoryFactIndexRepository(store)
    legacy = fact_repo.get_entry("legacy-fact-1")

    assert legacy is not None
    assert legacy.memory_type == "fact"
    assert legacy.relation_kind == "references"
    assert legacy.supersedes_entry_id is None
    assert legacy.is_latest is True
    assert legacy.valid_from == _utc("2026-03-29T09:15:00+00:00")
    assert legacy.expires_at is None
    assert legacy.confidence_tier == "standard"


def test_truth_first_memory_views_materialize_on_upgraded_legacy_db(tmp_path) -> None:
    db_path = tmp_path / "legacy-materialize.db"
    _create_legacy_memory_db(db_path)
    store = SQLiteStateStore(db_path)
    store.initialize()
    profile_repo = SqliteMemoryProfileViewRepository(store)
    episode_repo = SqliteMemoryEpisodeViewRepository(store)

    profile = MemoryProfileViewRecord(
        profile_id="memory-profile:industry:industry-legacy",
        scope_type="industry",
        scope_id="industry-legacy",
        owner_agent_id="agent-legacy",
        industry_instance_id="industry-legacy",
        static_profile="Legacy durable profile",
        dynamic_profile="Rebuilt from upgraded legacy facts.",
        active_preferences=["preserve-bootability"],
        current_focus_summary="Rebuild views after additive migration.",
        source_refs=["legacy-fact-1"],
    )
    episode = MemoryEpisodeViewRecord(
        episode_id="memory-episode:industry:industry-legacy:1",
        scope_type="industry",
        scope_id="industry-legacy",
        owner_agent_id="agent-legacy",
        industry_instance_id="industry-legacy",
        headline="Legacy rebuild",
        summary="Materialized truth-first projections after schema upgrade.",
        source_refs=["legacy-fact-1"],
        started_at=_utc("2026-03-30T13:00:00+00:00"),
        ended_at=_utc("2026-03-30T13:05:00+00:00"),
    )

    profile_repo.upsert_view(profile)
    episode_repo.upsert_view(episode)

    assert profile_repo.get_view(profile.profile_id) is not None
    assert episode_repo.get_view(episode.episode_id) is not None


def test_truth_first_memory_store_initialize_is_idempotent(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")

    store.initialize()
    store.initialize()
    store.initialize()

    with store.connection() as conn:
        table_names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'",
            ).fetchall()
        }
        fact_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(memory_fact_index)",
            ).fetchall()
        }

    assert "memory_profile_views" in table_names
    assert "memory_episode_views" in table_names
    assert {
        "memory_type",
        "relation_kind",
        "supersedes_entry_id",
        "is_latest",
        "valid_from",
        "expires_at",
        "confidence_tier",
    }.issubset(fact_columns)
