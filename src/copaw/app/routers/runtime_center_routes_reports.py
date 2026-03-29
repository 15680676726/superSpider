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
    industry_instance_id: str | None = None,
    assignment_id: str | None = None,
    lane_id: str | None = None,
    cycle_id: str | None = None,
    needs_followup: bool | None = None,
    processed: bool | None = None,
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
    payload = [report.model_dump(mode="json") for report in reports]

    def _matches(report_payload: dict[str, object]) -> bool:
        if industry_instance_id and report_payload.get("industry_instance_id") != industry_instance_id:
            return False
        if assignment_id and report_payload.get("assignment_id") != assignment_id:
            return False
        if lane_id and report_payload.get("lane_id") != lane_id:
            return False
        if cycle_id and report_payload.get("cycle_id") != cycle_id:
            return False
        if needs_followup is not None and bool(report_payload.get("needs_followup")) is not needs_followup:
            return False
        if processed is not None and bool(report_payload.get("processed")) is not processed:
            return False
        return True

    return [item for item in payload if _matches(item)]


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
