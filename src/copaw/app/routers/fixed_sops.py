# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ...sop_kernel import (
    FixedSopBindingCreateRequest,
    FixedSopBindingDetail,
    FixedSopDoctorReport,
    FixedSopRunDetail,
    FixedSopRunRequest,
    FixedSopRunResponse,
    FixedSopService,
    FixedSopTemplateListResponse,
)
from ...state import FixedSopTemplateRecord

router = APIRouter(prefix="/fixed-sops", tags=["fixed-sops"])


def _get_fixed_sop_service(request: Request) -> FixedSopService:
    service = getattr(request.app.state, "fixed_sop_service", None)
    if isinstance(service, FixedSopService):
        return service
    raise HTTPException(503, detail="Fixed SOP service is not available")


@router.get("/templates", response_model=FixedSopTemplateListResponse)
async def list_fixed_sop_templates(
    request: Request,
    status: str | None = Query(default="active"),
) -> FixedSopTemplateListResponse:
    return _get_fixed_sop_service(request).list_template_catalog(status=status)


@router.get("/templates/{template_id}", response_model=FixedSopTemplateRecord)
async def get_fixed_sop_template(
    request: Request,
    template_id: str,
) -> FixedSopTemplateRecord:
    template = _get_fixed_sop_service(request).get_template(template_id)
    if template is None:
        raise HTTPException(404, detail=f"Fixed SOP template '{template_id}' not found")
    return template


@router.get("/bindings", response_model=list[FixedSopBindingDetail])
async def list_fixed_sop_bindings(
    request: Request,
    template_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    industry_instance_id: str | None = Query(default=None),
    owner_agent_id: str | None = Query(default=None),
    limit: int | None = Query(default=50),
) -> list[FixedSopBindingDetail]:
    return _get_fixed_sop_service(request).list_binding_details(
        template_id=template_id,
        status=status,
        industry_instance_id=industry_instance_id,
        owner_agent_id=owner_agent_id,
        limit=limit,
    )


@router.post("/bindings", response_model=FixedSopBindingDetail, status_code=201)
async def create_fixed_sop_binding(
    request: Request,
    payload: FixedSopBindingCreateRequest,
) -> FixedSopBindingDetail:
    service = _get_fixed_sop_service(request)
    try:
        return service.create_binding(payload)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@router.get("/bindings/{binding_id}", response_model=FixedSopBindingDetail)
async def get_fixed_sop_binding(
    request: Request,
    binding_id: str,
) -> FixedSopBindingDetail:
    service = _get_fixed_sop_service(request)
    try:
        return service.get_binding(binding_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@router.put("/bindings/{binding_id}", response_model=FixedSopBindingDetail)
async def update_fixed_sop_binding(
    request: Request,
    binding_id: str,
    payload: FixedSopBindingCreateRequest,
) -> FixedSopBindingDetail:
    service = _get_fixed_sop_service(request)
    try:
        return service.update_binding(binding_id, payload)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@router.post("/bindings/{binding_id}/doctor", response_model=FixedSopDoctorReport)
async def run_fixed_sop_doctor(
    request: Request,
    binding_id: str,
) -> FixedSopDoctorReport:
    service = _get_fixed_sop_service(request)
    try:
        return service.run_doctor(binding_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@router.post("/bindings/{binding_id}/run", response_model=FixedSopRunResponse)
async def run_fixed_sop_binding(
    request: Request,
    binding_id: str,
    payload: FixedSopRunRequest,
) -> FixedSopRunResponse:
    service = _get_fixed_sop_service(request)
    try:
        return await service.run_binding(binding_id, payload)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@router.get("/runs/{run_id}", response_model=FixedSopRunDetail)
async def get_fixed_sop_run(
    request: Request,
    run_id: str,
) -> FixedSopRunDetail:
    service = _get_fixed_sop_service(request)
    try:
        return service.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
