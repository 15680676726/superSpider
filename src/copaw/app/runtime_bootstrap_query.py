# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import TypeAlias

from ..evidence import EvidenceLedger
from ..environments import EnvironmentService
from ..memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
    QmdBackendConfig,
    QmdRecallBackend,
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
    AgentExperienceMemoryService,
]


def resolve_default_memory_recall_backend(*, qmd_backend: QmdRecallBackend) -> str:
    explicit_backend = str(os.environ.get("COPAW_MEMORY_RECALL_BACKEND", "") or "").strip().lower()
    if explicit_backend:
        return explicit_backend
    return "hybrid-local"


def build_runtime_query_services(
    *,
    repositories: RuntimeRepositories,
    evidence_ledger: EvidenceLedger,
    runtime_event_bus: RuntimeEventBus,
    human_assist_task_service: object | None = None,
    environment_service: EnvironmentService | None = None,
) -> RuntimeQueryServices:
    qmd_backend = QmdRecallBackend(config=QmdBackendConfig.from_env())
    default_recall_backend = resolve_default_memory_recall_backend(
        qmd_backend=qmd_backend,
    )
    state_query_service = RuntimeCenterStateQueryService(
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        runtime_frame_repository=repositories.runtime_frame_repository,
        schedule_repository=repositories.schedule_repository,
        goal_repository=repositories.goal_repository,
        work_context_repository=repositories.work_context_repository,
        decision_request_repository=repositories.decision_request_repository,
        evidence_ledger=evidence_ledger,
        human_assist_task_service=human_assist_task_service,
        runtime_event_bus=runtime_event_bus,
        environment_service=environment_service,
    )
    evidence_query_service = RuntimeCenterEvidenceQueryService(
        evidence_ledger=evidence_ledger,
    )
    derived_memory_index_service = DerivedMemoryIndexService(
        fact_index_repository=repositories.memory_fact_index_repository,
        entity_view_repository=repositories.memory_entity_view_repository,
        opinion_view_repository=repositories.memory_opinion_view_repository,
        reflection_run_repository=repositories.memory_reflection_run_repository,
        knowledge_repository=repositories.knowledge_chunk_repository,
        strategy_repository=repositories.strategy_memory_repository,
        agent_report_repository=repositories.agent_report_repository,
        routine_repository=repositories.routine_repository,
        routine_run_repository=repositories.routine_run_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        evidence_ledger=evidence_ledger,
        sidecar_backends=[qmd_backend],
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
        sidecar_backends=[qmd_backend],
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
        experience_memory_service,
    )
