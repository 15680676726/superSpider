from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.app.runtime_center.models import RuntimeOverviewEntry
from copaw.app.runtime_center.overview_cards import _RuntimeCenterOverviewCardsSupport


class _StaticListService:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self._items = items

    async def list_strategies(self) -> list[dict[str, object]]:
        return list(self._items)

    async def list_instances(self) -> list[dict[str, object]]:
        return list(self._items)


def test_main_brain_card_unavailable_surface_uses_localized_copy() -> None:
    support = _RuntimeCenterOverviewCardsSupport()
    app_state = SimpleNamespace(
        strategy_memory_service=_StaticListService([]),
        industry_service=_StaticListService([]),
        actor_supervisor_snapshot=lambda: {},
    )

    card = asyncio.run(support._build_main_brain_card(app_state))

    assert card.key == "main-brain"
    assert card.count == 0
    assert card.summary


def test_main_brain_card_localizes_runtime_summary_and_signal_details() -> None:
    support = _RuntimeCenterOverviewCardsSupport()
    app_state = SimpleNamespace(
        strategy_memory_service=_StaticListService(
            [
                {
                    "strategy_id": "strategy-1",
                    "title": "growth-track",
                    "summary": "Drive this week's growth loop.",
                    "status": "active",
                    "industry_instance_id": "industry-1",
                    "updated_at": "2026-04-17T10:00:00+00:00",
                }
            ]
        ),
        industry_service=_StaticListService(
            [
                {
                    "instance_id": "industry-1",
                    "label": "retail",
                    "status": "active",
                    "updated_at": "2026-04-17T10:00:00+00:00",
                    "stats": {
                        "lane_count": 2,
                        "backlog_count": 3,
                        "cycle_count": 1,
                        "assignment_count": 4,
                        "report_count": 5,
                        "evidence_count": 6,
                        "decision_count": 1,
                        "patch_count": 2,
                        "unconsumed_report_count": 1,
                        "current_cycle_title": "Week 16",
                    },
                }
            ]
        ),
        actor_supervisor_snapshot=lambda: {
            "absorption_case_count": 2,
            "human_required_case_count": 1,
            "absorption_summary": "This legacy actor-supervisor signal should stay hidden.",
        },
    )

    card = asyncio.run(support._build_main_brain_card(app_state))

    assert card.summary
    assert "exception_absorption" not in card.meta
    assert "exception_absorption" not in card.meta["signals"]
    assert card.meta["signals"]["lanes"]["detail"]
    assert card.meta["signals"]["backlog"]["detail"]
    assert card.meta["signals"]["current_cycle"]["detail"]
    assert card.meta["signals"]["agent_reports"]["detail"]
    assert card.meta["signals"]["environment"]["summary"]
    assert card.meta["signals"]["evidence"]["detail"]
    assert card.meta["signals"]["decisions"]["detail"]
    assert card.meta["signals"]["patches"]["detail"]


def test_main_brain_card_meta_localizes_carrier_fallback_and_cognition_defaults() -> None:
    support = _RuntimeCenterOverviewCardsSupport()
    first_entry = RuntimeOverviewEntry(
        id="strategy-1",
        title="growth-track",
        kind="main-brain",
        status="active",
        owner=None,
        summary="Drive this week's growth loop.",
        route="/api/runtime-center/strategy-memory",
        meta={},
    )

    meta = support._main_brain_assembly.main_brain_card_meta(first_entry, total=1)
    conflict = support._main_brain_assembly.normalize_main_brain_cognition_conflict(
        {},
        industry_instance_id="industry-1",
    )
    hole = support._main_brain_assembly.normalize_main_brain_cognition_hole(
        {},
        industry_instance_id="industry-1",
    )

    assert meta["signals"]["carrier"]["value"]
    assert conflict["title"]
    assert conflict["summary"]
    assert hole["title"]
    assert hole["summary"]
