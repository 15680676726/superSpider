# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ...kernel.buddy_onboarding_service import BuddyOnboardingService
from ...kernel.buddy_projection_service import BuddyProjectionService

router = APIRouter(prefix="/buddy", tags=["buddy"])
logger = logging.getLogger(__name__)


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
    capability_action: str = Field(..., min_length=1)
    target_domain_id: str | None = None


class BuddyDirectionTransitionPreviewRequest(BaseModel):
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


def _get_buddy_projection_service(request: Request) -> BuddyProjectionService:
    service = getattr(request.app.state, "buddy_projection_service", None)
    if isinstance(service, BuddyProjectionService):
        return service
    raise HTTPException(503, detail="Buddy projection service is not available")


def _spawn_buddy_activation_job(*, kickoff, instance_id: str) -> None:
    async def _run() -> None:
        await kickoff(
            industry_instance_id=instance_id,
            message_text="Buddy onboarding confirmed. Start the first concrete task now.",
            trigger_source="buddy-onboarding",
            trigger_reason_override="Buddy onboarding confirmed. Start the first concrete task now.",
        )

    def _runner() -> None:
        try:
            import asyncio

            asyncio.run(_run())
        except Exception:
            logger.warning("Buddy onboarding activation task failed.", exc_info=True)

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"buddy-onboarding-activation-{instance_id}",
    ).start()


def _maybe_activate_buddy_execution(
    request: Request,
    *,
    execution_carrier: dict[str, object] | None,
    domain_capability: object,
) -> dict[str, object] | None:
    industry_service = getattr(request.app.state, "industry_service", None)
    kickoff = getattr(industry_service, "kickoff_execution_from_chat", None)
    if not callable(kickoff):
        return None
    carrier = dict(execution_carrier or {})
    instance_id = str(
        carrier.get("instance_id")
        or getattr(domain_capability, "industry_instance_id", "")
        or "",
    ).strip()
    if not instance_id:
        return None
    _spawn_buddy_activation_job(kickoff=kickoff, instance_id=instance_id)
    return {
        "status": "queued",
        "industry_instance_id": instance_id,
        "trigger_source": "buddy-onboarding",
    }


@router.post("/onboarding/identity")
async def submit_buddy_identity(
    request: Request,
    payload: BuddyIdentityRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        result = service.submit_identity(**payload.model_dump())
    except TimeoutError as exc:
        raise HTTPException(504, detail=str(exc) or "Buddy onboarding model timed out.") from exc
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
    except TimeoutError as exc:
        raise HTTPException(504, detail=str(exc) or "Buddy onboarding model timed out.") from exc
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
    except TimeoutError as exc:
        raise HTTPException(504, detail=str(exc) or "Buddy onboarding model timed out.") from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    activation = _maybe_activate_buddy_execution(
        request,
        execution_carrier=result.execution_carrier,
        domain_capability=result.domain_capability,
    )
    return {
        "session": result.session.model_dump(mode="json"),
        "growth_target": result.growth_target.model_dump(mode="json"),
        "relationship": result.relationship.model_dump(mode="json"),
        "domain_capability": result.domain_capability.model_dump(mode="json"),
        "execution_carrier": result.execution_carrier,
        "activation": activation,
    }


@router.post("/onboarding/direction-transition-preview")
async def preview_buddy_direction_transition(
    request: Request,
    payload: BuddyDirectionTransitionPreviewRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        result = service.preview_primary_direction_transition(
            session_id=payload.session_id,
            selected_direction=payload.selected_direction,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


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


@router.get("/surface", response_model=None)
async def get_buddy_surface(
    request: Request,
    profile_id: str | None = None,
):
    service = _get_buddy_projection_service(request)
    try:
        surface = service.build_optional_chat_surface(profile_id=profile_id)
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    if surface is None:
        return Response(status_code=204)
    return surface.model_dump(mode="json")


__all__ = ["router"]
