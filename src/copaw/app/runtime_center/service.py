# -*- coding: utf-8 -*-
"""Runtime Center overview query facade."""
from __future__ import annotations

from typing import Any

from .models import (
    RuntimeCenterAppStateView,
    RuntimeCenterSurfaceResponse,
    RuntimeMainBrainResponse,
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

    async def get_main_brain_view(
        self,
        runtime_state: RuntimeCenterAppStateView,
        *,
        buddy_profile_id: str | None = None,
    ) -> RuntimeMainBrainResponse:
        try:
            return await self._overview_builder.build_main_brain_payload(
                runtime_state,
                buddy_profile_id=buddy_profile_id,
            )
        except TypeError:
            return await self._overview_builder.build_main_brain_payload(runtime_state)

    async def get_surface_view(
        self,
        runtime_state: RuntimeCenterAppStateView,
        *,
        include_cards: bool = True,
        include_main_brain: bool = True,
        buddy_profile_id: str | None = None,
    ) -> RuntimeCenterSurfaceResponse:
        build_surface_payload = getattr(self._overview_builder, "build_surface_payload", None)
        if callable(build_surface_payload):
            try:
                return await build_surface_payload(
                    runtime_state,
                    include_cards=include_cards,
                    include_main_brain=include_main_brain,
                    buddy_profile_id=buddy_profile_id,
                )
            except TypeError:
                return await build_surface_payload(runtime_state)
        cards = []
        surface = build_runtime_surface(cards)
        main_brain = None
        if include_cards:
            cards = await self._overview_builder.build_cards(runtime_state)
            surface = build_runtime_surface(cards)
        if include_main_brain:
            main_brain = await self.get_main_brain_view(
                runtime_state,
                buddy_profile_id=buddy_profile_id,
            )
            if not include_cards:
                surface = main_brain.surface
        return RuntimeCenterSurfaceResponse(
            surface=surface,
            cards=cards,
            main_brain=main_brain,
        )

    async def get_surface(
        self,
        app_state: Any | RuntimeCenterAppStateView,
        *,
        include_cards: bool = True,
        include_main_brain: bool = True,
        buddy_profile_id: str | None = None,
    ) -> RuntimeCenterSurfaceResponse:
        return await self.get_surface_view(
            self._coerce_runtime_state(app_state),
            include_cards=include_cards,
            include_main_brain=include_main_brain,
            buddy_profile_id=buddy_profile_id,
        )


__all__ = ["RuntimeCenterQueryService"]
