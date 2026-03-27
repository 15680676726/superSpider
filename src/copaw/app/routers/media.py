# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ...media import (
    MediaAnalysisRequest,
    MediaAnalysisResponse,
    MediaAnalysisSummary,
    MediaCapabilityState,
    MediaIngestRequest,
    MediaIngestResponse,
    MediaResolveLinkRequest,
    MediaResolveLinkResponse,
    MediaService,
    MediaSourceSpec,
)

router = APIRouter(prefix="/media", tags=["media"])


def _get_media_service(request: Request) -> MediaService:
    service = getattr(request.app.state, "media_service", None)
    if isinstance(service, MediaService):
        return service
    raise HTTPException(503, detail="Media service is not available")


@router.get("/capabilities", response_model=MediaCapabilityState)
async def get_media_capabilities(request: Request) -> MediaCapabilityState:
    return _get_media_service(request).capabilities()


@router.post("/resolve-link", response_model=MediaResolveLinkResponse)
async def resolve_media_link(
    request: Request,
    payload: MediaResolveLinkRequest,
) -> MediaResolveLinkResponse:
    try:
        return _get_media_service(request).resolve_link(payload)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.post("/ingest", response_model=MediaIngestResponse)
async def ingest_media(
    request: Request,
    file: UploadFile | None = File(default=None),
    source: str | None = Form(default=None),
) -> MediaIngestResponse:
    service = _get_media_service(request)
    if file is not None:
        try:
            source_payload = json.loads(source) if source else {}
        except json.JSONDecodeError as exc:
            raise HTTPException(400, detail="Invalid media source payload") from exc
        if not isinstance(source_payload, dict):
            raise HTTPException(400, detail="Invalid media source payload")
        payload = MediaIngestRequest(
            source=MediaSourceSpec.model_validate(
                {"source_kind": "upload", **source_payload},
            )
        )
        try:
            return service.ingest(
                payload,
                file_bytes=await file.read(),
                filename=file.filename,
                mime_type=file.content_type,
            )
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    try:
        raw_payload = await request.json()
    except Exception as exc:
        raise HTTPException(400, detail="Media ingest requires JSON or multipart form data") from exc
    try:
        payload = MediaIngestRequest.model_validate(raw_payload)
        return service.ingest(payload)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.post("/analyses", response_model=MediaAnalysisResponse)
async def analyze_media(
    request: Request,
    payload: MediaAnalysisRequest,
) -> MediaAnalysisResponse:
    try:
        return await _get_media_service(request).analyze(payload)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.get("/analyses", response_model=list[MediaAnalysisSummary])
async def list_media_analyses(
    request: Request,
    industry_instance_id: str | None = None,
    thread_id: str | None = None,
    entry_point: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[MediaAnalysisSummary]:
    return _get_media_service(request).list_analyses(
        industry_instance_id=industry_instance_id,
        thread_id=thread_id,
        entry_point=entry_point,
        status=status,
        limit=limit,
    )


@router.get("/analyses/{analysis_id}", response_model=MediaAnalysisSummary)
async def get_media_analysis(
    request: Request,
    analysis_id: str,
) -> MediaAnalysisSummary:
    summary = _get_media_service(request).get_analysis(analysis_id)
    if summary is None:
        raise HTTPException(404, detail=f"Media analysis '{analysis_id}' not found")
    return summary
