# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...kernel.buddy_onboarding_service import BuddyOnboardingService

router = APIRouter(prefix="/buddy", tags=["buddy"])


class BuddyIdentityRequest(BaseModel):
    display_name: str = Field(..., min_length=1)
    profession: str = Field(..., min_length=1)
    current_stage: str = Field(..., min_length=1)
    interests: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    goal_intention: str = Field(..., min_length=1)


class BuddyClarifyRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    existing_question_count: int | None = Field(default=None, ge=1)


class BuddyConfirmDirectionRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    selected_direction: str = Field(..., min_length=1)


class BuddyNameRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    buddy_name: str = Field(..., min_length=1)


def _get_buddy_onboarding_service(request: Request) -> BuddyOnboardingService:
    service = getattr(request.app.state, "buddy_onboarding_service", None)
    if isinstance(service, BuddyOnboardingService):
        return service
    raise HTTPException(503, detail="Buddy onboarding service is not available")


@router.post("/onboarding/identity")
async def submit_buddy_identity(
    request: Request,
    payload: BuddyIdentityRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        result = service.submit_identity(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.post("/onboarding/clarify")
async def answer_buddy_clarification(
    request: Request,
    payload: BuddyClarifyRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        result = service.answer_clarification_turn(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.get("/onboarding/{session_id}/candidates")
async def list_buddy_candidate_directions(
    request: Request,
    session_id: str,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        result = service.get_candidate_directions(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.post("/onboarding/confirm-direction")
async def confirm_buddy_direction(
    request: Request,
    payload: BuddyConfirmDirectionRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        result = service.confirm_primary_direction(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return {
        "session": result.session.model_dump(mode="json"),
        "growth_target": result.growth_target.model_dump(mode="json"),
        "relationship": result.relationship.model_dump(mode="json"),
    }


@router.post("/name")
async def name_buddy(
    request: Request,
    payload: BuddyNameRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        relationship = service.name_buddy(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return relationship.model_dump(mode="json")


__all__ = ["router"]
