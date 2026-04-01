# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from ..capabilities import CapabilityService
from ..constant import WORKING_DIR
from ..evidence import EvidenceLedger
from ..environments import EnvironmentRegistry, EnvironmentService
from ..goals import GoalService
from ..industry import IndustryDraftGenerator, IndustryService
from ..kernel import (
    ActorMailboxService,
    ActorSupervisor,
    ActorWorker,
    AgentProfileService,
    GovernanceService,
    KernelDispatcher,
    MainBrainChatService,
    MainBrainOrchestrator,
    KernelQueryExecutionService,
    KernelTaskStore,
    KernelToolBridge,
    KernelTurnExecutor,
    TaskDelegationService,
)
from ..learning import LearningService, PatchExecutor
from ..media import MediaService
from ..memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
)
from ..predictions import PredictionService
from ..providers.provider_manager import ProviderManager
from ..routines import RoutineService
from ..sop_kernel import FixedSopService
from ..state import SQLiteStateStore
from ..state.human_assist_task_service import HumanAssistTaskService
from ..state.main_brain_service import (
    AgentReportService,
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from ..state.agent_experience_service import AgentExperienceMemoryService
from ..state.knowledge_service import StateKnowledgeService
from ..state.reporting_service import StateReportingService
from ..state.strategy_memory_service import StateStrategyMemoryService
from ..state.work_context_service import WorkContextService
from ..state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentLeaseRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentReportRepository,
    SqliteAgentRuntimeRepository,
    SqliteAssignmentRepository,
    SqliteAgentThreadBindingRepository,
    SqliteBacklogItemRepository,
    SqliteCapabilityOverrideRepository,
    SqliteDecisionRequestRepository,
    SqliteExecutionRoutineRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteGovernanceControlRepository,
    SqliteIndustryInstanceRepository,
    SqliteMediaAnalysisRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteOperatingCycleRepository,
    SqliteOperatingLaneRepository,
    SqlitePredictionCaseRepository,
    SqlitePredictionRecommendationRepository,
    SqlitePredictionReviewRepository,
    SqlitePredictionScenarioRepository,
    SqlitePredictionSignalRepository,
    SqliteRoutineRunRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteStrategyMemoryRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
    SqliteWorkflowPresetRepository,
    SqliteWorkflowRunRepository,
    SqliteWorkflowTemplateRepository,
)
from ..workflows import WorkflowTemplateService
from .mcp import MCPClientManager
from .runtime_bootstrap_execution import (
    build_runtime_execution_stack as build_runtime_execution_stack_components,
)
from .runtime_bootstrap_domains import build_runtime_domain_services
from .runtime_bootstrap_models import RuntimeBootstrap, RuntimeRepositories
from .runtime_bootstrap_observability import (
    build_runtime_observability as build_runtime_observability_components,
)
from .runtime_bootstrap_query import (
    build_runtime_query_services as build_runtime_query_services_components,
    resolve_default_memory_recall_backend,
)
from .runtime_bootstrap_repositories import (
    build_runtime_repositories as build_runtime_repositories_from_state_store,
)
from .runtime_center import (
    RuntimeCenterEvidenceQueryService,
    RuntimeCenterStateQueryService,
)
from .runtime_events import RuntimeEventBus
from .runtime_health_service import RuntimeHealthService
from .runtime_threads import SessionRuntimeThreadHistoryReader


async def initialize_mcp_manager(
    *,
    config: Any,
    logger: logging.Logger,
    strict: bool,
    timeout: float = 60.0,
) -> MCPClientManager:
    mcp_manager = MCPClientManager()
    if not hasattr(config, "mcp"):
        return mcp_manager
    try:
        await mcp_manager.init_from_config(
            config.mcp,
            strict=strict,
            timeout=timeout,
        )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if strict:
            raise
        logger.exception("Failed to initialize MCP manager")
    else:
        logger.debug("MCP client manager initialized")
    return mcp_manager


def _resolve_default_memory_recall_backend() -> str:
    return resolve_default_memory_recall_backend()


def build_runtime_repositories(state_store: SQLiteStateStore) -> RuntimeRepositories:
    return build_runtime_repositories_from_state_store(state_store)


def _resolve_state_store() -> SQLiteStateStore:
    return SQLiteStateStore(WORKING_DIR / "state" / "phase1.sqlite3")


def _resolve_provider_manager() -> ProviderManager:
    return ProviderManager.get_instance()


def _build_runtime_observability(
    *,
    state_store: SQLiteStateStore,
    repositories: RuntimeRepositories,
) -> tuple[EvidenceLedger, EnvironmentRegistry, EnvironmentService, RuntimeEventBus]:
    return build_runtime_observability_components(
        state_store=state_store,
        repositories=repositories,
    )


