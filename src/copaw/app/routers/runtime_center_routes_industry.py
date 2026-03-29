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
    focus_kind: Literal["assignment", "backlog", "agent_report", "lane", "cycle"] | None = None,
    focus_id: str | None = None,
    report_id: str | None = None,
    lane_id: str | None = None,
    cycle_id: str | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_industry_service(request)
    if focus_id and focus_kind == "assignment" and assignment_id is None:
        assignment_id = focus_id
    if focus_id and focus_kind == "backlog" and backlog_item_id is None:
        backlog_item_id = focus_id
    detail = service.get_instance_detail(
        instance_id,
        assignment_id=assignment_id,
        backlog_item_id=backlog_item_id,
    )
    if detail is None:
        raise HTTPException(404, detail=f"Industry instance '{instance_id}' not found")
    payload = detail.model_dump(mode="json")
    selected_focus: dict[str, object] | None = None
    if focus_kind == "agent_report" and focus_id:
        selected_focus = {
            "selection_kind": "agent_report",
            "report_id": focus_id,
            "title": focus_id,
        }
    elif focus_kind == "lane" and focus_id:
        selected_focus = {
            "selection_kind": "lane",
            "lane_id": focus_id,
            "title": focus_id,
        }
    elif focus_kind == "cycle" and focus_id:
        selected_focus = {
            "selection_kind": "cycle",
            "cycle_id": focus_id,
            "title": focus_id,
        }
    elif report_id:
        selected_focus = {
            "selection_kind": "agent_report",
            "report_id": report_id,
            "title": report_id,
        }
    elif lane_id:
        selected_focus = {
            "selection_kind": "lane",
            "lane_id": lane_id,
            "title": lane_id,
        }
    elif cycle_id:
        selected_focus = {
            "selection_kind": "cycle",
            "cycle_id": cycle_id,
            "title": cycle_id,
        }
    if selected_focus:
        payload["focus_selection"] = selected_focus
    return payload
