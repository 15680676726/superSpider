# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..media import MediaService
    from ..capabilities import CapabilityService
    from ..capabilities.browser_runtime import BrowserRuntimeService
    from ..evidence import EvidenceLedger
    from ..environments import EnvironmentRegistry, EnvironmentService, SessionMountRepository
    from ..goals import GoalService
    from ..industry import IndustryService
    from ..kernel import (
        ActorMailboxService,
        ActorSupervisor,
        ActorWorker,
        AgentProfileService,
        BuddyOnboardingService,
        BuddyProjectionService,
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
    from ..kernel.runtime_coordination import AssignmentExecutorRuntimeCoordinator
    from ..kernel.executor_event_writeback_service import ExecutorEventWritebackService
    from ..learning import LearningService
    from ..memory import (
        ConversationCompactionService,
        DerivedMemoryIndexService,
        MemoryRecallService,
        MemoryReflectionService,
        MemoryRetainService,
        MemorySleepService,
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
    from ..state.executor_runtime_service import ExecutorRuntimeService
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
        SqliteAutomationLoopRuntimeRepository,
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
        SqliteMemorySleepRepository,
        SqliteOperatingCycleRepository,
        SqliteOperatingLaneRepository,
        SqlitePredictionCaseRepository,
        SqlitePredictionRecommendationRepository,
        SqlitePredictionReviewRepository,
        SqlitePredictionScenarioRepository,
        SqlitePredictionSignalRepository,
        SqliteResearchSessionRepository,
        SqliteExecutionRoutineRepository,
        SqliteRuntimeFrameRepository,
        SqliteRoutineRunRepository,
        SqliteScheduleRepository,
        SqliteSurfaceCapabilityTwinRepository,
        SqliteSurfacePlaybookRepository,
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
    memory_sleep_repository: SqliteMemorySleepRepository
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
    research_session_repository: SqliteResearchSessionRepository | None = None
    automation_loop_runtime_repository: SqliteAutomationLoopRuntimeRepository | None = None
    session_mount_repository: SessionMountRepository | None = None
    external_runtime_repository: Any | None = None
    surface_capability_twin_repository: SqliteSurfaceCapabilityTwinRepository | None = None
    surface_playbook_repository: SqliteSurfacePlaybookRepository | None = None


@dataclass(slots=True)
class SurfaceCapabilityTwinSummary:
    twin_id: str
    capability_name: str
    capability_kind: str
    surface_kind: str
    summary: str
    risk_level: str
    version: int
    updated_at: datetime | None


@dataclass(slots=True)
class SurfacePlaybookSummary:
    playbook_id: str
    twin_id: str | None
    summary: str
    capability_names: list[str]
    recommended_steps: list[str]
    execution_steps: list[str]
    success_signals: list[str]
    version: int
    updated_at: datetime | None


@dataclass(slots=True)
class SurfaceLearningBootstrapProjection:
    scope_level: str
    scope_id: str
    version: int | None
    updated_at: datetime | None
    active_twins: list[SurfaceCapabilityTwinSummary] = field(default_factory=list)
    active_playbook: SurfacePlaybookSummary | None = None


@dataclass(slots=True)
class SourceCollectionFrontdoorResult:
    session_id: str | None
    status: str
    route_mode: str
    execution_agent_id: str
    trigger_source: str
    goal: str
    stop_reason: str | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    collected_sources: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    final_report_id: str | None = None

    def model_dump(self, *, mode: str = "json") -> dict[str, Any]:
        _ = mode
        return {
            "session_id": self.session_id,
            "status": self.status,
            "route_mode": self.route_mode,
            "execution_agent_id": self.execution_agent_id,
            "trigger_source": self.trigger_source,
            "goal": self.goal,
            "stop_reason": self.stop_reason,
            "findings": list(self.findings),
            "collected_sources": list(self.collected_sources),
            "conflicts": list(self.conflicts),
            "gaps": list(self.gaps),
            "final_report_id": self.final_report_id,
        }


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
    provider_admin_service: Any
    state_query_service: RuntimeCenterStateQueryService
    evidence_query_service: RuntimeCenterEvidenceQueryService
    donor_source_service: Any | None
    capability_candidate_service: Any | None
    capability_donor_service: Any | None
    donor_package_service: Any | None
    donor_trust_service: Any | None
    capability_portfolio_service: Any | None
    donor_scout_service: Any | None
    skill_trial_service: Any | None
    skill_lifecycle_decision_service: Any | None
    human_assist_task_service: HumanAssistTaskService
    strategy_memory_service: StateStrategyMemoryService
    work_context_service: WorkContextService
    knowledge_service: StateKnowledgeService
    media_service: MediaService
    derived_memory_index_service: DerivedMemoryIndexService
    memory_recall_service: MemoryRecallService
    memory_reflection_service: MemoryReflectionService
    memory_retain_service: MemoryRetainService
    memory_sleep_service: MemorySleepService
    memory_activation_service: Any | None
    knowledge_graph_service: Any | None
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
    external_runtime_service: Any | None = None
    executor_runtime_service: ExecutorRuntimeService | None = None
    executor_runtime_coordinator: AssignmentExecutorRuntimeCoordinator | None = None
    executor_event_writeback_service: ExecutorEventWritebackService | None = None
    weixin_ilink_runtime_state: Any | None = None
    research_session_service: Any | None = None
    buddy_onboarding_service: BuddyOnboardingService | None = None
    buddy_projection_service: BuddyProjectionService | None = None
    main_brain_orchestrator: MainBrainOrchestrator | None = None


@dataclass(slots=True)
class RuntimeManagerStack:
    mcp_manager: MCPClientManager | None = None
    channel_manager: ChannelManager | None = None
    cron_manager: CronManager | None = None
    job_repository: StateBackedJobRepository | None = None
    config_watcher: object | None = None
    mcp_watcher: MCPConfigWatcher | None = None
    browser_runtime_service: BrowserRuntimeService | None = None
