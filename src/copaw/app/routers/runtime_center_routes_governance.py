# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import HTTPException, Request, Response

from ..runtime_center import apply_runtime_center_surface_headers
from .runtime_center_actor_capabilities import (
    _get_decision_payload,
    _schedule_query_tool_confirmation_resume,
)
from .runtime_center_dependencies import (
    _get_kernel_dispatcher,
    _get_learning_service,
    _get_state_query_service,
)
from .runtime_center_mutation_helpers import (
    _call_runtime_query_method,
    _raise_dispatcher_error,
)
from .runtime_center_request_models import (
    DecisionApproveRequest,
    DecisionRejectRequest,
)
from .runtime_center_shared import router


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
        decision_payload = (
            _get_decision_payload(request, resolved_decision_id)
            or (
                decision_repository.get_decision_request(resolved_decision_id).model_dump(mode="json")
                if decision_repository is not None
                and decision_repository.get_decision_request(resolved_decision_id) is not None
                else None
            )
        )
        return {
            "decision_request_id": resolved_decision_id,
            "decision": decision_payload,
            "proposal": finalized.get("proposal"),
            "plan": finalized.get("plan"),
            "onboarding_run": finalized.get("onboarding_run"),
            "kernel_result": finalized.get("kernel_result") or response_payload,
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
            "decision": _get_decision_payload(request, resolved_decision_id),
            "proposal": finalized.get("proposal"),
            "kernel_result": finalized.get("kernel_result") or response_payload,
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