def _build_query_services(
    *,
    repositories: RuntimeRepositories,
    evidence_ledger: EvidenceLedger,
    runtime_event_bus: RuntimeEventBus,
    human_assist_task_service: HumanAssistTaskService | None,
    environment_service: EnvironmentService,
) -> tuple[
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
]:
    return build_runtime_query_services_components(
        repositories=repositories,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=runtime_event_bus,
        human_assist_task_service=human_assist_task_service,
        environment_service=environment_service,
    )


def _build_kernel_runtime(
    *,
    mcp_manager: MCPClientManager,
    environment_service: EnvironmentService,
    evidence_ledger: EvidenceLedger,
    repositories: RuntimeRepositories,
    runtime_event_bus: RuntimeEventBus,
    state_query_service: RuntimeCenterStateQueryService,
    conversation_compaction_service: object | None,
    experience_memory_service: AgentExperienceMemoryService | None,
    state_store: SQLiteStateStore,
    work_context_service: WorkContextService,
) -> tuple[
    LearningService,
    GovernanceService,
    KernelTaskStore,
    KernelToolBridge,
    CapabilityService,
    KernelDispatcher,
    ActorMailboxService,
    ActorWorker,
    ActorSupervisor,
]:
    return build_runtime_execution_stack_components(
        mcp_manager=mcp_manager,
        environment_service=environment_service,
        evidence_ledger=evidence_ledger,
        repositories=repositories,
        runtime_event_bus=runtime_event_bus,
        state_query_service=state_query_service,
        conversation_compaction_service=conversation_compaction_service,
        experience_memory_service=experience_memory_service,
        state_store=state_store,
        work_context_service=work_context_service,
        patch_executor_cls=PatchExecutor,
        learning_service_cls=LearningService,
        governance_service_cls=GovernanceService,
        kernel_task_store_cls=KernelTaskStore,
        kernel_tool_bridge_cls=KernelToolBridge,
        capability_service_cls=CapabilityService,
        kernel_dispatcher_cls=KernelDispatcher,
        actor_mailbox_service_cls=ActorMailboxService,
        actor_worker_cls=ActorWorker,
        actor_supervisor_cls=ActorSupervisor,
    )


def _warm_runtime_memory_services(
    *,
    repositories: RuntimeRepositories,
    derived_memory_index_service: DerivedMemoryIndexService,
    memory_recall_service: MemoryRecallService,
    memory_reflection_service: MemoryReflectionService,
) -> None:
    derived_memory_index_service.rebuild_all()
    try:
        memory_recall_service.prepare_sidecar_backends(
            prewarm_backend_ids=[],
        )
    except Exception:
        pass
    try:
        memory_reflection_service.reflect(
            scope_type="global",
            scope_id="runtime",
            trigger_kind="startup",
            create_learning_proposals=False,
        )
        for instance in repositories.industry_instance_repository.list_instances(limit=None):
            memory_reflection_service.reflect(
                scope_type="industry",
                scope_id=instance.instance_id,
                industry_instance_id=instance.instance_id,
                trigger_kind="startup",
                create_learning_proposals=False,
            )
    except Exception:
        pass


