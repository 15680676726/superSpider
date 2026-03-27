from __future__ import annotations

from datetime import datetime, timezone

from copaw.evidence import ArtifactRecord, EvidenceLedger, EvidenceRecord, ReplayPointer


def test_append_persists_linked_artifacts_and_replays(tmp_path) -> None:
    database_path = tmp_path / "evidence.sqlite3"

    with EvidenceLedger(database_path=database_path) as ledger:
        stored = ledger.append(
            EvidenceRecord(
                task_id="task-1",
                actor_ref="agent:worker-2",
                environment_ref="env:workspace",
                capability_ref="capability:evidence",
                risk_level="auto",
                action_summary="capture task output",
                result_summary="stored screenshot and replay pointer",
                input_digest="input-1",
                output_digest="output-1",
                metadata={"source": "test"},
            ),
            artifacts=[
                ArtifactRecord(
                    artifact_type="screenshot",
                    storage_uri="file://artifacts/screenshot-1.png",
                    summary="post-run screenshot",
                    metadata={"format": "png"},
                ),
            ],
            replay_pointers=[
                ReplayPointer(
                    replay_type="shell",
                    storage_uri="replay://session/1",
                    summary="shell session replay",
                    metadata={"terminal": "powershell"},
                ),
            ],
        )

    with EvidenceLedger(database_path=database_path) as ledger:
        records = ledger.list_by_task("task-1")

    assert len(records) == 1
    record = records[0]
    assert record.id == stored.id
    assert record.status == "recorded"
    assert record.metadata == {"source": "test"}
    assert record.created_at is not None
    assert record.created_at.tzinfo == timezone.utc

    assert len(record.artifacts) == 1
    assert record.artifacts[0].evidence_id == record.id
    assert record.artifacts[0].artifact_type == "screenshot"
    assert record.artifact_refs == ("file://artifacts/screenshot-1.png",)

    assert len(record.replay_pointers) == 1
    assert record.replay_pointers[0].evidence_id == record.id
    assert record.replay_pointers[0].replay_type == "shell"
    assert record.replay_refs == ("replay://session/1",)


def test_query_by_task_filters_and_orders_records(tmp_path) -> None:
    database_path = tmp_path / "evidence.sqlite3"

    with EvidenceLedger(database_path=database_path) as ledger:
        first = ledger.append(
            EvidenceRecord(
                task_id="task-keep",
                actor_ref="agent:worker-2",
                risk_level="auto",
                action_summary="first action",
                result_summary="first result",
                created_at=datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc),
            ),
        )
        ledger.append(
            EvidenceRecord(
                task_id="task-skip",
                actor_ref="agent:worker-2",
                risk_level="guarded",
                action_summary="other action",
                result_summary="other result",
                created_at=datetime(2026, 3, 9, 9, 1, tzinfo=timezone.utc),
            ),
        )
        second = ledger.append(
            EvidenceRecord(
                task_id="task-keep",
                actor_ref="agent:worker-2",
                risk_level="confirm",
                action_summary="second action",
                result_summary="second result",
                created_at=datetime(2026, 3, 9, 9, 2, tzinfo=timezone.utc),
            ),
        )

        records = ledger.query_by_task("task-keep")

    assert [record.id for record in records] == [first.id, second.id]
    assert [record.task_id for record in records] == ["task-keep", "task-keep"]
    assert [record.action_summary for record in records] == [
        "first action",
        "second action",
    ]


def test_delete_records_cascades_artifacts_and_replays(tmp_path) -> None:
    database_path = tmp_path / "evidence.sqlite3"

    with EvidenceLedger(database_path=database_path) as ledger:
        stored = ledger.append(
            EvidenceRecord(
                task_id="task-delete",
                actor_ref="agent:worker-3",
                risk_level="guarded",
                action_summary="capture delete target",
                result_summary="delete this evidence chain",
            ),
            artifacts=[
                ArtifactRecord(
                    artifact_type="log",
                    storage_uri="file://artifacts/delete.log",
                    summary="log artifact",
                ),
            ],
            replay_pointers=[
                ReplayPointer(
                    replay_type="shell",
                    storage_uri="replay://delete/session",
                    summary="delete replay",
                ),
            ],
        )

        deleted = ledger.delete_records(task_ids=["task-delete"])

        assert deleted == 1
        assert ledger.get_record(stored.id) is None
        assert ledger.get_artifact_record(stored.artifacts[0].id) is None
        assert ledger.get_replay_pointer(stored.replay_pointers[0].id) is None
