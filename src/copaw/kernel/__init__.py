# -*- coding: utf-8 -*-
"""SRK kernel module for CoPaw."""
from __future__ import annotations

from importlib import import_module

__all__ = [
    "AbsorptionAction",
    "AbsorptionCase",
    "AbsorptionContinuityContext",
    "AbsorptionSummary",
    "ActorMailboxService",
    "ActorSupervisor",
    "ActorWorker",
    "AgentDailyReport",
    "AgentProfile",
    "AgentProfileService",
    "AgentStatus",
    "BuddyOnboardingService",
    "BuddyDomainCapabilityGrowthService",
    "BuddyProjectionService",
    "DEFAULT_AGENTS",
    "ExecutorEventWritebackService",
    "GovernanceBatchResult",
    "GovernanceService",
    "GovernanceStatus",
    "MainBrainExceptionAbsorptionService",
    "MainBrainChatService",
    "MainBrainOrchestrator",
    "KernelConfig",
    "TaskDelegationService",
    "KernelDispatcher",
    "KernelResult",
    "KernelQueryExecutionService",
    "KernelTaskStore",
    "KernelToolBridge",
    "KernelTurnExecutor",
    "KernelTask",
    "RiskLevel",
    "TaskLifecycleManager",
    "TaskPhase",
]

_EXPORTS = {
    "AbsorptionCase": (".main_brain_exception_absorption", "AbsorptionCase"),
    "AbsorptionAction": (".main_brain_exception_absorption", "AbsorptionAction"),
    "AbsorptionContinuityContext": (
        ".main_brain_exception_absorption",
        "AbsorptionContinuityContext",
    ),
    "AbsorptionSummary": (".main_brain_exception_absorption", "AbsorptionSummary"),
    "ActorMailboxService": (".actor_mailbox", "ActorMailboxService"),
    "ActorSupervisor": (".actor_supervisor", "ActorSupervisor"),
    "ActorWorker": (".actor_worker", "ActorWorker"),
    "AgentDailyReport": (".agent_profile", "AgentDailyReport"),
    "AgentProfile": (".agent_profile", "AgentProfile"),
    "AgentProfileService": (".agent_profile_service", "AgentProfileService"),
    "AgentStatus": (".agent_profile", "AgentStatus"),
    "BuddyOnboardingService": (".buddy_onboarding_service", "BuddyOnboardingService"),
    "BuddyDomainCapabilityGrowthService": (
        ".buddy_domain_capability_growth",
        "BuddyDomainCapabilityGrowthService",
    ),
    "BuddyProjectionService": (".buddy_projection_service", "BuddyProjectionService"),
    "DEFAULT_AGENTS": (".agent_profile", "DEFAULT_AGENTS"),
    "ExecutorEventWritebackService": (
        ".executor_event_writeback_service",
        "ExecutorEventWritebackService",
    ),
    "GovernanceBatchResult": (".governance", "GovernanceBatchResult"),
    "GovernanceService": (".governance", "GovernanceService"),
    "GovernanceStatus": (".governance", "GovernanceStatus"),
    "KernelConfig": (".models", "KernelConfig"),
    "KernelDispatcher": (".dispatcher", "KernelDispatcher"),
    "KernelQueryExecutionService": (".query_execution", "KernelQueryExecutionService"),
    "KernelResult": (".models", "KernelResult"),
    "KernelTask": (".models", "KernelTask"),
    "KernelTaskStore": (".persistence", "KernelTaskStore"),
    "KernelToolBridge": (".tool_bridge", "KernelToolBridge"),
    "KernelTurnExecutor": (".turn_executor", "KernelTurnExecutor"),
    "MainBrainChatService": (".main_brain_chat_service", "MainBrainChatService"),
    "MainBrainExceptionAbsorptionService": (
        ".main_brain_exception_absorption",
        "MainBrainExceptionAbsorptionService",
    ),
    "MainBrainOrchestrator": (".main_brain_orchestrator", "MainBrainOrchestrator"),
    "RiskLevel": (".models", "RiskLevel"),
    "TaskDelegationService": (".delegation_service", "TaskDelegationService"),
    "TaskLifecycleManager": (".lifecycle", "TaskLifecycleManager"),
    "TaskPhase": (".models", "TaskPhase"),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, symbol = target
    module = import_module(module_name, __name__)
    return getattr(module, symbol)
