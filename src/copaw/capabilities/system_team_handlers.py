# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from ..industry.models import (
    IndustryDraftGoal,
    IndustryDraftSchedule,
    IndustryRoleBlueprint,
)
from ..state import AgentProfileOverrideRecord
from .execution_support import _string_value


class SystemTeamCapabilityFacade:
    def __init__(
        self,
        *,
        get_capability_fn: Callable[[str], object | None],
        resolve_agent_profile_fn: Callable[[str | None], object | None],
        goal_service: object | None = None,
        agent_profile_service: object | None = None,
        agent_profile_override_repository: object | None = None,
        industry_service: object | None = None,
    ) -> None:
        self._get_capability = get_capability_fn
        self._resolve_agent_profile = resolve_agent_profile_fn
        _ = goal_service
        self._agent_profile_service = agent_profile_service
        self._agent_profile_override_repository = agent_profile_override_repository
        self._industry_service = industry_service

    def set_goal_service(self, goal_service: object | None) -> None:
        _ = goal_service

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_agent_profile_override_repository(
        self,
        override_repository: object | None,
    ) -> None:
        self._agent_profile_override_repository = override_repository

    def set_industry_service(self, industry_service: object | None) -> None:
        self._industry_service = industry_service

    async def handle_apply_role(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._agent_profile_override_repository is None:
            return {
                "success": False,
                "error": "Agent profile override repository is not available",
            }

        role_text = str(resolved_payload.get("role_text") or "").strip()
        role_name_input = _string_value(resolved_payload.get("role_name"))
        role_summary_input = _string_value(resolved_payload.get("role_summary"))
        capabilities_provided = "capabilities" in resolved_payload
        raw_capabilities = resolved_payload.get("capabilities")
        requested_capabilities: list[str] | None = None
        if capabilities_provided:
            if raw_capabilities is None:
                requested_capabilities = []
            elif not isinstance(raw_capabilities, list):
                return {
                    "success": False,
                    "error": "capabilities must be a list of strings",
                }
            else:
                requested_capabilities = []
                for item in raw_capabilities:
                    if not isinstance(item, str):
                        return {
                            "success": False,
                            "error": "capabilities must be a list of strings",
                        }
                    normalized = item.strip()
                    if normalized and normalized not in requested_capabilities:
                        requested_capabilities.append(normalized)

        has_role_update = bool(role_text or role_name_input or role_summary_input)
        if not has_role_update and not capabilities_provided:
            return {"success": False, "error": "role_text or capabilities is required"}

        capability_assignment_mode = str(
            resolved_payload.get("capability_assignment_mode")
            or resolved_payload.get("capabilities_mode")
            or "replace",
        ).strip().lower()
        if capability_assignment_mode not in {"replace", "merge"}:
            return {
                "success": False,
                "error": "capability_assignment_mode must be 'replace' or 'merge'",
            }

        agent_id = str(
            resolved_payload.get("agent_id")
            or resolved_payload.get("target_agent_id")
            or resolved_payload.get("owner_agent_id")
            or "copaw-agent-runner",
        )
        invalid_capabilities = [
            capability_name
            for capability_name in (requested_capabilities or [])
            if self._get_capability(capability_name) is None
        ]
        if invalid_capabilities:
            names = ", ".join(sorted(invalid_capabilities))
            return {
                "success": False,
                "error": f"Unknown capability ids: {names}",
            }

        current = self._agent_profile_override_repository.get_override(agent_id)
        update: dict[str, object] = {}
        if has_role_update:
            role_name = role_name_input or (
                role_text.splitlines()[0].strip()[:120] if role_text else None
            )
            role_summary = role_summary_input or role_text or None
            if role_name is not None:
                update["role_name"] = role_name
            if role_summary is not None:
                update["role_summary"] = role_summary

        if capabilities_provided:
            allowlist_builder = getattr(
                self._agent_profile_service,
                "build_capability_allowlist",
                None,
            )
            if callable(allowlist_builder):
                update["capabilities"] = allowlist_builder(
                    agent_id=agent_id,
                    capabilities=requested_capabilities,
                    mode=capability_assignment_mode,
                )
            else:
                merged_capabilities = list(requested_capabilities or [])
                if capability_assignment_mode == "merge" and current is not None:
                    existing = [
                        str(capability).strip()
                        for capability in (current.capabilities or [])
                        if str(capability).strip()
                    ]
                    for capability_name in existing:
                        if capability_name not in merged_capabilities:
                            merged_capabilities.insert(0, capability_name)
                update["capabilities"] = merged_capabilities

        reason = _string_value(resolved_payload.get("reason")) or "system:apply_role"
        update["reason"] = reason
        if current is not None:
            override = current.model_copy(update=update)
        else:
            seed_profile = self._resolve_agent_profile(agent_id)
            override = AgentProfileOverrideRecord(
                agent_id=agent_id,
                name=_string_value(getattr(seed_profile, "name", None)),
                role_name=(
                    update.get("role_name")
                    if isinstance(update.get("role_name"), str)
                    else _string_value(getattr(seed_profile, "role_name", None))
                ),
                role_summary=(
                    update.get("role_summary")
                    if isinstance(update.get("role_summary"), str)
                    else _string_value(getattr(seed_profile, "role_summary", None))
                ),
                industry_instance_id=_string_value(
                    getattr(seed_profile, "industry_instance_id", None),
                ),
                industry_role_id=_string_value(
                    getattr(seed_profile, "industry_role_id", None),
                ),
                capabilities=(
                    list(update.get("capabilities"))
                    if isinstance(update.get("capabilities"), list)
                    else None
                ),
                reason=reason,
            )
        stored = self._agent_profile_override_repository.upsert_override(override)
        sync_runtime_capability_override = getattr(
            self._industry_service,
            "sync_agent_runtime_capability_override",
            None,
        )
        if capabilities_provided and callable(sync_runtime_capability_override):
            sync_runtime_capability_override(
                agent_id=agent_id,
                capability_ids=list(stored.capabilities or []),
            )
        if has_role_update and capabilities_provided:
            summary = (
                f"Updated role/profile and capability allowlist for agent '{agent_id}'."
            )
        elif has_role_update:
            summary = f"Applied role/profile override to agent '{agent_id}'."
        else:
            summary = f"Updated capability allowlist for agent '{agent_id}'."
        return {
            "success": True,
            "summary": summary,
            "agent_id": agent_id,
            "role_name": stored.role_name,
            "role_summary": stored.role_summary,
            "capabilities": list(stored.capabilities or []),
            "capability_assignment_mode": capability_assignment_mode,
        }

    async def handle_update_industry_team(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._industry_service is None:
            return {"success": False, "error": "Industry service is not available"}

        instance_id = _string_value(
            resolved_payload.get("instance_id")
            or resolved_payload.get("industry_instance_id"),
        )
        if not instance_id:
            return {"success": False, "error": "instance_id is required"}

        operation = _string_value(resolved_payload.get("operation")) or "add-role"

        detail_getter = getattr(self._industry_service, "get_instance_detail", None)
        detail = detail_getter(instance_id) if callable(detail_getter) else None
        if detail is None:
            return {
                "success": False,
                "error": f"Industry instance '{instance_id}' not found",
            }

        raw_role = resolved_payload.get("role")
        role: IndustryRoleBlueprint | None = None
        if isinstance(raw_role, dict):
            try:
                role = IndustryRoleBlueprint.model_validate(raw_role)
            except Exception as exc:
                return {"success": False, "error": f"Invalid role payload: {exc}"}

        team = getattr(detail, "team", None)
        existing_agents = list(getattr(team, "agents", []) or [])
        existing_role = (
            next(
                (
                    agent
                    for agent in existing_agents
                    if (
                        role is not None
                        and (
                            _string_value(getattr(agent, "role_id", None)) == role.role_id
                            or _string_value(getattr(agent, "agent_id", None)) == role.agent_id
                        )
                    )
                ),
                None,
            )
            if role is not None
            else None
        )

        if operation == "promote-role":
            promote_role = getattr(
                self._industry_service,
                "promote_role_in_instance_team",
                None,
            )
            if not callable(promote_role):
                return {
                    "success": False,
                    "error": "Industry service does not support team role promotion",
                }
            target_role_id = _string_value(resolved_payload.get("role_id")) or (
                role.role_id if role is not None else None
            )
            target_agent_id = _string_value(resolved_payload.get("agent_id")) or (
                role.agent_id if role is not None else None
            )
            try:
                promoted_detail = promote_role(
                    instance_id,
                    role=role,
                    role_id=target_role_id,
                    agent_id=target_agent_id,
                )
            except KeyError as exc:
                return {"success": False, "error": str(exc).strip("'")}
            except ValueError as exc:
                return {"success": False, "error": str(exc)}
            promoted_role = next(
                (
                    agent
                    for agent in promoted_detail.team.agents
                    if _string_value(getattr(agent, "role_id", None)) == target_role_id
                    or _string_value(getattr(agent, "agent_id", None)) == target_agent_id
                ),
                None,
            )
            return {
                "success": True,
                "summary": (
                    f"Promoted role '{target_role_id or target_agent_id}' to a career seat "
                    f"inside industry instance '{instance_id}'."
                ),
                "instance_id": instance_id,
                "role_id": _string_value(getattr(promoted_role, "role_id", None)) or target_role_id,
                "agent_id": _string_value(getattr(promoted_role, "agent_id", None)) or target_agent_id,
                "employment_mode": _string_value(
                    getattr(promoted_role, "employment_mode", None),
                )
                or "career",
                "routes": {
                    "industry": f"/api/runtime-center/industry/{instance_id}",
                    "agent": (
                        f"/api/runtime-center/agents/{_string_value(getattr(promoted_role, 'agent_id', None))}"
                        if promoted_role is not None
                        and _string_value(getattr(promoted_role, "agent_id", None))
                        else None
                    ),
                },
            }

        if operation == "retire-role":
            retire_role = getattr(
                self._industry_service,
                "retire_role_from_instance_team",
                None,
            )
            if not callable(retire_role):
                return {
                    "success": False,
                    "error": "Industry service does not support team role retirement",
                }
            target_role_id = _string_value(resolved_payload.get("role_id")) or (
                role.role_id if role is not None else None
            )
            target_agent_id = _string_value(resolved_payload.get("agent_id")) or (
                role.agent_id if role is not None else None
            )
            try:
                retire_role(
                    instance_id,
                    role_id=target_role_id,
                    agent_id=target_agent_id,
                    force=bool(resolved_payload.get("force", False)),
                )
            except KeyError as exc:
                return {"success": False, "error": str(exc).strip("'")}
            except ValueError as exc:
                return {"success": False, "error": str(exc)}
            return {
                "success": True,
                "summary": (
                    f"Retired role '{target_role_id or target_agent_id}' from industry instance "
                    f"'{instance_id}'."
                ),
                "instance_id": instance_id,
                "role_id": target_role_id,
                "agent_id": target_agent_id,
                "employment_mode": "career",
                "routes": {
                    "industry": f"/api/runtime-center/industry/{instance_id}",
                },
            }

        if operation != "add-role":
            return {
                "success": False,
                "error": "operation must be 'add-role', 'promote-role', or 'retire-role'",
            }
        if role is None:
            return {"success": False, "error": "role payload is required"}
        if existing_role is not None:
            existing_employment_mode = _string_value(
                getattr(existing_role, "employment_mode", None),
            ) or "career"
            return {
                "success": True,
                "summary": (
                    f"Industry instance '{instance_id}' already contains a matching "
                    f"{existing_employment_mode} role for '{role.role_id}', so the existing seat was reused."
                ),
                "instance_id": instance_id,
                "role_id": _string_value(getattr(existing_role, "role_id", None)) or role.role_id,
                "agent_id": _string_value(getattr(existing_role, "agent_id", None)) or role.agent_id,
                "employment_mode": existing_employment_mode,
                "no_op": True,
                "routes": {
                    "industry": f"/api/runtime-center/industry/{instance_id}",
                    "agent": (
                        f"/api/runtime-center/agents/{_string_value(getattr(existing_role, 'agent_id', None))}"
                        if _string_value(getattr(existing_role, "agent_id", None))
                        else None
                    ),
                },
            }

        raw_goal = resolved_payload.get("goal")
        goal: IndustryDraftGoal | None = None
        if isinstance(raw_goal, dict):
            try:
                goal = IndustryDraftGoal.model_validate(raw_goal)
            except Exception as exc:
                return {"success": False, "error": f"Invalid goal payload: {exc}"}

        raw_schedule = resolved_payload.get("schedule")
        schedule: IndustryDraftSchedule | None = None
        if isinstance(raw_schedule, dict):
            try:
                schedule = IndustryDraftSchedule.model_validate(raw_schedule)
            except Exception as exc:
                return {
                    "success": False,
                    "error": f"Invalid schedule payload: {exc}",
                }

        add_role = getattr(self._industry_service, "add_role_to_instance_team", None)
        if not callable(add_role):
            return {
                "success": False,
                "error": "Industry service does not support team role updates",
            }

        try:
            response = await add_role(
                instance_id,
                role=role,
                goal=goal,
                schedule=schedule,
                seed_default_goal=(
                    bool(resolved_payload.get("seed_default_goal"))
                    if "seed_default_goal" in resolved_payload
                    else True
                ),
                auto_activate=(
                    bool(resolved_payload.get("auto_activate"))
                    if "auto_activate" in resolved_payload
                    else None
                ),
                auto_dispatch=(
                    bool(resolved_payload.get("auto_dispatch"))
                    if "auto_dispatch" in resolved_payload
                    else None
                ),
                execute=(
                    bool(resolved_payload.get("execute"))
                    if "execute" in resolved_payload
                    else None
                ),
            )
        except KeyError as exc:
            return {"success": False, "error": str(exc).strip("'")}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        return {
            "success": True,
            "summary": (
                f"Added role '{role.role_name}' to industry instance '{instance_id}' and "
                "reconciled the canonical team plan."
            ),
            "instance_id": instance_id,
            "role_id": role.role_id,
            "agent_id": role.agent_id,
            "employment_mode": role.employment_mode,
            "team_size": len(response.team.agents),
            "schedule_count": len(response.schedule_summaries),
            "routes": {
                "industry": f"/api/runtime-center/industry/{instance_id}",
                "agent": f"/api/runtime-center/agents/{role.agent_id}",
            },
        }

    async def handle_run_operating_cycle(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._industry_service is None:
            return {"success": False, "error": "Industry service is not available"}
        runner = getattr(self._industry_service, "run_operating_cycle", None)
        if not callable(runner):
            return {"success": False, "error": "Industry service cannot run operating cycles"}
        result = await runner(
            instance_id=_string_value(
                resolved_payload.get("instance_id")
                or resolved_payload.get("industry_instance_id"),
            ),
            actor=_string_value(resolved_payload.get("actor")) or "system:automation",
            force=bool(resolved_payload.get("force", False)),
            limit=(
                int(resolved_payload["limit"])
                if isinstance(resolved_payload.get("limit"), int)
                else None
            ),
            auto_dispatch_materialized_goals=(
                bool(resolved_payload.get("auto_dispatch_materialized_goals"))
                if "auto_dispatch_materialized_goals" in resolved_payload
                else True
            ),
        )
        processed = result.get("processed_instances") if isinstance(result, dict) else None
        processed_count = len(processed) if isinstance(processed, list) else 0
        return {
            "success": True,
            "summary": f"Operating cycle processed {processed_count} instance(s).",
            "result": result,
        }

