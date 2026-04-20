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
    build_memory_sleep_model_runner,
    MemorySleepInferenceService,
    MemorySleepService,
)
from ..state.agent_experience_service import AgentExperienceMemoryService
from ..state.knowledge_service import StateKnowledgeService
from ..state.strategy_memory_service import StateStrategyMemoryService
from .runtime_bootstrap_models import (
    RuntimeRepositories,
    SurfaceCapabilityTwinSummary,
    SurfaceLearningBootstrapProjection,
    SurfacePlaybookSummary,
)
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
    MemorySleepService,
    Any | None,
    AgentExperienceMemoryService,
]


def build_surface_learning_bootstrap_projection(
    *,
    repositories: RuntimeRepositories,
    scope_level: str,
    scope_id: str,
    twin_limit: int | None = 5,
) -> SurfaceLearningBootstrapProjection | None:
    twin_repository = getattr(repositories, "surface_capability_twin_repository", None)
    playbook_repository = getattr(repositories, "surface_playbook_repository", None)
    if twin_repository is None and playbook_repository is None:
        return None
    active_twins = (
        twin_repository.get_active_twins(
            scope_level=scope_level,
            scope_id=scope_id,
            limit=twin_limit,
        )
        if twin_repository is not None
        else []
    )
    active_playbook = (
        playbook_repository.get_active_playbook(
            scope_level=scope_level,
            scope_id=scope_id,
        )
        if playbook_repository is not None
        else None
    )
    if not active_twins and active_playbook is None:
        return None
    version_candidates = [record.version for record in active_twins]
    updated_candidates = [
        record.updated_at
        for record in active_twins
        if record.updated_at is not None
    ]
    if active_playbook is not None:
        version_candidates.append(active_playbook.version)
        if active_playbook.updated_at is not None:
            updated_candidates.append(active_playbook.updated_at)
    return SurfaceLearningBootstrapProjection(
        scope_level=scope_level,
        scope_id=scope_id,
        version=max(version_candidates) if version_candidates else None,
        updated_at=max(updated_candidates) if updated_candidates else None,
        active_twins=[
            SurfaceCapabilityTwinSummary(
                twin_id=record.twin_id,
                capability_name=record.capability_name,
                capability_kind=record.capability_kind,
                surface_kind=record.surface_kind,
                summary=record.summary,
                risk_level=record.risk_level,
                version=record.version,
                updated_at=record.updated_at,
            )
            for record in active_twins
        ],
        active_playbook=(
            SurfacePlaybookSummary(
                playbook_id=active_playbook.playbook_id,
                twin_id=active_playbook.twin_id,
                summary=active_playbook.summary,
                capability_names=list(active_playbook.capability_names),
                recommended_steps=list(active_playbook.recommended_steps),
                execution_steps=list(active_playbook.execution_steps),
                success_signals=list(active_playbook.success_signals),
                version=active_playbook.version,
                updated_at=active_playbook.updated_at,
            )
            if active_playbook is not None
            else None
        ),
    )


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
    if explicit_backend == "truth-first":
        return explicit_backend
    return "truth-first"


def build_runtime_query_services(
    *,
    repositories: RuntimeRepositories,
    evidence_ledger: EvidenceLedger,
    runtime_event_bus: RuntimeEventBus,
    donor_source_service: object | None = None,
    capability_candidate_service: object | None = None,
    capability_donor_service: object | None = None,
    donor_package_service: object | None = None,
    donor_trust_service: object | None = None,
    capability_portfolio_service: object | None = None,
    donor_scout_service: object | None = None,
    skill_trial_service: object | None = None,
    skill_lifecycle_decision_service: object | None = None,
    human_assist_task_service: object | None = None,
    environment_service: EnvironmentService | None = None,
    external_runtime_service: object | None = None,
    weixin_ilink_runtime_state: object | None = None,
    runtime_provider: object | None = None,
) -> RuntimeQueryServices:
    default_recall_backend = resolve_default_memory_recall_backend()
    state_query_service = RuntimeCenterStateQueryService(
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        runtime_frame_repository=repositories.runtime_frame_repository,
        schedule_repository=repositories.schedule_repository,
        backlog_item_repository=repositories.backlog_item_repository,
        assignment_repository=repositories.assignment_repository,
        agent_report_repository=repositories.agent_report_repository,
        goal_repository=repositories.goal_repository,
        work_context_repository=repositories.work_context_repository,
        decision_request_repository=repositories.decision_request_repository,
        donor_source_service=donor_source_service,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        donor_package_service=donor_package_service,
        donor_trust_service=donor_trust_service,
        capability_portfolio_service=capability_portfolio_service,
        donor_scout_service=donor_scout_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        evidence_ledger=evidence_ledger,
        human_assist_task_service=human_assist_task_service,
        environment_service=environment_service,
        external_runtime_service=external_runtime_service,
        weixin_ilink_runtime_state=weixin_ilink_runtime_state,
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
    memory_sleep_service = MemorySleepService(
        repository=repositories.memory_sleep_repository,
        knowledge_service=knowledge_service,
        strategy_memory_service=strategy_memory_service,
        derived_index_service=derived_memory_index_service,
        reflection_service=memory_reflection_service,
        inference_service=MemorySleepInferenceService(
            model_runner=build_memory_sleep_model_runner(
                model_factory=(
                    getattr(runtime_provider, "get_active_chat_model", None)
                    if runtime_provider is not None
                    else None
                ),
            ),
        ),
    )
    knowledge_service.set_memory_sleep_service(memory_sleep_service)
    strategy_memory_service.set_memory_sleep_service(memory_sleep_service)
    memory_retain_service.set_memory_sleep_service(memory_sleep_service)
    memory_recall_service.set_memory_sleep_service(memory_sleep_service)
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
        memory_sleep_service,
        memory_activation_service,
        experience_memory_service,
    )
