# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403
from .runtime_center_payloads import serialize_surface_learning_payload


@router.get("/knowledge/documents", response_model=list[dict[str, object]])
async def list_knowledge_documents(
    request: Request,
    response: Response,
    query: str | None = None,
    role: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    return service.list_documents(query=query, role=role, limit=limit)


@router.get("/knowledge/retrieve", response_model=list[dict[str, object]])
async def retrieve_knowledge_chunks(
    request: Request,
    response: Response,
    query: str,
    role: str | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    return [
        _serialize_knowledge_chunk(chunk)
        for chunk in service.retrieve(query=query, role=role, limit=limit)
    ]


@router.get("/knowledge/memory", response_model=list[dict[str, object]])
async def list_memory_chunks(
    request: Request,
    response: Response,
    query: str | None = None,
    role: str | None = None,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    return [
        _serialize_knowledge_chunk(chunk)
        for chunk in service.list_memory(
            query=query,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            agent_id=agent_id,
            industry_instance_id=industry_instance_id,
            global_scope_id=global_scope_id,
            limit=limit,
        )
    ]


@router.post("/knowledge/memory", response_model=dict[str, object])
async def remember_memory_fact(
    payload: KnowledgeMemoryUpsertRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    try:
        chunk = service.remember_fact(
            title=payload.title,
            content=payload.content,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            source_ref=payload.source_ref,
            role_bindings=payload.role_bindings,
            tags=payload.tags,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return _serialize_knowledge_chunk(chunk)


@router.get("/knowledge", response_model=list[dict[str, object]])
async def list_knowledge_chunks(
    request: Request,
    response: Response,
    query: str | None = None,
    role: str | None = None,
    document_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    return [
        _serialize_knowledge_chunk(chunk)
        for chunk in service.list_chunks(
            query=query,
            role=role,
            document_id=document_id,
            limit=limit,
        )
    ]


@router.post("/knowledge/import", response_model=dict[str, object])
async def import_knowledge_document(
    request: Request,
    response: Response,
    payload: KnowledgeImportRequest,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    try:
        result = service.import_document(
            title=payload.title,
            content=payload.content,
            source_ref=payload.source_ref,
            role_bindings=payload.role_bindings,
            tags=payload.tags,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    result["chunks"] = [
        _serialize_knowledge_chunk(chunk)
        for chunk in result.get("chunks", [])
    ]
    return result


@router.get("/knowledge/surface", response_model=dict[str, object])
async def get_surface_learning_knowledge_payload(
    request: Request,
    response: Response,
    scope_type: Literal["industry", "agent", "work_context"],
    scope_id: str,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    owner_agent_id: str | None = None,
    limit: int = 3,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query_service = _get_state_query_service(request)
    payload = state_query_service.get_surface_learning_scope(
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        owner_agent_id=owner_agent_id,
        limit=limit,
    )
    if payload is None:
        raise HTTPException(404, detail="Surface learning scope not found")
    serialized = serialize_surface_learning_payload(
        payload=payload,
        live_graph=payload.get("live_graph") if isinstance(payload, dict) else None,
        latest_evidence=payload.get("latest_evidence") if isinstance(payload, dict) else None,
    )
    if serialized is None:
        raise HTTPException(404, detail="Surface learning scope not found")
    return serialized


@router.get("/knowledge/{chunk_id}", response_model=dict[str, object])
async def get_knowledge_chunk(
    chunk_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    chunk = service.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(404, detail=f"Knowledge chunk '{chunk_id}' not found")
    return _serialize_knowledge_chunk(chunk)


@router.put("/knowledge/{chunk_id}", response_model=dict[str, object])
async def upsert_knowledge_chunk(
    chunk_id: str,
    request: Request,
    response: Response,
    payload: KnowledgeChunkUpsertRequest,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    try:
        chunk = service.upsert_chunk(
            chunk_id=chunk_id,
            document_id=payload.document_id,
            title=payload.title,
            content=payload.content,
            source_ref=payload.source_ref,
            chunk_index=payload.chunk_index,
            role_bindings=payload.role_bindings,
            tags=payload.tags,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return _serialize_knowledge_chunk(chunk)


@router.delete("/knowledge/{chunk_id}", response_model=dict[str, object])
async def delete_knowledge_chunk(
    chunk_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_knowledge_service(request)
    deleted = service.delete_chunk(chunk_id)
    return {"deleted": bool(deleted)}
