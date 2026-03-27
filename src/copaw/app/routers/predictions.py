# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ...industry import IndustryService
from ...predictions import (
    PredictionCaseDetail,
    PredictionCaseSummary,
    PredictionCreateRequest,
    PredictionRecommendationCoordinationResponse,
    PredictionRecommendationExecuteRequest,
    PredictionRecommendationExecutionResponse,
    PredictionReviewCreateRequest,
    PredictionService,
)
from ._prediction_main_brain_bridge import (
    coordinate_prediction_recommendation as coordinate_prediction_recommendation_bridge,
)

router = APIRouter(tags=["predictions"])


def _get_prediction_service(request: Request) -> PredictionService:
    service = getattr(request.app.state, "prediction_service", None)
    if isinstance(service, PredictionService):
        return service
    raise HTTPException(503, detail="Prediction service is not available")


def _get_industry_service(request: Request) -> IndustryService:
    service = getattr(request.app.state, "industry_service", None)
    if isinstance(service, IndustryService):
        return service
    raise HTTPException(503, detail="Industry service is not available")


@router.get("/predictions", response_model=list[PredictionCaseSummary])
async def list_predictions(
    request: Request,
    case_kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    industry_instance_id: str | None = Query(default=None),
    owner_scope: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[PredictionCaseSummary]:
    service = _get_prediction_service(request)
    return service.list_cases(
        case_kind=case_kind,
        status=status,
        industry_instance_id=industry_instance_id,
        owner_scope=owner_scope,
        limit=limit,
    )


@router.post("/predictions", response_model=PredictionCaseDetail)
async def create_prediction(
    request: Request,
    payload: PredictionCreateRequest,
) -> PredictionCaseDetail:
    service = _get_prediction_service(request)
    try:
        return service.create_case(payload)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.get("/predictions/{case_id}", response_model=PredictionCaseDetail)
async def get_prediction_detail(
    request: Request,
    case_id: str,
) -> PredictionCaseDetail:
    service = _get_prediction_service(request)
    try:
        return service.get_case_detail(case_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc


@router.post(
    "/predictions/{case_id}/recommendations/{recommendation_id}/coordinate",
    response_model=PredictionRecommendationCoordinationResponse,
)
async def coordinate_prediction_recommendation(
    request: Request,
    case_id: str,
    recommendation_id: str,
    payload: PredictionRecommendationExecuteRequest,
) -> PredictionRecommendationCoordinationResponse:
    service = _get_prediction_service(request)
    industry_service = _get_industry_service(request)
    try:
        detail = service.get_case_detail(case_id)
        recommendation_view = next(
            (
                item
                for item in detail.recommendations
                if item.recommendation.get("recommendation_id") == recommendation_id
            ),
            None,
        )
        if recommendation_view is None:
            raise KeyError(
                f"Prediction recommendation '{recommendation_id}' not found for case '{case_id}'",
            )
        case_payload = dict(detail.case or {})
        metadata = (
            dict(case_payload.get("metadata") or {})
            if isinstance(case_payload.get("metadata"), dict)
            else {}
        )
        industry_instance_id = str(case_payload.get("industry_instance_id") or "").strip()
        if not industry_instance_id:
            raise ValueError("Prediction case is not bound to an industry instance")
        coordination = await coordinate_prediction_recommendation_bridge(
            industry_service,
            industry_instance_id=industry_instance_id,
            actor=payload.actor,
            case_id=case_id,
            case_payload=case_payload,
            recommendation=recommendation_view.recommendation,
            source_route=(
                recommendation_view.routes.get("case")
                if isinstance(recommendation_view.routes, dict)
                else None
            ),
            meeting_window=str(metadata.get("meeting_window") or "").strip() or None,
        )
        return PredictionRecommendationCoordinationResponse(
            detail=service.get_case_detail(case_id),
            **coordination,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc


@router.post("/predictions/{case_id}/reviews", response_model=PredictionCaseDetail)
async def create_prediction_review(
    request: Request,
    case_id: str,
    payload: PredictionReviewCreateRequest,
) -> PredictionCaseDetail:
    service = _get_prediction_service(request)
    try:
        return service.add_review(case_id, payload)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
