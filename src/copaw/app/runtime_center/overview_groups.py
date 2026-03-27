# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .models import RuntimeOverviewCard
from .overview_cards import _RuntimeCenterOverviewCardsSupport


class RuntimeCenterOperationsCardsBuilder(_RuntimeCenterOverviewCardsSupport):
    """Build operator-facing runtime cards."""

    async def build_cards(self, app_state: Any) -> list[RuntimeOverviewCard]:
        return [
            await self._build_tasks_card(app_state),
            await self._build_work_contexts_card(app_state),
            await self._build_routines_card(app_state),
            await self._build_industry_card(app_state),
            await self._build_agents_card(app_state),
        ]


class RuntimeCenterControlCardsBuilder(_RuntimeCenterOverviewCardsSupport):
    """Build control-plane and governance cards."""

    async def build_cards(self, app_state: Any) -> list[RuntimeOverviewCard]:
        return [
            await self._build_predictions_card(app_state),
            await self._build_capabilities_card(app_state),
            await self._build_evidence_card(app_state),
            await self._build_governance_card(app_state),
            await self._build_decisions_card(app_state),
        ]


class RuntimeCenterLearningCardsBuilder(_RuntimeCenterOverviewCardsSupport):
    """Build learning and patch state cards."""

    async def build_cards(self, app_state: Any) -> list[RuntimeOverviewCard]:
        return [
            await self._build_patches_card(app_state),
            await self._build_growth_card(app_state),
        ]


__all__ = [
    "RuntimeCenterControlCardsBuilder",
    "RuntimeCenterLearningCardsBuilder",
    "RuntimeCenterOperationsCardsBuilder",
]
