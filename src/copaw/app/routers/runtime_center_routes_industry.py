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
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_industry_service(request)
    detail = service.get_instance_detail(instance_id)
    if detail is None:
        raise HTTPException(404, detail=f"Industry instance '{instance_id}' not found")
    return detail.model_dump(mode="json")
