# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403


@router.get("/overview", response_model=RuntimeOverviewResponse)
async def get_runtime_overview(
    request: Request,
    response: Response,
) -> RuntimeOverviewResponse:
    """Return the Runtime Center operator overview."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = RuntimeCenterQueryService()
    return await service.get_overview(request.app.state)


@router.get("/main-brain", response_model=RuntimeMainBrainResponse)
async def get_runtime_main_brain(
    request: Request,
    response: Response,
) -> RuntimeMainBrainResponse:
    """Return the dedicated Runtime Center main-brain cockpit payload."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = RuntimeCenterQueryService()
    return await service.get_main_brain(request.app.state)


@router.get("/events")
async def stream_runtime_events(
    request: Request,
    response: Response,
    after_id: int = 0,
    once: bool = False,
):
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    bus = _get_runtime_event_bus(request)
    header_after_id = request.headers.get("last-event-id")
    if after_id <= 0 and header_after_id:
        try:
            after_id = int(header_after_id)
        except ValueError:
            after_id = 0

    async def _event_stream():
        next_after_id = max(0, after_id)
        while True:
            if await request.is_disconnected():
                return
            events = await bus.wait_for_events(
                after_id=next_after_id,
                timeout=15.0,
                limit=100,
            )
            if not events:
                if once:
                    return
                yield ": keep-alive\n\n"
                continue
            for event in events:
                next_after_id = max(next_after_id, int(event.event_id))
                payload = event.model_dump(mode="json")
                payload["event_name"] = event.event_name
                yield (
                    f"id: {event.event_id}\n"
                    "event: runtime\n"
                    f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                )
            if once:
                return

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
