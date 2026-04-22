# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
from typing import Any, Callable

from .skill_service import CapabilitySkillService
from .system_actor_handlers import SystemActorCapabilityFacade
from .system_config_handlers import SystemConfigCapabilityFacade
from .system_discovery_handlers import SystemCapabilityDiscoveryFacade
from .system_dispatch import SystemDispatchFacade
from .system_learning_handlers import SystemLearningCapabilityFacade
from .system_routine_handlers import SystemRoutineCapabilityFacade
from .system_schedule_handlers import SystemScheduleCapabilityFacade
from .system_skill_handlers import SystemSkillCapabilityFacade
from .system_team_handlers import SystemTeamCapabilityFacade

_ACTOR_CAPABILITIES = {
    "system:enqueue_task",
    "system:pause_actor",
    "system:resume_actor",
    "system:cancel_actor_task",
    "system:retry_actor_mailbox",
    "system:list_teammates",
}

_CONFIG_CAPABILITIES = {
    "system:set_capability_enabled",
    "system:delete_capability",
    "system:update_channels_config",
    "system:update_channel_config",
    "system:update_heartbeat_config",
    "system:update_agents_llm_routing",
    "system:update_agents_running_config",
    "system:create_mcp_client",
    "system:update_mcp_client",
}

_SKILL_CAPABILITIES = {
    "system:create_skill",
    "system:install_hub_skill",
    "system:trial_remote_skill_assignment",
    "system:apply_capability_lifecycle",
}

_DISCOVERY_CAPABILITIES = {
    "system:discover_capabilities",
}

_SCHEDULE_CAPABILITIES = {
    "system:create_schedule",
    "system:update_schedule",
    "system:delete_schedule",
    "system:pause_schedule",
    "system:resume_schedule",
    "system:run_schedule",
}


