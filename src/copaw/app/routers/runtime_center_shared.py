# -*- coding: utf-8 -*-
"""Runtime Center API for the operator surface."""
from __future__ import annotations

import asyncio
import json
import inspect
import logging
import sys

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from ..crons.models import CronJobSpec
from ..runtime_center import (
    RuntimeConversationFacade,
    RuntimeConversationPayload,
    RuntimeCenterQueryService,
    RuntimeOverviewResponse,
    apply_runtime_center_surface_headers,
)
from ..runtime_threads import SessionRuntimeThreadHistoryReader
from ...config import get_heartbeat_config
from ...industry import IndustryService
from ...predictions import PredictionCapabilityOptimizationOverview
from ...config.config import HeartbeatConfig
from ...utils.runtime_action_links import build_patch_actions
from .governed_mutations import (
    dispatch_governed_mutation,
    get_capability_service as _shared_get_capability_service,
    get_kernel_dispatcher as _shared_get_kernel_dispatcher,
    translate_dispatcher_error,
)

router = APIRouter(prefix="/runtime-center", tags=["runtime-center"])
logger = logging.getLogger(__name__)

_ACTIVE_ACTOR_MAILBOX_STATUSES = frozenset(
    {"queued", "leased", "running", "blocked", "retry-wait"},
)
_ACTIVE_ACTOR_CHECKPOINT_STATUSES = frozenset({"ready"})


class DecisionApproveRequest(BaseModel):
    resolution: str | None = Field(default=None)
    execute: bool | None = Field(default=None)


class DecisionRejectRequest(BaseModel):
    resolution: str | None = Field(default=None)


class GoalCompileActionRequest(BaseModel):
    context: dict[str, object] = Field(default_factory=dict)


class PatchActionRequest(BaseModel):
    actor: str = Field(default="system")


class GovernanceEmergencyStopRequest(BaseModel):
    actor: str = Field(default="runtime-center")
    reason: str = Field(default="Operator emergency stop")


class GovernanceResumeRequest(BaseModel):
    actor: str = Field(default="runtime-center")
    reason: str | None = Field(default=None)


class GovernanceDecisionBatchRequest(BaseModel):
    decision_ids: list[str] = Field(default_factory=list)
    actor: str = Field(default="runtime-center")
    resolution: str | None = Field(default=None)
    execute: bool | None = Field(default=None)
    control_thread_id: str | None = Field(default=None)
    session_id: str | None = Field(default=None)
    user_id: str | None = Field(default=None)
    agent_id: str | None = Field(default=None)
    work_context_id: str | None = Field(default=None)


class GovernancePatchBatchRequest(BaseModel):
    patch_ids: list[str] = Field(default_factory=list)
    actor: str = Field(default="runtime-center")


class SessionForceReleaseRequest(BaseModel):
    reason: str = Field(default="forced release from runtime center")


class BridgeSessionWorkAckRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    work_id: str = Field(min_length=1)
    bridge_session_id: str | None = Field(default=None)
    ttl_seconds: int | None = Field(default=None, ge=1)
    workspace_trusted: bool | None = Field(default=None)
    elevated_auth_state: str | None = Field(default=None)
    handle: dict[str, object] | None = Field(default=None)


class BridgeSessionWorkHeartbeatRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    work_id: str = Field(min_length=1)
    ttl_seconds: int | None = Field(default=None, ge=1)
    handle: dict[str, object] | None = Field(default=None)


class BridgeSessionWorkReconnectRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    work_id: str = Field(min_length=1)
    ttl_seconds: int | None = Field(default=None, ge=1)
    handle: dict[str, object] | None = Field(default=None)


class BridgeSessionWorkStopRequest(BaseModel):
    work_id: str = Field(min_length=1)
    force: bool = Field(default=False)
    lease_token: str | None = Field(default=None)
    reason: str | None = Field(default=None)


class BridgeSessionArchiveRequest(BaseModel):
    lease_token: str | None = Field(default=None)
    reason: str | None = Field(default=None)


class BridgeEnvironmentDeregisterRequest(BaseModel):
    reason: str | None = Field(default=None)


class KnowledgeImportRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_ref: str | None = None
    role_bindings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KnowledgeChunkUpsertRequest(BaseModel):
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_ref: str | None = None
    chunk_index: int = Field(default=0, ge=0)
    role_bindings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KnowledgeMemoryUpsertRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] = "agent"
    scope_id: str = Field(min_length=1)
    source_ref: str | None = None
    role_bindings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class MemoryRebuildRequest(BaseModel):
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = Field(default=None)
    scope_id: str | None = Field(default=None)
    include_reporting: bool = True
    include_learning: bool = True
    evidence_limit: int = Field(default=200, ge=0, le=2000)


class MemoryReflectRequest(BaseModel):
    scope_type: Literal["global", "industry", "agent", "task", "work_context"]
    scope_id: str = Field(min_length=1)
    owner_agent_id: str | None = Field(default=None)
    industry_instance_id: str | None = Field(default=None)
    trigger_kind: str = Field(default="manual", min_length=1)
    create_learning_proposals: bool = True


class TaskBatchActionRequest(BaseModel):
    task_ids: list[str] = Field(default_factory=list)
    action: Literal["cancel"] = "cancel"
    actor: str = Field(default="runtime-center", min_length=1)
    reason: str | None = Field(default=None)


class ActorPauseRequest(BaseModel):
    reason: str | None = Field(default=None)
    actor: str = Field(default="runtime-center")


class ActorCancelRequest(BaseModel):
    task_id: str | None = Field(default=None)
    actor: str = Field(default="runtime-center")


class AgentCapabilityAssignmentRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    mode: Literal["replace", "merge"] = "replace"
    actor: str = Field(default="runtime-center")
    reason: str | None = Field(default=None)


class GovernedAgentCapabilityAssignmentRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    mode: Literal["replace", "merge"] = "replace"
    actor: str = Field(default="copaw-governance")
    reason: str | None = Field(default=None)
    use_recommended: bool = Field(default=True)


def _get_state_query_service(request: Request):
    service = getattr(request.app.state, "state_query_service", None)
    if service is None:
        raise HTTPException(503, detail="Runtime state query service is not available")
    return service


def _get_kernel_dispatcher(request: Request):
    return _shared_get_kernel_dispatcher(request)


def _get_goal_service(request: Request):
    service = getattr(request.app.state, "goal_service", None)
    if service is None:
        raise HTTPException(503, detail="Goal service is not available")
    return service


def _get_environment_service(request: Request):
    service = getattr(request.app.state, "environment_service", None)
    if service is None:
        raise HTTPException(503, detail="Environment service is not available")
    return service


def _get_agent_profile_service(request: Request):
    service = getattr(request.app.state, "agent_profile_service", None)
    if service is None:
        raise HTTPException(503, detail="Agent profile service is not available")
    return service


def _get_agent_runtime_repository(request: Request):
    repository = getattr(request.app.state, "agent_runtime_repository", None)
    if repository is None:
        raise HTTPException(503, detail="Agent runtime repository is not available")
    return repository


def _get_agent_mailbox_repository(request: Request):
    repository = getattr(request.app.state, "agent_mailbox_repository", None)
    if repository is None:
        raise HTTPException(503, detail="Agent mailbox repository is not available")
    return repository


def _get_agent_checkpoint_repository(request: Request):
    repository = getattr(request.app.state, "agent_checkpoint_repository", None)
    if repository is None:
        raise HTTPException(503, detail="Agent checkpoint repository is not available")
    return repository


def _get_agent_lease_repository(request: Request):
    repository = getattr(request.app.state, "agent_lease_repository", None)
    if repository is None:
        raise HTTPException(503, detail="Agent lease repository is not available")
    return repository


def _get_agent_thread_binding_repository(request: Request):
    repository = getattr(request.app.state, "agent_thread_binding_repository", None)
    if repository is None:
        raise HTTPException(503, detail="Agent thread binding repository is not available")
    return repository


def _get_actor_mailbox_service(request: Request):
    service = getattr(request.app.state, "actor_mailbox_service", None)
    if service is None:
        raise HTTPException(503, detail="Actor mailbox service is not available")
    return service


