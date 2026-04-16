# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable
from typing import TYPE_CHECKING

from ..config import get_config_file_signature, load_config, save_config
from ..evidence import EvidenceLedger, EvidenceRecord
from .capability_discovery import CapabilityDiscoveryService
from .catalog import CapabilityCatalogFacade, summarize_capability_mounts
from .external_adapter_execution import ExternalAdapterExecution
from .external_runtime_execution import ExternalRuntimeExecution
from .execution import CapabilityExecutionFacade
from .models import CapabilityMount, CapabilitySummary
from .registry import CapabilityRegistry
from .skill_service import CapabilitySkillService, default_skill_service
from .system_handlers import SystemCapabilityHandler

if TYPE_CHECKING:
    from ..app.channels import ChannelManager
    from ..app.mcp import MCPClientManager
    from ..goals import GoalService
    from ..kernel import KernelToolBridge, KernelTurnExecutor, TaskDelegationService
    from ..kernel.agent_profile import AgentProfile
    from ..kernel.agent_profile_service import AgentProfileService
    from ..kernel.models import KernelTask
    from ..learning import LearningService
    from ..state import SQLiteStateStore
    from ..state.repositories import (
        SqliteAgentProfileOverrideRepository,
        SqliteCapabilityOverrideRepository,
    )


