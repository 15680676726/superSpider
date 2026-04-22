# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import HTTPException, Request, Response

from ..runtime_center import apply_runtime_center_surface_headers
from .runtime_center_actor_capabilities import (
    _get_decision_payload,
    _schedule_query_tool_confirmation_resume,
)
from .runtime_center_dependencies import (
    _get_evidence_query_service,
    _get_kernel_dispatcher,
    _get_learning_service,
    _get_state_query_service,
)
from .runtime_center_mutation_helpers import (
    _call_runtime_query_method,
    _dispatch_runtime_mutation,
    _raise_dispatcher_error,
)
from .runtime_center_payloads import _build_patch_actions, _model_dump_or_dict
from .runtime_center_request_models import (
    DecisionApproveRequest,
    DecisionRejectRequest,
    PatchActionRequest,
)
from .runtime_center_shared import router


def _serialize_learning_object(value: object | None) -> dict[str, object] | None:
    payload = _model_dump_or_dict(value)
    return payload if isinstance(payload, dict) else None


def _serialize_learning_list(items: object | None) -> list[dict[str, object]]:
    if not isinstance(items, list):
        return []
    payload: list[dict[str, object]] = []
    for item in items:
        serialized = _serialize_learning_object(item)
        if serialized is not None:
            payload.append(serialized)
    return payload


def _get_learning_patch_or_404(service: object, patch_id: str) -> tuple[object, dict[str, object]]:
    getter = getattr(service, "get_patch", None)
    if not callable(getter):
        raise HTTPException(503, detail="Learning patch queries are not available")
    try:
        patch = getter(patch_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    payload = _serialize_learning_object(patch)
    if payload is None:
        raise HTTPException(500, detail="Learning patch payload is not serializable")
    return patch, payload


async def _govern_patch_mutation(
    *,
    request: Request,
    patch_id: str,
    actor: str,
    capability_ref: str,
    title: str,
    response_key: str,
    allowed_statuses: set[str],
    invalid_detail: str,
) -> dict[str, object]:
    service = _get_learning_service(request)
    _patch, patch_payload = _get_learning_patch_or_404(service, patch_id)
    status = str(patch_payload.get("status") or "").strip()
    if status not in allowed_statuses:
        raise HTTPException(400, detail=invalid_detail)
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref=capability_ref,
        title=title,
        payload={
            "patch_id": patch_id,
            "actor": actor,
            "owner_agent_id": "runtime-center",
            "disable_main_brain_auto_approval": True,
        },
        fallback_risk="confirm",
        risk_level_override="confirm",
    )
    if not result.get("success") and result.get("phase") == "waiting-confirm":
        return {response_key: False, "result": result}
    if not result.get("success"):
        raise HTTPException(400, detail=result.get("error") or f"Patch mutation failed for '{patch_id}'")
    _updated_patch, updated_payload = _get_learning_patch_or_404(service, patch_id)
    return {response_key: True, "patch": updated_payload, "result": result}


def _goal_route(goal_id: str | None) -> str | None:
    normalized = str(goal_id or "").strip()
    if not normalized:
        return None
    return f"/api/goals/{normalized}/detail"


def _patch_evidence_payloads(
    *,
    evidence_query: object,
    patch_id: str,
    patch_payload: dict[str, object],
) -> list[dict[str, object]]:
    list_by_task = getattr(evidence_query, "list_by_task", None)
    serialize_record = getattr(evidence_query, "serialize_record", None)
    if callable(list_by_task) and callable(serialize_record):
        return [
            serialize_record(record)
            for record in list_by_task(patch_id, limit=None)
        ]
    getter = getattr(evidence_query, "get_record", None)
    if not callable(getter) or not callable(serialize_record):
        return []
    evidence_ids: list[str] = []
    source_evidence_id = str(patch_payload.get("source_evidence_id") or "").strip()
    if source_evidence_id:
        evidence_ids.append(source_evidence_id)
    for evidence_id in patch_payload.get("evidence_refs") or []:
        normalized = str(evidence_id or "").strip()
        if normalized and normalized not in evidence_ids:
            evidence_ids.append(normalized)
    payload: list[dict[str, object]] = []
    for evidence_id in evidence_ids:
        record = getter(evidence_id)
        if record is not None:
            payload.append(serialize_record(record))
    return payload


