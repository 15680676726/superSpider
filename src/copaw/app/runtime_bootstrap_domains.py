# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..capabilities import CapabilityService
from ..compiler import (
    AssignmentPlanningCompiler,
    CyclePlanningCompiler,
    ReportReplanEngine,
    StrategyPlanningCompiler,
)
from ..evidence import EvidenceLedger
from ..environments import EnvironmentService
from ..goals import GoalService
from ..industry import IndustryDraftGenerator, IndustryService
from ..industry.service_context import build_industry_service_runtime_bindings
from ..kernel import (
    ActorMailboxService,
    ActorSupervisor,
    AgentProfileService,
    KernelDispatcher,
    KernelQueryExecutionService,
    KernelToolBridge,
    MainBrainChatService,
    MainBrainOrchestrator,
    TaskDelegationService,
)
from ..kernel.main_brain_execution_planner import MainBrainExecutionPlanner
from ..kernel.main_brain_intake import resolve_request_main_brain_intake_contract
from ..learning import LearningService
from ..learning.runtime_bindings import LearningRuntimeBindings
from ..media import MediaService
from ..memory import (
    DerivedMemoryIndexService,
    KnowledgeGraphService,
    MemoryActivationService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
)
from ..predictions import PredictionService
from ..providers.runtime_provider_facade import ProviderRuntimeSurface
from ..routines import RoutineService
from ..sop_kernel import FixedSopService
from ..state import SQLiteStateStore
from ..state.agent_experience_service import AgentExperienceMemoryService
from ..state.knowledge_service import StateKnowledgeService
from ..state.main_brain_service import (
    AgentReportService,
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from ..state.reporting_service import StateReportingService
from ..state.strategy_memory_service import StateStrategyMemoryService
from ..state.work_context_service import WorkContextService
from ..workflows import WorkflowTemplateService
from .mcp import MCPClientManager
from .runtime_bootstrap_models import RuntimeRepositories
from .runtime_center import RuntimeCenterStateQueryService
from .runtime_events import RuntimeEventBus


@dataclass(slots=True)
class RuntimeDomainServices:
    goal_service: GoalService
    agent_profile_service: AgentProfileService
    reporting_service: StateReportingService
    operating_lane_service: OperatingLaneService
    backlog_service: BacklogService
    operating_cycle_service: OperatingCycleService
    assignment_service: AssignmentService
    agent_report_service: AgentReportService
    media_service: MediaService
    industry_service: IndustryService
    workflow_template_service: WorkflowTemplateService
    fixed_sop_service: FixedSopService
    routine_service: RoutineService
    prediction_service: PredictionService
    delegation_service: TaskDelegationService
    query_execution_service: KernelQueryExecutionService
    main_brain_chat_service: MainBrainChatService
    main_brain_orchestrator: MainBrainOrchestrator
    report_replan_engine: ReportReplanEngine


def _build_goal_service(
    *,
    assignment_planner: AssignmentPlanningCompiler,
    **kwargs: Any,
) -> GoalService:
    try:
        return GoalService(
            assignment_planner=assignment_planner,
            **kwargs,
        )
    except TypeError as exc:
        if "assignment_planner" not in str(exc):
            raise
        return GoalService(**kwargs)


def build_runtime_domain_services(
    *,
    session_backend: Any,
    conversation_compaction_service: Any,
    mcp_manager: MCPClientManager,
    state_store: SQLiteStateStore,
    repositories: RuntimeRepositories,
    evidence_ledger: EvidenceLedger,
    environment_service: EnvironmentService,
    runtime_event_bus: RuntimeEventBus,
    runtime_provider: ProviderRuntimeSurface,
    state_query_service: RuntimeCenterStateQueryService,
    strategy_memory_service: StateStrategyMemoryService,
    knowledge_service: StateKnowledgeService,
    derived_memory_index_service: DerivedMemoryIndexService,
    memory_reflection_service: MemoryReflectionService,
    memory_recall_service: MemoryRecallService,
    memory_retain_service: MemoryRetainService,
    memory_activation_service: MemoryActivationService | None = None,
    knowledge_graph_service: KnowledgeGraphService | None = None,
    agent_experience_service: AgentExperienceMemoryService | None = None,
    work_context_service: WorkContextService | None = None,
    learning_service: LearningService | None = None,
    capability_service: CapabilityService | None = None,
    capability_candidate_service: object | None = None,
    capability_donor_service: object | None = None,
    capability_portfolio_service: object | None = None,
    skill_trial_service: object | None = None,
    skill_lifecycle_decision_service: object | None = None,
    kernel_dispatcher: KernelDispatcher | None = None,
    kernel_tool_bridge: KernelToolBridge | None = None,
    actor_mailbox_service: ActorMailboxService | None = None,
    actor_supervisor: ActorSupervisor | None = None,
) -> RuntimeDomainServices:
    strategy_planning_compiler = StrategyPlanningCompiler()
    cycle_planner = CyclePlanningCompiler()
    assignment_planner = AssignmentPlanningCompiler()
    report_replan_engine = ReportReplanEngine()

    goal_service = _build_goal_service(
        assignment_planner=assignment_planner,
        repository=repositories.goal_repository,
        override_repository=repositories.goal_override_repository,
        dispatcher=kernel_dispatcher,
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        runtime_frame_repository=repositories.runtime_frame_repository,
        decision_request_repository=repositories.decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        strategy_memory_service=strategy_memory_service,
        knowledge_service=knowledge_service,
        memory_recall_service=memory_recall_service,
        memory_activation_service=memory_activation_service,
        industry_instance_repository=repositories.industry_instance_repository,
        runtime_event_bus=runtime_event_bus,
    )
    capability_service.set_goal_service(goal_service)
    state_query_service.set_goal_service(goal_service)

    agent_profile_service = AgentProfileService(
        override_repository=repositories.agent_profile_override_repository,
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        agent_runtime_repository=repositories.agent_runtime_repository,
        agent_mailbox_repository=repositories.agent_mailbox_repository,
        agent_checkpoint_repository=repositories.agent_checkpoint_repository,
        agent_lease_repository=repositories.agent_lease_repository,
        agent_thread_binding_repository=repositories.agent_thread_binding_repository,
        decision_request_repository=repositories.decision_request_repository,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        capability_service=capability_service,
        learning_service=learning_service,
        goal_service=goal_service,
        industry_instance_repository=repositories.industry_instance_repository,
    )
    agent_profile_service.backfill_industry_baseline_capabilities()
    goal_service.set_agent_profile_service(agent_profile_service)
    state_query_service.set_learning_service(learning_service)
    state_query_service.set_agent_profile_service(agent_profile_service)
    capability_service.set_agent_profile_service(agent_profile_service)

    reporting_service = StateReportingService(
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        goal_repository=repositories.goal_repository,
        decision_request_repository=repositories.decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        industry_instance_repository=repositories.industry_instance_repository,
        agent_profile_service=agent_profile_service,
        prediction_case_repository=repositories.prediction_case_repository,
        prediction_recommendation_repository=repositories.prediction_recommendation_repository,
        prediction_review_repository=repositories.prediction_review_repository,
    )
    derived_memory_index_service.set_reporting_service(reporting_service)
    derived_memory_index_service.set_learning_service(learning_service)
    memory_reflection_service.set_learning_service(learning_service)

    operating_lane_service = OperatingLaneService(
        repository=repositories.operating_lane_repository,
    )
    backlog_service = BacklogService(
        repository=repositories.backlog_item_repository,
    )
    operating_cycle_service = OperatingCycleService(
        repository=repositories.operating_cycle_repository,
    )
    assignment_service = AssignmentService(
        repository=repositories.assignment_repository,
    )
    agent_report_service = AgentReportService(
        repository=repositories.agent_report_repository,
        memory_retain_service=memory_retain_service,
    )
    media_service = MediaService(
        repository=repositories.media_analysis_repository,
        evidence_ledger=evidence_ledger,
        knowledge_service=knowledge_service,
        strategy_memory_service=strategy_memory_service,
        backlog_service=backlog_service,
        operating_lane_service=operating_lane_service,
        industry_instance_repository=repositories.industry_instance_repository,
        memory_retain_service=memory_retain_service,
    )
    industry_runtime_bindings = build_industry_service_runtime_bindings(
        kernel_dispatcher=kernel_dispatcher,
        operating_lane_repository=repositories.operating_lane_repository,
        backlog_item_repository=repositories.backlog_item_repository,
        operating_cycle_repository=repositories.operating_cycle_repository,
        assignment_repository=repositories.assignment_repository,
        agent_report_repository=repositories.agent_report_repository,
        agent_runtime_repository=repositories.agent_runtime_repository,
        agent_thread_binding_repository=repositories.agent_thread_binding_repository,
        schedule_repository=repositories.schedule_repository,
        agent_mailbox_repository=repositories.agent_mailbox_repository,
        agent_checkpoint_repository=repositories.agent_checkpoint_repository,
        agent_lease_repository=repositories.agent_lease_repository,
        strategy_memory_repository=repositories.strategy_memory_repository,
        workflow_run_repository=repositories.workflow_run_repository,
        prediction_case_repository=repositories.prediction_case_repository,
        prediction_scenario_repository=repositories.prediction_scenario_repository,
        prediction_signal_repository=repositories.prediction_signal_repository,
        prediction_recommendation_repository=repositories.prediction_recommendation_repository,
        prediction_review_repository=repositories.prediction_review_repository,
        operating_lane_service=operating_lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=operating_cycle_service,
        assignment_service=assignment_service,
        agent_report_service=agent_report_service,
        strategy_planning_compiler=strategy_planning_compiler,
        cycle_planner=cycle_planner,
        assignment_planner=assignment_planner,
        report_replan_engine=report_replan_engine,
        state_store=state_store,
        memory_retain_service=memory_retain_service,
        memory_activation_service=memory_activation_service,
        knowledge_service=knowledge_service,
    )
    industry_service = IndustryService(
        goal_service=goal_service,
        industry_instance_repository=repositories.industry_instance_repository,
        session_backend=session_backend,
        media_service=media_service,
        goal_override_repository=repositories.goal_override_repository,
        agent_profile_override_repository=repositories.agent_profile_override_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        agent_profile_service=agent_profile_service,
        capability_service=capability_service,
        strategy_memory_service=strategy_memory_service,
        state_store=state_store,
        draft_generator=IndustryDraftGenerator(provider_manager=runtime_provider),
        runtime_bindings=industry_runtime_bindings,
        memory_retain_service=memory_retain_service,
        memory_activation_service=memory_activation_service,
        knowledge_service=knowledge_service,
        work_context_service=work_context_service,
        actor_mailbox_service=actor_mailbox_service,
    )
    capability_service.set_industry_service(industry_service)

    workflow_template_service = WorkflowTemplateService(
        workflow_template_repository=repositories.workflow_template_repository,
        workflow_run_repository=repositories.workflow_run_repository,
        workflow_preset_repository=repositories.workflow_preset_repository,
        goal_service=goal_service,
        goal_override_repository=repositories.goal_override_repository,
        schedule_repository=repositories.schedule_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        strategy_memory_service=strategy_memory_service,
        task_repository=repositories.task_repository,
        decision_request_repository=repositories.decision_request_repository,
        agent_profile_override_repository=repositories.agent_profile_override_repository,
        agent_profile_service=agent_profile_service,
        evidence_ledger=evidence_ledger,
        capability_service=capability_service,
        environment_service=environment_service,
    )
    fixed_sop_service = FixedSopService(
        template_repository=repositories.fixed_sop_template_repository,
        binding_repository=repositories.fixed_sop_binding_repository,
        workflow_run_repository=repositories.workflow_run_repository,
        agent_report_repository=repositories.agent_report_repository,
        evidence_ledger=evidence_ledger,
        routine_service=None,
        environment_service=environment_service,
    )
    routine_service = RoutineService(
        routine_repository=repositories.routine_repository,
        routine_run_repository=repositories.routine_run_repository,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        kernel_dispatcher=kernel_dispatcher,
        state_store=state_store,
        memory_retain_service=memory_retain_service,
        learning_service=learning_service,
        capability_service=capability_service,
        agent_profile_service=agent_profile_service,
    )
    fixed_sop_service.set_routine_service(routine_service)
    capability_service.set_routine_service(routine_service)
    capability_service.set_fixed_sop_service(fixed_sop_service)
    capability_service.get_discovery_service().set_fixed_sop_service(fixed_sop_service)
    learning_service.configure_bindings(
        LearningRuntimeBindings(
            industry_service=industry_service,
            capability_service=capability_service,
            kernel_dispatcher=kernel_dispatcher,
            fixed_sop_service=fixed_sop_service,
            agent_profile_service=agent_profile_service,
            experience_memory_service=agent_experience_service,
        ),
    )

    prediction_service = PredictionService(
        case_repository=repositories.prediction_case_repository,
        scenario_repository=repositories.prediction_scenario_repository,
        signal_repository=repositories.prediction_signal_repository,
        recommendation_repository=repositories.prediction_recommendation_repository,
        review_repository=repositories.prediction_review_repository,
        evidence_ledger=evidence_ledger,
        reporting_service=reporting_service,
        goal_repository=repositories.goal_repository,
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        decision_request_repository=repositories.decision_request_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        workflow_run_repository=repositories.workflow_run_repository,
        strategy_memory_service=strategy_memory_service,
        capability_service=capability_service,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        capability_portfolio_service=capability_portfolio_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        agent_profile_service=agent_profile_service,
        kernel_dispatcher=kernel_dispatcher,
    )
    industry_service.set_prediction_service(prediction_service)

    delegation_service = TaskDelegationService(
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        kernel_dispatcher=kernel_dispatcher,
        evidence_ledger=evidence_ledger,
        agent_profile_service=agent_profile_service,
        industry_service=industry_service,
        environment_service=environment_service,
        actor_mailbox_service=actor_mailbox_service,
        actor_supervisor=actor_supervisor,
        runtime_event_bus=runtime_event_bus,
        experience_memory_service=agent_experience_service,
    )
    capability_service.set_delegation_service(delegation_service)
    capability_service.set_actor_mailbox_service(actor_mailbox_service)
    capability_service.set_actor_supervisor(actor_supervisor)
    environment_service.set_kernel_dispatcher(kernel_dispatcher)

    query_execution_service = KernelQueryExecutionService(
        session_backend=session_backend,
        conversation_compaction_service=conversation_compaction_service,
        mcp_manager=mcp_manager,
        tool_bridge=kernel_tool_bridge,
        environment_service=environment_service,
        capability_service=capability_service,
        kernel_dispatcher=kernel_dispatcher,
        agent_profile_service=agent_profile_service,
        delegation_service=delegation_service,
        industry_service=industry_service,
        strategy_memory_service=strategy_memory_service,
        prediction_service=prediction_service,
        knowledge_service=knowledge_service,
        memory_recall_service=memory_recall_service,
        memory_activation_service=memory_activation_service,
        actor_mailbox_service=actor_mailbox_service,
        agent_runtime_repository=repositories.agent_runtime_repository,
        governance_control_repository=repositories.governance_control_repository,
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        evidence_ledger=evidence_ledger,
        provider_manager=runtime_provider,
    )
    main_brain_chat_service = MainBrainChatService(
        session_backend=session_backend,
        industry_service=industry_service,
        agent_profile_service=agent_profile_service,
        memory_recall_service=memory_recall_service,
        actor_supervisor=actor_supervisor,
        model_factory=runtime_provider.get_active_chat_model,
    )
    main_brain_orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        session_backend=session_backend,
        environment_service=environment_service,
        intake_contract_resolver=resolve_request_main_brain_intake_contract,
        execution_planner=MainBrainExecutionPlanner(
            knowledge_graph_service=knowledge_graph_service,
        ),
    )

    return RuntimeDomainServices(
        goal_service=goal_service,
        agent_profile_service=agent_profile_service,
        reporting_service=reporting_service,
        operating_lane_service=operating_lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=operating_cycle_service,
        assignment_service=assignment_service,
        agent_report_service=agent_report_service,
        media_service=media_service,
        industry_service=industry_service,
        workflow_template_service=workflow_template_service,
        fixed_sop_service=fixed_sop_service,
        routine_service=routine_service,
        prediction_service=prediction_service,
        delegation_service=delegation_service,
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
        report_replan_engine=report_replan_engine,
    )
