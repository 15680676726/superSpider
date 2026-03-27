# -*- coding: utf-8 -*-
"""Tests for the enhanced EvidenceLedger query methods."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from copaw.evidence import ArtifactRecord, EvidenceLedger, EvidenceRecord, ReplayPointer
from copaw.environments.observations import ActionReplayStore, ArtifactStore


def _make_record(
    *,
    task_id: str = "task-1",
    capability_ref: str | None = None,
    action_summary: str = "test action",
) -> EvidenceRecord:
    return EvidenceRecord(
        task_id=task_id,
        actor_ref="test-actor",
        risk_level="auto",
        action_summary=action_summary,
        result_summary="ok",
        capability_ref=capability_ref,
    )


def test_get_record_returns_existing() -> None:
    with EvidenceLedger() as ledger:
        record = ledger.append(_make_record(capability_ref="tool:shell"))
        found = ledger.get_record(record.id)
        assert found is not None
        assert found.id == record.id
        assert found.capability_ref == "tool:shell"


def test_get_record_returns_none_for_missing() -> None:
    with EvidenceLedger() as ledger:
        assert ledger.get_record("nonexistent") is None


def test_list_by_capability_ref() -> None:
    with EvidenceLedger() as ledger:
        ledger.append(_make_record(capability_ref="tool:shell", action_summary="cmd-1"))
        ledger.append(_make_record(capability_ref="tool:file_io", action_summary="file-1"))
        ledger.append(_make_record(capability_ref="tool:shell", action_summary="cmd-2"))

        shell_records = ledger.list_by_capability_ref("tool:shell")
        assert len(shell_records) == 2
        assert all(r.capability_ref == "tool:shell" for r in shell_records)

        file_records = ledger.list_by_capability_ref("tool:file_io")
        assert len(file_records) == 1


def test_list_by_capability_ref_respects_limit() -> None:
    with EvidenceLedger() as ledger:
        for i in range(5):
            ledger.append(_make_record(capability_ref="tool:shell", action_summary=f"cmd-{i}"))

        records = ledger.list_by_capability_ref("tool:shell", limit=3)
        assert len(records) == 3


def test_count_by_capability_ref() -> None:
    with EvidenceLedger() as ledger:
        ledger.append(_make_record(capability_ref="tool:shell"))
        ledger.append(_make_record(capability_ref="tool:shell"))
        ledger.append(_make_record(capability_ref="tool:file_io"))
        ledger.append(_make_record(capability_ref=None))

        dist = ledger.count_by_capability_ref()
        assert dist["tool:shell"] == 2
        assert dist["tool:file_io"] == 1
        assert dist.get("unknown", 0) == 1


def test_list_replay_pointers_by_environment_ref_orders_by_replay_time_and_limits() -> None:
    with EvidenceLedger() as ledger:
        base_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
        record = ledger.append(
            EvidenceRecord(
                task_id="task-1",
                actor_ref="test-actor",
                environment_ref="env:windows-seat",
                capability_ref="tool:execute_shell_command",
                risk_level="guarded",
                action_summary="capture replayable step",
                result_summary="step captured",
                created_at=base_time,
            ),
            replay_pointers=[
                ReplayPointer(
                    replay_type="shell",
                    storage_uri="replay://older",
                    summary="older replay",
                    created_at=base_time,
                ),
                ReplayPointer(
                    replay_type="shell",
                    storage_uri="replay://newer",
                    summary="newer replay",
                    created_at=base_time + timedelta(seconds=5),
                ),
            ],
        )

        replays = ledger.list_replay_pointers_by_environment_ref(
            "env:windows-seat",
            limit=1,
        )

    assert len(replays) == 1
    assert replays[0].storage_uri == "replay://newer"
    assert replays[0].evidence_id == record.id


def test_list_artifact_records_by_environment_ref_orders_by_artifact_time_and_limits() -> None:
    with EvidenceLedger() as ledger:
        base_time = datetime(2026, 3, 27, 12, 30, tzinfo=timezone.utc)
        record = ledger.append(
            EvidenceRecord(
                task_id="task-2",
                actor_ref="test-actor",
                environment_ref="env:windows-seat",
                capability_ref="tool:write_file",
                risk_level="auto",
                action_summary="capture verification artifacts",
                result_summary="artifacts captured",
                created_at=base_time,
            ),
            artifacts=[
                ArtifactRecord(
                    artifact_type="screenshot",
                    storage_uri="file://older.png",
                    summary="older screenshot",
                    created_at=base_time,
                ),
                ArtifactRecord(
                    artifact_type="screenshot",
                    storage_uri="file://newer.png",
                    summary="newer screenshot",
                    created_at=base_time + timedelta(seconds=3),
                ),
            ],
        )

        artifacts = ledger.list_artifact_records_by_environment_ref(
            "env:windows-seat",
            limit=1,
        )

    assert len(artifacts) == 1
    assert artifacts[0].storage_uri == "file://newer.png"
    assert artifacts[0].evidence_id == record.id


def test_action_replay_store_uses_replay_entry_limit_not_evidence_row_limit() -> None:
    with EvidenceLedger() as ledger:
        base_time = datetime(2026, 3, 27, 13, 0, tzinfo=timezone.utc)
        ledger.append(
            EvidenceRecord(
                task_id="task-3",
                actor_ref="test-actor",
                environment_ref="env:windows-seat",
                capability_ref="tool:execute_shell_command",
                risk_level="guarded",
                action_summary="capture multi replay evidence",
                result_summary="captured",
                created_at=base_time,
            ),
            replay_pointers=[
                ReplayPointer(
                    replay_type="shell",
                    storage_uri="replay://older-store",
                    summary="older replay",
                    created_at=base_time,
                ),
                ReplayPointer(
                    replay_type="shell",
                    storage_uri="replay://newer-store",
                    summary="newer replay",
                    created_at=base_time + timedelta(seconds=2),
                ),
            ],
        )

        store = ActionReplayStore(ledger=ledger)
        replays = store.list_replays(environment_ref="env:windows-seat", limit=1)

    assert [entry.storage_uri for entry in replays] == ["replay://newer-store"]


def test_artifact_store_uses_artifact_entry_limit_not_evidence_row_limit() -> None:
    with EvidenceLedger() as ledger:
        base_time = datetime(2026, 3, 27, 13, 30, tzinfo=timezone.utc)
        ledger.append(
            EvidenceRecord(
                task_id="task-4",
                actor_ref="test-actor",
                environment_ref="env:windows-seat",
                capability_ref="tool:write_file",
                risk_level="auto",
                action_summary="capture multi artifact evidence",
                result_summary="captured",
                created_at=base_time,
            ),
            artifacts=[
                ArtifactRecord(
                    artifact_type="screenshot",
                    storage_uri="file://older-store.png",
                    summary="older artifact",
                    created_at=base_time,
                ),
                ArtifactRecord(
                    artifact_type="screenshot",
                    storage_uri="file://newer-store.png",
                    summary="newer artifact",
                    created_at=base_time + timedelta(seconds=2),
                ),
            ],
        )

        store = ArtifactStore(ledger=ledger)
        artifacts = store.list_artifacts(environment_ref="env:windows-seat", limit=1)

    assert [entry.storage_uri for entry in artifacts] == ["file://newer-store.png"]
