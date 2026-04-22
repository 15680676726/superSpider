# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import Request, Response

from ..runtime_center import apply_runtime_center_surface_headers
from .runtime_center_actor_capabilities import (
    AgentCapabilityAssignmentRequest,
    GovernedAgentCapabilityAssignmentRequest,
    _assign_agent_capabilities,
    _get_agent_capability_surface,
    _submit_governed_capabilities,
)
from .runtime_center_shared import router


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
