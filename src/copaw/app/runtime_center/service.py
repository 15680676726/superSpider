# -*- coding: utf-8 -*-
"""Runtime Center overview query facade."""
from __future__ import annotations

from typing import Any

from .models import RuntimeOverviewResponse
from .overview_cards import RuntimeCenterOverviewBuilder
from .overview_helpers import build_runtime_surface


class RuntimeCenterQueryService:
    """Thin facade for Runtime Center overview queries."""

    def __init__(
        self,
        *,
        item_limit: int = 5,
        overview_builder: RuntimeCenterOverviewBuilder | None = None,
    ) -> None:
        self._overview_builder = overview_builder or RuntimeCenterOverviewBuilder(
            item_limit=item_limit,
        )

    async def get_overview(self, app_state: Any) -> RuntimeOverviewResponse:
        cards = await self._overview_builder.build_cards(app_state)
        return RuntimeOverviewResponse(
            surface=build_runtime_surface(cards),
            cards=cards,
        )


__all__ = ["RuntimeCenterQueryService"]
