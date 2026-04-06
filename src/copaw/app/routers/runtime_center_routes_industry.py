# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403


@router.get("/industry", response_model=list[dict[str, object]])
async def list_industry_instances(
    request: Request,
    response: Response,
    limit: int = 20,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_industry_service(request)
    return [item.model_dump(mode="json") for item in service.list_instances(limit=limit)]


@router.get("/industry/{instance_id}", response_model=dict[str, object])
async def get_industry_instance_detail(
    instance_id: str,
    request: Request,
    response: Response,
    assignment_id: str | None = None,
    backlog_item_id: str | None = None,
    focus_kind: str | None = None,
    focus_id: str | None = None,
    report_id: str | None = None,
    lane_id: str | None = None,
    cycle_id: str | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_industry_service(request)
    supported_focus_kinds = {"assignment", "backlog"}
    if (
        report_id is not None
        or lane_id is not None
        or cycle_id is not None
        or (focus_kind is not None and focus_kind not in supported_focus_kinds)
    ):
        raise HTTPException(
            400,
            detail=(
                "Unsupported runtime-center industry focus; "
                "only assignment/backlog focus is supported."
            ),
        )
    if focus_id is not None and focus_kind is None:
        raise HTTPException(
            400,
            detail="focus_kind is required when focus_id is provided.",
        )
    if focus_kind is not None and focus_id is None:
        raise HTTPException(
            400,
            detail="focus_id is required when focus_kind is provided.",
        )
    if focus_id and focus_kind == "assignment" and assignment_id is None:
        assignment_id = focus_id
    if focus_id and focus_kind == "backlog" and backlog_item_id is None:
        backlog_item_id = focus_id
    detail_kwargs: dict[str, str] = {}
    if assignment_id is not None:
        detail_kwargs["assignment_id"] = assignment_id
    if backlog_item_id is not None:
        detail_kwargs["backlog_item_id"] = backlog_item_id
    detail = service.get_instance_detail(instance_id, **detail_kwargs)
    if detail is None:
        raise HTTPException(404, detail=f"Industry instance '{instance_id}' not found")
    return detail.model_dump(mode="json")
