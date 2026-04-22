# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import HTTPException, Request, Response

from ..runtime_center import apply_runtime_center_surface_headers
from .runtime_center_actor_capabilities import (
    AgentCapabilityAssignmentRequest,
    GovernedAgentCapabilityAssignmentRequest,
    _assign_agent_capabilities,
    _get_agent_capability_surface,
    _submit_governed_capabilities,
)
from .runtime_center_dependencies import _get_agent_profile_service
from .runtime_center_payloads import _public_agent_detail_payload, _public_agent_payload
from .runtime_center_shared import router
from ...utils.runtime_routes import agent_route


def _normalized_agent_payload(agent_id: str, payload: object | None) -> dict[str, object] | None:
    normalized = _public_agent_payload(payload)
    if normalized is None:
        return None
    normalized.setdefault("route", agent_route(agent_id))
    return normalized


@router.get("/agents", response_model=list[dict[str, object]])
async def list_agents(
    request: Request,
    response: Response,
    limit: int | None = None,
    view: str = "all",
    industry_instance_id: str | None = None,
) -> list[dict[str, object]]:
    """List visible agents for the Runtime Center surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    profile_service = _get_agent_profile_service(request)
    lister = getattr(profile_service, "list_agents", None)
    if not callable(lister):
        raise HTTPException(503, detail="Agent list queries are not available")
    agents = lister(
        limit=limit,
        view=view,
        industry_instance_id=industry_instance_id,
    )
    if not isinstance(agents, list):
        return []
    payload: list[dict[str, object]] = []
    for item in agents:
        agent_id = str(
            (item.get("agent_id") if isinstance(item, dict) else getattr(item, "agent_id", ""))
            or ""
        ).strip()
        normalized = _normalized_agent_payload(agent_id, item)
        if normalized is not None:
            payload.append(normalized)
    return payload


@router.get("/agents/{agent_id}", response_model=dict[str, object])
async def get_agent_detail(
    agent_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single agent detail payload for Runtime Center."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    profile_service = _get_agent_profile_service(request)
    detail_getter = getattr(profile_service, "get_agent_detail", None)
    detail = detail_getter(agent_id) if callable(detail_getter) else None
    if detail is not None:
        payload = _public_agent_detail_payload(detail)
        if payload is None:
            raise HTTPException(500, detail="Agent detail payload is not serializable")
        agent_payload = _normalized_agent_payload(agent_id, payload.get("agent"))
        if agent_payload is not None:
            payload["agent"] = agent_payload
        payload.setdefault("route", agent_route(agent_id))
        return payload
    getter = getattr(profile_service, "get_agent", None)
    agent = getter(agent_id) if callable(getter) else None
    if agent is None:
        raise HTTPException(404, detail=f"Agent '{agent_id}' not found")
    payload = _normalized_agent_payload(agent_id, agent)
    if payload is None:
        raise HTTPException(500, detail="Agent payload is not serializable")
    return {"agent": payload, "route": agent_route(agent_id)}


@router.get("/agents/{agent_id}/capabilities", response_model=dict[str, object])
async def get_agent_capabilities(
    agent_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return the effective capability surface for a visible agent."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    return _get_agent_capability_surface(request, agent_id=agent_id)


@router.put("/agents/{agent_id}/capabilities", response_model=dict[str, object])
async def assign_agent_capabilities(
    agent_id: str,
    request: Request,
    response: Response,
    payload: AgentCapabilityAssignmentRequest | None = None,
) -> dict[str, object]:
    """Assign an explicit capability allowlist through the agent surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    request_payload = payload or AgentCapabilityAssignmentRequest()
    return await _assign_agent_capabilities(
        request,
        agent_id=agent_id,
        payload=request_payload,
        require_actor=False,
    )


@router.post("/agents/{agent_id}/capabilities/governed", response_model=dict[str, object])
async def govern_agent_capabilities(
    agent_id: str,
    request: Request,
    response: Response,
    payload: GovernedAgentCapabilityAssignmentRequest | None = None,
) -> dict[str, object]:
    """Submit an agent capability assignment into the governance flow."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    request_payload = payload or GovernedAgentCapabilityAssignmentRequest()
    return await _submit_governed_capabilities(
        request,
        agent_id=agent_id,
        payload=request_payload,
        require_actor=False,
    )
