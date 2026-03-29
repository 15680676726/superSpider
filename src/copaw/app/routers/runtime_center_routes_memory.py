# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403


@router.get("/memory/backends", response_model=list[dict[str, object]])
async def list_memory_backends(
    request: Request,
    response: Response,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_recall_service(request)
    return [item.model_dump(mode="json") for item in service.list_backends()]


@router.get("/memory/recall", response_model=dict[str, object])
async def recall_memory(
    request: Request,
    response: Response,
    query: str,
    role: str | None = None,
    backend: str | None = None,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    include_related_scopes: bool = True,
    limit: int = 8,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_recall_service(request)
    result = service.recall(
        query=query,
        role=role,
        backend=backend,
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
        include_related_scopes=include_related_scopes,
        limit=limit,
    )
    return result.model_dump(mode="json")


@router.get("/memory/index", response_model=list[dict[str, object]])
async def list_memory_index_entries(
    request: Request,
    response: Response,
    source_type: str | None = None,
    source_ref: str | None = None,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_derived_memory_index_service(request)
    return [
        entry.model_dump(mode="json")
        for entry in service.list_fact_entries(
            source_type=source_type,
            source_ref=source_ref,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            limit=limit,
        )
    ]


@router.post("/memory/rebuild", response_model=dict[str, object])
async def rebuild_memory_index(
    payload: MemoryRebuildRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_derived_memory_index_service(request)
    result = service.rebuild_all(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        include_reporting=payload.include_reporting,
        include_learning=payload.include_learning,
        evidence_limit=payload.evidence_limit,
    )
    return result.model_dump(mode="json")


@router.get("/memory/entities", response_model=list[dict[str, object]])
async def list_memory_entities(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    entity_key: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_derived_memory_index_service(request)
    return [
        view.model_dump(mode="json")
        for view in service.list_entity_views(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            entity_key=entity_key,
            limit=limit,
        )
    ]


@router.get("/memory/opinions", response_model=list[dict[str, object]])
async def list_memory_opinions(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    subject_key: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_derived_memory_index_service(request)
    return [
        view.model_dump(mode="json")
        for view in service.list_opinion_views(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            subject_key=subject_key,
            limit=limit,
        )
    ]


@router.get("/memory/reflections", response_model=list[dict[str, object]])
async def list_memory_reflections(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_reflection_service(request)
    return [
        run.model_dump(mode="json")
        for run in service.list_runs(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            status=status,
            limit=limit,
        )
    ]


@router.post("/memory/reflect", response_model=dict[str, object])
async def reflect_memory_scope(
    payload: MemoryReflectRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_reflection_service(request)
    result = service.reflect(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        owner_agent_id=payload.owner_agent_id,
        industry_instance_id=payload.industry_instance_id,
        trigger_kind=payload.trigger_kind,
        create_learning_proposals=payload.create_learning_proposals,
    )
    return result.model_dump(mode="json")
