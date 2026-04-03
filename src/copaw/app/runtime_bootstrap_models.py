# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..media import MediaService
    from ..capabilities import CapabilityService
    from ..evidence import EvidenceLedger
    from ..environments import EnvironmentRegistry, EnvironmentService, SessionMountRepository
    from ..goals import GoalService
    from ..industry import IndustryService
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
    from ..learning import LearningService
    from ..memory import (
        ConversationCompactionService,
        DerivedMemoryIndexService,
        MemoryRecallService,
        MemoryReflectionService,
        MemoryRetainService,
    )
    from ..predictions import PredictionService
    from ..providers.runtime_provider_facade import ProviderRuntimeSurface
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
        SqliteFixedSopBindingRepository,
        SqliteFixedSopTemplateRepository,
        SqliteGoalOverrideRepository,
        SqliteGoalRepository,
        SqliteGovernanceControlRepository,
        SqliteHumanAssistTaskRepository,
        SqliteIndustryInstanceRepository,
        SqliteKnowledgeChunkRepository,
        SqliteMediaAnalysisRepository,
        SqliteMemoryEntityViewRepository,
        SqliteMemoryFactIndexRepository,
        SqliteMemoryOpinionViewRepository,
        SqliteMemoryRelationViewRepository,
        SqliteMemoryReflectionRunRepository,
        SqliteOperatingCycleRepository,
        SqliteOperatingLaneRepository,
        SqlitePredictionCaseRepository,
        SqlitePredictionRecommendationRepository,
        SqlitePredictionReviewRepository,
        SqlitePredictionScenarioRepository,
        SqlitePredictionSignalRepository,
        SqliteExecutionRoutineRepository,
        SqliteRuntimeFrameRepository,
        SqliteRoutineRunRepository,
        SqliteScheduleRepository,
        SqliteStrategyMemoryRepository,
        SqliteTaskRepository,
        SqliteTaskRuntimeRepository,
        SqliteWorkContextRepository,
        SqliteWorkflowPresetRepository,
        SqliteWorkflowRunRepository,
        SqliteWorkflowTemplateRepository,
    )
    from ..workflows import WorkflowTemplateService
    from .channels import ChannelManager
    from .crons.manager import CronManager
    from .crons.repo import StateBackedJobRepository
    from .mcp import MCPClientManager, MCPConfigWatcher
    from .runtime_center import (
        RuntimeCenterEvidenceQueryService,
        RuntimeCenterStateQueryService,
    )
    from .runtime_events import RuntimeEventBus
    from .runtime_health_service import RuntimeHealthService
    from .runtime_threads import SessionRuntimeThreadHistoryReader


@dataclass(slots=True)
class RuntimeRepositories:
    task_repository: SqliteTaskRepository
    task_runtime_repository: SqliteTaskRuntimeRepository
    runtime_frame_repository: SqliteRuntimeFrameRepository
    bootstrap_schedule_repository: SqliteScheduleRepository
    schedule_repository: SqliteScheduleRepository
    goal_repository: SqliteGoalRepository
    human_assist_task_repository: SqliteHumanAssistTaskRepository
    work_context_repository: SqliteWorkContextRepository
    decision_request_repository: SqliteDecisionRequestRepository
    governance_control_repository: SqliteGovernanceControlRepository
    capability_override_repository: SqliteCapabilityOverrideRepository
    agent_profile_override_repository: SqliteAgentProfileOverrideRepository
    agent_runtime_repository: SqliteAgentRuntimeRepository
    agent_mailbox_repository: SqliteAgentMailboxRepository
    agent_checkpoint_repository: SqliteAgentCheckpointRepository
    agent_lease_repository: SqliteAgentLeaseRepository
    agent_thread_binding_repository: SqliteAgentThreadBindingRepository
    industry_instance_repository: SqliteIndustryInstanceRepository
    media_analysis_repository: SqliteMediaAnalysisRepository
    operating_lane_repository: SqliteOperatingLaneRepository
    backlog_item_repository: SqliteBacklogItemRepository
    operating_cycle_repository: SqliteOperatingCycleRepository
    assignment_repository: SqliteAssignmentRepository
    agent_report_repository: SqliteAgentReportRepository
    goal_override_repository: SqliteGoalOverrideRepository
    strategy_memory_repository: SqliteStrategyMemoryRepository
    knowledge_chunk_repository: SqliteKnowledgeChunkRepository
    memory_fact_index_repository: SqliteMemoryFactIndexRepository
    memory_entity_view_repository: SqliteMemoryEntityViewRepository
    memory_opinion_view_repository: SqliteMemoryOpinionViewRepository
    memory_relation_view_repository: SqliteMemoryRelationViewRepository
    memory_reflection_run_repository: SqliteMemoryReflectionRunRepository
    workflow_template_repository: SqliteWorkflowTemplateRepository
    workflow_preset_repository: SqliteWorkflowPresetRepository
    workflow_run_repository: SqliteWorkflowRunRepository
    fixed_sop_template_repository: SqliteFixedSopTemplateRepository
    fixed_sop_binding_repository: SqliteFixedSopBindingRepository
    routine_repository: SqliteExecutionRoutineRepository
    routine_run_repository: SqliteRoutineRunRepository
    prediction_case_repository: SqlitePredictionCaseRepository
    prediction_scenario_repository: SqlitePredictionScenarioRepository
    prediction_signal_repository: SqlitePredictionSignalRepository
    prediction_recommendation_repository: SqlitePredictionRecommendationRepository
    prediction_review_repository: SqlitePredictionReviewRepository
    session_mount_repository: SessionMountRepository


