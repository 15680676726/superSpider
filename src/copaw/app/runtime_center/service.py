# -*- coding: utf-8 -*-
"""Runtime Center overview query facade."""
from __future__ import annotations

from typing import Any

from .models import (
    RuntimeCenterAppStateView,
    RuntimeCenterSurfaceResponse,
    RuntimeMainBrainResponse,
    RuntimeOverviewResponse,
)
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

    def _coerce_runtime_state(
        self,
        app_state: Any | RuntimeCenterAppStateView,
    ) -> RuntimeCenterAppStateView:
        if isinstance(app_state, RuntimeCenterAppStateView):
            return app_state
        return RuntimeCenterAppStateView.from_object(app_state)

    async def get_overview_view(
        self,
        runtime_state: RuntimeCenterAppStateView,
    ) -> RuntimeOverviewResponse:
        cards = await self._overview_builder.build_cards(runtime_state)
        return RuntimeOverviewResponse(
            surface=build_runtime_surface(cards),
            cards=cards,
        )

    async def get_overview(self, app_state: Any | RuntimeCenterAppStateView) -> RuntimeOverviewResponse:
        return await self.get_overview_view(self._coerce_runtime_state(app_state))

    async def get_main_brain_view(
        self,
        runtime_state: RuntimeCenterAppStateView,
    ) -> RuntimeMainBrainResponse:
        return await self._overview_builder.build_main_brain_payload(runtime_state)

    async def get_main_brain(self, app_state: Any | RuntimeCenterAppStateView) -> RuntimeMainBrainResponse:
        """Return the dedicated Runtime Center main-brain cockpit payload."""
        return await self.get_main_brain_view(self._coerce_runtime_state(app_state))

    async def get_surface_view(
        self,
        runtime_state: RuntimeCenterAppStateView,
    ) -> RuntimeCenterSurfaceResponse:
        build_surface_payload = getattr(self._overview_builder, "build_surface_payload", None)
        if callable(build_surface_payload):
            return await build_surface_payload(runtime_state)
        overview = await self.get_overview_view(runtime_state)
        main_brain = await self.get_main_brain_view(runtime_state)
        return RuntimeCenterSurfaceResponse(
            surface=overview.surface,
            cards=overview.cards,
            main_brain=main_brain,
        )

    async def get_surface(
        self,
        app_state: Any | RuntimeCenterAppStateView,
    ) -> RuntimeCenterSurfaceResponse:
        return await self.get_surface_view(self._coerce_runtime_state(app_state))


__all__ = ["RuntimeCenterQueryService"]
