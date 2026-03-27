# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ...state import ExecutionRoutineRecord, RoutineRunRecord
from ...routines import (
    RoutineCreateFromEvidenceRequest,
    RoutineCreateRequest,
    RoutineDetail,
    RoutineDiagnosis,
    RoutineRunDetail,
    RoutineService,
)

router = APIRouter(prefix="/routines", tags=["routines"])


def _get_routine_service(request: Request) -> RoutineService:
    service = getattr(request.app.state, "routine_service", None)
    if isinstance(service, RoutineService):
        return service
    raise HTTPException(503, detail="Routine service is not available")


@router.get("/runs", response_model=list[RoutineRunRecord])
async def list_routine_runs(
    request: Request,
    routine_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    owner_agent_id: str | None = Query(default=None),
    failure_class: str | None = Query(default=None),
) -> list[RoutineRunRecord]:
    service = _get_routine_service(request)
    return service.list_runs(
        routine_id=routine_id,
        status=status,
        source_type=source_type,
        owner_agent_id=owner_agent_id,
        failure_class=failure_class,
    )


@router.get("/runs/{run_id}", response_model=RoutineRunDetail)
async def get_routine_run(
    request: Request,
    run_id: str,
) -> RoutineRunDetail:
    service = _get_routine_service(request)
    try:
        return service.get_run_detail(run_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@router.post("", response_model=ExecutionRoutineRecord, status_code=201)
async def create_routine(
    request: Request,
    payload: RoutineCreateRequest,
) -> ExecutionRoutineRecord:
    service = _get_routine_service(request)
    try:
        return service.create_routine(payload)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.post("/from-evidence", response_model=ExecutionRoutineRecord, status_code=201)
async def create_routine_from_evidence(
    request: Request,
    payload: RoutineCreateFromEvidenceRequest,
) -> ExecutionRoutineRecord:
    service = _get_routine_service(request)
    try:
        return service.create_routine_from_evidence(payload)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.get("", response_model=list[ExecutionRoutineRecord])
async def list_routines(
    request: Request,
    status: str | None = Query(default=None),
    owner_scope: str | None = Query(default=None),
    owner_agent_id: str | None = Query(default=None),
    engine_kind: str | None = Query(default=None),
) -> list[ExecutionRoutineRecord]:
    service = _get_routine_service(request)
    return service.list_routines(
        status=status,
        owner_scope=owner_scope,
        owner_agent_id=owner_agent_id,
        engine_kind=engine_kind,
    )


@router.get("/{routine_id}", response_model=RoutineDetail)
async def get_routine(
    request: Request,
    routine_id: str,
) -> RoutineDetail:
    service = _get_routine_service(request)
    try:
        return service.get_routine_detail(routine_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@router.get("/{routine_id}/diagnosis", response_model=RoutineDiagnosis)
async def get_routine_diagnosis(
    request: Request,
    routine_id: str,
) -> RoutineDiagnosis:
    service = _get_routine_service(request)
    try:
        return service.get_diagnosis(routine_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
