# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TypeAlias

from ..capabilities import CapabilityService
from ..evidence import EvidenceLedger
from ..environments import EnvironmentService
from ..kernel import (
    ActorMailboxService,
    ActorSupervisor,
    ActorWorker,
    GovernanceService,
    KernelDispatcher,
    KernelTaskStore,
    KernelToolBridge,
)
from ..learning import LearningService, PatchExecutor
from ..state import SQLiteStateStore
from ..state.agent_experience_service import AgentExperienceMemoryService
from ..state.work_context_service import WorkContextService
from .mcp import MCPClientManager
from .runtime_bootstrap_models import RuntimeRepositories
from .runtime_center import RuntimeCenterStateQueryService
from .runtime_events import RuntimeEventBus

RuntimeExecutionStack: TypeAlias = tuple[
    LearningService,
    GovernanceService,
    KernelTaskStore,
    KernelToolBridge,
    CapabilityService,
    KernelDispatcher,
    ActorMailboxService,
    ActorWorker,
    ActorSupervisor,
]


def build_runtime_execution_stack(
    *,
    mcp_manager: MCPClientManager,
    environment_service: EnvironmentService,
    evidence_ledger: EvidenceLedger,
    repositories: RuntimeRepositories,
    runtime_event_bus: RuntimeEventBus,
    state_query_service: RuntimeCenterStateQueryService,
    experience_memory_service: AgentExperienceMemoryService | None,
    state_store: SQLiteStateStore,
    work_context_service: WorkContextService,
    patch_executor_cls: type[PatchExecutor] = PatchExecutor,
    learning_service_cls: type[LearningService] = LearningService,
    governance_service_cls: type[GovernanceService] = GovernanceService,
    kernel_task_store_cls: type[KernelTaskStore] = KernelTaskStore,
    kernel_tool_bridge_cls: type[KernelToolBridge] = KernelToolBridge,
    capability_service_cls: type[CapabilityService] = CapabilityService,
    kernel_dispatcher_cls: type[KernelDispatcher] = KernelDispatcher,
    actor_mailbox_service_cls: type[ActorMailboxService] = ActorMailboxService,
    actor_worker_cls: type[ActorWorker] = ActorWorker,
    actor_supervisor_cls: type[ActorSupervisor] = ActorSupervisor,
) -> RuntimeExecutionStack:
    patch_executor = patch_executor_cls(
        capability_override_repository=repositories.capability_override_repository,
        agent_profile_override_repository=repositories.agent_profile_override_repository,
        goal_override_repository=repositories.goal_override_repository,
    )
    learning_service = learning_service_cls(
        patch_executor=patch_executor,
        decision_request_repository=repositories.decision_request_repository,
        task_repository=repositories.task_repository,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=runtime_event_bus,
    )
    governance_service = governance_service_cls(
        control_repository=repositories.governance_control_repository,
        decision_request_repository=repositories.decision_request_repository,
        learning_service=learning_service,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=runtime_event_bus,
        environment_service=environment_service,
    )
    kernel_task_store = kernel_task_store_cls(
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        runtime_frame_repository=repositories.runtime_frame_repository,
        decision_request_repository=repositories.decision_request_repository,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=runtime_event_bus,
        work_context_service=work_context_service,
    )
    kernel_tool_bridge = kernel_tool_bridge_cls(
        task_store=kernel_task_store,
        environment_service=environment_service,
    )
    capability_service = capability_service_cls(
        evidence_ledger=evidence_ledger,
        tool_bridge=kernel_tool_bridge,
        mcp_manager=mcp_manager,
        learning_service=learning_service,
        override_repository=repositories.capability_override_repository,
        agent_profile_override_repository=repositories.agent_profile_override_repository,
        state_store=state_store,
        environment_service=environment_service,
    )
    kernel_dispatcher = kernel_dispatcher_cls(
        task_store=kernel_task_store,
        capability_service=capability_service,
        governance_service=governance_service,
        learning_service=learning_service,
    )
    actor_mailbox_service = actor_mailbox_service_cls(
        mailbox_repository=repositories.agent_mailbox_repository,
        runtime_repository=repositories.agent_runtime_repository,
        checkpoint_repository=repositories.agent_checkpoint_repository,
        thread_binding_repository=repositories.agent_thread_binding_repository,
        kernel_dispatcher=kernel_dispatcher,
        runtime_event_bus=runtime_event_bus,
    )
    actor_worker = actor_worker_cls(
        worker_id="copaw-actor-worker",
        mailbox_service=actor_mailbox_service,
        kernel_dispatcher=kernel_dispatcher,
        environment_service=environment_service,
        agent_runtime_repository=repositories.agent_runtime_repository,
        experience_memory_service=experience_memory_service,
    )
    actor_supervisor = actor_supervisor_cls(
        runtime_repository=repositories.agent_runtime_repository,
        mailbox_service=actor_mailbox_service,
        worker=actor_worker,
        runtime_event_bus=runtime_event_bus,
    )
    governance_service.set_kernel_dispatcher(kernel_dispatcher)
    state_query_service.set_kernel_dispatcher(kernel_dispatcher)
    return (
        learning_service,
        governance_service,
        kernel_task_store,
        kernel_tool_bridge,
        capability_service,
        kernel_dispatcher,
        actor_mailbox_service,
        actor_worker,
        actor_supervisor,
    )
