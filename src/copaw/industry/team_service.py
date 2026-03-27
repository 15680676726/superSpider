# -*- coding: utf-8 -*-
from __future__ import annotations

from .models import IndustryBootstrapResponse


class IndustryTeamService:
    """Team/staffing facade over the existing industry lifecycle logic."""

    def __init__(self, facade: object) -> None:
        self._facade = facade

    async def update_instance_team(
        self,
        instance_id: str,
        request,
        *,
        public_contract: bool = True,
    ) -> IndustryBootstrapResponse:
        current_detail = self._facade.get_instance_detail(instance_id)
        plan = await self._facade._prepare_team_update(
            instance_id=instance_id,
            request=request,
        )
        flags = (
            self._facade._default_team_update_flags(current_detail)
            if public_contract
            and current_detail is not None
            else {
                "auto_activate": bool(request.auto_activate),
                "auto_dispatch": bool(request.auto_dispatch),
                "execute": bool(request.execute),
            }
        )
        return await self._facade._activate_plan(
            plan=plan,
            goal_priority=request.goal_priority,
            auto_activate=flags["auto_activate"],
            auto_dispatch=flags["auto_dispatch"],
            execute=flags["execute"],
            install_plan=list(request.install_plan or []),
        )