def _get_actor_supervisor(request: Request):
    service = getattr(request.app.state, "actor_supervisor", None)
    if service is None:
        raise HTTPException(503, detail="Actor supervisor is not available")
    return service


def _get_knowledge_service(request: Request):
    service = getattr(request.app.state, "knowledge_service", None)
    if service is None or not all(
        callable(getattr(service, method_name, None))
        for method_name in (
            "list_chunks",
            "list_documents",
            "retrieve",
            "get_chunk",
            "upsert_chunk",
            "delete_chunk",
            "import_document",
            "remember_fact",
            "list_memory",
            "retrieve_memory",
        )
    ):
        raise HTTPException(503, detail="Knowledge service is not available")
    return service


def _get_strategy_memory_service(request: Request):
    service = getattr(request.app.state, "strategy_memory_service", None)
    if service is None or not callable(getattr(service, "list_strategies", None)):
        raise HTTPException(503, detail="Strategy memory service is not available")
    return service


def _get_derived_memory_index_service(request: Request):
    service = getattr(request.app.state, "derived_memory_index_service", None)
    if service is None or not all(
        callable(getattr(service, method_name, None))
        for method_name in (
            "list_fact_entries",
            "list_entity_views",
            "list_opinion_views",
            "list_reflection_runs",
            "rebuild_all",
        )
    ):
        raise HTTPException(503, detail="Derived memory index service is not available")
    return service


def _list_memory_relation_views(request: Request, **kwargs: object) -> list[object]:
    service = getattr(request.app.state, "derived_memory_index_service", None)
    list_relation_views = getattr(service, "list_relation_views", None)
    if callable(list_relation_views):
        return list(list_relation_views(**kwargs) or [])

    repository = getattr(request.app.state, "memory_relation_view_repository", None)
    list_views = getattr(repository, "list_views", None)
    if callable(list_views):
        return list(list_views(**kwargs) or [])

    return []


def _get_memory_recall_service(request: Request):
    service = getattr(request.app.state, "memory_recall_service", None)
    if service is None or not all(
        callable(getattr(service, method_name, None))
        for method_name in ("recall", "list_backends")
    ):
        raise HTTPException(503, detail="Memory recall service is not available")
    return service


def _get_memory_activation_service(request: Request):
    service = getattr(request.app.state, "memory_activation_service", None)
    if service is None or not callable(getattr(service, "activate_for_query", None)):
        raise HTTPException(503, detail="Memory activation service is not available")
    return service


def _get_memory_reflection_service(request: Request):
    service = getattr(request.app.state, "memory_reflection_service", None)
    if service is None or not all(
        callable(getattr(service, method_name, None))
        for method_name in ("reflect", "list_runs")
    ):
        raise HTTPException(503, detail="Memory reflection service is not available")
    return service


def _get_reporting_service(request: Request):
    service = getattr(request.app.state, "reporting_service", None)
    if service is None or not all(
        callable(getattr(service, method_name, None))
        for method_name in (
            "list_reports",
            "get_report",
            "get_performance_overview",
        )
    ):
        raise HTTPException(503, detail="Reporting service is not available")
    return service


def _get_industry_service(request: Request) -> IndustryService:
    service = getattr(request.app.state, "industry_service", None)
    if isinstance(service, IndustryService):
        return service
    raise HTTPException(503, detail="Industry service is not available")


def _get_runtime_conversation_facade(request: Request) -> RuntimeConversationFacade:
    reader = getattr(request.app.state, "runtime_thread_history_reader", None)
    if reader is None:
        session_backend = getattr(request.app.state, "session_backend", None)
        if session_backend is None:
            raise HTTPException(503, detail="Session backend is not available")
        reader = SessionRuntimeThreadHistoryReader(session_backend=session_backend)
    return RuntimeConversationFacade(
        history_reader=reader,
        industry_service=getattr(request.app.state, "industry_service", None),
        agent_profile_service=getattr(request.app.state, "agent_profile_service", None),
        agent_thread_binding_repository=getattr(
            request.app.state,
            "agent_thread_binding_repository",
            None,
        ),
        human_assist_task_service=getattr(
            request.app.state,
            "human_assist_task_service",
            None,
        ),
        work_context_repository=getattr(request.app.state, "work_context_repository", None),
    )


