# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _WorkflowServiceContextMixin:
    def _resolve_owner_agent_id(
        self,
        *,
        owner_role_id: str | None,
        industry_context: dict[str, Any],
        fallback_owner_agent_id: str | None,
    ) -> str | None:
        role_mapping = industry_context.get("role_agent_map")
        if isinstance(role_mapping, dict) and owner_role_id:
            resolved = _string(role_mapping.get(owner_role_id))
            if resolved:
                return resolved
        return (
            _string(fallback_owner_agent_id)
            or _string(industry_context.get("execution_core_agent_id"))
            or EXECUTION_CORE_AGENT_ID
        )

    def _resolve_owner_binding(
        self,
        *,
        raw_step: dict[str, Any],
        template: WorkflowTemplateRecord,
        industry_context: dict[str, Any],
        fallback_owner_agent_id: str | None,
    ) -> tuple[str | None, str | None]:
        explicit_owner_agent_id = _string(raw_step.get("owner_agent_id"))
        requested_owner_role_id = (
            _string(raw_step.get("owner_role_id")) or template.owner_role_id
        )
        if explicit_owner_agent_id:
            return (
                self._resolve_role_id_for_agent(
                    agent_id=explicit_owner_agent_id,
                    industry_context=industry_context,
                )
                or requested_owner_role_id,
                explicit_owner_agent_id,
        )
        execution_mode = (
            "control"
            if _string(raw_step.get("execution_mode")) == "control"
            else "leaf"
        )
        owner_role_candidates = self._build_owner_role_candidates(
            requested_owner_role_id=requested_owner_role_id,
            raw_candidates=raw_step.get("owner_role_candidates"),
        )
        resolved_owner_role_id = self._resolve_owner_role_id(
            requested_owner_role_id=requested_owner_role_id,
            candidate_role_ids=owner_role_candidates,
            execution_mode=execution_mode,
            industry_context=industry_context,
        )
        owner_agent_id = self._resolve_owner_agent_id(
            owner_role_id=resolved_owner_role_id or requested_owner_role_id,
            industry_context=industry_context,
            fallback_owner_agent_id=fallback_owner_agent_id,
        )
        if resolved_owner_role_id is None and owner_agent_id is not None:
            resolved_owner_role_id = self._resolve_role_id_for_agent(
                agent_id=owner_agent_id,
                industry_context=industry_context,
            )
        return resolved_owner_role_id or requested_owner_role_id, owner_agent_id

    def _build_owner_role_candidates(
        self,
        *,
        requested_owner_role_id: str | None,
        raw_candidates: Any,
    ) -> list[str]:
        candidates = _unique_strings(raw_candidates)
        if requested_owner_role_id and requested_owner_role_id not in candidates:
            candidates.append(requested_owner_role_id)
        return candidates

    def _resolve_owner_role_id(
        self,
        *,
        requested_owner_role_id: str | None,
        candidate_role_ids: list[str],
        execution_mode: str,
        industry_context: dict[str, Any],
    ) -> str | None:
        role_mapping = industry_context.get("role_agent_map")
        if isinstance(role_mapping, dict):
            for role_id in candidate_role_ids:
                resolved_agent_id = _string(role_mapping.get(role_id))
                if role_id and resolved_agent_id:
                    return role_id
        business_role_ids = [
            role_id
            for role_id in list(industry_context.get("business_role_ids") or [])
            if isinstance(role_id, str) and role_id and role_id != EXECUTION_CORE_ROLE_ID
        ]
        if execution_mode == "leaf":
            for role_id in business_role_ids:
                if role_id not in candidate_role_ids:
                    return role_id
            for role_id in business_role_ids:
                return role_id
        if isinstance(role_mapping, dict):
            resolved_execution_core = _string(role_mapping.get(EXECUTION_CORE_ROLE_ID))
            if resolved_execution_core:
                return EXECUTION_CORE_ROLE_ID
        return requested_owner_role_id

    def _resolve_role_id_for_agent(
        self,
        *,
        agent_id: str,
        industry_context: dict[str, Any],
    ) -> str | None:
        agent_role_map = industry_context.get("agent_role_map")
        if not isinstance(agent_role_map, dict):
            return None
        return _string(agent_role_map.get(agent_id))

    def _resolve_industry_context(self, industry_instance_id: str | None) -> dict[str, Any]:
        context: dict[str, Any] = {
            "industry_label": "Workflow",
            "industry_summary": "",
            "owner_scope": None,
            "execution_core_agent_id": EXECUTION_CORE_AGENT_ID,
            "role_agent_map": {EXECUTION_CORE_ROLE_ID: EXECUTION_CORE_AGENT_ID},
            "agent_role_map": {EXECUTION_CORE_AGENT_ID: EXECUTION_CORE_ROLE_ID},
            "business_role_ids": [],
            "strategy_memory": None,
            "strategy_id": None,
            "strategy_title": "",
            "strategy_summary": "",
            "strategy_mission": "",
            "north_star": "",
            "priority_order": [],
            "priority_order_text": "",
            "thinking_axes": [],
            "thinking_axes_text": "",
            "delegation_policy": [],
            "delegation_policy_text": "",
            "direct_execution_policy": [],
            "direct_execution_policy_text": "",
            "execution_constraints": [],
            "execution_constraints_text": "",
            "evidence_requirements": [],
            "evidence_requirements_text": "",
            "current_focuses": [],
            "current_focuses_text": "",
        }
        if not industry_instance_id or self._industry_instance_repository is None:
            return context
        record = self._industry_instance_repository.get_instance(industry_instance_id)
        if record is None:
            return context
        team_payload = dict(record.team_payload or {})
        agents = list(team_payload.get("agents") or [])
        role_agent_map: dict[str, str] = {EXECUTION_CORE_ROLE_ID: EXECUTION_CORE_AGENT_ID}
        agent_role_map: dict[str, str] = {EXECUTION_CORE_AGENT_ID: EXECUTION_CORE_ROLE_ID}
        business_role_ids: list[str] = []
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            role_id = _string(agent.get("role_id"))
            agent_id = _string(agent.get("agent_id"))
            if role_id and agent_id:
                role_agent_map[role_id] = agent_id
                agent_role_map[agent_id] = role_id
                agent_class = _string(agent.get("agent_class")) or "business"
                if agent_class != "system" and role_id != EXECUTION_CORE_ROLE_ID:
                    business_role_ids.append(role_id)
        execution_core_agent_id = (
            _string((record.execution_core_identity_payload or {}).get("agent_id"))
            or EXECUTION_CORE_AGENT_ID
        )
        strategy_payload = self._resolve_strategy_memory_payload(
            industry_instance_id=record.instance_id,
            owner_agent_id=execution_core_agent_id,
        )
        profile_goals = _unique_strings(
            (record.profile_payload or {}).get("goals")
            if isinstance(record.profile_payload, dict)
            else None,
        )
        current_focuses = _unique_strings(
            strategy_payload.get("current_focuses") if strategy_payload else None,
            profile_goals,
        )
        priority_order = _unique_strings(
            strategy_payload.get("priority_order") if strategy_payload else None,
            current_focuses,
            profile_goals,
        )
        thinking_axes = _unique_strings(
            strategy_payload.get("thinking_axes") if strategy_payload else None,
        )
        delegation_policy = _unique_strings(
            strategy_payload.get("delegation_policy") if strategy_payload else None,
        )
        direct_execution_policy = _unique_strings(
            strategy_payload.get("direct_execution_policy") if strategy_payload else None,
        )
        execution_constraints = _unique_strings(
            strategy_payload.get("execution_constraints") if strategy_payload else None,
        )
        evidence_requirements = _unique_strings(
            strategy_payload.get("evidence_requirements") if strategy_payload else None,
        )
        strategy_memory = dict(strategy_payload) if strategy_payload else None
        if strategy_memory is not None:
            strategy_memory["priority_order"] = list(priority_order)
            strategy_memory["current_focuses"] = list(current_focuses)
        return {
            "industry_label": _string(record.label) or "Workflow",
            "industry_summary": _string(record.summary) or "",
            "owner_scope": _string(record.owner_scope),
            "execution_core_agent_id": execution_core_agent_id,
            "role_agent_map": role_agent_map,
            "agent_role_map": agent_role_map,
            "business_role_ids": business_role_ids,
            "strategy_memory": strategy_memory,
            "strategy_id": _string(strategy_memory.get("strategy_id")) if strategy_memory else None,
            "strategy_title": _string(strategy_memory.get("title")) if strategy_memory else "",
            "strategy_summary": _string(strategy_memory.get("summary")) if strategy_memory else "",
            "strategy_mission": _string(strategy_memory.get("mission")) if strategy_memory else "",
            "north_star": _string(strategy_memory.get("north_star")) if strategy_memory else "",
            "priority_order": priority_order,
            "priority_order_text": " / ".join(priority_order),
            "thinking_axes": thinking_axes,
            "thinking_axes_text": " / ".join(thinking_axes),
            "delegation_policy": delegation_policy,
            "delegation_policy_text": " / ".join(delegation_policy),
            "direct_execution_policy": direct_execution_policy,
            "direct_execution_policy_text": " / ".join(direct_execution_policy),
            "execution_constraints": execution_constraints,
            "execution_constraints_text": " / ".join(execution_constraints),
            "evidence_requirements": evidence_requirements,
            "evidence_requirements_text": " / ".join(evidence_requirements),
            "current_focuses": current_focuses,
            "current_focuses_text": " / ".join(current_focuses),
        }

    def _resolve_strategy_memory_payload(
        self,
        *,
        industry_instance_id: str,
        owner_agent_id: str | None,
    ) -> dict[str, Any] | None:
        return resolve_strategy_payload(
            service=self._strategy_memory_service,
            scope_type="industry",
            scope_id=industry_instance_id,
            owner_agent_id=_string(owner_agent_id),
            fallback_owner_agent_ids=[EXECUTION_CORE_AGENT_ID, None],
        )

    def _resolve_preset(
        self,
        *,
        template_id: str,
        preset_id: str | None,
    ) -> WorkflowPresetRecord | None:
        if not preset_id or self._workflow_preset_repository is None:
            return None
        preset = self._workflow_preset_repository.get_preset(preset_id)
        if preset is None:
            raise KeyError(f"Workflow preset '{preset_id}' not found")
        if preset.template_id != template_id:
            raise ValueError(
                f"Workflow preset '{preset_id}' does not belong to template '{template_id}'",
            )
        return preset

    def _merge_parameters(
        self,
        *,
        preset: WorkflowPresetRecord | None,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(preset.parameter_overrides if preset is not None else {})
        merged.update(dict(parameters or {}))
        return merged

    def _get_agent_profile(self, agent_id: str) -> Any | None:
        if self._agent_profile_service is None:
            return None
        getter = getattr(self._agent_profile_service, "get_agent", None)
        if not callable(getter):
            return None
        try:
            return getter(agent_id)
        except Exception:
            return None

    def _get_agent_capability_surface(self, agent_id: str) -> dict[str, Any] | None:
        if self._agent_profile_service is None:
            return None
        getter = getattr(self._agent_profile_service, "get_capability_surface", None)
        if not callable(getter):
            return None
        try:
            payload = getter(agent_id)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _summarize_launch_blockers(
        self,
        blockers: list[WorkflowTemplateLaunchBlocker],
    ) -> str:
        if not blockers:
            return "Workflow launch is blocked."
        lines: list[str] = []
        for blocker in blockers[:4]:
            message = blocker.message.strip()
            if message and message not in lines:
                lines.append(message)
        remaining = len(blockers) - len(lines)
        if remaining > 0:
            lines.append(f"... and {remaining} more blocker(s).")
        return "Workflow launch blocked: " + " ".join(lines)

    def _get_capability_mount(self, capability_id: str):
        if self._capability_service is None:
            return None
        getter = getattr(self._capability_service, "get_capability", None)
        if not callable(getter):
            return None
        return getter(capability_id)

    def _has_capability(self, capability_id: str) -> bool:
        mount = self._get_capability_mount(capability_id)
        return bool(mount is not None and mount.enabled)

    def _list_installed_mcp_client_keys(self) -> set[str]:
        if self._capability_service is None:
            return set()
        lister = getattr(self._capability_service, "list_mcp_client_infos", None)
        if not callable(lister):
            return set()
        try:
            payload = lister()
        except Exception:
            return set()
        installed: set[str] = set()
        if not isinstance(payload, list):
            return installed
        for item in payload:
            if not isinstance(item, dict):
                continue
            key = _string(item.get("key"))
            if key:
                installed.add(key)
        return installed

    def _resolve_install_templates_for_capability(
        self,
        *,
        template: WorkflowTemplateRecord,
        capability_id: str,
        installed_client_keys: set[str],
    ) -> list[WorkflowTemplateInstallTemplateRef]:
        mappings = template.metadata.get("dependency_install_templates")
        explicit_template_ids = _unique_strings(
            mappings.get(capability_id) if isinstance(mappings, dict) else [],
        )
        candidates = list_install_templates(
            capability_service=self._capability_service,
            decision_request_repository=self._decision_request_repository,
            include_runtime=False,
        )
        if not explicit_template_ids:
            explicit_template_ids = [
                candidate.id
                for candidate in candidates
                if match_install_template_capability_ids(
                    template_id=candidate.id,
                    capability_ids=[capability_id],
                )
            ]
        matched_ids = set(explicit_template_ids)
        refs: list[WorkflowTemplateInstallTemplateRef] = []
        for candidate in candidates:
            if candidate.id not in matched_ids:
                continue
            refs.append(
                WorkflowTemplateInstallTemplateRef(
                    template_id=candidate.id,
                    name=candidate.name,
                    installed=(
                        candidate.installed
                        if candidate.default_client_key is None
                        else candidate.default_client_key in installed_client_keys
                    ),
                    default_client_key=candidate.default_client_key,
                    capability_tags=list(candidate.capability_tags),
                    routes={
                        "detail": f"/api/capability-market/install-templates/{candidate.id}",
                        "install": (
                            f"/api/capability-market/install-templates/{candidate.id}/install"
                        ),
                        "market": (
                            f"/capability-market?tab=install-templates&template={candidate.id}"
                        ),
                    },
                ),
            )
        return refs

    async def _persist_schedule_spec(self, spec: dict[str, Any]) -> None:
        if self._cron_manager is not None and callable(
            getattr(self._cron_manager, "create_or_replace_job", None),
        ):
            from ..app.crons.models import CronJobSpec

            await self._cron_manager.create_or_replace_job(CronJobSpec.model_validate(spec))
            return
        if self._schedule_writer is not None and callable(
            getattr(self._schedule_writer, "upsert_job", None),
        ):
            from ..app.crons.models import CronJobSpec

            result = self._schedule_writer.upsert_job(CronJobSpec.model_validate(spec))
            if inspect.isawaitable(result):
                await result

    async def _pause_schedule(self, schedule_id: str) -> None:
        if self._cron_manager is not None and callable(
            getattr(self._cron_manager, "pause_job", None),
        ):
            try:
                await self._cron_manager.pause_job(schedule_id)
                return
            except Exception:
                pass
        if self._schedule_repository is None:
            return
        schedule = self._schedule_repository.get_schedule(schedule_id)
        if schedule is None:
            return
        self._schedule_repository.upsert_schedule(
            schedule.model_copy(
                update={
                    "enabled": False,
                    "status": "paused",
                    "updated_at": _utc_now(),
                },
            ),
        )

    async def _resume_schedule(self, schedule_id: str) -> None:
        if self._cron_manager is not None and callable(
            getattr(self._cron_manager, "resume_job", None),
        ):
            try:
                await self._cron_manager.resume_job(schedule_id)
                return
            except Exception:
                pass
        if self._schedule_repository is None:
            return
        schedule = self._schedule_repository.get_schedule(schedule_id)
        if schedule is None:
            return
        self._schedule_repository.upsert_schedule(
            schedule.model_copy(
                update={
                    "enabled": True,
                    "status": "scheduled",
                    "updated_at": _utc_now(),
                },
            ),
        )

    def _seed_builtin_templates(self) -> None:
        for template in self._builtin_templates():
            self._workflow_template_repository.upsert_template(template)
