# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping

from .runtime_center_shared_core import *  # noqa: F401,F403


def _resolve_report_focus_targets(
    payload: Mapping[str, object],
    *,
    report_id: str,
) -> tuple[str | None, str | None]:
    normalized_report_id = str(report_id or "").strip()
    if not normalized_report_id:
        return None, None
    report_lists = [
        payload.get("agent_reports"),
        payload.get("reports"),
    ]
    for report_list in report_lists:
        if not isinstance(report_list, list):
            continue
        for item in report_list:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("report_id") or "").strip() != normalized_report_id:
                continue
            assignment_id = str(item.get("assignment_id") or "").strip() or None
            if assignment_id is not None:
                return assignment_id, None
            break
    backlog = payload.get("backlog")
    if isinstance(backlog, list):
        for item in backlog:
            if not isinstance(item, Mapping):
                continue
            metadata = item.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            source_report_ids = metadata.get("source_report_ids")
            if isinstance(source_report_ids, list) and normalized_report_id in {
                str(candidate).strip()
                for candidate in source_report_ids
                if str(candidate).strip()
            }:
                backlog_item_id = str(item.get("backlog_item_id") or "").strip() or None
                return None, backlog_item_id
            if str(metadata.get("source_report_id") or "").strip() == normalized_report_id:
                backlog_item_id = str(item.get("backlog_item_id") or "").strip() or None
                return None, backlog_item_id
    return None, None


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
    supported_focus_kinds = {"assignment", "backlog", "report"}
    if (
        lane_id is not None
        or cycle_id is not None
        or (focus_kind is not None and focus_kind not in supported_focus_kinds)
    ):
        raise HTTPException(
            400,
            detail=(
                "Unsupported runtime-center industry focus; "
                "only assignment/backlog/report focus is supported."
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
    if focus_id and focus_kind == "report" and report_id is None:
        report_id = focus_id
    if focus_id and focus_kind == "assignment" and assignment_id is None:
        assignment_id = focus_id
    if focus_id and focus_kind == "backlog" and backlog_item_id is None:
        backlog_item_id = focus_id
    if report_id is not None:
        base_detail = service.get_instance_detail(instance_id)
        if base_detail is None:
            raise HTTPException(404, detail=f"Industry instance '{instance_id}' not found")
        base_payload = base_detail.model_dump(mode="json")
        resolved_assignment_id, resolved_backlog_item_id = _resolve_report_focus_targets(
            base_payload,
            report_id=report_id,
        )
        if resolved_assignment_id is None and resolved_backlog_item_id is None:
            raise HTTPException(
                404,
                detail=f"Industry report '{report_id}' not found in instance '{instance_id}'",
            )
        assignment_id = assignment_id or resolved_assignment_id
        backlog_item_id = backlog_item_id or resolved_backlog_item_id
    detail_kwargs: dict[str, str] = {}
    if assignment_id is not None:
        detail_kwargs["assignment_id"] = assignment_id
    if backlog_item_id is not None:
        detail_kwargs["backlog_item_id"] = backlog_item_id
    detail = service.get_instance_detail(instance_id, **detail_kwargs)
    if detail is None:
        raise HTTPException(404, detail=f"Industry instance '{instance_id}' not found")
    return detail.model_dump(mode="json")
