# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403
from ..runtime_center.models import RuntimeCenterAppStateView


def _get_runtime_center_query_service(request: Request) -> RuntimeCenterQueryService:
    service = getattr(request.app.state, "runtime_center_query_service", None)
    if isinstance(service, RuntimeCenterQueryService):
        return service
    if (
        service is not None
        and callable(getattr(service, "get_surface", None))
    ):
        return service
    service = RuntimeCenterQueryService()
    request.app.state.runtime_center_query_service = service
    return service


def _get_runtime_center_state_view(request: Request) -> RuntimeCenterAppStateView:
    return RuntimeCenterAppStateView.from_object(request.app.state)


def _normalize_surface_sections(raw_sections: str | None) -> tuple[bool, bool]:
    if raw_sections is None or not raw_sections.strip():
        return True, True
    requested = {
        value.strip().lower()
        for value in raw_sections.split(",")
        if value.strip()
    }
    if not requested or "all" in requested:
        return True, True
    include_cards = "cards" in requested
    include_main_brain = "main_brain" in requested or "main-brain" in requested
    if not include_cards and not include_main_brain:
        return True, True
    return include_cards, include_main_brain


@router.get("/surface", response_model=RuntimeCenterSurfaceResponse)
async def get_runtime_surface(
    request: Request,
    response: Response,
    sections: str | None = None,
) -> RuntimeCenterSurfaceResponse:
    """Return the canonical Runtime Center page surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_runtime_center_query_service(request)
    include_cards, include_main_brain = _normalize_surface_sections(sections)
    runtime_state = _get_runtime_center_state_view(request)
    try:
        return await service.get_surface(
            runtime_state,
            include_cards=include_cards,
            include_main_brain=include_main_brain,
        )
    except TypeError:
        return await service.get_surface(runtime_state)


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
