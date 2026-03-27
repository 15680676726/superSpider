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
        delegation_service: object | None = None,
        industry_service: object | None = None,
    ) -> None:
        self._get_capability = get_capability_fn
        self._resolve_agent_profile = resolve_agent_profile_fn
        self._goal_service = goal_service
        self._agent_profile_service = agent_profile_service
        self._agent_profile_override_repository = agent_profile_override_repository
        self._delegation_service = delegation_service
        self._industry_service = industry_service

    def set_goal_service(self, goal_service: object | None) -> None:
        self._goal_service = goal_service

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_agent_profile_override_repository(
        self,
        override_repository: object | None,
    ) -> None:
        self._agent_profile_override_repository = override_repository

    def set_delegation_service(self, delegation_service: object | None) -> None:
        self._delegation_service = delegation_service

    def set_industry_service(self, industry_service: object | None) -> None:
        self._industry_service = industry_service

    async def handle_delegate_task(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._delegation_service is None:
            return {"success": False, "error": "Delegation service is not available"}

        parent_task_id = str(resolved_payload.get("parent_task_id") or "").strip()
        if not parent_task_id:
            return {"success": False, "error": "parent_task_id is required"}

        owner_agent_id = str(resolved_payload.get("owner_agent_id") or "").strip()
        target_agent_id = (
            str(resolved_payload.get("target_agent_id") or "").strip() or None
        )
        if not owner_agent_id and not target_agent_id:
            return {"success": False, "error": "owner_agent_id is required"}

        title = str(resolved_payload.get("title") or "").strip()
        candidate_agent = target_agent_id or owner_agent_id
        if not title:
            title = f"Delegated task for {candidate_agent or 'teammate'}"

        prompt_text = resolved_payload.get("prompt_text") or resolved_payload.get(
            "prompt",
        )
        summary = resolved_payload.get("summary")
        capability_ref = str(
            resolved_payload.get("capability_ref") or "system:dispatch_query",
        ).strip()
        risk_level = str(resolved_payload.get("risk_level") or "guarded").strip()
        if risk_level not in {"auto", "guarded", "confirm"}:
            risk_level = "guarded"

        channel = str(resolved_payload.get("channel") or "console").strip() or "console"
        session_id = resolved_payload.get("session_id")
        user_id = resolved_payload.get("user_id")
        request_payload = resolved_payload.get("request_payload") or resolved_payload.get(
            "request",
        )
        if not isinstance(request_payload, dict):
            request_payload = None
        child_payload = resolved_payload.get("payload")
        if not isinstance(child_payload, dict):
            child_payload = None
        if prompt_text is None and request_payload is None and child_payload is None:
            return {
                "success": False,
                "error": "prompt_text or request payload is required for delegation",
            }

        target_role_id = _string_value(
            resolved_payload.get("target_role_id")
            or resolved_payload.get("industry_role_id"),
        )
        target_role_name = _string_value(
            resolved_payload.get("target_role_name")
            or resolved_payload.get("industry_role_name"),
        )

        try:
            return await self._delegation_service.delegate_task(
                parent_task_id,
                title=title,
                owner_agent_id=owner_agent_id or candidate_agent or "",
                target_agent_id=target_agent_id,
                target_role_id=target_role_id,
                target_role_name=target_role_name,
                prompt_text=(
                    str(prompt_text).strip() if prompt_text is not None else None
                ),
                summary=(
                    str(summary).strip()
                    if isinstance(summary, str) and summary.strip()
                    else None
                ),
                capability_ref=capability_ref or "system:dispatch_query",
                risk_level=risk_level,
                environment_ref=resolved_payload.get("environment_ref"),
                channel=channel,
                session_id=(
                    str(session_id).strip()
                    if isinstance(session_id, str) and session_id.strip()
                    else None
                ),
                user_id=(
                    str(user_id).strip()
                    if isinstance(user_id, str) and user_id.strip()
                    else None
                ),
                request_payload=request_payload,
                payload=child_payload,
                actor=str(resolved_payload.get("actor") or "runtime-center"),
                execute=bool(resolved_payload.get("execute", False)),
                force=bool(resolved_payload.get("force", False)),
                industry_instance_id=_string_value(
                    resolved_payload.get("industry_instance_id"),
                ),
                industry_role_id=_string_value(resolved_payload.get("industry_role_id")),
                industry_label=_string_value(resolved_payload.get("industry_label")),
                owner_scope=_string_value(resolved_payload.get("owner_scope")),
                session_kind=_string_value(resolved_payload.get("session_kind")),
            )
        except KeyError as exc:
            return {
                "success": False,
                "error": str(exc).strip("'"),
                "error_code": getattr(exc, "code", "target_not_found"),
                "dispatch_status": "failed",
                "target_agent_id": candidate_agent,
            }
        except Exception as exc:
            error_code = getattr(exc, "code", "delegation_failed")
            return {
                "success": False,
                "error": str(exc),
                "error_code": error_code,
                "dispatch_status": "failed",
                "target_agent_id": candidate_agent,
            }

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
            "schedule_count": len(response.schedules),
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

    async def handle_goal_dispatch(
        self,
        capability_id: str,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._goal_service is None:
            return {"success": False, "error": "Goal service is not available"}

        owner_agent_id = (
            str(resolved_payload.get("owner_agent_id")).strip()
            if isinstance(resolved_payload.get("owner_agent_id"), str)
            and str(resolved_payload.get("owner_agent_id")).strip()
            else None
        )
        execute = bool(resolved_payload.get("execute", False))
        activate = bool(resolved_payload.get("activate", True))
        context = resolved_payload.get("context") or {}

        if capability_id == "system:dispatch_goal":
            goal_id = str(resolved_payload.get("goal_id") or "")
            if not goal_id:
                return {"success": False, "error": "goal_id is required"}
            result = await self._goal_service.dispatch_goal(
                goal_id,
                context=context if isinstance(context, dict) else {},
                owner_agent_id=owner_agent_id,
                execute=execute,
                activate=activate,
            )
            return {
                "success": True,
                "summary": f"Dispatched goal '{goal_id}'.",
                "result": result,
            }

        limit = resolved_payload.get("limit")
        if isinstance(limit, int) and limit <= 0:
            limit = None
        results = await self._goal_service.dispatch_active_goals(
            owner_agent_id=owner_agent_id,
            execute=execute,
            limit=limit,
            context=context if isinstance(context, dict) else {},
        )
        return {
            "success": True,
            "summary": f"Dispatched {len(results)} active goal(s).",
            "results": results,
        }
