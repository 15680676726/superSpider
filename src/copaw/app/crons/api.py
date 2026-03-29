# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .manager import CronManager
from .models import CronJobSpec, CronJobView
from ..runtime_center import apply_runtime_center_surface_headers

router = APIRouter(prefix="/cron", tags=["cron"])


def _mark_runtime_center_surface(response: Response) -> None:
    apply_runtime_center_surface_headers(response, surface="cron")


def get_cron_manager(request: Request) -> CronManager:
    mgr = getattr(request.app.state, "cron_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="cron manager not initialized",
        )
    return mgr


async def _dispatch_governed_schedule_mutation(
    request: Request,
    *,
    capability_ref: str,
    title: str,
    payload: dict[str, object],
    fallback_risk: str = "guarded",
) -> dict[str, object]:
    from ..routers.governed_mutations import dispatch_governed_mutation

    return await dispatch_governed_mutation(
        request,
        capability_ref=capability_ref,
        title=title,
        payload=payload,
        environment_ref="config:runtime",
        fallback_risk=fallback_risk,
    )


@router.get("/jobs", response_model=list[CronJobSpec])
async def list_jobs(
    response: Response,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    return await mgr.list_jobs()


@router.get("/jobs/{job_id}", response_model=CronJobView)
async def get_job(
    job_id: str,
    response: Response,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return CronJobView(spec=job, state=mgr.get_state(job_id))


@router.post("/jobs", response_model=dict[str, object])
async def create_job(
    request: Request,
    response: Response,
    spec: CronJobSpec,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    # server generates id; ignore client-provided spec.id
    job_id = str(uuid.uuid4())
    created = spec.model_copy(update={"id": job_id})
    if await mgr.get_job(job_id) is not None:
        raise HTTPException(status_code=409, detail=f"job already exists: {job_id}")
    result = await _dispatch_governed_schedule_mutation(
        request,
        capability_ref="system:create_schedule",
        title=f"Create cron job '{job_id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "job": created.model_dump(mode="json"),
            "disable_main_brain_auto_adjudicate": True,
        },
        fallback_risk="confirm",
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"created": False, "result": result, "job": created.model_dump(mode="json")}
        raise HTTPException(status_code=400, detail=result.get("error") or "job creation failed")
    return {"created": True, "result": result, "job": created.model_dump(mode="json")}


@router.put("/jobs/{job_id}", response_model=dict[str, object])
async def replace_job(
    job_id: str,
    spec: CronJobSpec,
    request: Request,
    response: Response,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    if spec.id != job_id:
        raise HTTPException(status_code=400, detail="job_id mismatch")
    if await mgr.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    result = await _dispatch_governed_schedule_mutation(
        request,
        capability_ref="system:update_schedule",
        title=f"Update cron job '{job_id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "schedule_id": job_id,
            "job": spec.model_dump(mode="json"),
            "disable_main_brain_auto_adjudicate": True,
        },
        fallback_risk="confirm",
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"updated": False, "result": result, "job": spec.model_dump(mode="json")}
        raise HTTPException(status_code=400, detail=result.get("error") or "job update failed")
    return {"updated": True, "result": result, "job": spec.model_dump(mode="json")}


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    request: Request,
    response: Response,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    if await mgr.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    result = await _dispatch_governed_schedule_mutation(
        request,
        capability_ref="system:delete_schedule",
        title=f"Delete cron job '{job_id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "schedule_id": job_id,
            "disable_main_brain_auto_adjudicate": True,
        },
        fallback_risk="confirm",
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"deleted": False, "result": result, "job_id": job_id}
        raise HTTPException(status_code=400, detail=result.get("error") or "job deletion failed")
    return {"deleted": True, "result": result, "job_id": job_id}


@router.post("/jobs/{job_id}/pause")
async def pause_job(
    job_id: str,
    request: Request,
    response: Response,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    if await mgr.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    result = await _dispatch_governed_schedule_mutation(
        request,
        capability_ref="system:pause_schedule",
        title=f"Pause cron job '{job_id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "schedule_id": job_id,
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"paused": False, "result": result, "job_id": job_id}
        raise HTTPException(status_code=400, detail=result.get("error") or "job pause failed")
    return {"paused": True, "result": result, "job_id": job_id}


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    request: Request,
    response: Response,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    if await mgr.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    result = await _dispatch_governed_schedule_mutation(
        request,
        capability_ref="system:resume_schedule",
        title=f"Resume cron job '{job_id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "schedule_id": job_id,
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"resumed": False, "result": result, "job_id": job_id}
        raise HTTPException(status_code=400, detail=result.get("error") or "job resume failed")
    return {"resumed": True, "result": result, "job_id": job_id}


@router.post("/jobs/{job_id}/run")
async def run_job(
    job_id: str,
    request: Request,
    response: Response,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    if await mgr.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    result = await _dispatch_governed_schedule_mutation(
        request,
        capability_ref="system:run_schedule",
        title=f"Run cron job '{job_id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "schedule_id": job_id,
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"started": False, "result": result, "job_id": job_id}
        raise HTTPException(status_code=400, detail=result.get("error") or "job run failed")
    return {"started": True, "result": result, "job_id": job_id}


@router.get("/jobs/{job_id}/state")
async def get_job_state(
    job_id: str,
    response: Response,
    mgr: CronManager = Depends(get_cron_manager),
):
    _mark_runtime_center_surface(response)
    job = await mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return mgr.get_state(job_id).model_dump(mode="json")
