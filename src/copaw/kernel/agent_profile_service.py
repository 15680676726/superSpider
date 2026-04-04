# -*- coding: utf-8 -*-
"""Merged agent profile projections for Runtime Center and workbench surfaces."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from .agent_profile import AgentProfile, DEFAULT_AGENTS
from .persistence import decode_kernel_task_metadata
from ..evidence import EvidenceLedger
from ..industry.models import (
    IndustrySeatCapabilityLayers,
    resolve_runtime_effective_capability_ids,
)
from ..industry.identity import EXECUTION_CORE_AGENT_ID, EXECUTION_CORE_ROLE_ID
from ..utils.runtime_action_links import build_decision_actions
from ..state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentLeaseRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentRuntimeRepository,
    SqliteAgentThreadBindingRepository,
    SqliteDecisionRequestRepository,
    SqliteIndustryInstanceRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)

if TYPE_CHECKING:
    from ..capabilities import CapabilityService
    from ..environments import EnvironmentService


AgentListView = str
PLATFORM_CONTROL_AGENT_IDS = frozenset(
    {
        "copaw-scheduler",
        "copaw-governance",
    },
)
PLATFORM_SYSTEM_AGENT_IDS = frozenset(
    {
        "copaw-scheduler",
        "copaw-governance",
    },
)
_EXECUTION_CORE_CONTROL_CAPABILITIES = [
    "system:dispatch_query",
    "system:delegate_task",
    "system:apply_role",
    "system:discover_capabilities",
]
_EXECUTION_CORE_LOCAL_TOOL_CAPABILITIES = [
    "tool:edit_file",
    "tool:execute_shell_command",
    "tool:get_current_time",
    "tool:read_file",
    "tool:write_file",
]

_ROLE_TOOL_BASELINE_CAPABILITIES = {
    EXECUTION_CORE_ROLE_ID: list(_EXECUTION_CORE_LOCAL_TOOL_CAPABILITIES),
    "researcher": [
        "tool:browser_use",
        "tool:edit_file",
        "tool:execute_shell_command",
        "tool:get_current_time",
        "tool:read_file",
        "tool:write_file",
    ],
}

_DEFAULT_TOOL_BASELINE_CAPABILITIES = [
    "tool:browser_use",
    "tool:edit_file",
    "tool:execute_shell_command",
    "tool:get_current_time",
    "tool:read_file",
    "tool:write_file",
]

_BASELINE_ROLE_CAPABILITIES = {
    EXECUTION_CORE_ROLE_ID: list(_EXECUTION_CORE_CONTROL_CAPABILITIES),
    "researcher": [
        "system:dispatch_query",
        "system:replay_routine",
        "system:run_fixed_sop",
    ],
}

_DEFAULT_BASELINE_CAPABILITIES = [
    "system:dispatch_query",
    "system:replay_routine",
    "system:run_fixed_sop",
]


class AgentProfileService:
    """Merge default agent profiles with overrides and runtime signals."""

    def __init__(
        self,
        *,
        override_repository: SqliteAgentProfileOverrideRepository | None = None,
        task_repository: SqliteTaskRepository | None = None,
        task_runtime_repository: SqliteTaskRuntimeRepository | None = None,
        agent_runtime_repository: SqliteAgentRuntimeRepository | None = None,
        agent_mailbox_repository: SqliteAgentMailboxRepository | None = None,
        agent_checkpoint_repository: SqliteAgentCheckpointRepository | None = None,
        agent_lease_repository: SqliteAgentLeaseRepository | None = None,
        agent_thread_binding_repository: SqliteAgentThreadBindingRepository | None = None,
        decision_request_repository: SqliteDecisionRequestRepository | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        environment_service: EnvironmentService | None = None,
        capability_service: CapabilityService | None = None,
        learning_service: object | None = None,
        goal_service: object | None = None,
        industry_instance_repository: SqliteIndustryInstanceRepository | None = None,
    ) -> None:
        self._override_repository = override_repository
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._agent_runtime_repository = agent_runtime_repository
        self._agent_mailbox_repository = agent_mailbox_repository
        self._agent_checkpoint_repository = agent_checkpoint_repository
        self._agent_lease_repository = agent_lease_repository
        self._agent_thread_binding_repository = agent_thread_binding_repository
        self._decision_request_repository = decision_request_repository
        self._evidence_ledger = evidence_ledger
        self._environment_service = environment_service
        self._capability_service = capability_service
        self._learning_service = learning_service
        self._goal_service = goal_service
        self._industry_instance_repository = industry_instance_repository

    def list_agents(
        self,
        *,
        view: AgentListView = "all",
        limit: int | None = None,
        industry_instance_id: str | None = None,
    ) -> list[AgentProfile]:
        profiles_by_id = {
            base.agent_id: self._project_agent(base)
            for base in DEFAULT_AGENTS
        }
        if self._override_repository is not None:
            for override in self._override_repository.list_overrides():
                if not self._is_override_visible(override):
                    continue
                if override.agent_id in profiles_by_id:
                    continue
                seed = AgentProfile(
                    agent_id=override.agent_id,
                    name=override.name or override.agent_id,
                    role_name=override.role_name or "",
                    role_summary=override.role_summary or "",
                )
                profiles_by_id[override.agent_id] = self._project_agent(seed)
        profiles = [
            profile
            for profile in profiles_by_id.values()
            if self._matches_view(profile, view=view)
            and (
                industry_instance_id is None
                or profile.industry_instance_id == industry_instance_id
            )
        ]
        profiles.sort(key=lambda item: item.updated_at, reverse=True)
        if limit is not None and limit >= 0:
            return profiles[:limit]
        return profiles

    def list_business_agents(
        self,
        *,
        limit: int | None = None,
        industry_instance_id: str | None = None,
    ) -> list[AgentProfile]:
        return self.list_agents(
            view="business",
            limit=limit,
            industry_instance_id=industry_instance_id,
        )

    def list_system_agents(
        self,
        *,
        limit: int | None = None,
        industry_instance_id: str | None = None,
    ) -> list[AgentProfile]:
        return self.list_agents(
            view="system",
            limit=limit,
            industry_instance_id=industry_instance_id,
        )

    def backfill_industry_baseline_capabilities(self) -> int:
        if self._override_repository is None:
            return 0
        updated = 0
        for override in self._override_repository.list_overrides():
            role_id = getattr(override, "industry_role_id", None)
            baseline = self._baseline_capabilities_for_role(role_id)
            if not baseline:
                continue
            merged = self._normalize_capabilities_for_role(
                override.capabilities,
                role_id,
            )
            if merged is None:
                merged = list(baseline)
            if merged != list(override.capabilities or []):
                refreshed = override.model_copy(update={"capabilities": merged})
                self._override_repository.upsert_override(refreshed)
                updated += 1
        return updated

    def build_capability_allowlist(
        self,
        *,
        agent_id: str,
        capabilities: list[str] | None,
        mode: str = "replace",
    ) -> list[str]:
        requested = _merge_unique(list(capabilities or []))
        merge_mode = (mode or "replace").strip().lower()
        if merge_mode not in {"replace", "merge"}:
            merge_mode = "replace"
        current = (
            self._override_repository.get_override(agent_id)
            if self._override_repository is not None
            else None
        )
        if merge_mode == "merge" and current is not None:
            requested = _merge_unique(list(current.capabilities or []), requested)
        role_id = getattr(current, "industry_role_id", None)
        if (
            (not isinstance(role_id, str) or not role_id.strip())
            and self._agent_runtime_repository is not None
        ):
            runtime = self._agent_runtime_repository.get_runtime(agent_id)
            if runtime is not None and isinstance(runtime.industry_role_id, str):
                role_id = runtime.industry_role_id
        if (not isinstance(role_id, str) or not role_id.strip()) and agent_id == EXECUTION_CORE_AGENT_ID:
            role_id = EXECUTION_CORE_ROLE_ID
        normalized = self._normalize_capabilities_for_role(requested, role_id)
        if normalized is not None:
            return normalized
        return requested

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        for base in DEFAULT_AGENTS:
            if base.agent_id == agent_id:
                return self._project_agent(base)
        override = (
            self._override_repository.get_override(agent_id)
            if self._override_repository is not None
            else None
        )
        if override is None or not self._is_override_visible(override):
            runtime = (
                self._agent_runtime_repository.get_runtime(agent_id)
                if self._agent_runtime_repository is not None
                else None
            )
            if runtime is None or runtime.desired_state == "retired":
                return None
            return self._project_agent(self._build_runtime_seed_profile(runtime))
        seed = AgentProfile(
            agent_id=agent_id,
            name=override.name or agent_id,
            role_name=override.role_name or "",
            role_summary=override.role_summary or "",
        )
        return self._project_agent(seed)

    def get_agent_detail(self, agent_id: str) -> dict[str, object] | None:
        profile = self.get_agent(agent_id)
        if profile is None:
            return None

        runtime = (
            self._agent_runtime_repository.get_runtime(agent_id)
            if self._agent_runtime_repository is not None
            else None
        )
        tasks = (
            self._task_repository.list_tasks(owner_agent_id=agent_id)
            if self._task_repository is not None
            else []
        )
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        task_payload: list[dict[str, object]] = []
        decisions: list[dict[str, object]] = []
        evidence: list[dict[str, object]] = []
        evidence_seen: set[str] = set()
        goal_ids: set[str] = set()
        environment_ids: set[str] = set()
        environment_refs: set[str] = set()
        current_environment_id: str | None = getattr(profile, "current_environment_id", None)

        for task in tasks[:10]:
            task_runtime = (
                self._task_runtime_repository.get_runtime(task.id)
                if self._task_runtime_repository is not None
                else None
            )
            if task_runtime is not None and task_runtime.active_environment_id:
                environment_ids.add(task_runtime.active_environment_id)
                if current_environment_id is None:
                    current_environment_id = task_runtime.active_environment_id
            if task.goal_id:
                goal_ids.add(task.goal_id)
            task_payload.append(
                {
                    "task": task.model_dump(mode="json"),
                    "runtime": task_runtime.model_dump(mode="json") if task_runtime is not None else None,
                    "route": f"/api/runtime-center/tasks/{task.id}",
                },
            )
            if self._decision_request_repository is not None:
                decisions.extend(
                    decision.model_dump(mode="json")
                    for decision in self._decision_request_repository.list_decision_requests(
                        task_id=task.id,
                    )
                )
            if self._evidence_ledger is not None:
                for record in self._evidence_ledger.list_by_task(task.id)[-5:]:
                    if record.id is None or record.id in evidence_seen:
                        continue
                    evidence_seen.add(record.id)
                    if record.environment_ref:
                        environment_refs.add(record.environment_ref)
                    evidence.append(_serialize_evidence(record))

        goals = [goal for goal_id in sorted(goal_ids) if (goal := self._resolve_goal(goal_id)) is not None]
        patches = self._list_related_patches(agent_id)
        growth = self._list_related_growth(agent_id)
        environments, workspace = self._collect_related_environments(
            environment_ids=environment_ids,
            environment_refs=environment_refs,
            current_environment_id=current_environment_id,
        )
        mailbox_items = (
            self._agent_mailbox_repository.list_items(agent_id=agent_id, limit=20)
            if self._agent_mailbox_repository is not None
            else []
        )
        checkpoints = (
            self._agent_checkpoint_repository.list_checkpoints(agent_id=agent_id, limit=20)
            if self._agent_checkpoint_repository is not None
            else []
        )
        leases = (
            self._agent_lease_repository.list_leases(agent_id=agent_id, limit=20)
            if self._agent_lease_repository is not None
            else []
        )
        thread_bindings = (
            self._agent_thread_binding_repository.list_bindings(
                agent_id=agent_id,
                active_only=False,
                limit=None,
            )
            if self._agent_thread_binding_repository is not None
            else []
        )
        teammates = self._list_teammates(profile)
        latest_collaboration = [
            item.model_dump(mode="json")
            for item in mailbox_items
            if item.source_agent_id or item.parent_mailbox_id
        ][:10]
        capability_surface = self.get_capability_surface(agent_id)

        return {
            "agent": profile.model_dump(mode="json"),
            "runtime": runtime.model_dump(mode="json") if runtime is not None else None,
            "goals": goals,
            "tasks": task_payload,
            "mailbox": [item.model_dump(mode="json") for item in mailbox_items],
            "checkpoints": [item.model_dump(mode="json") for item in checkpoints],
            "leases": [item.model_dump(mode="json") for item in leases],
            "thread_bindings": [item.model_dump(mode="json") for item in thread_bindings],
            "teammates": teammates,
            "latest_collaboration": latest_collaboration,
            "decisions": decisions[:20],
            "evidence": evidence[:20],
            "patches": patches,
            "growth": growth,
            "environments": environments,
            "workspace": workspace,
            "capability_surface": capability_surface,
            "stats": {
                "task_count": len(task_payload),
                "mailbox_count": len(mailbox_items),
                "checkpoint_count": len(checkpoints),
                "lease_count": len(leases),
                "binding_count": len(thread_bindings),
                "teammate_count": len(teammates),
                "decision_count": len(decisions),
                "evidence_count": len(evidence),
                "patch_count": len(patches),
                "growth_count": len(growth),
                "environment_count": len(environments),
            },
        }

    def get_capability_surface(
        self,
        agent_id: str,
        *,
        decision_limit: int = 10,
    ) -> dict[str, object] | None:
        profile = self.get_agent(agent_id)
        if profile is None:
            return None
        runtime = (
            self._agent_runtime_repository.get_runtime(agent_id)
            if self._agent_runtime_repository is not None
            else None
        )
        override = (
            self._override_repository.get_override(agent_id)
            if self._override_repository is not None
            else None
        )
        role_id = _coerce_non_empty_str(profile.industry_role_id)
        if role_id is None and agent_id == EXECUTION_CORE_AGENT_ID:
            role_id = EXECUTION_CORE_ROLE_ID
        baseline_capabilities = self._baseline_capabilities_for_role(role_id)
        blueprint_capabilities = self._resolve_blueprint_capabilities(
            profile=profile,
            runtime=runtime,
        )
        explicit_capabilities = _merge_unique(list(override.capabilities or [])) if (
            override is not None and override.capabilities is not None
        ) else []
        effective_capabilities = _merge_unique(list(profile.capabilities or []))
        recommended_capabilities = self._resolve_recommended_capabilities(
            baseline_capabilities=baseline_capabilities,
            blueprint_capabilities=blueprint_capabilities,
            explicit_capabilities=explicit_capabilities,
            effective_capabilities=effective_capabilities,
        )
        catalog_ids = _merge_unique(
            baseline_capabilities,
            blueprint_capabilities,
            explicit_capabilities,
            recommended_capabilities,
            effective_capabilities,
        )
        capability_items = [
            self._build_capability_surface_item(
                capability_id,
                baseline_capabilities=baseline_capabilities,
                blueprint_capabilities=blueprint_capabilities,
                explicit_capabilities=explicit_capabilities,
                recommended_capabilities=recommended_capabilities,
                effective_capabilities=effective_capabilities,
            )
            for capability_id in catalog_ids
        ]
        capability_decisions = self._list_capability_governance_decisions(
            agent_id=agent_id,
            limit=decision_limit,
        )
        pending_decisions = [
            decision
            for decision in capability_decisions
            if str(decision.get("status") or "") in {"open", "reviewing"}
        ]
        return {
            "agent_id": agent_id,
            "actor_present": runtime is not None,
            "industry_instance_id": profile.industry_instance_id,
            "industry_role_id": profile.industry_role_id,
            "default_mode": "governed",
            "baseline_capabilities": baseline_capabilities,
            "blueprint_capabilities": blueprint_capabilities,
            "explicit_capabilities": explicit_capabilities,
            "recommended_capabilities": recommended_capabilities,
            "effective_capabilities": effective_capabilities,
            "items": capability_items,
            "pending_decisions": pending_decisions,
            "recent_decisions": capability_decisions,
            "drift_detected": set(recommended_capabilities) != set(effective_capabilities),
            "stats": {
                "baseline_count": len(baseline_capabilities),
                "blueprint_count": len(blueprint_capabilities),
                "explicit_count": len(explicit_capabilities),
                "recommended_count": len(recommended_capabilities),
                "effective_count": len(effective_capabilities),
                "pending_decision_count": len(pending_decisions),
                "recent_decision_count": len(capability_decisions),
            },
            "routes": {
                "detail": f"/api/runtime-center/agents/{agent_id}/capabilities",
                "actor_detail": f"/api/runtime-center/actors/{agent_id}/capabilities",
                "governed_assign": f"/api/runtime-center/agents/{agent_id}/capabilities/governed",
                "actor_governed_assign": f"/api/runtime-center/actors/{agent_id}/capabilities/governed",
                "direct_assign": f"/api/runtime-center/agents/{agent_id}/capabilities",
                "actor_direct_assign": f"/api/runtime-center/actors/{agent_id}/capabilities",
            },
        }

    def get_prompt_capability_projection(
        self,
        agent_id: str,
        *,
        item_limit: int = 4,
    ) -> dict[str, object] | None:
        surface = self.get_capability_surface(agent_id, decision_limit=5)
        if surface is None:
            return None
        effective_capabilities = {
            capability_id
            for capability_id in _string_list(surface.get("effective_capabilities"))
        }
        if not effective_capabilities:
            return None
        normalized_limit = max(1, int(item_limit))
        bucket_keys = (
            "system_dispatch",
            "system_governance",
            "tools",
            "skills",
            "mcp",
            "other",
        )
        buckets: dict[str, list[dict[str, str]]] = {
            key: []
            for key in bucket_keys
        }
        bucket_counts = {key: 0 for key in bucket_keys}
        risk_levels: dict[str, int] = {}
        environment_requirements: list[str] = []
        evidence_contract: list[str] = []
        seen_environment_requirements: set[str] = set()
        seen_evidence_contract: set[str] = set()
        items = surface.get("items") if isinstance(surface.get("items"), list) else []
        for raw_item in items:
            if not isinstance(raw_item, dict):
                continue
            capability_id = _coerce_non_empty_str(raw_item.get("id"))
            if capability_id is None or capability_id not in effective_capabilities:
                continue
            prompt_item = self._build_prompt_capability_projection_item(raw_item)
            if prompt_item is None:
                continue
            source_kind = _coerce_non_empty_str(raw_item.get("source_kind"))
            bucket_key = self._classify_prompt_capability_bucket(
                capability_id,
                source_kind=source_kind,
            )
            bucket_counts[bucket_key] += 1
            if len(buckets[bucket_key]) < normalized_limit:
                buckets[bucket_key].append(prompt_item)
            risk_level = prompt_item["risk_level"]
            risk_levels[risk_level] = risk_levels.get(risk_level, 0) + 1
            for requirement in _string_list(raw_item.get("environment_requirements")):
                if requirement in seen_environment_requirements:
                    continue
                seen_environment_requirements.add(requirement)
                environment_requirements.append(requirement)
            for evidence_item in _string_list(raw_item.get("evidence_contract")):
                if evidence_item in seen_evidence_contract:
                    continue
                seen_evidence_contract.add(evidence_item)
                evidence_contract.append(evidence_item)
        pending_decisions = (
            surface.get("pending_decisions")
            if isinstance(surface.get("pending_decisions"), list)
            else []
        )
        return {
            "agent_id": agent_id,
            "default_mode": _coerce_non_empty_str(surface.get("default_mode")) or "governed",
            "effective_count": len(effective_capabilities),
            "pending_decision_count": len(pending_decisions),
            "drift_detected": bool(surface.get("drift_detected")),
            "bucket_counts": bucket_counts,
            "system_dispatch": buckets["system_dispatch"],
            "system_governance": buckets["system_governance"],
            "tools": buckets["tools"],
            "skills": buckets["skills"],
            "mcp": buckets["mcp"],
            "other": buckets["other"],
            "risk_levels": risk_levels,
            "environment_requirements": environment_requirements[:8],
            "evidence_contract": evidence_contract[:8],
        }

    def _project_agent(self, base: AgentProfile) -> AgentProfile:
        profile = base.model_copy(deep=True)
        override = (
            self._override_repository.get_override(profile.agent_id)
            if self._override_repository is not None
            else None
        )
        if override is not None:
            override = self._ensure_industry_baseline_capabilities(override)
            update: dict[str, Any] = {}
            for field in (
                "name",
                "role_name",
                "role_summary",
                "agent_class",
                "employment_mode",
                "activation_mode",
                "suspendable",
                "reports_to",
                "mission",
                "status",
                "risk_level",
                "current_focus_kind",
                "current_focus_id",
                "current_focus",
                "current_task_id",
                "industry_instance_id",
                "industry_role_id",
                "environment_summary",
                "today_output_summary",
                "latest_evidence_summary",
            ):
                value = getattr(override, field)
                if value is not None:
                    update[field] = value
            if override.environment_constraints is not None:
                update["environment_constraints"] = list(override.environment_constraints)
            if override.evidence_expectations is not None:
                update["evidence_expectations"] = list(override.evidence_expectations)
            if override.capabilities is not None:
                update["capabilities"] = list(override.capabilities)
            update["updated_at"] = max(
                profile.updated_at,
                override.updated_at or override.created_at,
            )
            profile = profile.model_copy(update=update)

        runtime_profile = self._apply_runtime_projection(profile)
        capabilities = self._resolve_capabilities(runtime_profile)
        if capabilities is not None:
            runtime_profile = runtime_profile.model_copy(update={"capabilities": capabilities})
        return runtime_profile

    def _resolve_blueprint_capabilities(
        self,
        *,
        profile: AgentProfile,
        runtime: object | None,
    ) -> list[str]:
        instance_id = _coerce_non_empty_str(profile.industry_instance_id)
        if instance_id is None and runtime is not None:
            instance_id = _coerce_non_empty_str(getattr(runtime, "industry_instance_id", None))
        if instance_id is None or self._industry_instance_repository is None:
            return []
        record = self._industry_instance_repository.get_instance(instance_id)
        if record is None:
            return []
        if profile.agent_id == EXECUTION_CORE_AGENT_ID:
            payload = (
                record.execution_core_identity_payload
                if isinstance(record.execution_core_identity_payload, dict)
                else {}
            )
            return _merge_unique(
                _string_list(payload.get("allowed_capabilities")),
                _string_list(payload.get("capabilities")),
            )
        team_payload = record.team_payload if isinstance(record.team_payload, dict) else {}
        agents = team_payload.get("agents")
        if not isinstance(agents, list):
            return []
        role_id_candidates = {
            value
            for value in (
                normalize_role(getattr(runtime, "industry_role_id", None)),
                normalize_role(profile.industry_role_id),
            )
            if value
        }
        for item in agents:
            if not isinstance(item, dict):
                continue
            item_agent_id = _coerce_non_empty_str(item.get("agent_id"))
            item_role_id = normalize_role(item.get("role_id"))
            if item_agent_id == profile.agent_id or (
                item_role_id is not None and item_role_id in role_id_candidates
            ):
                return _merge_unique(
                    _string_list(item.get("allowed_capabilities")),
                    _string_list(item.get("capabilities")),
                )
        return []

    def _resolve_recommended_capabilities(
        self,
        *,
        baseline_capabilities: list[str],
        blueprint_capabilities: list[str],
        explicit_capabilities: list[str],
        effective_capabilities: list[str],
    ) -> list[str]:
        seed = (
            blueprint_capabilities
            or explicit_capabilities
            or baseline_capabilities
            or effective_capabilities
        )
        return _merge_unique(seed, baseline_capabilities)

    def _build_capability_surface_item(
        self,
        capability_id: str,
        *,
        baseline_capabilities: list[str],
        blueprint_capabilities: list[str],
        explicit_capabilities: list[str],
        recommended_capabilities: list[str],
        effective_capabilities: list[str],
    ) -> dict[str, object]:
        mount = (
            self._capability_service.get_capability(capability_id)
            if self._capability_service is not None
            else None
        )
        sources: list[str] = []
        if capability_id in baseline_capabilities:
            sources.append("baseline")
        if capability_id in blueprint_capabilities:
            sources.append("blueprint")
        if capability_id in explicit_capabilities:
            sources.append("explicit")
        if capability_id in recommended_capabilities:
            sources.append("recommended")
        if capability_id in effective_capabilities:
            sources.append("effective")
        payload = {
            "id": capability_id,
            "name": getattr(mount, "name", None) or capability_id,
            "summary": getattr(mount, "summary", None) or "",
            "kind": getattr(mount, "kind", None) or "unknown",
            "source_kind": getattr(mount, "source_kind", None) or _infer_capability_source_kind(capability_id),
            "risk_level": getattr(mount, "risk_level", None) or "guarded",
            "enabled": bool(getattr(mount, "enabled", False)) if mount is not None else False,
            "available": mount is not None,
            "assignment_sources": sources,
            "route": f"/api/capabilities/{quote(capability_id, safe='')}",
        }
        if mount is not None:
            payload.update(
                {
                    "role_access_policy": list(getattr(mount, "role_access_policy", []) or []),
                    "tags": list(getattr(mount, "tags", []) or []),
                    "environment_requirements": list(
                        getattr(mount, "environment_requirements", []) or [],
                    ),
                    "evidence_contract": list(getattr(mount, "evidence_contract", []) or []),
                },
            )
        return payload

    def _build_prompt_capability_projection_item(
        self,
        item: dict[str, object],
    ) -> dict[str, str] | None:
        capability_id = _coerce_non_empty_str(item.get("id"))
        if capability_id is None:
            return None
        name = _coerce_non_empty_str(item.get("name")) or capability_id
        return {
            "id": capability_id,
            "label": _prompt_capability_label(capability_id, name=name),
            "risk_level": _coerce_non_empty_str(item.get("risk_level")) or "guarded",
        }

    def _classify_prompt_capability_bucket(
        self,
        capability_id: str,
        *,
        source_kind: str | None,
    ) -> str:
        normalized_source_kind = (
            source_kind.strip().lower()
            if isinstance(source_kind, str) and source_kind.strip()
            else _infer_capability_source_kind(capability_id)
        )
        if normalized_source_kind == "system":
            if capability_id in {
                "system:dispatch_query",
                "system:delegate_task",
            }:
                return "system_dispatch"
            return "system_governance"
        if normalized_source_kind == "tool":
            return "tools"
        if normalized_source_kind == "skill":
            return "skills"
        if normalized_source_kind == "mcp":
            return "mcp"
        return "other"

    def _list_capability_governance_decisions(
        self,
        *,
        agent_id: str,
        limit: int,
    ) -> list[dict[str, object]]:
        if self._task_repository is None:
            return []
        payload: list[dict[str, object]] = []
        scan_limit = max(limit * 20, 200)
        for task in self._task_repository.list_tasks(
            task_type="system:apply_role",
            acceptance_criteria_like=agent_id,
            limit=scan_limit,
        ):
            metadata = decode_kernel_task_metadata(task.acceptance_criteria)
            if not isinstance(metadata, dict):
                continue
            raw_payload = metadata.get("payload")
            task_payload = raw_payload if isinstance(raw_payload, dict) else {}
            target_agent_id = _coerce_non_empty_str(
                task_payload.get("agent_id")
                or task_payload.get("target_agent_id")
                or task_payload.get("owner_agent_id"),
            )
            if target_agent_id != agent_id:
                continue
            decisions = (
                self._decision_request_repository.list_decision_requests(task_id=task.id)
                if self._decision_request_repository is not None
                else []
            )
            serialized_decisions = [
                self._serialize_capability_decision_request(task, task_payload, decision)
                for decision in decisions
            ]
            if serialized_decisions:
                payload.extend(serialized_decisions)
                continue
            payload.append(
                self._serialize_capability_mutation_task(
                    task=task,
                    task_payload=task_payload,
                ),
            )
        payload.sort(
            key=lambda item: str(item.get("created_at") or item.get("updated_at") or ""),
            reverse=True,
        )
        return payload[:limit]

    def _serialize_capability_decision_request(
        self,
        task: object,
        task_payload: dict[str, object],
        decision: object,
    ) -> dict[str, object]:
        return {
            "id": getattr(decision, "id", None),
            "task_id": getattr(decision, "task_id", None) or getattr(task, "id", None),
            "decision_type": getattr(decision, "decision_type", None),
            "risk_level": getattr(decision, "risk_level", None),
            "summary": getattr(decision, "summary", None),
            "status": getattr(decision, "status", None),
            "requested_by": getattr(decision, "requested_by", None),
            "resolution": getattr(decision, "resolution", None),
            "created_at": _json_datetime(getattr(decision, "created_at", None)),
            "resolved_at": _json_datetime(getattr(decision, "resolved_at", None)),
            "expires_at": _json_datetime(getattr(decision, "expires_at", None)),
            "task_route": f"/api/runtime-center/tasks/{getattr(task, 'id', '')}",
            "route": f"/api/runtime-center/decisions/{getattr(decision, 'id', '')}",
            "capabilities": _merge_unique(_string_list(task_payload.get("capabilities"))),
            "capability_assignment_mode": (
                _coerce_non_empty_str(task_payload.get("capability_assignment_mode"))
                or _coerce_non_empty_str(task_payload.get("capabilities_mode"))
                or "replace"
            ),
            "reason": _coerce_non_empty_str(task_payload.get("reason")),
            "actor": _coerce_non_empty_str(task_payload.get("actor")),
            "actions": self._capability_decision_actions(decision),
        }

    def _serialize_capability_mutation_task(
        self,
        *,
        task: object,
        task_payload: dict[str, object],
    ) -> dict[str, object]:
        return {
            "id": f"task:{getattr(task, 'id', '')}",
            "task_id": getattr(task, "id", None),
            "decision_type": "capability-update",
            "risk_level": getattr(task, "current_risk_level", None),
            "summary": getattr(task, "summary", None) or getattr(task, "title", None),
            "status": getattr(task, "status", None),
            "requested_by": _coerce_non_empty_str(task_payload.get("actor")),
            "resolution": None,
            "created_at": _json_datetime(getattr(task, "created_at", None)),
            "resolved_at": None,
            "expires_at": None,
            "task_route": f"/api/runtime-center/tasks/{getattr(task, 'id', '')}",
            "route": f"/api/runtime-center/tasks/{getattr(task, 'id', '')}",
            "capabilities": _merge_unique(_string_list(task_payload.get("capabilities"))),
            "capability_assignment_mode": (
                _coerce_non_empty_str(task_payload.get("capability_assignment_mode"))
                or _coerce_non_empty_str(task_payload.get("capabilities_mode"))
                or "replace"
            ),
            "reason": _coerce_non_empty_str(task_payload.get("reason")),
            "actor": _coerce_non_empty_str(task_payload.get("actor")),
            "actions": {},
        }

    def _capability_decision_actions(self, decision: object) -> dict[str, str]:
        decision_id = _coerce_non_empty_str(getattr(decision, "id", None))
        status = _coerce_non_empty_str(getattr(decision, "status", None))
        if decision_id is None or status is None:
            return {}
        if status == "open":
            return build_decision_actions(decision_id, status="open")
        if status == "reviewing":
            return build_decision_actions(decision_id, status="reviewing")
        return {}

    def _build_runtime_seed_profile(self, runtime: object) -> AgentProfile:
        metadata = getattr(runtime, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
        agent_id = str(getattr(runtime, "agent_id", "") or "").strip()
        display_name = getattr(runtime, "display_name", None)
        role_name = getattr(runtime, "role_name", None)
        industry_role_id = getattr(runtime, "industry_role_id", None)
        runtime_role_id = industry_role_id if isinstance(industry_role_id, str) else None
        normalized_name = (
            display_name.strip()
            if isinstance(display_name, str) and display_name.strip()
            else agent_id
        )
        normalized_role_name = (
            role_name.strip()
            if isinstance(role_name, str) and role_name.strip()
            else runtime_role_id or ""
        )
        activation_mode = getattr(runtime, "activation_mode", None)
        if activation_mode not in {"persistent", "on-demand"}:
            activation_mode = "persistent"
        employment_mode = getattr(runtime, "employment_mode", None)
        if employment_mode not in {"career", "temporary"}:
            employment_mode = "career"
        actor_class = getattr(runtime, "actor_class", None)
        agent_class = (
            "system"
            if actor_class == "system" or agent_id in PLATFORM_SYSTEM_AGENT_IDS
            else "business"
        )
        updated_at = getattr(runtime, "updated_at", None)
        if not isinstance(updated_at, datetime):
            updated_at = getattr(runtime, "created_at", None)
        if not isinstance(updated_at, datetime):
            updated_at = _utc_now()
        return AgentProfile(
            agent_id=agent_id,
            name=normalized_name,
            role_name=normalized_role_name,
            role_summary=_coerce_non_empty_str(metadata.get("role_summary")) or "",
            agent_class=agent_class,
            employment_mode=employment_mode,
            activation_mode=activation_mode,
            suspendable=agent_class != "system",
            mission=_coerce_non_empty_str(metadata.get("mission")) or "",
            current_focus_kind=_coerce_non_empty_str(metadata.get("current_focus_kind")),
            current_focus_id=_coerce_non_empty_str(metadata.get("current_focus_id")),
            current_focus=_coerce_non_empty_str(metadata.get("current_focus")) or "",
            industry_instance_id=getattr(runtime, "industry_instance_id", None),
            industry_role_id=runtime_role_id,
            capabilities=self._baseline_capabilities_for_role(runtime_role_id),
            updated_at=updated_at,
        )

    def _apply_runtime_projection(self, profile: AgentProfile) -> AgentProfile:
        actor_runtime = (
            self._agent_runtime_repository.get_runtime(profile.agent_id)
            if self._agent_runtime_repository is not None
            else None
        )
        mailbox_items = (
            self._agent_mailbox_repository.list_items(
                agent_id=profile.agent_id,
                limit=50,
            )
            if self._agent_mailbox_repository is not None
            else []
        )
        mailbox_items.sort(key=lambda item: item.updated_at, reverse=True)
        checkpoints = (
            self._agent_checkpoint_repository.list_checkpoints(
                agent_id=profile.agent_id,
                limit=50,
            )
            if self._agent_checkpoint_repository is not None
            else []
        )
        checkpoints.sort(key=lambda item: item.updated_at, reverse=True)

        active_mailbox = next(
            (
                item
                for item in mailbox_items
                if item.id == getattr(actor_runtime, "current_mailbox_id", None)
            ),
            None,
        )
        if active_mailbox is None:
            active_mailbox = next(
                (
                    item
                    for item in mailbox_items
                    if item.status in {"running", "leased", "queued", "retry-wait", "blocked"}
                ),
                None,
            )
        latest_mailbox_result = next(
            (item for item in mailbox_items if _coerce_non_empty_str(item.result_summary)),
            None,
        )
        latest_mailbox_error = next(
            (item for item in mailbox_items if _coerce_non_empty_str(item.error_summary)),
            None,
        )
        current_checkpoint = next(
            (
                item
                for item in checkpoints
                if item.id == getattr(actor_runtime, "last_checkpoint_id", None)
            ),
            None,
        )
        if current_checkpoint is None and checkpoints:
            current_checkpoint = checkpoints[0]

        active_task_id = (
            _coerce_non_empty_str(getattr(actor_runtime, "current_task_id", None))
            or _coerce_non_empty_str(getattr(active_mailbox, "task_id", None))
            or _coerce_non_empty_str(getattr(current_checkpoint, "task_id", None))
            or profile.current_task_id
        )
        tasks = (
            [
                task
                for task in self._task_repository.list_tasks(owner_agent_id=profile.agent_id)
                if task.status not in {"completed", "cancelled"}
            ]
            if self._task_repository is not None
            else []
        )
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        task = (
            self._task_repository.get_task(active_task_id)
            if active_task_id and self._task_repository is not None
            else None
        )
        if task is None and tasks:
            task = tasks[0]
            active_task_id = task.id
        task_runtime = (
            self._task_runtime_repository.get_runtime(task.id)
            if task is not None and self._task_runtime_repository is not None
            else None
        )

        runtime_metadata = dict(actor_runtime.metadata) if actor_runtime is not None else {}
        mailbox_payload = dict(active_mailbox.payload) if active_mailbox is not None else {}
        mailbox_metadata = dict(active_mailbox.metadata) if active_mailbox is not None else {}
        checkpoint_resume = (
            dict(current_checkpoint.resume_payload)
            if current_checkpoint is not None
            else {}
        )
        checkpoint_snapshot = (
            dict(current_checkpoint.snapshot_payload)
            if current_checkpoint is not None
            else {}
        )
        runtime_layers = IndustrySeatCapabilityLayers.from_metadata(
            runtime_metadata.get("capability_layers"),
        )

        explicit_focus_kind = (
            _coerce_non_empty_str(runtime_metadata.get("current_focus_kind"))
            or _coerce_non_empty_str(mailbox_metadata.get("current_focus_kind"))
            or _coerce_non_empty_str(mailbox_payload.get("current_focus_kind"))
            or _coerce_non_empty_str(checkpoint_resume.get("current_focus_kind"))
            or _coerce_non_empty_str(checkpoint_snapshot.get("current_focus_kind"))
        )
        explicit_focus_id = (
            _coerce_non_empty_str(runtime_metadata.get("current_focus_id"))
            or _coerce_non_empty_str(mailbox_metadata.get("current_focus_id"))
            or _coerce_non_empty_str(mailbox_payload.get("current_focus_id"))
            or _coerce_non_empty_str(checkpoint_resume.get("current_focus_id"))
            or _coerce_non_empty_str(checkpoint_snapshot.get("current_focus_id"))
        )
        explicit_focus = (
            _coerce_non_empty_str(runtime_metadata.get("current_focus"))
            or _coerce_non_empty_str(mailbox_metadata.get("current_focus"))
            or _coerce_non_empty_str(mailbox_payload.get("current_focus"))
            or _coerce_non_empty_str(checkpoint_resume.get("current_focus"))
            or _coerce_non_empty_str(checkpoint_snapshot.get("current_focus"))
        )
        current_focus_kind = explicit_focus_kind or profile.current_focus_kind
        current_focus_id = explicit_focus_id or profile.current_focus_id
        current_focus = explicit_focus or profile.current_focus

        current_environment_id = (
            _coerce_non_empty_str(getattr(actor_runtime, "current_environment_id", None))
            or _coerce_non_empty_str(mailbox_payload.get("environment_ref"))
            or _coerce_non_empty_str(getattr(current_checkpoint, "environment_ref", None))
            or (
                task_runtime.active_environment_id
                if task_runtime is not None and task_runtime.active_environment_id
                else None
            )
            or getattr(profile, "current_environment_id", None)
        )
        queue_depth = (
            actor_runtime.queue_depth
            if actor_runtime is not None
            else sum(
                1
                for item in mailbox_items
                if item.status in {"queued", "leased", "running", "retry-wait", "blocked"}
            )
        )
        latest_checkpoint_id = (
            getattr(actor_runtime, "last_checkpoint_id", None)
            or (current_checkpoint.id if current_checkpoint is not None else None)
        )
        result_summary = _coerce_non_empty_str(
            getattr(actor_runtime, "last_result_summary", None),
        )
        if result_summary is None and current_checkpoint is not None and current_checkpoint.status == "applied":
            result_summary = _coerce_non_empty_str(getattr(current_checkpoint, "summary", None))
        if result_summary is None:
            result_summary = (
                _coerce_non_empty_str(
                    latest_mailbox_result.result_summary if latest_mailbox_result is not None else None,
                )
                or (
                    task_runtime.last_result_summary
                    if task_runtime is not None and task_runtime.last_result_summary
                    else None
                )
                or profile.today_output_summary
            )
        error_summary = _coerce_non_empty_str(
            getattr(actor_runtime, "last_error_summary", None),
        )
        if error_summary is None and current_checkpoint is not None and current_checkpoint.status == "failed":
            error_summary = _coerce_non_empty_str(getattr(current_checkpoint, "summary", None))
        if error_summary is None:
            error_summary = _coerce_non_empty_str(
                latest_mailbox_error.error_summary if latest_mailbox_error is not None else None,
            )
        if error_summary is None and task_runtime is not None and task_runtime.last_error_summary:
            error_summary = task_runtime.last_error_summary

        updated_candidates = [profile.updated_at]
        if actor_runtime is not None:
            updated_candidates.append(actor_runtime.updated_at)
        if active_mailbox is not None:
            updated_candidates.append(active_mailbox.updated_at)
        if current_checkpoint is not None:
            updated_candidates.append(current_checkpoint.updated_at)
        if task_runtime is not None:
            updated_candidates.append(task_runtime.updated_at)
        if task is not None:
            updated_candidates.append(task.updated_at)

        update: dict[str, Any] = {
            "current_focus_kind": current_focus_kind,
            "current_focus_id": current_focus_id,
            "current_focus": current_focus,
            "updated_at": max(updated_candidates),
        }
        merged_runtime_capabilities = resolve_runtime_effective_capability_ids(
            runtime_metadata,
        )
        if merged_runtime_capabilities:
            update["capabilities"] = merged_runtime_capabilities
        if actor_runtime is not None:
            update.update(
                {
                    "actor_key": actor_runtime.actor_key,
                    "actor_fingerprint": actor_runtime.actor_fingerprint,
                    "desired_state": actor_runtime.desired_state,
                    "runtime_status": actor_runtime.runtime_status,
                    "resident": actor_runtime.persistent,
                    "status": _derive_actor_status(
                        actor_runtime.runtime_status,
                        fallback=profile.status,
                    ),
                    "employment_mode": actor_runtime.employment_mode,
                    "activation_mode": actor_runtime.activation_mode,
                    "current_task_id": active_task_id or actor_runtime.current_task_id or profile.current_task_id,
                    "current_mailbox_id": actor_runtime.current_mailbox_id or getattr(active_mailbox, "id", None),
                    "queue_depth": queue_depth,
                    "industry_instance_id": actor_runtime.industry_instance_id or profile.industry_instance_id,
                    "industry_role_id": actor_runtime.industry_role_id or profile.industry_role_id,
                    "environment_summary": current_environment_id or profile.environment_summary,
                    "current_environment_id": current_environment_id,
                    "last_checkpoint_id": latest_checkpoint_id,
                    "today_output_summary": result_summary,
                    "latest_evidence_summary": (
                        result_summary
                        or error_summary
                        or profile.latest_evidence_summary
                    ),
                    "thread_id": self._resolve_primary_thread_id(profile.agent_id),
                },
            )
        if task is not None:
            update.update(
                {
                    "status": _derive_agent_status(
                        task.status,
                        runtime_status=(
                            task_runtime.runtime_status
                            if task_runtime is not None
                            else (actor_runtime.runtime_status if actor_runtime is not None else None)
                        ),
                    ),
                    "risk_level": (
                        task_runtime.risk_level
                        if task_runtime is not None
                        else task.current_risk_level
                    ),
                    "current_task_id": active_task_id or task.id,
                    "environment_summary": (
                        current_environment_id
                        or update.get("environment_summary", profile.environment_summary)
                    ),
                    "current_environment_id": (
                        current_environment_id or update.get("current_environment_id")
                    ),
                    "today_output_summary": result_summary
                    or update.get("today_output_summary", profile.today_output_summary),
                    "latest_evidence_summary": (
                        result_summary
                        or error_summary
                        or update.get("latest_evidence_summary", profile.latest_evidence_summary)
                    ),
                },
            )
        elif actor_runtime is None and active_mailbox is not None:
            update.update(
                {
                    "status": (
                        "blocked"
                        if active_mailbox.status == "blocked"
                        else "executing"
                        if active_mailbox.status == "running"
                        else "claimed"
                        if active_mailbox.status == "leased"
                        else "queued"
                    ),
                    "current_task_id": active_task_id,
                    "current_mailbox_id": active_mailbox.id,
                    "queue_depth": queue_depth,
                    "environment_summary": current_environment_id or profile.environment_summary,
                    "current_environment_id": current_environment_id,
                    "last_checkpoint_id": latest_checkpoint_id,
                    "today_output_summary": result_summary or profile.today_output_summary,
                    "latest_evidence_summary": (
                        result_summary
                        or error_summary
                        or profile.latest_evidence_summary
                    ),
                    "thread_id": self._resolve_primary_thread_id(profile.agent_id),
                },
            )
        return profile.model_copy(update=update)

    def _resolve_primary_thread_id(self, agent_id: str) -> str | None:
        if self._agent_thread_binding_repository is None:
            return None
        bindings = self._agent_thread_binding_repository.list_bindings(
            agent_id=agent_id,
            active_only=True,
            limit=None,
        )
        for binding in bindings:
            if binding.binding_kind == "agent-primary":
                return binding.thread_id
        return bindings[0].thread_id if bindings else None

    def _list_teammates(self, profile: AgentProfile) -> list[dict[str, object]]:
        if self._agent_runtime_repository is None or not profile.industry_instance_id:
            return []
        payload: list[dict[str, object]] = []
        for runtime in self._agent_runtime_repository.list_runtimes(
            industry_instance_id=profile.industry_instance_id,
            limit=None,
        ):
            if runtime.agent_id == profile.agent_id or runtime.desired_state == "retired":
                continue
            item = {
                **runtime.model_dump(mode="json"),
                "thread_id": self._resolve_primary_thread_id(runtime.agent_id),
            }
            teammate_profile = self.get_agent(runtime.agent_id)
            if teammate_profile is not None:
                item["name"] = teammate_profile.name
                item["role_name"] = teammate_profile.role_name
                item["current_focus_kind"] = teammate_profile.current_focus_kind
                item["current_focus_id"] = teammate_profile.current_focus_id
                item["current_focus"] = teammate_profile.current_focus
                item["capabilities"] = list(teammate_profile.capabilities)
            payload.append(item)
        payload.sort(key=lambda item: ((item.get("queue_depth") or 0), str(item.get("role_name") or "")), reverse=True)
        return payload

    def _resolve_goal_title(self, goal_id: str) -> str | None:
        service = self._goal_service
        getter = getattr(service, "get_goal", None)
        if not callable(getter):
            return None
        goal = getter(goal_id)
        if goal is None:
            return None
        title = getattr(goal, "title", None)
        return title if isinstance(title, str) and title else None

    def _resolve_capabilities(self, profile: AgentProfile) -> list[str] | None:
        role_id = getattr(profile, "industry_role_id", None)
        if (
            (not isinstance(role_id, str) or not role_id.strip())
            and profile.agent_id == EXECUTION_CORE_AGENT_ID
        ):
            role_id = EXECUTION_CORE_ROLE_ID
        if profile.agent_id == EXECUTION_CORE_AGENT_ID:
            normalized = self._normalize_capabilities_for_role(
                list(profile.capabilities),
                role_id,
            )
            if normalized:
                return normalized
            baseline = self._baseline_capabilities_for_role(role_id)
            return list(baseline)
        return list(profile.capabilities)

    def _baseline_capabilities_for_role(self, role_id: str | None) -> list[str]:
        if not isinstance(role_id, str):
            return []
        normalized = role_id.strip().lower()
        if not normalized:
            return []
        if normalized == EXECUTION_CORE_ROLE_ID:
            return [
                *_EXECUTION_CORE_CONTROL_CAPABILITIES,
                *_EXECUTION_CORE_LOCAL_TOOL_CAPABILITIES,
            ]
        system_baseline = list(
            _BASELINE_ROLE_CAPABILITIES.get(
                normalized,
                _DEFAULT_BASELINE_CAPABILITIES,
            ),
        )
        tool_baseline = list(
            _ROLE_TOOL_BASELINE_CAPABILITIES.get(
                normalized,
                _DEFAULT_TOOL_BASELINE_CAPABILITIES,
            ),
        )
        return _merge_unique(tool_baseline, system_baseline)

    def _merge_capabilities(
        self,
        existing: list[str] | None,
        baseline: list[str],
    ) -> list[str] | None:
        if existing is None:
            return None
        merged: list[str] = []
        seen: set[str] = set()
        for capability in existing:
            if not isinstance(capability, str):
                continue
            normalized = capability.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        for capability in baseline:
            if not isinstance(capability, str):
                continue
            normalized = capability.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        return merged

    def _normalize_capabilities_for_role(
        self,
        existing: list[str] | None,
        role_id: str | None,
    ) -> list[str] | None:
        baseline = self._baseline_capabilities_for_role(role_id)
        merged = self._merge_capabilities(existing, baseline)
        if merged is None:
            return None
        if isinstance(role_id, str) and role_id.strip().lower() == EXECUTION_CORE_ROLE_ID:
            allowed = set(baseline)
            return [capability for capability in merged if capability in allowed]
        return merged

    def _ensure_industry_baseline_capabilities(self, override: object) -> object:
        role_id = getattr(override, "industry_role_id", None)
        baseline = self._baseline_capabilities_for_role(role_id)
        if not baseline:
            return override
        existing = getattr(override, "capabilities", None)
        merged = self._normalize_capabilities_for_role(existing, role_id)
        if merged is None:
            merged = list(baseline)
        if merged == list(existing or []):
            return override
        refreshed = override.model_copy(update={"capabilities": merged})
        if self._override_repository is not None:
            self._override_repository.upsert_override(refreshed)
        return refreshed

    def _resolve_goal(self, goal_id: str) -> dict[str, object] | None:
        service = self._goal_service
        getter = getattr(service, "get_goal", None)
        if not callable(getter):
            return None
        goal = getter(goal_id)
        if goal is None:
            return None
        return goal.model_dump(mode="json")

    def _list_related_patches(self, agent_id: str) -> list[dict[str, object]]:
        service = self._learning_service
        lister = getattr(service, "list_patches", None)
        if not callable(lister):
            return []
        patches = list(lister(agent_id=agent_id))
        return [patch.model_dump(mode="json") for patch in patches[:20]]

    def _list_related_growth(self, agent_id: str) -> list[dict[str, object]]:
        service = self._learning_service
        lister = getattr(service, "list_growth", None)
        if not callable(lister):
            return []
        events = list(lister(agent_id=agent_id, limit=20))
        return [event.model_dump(mode="json") for event in events]

    def _is_override_visible(self, override: object) -> bool:
        if getattr(override, "status", None) == "retired":
            return False
        instance_id = getattr(override, "industry_instance_id", None)
        if not isinstance(instance_id, str) or not instance_id.strip():
            return True
        if self._industry_instance_repository is None:
            return True
        record = self._industry_instance_repository.get_instance(instance_id.strip())
        if record is None:
            return False
        active_agent_ids = set(record.agent_ids or [])
        team_payload = record.team_payload if isinstance(record.team_payload, dict) else {}
        agents = team_payload.get("agents") if isinstance(team_payload, dict) else None
        if isinstance(agents, list):
            for item in agents:
                if not isinstance(item, dict):
                    continue
                agent_id = item.get("agent_id")
                if isinstance(agent_id, str) and agent_id.strip():
                    active_agent_ids.add(agent_id.strip())
        if not active_agent_ids:
            return False
        agent_id = getattr(override, "agent_id", None)
        if not isinstance(agent_id, str) or not agent_id.strip():
            return False
        return agent_id.strip() in active_agent_ids

    def _matches_view(self, profile: AgentProfile, *, view: AgentListView) -> bool:
        normalized = (view or "all").strip().lower()
        is_platform_control = profile.agent_id in PLATFORM_CONTROL_AGENT_IDS
        if normalized == "business":
            return not is_platform_control
        if normalized == "system":
            return profile.agent_id in PLATFORM_SYSTEM_AGENT_IDS
        return True

    def _collect_related_environments(
        self,
        *,
        environment_ids: set[str],
        environment_refs: set[str],
        current_environment_id: str | None,
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        service = self._environment_service
        if service is None:
            return [], {
                "current_environment_id": current_environment_id,
                "current_environment_ref": None,
                "current_environment": None,
                "files_supported": False,
            }

        mounts_by_id: dict[str, object] = {}
        for environment_id in sorted(environment_ids):
            mount = service.get_environment(environment_id)
            if mount is not None:
                mounts_by_id[mount.id] = mount
        if environment_refs:
            for mount in service.list_environments():
                if mount.ref in environment_refs:
                    mounts_by_id.setdefault(mount.id, mount)

        environments: list[dict[str, object]] = []
        for mount in mounts_by_id.values():
            detail = service.get_environment_detail(mount.id, limit=10)
            payload = detail if isinstance(detail, dict) else mount.model_dump(mode="json")
            payload.setdefault("id", mount.id)
            payload.setdefault("kind", mount.kind)
            payload.setdefault("display_name", mount.display_name)
            payload.setdefault("ref", mount.ref)
            payload.setdefault("status", mount.status)
            payload["route"] = f"/api/runtime-center/environments/{mount.id}"
            environments.append(payload)

        environments.sort(
            key=lambda item: (
                item.get("id") == current_environment_id,
                str(item.get("last_active_at") or ""),
            ),
            reverse=True,
        )

        current_environment = next(
            (
                item
                for item in environments
                if item.get("id") == current_environment_id
            ),
            None,
        )
        workspace_environment = next(
            (
                item
                for item in environments
                if item.get("kind") == "workspace"
                and item.get("id") == current_environment_id
            ),
            None,
        )
        if workspace_environment is None:
            workspace_environment = next(
                (item for item in environments if item.get("kind") == "workspace"),
                None,
            )

        current_environment_ref = None
        if isinstance(current_environment, dict):
            ref = current_environment.get("ref")
            if isinstance(ref, str) and ref:
                current_environment_ref = ref
        if current_environment_ref is None and isinstance(workspace_environment, dict):
            ref = workspace_environment.get("ref")
            if isinstance(ref, str) and ref:
                current_environment_ref = ref

        return environments, {
            "current_environment_id": current_environment_id,
            "current_environment_ref": current_environment_ref,
            "current_environment": workspace_environment,
            "files_supported": bool(workspace_environment and current_environment_ref),
        }


def _derive_actor_status(runtime_status: str | None, *, fallback: str) -> str:
    if runtime_status in {"blocked", "degraded"}:
        return "blocked"
    if runtime_status in {"assigned", "queued", "claimed", "executing"}:
        return runtime_status
    if runtime_status in {"waiting", "waiting-input", "hydrating"}:
        return "queued"
    if runtime_status in {"running", "active"}:
        return "executing"
    if runtime_status == "paused":
        return "paused"
    if runtime_status == "retired":
        return "idle"
    return fallback or "idle"


def _derive_agent_status(task_status: str, *, runtime_status: str | None) -> str:
    if task_status == "needs-confirm" or runtime_status == "waiting-confirm":
        return "needs-confirm"
    if task_status in {"failed", "blocked"} or runtime_status == "blocked":
        return "blocked"
    if runtime_status in {"assigned", "queued", "claimed", "executing"}:
        return runtime_status
    if task_status == "running" or runtime_status == "active":
        return "executing"
    if task_status in {"waiting", "queued"} or runtime_status in {"waiting-input", "hydrating"}:
        return "queued"
    return "idle"


def _merge_unique(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for capability in group:
            if not isinstance(capability, str):
                continue
            normalized = capability.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _coerce_non_empty_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        text
        for item in value
        if (text := _coerce_non_empty_str(item)) is not None
    ]


def _json_datetime(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def normalize_role(value: object) -> str | None:
    normalized = _coerce_non_empty_str(value)
    return normalized.lower() if normalized is not None else None


def _infer_capability_source_kind(capability_id: str) -> str:
    if capability_id.startswith("tool:"):
        return "tool"
    if capability_id.startswith("mcp:"):
        return "mcp"
    if capability_id.startswith("skill:"):
        return "skill"
    if capability_id.startswith("system:"):
        return "system"
    return "unknown"


def _prompt_capability_label(capability_id: str, *, name: str) -> str:
    normalized_name = _coerce_non_empty_str(name)
    if normalized_name is not None and normalized_name != capability_id:
        return normalized_name
    for prefix in ("tool:", "skill:", "mcp:", "system:"):
        if capability_id.startswith(prefix):
            return capability_id[len(prefix) :]
    return capability_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_evidence(record) -> dict[str, object]:
    return {
        "id": record.id,
        "task_id": record.task_id,
        "actor_ref": record.actor_ref,
        "environment_ref": record.environment_ref,
        "capability_ref": record.capability_ref,
        "risk_level": record.risk_level,
        "action_summary": record.action_summary,
        "result_summary": record.result_summary,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "status": record.status,
    }


__all__ = ["AgentProfileService"]
