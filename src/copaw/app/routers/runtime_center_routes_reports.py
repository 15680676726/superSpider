# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403


@router.get("/reports", response_model=list[dict[str, object]])
async def list_runtime_reports(
    request: Request,
    response: Response,
    window: Literal["daily", "weekly", "monthly"] | None = None,
    scope_type: Literal["global", "industry", "agent"] = "global",
    scope_id: str | None = None,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_reporting_service(request)
    try:
        reports = service.list_reports(
            window=window,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    return [report.model_dump(mode="json") for report in reports]


@router.get("/performance", response_model=dict[str, object])
async def get_runtime_performance_overview(
    request: Request,
    response: Response,
    window: Literal["daily", "weekly", "monthly"] = "weekly",
    scope_type: Literal["global", "industry", "agent"] = "global",
    scope_id: str | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_reporting_service(request)
    try:
        overview = service.get_performance_overview(
            window=window,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    return overview


@router.get("/strategy-memory", response_model=list[dict[str, object]])
async def list_strategy_memory(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    status: str | None = "active",
    limit: int = 20,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_strategy_memory_service(request)
    records = service.list_strategies(
        scope_type=scope_type,
        scope_id=scope_id,
        owner_agent_id=owner_agent_id,
        industry_instance_id=industry_instance_id,
        status=status,
        limit=limit,
    )
    payload: list[dict[str, object]] = []
    for record in records:
        if hasattr(record, "model_dump") and callable(getattr(record, "model_dump")):
            payload.append(record.model_dump(mode="json"))
        elif isinstance(record, dict):
            payload.append(dict(record))
    return payload
