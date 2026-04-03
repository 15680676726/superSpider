# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from .runtime_center_dependencies import (
    _get_agent_profile_service,
    _get_agent_runtime_repository,
)
from .runtime_center_mutation_helpers import (
    _dispatch_runtime_mutation,
    _get_runtime_center_facade_attr,
)
from .runtime_center_payloads import (
    _actor_runtime_payload,
    _model_dump_or_dict,
    _public_agent_payload,
)
from .runtime_center_request_models import (
    AgentCapabilityAssignmentRequest,
    GovernedAgentCapabilityAssignmentRequest,
)


def _get_agent_capability_surface(
    request: Request,
    *,
    agent_id: str,
) -> dict[str, object]:
    profile_service = _get_agent_profile_service(request)
    getter = getattr(profile_service, "get_capability_surface", None)
    if not callable(getter):
        raise HTTPException(503, detail="Agent capability surface is not available")
    surface = getter(agent_id)
    if surface is None:
        raise HTTPException(404, detail=f"Agent '{agent_id}' not found")
    return surface


def _get_decision_payload(
    request: Request,
    decision_id: str | None,
) -> dict[str, object] | None:
    if not isinstance(decision_id, str) or not decision_id.strip():
        return None
    repository = getattr(request.app.state, "decision_request_repository", None)
    if repository is None:
        return None
    decision = repository.get_decision_request(decision_id.strip())
    if decision is None:
        return None
    state_query = getattr(request.app.state, "state_query_service", None)
    getter = getattr(state_query, "get_decision_request", None)
    if callable(getter):
        detailed = getter(decision_id.strip())
        if isinstance(detailed, dict):
            return detailed
    return _model_dump_or_dict(decision)


async def _resume_query_tool_confirmation_in_background(
    query_execution_service: object,
    *,
    decision_id: str,
) -> None:
    resume = getattr(query_execution_service, "resume_query_tool_confirmation", None)
    if not callable(resume):
        return
    try:
        result = resume(decision_request_id=decision_id)
        if hasattr(result, "__await__"):
            await result
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Runtime Center failed to resume approved query-tool-confirmation '%s'",
            decision_id,
        )


def _schedule_query_tool_confirmation_resume(
    request: Request,
    *,
    decision_id: str | None,
) -> bool:
    decision = _get_decision_payload(request, decision_id)
    if not isinstance(decision, dict):
        return False
    if decision.get("decision_type") != "query-tool-confirmation":
        return False
    query_execution_service = getattr(request.app.state, "query_execution_service", None)
    resume = getattr(query_execution_service, "resume_query_tool_confirmation", None)
    if not callable(resume) or not isinstance(decision_id, str) or not decision_id.strip():
        return False
    asyncio_module = _get_runtime_center_facade_attr("asyncio", asyncio)
    create_task = getattr(asyncio_module, "create_task", asyncio.create_task)
    create_task(
        _resume_query_tool_confirmation_in_background(
            query_execution_service,
            decision_id=decision_id.strip(),
        ),
    )
    return True


async def _assign_agent_capabilities(
    request: Request,
    *,
    agent_id: str,
    payload: AgentCapabilityAssignmentRequest,
    require_actor: bool = False,
) -> dict[str, object]:
    profile_service = _get_agent_profile_service(request)
    agent = profile_service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(404, detail=f"Agent '{agent_id}' not found")
    runtime_repository = getattr(request.app.state, "agent_runtime_repository", None)
    runtime = runtime_repository.get_runtime(agent_id) if runtime_repository is not None else None
    if require_actor:
        runtime_repository = _get_agent_runtime_repository(request)
        runtime = runtime_repository.get_runtime(agent_id)
        if runtime is None:
            raise HTTPException(404, detail=f"Actor '{agent_id}' not found")
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:apply_role",
        title=f"Update capability allowlist for agent '{agent_id}'",
        payload={
            "actor": payload.actor,
            "agent_id": agent_id,
            "capabilities": list(payload.capabilities),
            "capability_assignment_mode": payload.mode,
            "reason": payload.reason,
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"updated": False, "result": result}
        raise HTTPException(400, detail=result.get("error") or "Agent capability update failed")
    detail_getter = getattr(profile_service, "get_agent_detail", None)
    detail = detail_getter(agent_id) if callable(detail_getter) else None
    if isinstance(detail, dict) and isinstance(detail.get("agent"), dict):
        agent_payload = _public_agent_payload(detail["agent"]) or {"agent_id": agent_id}
    else:
        refreshed = profile_service.get_agent(agent_id)
        agent_payload = _public_agent_payload(refreshed) or {"agent_id": agent_id}
    if runtime_repository is not None:
        runtime = runtime_repository.get_runtime(agent_id)
    return {
        "updated": True,
        "result": result,
        "agent": agent_payload,
        "runtime": _actor_runtime_payload(runtime) if runtime is not None else None,
    }


