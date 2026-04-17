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


def test_main_brain_card_unavailable_surface_uses_chinese_copy() -> None:
    support = _RuntimeCenterOverviewCardsSupport()
    app_state = SimpleNamespace(
        strategy_memory_service=_StaticListService([]),
        industry_service=_StaticListService([]),
        actor_supervisor_snapshot=lambda: {},
    )

    card = asyncio.run(support._build_main_brain_card(app_state))

    assert card.title == "主脑"
    assert card.summary == "主脑驾驶舱暂未接入。"


def test_main_brain_card_localizes_runtime_summary_and_signal_details() -> None:
    support = _RuntimeCenterOverviewCardsSupport()
    app_state = SimpleNamespace(
        strategy_memory_service=_StaticListService(
            [
                {
                    "strategy_id": "strategy-1",
                    "title": "增长主线",
                    "summary": "推进本周增长闭环。",
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
                    "label": "零售行业",
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
                        "current_cycle_title": "第 16 周",
                    },
                }
            ]
        ),
        actor_supervisor_snapshot=lambda: {
            "absorption_case_count": 2,
            "human_required_case_count": 1,
            "absorption_summary": "主脑正在吸收内部执行压力，且至少有一个案例现在需要受治理的人类动作。",
        },
    )

    card = asyncio.run(support._build_main_brain_card(app_state))

    assert (
        card.summary
        == "主脑正在吸收内部执行压力，且至少有一个案例现在需要受治理的人类动作。"
        " 主脑驾驶舱当前跟踪 2 条车道、3 条待办、4 条派工、5 条汇报、6 条证据、1 条决策与 2 条补丁。"
    )
    assert card.meta["signals"]["lanes"]["detail"] == "当前运行驾驶舱里可见 2 条车道。"
    assert card.meta["signals"]["backlog"]["detail"] == "当前有 3 条待办正在等待排入执行周期。"
    assert card.meta["signals"]["current_cycle"]["detail"] == "当前关联 1 个周期。当前周期：第 16 周。"
    assert card.meta["signals"]["agent_reports"]["detail"] == "当前可见 5 条汇报，其中 1 条尚未消化。"
    assert card.meta["signals"]["environment"]["summary"] == "打开治理宿主镜像与环境连续性读面。"
    assert card.meta["signals"]["evidence"]["detail"] == "当前有 6 条证据可用于回放运行链路。"
    assert card.meta["signals"]["decisions"]["detail"] == "当前有 1 条治理决策待处理或已记录。"
    assert card.meta["signals"]["patches"]["detail"] == "当前运行中心已跟踪 2 条学习补丁。"


def test_main_brain_card_meta_localizes_carrier_fallback_and_cognition_defaults() -> None:
    support = _RuntimeCenterOverviewCardsSupport()
    first_entry = RuntimeOverviewEntry(
        id="strategy-1",
        title="增长主线",
        kind="main-brain",
        status="active",
        owner=None,
        summary="推进本周增长闭环。",
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

    assert meta["signals"]["carrier"]["value"] == "主脑载体"
    assert conflict["title"] == "汇报冲突"
    assert conflict["summary"] == "多条汇报之间仍存在冲突。"
    assert hole["title"] == "汇报缺口"
    assert hole["summary"] == "当前仍有一条汇报缺口尚未补齐。"
