# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_actor import *  # noqa: F401,F403


@router.get("/agents", response_model=list[dict[str, object]])
async def list_agents(
    request: Request,
    response: Response,
    view: Literal["all", "business", "system"] = "all",
    industry_instance_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """List all registered agent profiles."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_agent_profile_service(request)
    agents = service.list_agents(
        view=view,
        limit=limit,
        industry_instance_id=industry_instance_id,
    )
    return [
        _public_agent_payload(agent) or {"agent_id": getattr(agent, "agent_id", None)}
        for agent in agents
    ]


@router.get("/agents/{agent_id}", response_model=dict[str, object])
async def get_agent(
    agent_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Get a single agent profile by ID."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_agent_profile_service(request)
    detail_getter = getattr(service, "get_agent_detail", None)
    if callable(detail_getter):
        detail = detail_getter(agent_id)
        if detail is not None:
            public_detail = _public_agent_detail_payload(detail)
            if public_detail is not None:
                return public_detail
    agent = service.get_agent(agent_id)
    if agent is not None:
        return _public_agent_payload(agent) or {"agent_id": agent_id}
    raise HTTPException(404, detail=f"Agent '{agent_id}' not found")


@router.get("/actors", response_model=list[dict[str, object]])
async def list_actors(
    request: Request,
    response: Response,
    runtime_status: str | None = None,
    desired_state: str | None = None,
    industry_instance_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List persisted resident actor runtimes."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    repository = _get_agent_runtime_repository(request)
    runtimes = repository.list_runtimes(
        runtime_status=runtime_status,
        desired_state=desired_state,
        industry_instance_id=industry_instance_id,
        limit=limit,
    )
    return [_actor_runtime_payload(runtime) for runtime in runtimes]


@router.get("/actors/{agent_id}", response_model=dict[str, object])
async def get_actor_detail(
    agent_id: str,
    request: Request,
    response: Response,
    mailbox_limit: int = 20,
    checkpoint_limit: int = 20,
    lease_limit: int = 20,
    binding_limit: int = 20,
) -> dict[str, object]:
    """Return actor runtime detail with mailbox, checkpoints, leases, and teammates."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    runtime_repository = _get_agent_runtime_repository(request)
    mailbox_repository = _get_agent_mailbox_repository(request)
    checkpoint_repository = _get_agent_checkpoint_repository(request)
    lease_repository = _get_agent_lease_repository(request)
    binding_repository = _get_agent_thread_binding_repository(request)
    mailbox_service = _get_actor_mailbox_service(request)

    runtime = runtime_repository.get_runtime(agent_id)
    if runtime is None:
        raise HTTPException(404, detail=f"Actor '{agent_id}' not found")

    runtime_payload = _actor_runtime_payload(runtime)
    mailbox_records = mailbox_repository.list_items(agent_id=agent_id, limit=mailbox_limit)
    mailbox_items = [
        _actor_mailbox_payload(item)
        for item in mailbox_records
    ]
    checkpoint_records = checkpoint_repository.list_checkpoints(
        agent_id=agent_id,
        limit=checkpoint_limit,
    )
    checkpoints = [
        checkpoint.model_dump(mode="json")
        for checkpoint in checkpoint_records
    ]
    leases = [
        lease.model_dump(mode="json")
        for lease in lease_repository.list_leases(agent_id=agent_id, limit=lease_limit)
    ]
    thread_bindings = [
        binding.model_dump(mode="json")
        for binding in binding_repository.list_bindings(
            agent_id=agent_id,
            active_only=False,
            limit=binding_limit,
        )
    ]
    teammates_payload: list[dict[str, object]] = []
    list_teammates = getattr(mailbox_service, "list_teammates", None)
    if callable(list_teammates):
        teammates = list_teammates(
            agent_id=agent_id,
            industry_instance_id=runtime.industry_instance_id,
        )
        teammates_payload = [
            item if isinstance(item, dict) else (_model_dump_or_dict(item) or {"agent_id": getattr(item, "agent_id", None)})
            for item in teammates
        ]
    focus = await _get_actor_focus_payload(
        request,
        runtime=runtime,
        mailbox_items=mailbox_records,
        checkpoints=checkpoint_records,
    )
    return {
        "runtime": runtime_payload,
        "mailbox": mailbox_items,
        "checkpoints": checkpoints,
        "leases": leases,
        "thread_bindings": thread_bindings,
        "teammates": teammates_payload,
        "focus": focus,
        "capability_surface": _get_agent_capability_surface(request, agent_id=agent_id),
        "stats": {
            "mailbox_count": len(mailbox_items),
            "checkpoint_count": len(checkpoints),
            "lease_count": len(leases),
            "binding_count": len(thread_bindings),
            "teammate_count": len(teammates_payload),
        },
    }


@router.get("/actors/{agent_id}/mailbox", response_model=list[dict[str, object]])
async def list_actor_mailbox(
    agent_id: str,
    request: Request,
    response: Response,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List mailbox items for a resident actor."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    runtime_repository = _get_agent_runtime_repository(request)
    mailbox_repository = _get_agent_mailbox_repository(request)
    if runtime_repository.get_runtime(agent_id) is None:
        raise HTTPException(404, detail=f"Actor '{agent_id}' not found")
    return [
        _actor_mailbox_payload(item)
        for item in mailbox_repository.list_items(
            agent_id=agent_id,
            status=status,
            limit=limit,
        )
    ]


@router.get("/actors/{agent_id}/mailbox/{item_id}", response_model=dict[str, object])
async def get_actor_mailbox_item(
    agent_id: str,
    item_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single mailbox item for a resident actor."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    mailbox_repository = _get_agent_mailbox_repository(request)
    item = mailbox_repository.get_item(item_id)
    if item is None or item.agent_id != agent_id:
        raise HTTPException(404, detail=f"Mailbox item '{item_id}' not found for actor '{agent_id}'")
    return _actor_mailbox_payload(item)


@router.get("/actors/{agent_id}/checkpoints", response_model=list[dict[str, object]])
async def list_actor_checkpoints(
    agent_id: str,
    request: Request,
    response: Response,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List execution checkpoints for a resident actor."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    runtime_repository = _get_agent_runtime_repository(request)
    checkpoint_repository = _get_agent_checkpoint_repository(request)
    if runtime_repository.get_runtime(agent_id) is None:
        raise HTTPException(404, detail=f"Actor '{agent_id}' not found")
    return [
        checkpoint.model_dump(mode="json")
        for checkpoint in checkpoint_repository.list_checkpoints(agent_id=agent_id, limit=limit)
    ]


@router.get("/actors/{agent_id}/leases", response_model=list[dict[str, object]])
async def list_actor_leases(
    agent_id: str,
    request: Request,
    response: Response,
    lease_status: str | None = None,
    lease_kind: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List active and historical leases for a resident actor."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    runtime_repository = _get_agent_runtime_repository(request)
    lease_repository = _get_agent_lease_repository(request)
    if runtime_repository.get_runtime(agent_id) is None:
        raise HTTPException(404, detail=f"Actor '{agent_id}' not found")
    return [
        lease.model_dump(mode="json")
        for lease in lease_repository.list_leases(
            agent_id=agent_id,
            lease_status=lease_status,
            lease_kind=lease_kind,
            limit=limit,
        )
    ]


@router.get("/actors/{agent_id}/teammates", response_model=list[dict[str, object]])
async def list_actor_teammates(
    agent_id: str,
    request: Request,
    response: Response,
    industry_instance_id: str | None = None,
) -> list[dict[str, object]]:
    """List teammates that can collaborate with the actor."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    runtime_repository = _get_agent_runtime_repository(request)
    mailbox_service = _get_actor_mailbox_service(request)
    if runtime_repository.get_runtime(agent_id) is None:
        raise HTTPException(404, detail=f"Actor '{agent_id}' not found")
    list_teammates = getattr(mailbox_service, "list_teammates", None)
    if not callable(list_teammates):
        raise HTTPException(503, detail="Actor mailbox service cannot list teammates")
    teammates = list_teammates(
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
    )
    return [
        item if isinstance(item, dict) else (_model_dump_or_dict(item) or {"agent_id": getattr(item, "agent_id", None)})
        for item in teammates
    ]


@router.get("/agents/{agent_id}/capabilities", response_model=dict[str, object])
async def get_agent_capabilities(
    agent_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return the effective capability surface for a visible agent."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    return _get_agent_capability_surface(request, agent_id=agent_id)


@router.get("/actors/{agent_id}/capabilities", response_model=dict[str, object])
async def get_actor_capabilities(
    agent_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return the effective capability surface for a resident actor."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    runtime_repository = _get_agent_runtime_repository(request)
    if runtime_repository.get_runtime(agent_id) is None:
        raise HTTPException(404, detail=f"Actor '{agent_id}' not found")
    return _get_agent_capability_surface(request, agent_id=agent_id)


@router.put("/agents/{agent_id}/capabilities", response_model=dict[str, object])
async def assign_agent_capabilities(
    agent_id: str,
    request: Request,
    response: Response,
    payload: AgentCapabilityAssignmentRequest | None = None,
) -> dict[str, object]:
    """Assign an explicit capability allowlist to a visible agent through the kernel-governed profile path."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    request_payload = payload or AgentCapabilityAssignmentRequest()
    return await _assign_agent_capabilities(
        request,
        agent_id=agent_id,
        payload=request_payload,
        require_actor=False,
    )


@router.post("/agents/{agent_id}/capabilities/governed", response_model=dict[str, object])
async def govern_agent_capabilities(
    agent_id: str,
    request: Request,
    response: Response,
    payload: GovernedAgentCapabilityAssignmentRequest | None = None,
) -> dict[str, object]:
    """Submit an agent capability assignment into the governance confirmation flow."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    request_payload = payload or GovernedAgentCapabilityAssignmentRequest()
    return await _submit_governed_capabilities(
        request,
        agent_id=agent_id,
        payload=request_payload,
        require_actor=False,
    )


# ── Kernel task endpoints ──────────────────────────────────────────


@router.get("/decisions", response_model=list[dict[str, object]])
async def list_decisions(
    request: Request,
    response: Response,
    limit: int = 5,
) -> list[dict[str, object]]:
    """List unified DecisionRequest records for Runtime Center."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    decisions = await _call_runtime_query_method(
        state_query,
        "list_decision_requests",
        "list_decisions",
        "get_decision_requests",
        not_available_detail="Decision queries are not available",
        limit=limit,
    )
    return decisions if isinstance(decisions, list) else []


@router.get("/decisions/{decision_id}", response_model=dict[str, object])
async def get_decision_detail(
    decision_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single DecisionRequest detail payload."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    decision = await _call_runtime_query_method(
        state_query,
        "get_decision_request",
        "get_decision",
        not_available_detail="Decision detail queries are not available",
        decision_id=decision_id,
    )
    if decision is None:
        raise HTTPException(404, detail=f"Decision request '{decision_id}' not found")
    return decision if isinstance(decision, dict) else {"decision": decision}


async def _review_decision_payload(
    decision_id: str,
    request: Request,
) -> dict[str, object]:
    dispatcher = _get_kernel_dispatcher(request)
    task_store = getattr(dispatcher, "task_store", None)
    reviewer = getattr(task_store, "mark_decision_reviewing", None)
    if not callable(reviewer):
        raise HTTPException(503, detail="Decision review updates are not available")
    decision_record = reviewer(decision_id)
    if decision_record is None:
        raise HTTPException(404, detail=f"Decision request '{decision_id}' not found")
    state_query = _get_state_query_service(request)
    decision = await _call_runtime_query_method(
        state_query,
        "get_decision_request",
        not_available_detail="Decision detail queries are not available",
        decision_id=decision_id,
    )
    if decision is None:
        return {"decision": _model_dump_or_dict(decision_record)}
    return decision if isinstance(decision, dict) else {"decision": decision}


@router.post("/governed/decisions/{decision_id}/review", response_model=dict[str, object])
async def review_decision_governed(
    decision_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Advance a decision from open to reviewing through the governed write surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    return await _review_decision_payload(decision_id, request)


@router.post("/decisions/{decision_id}/approve", response_model=dict[str, object])
async def approve_decision(
    decision_id: str,
    request: Request,
    response: Response,
    payload: DecisionApproveRequest | None = None,
) -> dict[str, object]:
    """Approve a DecisionRequest through the kernel dispatcher."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    decision_repository = getattr(request.app.state, "decision_request_repository", None)
    decision = (
        decision_repository.get_decision_request(decision_id)
        if decision_repository is not None
        else None
    )
    is_acquisition_decision = (
        decision is not None
        and str(getattr(decision, "decision_type", "") or "").strip() == "acquisition-approval"
    )
    dispatcher = _get_kernel_dispatcher(request)
    response_payload: dict[str, object]
    resolved_decision_id = decision_id
    try:
        result = await _call_runtime_query_method(
            dispatcher,
            "approve_decision",
            not_available_detail="Kernel dispatcher is not available",
            decision_id=decision_id,
            resolution=payload.resolution if payload is not None else None,
            execute=payload.execute if payload is not None else None,
        )
    except KeyError as exc:
        _raise_dispatcher_error(exc)
    except Exception as exc:  # pragma: no cover - mapped explicitly below
        _raise_dispatcher_error(exc)
    else:
        response_payload = result.model_dump(mode="json")
        resolved_decision_id = (
            str(getattr(result, "decision_request_id", "") or "").strip() or decision_id
        )
    if is_acquisition_decision:
        service = _get_learning_service(request)
        try:
            finalized = await _call_runtime_query_method(
                service,
                "finalize_resolved_decision",
                not_available_detail="Learning service is not available",
                decision_id=resolved_decision_id,
                status="approved",
                actor="runtime-center",
                resolution=payload.resolution if payload is not None else None,
            )
        except KeyError as exc:
            raise HTTPException(404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        decision_payload = (
            _model_dump_or_dict(finalized.get("decision"))
            or _model_dump_or_dict(finalized.get("decision_request"))
            or (
                _model_dump_or_dict(decision_repository.get_decision_request(resolved_decision_id))
                if decision_repository is not None
                else None
            )
        )
        return {
            "decision_request_id": resolved_decision_id,
            "decision": decision_payload,
            "proposal": _model_dump_or_dict(finalized.get("proposal")),
            "plan": _model_dump_or_dict(finalized.get("plan")),
            "onboarding_run": _model_dump_or_dict(finalized.get("onboarding_run")),
            "kernel_result": (
                _model_dump_or_dict(finalized.get("kernel_result")) or response_payload
            ),
        }
    if _schedule_query_tool_confirmation_resume(
        request,
        decision_id=resolved_decision_id,
    ):
        response_payload["resume_scheduled"] = True
        response_payload["resume_kind"] = "query-tool-confirmation"
    return response_payload


@router.post("/decisions/{decision_id}/reject", response_model=dict[str, object])
async def reject_decision(
    decision_id: str,
    request: Request,
    response: Response,
    payload: DecisionRejectRequest | None = None,
) -> dict[str, object]:
    """Reject a DecisionRequest through the kernel dispatcher."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    decision_repository = getattr(request.app.state, "decision_request_repository", None)
    decision = (
        decision_repository.get_decision_request(decision_id)
        if decision_repository is not None
        else None
    )
    is_acquisition_decision = (
        decision is not None
        and str(getattr(decision, "decision_type", "") or "").strip() == "acquisition-approval"
    )
    dispatcher = _get_kernel_dispatcher(request)
    response_payload: dict[str, object]
    resolved_decision_id = decision_id
    try:
        result = await _call_runtime_query_method(
            dispatcher,
            "reject_decision",
            not_available_detail="Kernel dispatcher is not available",
            decision_id=decision_id,
            resolution=payload.resolution if payload is not None else None,
        )
    except KeyError as exc:
        _raise_dispatcher_error(exc)
    except Exception as exc:  # pragma: no cover - mapped explicitly below
        _raise_dispatcher_error(exc)
    else:
        response_payload = result.model_dump(mode="json")
        resolved_decision_id = (
            str(getattr(result, "decision_request_id", "") or "").strip() or decision_id
        )
    if is_acquisition_decision:
        service = _get_learning_service(request)
        try:
            finalized = await _call_runtime_query_method(
                service,
                "finalize_resolved_decision",
                not_available_detail="Learning service is not available",
                decision_id=resolved_decision_id,
                status="rejected",
                actor="runtime-center",
                resolution=payload.resolution if payload is not None else None,
            )
        except KeyError as exc:
            raise HTTPException(404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        decision_payload = (
            _model_dump_or_dict(finalized.get("decision"))
            or _model_dump_or_dict(finalized.get("decision_request"))
            or (
                _model_dump_or_dict(decision_repository.get_decision_request(resolved_decision_id))
                if decision_repository is not None
                else None
            )
        )
        return {
            "decision_request_id": resolved_decision_id,
            "decision": decision_payload,
            "proposal": _model_dump_or_dict(finalized.get("proposal")),
            "kernel_result": (
                _model_dump_or_dict(finalized.get("kernel_result")) or response_payload
            ),
        }
    return response_payload


@router.get("/kernel/tasks", response_model=list[dict[str, object]])
async def list_kernel_tasks(
    request: Request,
    response: Response,
    phase: str | None = None,
) -> list[dict[str, object]]:
    """List active kernel tasks."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    tasks = await _call_runtime_query_method(
        state_query,
        "list_kernel_tasks",
        not_available_detail="Kernel task queries are not available",
        phase=phase,
    )
    return tasks if isinstance(tasks, list) else []


@router.post("/kernel/tasks/{task_id}/confirm", response_model=dict[str, object])
async def confirm_kernel_task(
    task_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Approve a waiting-confirm kernel task and execute it when possible."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    dispatcher = _get_kernel_dispatcher(request)

    task = dispatcher.lifecycle.get_task(task_id)
    if task is None:
        raise HTTPException(404, detail=f"Kernel task '{task_id}' not found")

    task_payload = task.payload if isinstance(task.payload, dict) else {}
    if task_payload.get("decision_type") == "query-tool-confirmation":
        task_store = dispatcher.task_store
        if task_store is None:
            raise HTTPException(
                503,
                detail="Decision requests are not backed by the unified state store",
            )
        pending_decision = next(
            (
                decision
                for decision in task_store.list_decision_requests(task_id=task_id)
                if getattr(decision, "status", None) in {"open", "reviewing"}
            ),
            None,
        )
        if pending_decision is None:
            raise HTTPException(
                409,
                detail=(
                    f"Kernel task '{task_id}' is missing an open decision request "
                    "for query-tool-confirmation"
                ),
            )
        try:
            result = await dispatcher.approve_decision(pending_decision.id)
        except Exception as exc:  # pragma: no cover - mapped explicitly below
            _raise_dispatcher_error(exc)
        response_payload = result.model_dump(mode="json")
        resolved_decision_id = (
            str(getattr(result, "decision_request_id", "") or "").strip()
            or pending_decision.id
        )
        if _schedule_query_tool_confirmation_resume(
            request,
            decision_id=resolved_decision_id,
        ):
            response_payload["resume_scheduled"] = True
            response_payload["resume_kind"] = "query-tool-confirmation"
        return response_payload

    try:
        result = await dispatcher.confirm_and_execute(task_id)
    except Exception as exc:  # pragma: no cover - mapped explicitly below
        _raise_dispatcher_error(exc)
    return result.model_dump(mode="json")


# ── Learning & growth endpoints ────────────────────────────────


@router.get("/learning/proposals", response_model=list[dict[str, object]])
async def list_proposals(
    request: Request,
    response: Response,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """List improvement proposals."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    proposals = service.list_proposals(status=status, limit=limit)
    return [p.model_dump(mode="json") for p in proposals]


@router.get("/learning/patches", response_model=list[dict[str, object]])
async def list_patches(
    request: Request,
    response: Response,
    status: str | None = None,
    goal_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """List patches."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    patches = service.list_patches(
        status=status,
        goal_id=goal_id,
        task_id=task_id,
        agent_id=agent_id,
        limit=limit,
    )
    return [p.model_dump(mode="json") for p in patches]


@router.get("/learning/patches/{patch_id}", response_model=dict[str, object])
async def get_patch_detail(
    patch_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    try:
        patch = service.get_patch(patch_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    patch_payload = patch.model_dump(mode="json")
    patch_status = str(patch_payload.get("status") or "proposed")
    patch_risk_level = str(patch_payload.get("risk_level") or "auto")

    task_repository = _get_task_repository(request)
    decision_repository = _get_decision_request_repository(request)
    evidence_query_service = _get_evidence_query_service(request)
    goal_service = _get_goal_service(request)
    agent_profile_service = _get_agent_profile_service(request)

    task = task_repository.get_task(patch.task_id) if patch.task_id else None
    goal = goal_service.get_goal(patch.goal_id) if patch.goal_id else None
    agent = agent_profile_service.get_agent(patch.agent_id) if patch.agent_id else None
    evidence_records = []
    seen_evidence_ids: set[str] = set()
    for evidence_id in [patch.source_evidence_id, *patch.evidence_refs]:
        if not evidence_id or evidence_id in seen_evidence_ids:
            continue
        seen_evidence_ids.add(evidence_id)
        record = evidence_query_service.get_record(evidence_id)
        if record is not None:
            evidence_records.append(evidence_query_service.serialize_record(record))

    decisions = [
        _model_dump_or_dict(decision)
        for decision in decision_repository.list_decision_requests(task_id=patch.id)
        if _model_dump_or_dict(decision) is not None
    ]
    growth = [
        _model_dump_or_dict(event)
        for event in service.list_growth(source_patch_id=patch.id, limit=200)
        if _model_dump_or_dict(event) is not None
    ]
    return {
        "patch": patch_payload,
        "goal": _model_dump_or_dict(goal),
        "task": _model_dump_or_dict(task),
        "agent": _model_dump_or_dict(agent),
        "evidence": evidence_records,
        "decisions": decisions,
        "growth": growth,
        "actions": _build_patch_actions(
            patch_id,
            patch_status,
            patch_risk_level,
        ),
        "routes": {
            "goal": f"/api/goals/{patch.goal_id}/detail" if patch.goal_id else None,
            "task": f"/api/runtime-center/tasks/{patch.task_id}" if patch.task_id else None,
            "agent": f"/api/runtime-center/agents/{patch.agent_id}" if patch.agent_id else None,
        },
    }


@router.post("/learning/patches/{patch_id}/approve", response_model=dict[str, object])
async def approve_runtime_center_patch(
    patch_id: str,
    request: Request,
    response: Response,
    payload: PatchActionRequest | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    actor = payload.actor if payload is not None else "system"
    try:
        service.get_patch(patch_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:approve_patch",
        title=f"Approve patch '{patch_id}'",
        payload={
            "actor": actor,
            "owner_agent_id": "copaw-operator",
            "patch_id": patch_id,
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            patch = service.get_patch(patch_id)
            return {
                "approved": False,
                "result": result,
                "decision": _get_decision_payload(request, result.get("decision_request_id")),
                "patch": patch.model_dump(mode="json"),
            }
        raise HTTPException(400, detail=result.get("error") or "Patch approval failed")
    patch = service.get_patch(patch_id)
    return patch.model_dump(mode="json")


@router.post("/learning/patches/{patch_id}/reject", response_model=dict[str, object])
async def reject_runtime_center_patch(
    patch_id: str,
    request: Request,
    response: Response,
    payload: PatchActionRequest | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    actor = payload.actor if payload is not None else "system"
    try:
        service.get_patch(patch_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:reject_patch",
        title=f"Reject patch '{patch_id}'",
        payload={
            "actor": actor,
            "owner_agent_id": "copaw-operator",
            "patch_id": patch_id,
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            patch = service.get_patch(patch_id)
            return {
                "rejected": False,
                "result": result,
                "decision": _get_decision_payload(request, result.get("decision_request_id")),
                "patch": patch.model_dump(mode="json"),
            }
        raise HTTPException(400, detail=result.get("error") or "Patch rejection failed")
    patch = service.get_patch(patch_id)
    return patch.model_dump(mode="json")


@router.post("/learning/patches/{patch_id}/apply", response_model=dict[str, object])
async def apply_runtime_center_patch(
    patch_id: str,
    request: Request,
    response: Response,
    payload: PatchActionRequest | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    actor = payload.actor if payload is not None else "system"
    try:
        patch = service.get_patch(patch_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    patch_payload = _model_dump_or_dict(patch) or {}
    if str(patch_payload.get("status") or "") != "approved":
        raise HTTPException(400, detail="Only approved patches can be applied")
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:apply_patch",
        title=f"Apply patch '{patch_id}'",
        payload={
            "actor": actor,
            "owner_agent_id": "copaw-operator",
            "patch_id": patch_id,
            "applied_by": actor,
            "disable_main_brain_auto_adjudicate": True,
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {
                "applied": False,
                "result": result,
                "decision": _get_decision_payload(request, result.get("decision_request_id")),
                "patch": patch_payload,
            }
        raise HTTPException(400, detail=result.get("error") or "Patch apply failed")
    patch = service.get_patch(patch_id)
    return patch.model_dump(mode="json")


@router.post("/learning/patches/{patch_id}/rollback", response_model=dict[str, object])
async def rollback_runtime_center_patch(
    patch_id: str,
    request: Request,
    response: Response,
    payload: PatchActionRequest | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    actor = payload.actor if payload is not None else "system"
    try:
        patch = service.get_patch(patch_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:rollback_patch",
        title=f"Rollback patch '{patch_id}'",
        payload={
            "actor": actor,
            "owner_agent_id": "copaw-operator",
            "patch_id": patch_id,
            "rolled_back_by": actor,
            "disable_main_brain_auto_adjudicate": True,
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {
                "rolled_back": False,
                "result": result,
                "decision": _get_decision_payload(request, result.get("decision_request_id")),
                "patch": patch.model_dump(mode="json"),
            }
        raise HTTPException(400, detail=result.get("error") or "Patch rollback failed")
    patch = service.get_patch(patch_id)
    return patch.model_dump(mode="json")


@router.get("/learning/growth", response_model=list[dict[str, object]])
async def list_growth(
    request: Request,
    response: Response,
    agent_id: str | None = None,
    goal_id: str | None = None,
    task_id: str | None = None,
    source_patch_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List agent growth events."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    events = service.list_growth(
        agent_id=agent_id,
        goal_id=goal_id,
        task_id=task_id,
        source_patch_id=source_patch_id,
        limit=limit,
    )
    return [e.model_dump(mode="json") for e in events]


@router.get("/learning/growth/{event_id}", response_model=dict[str, object])
async def get_growth_detail(
    event_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single growth event."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    try:
        event = service.get_growth_event(event_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    event_payload = event.model_dump(mode="json")
    source_patch_id = _runtime_non_empty_str(event_payload.get("source_patch_id"))
    source_evidence_id = _runtime_non_empty_str(event_payload.get("source_evidence_id"))
    goal_id = _runtime_non_empty_str(event_payload.get("goal_id"))
    task_id = _runtime_non_empty_str(event_payload.get("task_id"))
    agent_id = _runtime_non_empty_str(event_payload.get("agent_id"))
    return {
        "event": event_payload,
        "routes": {
            "patch": (
                f"/api/runtime-center/learning/patches/{source_patch_id}"
                if source_patch_id is not None
                else None
            ),
            "evidence": (
                f"/api/runtime-center/evidence/{source_evidence_id}"
                if source_evidence_id is not None
                else None
            ),
            "goal": (
                f"/api/goals/{goal_id}/detail"
                if goal_id is not None
                else None
            ),
            "task": (
                f"/api/runtime-center/tasks/{task_id}"
                if task_id is not None
                else None
            ),
            "agent": (
                f"/api/runtime-center/agents/{agent_id}"
                if agent_id is not None
                else None
            ),
        },
    }
