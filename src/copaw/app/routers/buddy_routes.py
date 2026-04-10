# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ...app.crons.models import CronJobSpec
from ...kernel.buddy_onboarding_service import BuddyOnboardingService
from ...kernel.buddy_onboarding_reasoner import BuddyOnboardingReasonerUnavailableError
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


class BuddyContractRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    service_intent: str = Field(..., min_length=1)
    collaboration_role: str = Field(default="orchestrator", min_length=1)
    autonomy_level: str = Field(default="proactive", min_length=1)
    confirm_boundaries: list[str] = Field(default_factory=list)
    report_style: str = Field(default="result-first", min_length=1)
    collaboration_notes: str = ""


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


class BuddyOnboardingOperationResponse(BaseModel):
    session_id: str
    profile_id: str
    operation_id: str
    operation_kind: str
    operation_status: str


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


def _maybe_activate_buddy_execution_for_app(
    app,
    *,
    execution_carrier: dict[str, object] | None,
    domain_capability: object,
) -> dict[str, object] | None:
    industry_service = getattr(app.state, "industry_service", None)
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


async def _maybe_register_buddy_schedules(
    request: Request,
    *,
    schedule_specs: list[dict[str, object]] | None,
) -> None:
    cron_manager = getattr(request.app.state, "cron_manager", None)
    create_or_replace = getattr(cron_manager, "create_or_replace_job", None)
    if not callable(create_or_replace):
        return
    for spec in list(schedule_specs or []):
        await create_or_replace(CronJobSpec.model_validate(spec))


async def _maybe_register_buddy_schedules_for_app(
    app,
    *,
    schedule_specs: list[dict[str, object]] | None,
) -> None:
    cron_manager = getattr(app.state, "cron_manager", None)
    create_or_replace = getattr(cron_manager, "create_or_replace_job", None)
    if not callable(create_or_replace):
        return
    for spec in list(schedule_specs or []):
        await create_or_replace(CronJobSpec.model_validate(spec))


def _spawn_buddy_onboarding_operation(
    *,
    name: str,
    work,
) -> None:
    def _runner() -> None:
        try:
            work()
        except Exception:
            logger.warning("Buddy onboarding async operation failed.", exc_info=True)

    threading.Thread(
        target=_runner,
        daemon=True,
        name=name,
    ).start()


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
    except BuddyOnboardingReasonerUnavailableError as exc:
        raise HTTPException(503, detail=str(exc) or "Buddy onboarding model is unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.post("/onboarding/identity/start", status_code=202)
async def start_buddy_identity(
    request: Request,
    payload: BuddyIdentityRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        handle = service.start_identity_operation(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    payload_data = payload.model_dump()

    def _work() -> None:
        try:
            service.submit_identity(**payload_data)
        except TimeoutError as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding model timed out.",
            )
        except BuddyOnboardingReasonerUnavailableError as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding model is unavailable.",
            )
        except Exception as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding failed.",
            )
        else:
            service.mark_operation_succeeded(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
            )

    _spawn_buddy_onboarding_operation(
        name=f"buddy-onboarding-identity-{handle.session_id}",
        work=_work,
    )
    return handle.model_dump(mode="json")


@router.post("/onboarding/contract")
async def submit_buddy_contract(
    request: Request,
    payload: BuddyContractRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        result = service.submit_contract(**payload.model_dump())
    except TimeoutError as exc:
        raise HTTPException(504, detail=str(exc) or "Buddy onboarding model timed out.") from exc
    except BuddyOnboardingReasonerUnavailableError as exc:
        raise HTTPException(503, detail=str(exc) or "Buddy onboarding model is unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.post("/onboarding/contract/start", status_code=202)
async def start_buddy_contract_compile(
    request: Request,
    payload: BuddyContractRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        handle = service.start_contract_compile(session_id=payload.session_id)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    payload_data = payload.model_dump()

    def _work() -> None:
        try:
            service.submit_contract(**payload_data)
        except TimeoutError as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding model timed out.",
            )
        except BuddyOnboardingReasonerUnavailableError as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding model is unavailable.",
            )
        except Exception as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding failed.",
            )
        else:
            service.mark_operation_succeeded(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
            )

    _spawn_buddy_onboarding_operation(
        name=f"buddy-onboarding-contract-{handle.session_id}",
        work=_work,
    )
    return handle.model_dump(mode="json")


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
    except BuddyOnboardingReasonerUnavailableError as exc:
        raise HTTPException(503, detail=str(exc) or "Buddy onboarding model is unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    await _maybe_register_buddy_schedules(
        request,
        schedule_specs=result.schedule_specs,
    )
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


@router.post("/onboarding/confirm-direction/start", status_code=202)
async def start_buddy_direction_confirmation(
    request: Request,
    payload: BuddyConfirmDirectionRequest,
) -> dict[str, object]:
    service = _get_buddy_onboarding_service(request)
    try:
        handle = service.start_confirm_direction_operation(session_id=payload.session_id)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    payload_data = payload.model_dump()
    app = request.app

    def _work() -> None:
        try:
            result = service.confirm_primary_direction(**payload_data)
        except TimeoutError as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding model timed out.",
            )
            return
        except BuddyOnboardingReasonerUnavailableError as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding model is unavailable.",
            )
            return
        except Exception as exc:
            service.mark_operation_failed(
                session_id=handle.session_id,
                operation_id=handle.operation_id,
                operation_kind=handle.operation_kind,
                error_message=str(exc) or "Buddy onboarding failed.",
            )
            return
        service.mark_operation_succeeded(
            session_id=handle.session_id,
            operation_id=handle.operation_id,
            operation_kind=handle.operation_kind,
        )
        try:
            import asyncio

            asyncio.run(
                _maybe_register_buddy_schedules_for_app(
                    app,
                    schedule_specs=result.schedule_specs,
                )
            )
        except Exception:
            logger.warning("Buddy onboarding async schedule registration failed.", exc_info=True)
        try:
            _maybe_activate_buddy_execution_for_app(
                app,
                execution_carrier=result.execution_carrier,
                domain_capability=result.domain_capability,
            )
        except Exception:
            logger.warning("Buddy onboarding async activation failed.", exc_info=True)

    _spawn_buddy_onboarding_operation(
        name=f"buddy-onboarding-confirm-{handle.session_id}",
        work=_work,
    )
    return handle.model_dump(mode="json")


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
    onboarding_service = getattr(request.app.state, "buddy_onboarding_service", None)
    if isinstance(onboarding_service, BuddyOnboardingService) and profile_id:
        try:
            onboarding_service.repair_active_domain_schedules(profile_id=profile_id)
        except Exception:
            logger.debug("Buddy surface schedule repair failed.", exc_info=True)
    service = _get_buddy_projection_service(request)
    try:
        surface = service.build_optional_chat_surface(profile_id=profile_id)
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    if surface is None:
        return Response(status_code=204)
    return surface.model_dump(mode="json")


__all__ = ["router"]
