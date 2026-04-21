# -*- coding: utf-8 -*-
from __future__ import annotations

from .query_execution_shared import *  # noqa: F401,F403


class _QueryExecutionToolsMixin:
    def _build_system_tool_functions(
        self,
        *,
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
        system_capability_ids: set[str] | None,
        kernel_task_id: str | None = None,
        delegation_guard: _DelegationFirstGuard | None = None,
    ) -> list[Any]:
        source_collection_service = getattr(self, "_source_collection_frontdoor", None)
        source_collection_runner = getattr(
            source_collection_service,
            "run_source_collection_frontdoor",
            None,
        )
        collect_sources_available = callable(source_collection_runner) and bool(
            {
                capability_id
                for capability_id in (system_capability_ids or set())
                if capability_id in {"system:dispatch_query", "system:delegate_task"}
            },
        )
        supported = {
            capability_id
            for capability_id in (system_capability_ids or set())
            if capability_id in {
                "system:apply_role",
                "system:discover_capabilities",
                "system:dispatch_query",
                "system:delegate_task",
            }
        }
        if not supported and not collect_sources_available:
            return []

        current_industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(agent_profile, "industry_instance_id", None) if agent_profile is not None else None,
        )
        current_industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(agent_profile, "industry_role_id", None) if agent_profile is not None else None,
        )
        current_industry_label = _first_non_empty(getattr(request, "industry_label", None))
        current_owner_scope = _first_non_empty(getattr(request, "owner_scope", None))
        current_session_id = _first_non_empty(getattr(request, "session_id", None))
        current_channel = _first_non_empty(getattr(request, "channel", None), DEFAULT_CHANNEL) or DEFAULT_CHANNEL
        current_entry_source = _first_non_empty(getattr(request, "entry_source", None)) or "agent-workbench"
        current_parent_task_id = _first_non_empty(kernel_task_id)
        current_environment_ref = (
            f"session:{current_channel}:{current_session_id}"
            if current_session_id is not None
            else None
        )
        execution_core_owner = (
            is_execution_core_agent_id(owner_agent_id)
            or current_industry_role_id == EXECUTION_CORE_ROLE_ID
        )
        assignment_leaf_owner = (
            not execution_core_owner
            and _first_non_empty(getattr(request, "assignment_id", None)) is not None
        )
        if assignment_leaf_owner:
            supported.difference_update(
                {"system:dispatch_query", "system:delegate_task"},
            )
            if not supported and not collect_sources_available:
                return []

        tools: list[Any] = []

        def _resolve_teammate(
            *,
            candidate_agent_id: str | None,
            target_role_id: str | None,
            target_role_name: str | None,
        ):
            return resolve_teammate_target(
                candidate_agent_id=candidate_agent_id,
                target_role_id=target_role_id,
                target_role_name=target_role_name,
                industry_instance_id=current_industry_instance_id,
                industry_service=self._industry_service,
                agent_profile_service=self._agent_profile_service,
            )

        def _record_guard_checkpoint(summary: str, snapshot_payload: dict[str, Any]) -> None:
            if kernel_task_id is None:
                return
            self._record_query_checkpoint(
                agent_id=owner_agent_id,
                task_id=kernel_task_id,
                session_id=_first_non_empty(getattr(request, "session_id", None)) or owner_agent_id,
                user_id=_first_non_empty(getattr(request, "user_id", None)) or owner_agent_id,
                conversation_thread_id=_first_non_empty(getattr(request, "session_id", None)),
                channel=current_channel,
                phase="delegation-policy",
                checkpoint_kind="worker-step",
                status="ready",
                summary=summary,
                snapshot_payload=snapshot_payload,
            )

        def _guard_target_required_response(action: str) -> ToolResponse:
            if execution_core_owner:
                error = (
                    "Main-brain orchestration requires an explicit teammate target. "
                    f"Use {action} with target_agent_id, target_role_id, or target_role_name."
                )
            else:
                error = (
                    "Delegation-first policy is active. "
                    f"Use {action} with target_agent_id, target_role_id, or target_role_name."
                )
            return _json_tool_response(
                {
                    "success": False,
                    "error_code": "delegation_target_required",
                    "error": error,
                    "teammates": delegation_guard.teammate_preview() if delegation_guard is not None else [],
                },
            )

        def _guard_self_target_response(action: str) -> ToolResponse:
            if execution_core_owner:
                error = (
                    "Main-brain orchestration cannot target the control core itself. "
                    f"{action} must point to a specialist teammate."
                )
            else:
                error = (
                    "Delegation-first policy is active. "
                    f"{action} must target a teammate before the execution core works directly."
                )
            return _json_tool_response(
                {
                    "success": False,
                    "error_code": "delegation_self_target_blocked",
                    "error": error,
                    "teammates": delegation_guard.teammate_preview() if delegation_guard is not None else [],
                },
            )

        def _mark_guard_delegation(
            *,
            capability_id: str,
            resolved_agent_id: str,
            resolution: Any,
        ) -> None:
            if delegation_guard is None or resolved_agent_id == owner_agent_id:
                return
            delegation_guard.mark_delegation(
                target_agent_id=resolved_agent_id,
                target_role_id=_first_non_empty(getattr(resolution, "role_id", None)),
                target_role_name=_first_non_empty(getattr(resolution, "role_name", None)),
                capability_id=capability_id,
            )
            _record_guard_checkpoint(
                f"Delegation-first policy satisfied via {capability_id} -> {resolved_agent_id}",
                {
                    "policy": "delegation-first",
                    "mode": "delegated",
                    "capability_id": capability_id,
                    "target_agent_id": resolved_agent_id,
                    "target_role_id": _first_non_empty(getattr(resolution, "role_id", None)),
                    "target_role_name": _first_non_empty(getattr(resolution, "role_name", None)),
                },
            )

        if collect_sources_available:
            async def collect_sources(
                question: str,
                requested_sources: list[str] | None = None,
                goal: str | None = None,
                why_needed: str | None = None,
                done_when: str | None = None,
                collection_mode_hint: str = "auto",
                title: str | None = None,
            ) -> ToolResponse:
                """Collect sources through the unified source-collection front door."""
                _ = title
                normalized_question = str(question or "").strip()
                if not normalized_question:
                    return _json_tool_response(
                        {"success": False, "error": "question is required"},
                    )
                normalized_goal = str(goal or normalized_question).strip()
                normalized_sources = [
                    str(item).strip()
                    for item in list(requested_sources or [])
                    if str(item).strip()
                ]
                work_context_id = _first_non_empty(getattr(request, "work_context_id", None))
                assignment_id = _first_non_empty(getattr(request, "assignment_id", None))
                writeback_target: dict[str, Any] | None = None
                if work_context_id is not None:
                    writeback_target = {
                        "scope_type": "work_context",
                        "scope_id": work_context_id,
                    }
                elif assignment_id is not None:
                    writeback_target = {
                        "scope_type": "assignment",
                        "scope_id": assignment_id,
                    }
                elif current_industry_instance_id is not None:
                    writeback_target = {
                        "scope_type": "industry",
                        "scope_id": current_industry_instance_id,
                    }
                researcher_resolution = _resolve_teammate(
                    candidate_agent_id=None,
                    target_role_id="researcher",
                    target_role_name=None,
                )
                preferred_researcher_agent_id = _first_non_empty(
                    getattr(researcher_resolution, "agent_id", None),
                )
                if preferred_researcher_agent_id is None and current_industry_instance_id is not None:
                    detail_getter = getattr(self._industry_service, "get_instance_detail", None)
                    if callable(detail_getter):
                        try:
                            detail = detail_getter(current_industry_instance_id)
                        except Exception:
                            detail = None
                        staffing = _mapping_value(_mapping_value(detail).get("staffing"))
                        researcher = _mapping_value(staffing.get("researcher"))
                        preferred_researcher_agent_id = _first_non_empty(
                            researcher.get("agent_id"),
                        )
                result = source_collection_runner(
                    goal=normalized_goal,
                    question=normalized_question,
                    why_needed=_first_non_empty(why_needed),
                    done_when=_first_non_empty(done_when),
                    trigger_source="agent-entry",
                    owner_agent_id=owner_agent_id,
                    preferred_researcher_agent_id=preferred_researcher_agent_id,
                    industry_instance_id=current_industry_instance_id,
                    work_context_id=work_context_id,
                    assignment_id=assignment_id,
                    task_id=current_parent_task_id,
                    supervisor_agent_id=owner_agent_id,
                    collection_mode_hint=(
                        _first_non_empty(collection_mode_hint, "auto") or "auto"
                    ),
                    requested_sources=normalized_sources,
                    writeback_target=writeback_target,
                    metadata={
                        "entry_surface": "query-execution-tools",
                        "entry_source": current_entry_source,
                        "request_channel": current_channel,
                    },
                )
                if asyncio.iscoroutine(result):
                    result = await result
                model_dump = getattr(result, "model_dump", None)
                payload = (
                    model_dump(mode="json")
                    if callable(model_dump)
                    else dict(result)
                    if isinstance(result, dict)
                    else {}
                )
                if not payload:
                    payload = {
                        "session_id": _first_non_empty(getattr(result, "session_id", None)),
                        "status": _first_non_empty(getattr(result, "status", None)),
                        "route_mode": _first_non_empty(getattr(result, "route_mode", None)),
                        "execution_agent_id": _first_non_empty(
                            getattr(result, "execution_agent_id", None),
                        ),
                        "findings": list(getattr(result, "findings", []) or []),
                        "collected_sources": list(
                            getattr(result, "collected_sources", []) or [],
                        ),
                        "conflicts": list(getattr(result, "conflicts", []) or []),
                        "gaps": list(getattr(result, "gaps", []) or []),
                    }
                return _json_tool_response(
                    {
                        "success": True,
                        "session_id": payload.get("session_id"),
                        "status": payload.get("status"),
                        "route_mode": payload.get("route_mode"),
                        "execution_agent_id": payload.get("execution_agent_id"),
                        "findings": list(payload.get("findings") or []),
                        "collected_sources": list(payload.get("collected_sources") or []),
                        "conflicts": list(payload.get("conflicts") or []),
                        "gaps": list(payload.get("gaps") or []),
                    },
                )

            tools.append(collect_sources)

        if "system:dispatch_query" in supported:
            async def dispatch_query(
                prompt_text: str,
                target_agent_id: str | None = None,
                target_role_id: str | None = None,
                target_role_name: str | None = None,
                title: str | None = None,
            ) -> ToolResponse:
                """Dispatch a focused sub-query to the current or a target agent through the kernel."""
                normalized_prompt = str(prompt_text or "").strip()
                if not normalized_prompt:
                    return _json_tool_response(
                        {"success": False, "error": "prompt_text is required"},
                    )
                target_specified = any(
                    _normalize_agent_candidate(value)
                    for value in (target_agent_id, target_role_id, target_role_name)
                )
                if execution_core_owner and not target_specified:
                    return _guard_target_required_response("dispatch_query")
                if delegation_guard is not None and delegation_guard.locked and not target_specified:
                    return _guard_target_required_response("dispatch_query")
                resolution = _resolve_teammate(
                    candidate_agent_id=_normalize_agent_candidate(target_agent_id),
                    target_role_id=_normalize_agent_candidate(target_role_id),
                    target_role_name=_normalize_agent_candidate(target_role_name),
                )
                if target_specified and resolution.error_code:
                    return _json_tool_response(
                        {
                            "success": False,
                            "error": resolution.error or "Target teammate not found",
                            "error_code": resolution.error_code,
                        },
                    )
                resolved_agent_id = resolution.agent_id or owner_agent_id
                if execution_core_owner and resolved_agent_id == owner_agent_id:
                    return _guard_self_target_response("dispatch_query")
                if delegation_guard is not None and delegation_guard.locked and resolved_agent_id == owner_agent_id:
                    return _guard_self_target_response("dispatch_query")
                target_profile = self._get_agent_profile(resolved_agent_id)
                target_industry_instance_id = _first_non_empty(
                    getattr(target_profile, "industry_instance_id", None) if target_profile is not None else None,
                    current_industry_instance_id,
                )
                target_industry_role_id = _first_non_empty(
                    getattr(target_profile, "industry_role_id", None) if target_profile is not None else None,
                    resolution.role_id if resolution else None,
                    current_industry_role_id,
                )
                target_industry_label = current_industry_label
                if target_industry_instance_id and target_industry_instance_id != current_industry_instance_id:
                    target_instance = self._get_industry_instance(target_industry_instance_id)
                    target_industry_label = _first_non_empty(
                        _field_value(target_instance, "label"),
                        current_industry_label,
                    )
                request_payload = {
                    "input": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": normalized_prompt,
                                }
                            ],
                        }
                    ],
                    "channel": current_channel,
                    "user_id": resolved_agent_id,
                    "session_id": f"dispatch:{getattr(request, 'session_id', owner_agent_id)}:{resolved_agent_id}",
                    "agent_id": resolved_agent_id,
                    "entry_source": current_entry_source,
                    "owner_scope": current_owner_scope,
                    "industry_instance_id": target_industry_instance_id,
                    "industry_role_id": target_industry_role_id,
                    "industry_label": target_industry_label,
                    "session_kind": (
                        "industry-agent-chat"
                        if target_industry_instance_id and target_industry_role_id
                        else "agent-chat"
                    ),
                }
                payload = {
                    "dispatch_request": request_payload,
                    "request": request_payload,
                    "mode": "final",
                    "dispatch_events": False,
                }
                result = _structured_tool_payload(
                    await self._execute_bound_system_capability(
                        capability_id="system:dispatch_query",
                        owner_agent_id=owner_agent_id,
                        payload=payload,
                        title=title or f"Dispatch query to {resolved_agent_id}",
                        parent_task_id=current_parent_task_id,
                        environment_ref=current_environment_ref,
                    ),
                    default_error=(
                        "dispatch_query returned an unexpected result payload"
                    ),
                )
                if result.get("success") is True:
                    _mark_guard_delegation(
                        capability_id="system:dispatch_query",
                        resolved_agent_id=resolved_agent_id,
                        resolution=resolution,
                    )
                return _json_tool_response(result)

            tools.append(dispatch_query)

        if "system:delegate_task" in supported:
            async def delegate_task(
                prompt_text: str,
                target_agent_id: str | None = None,
                target_role_id: str | None = None,
                target_role_name: str | None = None,
                title: str | None = None,
                parent_task_id: str | None = None,
                execute: bool = False,
            ) -> ToolResponse:
                """Delegate a focused task through the legacy local delegation compatibility path."""
                normalized_prompt = str(prompt_text or "").strip()
                if not normalized_prompt:
                    return _json_tool_response(
                        {"success": False, "error": "prompt_text is required"},
                    )
                # The live interactive query task is the authoritative delegation parent.
                # Model-supplied parent ids may reflect stale recovery/runtime context and
                # must not override the current frontdoor chain.
                resolved_parent_task_id = _first_non_empty(
                    current_parent_task_id,
                    parent_task_id,
                )
                if not resolved_parent_task_id:
                    return _json_tool_response(
                        {
                            "success": False,
                            "error": "parent_task_id is required",
                        },
                    )
                target_specified = any(
                    _normalize_agent_candidate(value)
                    for value in (target_agent_id, target_role_id, target_role_name)
                )
                if execution_core_owner and not target_specified:
                    return _guard_target_required_response("delegate_task")
                if delegation_guard is not None and delegation_guard.locked and not target_specified:
                    return _guard_target_required_response("delegate_task")
                resolution = _resolve_teammate(
                    candidate_agent_id=_normalize_agent_candidate(target_agent_id),
                    target_role_id=_normalize_agent_candidate(target_role_id),
                    target_role_name=_normalize_agent_candidate(target_role_name),
                )
                if target_specified and resolution.error_code:
                    return _json_tool_response(
                        {
                            "success": False,
                            "error": resolution.error or "Target teammate not found",
                            "error_code": resolution.error_code,
                        },
                    )
                resolved_agent_id = resolution.agent_id or owner_agent_id
                if execution_core_owner and resolved_agent_id == owner_agent_id:
                    return _guard_self_target_response("delegate_task")
                if delegation_guard is not None and delegation_guard.locked and resolved_agent_id == owner_agent_id:
                    return _guard_self_target_response("delegate_task")
                if self._capability_service is not None:
                    mounts = self._capability_service.list_accessible_capabilities(
                        agent_id=resolved_agent_id,
                        enabled_only=True,
                    )
                    if not any(str(mount.id) == "system:dispatch_query" for mount in mounts):
                        return _json_tool_response(
                            {
                                "success": False,
                                "error": (
                                    f"Target agent '{resolved_agent_id}' is not authorized for dispatch_query."
                                ),
                                "error_code": "target_not_authorized",
                            },
                        )
                target_profile = self._get_agent_profile(resolved_agent_id)
                target_industry_instance_id = _first_non_empty(
                    getattr(target_profile, "industry_instance_id", None) if target_profile is not None else None,
                    current_industry_instance_id,
                )
                target_industry_role_id = _first_non_empty(
                    getattr(target_profile, "industry_role_id", None) if target_profile is not None else None,
                    resolution.role_id if resolution else None,
                    current_industry_role_id,
                )
                target_industry_label = current_industry_label
                if target_industry_instance_id and target_industry_instance_id != current_industry_instance_id:
                    target_instance = self._get_industry_instance(target_industry_instance_id)
                    target_industry_label = _first_non_empty(
                        _field_value(target_instance, "label"),
                        current_industry_label,
                    )
                payload = {
                    "parent_task_id": resolved_parent_task_id,
                    "owner_agent_id": resolved_agent_id,
                    "target_agent_id": resolved_agent_id,
                    "target_role_id": resolution.role_id if resolution else None,
                    "target_role_name": resolution.role_name if resolution else None,
                    "title": title or f"Delegated task for {resolved_agent_id}",
                    "prompt_text": normalized_prompt,
                    "execute": bool(execute),
                    "channel": current_channel,
                    "industry_instance_id": target_industry_instance_id,
                    "industry_role_id": target_industry_role_id,
                    "industry_label": target_industry_label,
                    "owner_scope": current_owner_scope,
                    "inherit_environment_ref": False,
                    "session_kind": (
                        "industry-agent-chat"
                        if target_industry_instance_id and target_industry_role_id
                        else "agent-chat"
                    ),
                }
                result = _structured_tool_payload(
                    await self._execute_bound_system_capability(
                        capability_id="system:delegate_task",
                        owner_agent_id=owner_agent_id,
                        payload=payload,
                        title=title or f"Delegate task to {resolved_agent_id}",
                        parent_task_id=current_parent_task_id,
                        environment_ref=current_environment_ref,
                    ),
                    default_error=(
                        "delegate_task returned an unexpected result payload"
                    ),
                )
                _enrich_delegate_task_payload(
                    result=result,
                    resolved_agent_id=resolved_agent_id,
                )
                if result.get("success") is True:
                    _mark_guard_delegation(
                        capability_id="system:delegate_task",
                        resolved_agent_id=resolved_agent_id,
                        resolution=resolution,
                    )
                return _json_tool_response(result)

            tools.append(delegate_task)

        if "system:apply_role" in supported:
            async def apply_role(
                target_agent_id: str | None = None,
                target_role_id: str | None = None,
                target_role_name: str | None = None,
                role_text: str | None = None,
                role_name: str | None = None,
                role_summary: str | None = None,
                capabilities: list[str] | None = None,
                capability_assignment_mode: str = "merge",
                reason: str | None = None,
                title: str | None = None,
            ) -> ToolResponse:
                """Apply a governed role/profile or capability update to the current or a target teammate."""
                target_specified = any(
                    _normalize_agent_candidate(value)
                    for value in (target_agent_id, target_role_id, target_role_name)
                )
                resolution = _resolve_teammate(
                    candidate_agent_id=_normalize_agent_candidate(target_agent_id),
                    target_role_id=_normalize_agent_candidate(target_role_id),
                    target_role_name=_normalize_agent_candidate(target_role_name),
                )
                if target_specified and resolution.error_code:
                    return _json_tool_response(
                        {
                            "success": False,
                            "error": resolution.error or "Target teammate not found",
                            "error_code": resolution.error_code,
                        },
                    )
                resolved_agent_id = resolution.agent_id or owner_agent_id
                normalized_role_text = _first_non_empty(role_text)
                normalized_role_name = _first_non_empty(role_name)
                normalized_role_summary = _first_non_empty(role_summary)
                capabilities_provided = capabilities is not None
                normalized_capabilities: list[str] | None = None
                if capabilities_provided:
                    if not isinstance(capabilities, list):
                        return _json_tool_response(
                            {
                                "success": False,
                                "error": "capabilities must be a list of strings",
                            },
                        )
                    normalized_capabilities = []
                    for item in capabilities:
                        normalized = _first_non_empty(item)
                        if normalized is None or normalized in normalized_capabilities:
                            continue
                        normalized_capabilities.append(normalized)
                if not any(
                    (
                        normalized_role_text,
                        normalized_role_name,
                        normalized_role_summary,
                        capabilities_provided,
                    ),
                ):
                    return _json_tool_response(
                        {
                            "success": False,
                            "error": "role_text, role_name, role_summary, or capabilities is required",
                        },
                    )
                normalized_mode = (
                    _first_non_empty(capability_assignment_mode, "merge") or "merge"
                ).strip().lower()
                if normalized_mode not in {"replace", "merge"}:
                    return _json_tool_response(
                        {
                            "success": False,
                            "error": "capability_assignment_mode must be 'replace' or 'merge'",
                        },
                    )
                payload: dict[str, Any] = {
                    "agent_id": resolved_agent_id,
                    "capability_assignment_mode": normalized_mode,
                    "reason": (
                        _first_non_empty(reason)
                        or f"runtime governed role/capability assignment by {owner_agent_id}"
                    ),
                }
                if normalized_role_text is not None:
                    payload["role_text"] = normalized_role_text
                if normalized_role_name is not None:
                    payload["role_name"] = normalized_role_name
                if normalized_role_summary is not None:
                    payload["role_summary"] = normalized_role_summary
                if capabilities_provided:
                    payload["capabilities"] = normalized_capabilities or []
                return _json_tool_response(
                    _structured_tool_payload(
                        await self._execute_bound_system_capability(
                            capability_id="system:apply_role",
                            owner_agent_id=owner_agent_id,
                            payload=payload,
                            title=title or f"Apply role/capabilities to {resolved_agent_id}",
                            parent_task_id=current_parent_task_id,
                            environment_ref=current_environment_ref,
                        ),
                        default_error=(
                            "apply_role returned an unexpected result payload"
                        ),
                    ),
                )

            tools.append(apply_role)

        if "system:discover_capabilities" in supported:
            async def discover_capabilities(
                query_text: str | None = None,
                queries: list[str] | None = None,
                current_capability_id: str | None = None,
                providers: list[str] | None = None,
                industry_profile: dict[str, Any] | None = None,
                role: dict[str, Any] | None = None,
                goal_context: list[str] | None = None,
                title: str | None = None,
            ) -> ToolResponse:
                """Discover governed install-template or allowlisted remote capability candidates."""
                normalized_queries = _string_list(
                    [
                        _first_non_empty(query_text),
                        *(queries or []),
                    ],
                )
                normalized_providers = [
                    str(provider).strip().lower()
                    for provider in _string_list(providers or [])
                    if str(provider).strip().lower()
                    in {
                        "install-template",
                        "builtin-runtime",
                        "curated-skill",
                        "hub-skill",
                        "mcp",
                        "mcp-registry",
                        "remote",
                    }
                ]
                payload: dict[str, Any] = {}
                if normalized_queries:
                    payload["queries"] = normalized_queries
                    if _first_non_empty(current_capability_id):
                        payload["current_capability_id"] = _first_non_empty(
                            current_capability_id,
                        )
                else:
                    if not isinstance(industry_profile, dict) or not isinstance(role, dict):
                        return _json_tool_response(
                            {
                                "success": False,
                                "error": (
                                    "query_text/queries is required, or provide both "
                                    "industry_profile and role for role-scoped discovery"
                                ),
                            },
                        )
                    payload["industry_profile"] = dict(industry_profile)
                    payload["role"] = dict(role)
                    if goal_context:
                        payload["goal_context"] = _string_list(goal_context)
                if normalized_providers:
                    payload["providers"] = normalized_providers
                return _json_tool_response(
                    _structured_tool_payload(
                        await self._execute_bound_system_capability(
                            capability_id="system:discover_capabilities",
                            owner_agent_id=owner_agent_id,
                            payload=payload,
                            title=title or "Discover capabilities",
                            parent_task_id=current_parent_task_id,
                            environment_ref=current_environment_ref,
                        ),
                        default_error=(
                            "discover_capabilities returned an unexpected result payload"
                        ),
                    ),
                )

            tools.append(discover_capabilities)

        return tools

    async def _execute_bound_system_capability(
        self,
        *,
        capability_id: str,
        owner_agent_id: str,
        payload: dict[str, object],
        title: str,
        parent_task_id: str | None = None,
        environment_ref: str | None = None,
    ) -> dict[str, object]:
        service = self._capability_service
        if service is None:
            return {"success": False, "error": "Capability service is not available"}
        getter = getattr(service, "get_capability", None)
        mount = getter(capability_id) if callable(getter) else None
        if mount is not None and self._kernel_dispatcher is not None:
            normalized_payload = dict(payload)
            task = KernelTask(
                title=title,
                capability_ref=capability_id,
                owner_agent_id=owner_agent_id,
                risk_level=getattr(mount, "risk_level", "guarded"),
                parent_task_id=parent_task_id,
                environment_ref=environment_ref,
                payload=normalized_payload,
            )
            if capability_id in {"system:dispatch_query", "system:dispatch_command"}:
                if not _first_non_empty(
                    normalized_payload.get("task_id"),
                    normalized_payload.get("kernel_task_id"),
                ):
                    task.payload["task_id"] = task.id
            admitted = self._kernel_dispatcher.submit(task)
            if admitted.phase != "executing":
                return admitted.model_dump(mode="json")
            executed = await self._kernel_dispatcher.execute_task(task.id)
            return executed.model_dump(mode="json")
        resolver = getattr(service, "resolve_executor", None)
        executor = resolver(capability_id) if callable(resolver) else None
        if executor is None:
            return {
                "success": False,
                "error": f"Capability '{capability_id}' does not have an executable binding",
            }
        result = executor(payload=payload)
        if asyncio.iscoroutine(result):
            return await result
        return result