async def _submit_governed_capabilities(
    request: Request,
    *,
    agent_id: str,
    payload: GovernedAgentCapabilityAssignmentRequest,
    require_actor: bool = False,
) -> dict[str, object]:
    profile_service = _get_agent_profile_service(request)
    agent = profile_service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(404, detail=f"Agent '{agent_id}' not found")
    runtime_repository = getattr(request.app.state, "agent_runtime_repository", None)
    runtime = runtime_repository.get_runtime(agent_id) if runtime_repository is not None else None
    if require_actor:
        runtime_repository = _get_agent_runtime_repository(request)
        runtime = runtime_repository.get_runtime(agent_id)
        if runtime is None:
            raise HTTPException(404, detail=f"Actor '{agent_id}' not found")
    surface = _get_agent_capability_surface(request, agent_id=agent_id)
    requested_capabilities = list(payload.capabilities)
    if not requested_capabilities and payload.use_recommended:
        requested_capabilities = list(surface.get("recommended_capabilities") or [])
    if not requested_capabilities:
        raise HTTPException(400, detail="No capabilities were provided or recommended for governance")
    reason = payload.reason or (
        "Submit capability allowlist change through governance review"
        if payload.use_recommended
        else "Submit capability allowlist change"
    )
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:apply_role",
        title=f"Govern capability allowlist for agent '{agent_id}'",
        payload={
            "actor": payload.actor,
            "agent_id": agent_id,
            "capabilities": requested_capabilities,
            "capability_assignment_mode": payload.mode,
            "reason": reason,
        },
        fallback_risk="confirm",
        risk_level_override="confirm",
    )
    decision = _get_decision_payload(request, result.get("decision_request_id"))
    refreshed_surface = _get_agent_capability_surface(request, agent_id=agent_id)
    if not result.get("success") and result.get("phase") == "waiting-confirm":
        return {
            "submitted": True,
            "updated": False,
            "result": result,
            "decision": decision,
            "capability_surface": refreshed_surface,
            "runtime": _actor_runtime_payload(runtime) if runtime is not None else None,
        }
    if not result.get("success"):
        raise HTTPException(400, detail=result.get("error") or "Governed capability assignment failed")
    detail_getter = getattr(profile_service, "get_agent_detail", None)
    detail = detail_getter(agent_id) if callable(detail_getter) else None
    if isinstance(detail, dict) and isinstance(detail.get("agent"), dict):
        agent_payload = _public_agent_payload(detail["agent"]) or {"agent_id": agent_id}
    else:
        refreshed = profile_service.get_agent(agent_id)
        agent_payload = _public_agent_payload(refreshed) or {"agent_id": agent_id}
    if runtime_repository is not None:
        runtime = runtime_repository.get_runtime(agent_id)
    return {
        "submitted": True,
        "updated": True,
        "result": result,
        "decision": decision,
        "agent": agent_payload,
        "capability_surface": refreshed_surface,
        "runtime": _actor_runtime_payload(runtime) if runtime is not None else None,
    }


__all__ = [
    "AgentCapabilityAssignmentRequest",
    "AgentRequest",
    "GovernedAgentCapabilityAssignmentRequest",
    "_assign_agent_capabilities",
    "_get_agent_capability_surface",
    "_get_decision_payload",
    "_resume_query_tool_confirmation_in_background",
    "_schedule_query_tool_confirmation_resume",
    "_submit_governed_capabilities",
]
