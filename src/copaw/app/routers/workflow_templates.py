# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...state import WorkflowPresetRecord, WorkflowRunRecord, WorkflowTemplateRecord
from ...workflows import (
    WorkflowPresetCreateRequest,
    WorkflowLaunchRequest,
    WorkflowPreviewRequest,
    WorkflowRunCancelRequest,
    WorkflowRunDetail,
    WorkflowRunResumeRequest,
    WorkflowStepExecutionDetail,
    WorkflowTemplatePreview,
    WorkflowTemplateService,
)

router = APIRouter(prefix="/workflow-templates", tags=["workflow-templates"])
run_router = APIRouter(prefix="/workflow-runs", tags=["workflow-runs"])


class WorkflowTemplateSummaryResponse(BaseModel):
    template: WorkflowTemplateRecord
    dependency_status: dict[str, bool] = Field(default_factory=dict)
    routes: dict[str, str] = Field(default_factory=dict)


def _get_workflow_service(request: Request) -> WorkflowTemplateService:
    service = getattr(request.app.state, "workflow_template_service", None)
    if isinstance(service, WorkflowTemplateService):
        return service
    raise HTTPException(503, detail="Workflow template service is not available")


@router.get("", response_model=list[WorkflowTemplateSummaryResponse])
async def list_workflow_templates(
    request: Request,
    category: str | None = Query(default=None),
    status: str | None = Query(default="active"),
) -> list[WorkflowTemplateSummaryResponse]:
    service = _get_workflow_service(request)
    templates = service.list_templates(category=category, status=status)
    payload: list[WorkflowTemplateSummaryResponse] = []
    for template in templates:
        dependency_status = {
            capability_id: service.has_capability(capability_id)
            for capability_id in template.dependency_capability_ids
        }
        payload.append(
            WorkflowTemplateSummaryResponse(
                template=template,
                dependency_status=dependency_status,
                routes={
                    "detail": f"/api/workflow-templates/{template.template_id}",
                    "preview": f"/api/workflow-templates/{template.template_id}/preview",
                },
            ),
        )
    return payload


@router.get("/{template_id}", response_model=WorkflowTemplateRecord)
async def get_workflow_template(
    request: Request,
    template_id: str,
) -> WorkflowTemplateRecord:
    service = _get_workflow_service(request)
    template = service.get_template(template_id)
    if template is None:
        raise HTTPException(404, detail=f"Workflow template '{template_id}' not found")
    return template


@router.get("/{template_id}/presets", response_model=list[WorkflowPresetRecord])
async def list_workflow_presets(
    request: Request,
    template_id: str,
    industry_instance_id: str | None = Query(default=None),
    owner_scope: str | None = Query(default=None),
) -> list[WorkflowPresetRecord]:
    service = _get_workflow_service(request)
    template = service.get_template(template_id)
    if template is None:
        raise HTTPException(404, detail=f"Workflow template '{template_id}' not found")
    return service.list_presets(
        template_id,
        industry_instance_id=industry_instance_id,
        owner_scope=owner_scope,
    )


@router.post("/{template_id}/presets", response_model=WorkflowPresetRecord, status_code=201)
async def create_workflow_preset(
    request: Request,
    template_id: str,
    payload: WorkflowPresetCreateRequest,
) -> WorkflowPresetRecord:
    service = _get_workflow_service(request)
    try:
        return service.create_preset(
            template_id,
            name=payload.name,
            summary=payload.summary,
            owner_scope=payload.owner_scope,
            industry_scope=payload.industry_scope,
            created_by=payload.created_by,
            parameters=payload.parameters,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc


@router.post("/{template_id}/preview", response_model=WorkflowTemplatePreview)
async def preview_workflow_template(
    request: Request,
    template_id: str,
    payload: WorkflowPreviewRequest,
) -> WorkflowTemplatePreview:
    service = _get_workflow_service(request)
    try:
        return service.preview_template(template_id, payload)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.post("/{template_id}/launch", response_model=WorkflowRunDetail)
async def launch_workflow_template(
    request: Request,
    template_id: str,
    payload: WorkflowLaunchRequest,
) -> WorkflowRunDetail:
    service = _get_workflow_service(request)
    try:
        return await service.launch_template(template_id, payload)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@run_router.get("", response_model=list[WorkflowRunRecord])
async def list_workflow_runs(
    request: Request,
    template_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    industry_instance_id: str | None = Query(default=None),
) -> list[WorkflowRunRecord]:
    service = _get_workflow_service(request)
    return service.list_runs(
        template_id=template_id,
        status=status,
        industry_instance_id=industry_instance_id,
    )


@run_router.get("/{run_id}", response_model=WorkflowRunDetail)
async def get_workflow_run(
    request: Request,
    run_id: str,
) -> WorkflowRunDetail:
    service = _get_workflow_service(request)
    try:
        return service.get_run_detail(run_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@run_router.post("/{run_id}/cancel", response_model=WorkflowRunDetail)
async def cancel_workflow_run(
    request: Request,
    run_id: str,
    payload: WorkflowRunCancelRequest,
) -> WorkflowRunDetail:
    service = _get_workflow_service(request)
    try:
        return await service.cancel_run(
            run_id,
            actor=payload.actor,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@run_router.post("/{run_id}/resume", response_model=WorkflowRunDetail)
async def resume_workflow_run(
    request: Request,
    run_id: str,
    payload: WorkflowRunResumeRequest,
) -> WorkflowRunDetail:
    service = _get_workflow_service(request)
    try:
        return await service.resume_run(
            run_id,
            actor=payload.actor,
            execute=payload.execute,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@run_router.get(
    "/{run_id}/steps/{step_id}",
    response_model=WorkflowStepExecutionDetail,
)
async def get_workflow_run_step_detail(
    request: Request,
    run_id: str,
    step_id: str,
) -> WorkflowStepExecutionDetail:
    service = _get_workflow_service(request)
    try:
        return service.get_run_step_detail(run_id, step_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
