# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...compiler import CompiledTaskSpec
from ...goals import GoalService
from ...state import GoalRecord

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalCreateRequest(BaseModel):
    title: str
    summary: str = ""
    status: str = "draft"
    priority: int = 0
    owner_scope: str | None = None


class GoalUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    priority: int | None = None
    owner_scope: str | None = None


class GoalCompileRequest(BaseModel):
    context: dict[str, object] = Field(default_factory=dict)


def _get_goal_service(request: Request) -> GoalService:
    service = getattr(request.app.state, "goal_service", None)
    if isinstance(service, GoalService):
        return service
    raise HTTPException(503, detail="Goal service is not available")


@router.get("", response_model=list[GoalRecord])
async def list_goals(
    request: Request,
    status: str | None = Query(default=None),
    owner_scope: str | None = Query(default=None),
    industry_instance_id: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=0),
) -> list[GoalRecord]:
    service = _get_goal_service(request)
    return service.list_goals(
        status=status,
        owner_scope=owner_scope,
        industry_instance_id=industry_instance_id,
        limit=limit,
    )


@router.post("", response_model=GoalRecord)
async def create_goal(
    request: Request,
    payload: GoalCreateRequest,
) -> GoalRecord:
    service = _get_goal_service(request)
    return service.create_goal(
        title=payload.title,
        summary=payload.summary,
        status=payload.status,
        priority=payload.priority,
        owner_scope=payload.owner_scope,
    )


@router.get("/{goal_id}", response_model=GoalRecord)
async def get_goal(request: Request, goal_id: str) -> GoalRecord:
    service = _get_goal_service(request)
    goal = service.get_goal(goal_id)
    if goal is None:
        raise HTTPException(404, detail=f"Goal '{goal_id}' not found")
    return goal


@router.get("/{goal_id}/detail", response_model=dict[str, object])
async def get_goal_detail(request: Request, goal_id: str) -> dict[str, object]:
    service = _get_goal_service(request)
    detail = service.get_goal_detail(goal_id)
    if detail is None:
        raise HTTPException(404, detail=f"Goal '{goal_id}' not found")
    return detail


@router.patch("/{goal_id}", response_model=GoalRecord)
async def update_goal(
    request: Request,
    goal_id: str,
    payload: GoalUpdateRequest,
) -> GoalRecord:
    service = _get_goal_service(request)
    try:
        return service.update_goal(
            goal_id,
            title=payload.title,
            summary=payload.summary,
            status=payload.status,
            priority=payload.priority,
            owner_scope=payload.owner_scope,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


@router.delete("/{goal_id}", response_model=dict[str, object])
async def delete_goal(request: Request, goal_id: str) -> dict[str, object]:
    service = _get_goal_service(request)
    deleted = service.delete_goal(goal_id)
    if not deleted:
        raise HTTPException(404, detail=f"Goal '{goal_id}' not found")
    return {"deleted": True, "id": goal_id}


@router.post("/{goal_id}/compile", response_model=list[CompiledTaskSpec])
async def compile_goal(
    request: Request,
    goal_id: str,
    payload: GoalCompileRequest,
) -> list[CompiledTaskSpec]:
    service = _get_goal_service(request)
    try:
        return service.compile_goal(goal_id, context=payload.context)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc

