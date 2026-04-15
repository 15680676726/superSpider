from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from copaw.memory.surface_service import MemorySurfaceService


def test_memory_surface_service_resolves_truth_first_scope_snapshot() -> None:
    calls: list[dict[str, object]] = []

    class _DerivedIndexService:
        def list_fact_entries(self, **kwargs):
            calls.append(dict(kwargs))
            return [
                SimpleNamespace(
                    title="Current operator preference",
                    summary="Use the current governed checklist first.",
                    content_excerpt="Use the current governed checklist first.",
                    content_text="Use the current governed checklist first.",
                    source_updated_at=None,
                    updated_at="2026-04-09T08:00:00Z",
                    created_at="2026-04-09T07:30:00Z",
                ),
                SimpleNamespace(
                    title="Older follow-up history",
                    summary="Earlier history still matters.",
                    content_excerpt="Earlier history still matters.",
                    content_text="Earlier history still matters.",
                    source_updated_at=None,
                    updated_at="2026-04-08T08:00:00Z",
                    created_at="2026-04-08T07:30:00Z",
                ),
                SimpleNamespace(
                    title="Archived execution note",
                    summary="Archived note should land in history entries.",
                    content_excerpt="Archived note should land in history entries.",
                    content_text="Archived note should land in history entries.",
                    source_updated_at=None,
                    updated_at="2026-04-07T08:00:00Z",
                    created_at="2026-04-07T07:30:00Z",
                ),
            ]

    recall_service = SimpleNamespace(_derived_index_service=_DerivedIndexService())
    service = MemorySurfaceService(memory_recall_service=recall_service)

    snapshot = service.resolve_truth_first_scope_snapshot(
        scope_type="work_context",
        scope_id="ctx-1",
        owner_agent_id="ops-agent",
        industry_instance_id="industry-1",
    )

    assert snapshot["entries"]
    assert snapshot["latest_entries"][0].title == "Current operator preference"
    assert snapshot["latest_entries"][1].title == "Older follow-up history"
    assert snapshot["history_entries"][0].title == "Archived execution note"
    assert calls == [
        {
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "owner_agent_id": "ops-agent",
            "industry_instance_id": "industry-1",
            "limit": 8,
        }
    ]


def test_memory_surface_service_resolves_private_visibility_payload() -> None:
    class _CompactionService:
        @staticmethod
        def build_visibility_payload(source: dict[str, object] | None = None) -> dict[str, object]:
            return dict(source or {})

        def runtime_visibility_payload(self) -> dict[str, object]:
            return {
                "compaction_state": {
                    "mode": "microcompact",
                    "summary": "Compacted 2 oversized tool results.",
                    "spill_count": 1,
                },
                "tool_result_budget": {
                    "message_budget": 2400,
                    "remaining_budget": 600,
                },
            }

    service = MemorySurfaceService(conversation_compaction_service=_CompactionService())

    payload = service.resolve_runtime_compaction_visibility_payload()

    assert payload == {
        "compaction_state": {
            "mode": "microcompact",
            "summary": "Compacted 2 oversized tool results.",
            "spill_count": 1,
        },
        "tool_result_budget": {
            "message_budget": 2400,
            "remaining_budget": 600,
        },
    }


def test_memory_surface_service_caps_truth_first_snapshot_budget() -> None:
    calls: list[dict[str, object]] = []

    class _DerivedIndexService:
        def list_fact_entries(self, **kwargs):
            calls.append(dict(kwargs))
            limit = int(kwargs.get("limit") or 0)
            return [
                SimpleNamespace(
                    title=f"Entry {index}",
                    summary=f"Summary {index}",
                    content_excerpt=f"Summary {index}",
                    content_text=f"Summary {index}",
                    source_updated_at=None,
                    updated_at=f"2026-04-{20 - index:02d}T08:00:00Z",
                    created_at=f"2026-04-{20 - index:02d}T07:30:00Z",
                )
                for index in range(limit)
            ]

    recall_service = SimpleNamespace(_derived_index_service=_DerivedIndexService())
    service = MemorySurfaceService(memory_recall_service=recall_service)

    snapshot = service.resolve_truth_first_scope_snapshot(
        scope_type="work_context",
        scope_id="ctx-1",
        owner_agent_id="ops-agent",
        industry_instance_id="industry-1",
        limit=20,
    )

    assert calls[0]["limit"] == 8
    assert len(snapshot["entries"]) == 8
    assert len(snapshot["latest_entries"]) == 2
    assert len(snapshot["history_entries"]) == 2


def test_memory_surface_service_exposes_sleep_overlay() -> None:
    class _SleepService:
        def resolve_scope_overlay(self, *, scope_type: str, scope_id: str) -> dict[str, object]:
            assert scope_type == "work_context"
            assert scope_id == "ctx-sleep"
            return {
                "digest": {"headline": "Finance review digest", "summary": "Review-first memory overlay."},
                "soft_rules": [{"rule_text": "Wait for finance review before outbound approval."}],
                "conflicts": [],
            }

    service = MemorySurfaceService(memory_recall_service=object(), memory_sleep_service=_SleepService())

    snapshot = service.resolve_truth_first_scope_snapshot(
        scope_type="work_context",
        scope_id="ctx-sleep",
    )

    assert snapshot["sleep"]["digest"]["headline"] == "Finance review digest"
    assert snapshot["sleep"]["soft_rules"][0]["rule_text"] == "Wait for finance review before outbound approval."
