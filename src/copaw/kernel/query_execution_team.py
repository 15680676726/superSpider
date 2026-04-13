# -*- coding: utf-8 -*-
from __future__ import annotations

from .main_brain_intake import (
    build_industry_chat_action_kwargs,
    read_attached_main_brain_intake_contract,
    resolve_execution_core_industry_instance_id,
)
from .decision_policy import decision_chat_route, decision_chat_thread_id
from .query_execution_shared import *  # noqa: F401,F403


_DELEGATION_FIRST_BLOCKED_TOOL_NAMES = frozenset(
    {
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "browser_use",
        "desktop_actuation",
    },
)


class _QueryExecutionTeamMixin:
    async def _handle_team_role_gap_chat_action(
        self,
        *,
        msgs: list[Any],
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
    ) -> Msg | None:
        action = _resolve_team_role_gap_action_request(
            text=_message_query_text(msgs),
            request=request,
        )
        if action is None:
            return None
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(agent_profile, "industry_instance_id", None)
            if agent_profile is not None
            else None,
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(agent_profile, "industry_role_id", None)
            if agent_profile is not None
            else None,
        )
        if not industry_instance_id:
            return None
        if not (
            is_execution_core_agent_id(owner_agent_id)
            or industry_role_id == EXECUTION_CORE_ROLE_ID
        ):
            return None
        recommendation = self._resolve_active_team_role_gap_recommendation(
            industry_instance_id=industry_instance_id,
        )
        if recommendation is None:
            return _team_role_gap_resolution_message(
                action=action,
                role_name=None,
                outcome_summary="当前没有待你批复的岗位补位建议。",
                decision_request_id=None,
            )
        role_name = _first_non_empty(recommendation.get("suggested_role_name"))
        case_id = _first_non_empty(recommendation.get("case_id"))
        recommendation_id = _first_non_empty(recommendation.get("recommendation_id"))
        decision_request_id = _first_non_empty(recommendation.get("decision_request_id"))
        prediction_service = self._prediction_service
        dispatcher = self._kernel_dispatcher
        actor = owner_agent_id or EXECUTION_CORE_AGENT_ID
        if action == "reject":
            rejecter = getattr(prediction_service, "reject_recommendation", None)
            resolution = f"操作方已在执行中枢聊天中拒绝补位“{role_name or '该岗位'}”。"
            if callable(rejecter) and case_id is not None and recommendation_id is not None:
                try:
                    result = rejecter(
                        case_id,
                        recommendation_id,
                        actor=actor,
                        summary=resolution,
                    )
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:
                    logger.exception(
                        "Failed to reject team-role-gap recommendation '%s' from chat",
                        recommendation_id,
                    )
                    return _team_role_gap_resolution_message(
                        action=action,
                        role_name=role_name,
                        outcome_summary=str(exc),
                        decision_request_id=decision_request_id,
                    )
            elif dispatcher is not None and decision_request_id is not None:
                try:
                    dispatcher.reject_decision(
                        decision_request_id,
                        resolution=resolution,
                    )
                except Exception as exc:
                    logger.exception(
                        "Failed to reject team-role-gap decision '%s' from chat",
                        decision_request_id,
                    )
                    return _team_role_gap_resolution_message(
                        action=action,
                        role_name=role_name,
                        outcome_summary=str(exc),
                        decision_request_id=decision_request_id,
                    )
            else:
                return _team_role_gap_resolution_message(
                    action=action,
                    role_name=role_name,
                    outcome_summary="当前补位建议缺少可拒绝的正式对象。",
                    decision_request_id=decision_request_id,
                )
            return _team_role_gap_resolution_message(
                action=action,
                role_name=role_name,
                outcome_summary=f"已拒绝补位“{role_name or '该岗位'}”，当前团队不会新增这个角色。",
                decision_request_id=decision_request_id,
            )

        if decision_request_id is None:
            executor = getattr(prediction_service, "execute_recommendation", None)
            if not callable(executor) or case_id is None or recommendation_id is None:
                return _team_role_gap_resolution_message(
                    action=action,
                    role_name=role_name,
                    outcome_summary="当前补位建议缺少可提交的正式执行入口。",
                    decision_request_id=None,
                )
            try:
                execution_result = executor(
                    case_id,
                    recommendation_id,
                    actor=actor,
                )
                if asyncio.iscoroutine(execution_result):
                    execution_result = await execution_result
            except Exception as exc:
                logger.exception(
                    "Failed to submit team-role-gap recommendation '%s' from chat",
                    recommendation_id,
                )
                return _team_role_gap_resolution_message(
                    action=action,
                    role_name=role_name,
                    outcome_summary=str(exc),
                    decision_request_id=None,
                )
            execution_payload = _mapping_value(
                _mapping_value(execution_result).get("execution"),
            )
            decision_payload = _mapping_value(
                _mapping_value(execution_result).get("decision"),
            )
            decision_request_id = _first_non_empty(
                execution_payload.get("decision_request_id"),
                decision_payload.get("id"),
            )
            phase = _first_non_empty(execution_payload.get("phase"))
            if decision_request_id is None and phase in {"completed", "executed"}:
                return _team_role_gap_resolution_message(
                    action=action,
                    role_name=role_name,
                    outcome_summary=_first_non_empty(
                        execution_payload.get("summary"),
                        "补位建议已执行。",
                    )
                    or "补位建议已执行。",
                    decision_request_id=None,
                )
            if decision_request_id is None:
                return _team_role_gap_resolution_message(
                    action=action,
                    role_name=role_name,
                    outcome_summary=_first_non_empty(
                        execution_payload.get("summary"),
                        "补位建议已提交，但没有生成可批准的决策单。",
                    )
                    or "补位建议已提交，但没有生成可批准的决策单。",
                    decision_request_id=None,
                )

        if dispatcher is None:
            return _team_role_gap_resolution_message(
                action=action,
                role_name=role_name,
                outcome_summary="内核调度器不可用，暂时无法在聊天里完成补位批准。",
                decision_request_id=decision_request_id,
            )
        try:
            approved = await dispatcher.approve_decision(
                decision_request_id,
                resolution=f"操作方已在执行中枢聊天中批准补位“{role_name or '该岗位'}”。",
                execute=True,
            )
        except Exception as exc:
            logger.exception(
                "Failed to approve team-role-gap decision '%s' from chat",
                decision_request_id,
            )
            return _team_role_gap_resolution_message(
                action=action,
                role_name=role_name,
                outcome_summary=str(exc),
                decision_request_id=decision_request_id,
            )
        approved_payload = _mapping_value(approved)
        return _team_role_gap_resolution_message(
            action=action,
            role_name=role_name,
            outcome_summary=_first_non_empty(
                approved_payload.get("summary"),
                "补位已批准并进入正式团队主链。",
            )
            or "补位已批准并进入正式团队主链。",
            decision_request_id=decision_request_id,
            task_id=_first_non_empty(approved_payload.get("task_id")),
        )

    def _build_team_role_gap_notice_message(
        self,
        *,
        msgs: list[Any],
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
    ) -> Msg | None:
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(agent_profile, "industry_instance_id", None)
            if agent_profile is not None
            else None,
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(agent_profile, "industry_role_id", None)
            if agent_profile is not None
            else None,
        )
        notice_requested = _should_surface_team_role_gap_notice(
            text=_message_query_text(msgs),
            request=request,
        )
        if not industry_instance_id or not notice_requested:
            return None
        if not (
            is_execution_core_agent_id(owner_agent_id)
            or industry_role_id == EXECUTION_CORE_ROLE_ID
        ):
            return None
        recommendation = self._resolve_active_team_role_gap_recommendation(
            industry_instance_id=industry_instance_id,
        )
        if recommendation is None:
            return None
        return _team_role_gap_notice_message(recommendation=recommendation)

    def _resolve_active_team_role_gap_summary(
        self,
        *,
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
    ) -> dict[str, Any] | None:
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(agent_profile, "industry_instance_id", None)
            if agent_profile is not None
            else None,
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(agent_profile, "industry_role_id", None)
            if agent_profile is not None
            else None,
        )
        if not industry_instance_id:
            return None
        if not (
            is_execution_core_agent_id(owner_agent_id)
            or industry_role_id == EXECUTION_CORE_ROLE_ID
        ):
            return None
        return self._resolve_active_team_role_gap_recommendation(
            industry_instance_id=industry_instance_id,
        )

    def _resolve_active_team_role_gap_recommendation(
        self,
        *,
        industry_instance_id: str,
    ) -> dict[str, Any] | None:
        service = self._prediction_service
        getter = getattr(service, "get_active_team_role_gap_recommendation", None)
        if not callable(getter):
            return None
        try:
            result = getter(industry_instance_id=industry_instance_id)
        except TypeError:
            result = getter(industry_instance_id)
        except Exception:
            logger.exception(
                "Failed to resolve active team-role-gap recommendation for '%s'",
                industry_instance_id,
            )
            return None
        if asyncio.iscoroutine(result):
            return None
        return _mapping_value(result) or None

    async def _apply_industry_chat_kickoff_intent(
        self,
        *,
        msgs: list[Any],
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
    ) -> dict[str, Any] | None:
        industry_instance_id = resolve_execution_core_industry_instance_id(
            request=request,
            owner_agent_id=owner_agent_id,
            agent_profile=agent_profile,
        )
        if industry_instance_id is None:
            return None
        _ = msgs
        intake_contract = read_attached_main_brain_intake_contract(request=request)
        if intake_contract is None or not intake_contract.should_kickoff:
            return None
        service = self._industry_service
        if service is None:
            return None
        kickoff = getattr(service, "kickoff_execution_from_chat", None)
        if not callable(kickoff):
            return None
        try:
            result = kickoff(
                **build_industry_chat_action_kwargs(
                    industry_instance_id=industry_instance_id,
                    message_text=intake_contract.message_text,
                    owner_agent_id=owner_agent_id,
                    request=request,
                ),
            )
            if asyncio.iscoroutine(result):
                result = await result
        except Exception:
            logger.exception(
                "Failed to kick off industry execution for '%s' from chat",
                industry_instance_id,
            )
            return None
        return result if isinstance(result, dict) else None

    def _list_delegation_first_teammates(
        self,
        *,
        industry_instance_id: str,
        owner_agent_id: str,
    ) -> list[dict[str, str | None]]:
        instance = self._get_industry_instance(industry_instance_id)
        if instance is None:
            return []
        agents = _field_value(instance, "agents")
        if not isinstance(agents, list):
            return []
        teammates: list[dict[str, str | None]] = []
        for agent in agents:
            agent_id = _first_non_empty(_field_value(agent, "agent_id", "id"))
            if agent_id is None or agent_id == owner_agent_id:
                continue
            role_id = _first_non_empty(
                _field_value(agent, "industry_role_id", "role_id"),
            )
            if role_id == EXECUTION_CORE_ROLE_ID:
                continue
            if not self._agent_supports_dispatch_query(
                agent_id=agent_id,
                agent_payload=agent,
            ):
                continue
            teammates.append(
                {
                    "agent_id": agent_id,
                    "role_id": role_id,
                    "role_name": _first_non_empty(_field_value(agent, "role_name")),
                    "mission": _first_non_empty(_field_value(agent, "mission")),
                },
            )
        return teammates

    def _agent_supports_dispatch_query(
        self,
        *,
        agent_id: str,
        agent_payload: Any,
    ) -> bool:
        allowed = _string_list(
            _field_value(agent_payload, "allowed_capabilities", "capabilities"),
        )
        if allowed:
            return "system:dispatch_query" in allowed

        service = self._capability_service
        lister = getattr(service, "list_accessible_capabilities", None)
        if callable(lister):
            try:
                mounts = lister(agent_id=agent_id, enabled_only=True)
            except Exception:
                logger.exception(
                    "Failed to resolve capability surface for teammate '%s'",
                    agent_id,
                )
            else:
                return any(
                    str(getattr(mount, "id", "")) == "system:dispatch_query"
                    for mount in mounts
                )
        return not allowed or "system:dispatch_query" in allowed

    def _build_tool_preflight(
        self,
        *,
        delegation_guard: _DelegationFirstGuard | None,
        msgs: list[Any] | None = None,
        request: Any | None = None,
        owner_agent_id: str | None = None,
        agent_profile: Any | None = None,
        kernel_task_id: str | None = None,
    ):
        user_confirmed_risky_execution = _is_explicit_risky_execution_confirmation(
            text=_message_query_text(msgs or []),
            request=request,
        )
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None) if request is not None else None,
            getattr(agent_profile, "industry_instance_id", None) if agent_profile is not None else None,
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None) if request is not None else None,
            getattr(agent_profile, "industry_role_id", None) if agent_profile is not None else None,
        )
        main_brain_control_runtime = bool(
            industry_instance_id
            and owner_agent_id is not None
            and (
                is_execution_core_agent_id(owner_agent_id)
                or is_execution_core_role_id(industry_role_id)
            )
        )
        confirmation_gate_cache: dict[tuple[str, str], dict[str, Any]] = {}

        def _preflight(
            tool_name: str,
            args: tuple[Any, ...] = (),
            kwargs: dict[str, Any] | None = None,
        ) -> ToolResponse | None:
            kwargs = kwargs or {}
            if (
                delegation_guard is not None
                and delegation_guard.locked
                and tool_name in _DELEGATION_FIRST_BLOCKED_TOOL_NAMES
            ):
                error = (
                    "Main-brain orchestration cannot execute local tools directly. "
                    "Dispatch to a specialist teammate first."
                    if main_brain_control_runtime
                    else "Delegation-first policy is active. "
                    "Dispatch to a teammate before running local tools directly."
                )
                return _json_tool_response(
                    {
                        "success": False,
                        "error_code": "delegation_direct_tool_blocked",
                        "error": error,
                        "blocked_tool": tool_name,
                        "teammates": delegation_guard.teammate_preview(),
                    },
                )
            if (
                tool_name == "browser_use"
            ):
                action = _normalize_browser_tool_action(args, kwargs)
                requires_confirmation, context_signature = _risky_tool_confirmation_state(
                    tool_name=tool_name,
                    action=action,
                    kwargs=kwargs,
                )
                if requires_confirmation:
                    if (
                        user_confirmed_risky_execution
                        and request is not None
                        and owner_agent_id is not None
                    ):
                        self._schedule_risky_tool_confirmation_chat_approval(
                            request=request,
                            owner_agent_id=owner_agent_id,
                            tool_name=tool_name,
                            action=action,
                            context_signature=context_signature,
                        )
                        return None
                    if not user_confirmed_risky_execution:
                        if (
                            request is not None
                            and owner_agent_id is not None
                            and self._is_risky_tool_confirmation_already_approved(
                                request=request,
                                msgs=msgs,
                                owner_agent_id=owner_agent_id,
                                tool_name=tool_name,
                                action=action,
                                context_signature=context_signature,
                            )
                        ):
                            return None
                        confirmation_gate: dict[str, Any] | None = None
                        if request is not None and owner_agent_id is not None:
                            cache_key = (tool_name, action, context_signature or "")
                            confirmation_gate = confirmation_gate_cache.get(cache_key)
                            if confirmation_gate is None:
                                confirmation_gate = self._lookup_existing_risky_tool_confirmation_gate(
                                    request=request,
                                    msgs=msgs,
                                    owner_agent_id=owner_agent_id,
                                    tool_name=tool_name,
                                    action=action,
                                    context_signature=context_signature,
                                )
                                if confirmation_gate is None:
                                    confirmation_gate = self._create_risky_tool_confirmation_gate(
                                        request=request,
                                        msgs=msgs or [],
                                        owner_agent_id=owner_agent_id,
                                        agent_profile=agent_profile,
                                        kernel_task_id=kernel_task_id,
                                        tool_name=tool_name,
                                        action=action,
                                        context_signature=context_signature,
                                    )
                                if confirmation_gate is not None:
                                    confirmation_gate_cache[cache_key] = confirmation_gate
                        payload = {
                            "success": False,
                            "error_code": "user_confirmation_required",
                            "error": (
                                "该浏览器步骤可能修改真实账号或触发外部动作。"
                                "请先请求用户明确确认，再继续当前会话。"
                            ),
                            "confirmation_required": True,
                            "tool": tool_name,
                            "action": action,
                            "resume_hint": (
                                "等待用户在主脑聊天里明确同意继续当前动作，"
                                "或在运行中心批准确认单后，再从当前会话继续推进。"
                            ),
                        }
                        if confirmation_gate:
                            payload.update(confirmation_gate)
                        return _json_tool_response(payload)
                    return None
            if (
                tool_name == "desktop_actuation"
            ):
                action = _normalize_desktop_tool_action(args, kwargs)
                requires_confirmation, context_signature = _risky_tool_confirmation_state(
                    tool_name=tool_name,
                    action=action,
                    kwargs=kwargs,
                )
                if requires_confirmation:
                    if (
                        user_confirmed_risky_execution
                        and request is not None
                        and owner_agent_id is not None
                    ):
                        self._schedule_risky_tool_confirmation_chat_approval(
                            request=request,
                            owner_agent_id=owner_agent_id,
                            tool_name=tool_name,
                            action=action,
                            context_signature=context_signature,
                        )
                        return None
                    if not user_confirmed_risky_execution:
                        if (
                            request is not None
                            and owner_agent_id is not None
                            and self._is_risky_tool_confirmation_already_approved(
                                request=request,
                                msgs=msgs,
                                owner_agent_id=owner_agent_id,
                                tool_name=tool_name,
                                action=action,
                                context_signature=context_signature,
                            )
                        ):
                            return None
                        confirmation_gate: dict[str, Any] | None = None
                        if request is not None and owner_agent_id is not None:
                            cache_key = (tool_name, action, context_signature or "")
                            confirmation_gate = confirmation_gate_cache.get(cache_key)
                            if confirmation_gate is None:
                                confirmation_gate = self._lookup_existing_risky_tool_confirmation_gate(
                                    request=request,
                                    msgs=msgs,
                                    owner_agent_id=owner_agent_id,
                                    tool_name=tool_name,
                                    action=action,
                                    context_signature=context_signature,
                                )
                                if confirmation_gate is None:
                                    confirmation_gate = self._create_risky_tool_confirmation_gate(
                                        request=request,
                                        msgs=msgs or [],
                                        owner_agent_id=owner_agent_id,
                                        agent_profile=agent_profile,
                                        kernel_task_id=kernel_task_id,
                                        tool_name=tool_name,
                                        action=action,
                                        context_signature=context_signature,
                                    )
                                if confirmation_gate is not None:
                                    confirmation_gate_cache[cache_key] = confirmation_gate
                        payload = {
                            "success": False,
                            "error_code": "user_confirmation_required",
                            "error": (
                                "This live desktop action may mutate a real application "
                                "or account. Ask for explicit confirmation first."
                            ),
                            "confirmation_required": True,
                            "tool": tool_name,
                            "action": action,
                            "resume_hint": (
                                "Wait for explicit user approval to continue the current action in "
                                "the main-brain chat, or approve the decision in Runtime Center."
                            ),
                        }
                        if confirmation_gate:
                            payload.update(confirmation_gate)
                        return _json_tool_response(payload)
                    return None
            return None

        return _preflight

    def _schedule_risky_tool_confirmation_chat_approval(
        self,
        *,
        request: Any,
        owner_agent_id: str,
        tool_name: str,
        action: str,
        context_signature: str | None = None,
    ) -> bool:
        dispatcher = self._kernel_dispatcher
        if dispatcher is None:
            return False
        match = self._find_risky_tool_confirmation_task(
            request=request,
            query_text=None,
            owner_agent_id=owner_agent_id,
            tool_name=tool_name,
            actions=_matching_risky_tool_actions(tool_name=tool_name, action=action),
            context_signature=context_signature,
            phases=("waiting-confirm",),
            match_query_text=False,
        )
        if match is None:
            return False
        decision_request_id = _first_non_empty(match.get("decision_request_id"))
        if decision_request_id is None:
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        resolution = (
            "操作方已在主脑聊天中明确同意继续当前高风险执行，"
            f"放行 {_risky_tool_surface_label(tool_name)} 动作“{_risky_tool_action_label(tool_name, action)}”。"
        )

        async def _approve() -> None:
            try:
                await dispatcher.approve_decision(
                    decision_request_id,
                    resolution=resolution,
                    execute=False,
                )
            except Exception:
                logger.exception(
                    "Failed to approve risky tool confirmation '%s' from main-brain chat",
                    decision_request_id,
                )

        loop.create_task(_approve())
        return True

    def _create_risky_tool_confirmation_gate(
        self,
        *,
        request: Any,
        msgs: list[Any],
        owner_agent_id: str,
        agent_profile: Any | None,
        kernel_task_id: str | None,
        tool_name: str,
        action: str,
        context_signature: str | None = None,
    ) -> dict[str, Any] | None:
        dispatcher = self._kernel_dispatcher
        if dispatcher is None:
            return None

        query_text = _message_query_text(msgs)
        query_preview = _first_non_empty(query_text)
        if query_preview and len(query_preview) > 120:
            query_preview = f"{query_preview[:117].rstrip()}..."

        session_id = (
            _first_non_empty(getattr(request, "session_id", None))
            or _first_non_empty(kernel_task_id)
            or owner_agent_id
        )
        channel = _first_non_empty(getattr(request, "channel", None), DEFAULT_CHANNEL) or DEFAULT_CHANNEL
        goal_focus_id = _first_non_empty(
            getattr(request, "goal_id", None),
            (
                getattr(agent_profile, "current_focus_id", None)
                if agent_profile is not None
                and getattr(agent_profile, "current_focus_kind", None) == "goal"
                else None
            ),
        )
        actor_owner_id = _first_non_empty(
            getattr(agent_profile, "actor_key", None) if agent_profile is not None else None,
            owner_agent_id,
        )
        surface_label = _risky_tool_surface_label(tool_name)
        workflow_label = _risky_tool_workflow_label(tool_name)
        action_label = _risky_tool_action_label(tool_name, action)
        decision_summary = (
            f"确认后继续执行{surface_label}动作“{action_label}”。"
            + (f" 当前请求：{query_preview}" if query_preview else "")
        )
        task = KernelTask(
            title=f"{surface_label}待确认：{action_label}",
            goal_id=goal_focus_id,
            parent_task_id=_first_non_empty(kernel_task_id),
            capability_ref=None,
            environment_ref=f"session:{channel}:{session_id}",
            owner_agent_id=owner_agent_id,
            actor_owner_id=actor_owner_id,
            risk_level="confirm",
            payload={
                "decision_type": "query-tool-confirmation",
                "decision_summary": decision_summary,
                "auto_complete_on_approval": True,
                "approval_completion_summary": f"{surface_label}确认“{action_label}”已批准。",
                "tool_name": tool_name,
                "tool_action": action,
                "tool_context_signature": context_signature,
                "query_text": query_text,
                "request_context": _query_confirmation_request_context(request),
                "resume_hint": (
                    f"用户批准后，在当前交互会话继续执行这个{workflow_label}，"
                    "不要重新从头拒绝或改写目标。"
                ),
            },
        )
        try:
            admitted = dispatcher.submit(task)
        except Exception:
            logger.exception(
                "Failed to create confirmation gate for risky tool action '%s/%s'",
                tool_name,
                action,
            )
            return None

        decision_request_id = _first_non_empty(getattr(admitted, "decision_request_id", None))
        task_id = _first_non_empty(getattr(admitted, "task_id", None), task.id)
        if decision_request_id is None or task_id is None:
            return None
        chat_thread_id = decision_chat_thread_id(task.payload)
        chat_route = decision_chat_route(chat_thread_id)

        if kernel_task_id is not None:
            self._record_query_checkpoint(
                agent_id=owner_agent_id,
                task_id=kernel_task_id,
                session_id=session_id,
                user_id=_first_non_empty(getattr(request, "user_id", None)) or owner_agent_id,
                conversation_thread_id=_first_non_empty(getattr(request, "session_id", None)),
                channel=channel,
                phase="waiting-confirm",
                checkpoint_kind="governance",
                status="blocked",
                summary=f"{surface_label}动作“{action_label}”已进入人工确认流",
                snapshot_payload={
                    "confirmation_gate": {
                        "tool_name": tool_name,
                        "tool_action": action,
                        "decision_request_id": decision_request_id,
                        "task_id": task_id,
                        "chat_thread_id": chat_thread_id,
                        "chat_route": chat_route,
                    },
                },
            )

        return {
            "decision_request_id": decision_request_id,
            "decision_status": "open",
            "decision_summary": decision_summary,
            "decision_route": _runtime_decision_route(decision_request_id),
            "chat_thread_id": chat_thread_id,
            "chat_route": chat_route,
            "preferred_route": chat_route or _runtime_decision_route(decision_request_id),
            "task_id": task_id,
            "task_route": _runtime_task_route(task_id),
            "actions": _runtime_decision_actions(decision_request_id),
        }

    def _is_risky_tool_confirmation_already_approved(
        self,
        *,
        request: Any,
        msgs: list[Any] | None,
        owner_agent_id: str,
        tool_name: str,
        action: str,
        context_signature: str | None = None,
    ) -> bool:
        match = self._find_risky_tool_confirmation_task(
            request=request,
            query_text=_message_query_text(msgs),
            owner_agent_id=owner_agent_id,
            tool_name=tool_name,
            actions=_matching_risky_tool_actions(tool_name=tool_name, action=action),
            context_signature=context_signature,
            phases=("completed", "executing"),
        )
        if match is None:
            return False
        decision_status = _first_non_empty(match.get("decision_status"))
        if decision_status == "approved":
            return True
        return _first_non_empty(match.get("phase")) == "completed"

    def _lookup_existing_risky_tool_confirmation_gate(
        self,
        *,
        request: Any,
        msgs: list[Any] | None,
        owner_agent_id: str,
        tool_name: str,
        action: str,
        context_signature: str | None = None,
    ) -> dict[str, Any] | None:
        match = self._find_risky_tool_confirmation_task(
            request=request,
            query_text=_message_query_text(msgs),
            owner_agent_id=owner_agent_id,
            tool_name=tool_name,
            actions=_matching_risky_tool_actions(tool_name=tool_name, action=action),
            context_signature=context_signature,
            phases=("waiting-confirm", "executing", "completed"),
        )
        if match is None:
            return None
        if _first_non_empty(match.get("decision_status")) == "approved":
            return None
        task_id = _first_non_empty(match.get("task_id"))
        decision_request_id = _first_non_empty(match.get("decision_request_id"))
        if task_id is None or decision_request_id is None:
            return None
        decision_summary = _first_non_empty(match.get("decision_summary"))
        decision_status = _first_non_empty(match.get("decision_status"), "open") or "open"
        return {
            "decision_request_id": decision_request_id,
            "decision_status": decision_status,
            "decision_summary": decision_summary,
            "decision_route": _runtime_decision_route(decision_request_id),
            "task_id": task_id,
            "task_route": _runtime_task_route(task_id),
            "actions": _runtime_decision_actions(
                decision_request_id,
                status=decision_status,
            ),
        }

    def _load_query_tool_confirmation_context(
        self,
        *,
        decision_request_id: str,
    ) -> dict[str, Any] | None:
        dispatcher = self._kernel_dispatcher
        task_store = getattr(dispatcher, "task_store", None) if dispatcher is not None else None
        if task_store is None:
            return None
        decision = task_store.get_decision_request(decision_request_id)
        if decision is None or getattr(decision, "status", None) != "approved":
            return None
        task = (
            dispatcher.lifecycle.get_task(decision.task_id)
            if dispatcher is not None and getattr(dispatcher, "lifecycle", None) is not None
            else None
        )
        if task is None:
            task = task_store.get(decision.task_id)
        if task is None:
            return None
        payload = _query_task_payload_mapping(task)
        if payload.get("decision_type") != "query-tool-confirmation":
            return None
        request_context = payload.get("request_context")
        if not isinstance(request_context, dict):
            return None
        owner_agent_id = _first_non_empty(
            getattr(task, "owner_agent_id", None),
            request_context.get("agent_id"),
            request_context.get("user_id"),
        )
        if owner_agent_id is None:
            return None
        return {
            "decision": decision,
            "task": task,
            "owner_agent_id": owner_agent_id,
            "tool_name": _first_non_empty(payload.get("tool_name")),
            "tool_action": _first_non_empty(payload.get("tool_action")),
            "query_text": _first_non_empty(payload.get("query_text")),
            "request_context": dict(request_context),
        }

    def _find_risky_tool_confirmation_task(
        self,
        *,
        request: Any,
        query_text: str | None,
        owner_agent_id: str,
        tool_name: str,
        actions: tuple[str, ...],
        phases: tuple[str, ...],
        context_signature: str | None = None,
        match_query_text: bool = True,
    ) -> dict[str, Any] | None:
        dispatcher = self._kernel_dispatcher
        task_store = getattr(dispatcher, "task_store", None) if dispatcher is not None else None
        if task_store is None:
            return None
        request_context = _query_confirmation_request_context(request)
        session_id = _first_non_empty(request_context.get("session_id"))
        channel = _first_non_empty(request_context.get("channel"))
        if session_id is None or channel is None:
            return None
        for phase in phases:
            tasks = task_store.list_tasks(
                phase=phase,
                owner_agent_id=owner_agent_id,
                limit=80,
            )
            for task in tasks:
                payload = task.payload if isinstance(task.payload, dict) else {}
                if payload.get("decision_type") != "query-tool-confirmation":
                    continue
                if _first_non_empty(payload.get("tool_name")) != tool_name:
                    continue
                if _first_non_empty(payload.get("tool_action")) not in actions:
                    continue
                if context_signature is not None and (
                    _first_non_empty(payload.get("tool_context_signature")) != context_signature
                ):
                    continue
                task_request_context = payload.get("request_context")
                if not isinstance(task_request_context, dict):
                    continue
                if _first_non_empty(task_request_context.get("session_id")) != session_id:
                    continue
                if _first_non_empty(task_request_context.get("channel")) != channel:
                    continue
                if match_query_text and query_text is not None:
                    task_query_text = _first_non_empty(payload.get("query_text"))
                    if (task_query_text or "").strip() != query_text.strip():
                        continue
                decisions = task_store.list_decision_requests(task_id=task.id, limit=5)
                decision = decisions[0] if decisions else None
                decision_status = _first_non_empty(
                    getattr(decision, "status", None),
                    "approved" if phase == "completed" else None,
                )
                return {
                    "task_id": task.id,
                    "phase": task.phase,
                    "decision_request_id": _first_non_empty(getattr(decision, "id", None)),
                    "decision_status": decision_status,
                    "decision_summary": _first_non_empty(
                        getattr(decision, "summary", None),
                        payload.get("decision_summary"),
                    ),
                }
        return None
