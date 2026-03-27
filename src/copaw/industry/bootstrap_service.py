# -*- coding: utf-8 -*-
from __future__ import annotations

from .models import IndustryBootstrapResponse, IndustryPreviewResponse


class IndustryBootstrapService:
    """Bootstrap-oriented facade over the existing industry lifecycle logic."""

    def __init__(self, facade: object) -> None:
        self._facade = facade

    async def preview_v1(self, request):
        plan = await self._facade._prepare_preview(request)
        return IndustryPreviewResponse(
            profile=plan.profile,
            draft=plan.draft,
            recommendation_pack=plan.recommendation_pack,
            readiness_checks=plan.readiness_checks,
            can_activate=all(
                not check.required or check.status != "missing"
                for check in plan.readiness_checks
            ),
            media_analyses=plan.media_analyses,
            media_warnings=plan.media_warnings,
        )

    async def bootstrap_v1(self, request) -> IndustryBootstrapResponse:
        plan = await self._facade._prepare_bootstrap(request)
        flags, auto_start_learning = self._facade._public_bootstrap_activation_flags(
            request,
        )
        return await self._facade._activate_plan(
            plan=plan,
            goal_priority=request.goal_priority,
            auto_activate=flags["auto_activate"],
            auto_dispatch=flags["auto_dispatch"],
            execute=flags["execute"],
            install_plan=list(request.install_plan or []),
            auto_start_learning=auto_start_learning,
        )
