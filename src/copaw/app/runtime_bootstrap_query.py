# -*- coding: utf-8 -*-
from __future__ import annotations

from importlib import import_module
import os
from typing import Any, TypeAlias

from ..evidence import EvidenceLedger
from ..environments import EnvironmentService
from ..memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
)
from ..state.agent_experience_service import AgentExperienceMemoryService
from ..state.knowledge_service import StateKnowledgeService
from ..state.strategy_memory_service import StateStrategyMemoryService
from .runtime_bootstrap_models import RuntimeRepositories
from .runtime_center import (
    RuntimeCenterEvidenceQueryService,
    RuntimeCenterStateQueryService,
)
from .runtime_events import RuntimeEventBus

RuntimeQueryServices: TypeAlias = tuple[
    RuntimeCenterStateQueryService,
    RuntimeCenterEvidenceQueryService,
    StateStrategyMemoryService,
    StateKnowledgeService,
    DerivedMemoryIndexService,
    MemoryReflectionService,
    MemoryRecallService,
    MemoryRetainService,
    Any | None,
    AgentExperienceMemoryService,
]


def _resolve_memory_activation_service_cls() -> type[Any] | None:
    try:
        module = import_module("copaw.memory.activation_service")
    except ImportError:
        return None
    activation_service_cls = getattr(module, "MemoryActivationService", None)
    if not callable(activation_service_cls):
        return None
    return activation_service_cls


def resolve_default_memory_recall_backend() -> str:
    explicit_backend = str(os.environ.get("COPAW_MEMORY_RECALL_BACKEND", "") or "").strip().lower()
    if explicit_backend in {"lexical", "hybrid-local"}:
        return explicit_backend
    return "hybrid-local"


def build_runtime_query_services(
    *,
    repositories: RuntimeRepositories,
    evidence_ledger: EvidenceLedger,
    runtime_event_bus: RuntimeEventBus,
    capability_candidate_service: object | None = None,
    capability_donor_service: object | None = None,
    capability_portfolio_service: object | None = None,
    skill_trial_service: object | None = None,
    skill_lifecycle_decision_service: object | None = None,
    human_assist_task_service: object | None = None,
    environment_service: EnvironmentService | None = None,
) -> RuntimeQueryServices:
    default_recall_backend = resolve_default_memory_recall_backend()
    state_query_service = RuntimeCenterStateQueryService(
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        runtime_frame_repository=repositories.runtime_frame_repository,
        schedule_repository=repositories.schedule_repository,
        goal_repository=repositories.goal_repository,
        work_context_repository=repositories.work_context_repository,
        decision_request_repository=repositories.decision_request_repository,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        capability_portfolio_service=capability_portfolio_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        evidence_ledger=evidence_ledger,
        human_assist_task_service=human_assist_task_service,
        environment_service=environment_service,
        memory_activation_service=None,
    )
    evidence_query_service = RuntimeCenterEvidenceQueryService(
        evidence_ledger=evidence_ledger,
    )
    derived_memory_index_service = DerivedMemoryIndexService(
        fact_index_repository=repositories.memory_fact_index_repository,
        entity_view_repository=repositories.memory_entity_view_repository,
        opinion_view_repository=repositories.memory_opinion_view_repository,
        relation_view_repository=getattr(
            repositories,
            "memory_relation_view_repository",
            None,
        ),
        reflection_run_repository=repositories.memory_reflection_run_repository,
        knowledge_repository=repositories.knowledge_chunk_repository,
        strategy_repository=repositories.strategy_memory_repository,
        agent_report_repository=repositories.agent_report_repository,
        routine_repository=repositories.routine_repository,
        routine_run_repository=repositories.routine_run_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        evidence_ledger=evidence_ledger,
        sidecar_backends=[],
    )
    memory_reflection_service = MemoryReflectionService(
        derived_index_service=derived_memory_index_service,
        entity_view_repository=repositories.memory_entity_view_repository,
        opinion_view_repository=repositories.memory_opinion_view_repository,
        reflection_run_repository=repositories.memory_reflection_run_repository,
    )
    memory_recall_service = MemoryRecallService(
        derived_index_service=derived_memory_index_service,
        default_backend=default_recall_backend,
        sidecar_backends=[],
    )
    strategy_memory_service = StateStrategyMemoryService(
        repository=repositories.strategy_memory_repository,
        derived_index_service=derived_memory_index_service,
        reflection_service=memory_reflection_service,
    )
    knowledge_service = StateKnowledgeService(
        repository=repositories.knowledge_chunk_repository,
        derived_index_service=derived_memory_index_service,
        reflection_service=memory_reflection_service,
    )
    memory_retain_service = MemoryRetainService(
        knowledge_service=knowledge_service,
        derived_index_service=derived_memory_index_service,
        reflection_service=memory_reflection_service,
    )
    memory_activation_service = None
    memory_activation_service_cls = _resolve_memory_activation_service_cls()
    if memory_activation_service_cls is not None:
        memory_activation_service = memory_activation_service_cls(
            derived_index_service=derived_memory_index_service,
            strategy_memory_service=strategy_memory_service,
        )
        state_query_service._memory_activation_service = memory_activation_service
    experience_memory_service = AgentExperienceMemoryService(
        knowledge_service=knowledge_service,
    )
    return (
        state_query_service,
        evidence_query_service,
        strategy_memory_service,
        knowledge_service,
        derived_memory_index_service,
        memory_reflection_service,
        memory_recall_service,
        memory_retain_service,
        memory_activation_service,
        experience_memory_service,
    )