def build_runtime_bootstrap(
    *,
    session_backend: Any,
    conversation_compaction_service: Any,
    mcp_manager: MCPClientManager,
) -> RuntimeBootstrap:
    runtime_thread_history_reader = SessionRuntimeThreadHistoryReader(
        session_backend=session_backend,
    )
    state_store = _resolve_state_store()
    repositories = build_runtime_repositories(state_store)
    (
        evidence_ledger,
        environment_registry,
        environment_service,
        runtime_event_bus,
    ) = _build_runtime_observability(
        state_store=state_store,
        repositories=repositories,
    )
    human_assist_task_service = HumanAssistTaskService(
        repository=repositories.human_assist_task_repository,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=runtime_event_bus,
    )

    provider_manager = _resolve_provider_manager()
    (
        state_query_service,
        evidence_query_service,
        strategy_memory_service,
        knowledge_service,
        derived_memory_index_service,
        memory_reflection_service,
        memory_recall_service,
        memory_retain_service,
        memory_activation_service,
        agent_experience_service,
    ) = _build_query_services(
        repositories=repositories,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=runtime_event_bus,
        human_assist_task_service=human_assist_task_service,
        environment_service=environment_service,
    )
    work_context_service = WorkContextService(
        repository=repositories.work_context_repository,
    )
    (
        learning_service,
        governance_service,
        kernel_task_store,
        kernel_tool_bridge,
        capability_service,
        kernel_dispatcher,
        actor_mailbox_service,
        actor_worker,
        actor_supervisor,
    ) = _build_kernel_runtime(
        mcp_manager=mcp_manager,
        environment_service=environment_service,
        evidence_ledger=evidence_ledger,
        repositories=repositories,
        runtime_event_bus=runtime_event_bus,
        state_query_service=state_query_service,
        conversation_compaction_service=conversation_compaction_service,
        experience_memory_service=agent_experience_service,
        state_store=state_store,
        work_context_service=work_context_service,
    )

    domain_services = build_runtime_domain_services(
        session_backend=session_backend,
        conversation_compaction_service=conversation_compaction_service,
        mcp_manager=mcp_manager,
        state_store=state_store,
        repositories=repositories,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        runtime_event_bus=runtime_event_bus,
        provider_manager=provider_manager,
        state_query_service=state_query_service,
        strategy_memory_service=strategy_memory_service,
        knowledge_service=knowledge_service,
        derived_memory_index_service=derived_memory_index_service,
        memory_reflection_service=memory_reflection_service,
        memory_recall_service=memory_recall_service,
        memory_retain_service=memory_retain_service,
        memory_activation_service=memory_activation_service,
        agent_experience_service=agent_experience_service,
        work_context_service=work_context_service,
        learning_service=learning_service,
        capability_service=capability_service,
        kernel_dispatcher=kernel_dispatcher,
        kernel_tool_bridge=kernel_tool_bridge,
        actor_mailbox_service=actor_mailbox_service,
        actor_supervisor=actor_supervisor,
    )
    goal_service = domain_services.goal_service
    agent_profile_service = domain_services.agent_profile_service
    reporting_service = domain_services.reporting_service
    operating_lane_service = domain_services.operating_lane_service
    backlog_service = domain_services.backlog_service
    operating_cycle_service = domain_services.operating_cycle_service
    assignment_service = domain_services.assignment_service
    agent_report_service = domain_services.agent_report_service
    media_service = domain_services.media_service
    industry_service = domain_services.industry_service
    workflow_template_service = domain_services.workflow_template_service
    fixed_sop_service = domain_services.fixed_sop_service
    routine_service = domain_services.routine_service
    prediction_service = domain_services.prediction_service
    delegation_service = domain_services.delegation_service
    query_execution_service = domain_services.query_execution_service
    main_brain_chat_service = domain_services.main_brain_chat_service
    main_brain_orchestrator = domain_services.main_brain_orchestrator
    governance_service.set_environment_service(environment_service)
    governance_service.set_human_assist_task_service(human_assist_task_service)
    governance_service.set_industry_service(industry_service)
    _warm_runtime_memory_services(
        repositories=repositories,
        derived_memory_index_service=derived_memory_index_service,
        memory_recall_service=memory_recall_service,
        memory_reflection_service=memory_reflection_service,
    )
    turn_executor = KernelTurnExecutor(
        session_backend=session_backend,
        conversation_compaction_service=conversation_compaction_service,
        mcp_manager=mcp_manager,
        kernel_dispatcher=kernel_dispatcher,
        tool_bridge=kernel_tool_bridge,
        environment_service=environment_service,
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    capability_service.set_turn_executor(turn_executor)
    runtime_health_service = RuntimeHealthService(
        state_store=state_store,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        capability_service=capability_service,
        kernel_dispatcher=kernel_dispatcher,
        governance_service=governance_service,
        runtime_event_bus=runtime_event_bus,
    )

    return RuntimeBootstrap(
        session_backend=session_backend,
        conversation_compaction_service=conversation_compaction_service,
        runtime_thread_history_reader=runtime_thread_history_reader,
        state_store=state_store,
        repositories=repositories,
        evidence_ledger=evidence_ledger,
        environment_registry=environment_registry,
        environment_service=environment_service,
        runtime_event_bus=runtime_event_bus,
        runtime_health_service=runtime_health_service,
        provider_manager=provider_manager,
        state_query_service=state_query_service,
        evidence_query_service=evidence_query_service,
        human_assist_task_service=human_assist_task_service,
        strategy_memory_service=strategy_memory_service,
        work_context_service=work_context_service,
        knowledge_service=knowledge_service,
        media_service=media_service,
        derived_memory_index_service=derived_memory_index_service,
        memory_recall_service=memory_recall_service,
        memory_reflection_service=memory_reflection_service,
        memory_retain_service=memory_retain_service,
        memory_activation_service=memory_activation_service,
        agent_experience_service=agent_experience_service,
        reporting_service=reporting_service,
        operating_lane_service=operating_lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=operating_cycle_service,
        assignment_service=assignment_service,
        agent_report_service=agent_report_service,
        delegation_service=delegation_service,
        capability_service=capability_service,
        agent_profile_service=agent_profile_service,
        industry_service=industry_service,
        workflow_template_service=workflow_template_service,
        fixed_sop_service=fixed_sop_service,
        routine_service=routine_service,
        prediction_service=prediction_service,
        goal_service=goal_service,
        learning_service=learning_service,
        governance_service=governance_service,
        kernel_dispatcher=kernel_dispatcher,
        kernel_task_store=kernel_task_store,
        kernel_tool_bridge=kernel_tool_bridge,
        turn_executor=turn_executor,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
        query_execution_service=query_execution_service,
        actor_mailbox_service=actor_mailbox_service,
        actor_worker=actor_worker,
        actor_supervisor=actor_supervisor,
    )
