# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...goals import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])
public_router = router


def _get_goal_service(request: Request) -> GoalService:
    service = getattr(request.app.state, "goal_service", None)
    if isinstance(service, GoalService):
        return service
    raise HTTPException(503, detail="Goal service is not available")


@router.get("/{goal_id}/detail", response_model=dict[str, object])
async def get_goal_detail(request: Request, goal_id: str) -> dict[str, object]:
    service = _get_goal_service(request)
    detail = service.get_goal_detail(goal_id)
    if detail is None:
        raise HTTPException(404, detail=f"Goal '{goal_id}' not found")
    return detail
