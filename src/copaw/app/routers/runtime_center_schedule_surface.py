# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import Request, Response


async def _get_schedule_surface(
    schedule_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    detail = await get_schedule_detail(schedule_id, request, response)
    return detail if isinstance(detail, dict) else {"schedule": detail}


async def get_schedule_detail(
    schedule_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    from .runtime_center_routes_ops import get_schedule_detail as impl

    return await impl(schedule_id, request, response)


__all__ = [
    "_get_schedule_surface",
    "get_schedule_detail",
]