@router.get("/learning/proposals", response_model=list[dict[str, object]])
async def list_learning_proposals(
    request: Request,
    response: Response,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """List learning proposals through the Runtime Center formal surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    proposals = await _call_runtime_query_method(
        service,
        "list_proposals",
        not_available_detail="Learning proposal queries are not available",
        status=status,
        limit=limit,
    )
    return _serialize_learning_list(proposals)


@router.get("/learning/patches", response_model=list[dict[str, object]])
async def list_learning_patches(
    request: Request,
    response: Response,
    status: str | None = None,
    goal_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """List learning patches through the Runtime Center formal surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    patches = await _call_runtime_query_method(
        service,
        "list_patches",
        not_available_detail="Learning patch queries are not available",
        status=status,
        goal_id=goal_id,
        task_id=task_id,
        agent_id=agent_id,
        limit=limit,
    )
    return _serialize_learning_list(patches)


@router.get("/learning/patches/{patch_id}", response_model=dict[str, object])
async def get_learning_patch_detail(
    patch_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a Runtime Center detail payload for a single patch."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    _patch, patch_payload = _get_learning_patch_or_404(service, patch_id)
    evidence_query = _get_evidence_query_service(request)
    evidence = _patch_evidence_payloads(
        evidence_query=evidence_query,
        patch_id=patch_id,
        patch_payload=patch_payload,
    )
    growth = _serialize_learning_list(
        await _call_runtime_query_method(
            service,
            "list_growth",
            not_available_detail="Learning growth queries are not available",
            source_patch_id=patch_id,
            limit=200,
        ),
    )
    decision_repository = getattr(request.app.state, "decision_request_repository", None)
    decision_lister = getattr(decision_repository, "list_decision_requests", None)
    decisions = (
        _serialize_learning_list(decision_lister(task_id=patch_id, status=None))
        if callable(decision_lister)
        else []
    )
    routes: dict[str, object] = {}
    goal_route = _goal_route(patch_payload.get("goal_id"))
    if goal_route is not None:
        routes["goal"] = goal_route
    return {
        "patch": patch_payload,
        "evidence": evidence,
        "growth": growth,
        "decisions": decisions,
        "routes": routes,
        "actions": _build_patch_actions(
            patch_id,
            status=str(patch_payload.get("status") or ""),
            risk_level=str(patch_payload.get("risk_level") or "auto"),
        ),
    }


@router.get("/learning/growth", response_model=list[dict[str, object]])
async def list_learning_growth(
    request: Request,
    response: Response,
    agent_id: str | None = None,
    goal_id: str | None = None,
    task_id: str | None = None,
    source_patch_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List learning growth events through the Runtime Center formal surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    events = await _call_runtime_query_method(
        service,
        "list_growth",
        not_available_detail="Learning growth queries are not available",
        agent_id=agent_id,
        goal_id=goal_id,
        task_id=task_id,
        source_patch_id=source_patch_id,
        limit=limit,
    )
    return _serialize_learning_list(events)


@router.get("/learning/growth/{event_id}", response_model=dict[str, object])
async def get_learning_growth_detail(
    event_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a Runtime Center detail payload for a single growth event."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    getter = getattr(service, "get_growth_event", None)
    if not callable(getter):
        raise HTTPException(503, detail="Learning growth detail queries are not available")
    try:
        event = getter(event_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    event_payload = _serialize_learning_object(event)
    if event_payload is None:
        raise HTTPException(500, detail="Learning growth payload is not serializable")
    routes: dict[str, object] = {}
    source_patch_id = str(event_payload.get("source_patch_id") or "").strip()
    if source_patch_id:
        routes["patch"] = f"/api/runtime-center/learning/patches/{source_patch_id}"
    return {"event": event_payload, "routes": routes}


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
        model_dump = getattr(decision_record, "model_dump", None)
        if callable(model_dump):
            return {"decision": model_dump(mode="json")}
        return {"decision": {"id": getattr(decision_record, "id", None)}}
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
    except Exception as exc:  # pragma: no cover
        _raise_dispatcher_error(exc)
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
        decision_payload = _serialize_learning_object(finalized.get("decision")) or _get_decision_payload(
            request,
            resolved_decision_id,
        ) or (
            decision_repository.get_decision_request(resolved_decision_id).model_dump(mode="json")
            if decision_repository is not None
            and decision_repository.get_decision_request(resolved_decision_id) is not None
            else None
        )
        return {
            "decision_request_id": resolved_decision_id,
            "decision": decision_payload,
            "proposal": _serialize_learning_object(finalized.get("proposal")) or finalized.get("proposal"),
            "plan": _serialize_learning_object(finalized.get("plan")) or finalized.get("plan"),
            "onboarding_run": (
                _serialize_learning_object(finalized.get("onboarding_run"))
                or finalized.get("onboarding_run")
            ),
            "kernel_result": _serialize_learning_object(finalized.get("kernel_result")) or response_payload,
        }
    if _schedule_query_tool_confirmation_resume(request, decision_id=resolved_decision_id):
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
    except Exception as exc:  # pragma: no cover
        _raise_dispatcher_error(exc)
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
        return {
            "decision_request_id": resolved_decision_id,
            "decision": _serialize_learning_object(finalized.get("decision"))
            or _get_decision_payload(request, resolved_decision_id),
            "proposal": _serialize_learning_object(finalized.get("proposal")) or finalized.get("proposal"),
            "kernel_result": _serialize_learning_object(finalized.get("kernel_result")) or response_payload,
        }
    return response_payload


@router.post("/learning/patches/{patch_id}/approve", response_model=dict[str, object])
async def approve_patch(
    patch_id: str,
    request: Request,
    response: Response,
    payload: PatchActionRequest | None = None,
) -> dict[str, object]:
    """Approve a learning patch through the Runtime Center governed surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    actor = payload.actor if payload is not None else "system"
    approver = getattr(service, "approve_patch", None)
    if not callable(approver):
        raise HTTPException(503, detail="Learning patch approvals are not available")
    try:
        patch = approver(patch_id, approved_by=actor)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    patch_payload = _serialize_learning_object(patch)
    if patch_payload is None:
        raise HTTPException(500, detail="Learning patch payload is not serializable")
    return patch_payload


@router.post("/learning/patches/{patch_id}/reject", response_model=dict[str, object])
async def reject_patch(
    patch_id: str,
    request: Request,
    response: Response,
    payload: PatchActionRequest | None = None,
) -> dict[str, object]:
    """Reject a learning patch through the Runtime Center governed surface."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_learning_service(request)
    actor = payload.actor if payload is not None else "system"
    rejecter = getattr(service, "reject_patch", None)
    if not callable(rejecter):
        raise HTTPException(503, detail="Learning patch rejections are not available")
    try:
        patch = rejecter(patch_id, rejected_by=actor)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    patch_payload = _serialize_learning_object(patch)
    if patch_payload is None:
        raise HTTPException(500, detail="Learning patch payload is not serializable")
    return patch_payload


@router.post("/learning/patches/{patch_id}/apply", response_model=dict[str, object])
async def apply_patch(
    patch_id: str,
    request: Request,
    response: Response,
    payload: PatchActionRequest | None = None,
) -> dict[str, object]:
    """Request governed application of a previously approved patch."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    actor = payload.actor if payload is not None else "system"
    return await _govern_patch_mutation(
        request=request,
        patch_id=patch_id,
        actor=actor,
        capability_ref="system:apply_patch",
        title=f"Apply patch '{patch_id}'",
        response_key="applied",
        allowed_statuses={"approved"},
        invalid_detail=f"Patch '{patch_id}' must be approved before applying.",
    )


@router.post("/learning/patches/{patch_id}/rollback", response_model=dict[str, object])
async def rollback_patch(
    patch_id: str,
    request: Request,
    response: Response,
    payload: PatchActionRequest | None = None,
) -> dict[str, object]:
    """Request governed rollback of an already applied patch."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    actor = payload.actor if payload is not None else "system"
    return await _govern_patch_mutation(
        request=request,
        patch_id=patch_id,
        actor=actor,
        capability_ref="system:rollback_patch",
        title=f"Rollback patch '{patch_id}'",
        response_key="rolled_back",
        allowed_statuses={"applied"},
        invalid_detail=f"Patch '{patch_id}' must be applied before rollback.",
    )


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
        except Exception as exc:  # pragma: no cover
            _raise_dispatcher_error(exc)
        response_payload = result.model_dump(mode="json")
        resolved_decision_id = (
            str(getattr(result, "decision_request_id", "") or "").strip()
            or pending_decision.id
        )
        if _schedule_query_tool_confirmation_resume(request, decision_id=resolved_decision_id):
            response_payload["resume_scheduled"] = True
            response_payload["resume_kind"] = "query-tool-confirmation"
        return response_payload

    try:
        result = await dispatcher.confirm_and_execute(task_id)
    except Exception as exc:  # pragma: no cover
        _raise_dispatcher_error(exc)
    return result.model_dump(mode="json")