class CapabilityService:
    def __init__(
        self,
        *,
        registry: CapabilityRegistry | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        tool_bridge: "KernelToolBridge | None" = None,
        mcp_manager: "MCPClientManager | None" = None,
        channel_manager: "ChannelManager | None" = None,
        turn_executor: "KernelTurnExecutor | None" = None,
        goal_service: "GoalService | None" = None,
        learning_service: "LearningService | None" = None,
        routine_service: object | None = None,
        fixed_sop_service: object | None = None,
        override_repository: "SqliteCapabilityOverrideRepository | None" = None,
        agent_profile_service: "AgentProfileService | None" = None,
        agent_profile_override_repository: "SqliteAgentProfileOverrideRepository | None" = None,
        delegation_service: "TaskDelegationService | None" = None,
        actor_mailbox_service: object | None = None,
        actor_supervisor: object | None = None,
        industry_service: object | None = None,
        skill_service: CapabilitySkillService | None = None,
        state_store: "SQLiteStateStore | None" = None,
        external_runtime_service: object | None = None,
        environment_service: object | None = None,
        runtime_provider: object | None = None,
        cron_manager: object | None = None,
        load_config_fn: Callable[[], Any] | None = None,
        save_config_fn: Callable[[Any], None] | None = None,
        config_signature_fn: Callable[[], object] | None = None,
    ) -> None:
        self._registry = registry or CapabilityRegistry()
        self._evidence_ledger = evidence_ledger
        self._tool_bridge = tool_bridge
        self._mcp_manager = mcp_manager
        self._channel_manager = channel_manager
        self._turn_executor = turn_executor
        self._goal_service = goal_service
        self._learning_service = learning_service
        self._routine_service = routine_service
        self._fixed_sop_service = fixed_sop_service
        self._override_repository = override_repository
        self._agent_profile_service = agent_profile_service
        self._agent_profile_override_repository = agent_profile_override_repository
        self._delegation_service = delegation_service
        self._actor_mailbox_service = actor_mailbox_service
        self._actor_supervisor = actor_supervisor
        self._industry_service = industry_service
        self._skill_service = skill_service or default_skill_service
        self._state_store = state_store
        self._external_runtime_service = external_runtime_service
        self._environment_service = environment_service
        self._runtime_provider = runtime_provider
        self._cron_manager = cron_manager
        self._load_config_fn = load_config_fn or (lambda: load_config())
        self._save_config_fn = save_config_fn or (lambda config: save_config(config))
        self._config_signature_fn = config_signature_fn
        if self._config_signature_fn is None and load_config_fn is None:
            self._config_signature_fn = lambda: (
                get_config_file_signature(),
                id(load_config),
            )

        self._catalog = CapabilityCatalogFacade(
            registry=self._registry,
            load_config_fn=self._load_config_fn,
            save_config_fn=self._save_config_fn,
            config_signature_fn=self._config_signature_fn,
            skill_service=self._skill_service,
            override_repository=self._override_repository,
            agent_profile_service=self._agent_profile_service,
            agent_profile_override_repository=self._agent_profile_override_repository,
        )
        self._discovery_service = CapabilityDiscoveryService(
            capability_service=self,
            agent_profile_service=self._agent_profile_service,
            state_store=self._state_store,
        )
        self._system_handler = SystemCapabilityHandler(
            get_capability_fn=self.get_capability,
            set_capability_enabled_fn=self.set_capability_enabled,
            delete_capability_fn=self.delete_capability,
            invalidate_capability_cache_fn=self.invalidate_catalog_cache,
            resolve_agent_profile_fn=self._resolve_agent_profile,
            load_config_fn=self._load_config_fn,
            save_config_fn=self._save_config_fn,
            skill_service=self._skill_service,
            channel_manager=self._channel_manager,
            turn_executor=self._turn_executor,
            goal_service=self._goal_service,
            learning_service=self._learning_service,
            routine_service=self._routine_service,
            fixed_sop_service=self._fixed_sop_service,
            agent_profile_service=self._agent_profile_service,
            agent_profile_override_repository=self._agent_profile_override_repository,
            delegation_service=self._delegation_service,
            industry_service=self._industry_service,
            actor_mailbox_service=self._actor_mailbox_service,
            actor_supervisor=self._actor_supervisor,
            capability_discovery_service=self._discovery_service,
            environment_service=self._environment_service,
            cron_manager=self._cron_manager,
        )
        self._execution = CapabilityExecutionFacade(
            get_capability_fn=self.get_capability,
            resolve_agent_profile_fn=self._resolve_agent_profile,
            resolve_explicit_capability_allowlist_fn=(
                self._resolve_explicit_capability_allowlist
            ),
            is_mount_accessible_fn=self._is_mount_accessible,
            append_execution_evidence_fn=self._append_execution_evidence,
            skill_service=self._skill_service,
            external_adapter_execution=ExternalAdapterExecution(
                mcp_manager=self._mcp_manager,
                environment_service=self._environment_service,
                provider_runtime_facade=self._runtime_provider,
            ),
            external_runtime_execution=(
                ExternalRuntimeExecution(
                    runtime_service=self._external_runtime_service,
                )
                if self._external_runtime_service is not None
                else None
            ),
            tool_bridge=self._tool_bridge,
            capability_service=self,
            state_store=self._state_store,
            environment_service=self._environment_service,
            mcp_manager=self._mcp_manager,
            system_handler=self._system_handler,
        )

    def list_capabilities(
        self,
        *,
        kind: str | None = None,
        enabled_only: bool = False,
    ) -> list[CapabilityMount]:
        return self._catalog.list_capabilities(kind=kind, enabled_only=enabled_only)

    def list_public_capabilities(
        self,
        *,
        kind: str | None = None,
        enabled_only: bool = False,
    ) -> list[CapabilityMount]:
        return self._catalog.list_public_capabilities(kind=kind, enabled_only=enabled_only)

    def list_public_capability_inventory(
        self,
        *,
        kind: str | None = None,
        enabled_only: bool = False,
    ) -> tuple[list[CapabilityMount], CapabilitySummary]:
        mounts = self.list_public_capabilities(kind=kind, enabled_only=enabled_only)
        return mounts, summarize_capability_mounts(mounts)

    def get_capability(self, capability_id: str) -> CapabilityMount | None:
        return self._catalog.get_capability(capability_id)

    def get_public_capability(self, capability_id: str) -> CapabilityMount | None:
        return self._catalog.get_public_capability(capability_id)

    def list_capability_lookup(self) -> dict[str, CapabilityMount]:
        return self._catalog.list_capability_lookup()

    def summarize(self) -> CapabilitySummary:
        return self._catalog.summarize()

    def summarize_public(self) -> CapabilitySummary:
        _mounts, summary = self.list_public_capability_inventory()
        return summary

    def invalidate_catalog_cache(self) -> None:
        self._catalog.invalidate_caches()

    def get_discovery_service(self) -> CapabilityDiscoveryService:
        return self._discovery_service

    def set_tool_bridge(self, tool_bridge: "KernelToolBridge | None") -> None:
        self._tool_bridge = tool_bridge
        self._execution.set_tool_bridge(tool_bridge)

    def set_evidence_ledger(self, evidence_ledger: EvidenceLedger | None) -> None:
        self._evidence_ledger = evidence_ledger

    def set_mcp_manager(self, mcp_manager: "MCPClientManager | None") -> None:
        self._mcp_manager = mcp_manager
        self._execution.set_mcp_manager(mcp_manager)

    def set_environment_service(self, environment_service: object | None) -> None:
        self._environment_service = environment_service
        self._system_handler.set_environment_service(environment_service)
        self._execution.set_environment_service(environment_service)

    def set_runtime_provider(self, runtime_provider: object | None) -> None:
        self._runtime_provider = runtime_provider
        self._execution.set_runtime_provider(runtime_provider)

    def set_channel_manager(self, channel_manager: "ChannelManager | None") -> None:
        self._channel_manager = channel_manager
        self._system_handler.set_channel_manager(channel_manager)

    def set_turn_executor(
        self,
        turn_executor: "KernelTurnExecutor | None",
    ) -> None:
        self._turn_executor = turn_executor
        self._system_handler.set_turn_executor(turn_executor)

    def set_goal_service(self, goal_service: "GoalService | None") -> None:
        self._goal_service = goal_service
        self._system_handler.set_goal_service(goal_service)

    def set_learning_service(self, learning_service: "LearningService | None") -> None:
        self._learning_service = learning_service
        self._system_handler.set_learning_service(learning_service)

    def set_routine_service(self, routine_service: object | None) -> None:
        self._routine_service = routine_service
        self._system_handler.set_routine_service(routine_service)

    def set_fixed_sop_service(self, fixed_sop_service: object | None) -> None:
        self._fixed_sop_service = fixed_sop_service
        self._system_handler.set_fixed_sop_service(fixed_sop_service)

    def set_override_repository(
        self,
        override_repository: "SqliteCapabilityOverrideRepository | None",
    ) -> None:
        self._override_repository = override_repository
        self._catalog.set_override_repository(override_repository)

    def set_agent_profile_service(
        self,
        agent_profile_service: "AgentProfileService | None",
    ) -> None:
        self._agent_profile_service = agent_profile_service
        self._catalog.set_agent_profile_service(agent_profile_service)
        self._discovery_service.set_agent_profile_service(agent_profile_service)
        self._system_handler.set_agent_profile_service(agent_profile_service)

    def set_agent_profile_override_repository(
        self,
        override_repository: "SqliteAgentProfileOverrideRepository | None",
    ) -> None:
        self._agent_profile_override_repository = override_repository
        self._catalog.set_agent_profile_override_repository(override_repository)
        self._system_handler.set_agent_profile_override_repository(override_repository)

    def set_delegation_service(
        self,
        delegation_service: "TaskDelegationService | None",
    ) -> None:
        self._delegation_service = delegation_service
        self._system_handler.set_delegation_service(delegation_service)

    def set_industry_service(self, industry_service: object | None) -> None:
        self._industry_service = industry_service
        self._system_handler.set_industry_service(industry_service)

    def set_state_store(self, state_store: "SQLiteStateStore | None") -> None:
        self._state_store = state_store
        self._discovery_service.set_state_store(state_store)
        self._system_handler.set_state_store(state_store)

    def set_actor_mailbox_service(self, actor_mailbox_service: object | None) -> None:
        self._actor_mailbox_service = actor_mailbox_service
        self._system_handler.set_actor_mailbox_service(actor_mailbox_service)

    def set_actor_supervisor(self, actor_supervisor: object | None) -> None:
        self._actor_supervisor = actor_supervisor
        self._system_handler.set_actor_supervisor(actor_supervisor)

    def set_cron_manager(self, cron_manager: object | None) -> None:
        self._cron_manager = cron_manager
        self._system_handler.set_cron_manager(cron_manager)

    def list_accessible_capabilities(
        self,
        *,
        agent_id: str | None,
        kind: str | None = None,
        enabled_only: bool = False,
    ) -> list[CapabilityMount]:
        return self._catalog.list_accessible_capabilities(
            agent_id=agent_id,
            kind=kind,
            enabled_only=enabled_only,
        )

    def toggle_capability(self, capability_id: str) -> dict[str, object]:
        return self._catalog.toggle_capability(capability_id)

    def set_capability_enabled(
        self,
        capability_id: str,
        *,
        enabled: bool,
    ) -> dict[str, object]:
        return self._catalog.set_capability_enabled(capability_id, enabled=enabled)

    def delete_capability(self, capability_id: str) -> dict[str, object]:
        return self._catalog.delete_capability(capability_id)

    def list_skill_specs(self, *, enabled_only: bool = False) -> list[dict[str, object]]:
        return self._catalog.list_skill_specs(enabled_only=enabled_only)

    def list_available_skill_specs(self) -> list[dict[str, object]]:
        return self._catalog.list_available_skill_specs()

    def install_skill_from_hub(self, **kwargs: object) -> object:
        return self._skill_service.install_skill_from_hub(**kwargs)

    def load_skill_file(
        self,
        *,
        skill_name: str,
        file_path: str,
        source: str,
    ) -> str | None:
        return self._skill_service.load_skill_file(
            skill_name=skill_name,
            file_path=file_path,
            source=source,
        )

    def sync_skills_to_working_dir(
        self,
        *,
        skill_names: list[str] | None = None,
        force: bool = False,
    ) -> tuple[int, int]:
        return self._skill_service.sync_to_working_dir(
            skill_names=skill_names,
            force=force,
        )

    def list_mcp_client_infos(self) -> list[dict[str, object]]:
        return self._catalog.list_mcp_client_infos()

    def get_mcp_client_info(self, client_key: str) -> dict[str, object] | None:
        return self._catalog.get_mcp_client_info(client_key)

    def get_mcp_client_config(self, client_key: str):
        return self._catalog.get_mcp_client_config(client_key)

    def resolve_executor(self, capability_id: str):
        return self._execution.resolve_executor(capability_id)

    async def execute_task(self, task: "KernelTask") -> dict[str, object]:
        return await self._execution.execute_task(task)

    async def execute_task_batch(
        self,
        tasks: list["KernelTask"],
    ) -> list[dict[str, object]]:
        return await self._execution.execute_task_batch(tasks)

    def _append_execution_evidence(
        self,
        *,
        task: "KernelTask",
        mount: CapabilityMount,
        result_summary: str,
        status: str,
        metadata: dict[str, object],
    ) -> str | None:
        if self._evidence_ledger is None:
            return None
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=task.id,
                actor_ref=mount.id,
                environment_ref=task.environment_ref,
                capability_ref=mount.id,
                risk_level=task.risk_level,
                action_summary=f"执行能力 {mount.id}",
                result_summary=result_summary,
                status=status,
                metadata={
                    **metadata,
                    "trace_id": task.trace_id,
                    "trace_task_id": task.id,
                    "trace_owner_agent_id": task.owner_agent_id,
                },
            ),
        )
        return record.id

    def _apply_overrides(
        self,
        mounts: list[CapabilityMount],
    ) -> list[CapabilityMount]:
        return self._catalog._apply_overrides(mounts)

    def _resolve_agent_profile(self, agent_id: str | None) -> "AgentProfile | None":
        return self._catalog._resolve_agent_profile(agent_id)

    def _resolve_explicit_capability_allowlist(
        self,
        agent_id: str | None,
    ) -> set[str] | None:
        return self._catalog._resolve_explicit_capability_allowlist(agent_id)

    def _is_mount_accessible(
        self,
        mount: CapabilityMount,
        *,
        agent_id: str | None,
        profile: "AgentProfile | None",
        explicit_allowlist: set[str] | None,
    ) -> bool:
        return self._catalog._is_mount_accessible(
            mount,
            agent_id=agent_id,
            profile=profile,
            explicit_allowlist=explicit_allowlist,
        )