class SystemCapabilityHandler:
    def __init__(
        self,
        *,
        get_capability_fn: Callable[[str], object | None],
        set_capability_enabled_fn: Callable[..., dict[str, object]],
        delete_capability_fn: Callable[[str], dict[str, object]],
        invalidate_capability_cache_fn: Callable[[], None] | None,
        resolve_agent_profile_fn: Callable[[str | None], object | None],
        load_config_fn: Callable[[], Any],
        save_config_fn: Callable[[Any], None],
        skill_service: CapabilitySkillService,
        channel_manager: object | None = None,
        turn_executor: object | None = None,
        goal_service: object | None = None,
        learning_service: object | None = None,
        routine_service: object | None = None,
        fixed_sop_service: object | None = None,
        agent_profile_service: object | None = None,
        agent_profile_override_repository: object | None = None,
        industry_service: object | None = None,
        actor_mailbox_service: object | None = None,
        actor_supervisor: object | None = None,
        capability_discovery_service: object | None = None,
        environment_service: object | None = None,
        cron_manager: object | None = None,
    ) -> None:
        self._dispatch = SystemDispatchFacade(
            channel_manager=channel_manager,
            turn_executor=turn_executor,
        )
        self._team = SystemTeamCapabilityFacade(
            get_capability_fn=get_capability_fn,
            resolve_agent_profile_fn=resolve_agent_profile_fn,
            goal_service=goal_service,
            agent_profile_service=agent_profile_service,
            agent_profile_override_repository=agent_profile_override_repository,
            industry_service=industry_service,
        )
        self._actor = SystemActorCapabilityFacade(
            actor_mailbox_service=actor_mailbox_service,
            actor_supervisor=actor_supervisor,
        )
        self._config = SystemConfigCapabilityFacade(
            load_config_fn=load_config_fn,
            save_config_fn=save_config_fn,
            set_capability_enabled_fn=set_capability_enabled_fn,
            delete_capability_fn=delete_capability_fn,
            invalidate_capability_cache_fn=invalidate_capability_cache_fn,
        )
        self._skills = SystemSkillCapabilityFacade(
            skill_service=skill_service,
            get_capability_fn=get_capability_fn,
            resolve_agent_profile_fn=resolve_agent_profile_fn,
            agent_profile_service=agent_profile_service,
            industry_service=industry_service,
            apply_role_handler=self._team.handle_apply_role,
        )
        self._discovery = SystemCapabilityDiscoveryFacade(
            capability_discovery_service=capability_discovery_service,
        )
        self._routine = SystemRoutineCapabilityFacade(
            routine_service=routine_service,
            fixed_sop_service=fixed_sop_service,
        )
        self._schedule = SystemScheduleCapabilityFacade(
            cron_manager=cron_manager,
        )
        self._learning = SystemLearningCapabilityFacade(
            learning_service=learning_service,
        )
        self._environment_service = environment_service

    def set_channel_manager(self, channel_manager: object | None) -> None:
        self._dispatch.set_channel_manager(channel_manager)

    def set_turn_executor(self, turn_executor: object | None) -> None:
        self._dispatch.set_turn_executor(turn_executor)

    def set_goal_service(self, goal_service: object | None) -> None:
        self._team.set_goal_service(goal_service)

    def set_learning_service(self, learning_service: object | None) -> None:
        self._learning.set_learning_service(learning_service)

    def set_routine_service(self, routine_service: object | None) -> None:
        self._routine.set_routine_service(routine_service)

    def set_fixed_sop_service(self, fixed_sop_service: object | None) -> None:
        self._routine.set_fixed_sop_service(fixed_sop_service)

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._team.set_agent_profile_service(agent_profile_service)
        self._skills.set_agent_profile_service(agent_profile_service)

    def set_agent_profile_override_repository(
        self,
        override_repository: object | None,
    ) -> None:
        self._team.set_agent_profile_override_repository(override_repository)

    def set_industry_service(self, industry_service: object | None) -> None:
        self._team.set_industry_service(industry_service)
        self._skills.set_industry_service(industry_service)

    def set_state_store(self, state_store: object | None) -> None:
        self._discovery.set_state_store(state_store)

    def set_cron_manager(self, cron_manager: object | None) -> None:
        self._schedule.set_cron_manager(cron_manager)

    def set_capability_discovery_service(
        self,
        capability_discovery_service: object | None,
    ) -> None:
        self._discovery.set_capability_discovery_service(capability_discovery_service)

    def set_environment_service(self, environment_service: object | None) -> None:
        self._environment_service = environment_service

    def set_actor_mailbox_service(self, actor_mailbox_service: object | None) -> None:
        self._actor.set_actor_mailbox_service(actor_mailbox_service)

    def set_actor_supervisor(self, actor_supervisor: object | None) -> None:
        self._actor.set_actor_supervisor(actor_supervisor)

    async def execute(
        self,
        capability_id: str,
        *,
        payload: dict[str, object] | None = None,
        **kwargs,
    ) -> dict[str, object]:
        _ = kwargs
        resolved_payload = payload or {}

        if capability_id == "system:send_channel_text":
            return await self._dispatch.handle_send_channel_text(resolved_payload)

        if capability_id == "system:dispatch_command":
            return await self._dispatch.execute_turn_dispatch(
                resolved_payload,
                summary="Dispatched command through the kernel-owned command execution service.",
            )

        if capability_id == "system:dispatch_query":
            return await self._dispatch.execute_turn_dispatch(
                resolved_payload,
                summary="Dispatched query through the kernel-owned query execution service.",
            )

        if capability_id == "system:replay_routine":
            return await self._routine.handle_replay_routine(resolved_payload)

        if capability_id == "system:run_fixed_sop":
            return await self._routine.handle_run_fixed_sop(resolved_payload)

        if capability_id == "system:apply_role":
            return await self._team.handle_apply_role(resolved_payload)

        if capability_id == "system:update_industry_team":
            return await self._team.handle_update_industry_team(resolved_payload)

        if capability_id == "system:run_operating_cycle":
            return await self._team.handle_run_operating_cycle(resolved_payload)

        if capability_id == "system:run_host_recovery":
            return await self._execute_host_recovery(resolved_payload)

        if capability_id in _ACTOR_CAPABILITIES:
            return await self._actor.execute(capability_id, resolved_payload)

        if capability_id in _SKILL_CAPABILITIES:
            return await self._execute_async_skill_capability(capability_id, resolved_payload)

        if capability_id in _DISCOVERY_CAPABILITIES:
            return await self._discovery.handle_discover_capabilities(resolved_payload)

        if capability_id in _SCHEDULE_CAPABILITIES:
            return await self._schedule.execute(capability_id, resolved_payload)

        if capability_id in _CONFIG_CAPABILITIES:
            return self._execute_config_capability(capability_id, resolved_payload)

        return self._learning.execute(capability_id, resolved_payload)

    async def _execute_host_recovery(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._environment_service is None:
            return {"success": False, "error": "Environment service is not available"}
        runner = getattr(self._environment_service, "run_host_recovery_cycle", None)
        if not callable(runner):
            return {
                "success": False,
                "error": "Environment service cannot run host recovery",
            }
        result = runner(
            limit=(
                int(resolved_payload["limit"])
                if isinstance(resolved_payload.get("limit"), int)
                else None
            ),
            allow_cross_process_recovery=bool(
                resolved_payload.get("allow_cross_process_recovery", False),
            ),
            actor=(
                str(resolved_payload.get("actor")).strip()
                if isinstance(resolved_payload.get("actor"), str)
                and str(resolved_payload.get("actor")).strip()
                else "system:automation"
            ),
            source=(
                str(resolved_payload.get("source")).strip()
                if isinstance(resolved_payload.get("source"), str)
                and str(resolved_payload.get("source")).strip()
                else None
            ),
        )
        if inspect.isawaitable(result):
            result = await result
        host_recovery = result if isinstance(result, dict) else {}
        executed = int(host_recovery.get("executed") or 0)
        return {
            "success": True,
            "summary": f"Host recovery processed {executed} actionable event(s).",
            "host_recovery": host_recovery,
            "evidence_metadata": {
                "host_recovery": host_recovery,
            },
        }

    def _execute_skill_capability(
        self,
        capability_id: str,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if capability_id == "system:create_skill":
            return self._skills.handle_create_skill(resolved_payload)
        if capability_id == "system:install_hub_skill":
            return self._skills.handle_install_hub_skill(resolved_payload)
        return {
            "success": False,
            "error": f"Unsupported skill capability '{capability_id}'",
        }

    async def _execute_async_skill_capability(
        self,
        capability_id: str,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if capability_id == "system:trial_remote_skill_assignment":
            return await self._skills.handle_trial_remote_skill_assignment(resolved_payload)
        if capability_id == "system:apply_capability_lifecycle":
            return await self._skills.handle_apply_capability_lifecycle(resolved_payload)
        return self._execute_skill_capability(capability_id, resolved_payload)

    async def execute_turn_dispatch(
        self,
        resolved_payload: dict[str, object],
        *,
        summary: str,
    ) -> dict[str, object]:
        return await self._dispatch.execute_turn_dispatch(
            resolved_payload,
            summary=summary,
        )

    def _execute_config_capability(
        self,
        capability_id: str,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if capability_id == "system:set_capability_enabled":
            return self._config.handle_set_capability_enabled(resolved_payload)
        if capability_id == "system:delete_capability":
            return self._config.handle_delete_capability(resolved_payload)
        if capability_id == "system:update_channels_config":
            return self._config.handle_update_channels_config(resolved_payload)
        if capability_id == "system:update_channel_config":
            return self._config.handle_update_channel_config(resolved_payload)
        if capability_id == "system:update_heartbeat_config":
            return self._config.handle_update_heartbeat_config(resolved_payload)
        if capability_id == "system:update_agents_llm_routing":
            return self._config.handle_update_agents_llm_routing(resolved_payload)
        if capability_id == "system:update_agents_running_config":
            return self._config.handle_update_agents_running_config(resolved_payload)
        if capability_id == "system:create_mcp_client":
            return self._config.handle_create_mcp_client(resolved_payload)
        if capability_id == "system:update_mcp_client":
            return self._config.handle_update_mcp_client(resolved_payload)
        return {
            "success": False,
            "error": f"Unsupported config capability '{capability_id}'",
        }
