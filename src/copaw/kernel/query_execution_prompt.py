# -*- coding: utf-8 -*-
from __future__ import annotations

from ..memory.models import MemoryRecallHit
from .query_execution_shared import *  # noqa: F401,F403


class _QueryExecutionPromptMixin:
    def _assert_bound_chat_context(
        self,
        *,
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
    ) -> None:
        entry_source = _first_non_empty(getattr(request, "entry_source", None))
        channel = _first_non_empty(getattr(request, "channel", None))
        if entry_source not in {"chat", "industry", "agent-workbench"}:
            return
        if channel != DEFAULT_CHANNEL:
            return
        if agent_profile is not None:
            return
        raise ValueError(
            "当前聊天会话尚未绑定真实的行业/智能体运行主体。"
            "请先从行业团队或智能体工作台进入聊天。"
            f"当前兜底负责人为：{owner_agent_id}。"
        )

    def _build_profile_prompt_appendix(
        self,
        *,
        request: Any,
        msgs: list[Any],
        owner_agent_id: str,
        agent_profile: Any | None,
        kernel_task_id: str | None = None,
        mounted_capabilities: list[str] | None = None,
        desktop_actuation_available: bool = False,
        execution_context: dict[str, Any] | None = None,
        delegation_guard: _DelegationFirstGuard | None = None,
        industry_kickoff_summary: dict[str, Any] | None = None,
        chat_writeback_summary: dict[str, Any] | None = None,
        team_role_gap_summary: dict[str, Any] | None = None,
    ) -> str | None:
        profile = agent_profile
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(profile, "industry_instance_id", None) if profile is not None else None,
        )
        industry_label = _first_non_empty(getattr(request, "industry_label", None))
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(profile, "industry_role_id", None) if profile is not None else None,
        )
        industry_role_name = _first_non_empty(getattr(request, "industry_role_name", None))
        is_execution_core_runtime = bool(
            industry_instance_id
            and (
                is_execution_core_agent_id(owner_agent_id)
                or industry_role_id == EXECUTION_CORE_ROLE_ID
            )
        )
        execution_core_identity = (
            self._resolve_execution_core_identity_payload(
                industry_instance_id=industry_instance_id,
            )
            if is_execution_core_runtime
            else {}
        )
        strategy_memory = (
            self._resolve_active_strategy_memory_payload(
                industry_instance_id=industry_instance_id,
                owner_agent_id=owner_agent_id,
            )
            if is_execution_core_runtime
            else {}
        )
        owner_scope = _first_non_empty(getattr(request, "owner_scope", None))
        session_kind = _first_non_empty(getattr(request, "session_kind", None))
        task_mode = _first_non_empty(
            getattr(request, "task_mode", None),
            infer_industry_task_mode(
                role_id=industry_role_id,
                goal_kind=industry_role_id if is_execution_core_runtime else None,
                source="goal",
            )
            if industry_role_id
            else None,
        )
        task_mode_label = describe_industry_task_mode(task_mode)
        lines = [
            "# Runtime Agent Context",
            "",
            f"- Active agent id: {owner_agent_id}",
        ]
        if profile is None and not execution_core_identity:
            return "\n".join(lines)
        name = getattr(profile, "name", None) if profile is not None else None
        role_name = getattr(profile, "role_name", None) if profile is not None else None
        role_summary = (
            getattr(profile, "role_summary", None) if profile is not None else None
        )
        mission = getattr(profile, "mission", None) if profile is not None else None
        reports_to = getattr(profile, "reports_to", None) if profile is not None else None
        employment_mode = (
            getattr(profile, "employment_mode", None) if profile is not None else None
        )
        activation_mode = (
            getattr(profile, "activation_mode", None) if profile is not None else None
        )
        current_focus_kind = (
            getattr(profile, "current_focus_kind", None) if profile is not None else None
        )
        current_focus_id = (
            getattr(profile, "current_focus_id", None) if profile is not None else None
        )
        current_focus = getattr(profile, "current_focus", None) if profile is not None else None
        current_goal_id = (
            getattr(profile, "current_goal_id", None) if profile is not None else None
        )
        current_goal = getattr(profile, "current_goal", None) if profile is not None else None
        current_task_id = (
            getattr(profile, "current_task_id", None) if profile is not None else None
        )
        environment_summary = (
            getattr(profile, "environment_summary", None) if profile is not None else None
        )
        task_segment = _mapping_value((execution_context or {}).get("task_segment"))
        resume_point = _mapping_value((execution_context or {}).get("resume_point"))
        resume_checkpoint = _mapping_value(
            (execution_context or {}).get("resume_checkpoint"),
        )
        main_brain_runtime = _mapping_value(
            (execution_context or {}).get("main_brain_runtime"),
        )
        capabilities = mounted_capabilities or (
            getattr(profile, "capabilities", None) if profile is not None else None
        ) or []
        environment_constraints = _string_list(
            getattr(profile, "environment_constraints", None) if profile is not None else None,
        )
        evidence_expectations = _string_list(
            getattr(profile, "evidence_expectations", None) if profile is not None else None,
        )
        if execution_core_identity:
            role_name = _first_non_empty(
                industry_role_name,
                execution_core_identity.get("role_name"),
                role_name,
            )
            role_summary = _first_non_empty(
                execution_core_identity.get("role_summary"),
                role_summary,
            )
            mission = _first_non_empty(
                execution_core_identity.get("mission"),
                mission,
            )
            environment_constraints = _string_list(
                execution_core_identity.get("environment_constraints"),
            ) or environment_constraints
            evidence_expectations = _string_list(
                execution_core_identity.get("evidence_expectations"),
            ) or evidence_expectations
        if strategy_memory:
            mission = _first_non_empty(strategy_memory.get("mission"), mission)
            evidence_expectations = _string_list(
                strategy_memory.get("evidence_requirements"),
            ) or evidence_expectations
        goal_focus = self._resolve_industry_goal_focus(
            industry_instance_id=industry_instance_id,
            owner_agent_id=owner_agent_id,
            industry_role_id=industry_role_id,
            allow_execution_core_alias=is_execution_core_runtime,
        )
        if goal_focus is not None:
            current_goal_id = _first_non_empty(goal_focus.get("goal_id"), current_goal_id)
            current_goal = _first_non_empty(goal_focus.get("title"), current_goal)
        current_focus_kind = (
            current_focus_kind
            or ("goal" if current_goal_id or current_goal else None)
        )
        current_focus_id = _first_non_empty(current_focus_id, current_goal_id)
        current_focus = _first_non_empty(current_focus, current_goal)
        execution_feedback = self._resolve_recent_execution_feedback(
            goal_id=_first_non_empty(getattr(request, "goal_id", None), current_goal_id),
            task_id=_first_non_empty(
                getattr(request, "task_id", None),
                current_task_id,
                kernel_task_id,
            ),
        )
        if name:
            lines.append(f"- Display name: {name}")
        if role_name:
            lines.append(f"- Role: {role_name}")
        if role_summary:
            lines.append(f"- Role summary: {role_summary}")
        if mission:
            lines.append(f"- Mission: {mission}")
        if reports_to:
            lines.append(f"- Reports to: {reports_to}")
        if industry_label:
            lines.append(f"- Industry team: {industry_label}")
        if industry_instance_id:
            lines.append(f"- Industry instance id: {industry_instance_id}")
        if industry_role_name and industry_role_name != role_name:
            lines.append(f"- Industry runtime role: {industry_role_name}")
        if industry_role_id:
            lines.append(f"- Industry role id: {industry_role_id}")
        if owner_scope:
            lines.append(f"- Owner scope: {owner_scope}")
        if session_kind:
            lines.append(f"- Session kind: {session_kind}")
        if task_mode_label:
            lines.append(f"- Task mode: {task_mode_label}")
        if employment_mode in {"career", "temporary"}:
            lines.append(f"- Employment mode: {employment_mode} seat")
        if activation_mode in {"persistent", "on-demand"}:
            lines.append(f"- Activation mode: {activation_mode}")
        if environment_summary:
            lines.append(f"- Environment constraints: {environment_summary}")
        if environment_constraints:
            lines.append(
                f"- Environment policy: {', '.join(environment_constraints[:6])}",
            )
        if evidence_expectations:
            lines.append(
                f"- Expected evidence: {', '.join(evidence_expectations[:6])}",
            )
        if current_focus_id or current_focus:
            focus_text = current_focus or current_focus_id
            if current_focus_id and current_focus and current_focus_id != current_focus:
                focus_text = f"{current_focus} ({current_focus_id})"
            lines.append(f"- Current focus: {focus_text}")
        if current_task_id:
            lines.append(f"- Current task: {current_task_id}")
        if task_segment:
            segment_kind = _first_non_empty(task_segment.get("segment_kind"))
            segment_index = task_segment.get("index")
            segment_total = task_segment.get("total")
            if (
                isinstance(segment_kind, str)
                and isinstance(segment_index, int)
                and isinstance(segment_total, int)
            ):
                lines.append(
                    f"- Execution segment: {segment_kind} {segment_index + 1}/{segment_total}",
                )
            elif segment_kind:
                lines.append(f"- Execution segment: {segment_kind}")
        if resume_point.get("phase"):
            lines.append(f"- Resume phase: {resume_point.get('phase')}")
        if resume_checkpoint.get("id"):
            checkpoint_summary = _first_non_empty(
                resume_checkpoint.get("summary"),
                resume_checkpoint.get("phase"),
            )
            if checkpoint_summary is not None:
                lines.append(
                    f"- Resume checkpoint: {resume_checkpoint.get('id')} / {checkpoint_summary}",
                )
        main_brain_runtime_lines = self._build_main_brain_runtime_lines(
            main_brain_runtime=main_brain_runtime,
        )
        if main_brain_runtime_lines:
            lines.extend(["", "# Main Brain Runtime", *main_brain_runtime_lines])
        industry_brief_lines = self._build_industry_brief_lines(
            industry_instance_id=industry_instance_id,
        )
        if industry_brief_lines:
            lines.extend(["", "# Industry Brief", *industry_brief_lines])
        execution_core_identity_lines = self._build_execution_core_identity_lines(
            execution_core_identity=execution_core_identity,
        )
        if execution_core_identity_lines:
            lines.extend(
                ["", "# Execution Core Identity", *execution_core_identity_lines],
            )
        strategy_memory_lines = self._build_strategy_memory_lines(
            strategy_memory=strategy_memory,
        )
        if strategy_memory_lines:
            lines.extend(["", "# Strategy Memory", *strategy_memory_lines])
        execution_feedback_lines = _execution_feedback_prompt_lines(execution_feedback)
        if execution_feedback_lines:
            lines.extend(["", "# Execution Feedback", *execution_feedback_lines])
        chat_writeback_lines = self._build_chat_writeback_lines(
            chat_writeback_summary=chat_writeback_summary,
        )
        if chat_writeback_lines:
            lines.extend(["", "# Formal Writeback", *chat_writeback_lines])
        industry_kickoff_lines = self._build_industry_kickoff_lines(
            industry_kickoff_summary=industry_kickoff_summary,
        )
        if industry_kickoff_lines:
            lines.extend(["", "# Initial Kickoff", *industry_kickoff_lines])
        team_role_gap_lines = self._build_team_role_gap_lines(
            team_role_gap_summary=team_role_gap_summary,
        )
        if team_role_gap_lines:
            lines.extend(["", "# Team Gap Governance", *team_role_gap_lines])
        team_roster_lines = self._build_team_roster_lines(
            industry_instance_id=industry_instance_id,
            owner_agent_id=owner_agent_id,
        )
        if team_roster_lines:
            lines.extend(["", "# Team Roster", *team_roster_lines])
        delegation_policy_lines = self._build_delegation_policy_lines(
            delegation_guard=delegation_guard,
        )
        if delegation_policy_lines:
            lines.extend(["", "# Delegation Policy", *delegation_policy_lines])
        team_operating_lines = build_team_operating_model_lines(
            has_team_context=bool(industry_instance_id or industry_role_id or reports_to),
            is_execution_core_runtime=is_execution_core_runtime,
        )
        if team_operating_lines:
            lines.extend(["", "# Team Operating Model", *team_operating_lines])
        role_contract_lines = build_role_execution_contract_lines(
            role_id=industry_role_id,
            is_execution_core_runtime=is_execution_core_runtime,
        )
        if role_contract_lines:
            lines.extend(["", "# Role Contract", *role_contract_lines])
        task_mode_contract_lines = build_task_mode_contract_lines(task_mode)
        if task_mode_contract_lines:
            lines.extend(["", "# Task Mode", *task_mode_contract_lines])
        evidence_contract_lines = build_evidence_contract_lines(
            task_mode=task_mode,
            is_execution_core_runtime=is_execution_core_runtime,
        )
        if evidence_contract_lines:
            lines.extend(["", "# Evidence Contract", *evidence_contract_lines])
        knowledge_lines = self._build_retrieved_knowledge_lines(
            msgs=msgs,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            industry_role_id=industry_role_id,
            owner_scope=owner_scope,
            task_id=_first_non_empty(
                getattr(request, "task_id", None),
                current_task_id,
            ),
            work_context_id=_first_non_empty(
                getattr(request, "work_context_id", None),
                (execution_context or {}).get("work_context_id"),
            ),
            session_kind=session_kind,
        )
        if knowledge_lines:
            lines.extend(["", *knowledge_lines])
        execution_principle_lines = self._build_execution_principle_lines(
            is_execution_core_runtime=is_execution_core_runtime,
        )
        if execution_principle_lines:
            lines.extend(["", "# Execution Principles", *execution_principle_lines])
        capability_projection = self._resolve_prompt_capability_projection(
            owner_agent_id=owner_agent_id,
            capabilities=capabilities,
        )
        capability_card_lines = self._build_capability_card_lines(
            capability_projection=capability_projection,
        )
        if capability_card_lines:
            lines.extend(["", "# Role Capability Card", *capability_card_lines])
        if capabilities:
            preview = ", ".join(str(item) for item in capabilities[:8])
            if len(capabilities) > 8:
                preview = f"{preview}, ... (+{len(capabilities) - 8} more)"
            lines.append(f"- Mounted capabilities: {preview}")
        capability_guardrails = self._build_capability_guardrail_lines(
            capabilities,
            desktop_actuation_available=desktop_actuation_available,
        )
        if capability_guardrails:
            lines.extend(["", "# Capability Guardrails", *capability_guardrails])
        lines.extend(
            [
                "- Use only the currently mounted capabilities exposed in this session.",
                "- When the user asks for execution, act with mounted tools or dispatch capabilities instead of stopping at a verbal plan.",
                "- If the next operating step is unclear, first learn from mounted skills, retrieved knowledge, files/pages, or prior evidence, then continue from the updated procedure.",
                "- Learning first does not override missing capability, permission, approval, or user-owned verification checkpoints.",
                "- Keep behavior consistent with the active runtime role and goal.",
                "- This runtime is part of a team; consult the roster and collaborate rather than claiming you are the only active agent.",
                "- Do not describe this runtime as a generic sandbox; explain the actual mounted capabilities and missing surfaces instead.",
            ],
        )
        return "\n".join(lines)

    def _build_main_brain_runtime_lines(
        self,
        *,
        main_brain_runtime: dict[str, Any],
    ) -> list[str]:
        if not main_brain_runtime:
            return []
        intent = _mapping_value(main_brain_runtime.get("intent"))
        environment = _mapping_value(main_brain_runtime.get("environment"))
        recovery = _mapping_value(main_brain_runtime.get("recovery"))
        lines: list[str] = []
        source_kind = _first_non_empty(intent.get("source_kind"))
        intent_kind = _first_non_empty(intent.get("kind"))
        intent_mode = _first_non_empty(intent.get("mode"))
        route = None
        if source_kind and intent_kind and intent_mode:
            route = f"{source_kind} -> {intent_kind} ({intent_mode})"
        elif source_kind and intent_kind:
            route = f"{source_kind} -> {intent_kind}"
        elif intent_kind and intent_mode:
            route = f"{intent_kind} ({intent_mode})"
        else:
            route = _first_non_empty(source_kind, intent_kind, intent_mode)
        if route:
            lines.append(f"- Execution route: {route}")
        if environment.get("ref"):
            lines.append(f"- Environment binding: {environment.get('ref')}")
        if environment.get("session_id"):
            lines.append(f"- Environment session: {environment.get('session_id')}")
        continuity_source = _first_non_empty(environment.get("continuity_source"))
        continuity_token = _first_non_empty(environment.get("continuity_token"))
        if continuity_source and continuity_token:
            lines.append(
                f"- Continuity proof: {continuity_source} / {continuity_token}",
            )
        elif continuity_source:
            lines.append(f"- Continuity proof: {continuity_source}")
        elif continuity_token:
            lines.append(f"- Continuity proof: {continuity_token}")
        if "resume_ready" in environment:
            lines.append(
                "- Environment resume-ready: "
                + ("yes" if bool(environment.get("resume_ready")) else "no"),
            )
        recovery_mode = _first_non_empty(recovery.get("mode"))
        recovery_reason = _first_non_empty(recovery.get("reason"))
        recovery_contract = None
        if recovery_mode and recovery_reason:
            recovery_contract = f"{recovery_mode} / {recovery_reason}"
        else:
            recovery_contract = _first_non_empty(recovery_mode, recovery_reason)
        if recovery_contract:
            lines.append(f"- Recovery contract: {recovery_contract}")
        if recovery.get("checkpoint_id"):
            lines.append(f"- Recovery checkpoint: {recovery.get('checkpoint_id')}")
        if recovery.get("mailbox_id"):
            lines.append(f"- Recovery mailbox: {recovery.get('mailbox_id')}")
        if recovery.get("kernel_task_id"):
            lines.append(f"- Recovery kernel task: {recovery.get('kernel_task_id')}")
        return lines

    def _resolve_execution_core_identity_payload(
        self,
        *,
        industry_instance_id: str | None,
    ) -> dict[str, Any]:
        if not industry_instance_id:
            return {}
        instance = self._get_industry_instance(industry_instance_id)
        if instance is None:
            return {}
        return _mapping_value(
            _field_value(
                instance,
                "execution_core_identity",
                "execution_core_identity_payload",
            ),
        )

    def _build_execution_core_identity_lines(
        self,
        *,
        execution_core_identity: dict[str, Any],
    ) -> list[str]:
        if not execution_core_identity:
            return []
        lines: list[str] = []
        identity_label = _first_non_empty(execution_core_identity.get("identity_label"))
        industry_summary = _first_non_empty(
            execution_core_identity.get("industry_summary"),
        )
        operating_mode = _first_non_empty(
            execution_core_identity.get("operating_mode"),
        )
        thinking_axes = _string_list(execution_core_identity.get("thinking_axes"))
        delegation_policy = _string_list(
            execution_core_identity.get("delegation_policy"),
        )
        direct_execution_policy = _string_list(
            execution_core_identity.get("direct_execution_policy"),
        )
        if identity_label:
            lines.append(f"- Identity label: {identity_label}")
        if industry_summary:
            lines.append(f"- Industry mandate: {industry_summary}")
        if operating_mode:
            lines.append(f"- Operating mode: {operating_mode}")
        for axis in thinking_axes[:6]:
            lines.append(f"- Thinking axis: {axis}")
        for policy in delegation_policy[:3]:
            lines.append(f"- Delegation rule: {policy}")
        for policy in direct_execution_policy[:2]:
            lines.append(f"- Direct execution rule: {policy}")
        return lines

    def _resolve_active_strategy_memory_payload(
        self,
        *,
        industry_instance_id: str | None,
        owner_agent_id: str | None,
    ) -> dict[str, Any]:
        strategy = resolve_strategy_payload(
            service=self._strategy_memory_service,
            scope_type="industry",
            scope_id=industry_instance_id,
            owner_agent_id=owner_agent_id,
            fallback_owner_agent_ids=[EXECUTION_CORE_AGENT_ID, None],
        )
        return _mapping_value(strategy) if strategy else {}

    def _build_strategy_memory_lines(
        self,
        *,
        strategy_memory: dict[str, Any],
    ) -> list[str]:
        if not strategy_memory:
            return []
        lines: list[str] = []
        north_star = _first_non_empty(strategy_memory.get("north_star"))
        summary = _first_non_empty(strategy_memory.get("summary"))
        priorities = _string_list(strategy_memory.get("priority_order"))
        delegation_policy = _string_list(strategy_memory.get("delegation_policy"))
        direct_execution_policy = _string_list(
            strategy_memory.get("direct_execution_policy"),
        )
        execution_constraints = _string_list(
            strategy_memory.get("execution_constraints"),
        )
        active_goals = _string_list(strategy_memory.get("active_goal_titles"))
        metadata = _mapping_value(strategy_memory.get("metadata"))
        planning_mode = _first_non_empty(metadata.get("experience_mode"))
        experience_notes = _first_non_empty(metadata.get("experience_notes"))
        operator_requirements = _string_list(
            metadata.get("operator_requirements"),
        )
        if north_star:
            lines.append(f"- North star: {north_star}")
        if summary:
            lines.append(f"- Strategy summary: {summary}")
        if planning_mode == "operator-guided":
            lines.append("- Planning mode: follow the operator's existing experience and explicit requirements.")
        elif planning_mode == "system-led":
            lines.append("- Planning mode: system-led full-loop planning.")
        if experience_notes:
            lines.append(f"- Operator playbook: {experience_notes}")
        for requirement in operator_requirements[:4]:
            lines.append(f"- Must include: {requirement}")
        for goal_title in active_goals[:4]:
            lines.append(f"- Active goal: {goal_title}")
        for priority in priorities[:4]:
            lines.append(f"- Priority: {priority}")
        for policy in delegation_policy[:3]:
            lines.append(f"- Delegation rule: {policy}")
        for policy in direct_execution_policy[:2]:
            lines.append(f"- Direct execution rule: {policy}")
        for constraint in execution_constraints[:4]:
            lines.append(f"- Execution constraint: {constraint}")
        return lines

    def _resolve_recent_execution_feedback(
        self,
        *,
        goal_id: str | None,
        task_id: str | None,
    ) -> dict[str, Any]:
        task_repository = self._task_repository
        if task_repository is None:
            return {}
        related_tasks: list[Any] = []
        resolved_goal_id = _first_non_empty(goal_id)
        if resolved_goal_id:
            related_tasks = task_repository.list_tasks(goal_id=resolved_goal_id)
        if not related_tasks:
            resolved_task_id = _first_non_empty(task_id)
            current_task = (
                task_repository.get_task(resolved_task_id)
                if resolved_task_id
                else None
            )
            if current_task is not None:
                task_goal_id = _first_non_empty(getattr(current_task, "goal_id", None))
                if task_goal_id:
                    related_tasks = task_repository.list_tasks(goal_id=task_goal_id)
                else:
                    related_tasks = [current_task]
                    related_tasks.extend(
                        task_repository.list_tasks(parent_task_id=current_task.id, limit=8),
                    )
        if not related_tasks:
            return {}
        related_tasks = [
            task
            for task in related_tasks
            if str(getattr(task, "task_type", "") or "") != "learning-patch"
        ]
        return _mapping_value(
            collect_recent_execution_feedback(
                tasks=related_tasks,
                task_runtime_repository=self._task_runtime_repository,
                evidence_ledger=self._evidence_ledger,
            ),
        )

    def _build_chat_writeback_lines(
        self,
        *,
        chat_writeback_summary: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(chat_writeback_summary, dict):
            return []
        lines: list[str] = []
        if chat_writeback_summary.get("strategy_updated"):
            lines.append("- The current operator correction has been written into formal strategy memory.")
        target_role_name = _first_non_empty(chat_writeback_summary.get("target_role_name"))
        if chat_writeback_summary.get("delegated") and target_role_name:
            lines.append(f"- This instruction has been delegated to: {target_role_name}.")
        created_goal_titles = _string_list(chat_writeback_summary.get("created_goal_titles"))
        for title in created_goal_titles[:3]:
            lines.append(f"- Newly recorded goal: {title}")
        created_schedule_titles = _string_list(
            chat_writeback_summary.get("created_schedule_titles"),
        )
        for title in created_schedule_titles[:3]:
            lines.append(f"- Newly recorded recurring loop: {title}")
        if chat_writeback_summary.get("deduplicated"):
            lines.append("- This instruction already exists in formal state; no duplicate record was created.")
        if chat_writeback_summary.get("dispatch_deferred"):
            requested_surfaces = _string_list(
                chat_writeback_summary.get("seat_requested_surfaces"),
            )
            gap_kind = _first_non_empty(
                chat_writeback_summary.get("seat_resolution_kind"),
                "routing-pending",
            )
            lines.append(
                "- No specialist has been assigned yet. The control core only recorded the work into formal backlog and is waiting for staffing/routing closure.",
            )
            if requested_surfaces:
                lines.append(
                    f"- Pending execution surfaces: {', '.join(requested_surfaces[:4])} ({gap_kind})",
                )
        return lines

    def _build_team_role_gap_lines(
        self,
        *,
        team_role_gap_summary: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(team_role_gap_summary, dict):
            return []
        role_name = _first_non_empty(team_role_gap_summary.get("suggested_role_name"))
        summary = _first_non_empty(team_role_gap_summary.get("summary"))
        status = _first_non_empty(team_role_gap_summary.get("status"))
        decision_request_id = _first_non_empty(
            team_role_gap_summary.get("decision_request_id"),
        )
        workflow_title = _first_non_empty(team_role_gap_summary.get("workflow_title"))
        if not any((role_name, summary, status, decision_request_id, workflow_title)):
            return []
        lines: list[str] = []
        if role_name:
            lines.append(f"- Active staffing gap: {role_name}")
        if workflow_title:
            lines.append(f"- Gap source workflow: {workflow_title}")
        if summary:
            lines.append(f"- Gap rationale: {summary}")
        if status:
            lines.append(f"- Governance status: {status}")
        if decision_request_id:
            lines.append(f"- Open decision id: {decision_request_id}")
        lines.append(
            '- If the operator agrees, tell them they can reply with "批准补位"; if not, "拒绝补位".',
        )
        return lines

    def _build_industry_kickoff_lines(
        self,
        *,
        industry_kickoff_summary: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(industry_kickoff_summary, dict):
            return []
        lines: list[str] = []
        started_goal_titles = _string_list(
            industry_kickoff_summary.get("started_goal_titles"),
        )
        resumed_schedule_titles = _string_list(
            industry_kickoff_summary.get("resumed_schedule_titles"),
        )
        if started_goal_titles:
            lines.append("- Initial execution has been confirmed from chat and the default goal chain is now live.")
            for title in started_goal_titles[:3]:
                lines.append(f"- Started default goal: {title}")
        if resumed_schedule_titles:
            for title in resumed_schedule_titles[:3]:
                lines.append(f"- Resumed recurring loop: {title}")
        return lines

    def _resolve_industry_goal_focus(
        self,
        *,
        industry_instance_id: str | None,
        owner_agent_id: str,
        industry_role_id: str | None,
        allow_execution_core_alias: bool,
    ) -> dict[str, Any] | None:
        if not industry_instance_id:
            return None
        instance = self._get_industry_instance(industry_instance_id)
        if instance is None:
            return None
        goals = _field_value(instance, "goals")
        if not isinstance(goals, list):
            return None
        raw_role_id = _first_non_empty(industry_role_id)
        normalized_role_id = (
            normalize_industry_role_id(raw_role_id)
            if allow_execution_core_alias
            else None
        )
        matches: list[dict[str, Any]] = []
        for goal in goals:
            if not isinstance(goal, dict):
                continue
            goal_owner_agent_id = _first_non_empty(goal.get("owner_agent_id"))
            goal_raw_role_id = _first_non_empty(
                goal.get("role_id"),
                goal.get("industry_role_id"),
            )
            goal_role_id = normalize_industry_role_id(goal_raw_role_id)
            if goal_owner_agent_id and goal_owner_agent_id == owner_agent_id:
                matches.append(goal)
                continue
            if (
                raw_role_id is not None
                and goal_raw_role_id is not None
                and goal_raw_role_id == raw_role_id
            ):
                matches.append(goal)
                continue
            if normalized_role_id and goal_role_id == normalized_role_id:
                matches.append(goal)
        if not matches:
            return None
        for status in ("active", "draft", "paused", "blocked"):
            for goal in matches:
                if _first_non_empty(goal.get("status")) == status:
                    return goal
        return matches[0]

    def _build_industry_brief_lines(
        self,
        *,
        industry_instance_id: str | None,
    ) -> list[str]:
        if not industry_instance_id or self._industry_service is None:
            return []
        instance = self._get_industry_instance(industry_instance_id)
        if instance is None:
            return []
        lines: list[str] = []
        label = _first_non_empty(_field_value(instance, "label"))
        summary = _first_non_empty(_field_value(instance, "summary"))
        profile = _mapping_value(_field_value(instance, "profile"))
        if not profile:
            profile = _mapping_value(_field_value(instance, "profile_payload"))
        if label:
            lines.append(f"- Team label: {label}")
        if summary:
            lines.append(f"- Team summary: {summary}")
        for title, value in (
            ("Industry", _first_non_empty(profile.get("industry"))),
            ("Company", _first_non_empty(profile.get("company_name"))),
            ("Sub-industry", _first_non_empty(profile.get("sub_industry"))),
            ("Product", _first_non_empty(profile.get("product"))),
            ("Business model", _first_non_empty(profile.get("business_model"))),
            ("Region", _first_non_empty(profile.get("region"))),
            ("Budget", _first_non_empty(profile.get("budget_summary"))),
            ("Notes", _first_non_empty(profile.get("notes"))),
        ):
            if value:
                lines.append(f"- {title}: {value}")
        for title, items in (
            ("Target customers", _string_list(profile.get("target_customers"))),
            ("Priority channels", _string_list(profile.get("channels"))),
            ("Operating goals", _string_list(profile.get("goals"))),
            ("Constraints", _string_list(profile.get("constraints"))),
        ):
            if items:
                lines.append(f"- {title}: {', '.join(items[:6])}")
        current_cycle = _mapping_value(_field_value(instance, "current_cycle"))
        synthesis = _mapping_value(current_cycle.get("synthesis")) if current_cycle else {}
        if synthesis:
            conflicts = list(synthesis.get("conflicts") or [])
            holes = list(synthesis.get("holes") or [])
            needs_replan = bool(synthesis.get("needs_replan"))
            lines.append(
                "- Control-core synthesis focus: compare reports, detect conflicts and holes, then own the final operator-facing conclusion before more delegation.",
            )
            lines.append(
                f"- Current synthesis status: conflicts={len(conflicts)}, holes={len(holes)}, needs_replan={'yes' if needs_replan else 'no'}",
            )
        staffing = _mapping_value(_field_value(instance, "staffing"))
        active_gap = _mapping_value(staffing.get("active_gap")) if staffing else {}
        if active_gap:
            gap_role = _first_non_empty(
                active_gap.get("target_role_name"),
                active_gap.get("role_name"),
            )
            gap_kind = _first_non_empty(active_gap.get("kind")) or "routing-pending"
            gap_label = gap_role or "unassigned lane"
            lines.append(f"- Active staffing/routing gap: {gap_label} ({gap_kind})")
        return lines

    def _build_team_roster_lines(
        self,
        *,
        industry_instance_id: str | None,
        owner_agent_id: str,
    ) -> list[str]:
        if not industry_instance_id:
            return []
        instance = self._get_industry_instance(industry_instance_id)
        if instance is None:
            return []
        agents = _field_value(instance, "agents")
        if not isinstance(agents, list):
            return []
        lines: list[str] = []
        for agent in agents:
            agent_id = _first_non_empty(
                _field_value(agent, "agent_id", "id"),
            )
            if not agent_id:
                continue
            role_id = _first_non_empty(
                _field_value(agent, "industry_role_id", "role_id"),
            )
            role_name = _first_non_empty(_field_value(agent, "role_name"))
            display_name = _first_non_empty(_field_value(agent, "name"))
            mission = _first_non_empty(_field_value(agent, "mission"))
            current_focus = _first_non_empty(
                _field_value(agent, "current_focus"),
                _field_value(agent, "current_goal"),
            )
            allowed_capabilities = _string_list(
                _field_value(agent, "allowed_capabilities", "capabilities"),
            )
            label = role_name or display_name or role_id or agent_id
            extra: list[str] = []
            if role_id and role_id.lower() != (role_name or role_id).lower():
                extra.append(role_id)
            if display_name and display_name != label:
                extra.append(display_name)
            suffix = f" ({', '.join(extra)})" if extra else ""
            marker = " (current)" if agent_id == owner_agent_id else ""
            line = f"- {agent_id}{marker}: {label}{suffix}"
            fields: list[str] = []
            if role_id:
                fields.append(f"role_id={role_id}")
            if role_name:
                fields.append(f"role_name={role_name}")
            if mission:
                fields.append(f"mission={mission}")
            if allowed_capabilities:
                preview = ", ".join(allowed_capabilities[:6])
                if len(allowed_capabilities) > 6:
                    preview = f"{preview}, ... (+{len(allowed_capabilities) - 6} more)"
                fields.append(f"allowed_capabilities={preview}")
            if current_focus:
                fields.append(f"current_focus={current_focus}")
            if fields:
                line = f"{line} | " + " | ".join(fields)
            lines.append(line)
        if not lines:
            return []
        if len(lines) > 12:
            lines = [*lines[:12], f"- ... (+{len(lines) - 12} more)"]
        return lines

    def _build_delegation_policy_lines(
        self,
        *,
        delegation_guard: _DelegationFirstGuard | None,
    ) -> list[str]:
        if delegation_guard is None or not delegation_guard.active:
            return []
        lines = [
            "- Delegation-first policy is active for this turn because specialist teammates are available.",
            "- Direct tools are disabled on the control core for this turn. Delegate one concrete subtask to a named specialist instead.",
            "- When using dispatch_query or delegate_task, include target_agent_id, target_role_id, or target_role_name explicitly; do not leave the target implicit.",
            "- Delegation stays available, but first compare reports, detect conflicts/holes, and own the operator-facing synthesis for this turn.",
            f"- Candidate teammates: {delegation_guard.teammate_summary()}",
        ]
        return lines

    def _build_execution_principle_lines(
        self,
        *,
        is_execution_core_runtime: bool,
    ) -> list[str]:
        lines = [
            "- If the exact procedure is unclear, first inspect retrieved knowledge, mounted skills, relevant SOPs, files/pages, or prior evidence until the next move is concrete.",
            "- Learn first, then act; do not freeze at uncertainty when the mounted environment already contains the needed procedure.",
            "- Learning never bypasses capability, approval, or user-owned verification boundaries; after inspection, state the exact missing surface if one still blocks execution.",
        ]
        if is_execution_core_runtime:
            lines.insert(
                0,
                "- As the control core, turn learned procedure into routing, assignment, and verification instructions instead of executing the leaf work yourself.",
            )
        else:
            lines.insert(
                0,
                "- After learning the procedure, continue inside your assigned role envelope and escalate cross-role changes back to the execution core.",
            )
        return lines

    def _resolve_prompt_capability_projection(
        self,
        *,
        owner_agent_id: str,
        capabilities: list[str],
    ) -> dict[str, Any] | None:
        service = self._agent_profile_service
        getter = getattr(service, "get_prompt_capability_projection", None)
        if callable(getter):
            try:
                projection = getter(owner_agent_id)
            except Exception:
                logger.exception("Failed to build prompt capability projection")
            else:
                resolved_projection = _mapping_value(projection)
                if resolved_projection:
                    return resolved_projection
        return self._build_prompt_capability_projection_from_mounts(
            owner_agent_id=owner_agent_id,
            capabilities=capabilities,
        )

    def _build_prompt_capability_projection_from_mounts(
        self,
        *,
        owner_agent_id: str,
        capabilities: list[str],
    ) -> dict[str, Any] | None:
        capability_ids = [
            capability_id
            for capability_id in capabilities
            if isinstance(capability_id, str) and capability_id.strip()
        ]
        if not capability_ids:
            return None
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
        getter = getattr(self._capability_service, "get_capability", None)
        for capability_id in capability_ids:
            mount = getter(capability_id) if callable(getter) else None
            source_kind = (
                str(getattr(mount, "source_kind", "") or "").strip().lower()
                or _infer_capability_source_kind(capability_id)
            )
            bucket_key = _prompt_capability_bucket(capability_id, source_kind=source_kind)
            bucket_counts[bucket_key] += 1
            risk_level = _first_non_empty(
                getattr(mount, "risk_level", None),
                "guarded",
            ) or "guarded"
            risk_levels[risk_level] = risk_levels.get(risk_level, 0) + 1
            if len(buckets[bucket_key]) < 4:
                buckets[bucket_key].append(
                    {
                        "id": capability_id,
                        "label": _prompt_capability_label(
                            capability_id,
                            name=(
                                _first_non_empty(
                                    getattr(mount, "name", None),
                                    capability_id,
                                )
                                or capability_id
                            ),
                        ),
                        "risk_level": risk_level,
                    },
                )
            for requirement in _string_list(
                getattr(mount, "environment_requirements", None),
            ):
                if requirement in seen_environment_requirements:
                    continue
                seen_environment_requirements.add(requirement)
                environment_requirements.append(requirement)
            for evidence_item in _string_list(
                getattr(mount, "evidence_contract", None),
            ):
                if evidence_item in seen_evidence_contract:
                    continue
                seen_evidence_contract.add(evidence_item)
                evidence_contract.append(evidence_item)
        return {
            "agent_id": owner_agent_id,
            "default_mode": "mounted-only",
            "effective_count": len(capability_ids),
            "pending_decision_count": 0,
            "drift_detected": False,
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

    def _build_capability_card_lines(
        self,
        *,
        capability_projection: dict[str, Any] | None,
    ) -> list[str]:
        if not capability_projection:
            return []
        lines: list[str] = []
        effective_count = capability_projection.get("effective_count")
        pending_decision_count = capability_projection.get("pending_decision_count")
        mode = _first_non_empty(capability_projection.get("default_mode")) or "governed"
        drift_detected = "yes" if capability_projection.get("drift_detected") else "no"
        summary_fields = [
            f"mode={mode}",
            f"effective={effective_count if isinstance(effective_count, int) else 0}",
            f"pending_governance={pending_decision_count if isinstance(pending_decision_count, int) else 0}",
            f"drift={drift_detected}",
        ]
        lines.append(f"- Capability summary: {'; '.join(summary_fields)}")
        bucket_counts = _mapping_value(capability_projection.get("bucket_counts"))
        for label, key in (
            ("Dispatch rights", "system_dispatch"),
            ("Governance rights", "system_governance"),
            ("Tool surfaces", "tools"),
            ("Skill surfaces", "skills"),
            ("MCP surfaces", "mcp"),
            ("Other surfaces", "other"),
        ):
            entries = capability_projection.get(key)
            if not isinstance(entries, list) or not entries:
                continue
            entry_count = bucket_counts.get(key)
            lines.append(
                f"- {label} ({entry_count if isinstance(entry_count, int) else len(entries)}): "
                + ", ".join(_prompt_capability_entry_label(entry) for entry in entries)
            )
        risk_levels = _mapping_value(capability_projection.get("risk_levels"))
        if risk_levels:
            risk_preview = ", ".join(
                f"{level}={count}"
                for level, count in sorted(risk_levels.items())
                if isinstance(level, str) and isinstance(count, int)
            )
            if risk_preview:
                lines.append(f"- Risk mix: {risk_preview}")
        environment_requirements = _string_list(
            capability_projection.get("environment_requirements"),
        )
        if environment_requirements:
            lines.append(
                f"- Environment dependencies: {', '.join(environment_requirements[:6])}",
            )
        evidence_contract = _string_list(capability_projection.get("evidence_contract"))
        if evidence_contract:
            lines.append(
                f"- Evidence outputs: {', '.join(evidence_contract[:6])}",
            )
        return lines

    def _get_industry_instance(self, industry_instance_id: str) -> Any | None:
        service = self._industry_service
        if service is None:
            return None
        for method_name in ("get_instance_detail", "get_instance_record"):
            getter = getattr(service, method_name, None)
            if not callable(getter):
                continue
            try:
                instance = getter(industry_instance_id)
            except Exception:
                logger.exception(
                    "Failed to load industry instance context for query prompt",
                )
                return None
            if instance is not None:
                return instance
        return None

    def _build_capability_guardrail_lines(
        self,
        capabilities: list[Any],
        *,
        desktop_actuation_available: bool = False,
    ) -> list[str]:
        capability_ids = {
            str(item).strip()
            for item in capabilities
            if str(item).strip()
        }
        if not capability_ids:
            return []
        lines: list[str] = []
        if "tool:browser_use" in capability_ids:
            lines.append(
                "- Browser actuation is available through the mounted browser capability.",
            )
        if desktop_actuation_available:
            lines.append(
                "- Desktop actuation is mounted in this session; use the available desktop/window tools for launch, focus, click, typing, and key input when needed.",
            )
        if "tool:browser_use" in capability_ids or desktop_actuation_available:
            lines.extend(
                [
                    "- Attempt mounted browser or desktop workflows before claiming the task is impossible or refusing on generic account-access grounds.",
                    "- Mounted browser/desktop actuation may be used for registration, login, dashboard operations, product listing, posting, messaging, upload, and other executable real-site workflows; do not refuse merely because the target is a real account or business backend.",
                    "- Ask for explicit confirmation only on irreversible, costly, publicly visible, or account/security-mutating actions such as publish/post to a public surface, publicly list a product, submit an order/payment, save account/security settings, change pricing, or bulk delete data.",
                    "- Routine login, navigation, draft editing, private replies, and ordinary uploads should continue without an extra confirmation unless the user or channel policy explicitly requires one.",
                    "- If login, CAPTCHA, SMS/2FA, device approval, payment confirmation, or another user-owned verification step appears, pause at that checkpoint, tell the user exactly what to finish, and resume from the current session after they confirm.",
                    "- Treat manual verification as a checkpoint to resume from, not as a blanket reason to abandon the rest of an otherwise executable workflow.",
                ],
            )
        if (
            "tool:desktop_screenshot" in capability_ids
            and not desktop_actuation_available
        ):
            lines.append(
                "- Desktop access is observation-only via screenshots; do not claim full mouse/keyboard control unless a dedicated desktop actuation capability is mounted.",
            )
        if "tool:execute_shell_command" not in capability_ids:
            lines.append(
                "- Shell/admin execution is not mounted in this session.",
            )
        if "system:dispatch_query" in capability_ids:
            lines.append(
                "- Focused sub-query dispatch is mounted; use it to hand work to a teammate from the team roster (agent_id/role_id/role_name) instead of only describing what should happen.",
            )
        if "system:delegate_task" in capability_ids:
            lines.append(
                "- Task delegation is mounted; use it to assign work to a specific teammate from the team roster and include their agent_id or role_id.",
            )
        if "system:apply_role" in capability_ids:
            lines.append(
                "- Governed role/capability assignment is mounted; use it to update a teammate's role or capability envelope through the kernel instead of leaving the change as a suggestion.",
            )
        if "system:discover_capabilities" in capability_ids:
            lines.append(
                "- Capability discovery is mounted; use it to search governed install-template and allowlisted remote capability candidates before inventing a new skill or leaving a capability gap unresolved.",
            )
        return lines

    def _build_retrieved_knowledge_lines(
        self,
        *,
        msgs: list[Any],
        owner_agent_id: str,
        industry_instance_id: str | None,
        industry_role_id: str | None,
        owner_scope: str | None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        session_kind: str | None = None,
    ) -> list[str]:
        service = self._knowledge_service
        recall_service = getattr(self, "_memory_recall_service", None)
        if service is None and recall_service is None:
            return []
        query = _message_query_text(msgs)
        if query is None:
            return []

        knowledge_retriever = getattr(service, "retrieve", None)
        memory_retriever = getattr(service, "retrieve_memory", None)
        recall = getattr(recall_service, "recall", None)
        resolved_work_context_id = _first_non_empty(work_context_id)
        if task_id and self._task_repository is not None:
            try:
                task_record = self._task_repository.get_task(task_id)
            except Exception:
                task_record = None
            if task_record is not None and resolved_work_context_id is None:
                resolved_work_context_id = _first_non_empty(
                    getattr(task_record, "work_context_id", None),
                )
        knowledge_chunks = (
            knowledge_retriever(query=query, role=industry_role_id, limit=4)
            if callable(knowledge_retriever)
            else []
        )
        if callable(recall):
            recall_response = recall(
                query=query,
                role=industry_role_id,
                scope_type=(
                    "work_context"
                    if resolved_work_context_id
                    else "task"
                    if task_id
                    else None
                ),
                scope_id=resolved_work_context_id or (
                    task_id if task_id else None
                ),
                task_id=task_id,
                work_context_id=resolved_work_context_id,
                agent_id=owner_agent_id,
                industry_instance_id=industry_instance_id,
                global_scope_id=owner_scope,
                include_related_scopes=not (resolved_work_context_id or task_id),
                limit=4,
            )
            memory_chunks = list(getattr(recall_response, "hits", []) or [])
        elif callable(memory_retriever):
            if resolved_work_context_id:
                memory_chunks = memory_retriever(
                    query=query,
                    role=industry_role_id,
                    scope_type="work_context",
                    scope_id=resolved_work_context_id,
                    task_id=task_id,
                    work_context_id=resolved_work_context_id,
                    include_related_scopes=False,
                    limit=4,
                )
            elif task_id:
                memory_chunks = memory_retriever(
                    query=query,
                    role=industry_role_id,
                    scope_type="task",
                    scope_id=task_id,
                    task_id=task_id,
                    work_context_id=work_context_id,
                    include_related_scopes=False,
                    limit=4,
                )
            else:
                memory_chunks = memory_retriever(
                    query=query,
                    role=industry_role_id,
                    task_id=task_id,
                    work_context_id=work_context_id,
                    agent_id=owner_agent_id,
                    industry_instance_id=industry_instance_id,
                    global_scope_id=owner_scope,
                    limit=3,
                )
        else:
            memory_chunks = []
        lines: list[str] = []
        if knowledge_chunks:
            lines.append("# Retrieved Knowledge")
            lines.extend(_knowledge_line(chunk) for chunk in knowledge_chunks[:4])
        derived_service = getattr(recall_service, "_derived_index_service", None)
        truth_first_entries = []
        if derived_service is not None and callable(getattr(derived_service, "list_fact_entries", None)):
            truth_first_entries = list(
                derived_service.list_fact_entries(
                    scope_type=(
                        "work_context"
                        if resolved_work_context_id
                        else "task"
                        if task_id
                        else None
                    ),
                    scope_id=resolved_work_context_id or (task_id if task_id else None),
                    owner_agent_id=owner_agent_id,
                    industry_instance_id=industry_instance_id,
                    limit=6,
                )
                or [],
            )
            truth_first_entries.sort(
                key=lambda item: (
                    getattr(item, "source_updated_at", None)
                    or getattr(item, "updated_at", None)
                    or getattr(item, "created_at", None)
                    or "",
                ),
                reverse=True,
            )
        if truth_first_entries:
            if lines:
                lines.append("")
            latest_entries = truth_first_entries[:1]
            history_entries = truth_first_entries[1:3]
            profile_entry = latest_entries[0] if latest_entries else None
            lines.append("# Truth-First Memory Profile")
            if profile_entry is not None:
                lines.append(
                    _knowledge_line(
                        MemoryRecallHit(
                            entry_id=f"profile:{getattr(profile_entry, 'scope_type', 'global')}:{getattr(profile_entry, 'scope_id', 'runtime')}",
                            kind="memory_profile",
                            title="Shared Memory Profile",
                            summary=_first_non_empty(
                                getattr(profile_entry, "summary", None),
                                getattr(profile_entry, "content_excerpt", None),
                                getattr(profile_entry, "title", None),
                            )
                            or "Shared truth-first profile.",
                            content_excerpt=_first_non_empty(
                                getattr(profile_entry, "content_excerpt", None),
                                getattr(profile_entry, "summary", None),
                            )
                            or "",
                            source_type="memory_profile",
                            source_ref=f"profile:{getattr(profile_entry, 'scope_type', 'global')}:{getattr(profile_entry, 'scope_id', 'runtime')}",
                            scope_type=str(getattr(profile_entry, "scope_type", "global") or "global"),
                            scope_id=str(getattr(profile_entry, "scope_id", "runtime") or "runtime"),
                            confidence=1.0,
                            quality_score=1.0,
                            score=1.0,
                            backend="truth-first",
                        ),
                    ),
                )
            else:
                lines.append("- Shared truth-first profile unavailable.")
            lines.append("")
            lines.append("# Truth-First Memory Latest Facts")
            lines.extend(_knowledge_line(chunk) for chunk in latest_entries[:2])
            if history_entries:
                lines.append("")
                lines.append("# Truth-First Memory History")
                lines.extend(_knowledge_line(chunk) for chunk in history_entries[:2])
        if memory_chunks:
            if lines:
                lines.append("")
            lines.append(
                "# Truth-First Lexical Recall"
                if truth_first_entries
                else "# Long-Term Memory"
            )
            lines.extend(_knowledge_line(chunk) for chunk in memory_chunks[:3])
        return lines