def _get_task_repository(request: Request):
    repository = getattr(request.app.state, "task_repository", None)
    if repository is None:
        raise HTTPException(503, detail="Task repository is not available")
    return repository


def _get_decision_request_repository(request: Request):
    repository = getattr(request.app.state, "decision_request_repository", None)
    if repository is None:
        raise HTTPException(503, detail="Decision request repository is not available")
    return repository


def _get_evidence_query_service(request: Request):
    service = getattr(request.app.state, "evidence_query_service", None)
    if service is None:
        raise HTTPException(503, detail="Evidence query service is not available")
    return service


def _get_cron_manager(request: Request):
    manager = getattr(request.app.state, "cron_manager", None)
    if manager is None:
        raise HTTPException(503, detail="Cron manager is not available")
    return manager


def _get_turn_executor(request: Request):
    turn_executor = getattr(request.app.state, "turn_executor", None)
    if turn_executor is None:
        raise HTTPException(503, detail="Kernel turn executor is not available")
    return turn_executor


def _get_human_assist_task_service(request: Request):
    service = getattr(request.app.state, "human_assist_task_service", None)
    if service is None:
        raise HTTPException(503, detail="Human assist task service is not available")
    return service


def _encode_sse_event(event: object) -> str:
    if hasattr(event, "model_dump_json"):
        payload = event.model_dump_json()
    elif hasattr(event, "json"):
        payload = event.json()
    else:
        payload = json.dumps(event, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _get_runtime_event_bus(request: Request):
    bus = getattr(request.app.state, "runtime_event_bus", None)
    if bus is None:
        raise HTTPException(503, detail="Runtime event bus is not available")
    return bus


def _get_governance_service(request: Request):
    service = getattr(request.app.state, "governance_service", None)
    if service is None:
        raise HTTPException(503, detail="Governance service is not available")
    return service


def _get_capability_service(request: Request):
    return _shared_get_capability_service(request)


def _get_prediction_service(request: Request):
    service = getattr(request.app.state, "prediction_service", None)
    if service is None or not callable(
        getattr(service, "get_runtime_capability_optimization_overview", None),
    ):
        raise HTTPException(503, detail="Prediction service is not available")
    return service


async def _call_runtime_query_method(
    target: object,
    *method_names: str,
    not_available_detail: str,
    **kwargs,
):
    for method_name in method_names:
        method = getattr(target, method_name, None)
        if not callable(method):
            continue
        result = method(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result
    raise HTTPException(503, detail=not_available_detail)


def _raise_dispatcher_error(exc: Exception) -> None:
    translate_dispatcher_error(exc)


def _get_runtime_center_facade_attr(name: str, default: object) -> object:
    facade = sys.modules.get("copaw.app.routers.runtime_center")
    if facade is None:
        return default
    return getattr(facade, name, default)


async def _dispatch_runtime_mutation(
    request: Request,
    *,
    capability_ref: str,
    title: str,
    payload: dict[str, object],
    fallback_risk: str = "guarded",
    risk_level_override: str | None = None,
) -> dict[str, object]:
    return await dispatch_governed_mutation(
        request,
        capability_ref=capability_ref,
        title=title,
        payload=payload,
        environment_ref="config:runtime",
        fallback_risk=fallback_risk,
        risk_level_override=risk_level_override,
    )


def _model_dump_or_dict(value: object | None) -> dict[str, object] | None:
    if value is None:
        return None
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    return None


def _public_agent_payload(value: object | None) -> dict[str, object] | None:
    payload = _model_dump_or_dict(value)
    if payload is None:
        return None
    payload.pop("current_goal_id", None)
    payload.pop("current_goal", None)
    return payload


def _public_agent_detail_payload(value: object | None) -> dict[str, object] | None:
    payload = _model_dump_or_dict(value)
    if payload is None:
        return None
    agent_payload = _public_agent_payload(payload.get("agent"))
    if agent_payload is not None:
        payload["agent"] = agent_payload
    return payload


def _runtime_non_empty_str(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    resolved = value.strip()
    return resolved or None


def _actor_runtime_payload(runtime: object) -> dict[str, object]:
    payload = _model_dump_or_dict(runtime)
    if payload is None:
        raise HTTPException(500, detail="Actor runtime payload is not serializable")
    agent_id = str(payload.get("agent_id") or "")
    if agent_id:
        payload["routes"] = {
            "detail": f"/api/runtime-center/actors/{agent_id}",
            "mailbox": f"/api/runtime-center/actors/{agent_id}/mailbox",
            "checkpoints": f"/api/runtime-center/actors/{agent_id}/checkpoints",
            "leases": f"/api/runtime-center/actors/{agent_id}/leases",
            "teammates": f"/api/runtime-center/actors/{agent_id}/teammates",
            "capabilities": f"/api/runtime-center/actors/{agent_id}/capabilities",
            "governed_capabilities": f"/api/runtime-center/actors/{agent_id}/capabilities/governed",
            "agent_capabilities": f"/api/runtime-center/agents/{agent_id}/capabilities",
        }
    return payload


def _actor_mailbox_payload(item: object) -> dict[str, object]:
    payload = _model_dump_or_dict(item)
    if payload is None:
        raise HTTPException(500, detail="Actor mailbox payload is not serializable")
    agent_id = str(payload.get("agent_id") or "")
    item_id = str(payload.get("id") or "")
    if agent_id and item_id:
        payload["route"] = f"/api/runtime-center/actors/{agent_id}/mailbox/{item_id}"
    return payload


def _resolve_actor_focus_task_id(
    runtime: object,
    *,
    mailbox_items: list[object],
    checkpoints: list[object],
) -> str | None:
    current_task_id = _runtime_non_empty_str(getattr(runtime, "current_task_id", None))
    if current_task_id is not None:
        return current_task_id

    current_mailbox_id = _runtime_non_empty_str(getattr(runtime, "current_mailbox_id", None))
    for item in mailbox_items:
        status = _runtime_non_empty_str(getattr(item, "status", None))
        task_id = _runtime_non_empty_str(getattr(item, "task_id", None))
        item_id = _runtime_non_empty_str(getattr(item, "id", None))
        if (
            current_mailbox_id is not None
            and item_id == current_mailbox_id
            and status in _ACTIVE_ACTOR_MAILBOX_STATUSES
            and task_id is not None
        ):
            return task_id

    for item in mailbox_items:
        status = _runtime_non_empty_str(getattr(item, "status", None))
        task_id = _runtime_non_empty_str(getattr(item, "task_id", None))
        if status in _ACTIVE_ACTOR_MAILBOX_STATUSES and task_id is not None:
            return task_id

    current_checkpoint_id = _runtime_non_empty_str(getattr(runtime, "last_checkpoint_id", None))
    for checkpoint in checkpoints:
        status = _runtime_non_empty_str(getattr(checkpoint, "status", None))
        task_id = _runtime_non_empty_str(getattr(checkpoint, "task_id", None))
        checkpoint_id = _runtime_non_empty_str(getattr(checkpoint, "id", None))
        if (
            current_checkpoint_id is not None
            and checkpoint_id == current_checkpoint_id
            and status in _ACTIVE_ACTOR_CHECKPOINT_STATUSES
            and task_id is not None
        ):
            return task_id

    for checkpoint in checkpoints:
        status = _runtime_non_empty_str(getattr(checkpoint, "status", None))
        task_id = _runtime_non_empty_str(getattr(checkpoint, "task_id", None))
        if status in _ACTIVE_ACTOR_CHECKPOINT_STATUSES and task_id is not None:
            return task_id
    return None


async def _get_actor_focus_payload(
    request: Request,
    *,
    runtime: object,
    mailbox_items: list[object],
    checkpoints: list[object],
) -> dict[str, object] | None:
    task_id = _resolve_actor_focus_task_id(
        runtime,
        mailbox_items=mailbox_items,
        checkpoints=checkpoints,
    )
    if task_id is None:
        return None
    payload: dict[str, object] = {
        "task_id": task_id,
        "route": f"/api/runtime-center/tasks/{task_id}/review",
        "review": None,
    }
    state_query = getattr(request.app.state, "state_query_service", None)
    getter = getattr(state_query, "get_task_review", None)
    if not callable(getter):
        return payload
    try:
        result = getter(task_id)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        logger.exception("Failed to resolve actor focus review for '%s'", task_id)
        return payload
    if not isinstance(result, dict):
        return payload
    review = result.get("review")
    if isinstance(review, dict):
        payload["review"] = review
    route = _runtime_non_empty_str(result.get("route"))
    if route is not None:
        payload["route"] = route
    return payload


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
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.exception(
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


def _serialize_knowledge_chunk(chunk: object) -> dict[str, object]:
    payload = _model_dump_or_dict(chunk)
    if payload is None:
        raise HTTPException(500, detail="Knowledge payload is not serializable")
    payload["route"] = f"/api/runtime-center/knowledge/{payload['id']}"
    memory_scope = _describe_memory_scope_from_service(chunk)
    if memory_scope is not None:
        payload.update(memory_scope)
    return payload


def _describe_memory_scope_from_service(chunk: object) -> dict[str, object] | None:
    document_id = None
    if isinstance(chunk, dict):
        document_id = chunk.get("document_id")
    else:
        document_id = getattr(chunk, "document_id", None)
    if not isinstance(document_id, str) or not document_id:
        return None
    if not document_id.startswith("memory:"):
        return None
    remainder = document_id[len("memory:") :]
    scope_type, separator, scope_id = remainder.partition(":")
    if not separator or not scope_type or not scope_id:
        return None
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
    }


def _get_learning_service(request: Request):
    service = getattr(request.app.state, "learning_service", None)
    if service is not None and any(
        callable(getattr(service, method_name, None))
        for method_name in ("list_patches", "list_proposals", "list_growth", "get_growth_history")
    ):
        return service
    raise HTTPException(503, detail="Learning service is not available")


def _build_patch_actions(patch_id: str, status: str, risk_level: str) -> dict[str, str]:
    return build_patch_actions(
        patch_id,
        status=status,
        risk_level=risk_level,
    )


def _heartbeat_route() -> str:
    return "/api/runtime-center/heartbeat"


def _serialize_timestamp(value: object) -> str | None:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return None


def _serialize_heartbeat_surface(request: Request) -> dict[str, object]:
    manager = _get_cron_manager(request)
    heartbeat_getter = _get_runtime_center_facade_attr(
        "get_heartbeat_config",
        get_heartbeat_config,
    )
    heartbeat = heartbeat_getter()
    heartbeat_payload = heartbeat.model_dump(mode="json", by_alias=True)
    state_getter = getattr(manager, "get_heartbeat_state", None)
    state = state_getter() if callable(state_getter) else None
    last_status = str(getattr(state, "last_status", None) or "")
    route = _heartbeat_route()
    return {
        "heartbeat": heartbeat_payload,
        "runtime": {
            "status": "paused" if not heartbeat.enabled else (last_status or "scheduled"),
            "enabled": heartbeat.enabled,
            "every": heartbeat.every,
            "target": heartbeat.target,
            "activeHours": heartbeat_payload.get("activeHours"),
            "last_run_at": _serialize_timestamp(getattr(state, "last_run_at", None)),
            "next_run_at": _serialize_timestamp(getattr(state, "next_run_at", None)),
            "last_error": getattr(state, "last_error", None),
            "query_path": "system:run_operating_cycle",
        },
        "route": route,
        "actions": {
            "update": route,
            "run": f"{route}/run",
        },
    }


def _maybe_publish_runtime_event(
    request: Request,
    *,
    topic: str,
    action: str,
    payload: dict[str, object] | None = None,
) -> None:
    bus = getattr(request.app.state, "runtime_event_bus", None)
    if bus is None or not callable(getattr(bus, "publish", None)):
        return
    bus.publish(topic=topic, action=action, payload=payload)


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



__all__ = [name for name in globals() if not name.startswith("__")]
