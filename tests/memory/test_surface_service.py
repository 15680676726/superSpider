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
