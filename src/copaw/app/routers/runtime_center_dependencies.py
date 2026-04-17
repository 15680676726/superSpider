# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import HTTPException, Request

from ..runtime_center import RuntimeConversationFacade
from ..runtime_threads import SessionRuntimeThreadHistoryReader
from ...industry import IndustryService
from .governed_mutations import (
    get_capability_service as _shared_get_capability_service,
    get_kernel_dispatcher as _shared_get_kernel_dispatcher,
)


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


def _get_memory_sleep_service(request: Request):
    service = getattr(request.app.state, "memory_sleep_service", None)
    if service is None or not all(
        callable(getattr(service, method_name, None))
        for method_name in (
            "run_sleep",
            "resolve_scope_overlay",
            "list_scope_states",
            "list_sleep_jobs",
            "list_digests",
            "list_soft_rules",
            "list_conflict_proposals",
        )
    ):
        raise HTTPException(503, detail="Memory sleep service is not available")
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


def _get_research_session_repository(request: Request):
    repository = getattr(request.app.state, "research_session_repository", None)
    if repository is None:
        raise HTTPException(503, detail="Research session repository is not available")
    return repository


def _get_research_session_service(request: Request):
    service = getattr(request.app.state, "research_session_service", None)
    if service is None:
        raise HTTPException(503, detail="Research session service is not available")
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
    service = getattr(request.app.state, "turn_executor", None)
    if service is None:
        raise HTTPException(503, detail="Turn executor is not available")
    return service


def _get_human_assist_task_service(request: Request):
    service = getattr(request.app.state, "human_assist_task_service", None)
    if service is None:
        raise HTTPException(503, detail="Human assist task service is not available")
    return service


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


def _get_learning_service(request: Request):
    service = getattr(request.app.state, "learning_service", None)
    if service is not None and any(
        callable(getattr(service, method_name, None))
        for method_name in (
            "list_patches",
            "list_proposals",
            "list_growth",
            "get_growth_history",
            "finalize_resolved_decision",
        )
    ):
        return service
    raise HTTPException(503, detail="Learning service is not available")


__all__ = [name for name in globals() if not name.startswith("__")]
