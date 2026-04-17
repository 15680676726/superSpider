# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
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
    BuddyDomainCapabilityGrowthService,
    BuddyOnboardingService,
    BuddyProjectionService,
    GovernanceService,
    KernelDispatcher,
    MainBrainChatService,
    MainBrainExceptionAbsorptionService,
    MainBrainOrchestrator,
    KernelQueryExecutionService,
    KernelTaskStore,
    KernelToolBridge,
    KernelTurnExecutor,
    TaskDelegationService,
)
from ..kernel.buddy_onboarding_reasoner import ModelDrivenBuddyOnboardingReasoner
from ..kernel.buddy_runtime_focus import build_buddy_current_focus_resolver
from ..learning import LearningService, PatchExecutor
from ..media import MediaService
from ..memory import (
    DerivedMemoryIndexService,
    KnowledgeGraphService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
    MemorySleepService,
)
from ..discovery.scout_service import DonorScoutService
from ..discovery.opportunity_radar import OpportunityRadarService
from ..discovery.models import DiscoveryActionRequest, DiscoveryHit
from ..discovery.provider_search import (
    github_opportunity_radar_items as _github_opportunity_radar_items,
    mcp_registry_opportunity_radar_items as _mcp_registry_opportunity_radar_items,
    search_curated_discovery_hits as _search_curated_discovery_hits,
    search_github_repository_donors as _search_github_repository_donors,
    search_mcp_registry_discovery_hits as _search_mcp_registry_discovery_hits,
    search_skillhub_discovery_hits as _search_skillhub_discovery_hits,
)
from ..predictions import PredictionService
from ..providers.provider_admin_service import (
    ProviderAdminService,
    build_provider_admin_service,
)
from ..providers.provider_manager import ProviderManager
from ..providers.runtime_provider_facade import (
    ProviderRuntimeFacade,
    get_runtime_provider_facade,
)
from ..routines import RoutineService
from ..sop_kernel import FixedSopService
from ..state import SQLiteStateStore
from ..state.human_assist_task_service import HumanAssistTaskService
from ..state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)
from ..state.main_brain_service import (
    AgentReportService,
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from ..state.agent_experience_service import AgentExperienceMemoryService
from ..state.capability_donor_service import CapabilityDonorService
from ..state.capability_portfolio_service import CapabilityPortfolioService
from ..state.donor_package_service import DonorPackageService
from ..state.donor_source_service import DonorSourceService
from ..state.donor_trust_service import DonorTrustService
from ..state.knowledge_service import StateKnowledgeService
from ..state.reporting_service import StateReportingService
from ..state.skill_lifecycle_decision_service import SkillLifecycleDecisionService
from ..state.strategy_memory_service import StateStrategyMemoryService
from ..state.skill_candidate_service import CapabilityCandidateService
from ..state.skill_trial_service import SkillTrialService
from ..state.external_runtime_service import ExternalCapabilityRuntimeService
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

logger = logging.getLogger(__name__)


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


def _resolve_runtime_provider_facade(
    provider_manager: ProviderManager,
) -> ProviderRuntimeFacade:
    return get_runtime_provider_facade(provider_manager=provider_manager)


def _execute_runtime_discovery_action(
    source: object,
    request: DiscoveryActionRequest,
) -> list[DiscoveryHit]:
    source_metadata = getattr(source, "metadata", None)
    source_endpoint = str(getattr(source, "endpoint", "") or "").strip() or None
    provider = ""
    if isinstance(source_metadata, dict):
        provider = str(source_metadata.get("provider") or "").strip().lower()
    limit = max(1, int(getattr(request, "limit", 20) or 20))
    query = str(getattr(request, "query", "") or "").strip()
    if provider == "github-repo":
        return _search_github_repository_donors(
            query,
            limit=limit,
            search_url=source_endpoint,
        )
    if provider == "skillhub-catalog":
        return _search_skillhub_discovery_hits(
            query,
            limit=limit,
            search_url=source_endpoint,
        )
    if provider == "skillhub-curated":
        return _search_curated_discovery_hits(
            query,
            limit=limit,
            search_url=source_endpoint,
        )
    if provider == "mcp-registry":
        return _search_mcp_registry_discovery_hits(
            query,
            limit=limit,
            base_url=source_endpoint,
        )
    return []


def _build_runtime_opportunity_radar_feeds() -> dict[str, object]:
    github_queries = (
        "browser automation github",
        "workflow automation github",
        "research assistant github",
    )
    mcp_queries = (
        "filesystem mcp",
        "browser mcp",
        "search mcp",
    )
    return {
        "github-trending": lambda: _github_opportunity_radar_items(
            github_queries,
            per_query_limit=2,
        ),
        "mcp-registry": lambda: _mcp_registry_opportunity_radar_items(
            mcp_queries,
            per_query_limit=2,
        ),
    }


def _external_runtime_process_exists(pid: int | None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _reconcile_external_runtime_truth(
    external_runtime_service: object | None,
) -> dict[str, int]:
    lister = getattr(external_runtime_service, "list_runtimes", None)
    marker = getattr(external_runtime_service, "mark_runtime_stopped", None)
    if not callable(lister) or not callable(marker):
        return {"checked": 0, "orphaned": 0}
    checked = 0
    orphaned = 0
    for runtime in lister(runtime_kind="service", limit=500):
        if getattr(runtime, "status", None) not in {
            "starting",
            "restarting",
            "ready",
            "degraded",
        }:
            continue
        process_id = getattr(runtime, "process_id", None)
        if process_id is None:
            continue
        checked += 1
        if _external_runtime_process_exists(process_id):
            continue
        marker(
            runtime.runtime_id,
            status="orphaned",
            last_error="Runtime process was missing during bootstrap reconcile.",
        )
        orphaned += 1
    return {"checked": checked, "orphaned": orphaned}


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
    donor_source_service: object | None,
    capability_candidate_service: CapabilityCandidateService | None,
    capability_donor_service: CapabilityDonorService | None,
    donor_package_service: object | None,
    donor_trust_service: object | None,
    capability_portfolio_service: CapabilityPortfolioService | None,
    donor_scout_service: object | None,
    skill_trial_service: object | None,
    skill_lifecycle_decision_service: object | None,
    human_assist_task_service: HumanAssistTaskService | None,
    environment_service: EnvironmentService,
    runtime_provider: object | None,
    external_runtime_service: object | None = None,
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
        donor_source_service=donor_source_service,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        donor_package_service=donor_package_service,
        donor_trust_service=donor_trust_service,
        capability_portfolio_service=capability_portfolio_service,
        donor_scout_service=donor_scout_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        human_assist_task_service=human_assist_task_service,
        environment_service=environment_service,
        external_runtime_service=external_runtime_service,
        runtime_provider=runtime_provider,
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
    runtime_provider: object | None,
    external_runtime_service: object | None = None,
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
        runtime_provider=runtime_provider,
        external_runtime_service=external_runtime_service,
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
    memory_reflection_service: MemoryReflectionService,
    memory_sleep_service: MemorySleepService | None = None,
) -> None:
    derived_memory_index_service.rebuild_all()
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
    idle_catchup = getattr(memory_sleep_service, "run_idle_catchup", None)
    if callable(idle_catchup):
        try:
            idle_catchup(limit=5)
        except Exception:
            logger.debug("startup memory sleep idle catchup failed", exc_info=True)


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
    buddy_profile_repository = SqliteHumanProfileRepository(state_store)
    buddy_growth_target_repository = SqliteGrowthTargetRepository(state_store)
    buddy_relationship_repository = SqliteCompanionRelationshipRepository(state_store)
    buddy_domain_capability_repository = SqliteBuddyDomainCapabilityRepository(state_store)
    buddy_onboarding_session_repository = SqliteBuddyOnboardingSessionRepository(state_store)
    donor_source_service = DonorSourceService(
        state_store=state_store,
    )
    capability_donor_service = CapabilityDonorService(
        state_store=state_store,
    )
    donor_package_service = DonorPackageService(
        donor_service=capability_donor_service,
    )
    capability_candidate_service = CapabilityCandidateService(
        state_store=state_store,
        donor_service=capability_donor_service,
    )
    skill_trial_service = SkillTrialService(
        state_store=state_store,
    )
    skill_lifecycle_decision_service = SkillLifecycleDecisionService(
        state_store=state_store,
    )
    donor_trust_service = DonorTrustService(
        donor_service=capability_donor_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
    )
    donor_trust_service.refresh_trust_records()
    capability_portfolio_service = CapabilityPortfolioService(
        donor_service=capability_donor_service,
        candidate_service=capability_candidate_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
    )
    opportunity_radar_service = OpportunityRadarService(
        feeds=_build_runtime_opportunity_radar_feeds(),
    )
    donor_scout_service = DonorScoutService(
        source_service=donor_source_service,
        candidate_service=capability_candidate_service,
        opportunity_radar_service=opportunity_radar_service,
        discovery_executor=_execute_runtime_discovery_action,
    )
    external_runtime_service = ExternalCapabilityRuntimeService(
        repository=repositories.external_runtime_repository,
    )
    _reconcile_external_runtime_truth(external_runtime_service)

    provider_manager = ProviderManager()
    runtime_provider = _resolve_runtime_provider_facade(provider_manager)
    provider_admin_service: ProviderAdminService = build_provider_admin_service(
        provider_manager,
    )
    (
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
        agent_experience_service,
    ) = _build_query_services(
        repositories=repositories,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=runtime_event_bus,
        donor_source_service=donor_source_service,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        donor_package_service=donor_package_service,
        donor_trust_service=donor_trust_service,
        capability_portfolio_service=capability_portfolio_service,
        donor_scout_service=donor_scout_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        human_assist_task_service=human_assist_task_service,
        environment_service=environment_service,
        runtime_provider=runtime_provider,
        external_runtime_service=external_runtime_service,
    )
    knowledge_graph_service = KnowledgeGraphService(
        knowledge_service=knowledge_service,
        derived_index_service=derived_memory_index_service,
        strategy_memory_service=strategy_memory_service,
        memory_activation_service=memory_activation_service,
    )
    set_knowledge_graph_service = getattr(
        state_query_service,
        "set_knowledge_graph_service",
        None,
    )
    if callable(set_knowledge_graph_service):
        set_knowledge_graph_service(knowledge_graph_service)
    work_context_service = WorkContextService(
        repository=repositories.work_context_repository,
    )
    set_work_context_graph_projection = getattr(
        work_context_service,
        "set_graph_projection_service",
        None,
    )
    if callable(set_work_context_graph_projection):
        set_work_context_graph_projection(knowledge_graph_service)
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
        runtime_provider=runtime_provider,
        external_runtime_service=external_runtime_service,
    )
    exception_absorption_service = MainBrainExceptionAbsorptionService()
    configure_exception_absorption = getattr(actor_supervisor, "configure_exception_absorption", None)

    domain_services = build_runtime_domain_services(
        session_backend=session_backend,
        conversation_compaction_service=conversation_compaction_service,
        mcp_manager=mcp_manager,
        state_store=state_store,
        repositories=repositories,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        runtime_event_bus=runtime_event_bus,
        runtime_provider=runtime_provider,
        state_query_service=state_query_service,
        strategy_memory_service=strategy_memory_service,
        knowledge_service=knowledge_service,
        derived_memory_index_service=derived_memory_index_service,
        memory_reflection_service=memory_reflection_service,
        memory_recall_service=memory_recall_service,
        memory_retain_service=memory_retain_service,
        memory_sleep_service=memory_sleep_service,
        memory_activation_service=memory_activation_service,
        knowledge_graph_service=knowledge_graph_service,
        agent_experience_service=agent_experience_service,
        work_context_service=work_context_service,
        learning_service=learning_service,
        capability_service=capability_service,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        capability_portfolio_service=capability_portfolio_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        kernel_dispatcher=kernel_dispatcher,
        kernel_tool_bridge=kernel_tool_bridge,
        actor_mailbox_service=actor_mailbox_service,
        actor_supervisor=actor_supervisor,
    )
    if callable(configure_exception_absorption):
        configure_exception_absorption(
            exception_absorption_service=exception_absorption_service,
            human_assist_task_service=human_assist_task_service,
            report_replan_engine=getattr(domain_services, "report_replan_engine", None),
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
    set_dispatcher_industry_service = getattr(kernel_dispatcher, "set_industry_service", None)
    if callable(set_dispatcher_industry_service):
        set_dispatcher_industry_service(industry_service)
    set_actor_worker_industry_service = getattr(actor_worker, "set_industry_service", None)
    if callable(set_actor_worker_industry_service):
        set_actor_worker_industry_service(industry_service)
    workflow_template_service = domain_services.workflow_template_service
    fixed_sop_service = domain_services.fixed_sop_service
    routine_service = domain_services.routine_service
    prediction_service = domain_services.prediction_service
    delegation_service = domain_services.delegation_service
    query_execution_service = domain_services.query_execution_service
    main_brain_chat_service = domain_services.main_brain_chat_service
    main_brain_orchestrator = domain_services.main_brain_orchestrator
    research_session_service = getattr(domain_services, "research_session_service", None)
    buddy_current_focus_resolver = build_buddy_current_focus_resolver(
        agent_profile_service=agent_profile_service,
        growth_target_repository=buddy_growth_target_repository,
        domain_capability_repository=buddy_domain_capability_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        assignment_service=assignment_service,
        backlog_service=backlog_service,
    )
    buddy_domain_capability_growth_service = BuddyDomainCapabilityGrowthService(
        domain_capability_repository=buddy_domain_capability_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        operating_lane_service=operating_lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=operating_cycle_service,
        assignment_service=assignment_service,
        agent_report_service=agent_report_service,
    )
    buddy_onboarding_service = BuddyOnboardingService(
        profile_repository=buddy_profile_repository,
        growth_target_repository=buddy_growth_target_repository,
        relationship_repository=buddy_relationship_repository,
        domain_capability_repository=buddy_domain_capability_repository,
        onboarding_session_repository=buddy_onboarding_session_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        operating_lane_service=operating_lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=operating_cycle_service,
        assignment_service=assignment_service,
        schedule_repository=repositories.schedule_repository,
        domain_capability_growth_service=buddy_domain_capability_growth_service,
        onboarding_reasoner=ModelDrivenBuddyOnboardingReasoner(
            provider_runtime=runtime_provider,
        ),
    )
    buddy_projection_service = BuddyProjectionService(
        profile_repository=buddy_profile_repository,
        growth_target_repository=buddy_growth_target_repository,
        relationship_repository=buddy_relationship_repository,
        domain_capability_repository=buddy_domain_capability_repository,
        onboarding_session_repository=buddy_onboarding_session_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        domain_capability_growth_service=buddy_domain_capability_growth_service,
        human_assist_task_service=human_assist_task_service,
        current_focus_resolver=buddy_current_focus_resolver,
    )
    set_query_buddy_projection = getattr(query_execution_service, "set_buddy_projection_service", None)
    if callable(set_query_buddy_projection):
        set_query_buddy_projection(buddy_projection_service)
    set_chat_buddy_projection = getattr(main_brain_chat_service, "set_buddy_projection_service", None)
    if callable(set_chat_buddy_projection):
        set_chat_buddy_projection(buddy_projection_service)
    try:
        capability_candidate_service.import_active_baseline_artifacts(
            mounts=capability_service.list_public_capabilities(enabled_only=True),
        )
    except Exception:
        logger.debug("capability candidate baseline import failed", exc_info=True)
    governance_service.set_environment_service(environment_service)
    governance_service.set_human_assist_task_service(human_assist_task_service)
    governance_service.set_industry_service(industry_service)
    _warm_runtime_memory_services(
        repositories=repositories,
        derived_memory_index_service=derived_memory_index_service,
        memory_reflection_service=memory_reflection_service,
        memory_sleep_service=memory_sleep_service,
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
        runtime_provider=runtime_provider,
        provider_admin_service=provider_admin_service,
        buddy_onboarding_service=buddy_onboarding_service,
        buddy_projection_service=buddy_projection_service,
        state_query_service=state_query_service,
        evidence_query_service=evidence_query_service,
        donor_source_service=donor_source_service,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        donor_package_service=donor_package_service,
        donor_trust_service=donor_trust_service,
        capability_portfolio_service=capability_portfolio_service,
        donor_scout_service=donor_scout_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        human_assist_task_service=human_assist_task_service,
        strategy_memory_service=strategy_memory_service,
        work_context_service=work_context_service,
        knowledge_service=knowledge_service,
        media_service=media_service,
        derived_memory_index_service=derived_memory_index_service,
        memory_recall_service=memory_recall_service,
        memory_reflection_service=memory_reflection_service,
        memory_retain_service=memory_retain_service,
        memory_sleep_service=memory_sleep_service,
        memory_activation_service=memory_activation_service,
        knowledge_graph_service=knowledge_graph_service,
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
        research_session_service=research_session_service,
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
        external_runtime_service=external_runtime_service,
    )
