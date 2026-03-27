# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...industry import (
    IndustryBootstrapRequest,
    IndustryBootstrapResponse,
    IndustryDraftGenerationError,
    IndustryInstanceDetail,
    IndustryInstanceSummary,
    IndustryPreviewRequest,
    IndustryPreviewResponse,
    IndustryService,
)

router = APIRouter(prefix="/industry", tags=["industry"])


def _get_industry_service(request: Request) -> IndustryService:
    service = getattr(request.app.state, "industry_service", None)
    if isinstance(service, IndustryService):
        return service
    raise HTTPException(503, detail="Industry bootstrap service is not available")


@router.post("/v1/bootstrap", response_model=IndustryBootstrapResponse)
async def bootstrap_industry_v1(
    request: Request,
    payload: IndustryBootstrapRequest,
) -> IndustryBootstrapResponse:
    service = _get_industry_service(request)
    try:
        return await service.bootstrap_v1(payload)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.post("/v1/preview", response_model=IndustryPreviewResponse)
async def preview_industry_v1(
    request: Request,
    payload: IndustryPreviewRequest,
) -> IndustryPreviewResponse:
    service = _get_industry_service(request)
    try:
        return await service.preview_v1(payload)
    except IndustryDraftGenerationError as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.get("/v1/instances", response_model=list[IndustryInstanceSummary])
async def list_industry_instances(
    request: Request,
    limit: int = 20,
    status: str | None = "active",
) -> list[IndustryInstanceSummary]:
    service = _get_industry_service(request)
    return service.list_instances(limit=limit, status=status)


@router.get("/v1/instances/{instance_id}", response_model=IndustryInstanceDetail)
async def get_industry_instance_detail(
    request: Request,
    instance_id: str,
) -> IndustryInstanceDetail:
    service = _get_industry_service(request)
    detail = service.get_instance_detail(instance_id)
    if detail is None:
        raise HTTPException(404, detail=f"Industry instance '{instance_id}' not found")
    return detail


@router.put("/v1/instances/{instance_id}/team", response_model=IndustryBootstrapResponse)
async def update_industry_instance_team(
    request: Request,
    instance_id: str,
    payload: IndustryBootstrapRequest,
) -> IndustryBootstrapResponse:
    service = _get_industry_service(request)
    try:
        return await service.update_instance_team(instance_id, payload)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.delete("/v1/instances/{instance_id}", response_model=dict[str, object])
async def delete_industry_instance(
    request: Request,
    instance_id: str,
) -> dict[str, object]:
    service = _get_industry_service(request)
    try:
        return await service.delete_instance(instance_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