@dataclass(slots=True)
class RuntimeBootstrap:
    session_backend: Any
    conversation_compaction_service: ConversationCompactionService | None
    runtime_thread_history_reader: SessionRuntimeThreadHistoryReader
    state_store: SQLiteStateStore
    repositories: RuntimeRepositories
    evidence_ledger: EvidenceLedger
    environment_registry: EnvironmentRegistry
    environment_service: EnvironmentService
    runtime_event_bus: RuntimeEventBus
    runtime_health_service: RuntimeHealthService
    runtime_provider: ProviderRuntimeSurface
    state_query_service: RuntimeCenterStateQueryService
    evidence_query_service: RuntimeCenterEvidenceQueryService
    human_assist_task_service: HumanAssistTaskService
    strategy_memory_service: StateStrategyMemoryService
    work_context_service: WorkContextService
    knowledge_service: StateKnowledgeService
    media_service: MediaService
    derived_memory_index_service: DerivedMemoryIndexService
    memory_recall_service: MemoryRecallService
    memory_reflection_service: MemoryReflectionService
    memory_retain_service: MemoryRetainService
    memory_activation_service: Any | None
    agent_experience_service: AgentExperienceMemoryService
    reporting_service: StateReportingService
    operating_lane_service: OperatingLaneService
    backlog_service: BacklogService
    operating_cycle_service: OperatingCycleService
    assignment_service: AssignmentService
    agent_report_service: AgentReportService
    delegation_service: TaskDelegationService
    capability_service: CapabilityService
    agent_profile_service: AgentProfileService
    industry_service: IndustryService
    workflow_template_service: WorkflowTemplateService
    fixed_sop_service: FixedSopService
    routine_service: RoutineService
    prediction_service: PredictionService
    goal_service: GoalService
    learning_service: LearningService
    governance_service: GovernanceService
    kernel_dispatcher: KernelDispatcher
    kernel_task_store: KernelTaskStore
    kernel_tool_bridge: KernelToolBridge
    turn_executor: KernelTurnExecutor
    main_brain_chat_service: MainBrainChatService
    query_execution_service: KernelQueryExecutionService
    actor_mailbox_service: ActorMailboxService
    actor_worker: ActorWorker
    actor_supervisor: ActorSupervisor
    main_brain_orchestrator: MainBrainOrchestrator | None = None


@dataclass(slots=True)
class RuntimeManagerStack:
    mcp_manager: MCPClientManager | None = None
    channel_manager: ChannelManager | None = None
    cron_manager: CronManager | None = None
    job_repository: StateBackedJobRepository | None = None
    config_watcher: object | None = None
    mcp_watcher: MCPConfigWatcher | None = None
