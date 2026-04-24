# -*- coding: utf-8 -*-
from __future__ import annotations

from ..capabilities.lifecycle_assignment import (
    build_capability_lifecycle_assignment_payload,
)
from .service_capability_governance import (
    resolve_industry_capability_governance_service,
)
from .service_context import *  # noqa: F401,F403
from .service_recommendation_search import *  # noqa: F401,F403
from .service_recommendation_pack import *  # noqa: F401,F403
from .models import _normalize_text_list


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _unique_strings(*values: object) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _normalize_text_list(value):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


class _IndustryTeamRuntimeMixin:
    def sync_agent_runtime_capability_override(
        self,
        *,
        agent_id: str,
        capability_ids: list[str] | None,
    ) -> None:
        if not isinstance(agent_id, str) or not agent_id.strip():
            return
        runtime = _get_industry_executor_runtime(self, agent_id=agent_id)
        if runtime is None:
            return
        metadata = _industry_executor_metadata(runtime)
        layers = IndustrySeatCapabilityLayers.from_metadata(
            metadata.get("capability_layers"),
        )
        role_prototype_capability_ids = list(layers.role_prototype_capability_ids)
        role_prototype_capability_set = set(role_prototype_capability_ids)
        effective_capability_ids = _normalize_text_list(capability_ids)
        seat_instance_capability_ids = [
            capability_id
            for capability_id in effective_capability_ids
            if capability_id not in role_prototype_capability_set
        ]
        current_trial = (
            dict(metadata.get("current_capability_trial"))
            if isinstance(metadata.get("current_capability_trial"), dict)
            else {}
        )
        snapshot = resolve_industry_capability_governance_service(
            self,
        ).recompose_runtime_capability_layers(
            role_prototype_capability_ids=role_prototype_capability_ids,
            seat_instance_capability_ids=seat_instance_capability_ids,
            cycle_delta_capability_ids=list(layers.cycle_delta_capability_ids),
            session_overlay_capability_ids=list(layers.session_overlay_capability_ids),
            current_capability_trial=current_trial,
            target_role_id=_industry_executor_role_id(runtime),
            target_seat_ref=_string(metadata.get("selected_seat_ref")),
            selected_scope=_string(current_trial.get("selected_scope")),
            candidate_id=_string(current_trial.get("candidate_id")),
        )
        metadata["capability_layers"] = snapshot.layers_payload
        self._executor_runtime_service.upsert_runtime(
            runtime.model_copy(
                update={
                    "metadata": metadata,
                },
            ),
        )

    def attach_candidate_to_scope(
        self,
        *,
        target_agent_id: str,
        capability_ids: list[str] | None = None,
        replacement_capability_ids: list[str] | None = None,
        capability_assignment_mode: str = "merge",
        selected_scope: str = "seat",
        scope_ref: str | None = None,
        selected_seat_ref: str | None = None,
        candidate_id: str | None = None,
        target_role_id: str | None = None,
        lifecycle_stage: str | None = None,
        next_lifecycle_stage: str | None = None,
        replacement_target_ids: list[str] | None = None,
        rollback_target_ids: list[str] | None = None,
        trial_scope: str | None = None,
        reason: str | None = None,
        preflight: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if (
            self._executor_runtime_service is None
            or not isinstance(target_agent_id, str)
            or not target_agent_id.strip()
        ):
            return {"success": False, "error": "Executor runtime service is not available"}
        runtime = _get_industry_executor_runtime(self, agent_id=target_agent_id)
        if runtime is None:
            runtime = self._seed_agent_runtime_for_scope_attach(
                agent_id=target_agent_id,
                target_role_id=target_role_id,
                selected_seat_ref=selected_seat_ref,
            )
            if runtime is None:
                return {"success": False, "error": f"Target agent '{target_agent_id}' is not available"}
        metadata = _industry_executor_metadata(runtime)
        if selected_seat_ref:
            metadata["selected_seat_ref"] = selected_seat_ref
        layers = IndustrySeatCapabilityLayers.from_metadata(
            metadata.get("capability_layers"),
        )
        normalized_scope = str(selected_scope or "seat").strip().lower() or "seat"
        normalized_capability_ids = _normalize_text_list(capability_ids)
        normalized_replacement_ids = _unique_strings(
            replacement_capability_ids,
            replacement_target_ids,
        )
        assignment_mode = (
            capability_assignment_mode
            if capability_assignment_mode in {"merge", "replace"}
            else "merge"
        )
        resolved_target_role_id = _string(target_role_id) or _string(
            _industry_executor_role_id(runtime),
        )
        resolved_seat_ref = _string(selected_seat_ref) or _string(
            metadata.get("selected_seat_ref"),
        )
        governance_service = resolve_industry_capability_governance_service(self)
        replacement_pressure = governance_service.resolve_replacement_pressure(
            replacement_target_ids=normalized_replacement_ids,
            target_role_id=resolved_target_role_id,
            target_seat_ref=resolved_seat_ref,
            selected_scope=normalized_scope,
        )
        allowed_replacement_ids = list(
            replacement_pressure.get("allowed_replacement_target_ids") or [],
        )
        if normalized_scope == "session":
            session_overlay_capability_ids = self._mutate_scope_capabilities(
                existing_capability_ids=layers.session_overlay_capability_ids,
                capability_ids=normalized_capability_ids,
                replacement_capability_ids=allowed_replacement_ids,
                capability_assignment_mode=assignment_mode,
            )
            scope_type = "session"
            resolved_scope_ref = _string(scope_ref) or _string(selected_seat_ref) or target_agent_id
            current_session_overlay = {
                "overlay_scope": "session",
                "overlay_mode": "additive",
                "session_id": resolved_scope_ref,
                "capability_ids": session_overlay_capability_ids,
                "status": "active",
                "candidate_id": candidate_id,
            }
            seat_instance_capability_ids = list(layers.seat_instance_capability_ids)
        else:
            seat_instance_capability_ids = self._mutate_scope_capabilities(
                existing_capability_ids=layers.seat_instance_capability_ids,
                capability_ids=normalized_capability_ids,
                replacement_capability_ids=allowed_replacement_ids,
                capability_assignment_mode=assignment_mode,
            )
            session_overlay_capability_ids = list(layers.session_overlay_capability_ids)
            scope_type = "seat" if _string(selected_seat_ref) is not None else "agent"
            resolved_scope_ref = _string(scope_ref) or _string(selected_seat_ref) or target_agent_id
            metadata.pop("current_session_overlay", None)
            current_session_overlay = None
        trial_id = (
            f"trial:{candidate_id}:{resolved_scope_ref}"
            if candidate_id
            else f"trial:{target_agent_id}:{resolved_scope_ref}"
        )
        current_trial = {
            "candidate_id": _string(candidate_id),
            "skill_trial_id": trial_id,
            "skill_candidate_id": _string(candidate_id),
            "skill_lifecycle_stage": _string(lifecycle_stage) or "trial",
            "selected_scope": normalized_scope,
            "selected_seat_ref": _string(selected_seat_ref),
            "scope_ref": resolved_scope_ref,
            "scope_type": scope_type,
            "target_agent_id": target_agent_id,
            "target_role_id": _string(target_role_id),
            "trial_scope": _string(trial_scope),
            "replacement_target_ids": _unique_strings(
                replacement_target_ids,
                normalized_replacement_ids,
            ),
            "rollback_target_ids": _normalize_text_list(rollback_target_ids),
            "capability_ids": normalized_capability_ids,
            "reason": _string(reason),
            "next_lifecycle_stage": _string(next_lifecycle_stage),
            "preflight": dict(preflight or {}),
        }
        snapshot = governance_service.recompose_runtime_capability_layers(
            role_prototype_capability_ids=list(layers.role_prototype_capability_ids),
            seat_instance_capability_ids=seat_instance_capability_ids,
            cycle_delta_capability_ids=list(layers.cycle_delta_capability_ids),
            session_overlay_capability_ids=session_overlay_capability_ids,
            current_capability_trial=current_trial,
            target_role_id=resolved_target_role_id,
            target_seat_ref=resolved_seat_ref,
            selected_scope=normalized_scope,
            candidate_id=_string(candidate_id),
        )
        metadata["capability_layers"] = snapshot.layers_payload
        metadata["current_capability_trial"] = current_trial
        if current_session_overlay is not None:
            metadata["current_session_overlay"] = {
                **current_session_overlay,
                "capability_ids": list(
                    snapshot.layers_payload.get("session_overlay_capability_ids") or [],
                ),
            }
        self._executor_runtime_service.upsert_runtime(
            runtime.model_copy(
                update={
                    "metadata": metadata,
                },
            ),
        )
        return {
            "success": True,
            "summary": (
                f"Attached candidate capabilities to {normalized_scope} scope "
                f"'{resolved_scope_ref}' for '{target_agent_id}'."
            ),
            "trial_id": trial_id,
            "selected_scope": normalized_scope,
            "scope_type": scope_type,
            "scope_ref": resolved_scope_ref,
            "attached_capability_ids": normalized_capability_ids,
            "replacement_target_ids": _unique_strings(
                replacement_target_ids,
                normalized_replacement_ids,
            ),
            "governance_result": snapshot.governance_result,
        }

    def _seed_agent_runtime_for_scope_attach(
        self,
        *,
        agent_id: str,
        target_role_id: str | None,
        selected_seat_ref: str | None,
    ) -> ExecutorRuntimeInstanceRecord | None:
        if self._executor_runtime_service is None:
            return None
        profile_getter = getattr(self._agent_profile_service, "get_agent", None)
        profile = profile_getter(agent_id) if callable(profile_getter) else None
        detail_getter = getattr(self._agent_profile_service, "get_agent_detail", None)
        detail = detail_getter(agent_id) if callable(detail_getter) else None
        runtime_detail = (
            dict((detail or {}).get("runtime"))
            if isinstance((detail or {}).get("runtime"), dict)
            else {}
        )
        runtime_metadata = (
            dict(runtime_detail.get("metadata"))
            if isinstance(runtime_detail.get("metadata"), dict)
            else {}
        )
        if profile is None:
            profile = (
                self._resolve_agent_profile(agent_id)
                if callable(getattr(self, "_resolve_agent_profile", None))
                else None
            )
        if profile is None:
            return None
        normalized_role_id = _string(target_role_id) or _string(
            getattr(profile, "industry_role_id", None),
        )
        detail_layers = IndustrySeatCapabilityLayers.from_metadata(
            runtime_metadata.get("capability_layers"),
        )
        metadata = {
            "selected_seat_ref": _string(selected_seat_ref)
            or _string(runtime_metadata.get("selected_seat_ref")),
            "owner_agent_id": agent_id,
            "industry_instance_id": _string(getattr(profile, "industry_instance_id", None)),
            "industry_role_id": normalized_role_id or _string(runtime_detail.get("industry_role_id")),
            "display_name": _string(getattr(profile, "name", None)),
            "role_name": _string(getattr(profile, "role_name", None)),
            "desired_state": "active",
            "seat_runtime_status": "idle",
            "capability_layers": (
                detail_layers.to_metadata_payload()
                if detail_layers.merged_capability_ids()
                or detail_layers.role_prototype_capability_ids
                or detail_layers.seat_instance_capability_ids
                or detail_layers.session_overlay_capability_ids
                else IndustrySeatCapabilityLayers(
                    role_prototype_capability_ids=_normalize_text_list(
                        getattr(profile, "capabilities", None),
                    ),
                ).to_metadata_payload()
            ),
        }
        runtime = self._executor_runtime_service.create_or_reuse_runtime(
            executor_id=self._industry_executor_id(
                instance_id=_string(getattr(profile, "industry_instance_id", None)) or "industry",
                agent_id=agent_id,
            ),
            protocol_kind="cli_runtime",
            scope_kind="role",
            role_id=normalized_role_id or _string(runtime_detail.get("industry_role_id")) or agent_id,
            thread_id=f"agent-chat:{agent_id}",
            metadata=metadata,
        )
        return self._executor_runtime_service.mark_runtime_ready(
            runtime.runtime_id,
            thread_id=f"agent-chat:{agent_id}",
            metadata=metadata,
        )

    @staticmethod
    def _mutate_scope_capabilities(
        *,
        existing_capability_ids: list[str] | None,
        capability_ids: list[str] | None,
        replacement_capability_ids: list[str] | None,
        capability_assignment_mode: str,
    ) -> list[str]:
        resolved_existing = _normalize_text_list(existing_capability_ids)
        resolved_capability_ids = _normalize_text_list(capability_ids)
        resolved_replacement_ids = _normalize_text_list(replacement_capability_ids)
        if capability_assignment_mode == "replace":
            final_capability_ids = [
                capability_id
                for capability_id in resolved_existing
                if capability_id not in resolved_replacement_ids
            ]
        else:
            final_capability_ids = list(resolved_existing)
        for capability_id in resolved_capability_ids:
            if capability_id not in final_capability_ids:
                final_capability_ids.append(capability_id)
        return final_capability_ids

    @staticmethod
    def _industry_executor_id(*, instance_id: str, agent_id: str) -> str:
        return f"industry-seat:{instance_id}:{agent_id}"

    def _build_actor_runtime_capability_layers(
        self,
        *,
        agent: IndustryRoleBlueprint,
        existing_metadata: dict[str, object],
    ) -> dict[str, object]:
        existing_layers = IndustrySeatCapabilityLayers.from_metadata(
            existing_metadata.get("capability_layers"),
        )
        non_role_capability_ids = {
            capability_id.lower()
            for capability_id in _unique_strings(
                existing_layers.seat_instance_capability_ids,
                existing_layers.cycle_delta_capability_ids,
                existing_layers.session_overlay_capability_ids,
            )
        }
        role_prototype_capability_ids = [
            capability_id
            for capability_id in _normalize_text_list(agent.allowed_capabilities)
            if capability_id.lower() not in non_role_capability_ids
        ]
        current_trial = (
            dict(existing_metadata.get("current_capability_trial"))
            if isinstance(existing_metadata.get("current_capability_trial"), dict)
            else {}
        )
        snapshot = resolve_industry_capability_governance_service(
            self,
        ).recompose_runtime_capability_layers(
            role_prototype_capability_ids=role_prototype_capability_ids,
            seat_instance_capability_ids=list(existing_layers.seat_instance_capability_ids),
            cycle_delta_capability_ids=list(existing_layers.cycle_delta_capability_ids),
            session_overlay_capability_ids=list(existing_layers.session_overlay_capability_ids),
            current_capability_trial=current_trial,
            target_role_id=_string(agent.role_id),
            target_seat_ref=_string(existing_metadata.get("selected_seat_ref")),
            selected_scope=_string(current_trial.get("selected_scope")),
            candidate_id=_string(current_trial.get("candidate_id")),
        )
        return snapshot.layers_payload

    def _ensure_execution_core_work_context(
        self,
        *,
        agent: IndustryRoleBlueprint,
        instance_id: str,
        owner_scope: str | None,
    ) -> str | None:
        service = getattr(self, "_work_context_service", None)
        ensure_context = getattr(service, "ensure_context", None)
        if not callable(ensure_context):
            return None
        canonical_thread_id = f"industry-chat:{instance_id}:{EXECUTION_CORE_ROLE_ID}"
        context = ensure_context(
            context_key=f"control-thread:{canonical_thread_id}",
            title=f"{agent.role_name or agent.name} control thread",
            summary=(
                f"Formal work context for the execution core control thread of "
                f"industry instance '{instance_id}'."
            ),
            context_type="industry-control-thread",
            owner_scope=owner_scope,
            owner_agent_id=agent.agent_id,
            industry_instance_id=instance_id,
            primary_thread_id=canonical_thread_id,
            source_kind="industry-thread-binding",
            source_ref=f"{instance_id}:{EXECUTION_CORE_ROLE_ID}",
            metadata={
                "agent_id": agent.agent_id,
                "industry_role_id": EXECUTION_CORE_ROLE_ID,
                "canonical_thread_id": canonical_thread_id,
            },
        )
        return _string(getattr(context, "id", None))

    async def _finalize_install_assignments(
        self,
        *,
        plan: _IndustryPlan,
        install_plan: list[IndustryBootstrapInstallItem],
        install_results: list[IndustryBootstrapInstallResult],
    ) -> None:
        if not install_plan or not install_results:
            return
        apply_capability_lifecycle = self._resolve_system_executor(
            "system:apply_capability_lifecycle",
        )
        if apply_capability_lifecycle is None:
            raise ValueError("Capability lifecycle executor is not available.")
        recommendation_by_id = {
            item.recommendation_id: item
            for item in plan.recommendation_pack.items
            if item.recommendation_id
        }
        for item, result in zip(install_plan, install_results):
            if result.status == "failed":
                continue
            recommendation = (
                recommendation_by_id.get(item.recommendation_id)
                if item.recommendation_id
                else None
            )
            target_agent_ids = self._resolve_install_targets(
                team=plan.draft.team,
                item=item,
                recommendation=recommendation,
            )
            capability_ids = _unique_strings(result.capability_ids)
            if not capability_ids:
                template_spec = get_install_template(
                    item.template_id,
                    capability_service=self._capability_service,
                    browser_runtime_service=self._get_browser_runtime_service(),
                    include_runtime=True,
                )
                capability_ids = self._resolve_install_capabilities(
                    item=item,
                    recommendation=recommendation,
                    client_key=result.client_key,
                    template=template_spec,
                )
            assignment_results: list[IndustryBootstrapInstallAssignmentResult] = []
            for agent_id in target_agent_ids:
                lifecycle_payload = build_capability_lifecycle_assignment_payload(
                    agent_profile_service=self._agent_profile_service,
                    target_agent_id=agent_id,
                    capability_ids=capability_ids,
                    capability_assignment_mode=item.capability_assignment_mode,
                    reason=f"Industry bootstrap install plan: {item.template_id}",
                    actor="copaw-main-brain",
                )
                assignment_response = await apply_capability_lifecycle(
                    payload=lifecycle_payload,
                )
                assignment_success = bool(assignment_response.get("success"))
                assignment_detail = str(
                    assignment_response.get("summary")
                    or assignment_response.get("error")
                    or (
                        f"Assigned {', '.join(capability_ids)} to '{agent_id}'."
                        if assignment_success
                        else f"Failed to assign capabilities to '{agent_id}'."
                    )
                )
                if not assignment_success and item.required:
                    raise ValueError(assignment_detail)
                assignment_results.append(
                    IndustryBootstrapInstallAssignmentResult(
                        agent_id=agent_id,
                        capability_ids=capability_ids,
                        status="assigned" if assignment_success else "failed",
                        detail=assignment_detail,
                        routes={
                            "agent": f"/api/runtime-center/agents/{agent_id}",
                        },
                    ),
                )
            result.assignment_results = assignment_results

    def _reconcile_draft_actors(
        self,
        *,
        draft: IndustryDraftPlan,
        existing: IndustryInstanceRecord | None,
    ) -> IndustryDraftPlan:
        if existing is None:
            return draft
        existing_team = self._materialize_team_blueprint(existing)
        used_existing_agent_ids: set[str] = set()
        agent_id_mapping: dict[str, str] = {}
        reconciled_agents: list[IndustryRoleBlueprint] = []
        for role in draft.team.agents:
            matched = self._match_existing_role_blueprint(
                existing_team=existing_team,
                role=role,
                used_existing_agent_ids=used_existing_agent_ids,
            )
            if matched is None:
                reconciled = role
            else:
                used_existing_agent_ids.add(matched.role.agent_id)
                reconciled = role.model_copy(
                    update={
                        "agent_id": matched.role.agent_id,
                        "actor_key": _string(role.actor_key) or _string(matched.role.actor_key),
                        "actor_fingerprint": (
                            _string(role.actor_fingerprint)
                            or matched.current_fingerprint
                            or _string(matched.role.actor_fingerprint)
                        ),
                    },
                )
            agent_id_mapping[role.agent_id] = reconciled.agent_id
            reconciled_agents.append(reconciled)

        reconciled_goals = [
            goal.model_copy(
                update={
                    "owner_agent_id": agent_id_mapping.get(
                        goal.owner_agent_id,
                        goal.owner_agent_id,
                    ),
                },
            )
            for goal in draft.goals
        ]
        reconciled_schedules = [
            schedule.model_copy(
                update={
                    "owner_agent_id": agent_id_mapping.get(
                        schedule.owner_agent_id,
                        schedule.owner_agent_id,
                    ),
                },
            )
            for schedule in draft.schedules
        ]
        return draft.model_copy(
            update={
                "team": draft.team.model_copy(update={"agents": reconciled_agents}),
                "goals": reconciled_goals,
                "schedules": reconciled_schedules,
            },
        )

    def _match_existing_role_blueprint(
        self,
        *,
        existing_team: IndustryTeamBlueprint,
        role: IndustryRoleBlueprint,
        used_existing_agent_ids: set[str],
    ) -> _ActorMatchResult | None:
        candidates = [
            candidate
            for candidate in existing_team.agents
            if candidate.agent_id not in used_existing_agent_ids
        ]
        if not candidates:
            return None

        target_actor_key = _string(role.actor_key)
        target_actor_fingerprint = _string(role.actor_fingerprint)
        target_role_id = _string(role.role_id)
        target_goal_kind = self._normalize_identity_token(role.goal_kind)
        target_role_name = self._normalize_identity_token(role.role_name or role.name)
        legacy_candidates = [
            candidate
            for candidate in candidates
            if _string(candidate.actor_key) is None
        ]

        def _build_match(candidate: IndustryRoleBlueprint, match_kind: str) -> _ActorMatchResult:
            previous_fingerprint = _string(candidate.actor_fingerprint)
            current_fingerprint = target_actor_fingerprint or previous_fingerprint
            semantic_drift = bool(
                target_actor_fingerprint
                and previous_fingerprint
                and previous_fingerprint != target_actor_fingerprint
            )
            return _ActorMatchResult(
                role=candidate,
                match_kind=match_kind,
                semantic_drift=semantic_drift,
                previous_fingerprint=previous_fingerprint,
                current_fingerprint=current_fingerprint,
            )

        if target_actor_key is not None:
            for candidate in candidates:
                if _string(candidate.actor_key) == target_actor_key:
                    return _build_match(candidate, "actor_key")

        if target_actor_fingerprint is not None:
            fingerprint_candidates = candidates if target_actor_key is None else legacy_candidates
            for candidate in fingerprint_candidates:
                if _string(candidate.actor_fingerprint) == target_actor_fingerprint:
                    return _build_match(candidate, "actor_fingerprint")

        if target_role_id is not None:
            for candidate in legacy_candidates:
                if _string(candidate.role_id) == target_role_id:
                    return _build_match(candidate, "legacy-role_id")
        if target_goal_kind:
            for candidate in legacy_candidates:
                if self._normalize_identity_token(candidate.goal_kind) == target_goal_kind:
                    return _build_match(candidate, "legacy-goal_kind")
        if target_role_name:
            for candidate in legacy_candidates:
                if self._normalize_identity_token(candidate.role_name or candidate.name) == target_role_name:
                    return _build_match(candidate, "legacy-role_name")
        return None

    def _normalize_identity_token(self, value: object | None) -> str:
        text = _string(value) or ""
        return "".join(character for character in text.lower() if character.isalnum())

    def _sync_actor_runtime_surface(
        self,
        *,
        agent: IndustryRoleBlueprint,
        instance_id: str,
        owner_scope: str | None,
        goal_id: str | None,
        goal_title: str | None,
        status: str | None,
        assignment_id: str | None = None,
        assignment_title: str | None = None,
        assignment_summary: str | None = None,
        assignment_status: str | None = None,
    ) -> None:
        runtime = self._upsert_actor_runtime(
            agent=agent,
            instance_id=instance_id,
            owner_scope=owner_scope,
            goal_id=goal_id,
            goal_title=goal_title,
            status=status,
            assignment_id=assignment_id,
            assignment_title=assignment_title,
            assignment_summary=assignment_summary,
            assignment_status=assignment_status,
        )
        if runtime is None:
            return
        if is_execution_core_agent_id(agent.agent_id):
            self._upsert_execution_core_thread_bindings(
                runtime=runtime,
                agent=agent,
                instance_id=instance_id,
                owner_scope=owner_scope,
            )
            return
        self._upsert_agent_thread_bindings(
            runtime=runtime,
            agent=agent,
            instance_id=instance_id,
            owner_scope=owner_scope,
        )

    def _upsert_actor_runtime(
        self,
        *,
        agent: IndustryRoleBlueprint,
        instance_id: str,
        owner_scope: str | None,
        goal_id: str | None,
        goal_title: str | None,
        status: str | None,
        assignment_id: str | None,
        assignment_title: str | None,
        assignment_summary: str | None,
        assignment_status: str | None,
    ) -> ExecutorRuntimeInstanceRecord | None:
        service = self._executor_runtime_service
        if service is None:
            return None
        existing = _get_industry_executor_runtime(
            self,
            industry_instance_id=instance_id,
            agent_id=agent.agent_id,
            role_id=agent.role_id,
        )
        existing_metadata = _industry_executor_metadata(existing)
        now = _utc_now()
        desired_state = "retired" if status == "retired" else "active"
        assignment_active = bool(
            assignment_id and assignment_status not in {"completed", "failed", "cancelled"}
        )
        existing_desired_state = _string(existing_metadata.get("desired_state"))
        if existing is not None and existing_desired_state == "paused":
            desired_state = "paused"
            seat_runtime_status = "paused"
        elif status == "retired":
            seat_runtime_status = "retired"
        elif status == "blocked":
            seat_runtime_status = "blocked"
        elif status == "running":
            seat_runtime_status = "running"
        elif status == "waiting":
            seat_runtime_status = "waiting" if assignment_active else "idle"
        else:
            seat_runtime_status = "idle"
        if (
            existing is not None
            and status in {"idle", "waiting"}
            and seat_runtime_status not in {"paused", "retired"}
        ):
            existing_queue_depth = int(existing_metadata.get("queue_depth") or 0)
            existing_seat_runtime_status = _string(existing_metadata.get("seat_runtime_status"))
            if existing_seat_runtime_status == "blocked" and (
                _string(existing_metadata.get("current_task_id")) is not None
                or existing_queue_depth > 0
                or _string(existing_metadata.get("last_error_summary")) is not None
            ):
                seat_runtime_status = "blocked"
            elif _string(existing_metadata.get("current_task_id")) is not None:
                seat_runtime_status = "running"
            elif existing_queue_depth > 0:
                seat_runtime_status = "running"
            elif assignment_active:
                seat_runtime_status = "waiting"
        incoming_actor_key = _string(agent.actor_key) or _string(existing_metadata.get("actor_key")) or f"{instance_id}:{agent.role_id}"
        incoming_actor_fingerprint = _string(agent.actor_fingerprint) or _string(existing_metadata.get("actor_fingerprint"))
        metadata = dict(existing_metadata)
        current_focus_kind = _string(metadata.get("current_focus_kind"))
        current_focus_id = _string(metadata.get("current_focus_id"))
        current_focus = _string(metadata.get("current_focus"))
        assignment_terminal = bool(
            assignment_id and assignment_status in {"completed", "failed", "cancelled"}
        )
        if assignment_active:
            current_focus_kind = "assignment"
            current_focus_id = assignment_id
            current_focus = assignment_title or assignment_summary or assignment_id
        elif current_focus_kind == "assignment" and (
            assignment_id is None
            or assignment_terminal
            or current_focus_id == assignment_id
        ):
            current_focus_kind = None
            current_focus_id = None
            current_focus = None
        metadata.pop("goal_id", None)
        metadata.pop("goal_title", None)
        metadata.update(
            {
                "owner_scope": owner_scope,
                "current_focus_kind": current_focus_kind,
                "current_focus_id": current_focus_id,
                "current_focus": current_focus,
                "employment_mode": agent.employment_mode,
                "environment_constraints": list(agent.environment_constraints),
                "evidence_expectations": list(agent.evidence_expectations),
                "capability_layers": self._build_actor_runtime_capability_layers(
                    agent=agent,
                    existing_metadata=metadata,
                ),
                "retired": status == "retired",
            },
        )
        for key in ("current_focus_kind", "current_focus_id", "current_focus"):
            if metadata.get(key) is None:
                metadata.pop(key, None)
        assignment_metadata = (
            {
                "current_assignment_id": None,
                "current_assignment_title": None,
                "current_assignment_summary": None,
                "current_assignment_status": None,
            }
            if assignment_terminal
            else {
                "current_assignment_id": assignment_id,
                "current_assignment_title": assignment_title,
                "current_assignment_summary": assignment_summary,
                "current_assignment_status": assignment_status,
            }
        )
        for key, value in assignment_metadata.items():
            if value is None:
                metadata.pop(key, None)
            else:
                metadata[key] = value
        previous_fingerprint = (
            _string(existing_metadata.get("actor_fingerprint"))
            if existing is not None
            else None
        )
        if previous_fingerprint and incoming_actor_fingerprint and previous_fingerprint != incoming_actor_fingerprint:
            metadata["actor_semantic_drift"] = {
                "previous_fingerprint": previous_fingerprint,
                "current_fingerprint": incoming_actor_fingerprint,
                "detected_at": now.isoformat(),
            }
        update = {
            "owner_agent_id": agent.agent_id,
            "industry_instance_id": instance_id,
            "industry_role_id": agent.role_id,
            "actor_key": incoming_actor_key,
            "actor_fingerprint": incoming_actor_fingerprint,
            "desired_state": desired_state,
            "seat_runtime_status": seat_runtime_status,
            "employment_mode": agent.employment_mode,
            "activation_mode": agent.activation_mode,
            "persistent": agent.activation_mode != "on-demand",
            "display_name": agent.name,
            "role_name": agent.role_name,
            "queue_depth": 0 if status == "retired" else int(metadata.get("queue_depth") or 0),
            "current_task_id": None if status == "retired" else _string(metadata.get("current_task_id")),
            "current_environment_id": _string(metadata.get("current_environment_id")),
            "last_started_at": metadata.get("last_started_at") or (now.isoformat() if seat_runtime_status == "running" else None),
            "last_heartbeat_at": now.isoformat(),
            "last_stopped_at": now.isoformat() if status == "retired" else _string(metadata.get("last_stopped_at")),
            "last_result_summary": goal_title or _string(metadata.get("last_result_summary")),
            "last_error_summary": _string(metadata.get("last_error_summary")) if status == "retired" else None,
            "last_checkpoint_id": _string(metadata.get("last_checkpoint_id")),
        }
        metadata.update(update)
        top_level_status = (
            "stopped"
            if seat_runtime_status == "retired"
            else "degraded"
            if seat_runtime_status == "blocked"
            else "ready"
        )
        thread_id = (
            f"industry-chat:{instance_id}:{EXECUTION_CORE_ROLE_ID}"
            if is_execution_core_agent_id(agent.agent_id)
            else f"agent-chat:{agent.agent_id}"
        )
        executor_id = self._industry_executor_id(
            instance_id=instance_id,
            agent_id=agent.agent_id,
        )
        if existing is None:
            runtime = service.create_or_reuse_runtime(
                executor_id=executor_id,
                protocol_kind="cli_runtime",
                scope_kind="role",
                role_id=agent.role_id or agent.agent_id,
                thread_id=thread_id,
                metadata=metadata,
            )
        else:
            runtime = existing.model_copy(update=update)
        runtime_metadata = dict(runtime.metadata or {})
        for key in (
            "goal_id",
            "goal_title",
            "current_focus_kind",
            "current_focus_id",
            "current_focus",
            "current_assignment_id",
            "current_assignment_title",
            "current_assignment_summary",
            "current_assignment_status",
        ):
            if key not in metadata:
                runtime_metadata.pop(key, None)
        runtime_metadata.update(metadata)
        runtime_metadata["executor_runtime_managed"] = True
        runtime = service.upsert_runtime(
            runtime.model_copy(
                update={
                    "executor_id": executor_id,
                    "protocol_kind": "cli_runtime",
                    "scope_kind": "role",
                    "role_id": agent.role_id or agent.agent_id,
                    "thread_id": thread_id,
                    "runtime_status": top_level_status,
                    "metadata": runtime_metadata,
                    "updated_at": now,
                },
            ),
        )
        return runtime

    def _upsert_agent_thread_bindings(
        self,
        *,
        runtime: ExecutorRuntimeInstanceRecord,
        agent: IndustryRoleBlueprint,
        instance_id: str,
        owner_scope: str | None,
    ) -> None:
        service = self._executor_runtime_service
        if service is None or is_execution_core_agent_id(agent.agent_id):
            return
        primary_thread_id = f"agent-chat:{agent.agent_id}"
        alias_thread_id = f"industry-chat:{instance_id}:{agent.role_id}"
        desired_thread_ids = {primary_thread_id, alias_thread_id}
        for binding in _list_industry_executor_thread_bindings(
            self,
            industry_instance_id=instance_id,
            agent_id=agent.agent_id,
        ):
            if _string(getattr(binding, "thread_id", None)) not in desired_thread_ids:
                service.delete_thread_binding(binding.binding_id)
        for thread_id, binding_kind, alias_of_thread_id in (
            (primary_thread_id, "agent-primary", None),
            (alias_thread_id, "industry-role-alias", primary_thread_id),
        ):
            existing = _get_industry_executor_thread_binding(self, thread_id=thread_id)
            metadata = {
                "binding_kind": binding_kind,
                "industry_instance_id": instance_id,
                "industry_role_id": agent.role_id,
                "owner_scope": owner_scope,
                "owner_agent_id": agent.agent_id,
                "agent_name": agent.name,
                "role_name": agent.role_name,
                "alias_of_thread_id": alias_of_thread_id,
                "canonical_thread_id": primary_thread_id,
            }
            if existing is None:
                record = ExecutorThreadBindingRecord(
                    runtime_id=runtime.runtime_id,
                    role_id=agent.role_id,
                    executor_provider_id=runtime.executor_id,
                    project_profile_id=runtime.project_profile_id,
                    assignment_id=runtime.assignment_id,
                    thread_id=thread_id,
                    runtime_status=runtime.runtime_status,
                    last_turn_id=None,
                    last_seen_at=_utc_now(),
                    metadata=metadata,
                )
            else:
                record = existing.model_copy(
                    update={
                        "runtime_id": runtime.runtime_id,
                        "role_id": agent.role_id,
                        "executor_provider_id": runtime.executor_id,
                        "project_profile_id": runtime.project_profile_id,
                        "assignment_id": runtime.assignment_id,
                        "thread_id": thread_id,
                        "runtime_status": runtime.runtime_status,
                        "last_seen_at": _utc_now(),
                        "metadata": {**dict(existing.metadata or {}), **metadata},
                        "updated_at": _utc_now(),
                    },
                )
            service.upsert_thread_binding(record)

    def _upsert_execution_core_thread_bindings(
        self,
        *,
        runtime: ExecutorRuntimeInstanceRecord,
        agent: IndustryRoleBlueprint,
        instance_id: str,
        owner_scope: str | None,
    ) -> None:
        service = self._executor_runtime_service
        if service is None or not is_execution_core_agent_id(agent.agent_id):
            return
        canonical_thread_id = f"industry-chat:{instance_id}:{EXECUTION_CORE_ROLE_ID}"
        work_context_id = self._ensure_execution_core_work_context(
            agent=agent,
            instance_id=instance_id,
            owner_scope=owner_scope,
        )
        for binding in _list_industry_executor_thread_bindings(
            self,
            industry_instance_id=instance_id,
            role_id=EXECUTION_CORE_ROLE_ID,
        ):
            if _string(getattr(binding, "thread_id", None)) != canonical_thread_id:
                service.delete_thread_binding(binding.binding_id)
        existing = _get_industry_executor_thread_binding(self, thread_id=canonical_thread_id)
        metadata = {
            "binding_kind": "industry-role-alias",
            "industry_instance_id": instance_id,
            "industry_role_id": EXECUTION_CORE_ROLE_ID,
            "owner_scope": owner_scope,
            "owner_agent_id": agent.agent_id,
            "agent_name": agent.name,
            "role_name": agent.role_name,
            "work_context_id": work_context_id,
            "canonical_thread_id": canonical_thread_id,
        }
        if existing is None:
            record = ExecutorThreadBindingRecord(
                runtime_id=runtime.runtime_id,
                role_id=EXECUTION_CORE_ROLE_ID,
                executor_provider_id=runtime.executor_id,
                project_profile_id=runtime.project_profile_id,
                assignment_id=runtime.assignment_id,
                thread_id=canonical_thread_id,
                runtime_status=runtime.runtime_status,
                last_turn_id=None,
                last_seen_at=_utc_now(),
                metadata=metadata,
            )
        else:
            record = existing.model_copy(
                update={
                    "runtime_id": runtime.runtime_id,
                    "role_id": EXECUTION_CORE_ROLE_ID,
                    "executor_provider_id": runtime.executor_id,
                    "project_profile_id": runtime.project_profile_id,
                    "assignment_id": runtime.assignment_id,
                    "thread_id": canonical_thread_id,
                    "runtime_status": runtime.runtime_status,
                    "last_seen_at": _utc_now(),
                    "metadata": {**dict(existing.metadata or {}), **metadata},
                    "updated_at": _utc_now(),
                },
            )
        service.upsert_thread_binding(record)

    def _retire_stale_actors(
        self,
        *,
        instance_id: str,
        active_agent_ids: set[str],
    ) -> None:
        normalized_instance_id = _string(instance_id)
        if normalized_instance_id is None:
            return
        normalized_agent_ids = {
            agent_id.strip()
            for agent_id in active_agent_ids
            if isinstance(agent_id, str) and agent_id.strip()
        }
        now = _utc_now()
        for override in self._agent_profile_override_repository.list_overrides():
            if _string(override.industry_instance_id) != normalized_instance_id:
                continue
            agent_id = _string(override.agent_id)
            if agent_id is None or is_execution_core_agent_id(agent_id) or agent_id in normalized_agent_ids:
                continue
            self._agent_profile_override_repository.delete_override(agent_id)
            if self._executor_runtime_service is not None:
                for runtime in _list_industry_executor_runtimes(
                    self,
                    industry_instance_id=normalized_instance_id,
                    agent_id=agent_id,
                ):
                    self._executor_runtime_service.delete_runtime(runtime.runtime_id)
                for binding in _list_industry_executor_thread_bindings(
                    self,
                    industry_instance_id=normalized_instance_id,
                    agent_id=agent_id,
                ):
                    self._executor_runtime_service.delete_thread_binding(
                        binding.binding_id,
                    )

    def _build_readiness_checks(
        self,
        *,
        team: IndustryTeamBlueprint,
        schedule_count: int,
    ) -> list[IndustryReadinessCheck]:
        enabled_capability_count = 0
        lister = getattr(self._capability_service, "list_capabilities", None)
        if callable(lister):
            try:
                enabled_capability_count = len(list(lister(enabled_only=True)))
            except TypeError:
                try:
                    enabled_capability_count = len(list(lister()))
                except Exception:
                    enabled_capability_count = 0
            except Exception:
                enabled_capability_count = 0
        checks = [
            IndustryReadinessCheck(
                key="draft-generator",
                title="Draft generator",
                status="ready",
                detail="The preview draft was generated through the active chat model instead of a fixed role template.",
                context={
                    **self._draft_generator.describe(),
                },
            ),
            IndustryReadinessCheck(
                key="industry-state",
                title="Industry state store",
                status="ready",
                detail="Formal industry instance records will be written into the unified state store.",
            ),
            IndustryReadinessCheck(
                key="kernel-dispatch",
                title="Kernel dispatch path",
                status=(
                    "ready"
                    if getattr(self._goal_service, "_dispatcher", None) is not None
                    else "missing"
                ),
                detail="Goal actions will be compiled and dispatched through the unified kernel.",
            ),
            IndustryReadinessCheck(
                key="capability-graph",
                title="Capability graph",
                status="ready" if enabled_capability_count > 0 else "warning",
                detail=(
                    f"{enabled_capability_count} enabled capability mount(s) are visible to the industry team."
                    if enabled_capability_count > 0
                    else "No enabled capability mounts were discovered; bootstrap can continue but execution depth will be limited."
                ),
                required=False,
                context={"enabledCount": enabled_capability_count},
            ),
            IndustryReadinessCheck(
                key="agent-surface",
                title="Agent visibility surface",
                status="ready",
                detail=(
                    f"{len(team.agents)} team role(s) will be projected into Runtime Center and Agent Workbench."
                ),
                context={"roleCount": len(team.agents)},
            ),
            IndustryReadinessCheck(
                key="schedule-runtime",
                title="Schedule runtime",
                status=(
                    "ready"
                    if self._cron_manager is not None or self._schedule_writer is not None
                    else "missing"
                ),
                detail=(
                    f"{schedule_count} recurring schedule(s) can be persisted for this activation."
                    if self._cron_manager is not None or self._schedule_writer is not None
                    else "Schedule runtime is not wired; recurring reviews cannot be activated."
                ),
                context={"scheduleCount": schedule_count},
            ),
        ]
        return checks

