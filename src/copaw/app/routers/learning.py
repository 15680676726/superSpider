# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...learning import LearningService

router = APIRouter(prefix="/learning", tags=["learning"])


class ProposalCreateRequest(BaseModel):
    title: str
    description: str
    source_agent_id: str = "copaw-agent-runner"
    goal_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    target_layer: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class PatchCreateRequest(BaseModel):
    kind: str
    title: str
    description: str
    goal_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    workflow_template_id: str | None = None
    workflow_run_id: str | None = None
    workflow_step_id: str | None = None
    diff_summary: str = ""
    patch_payload: dict[str, object] = Field(default_factory=dict)
    proposal_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    source_evidence_id: str | None = None
    risk_level: str = "auto"
    auto_apply: bool = False


class PatchActionRequest(BaseModel):
    actor: str = "system"


class LearningAutomationRequest(BaseModel):
    actor: str = "copaw-main-brain"
    limit: int | None = None


class LearningStrategyRequest(BaseModel):
    actor: str = "copaw-main-brain"
    limit: int | None = None
    auto_apply: bool = True
    auto_rollback: bool = False
    failure_threshold: int = 2
    confirm_threshold: int = 6
    max_proposals: int = 5


class IndustryAcquisitionRunRequest(BaseModel):
    industry_instance_id: str
    actor: str = "copaw-main-brain"
    rerun_existing: bool = False


def _get_learning_service(request: Request) -> LearningService:
    service = getattr(request.app.state, "learning_service", None)
    if isinstance(service, LearningService):
        return service
    raise HTTPException(503, detail="Learning service is not available")


LearningServiceDep = Annotated[LearningService, Depends(_get_learning_service)]


def _model_dump_or_dict(value: object | None) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
        return payload if isinstance(payload, dict) else None
    return None


@router.get("/proposals", response_model=list[dict[str, object]])
async def list_proposals(
    service: LearningServiceDep,
    status: str | None = Query(default=None),
) -> list[dict[str, object]]:
    proposals = service.list_proposals(status=status)
    return [p.model_dump(mode="json") for p in proposals]


@router.post("/proposals", response_model=dict[str, object])
async def create_proposal(
    service: LearningServiceDep,
    payload: ProposalCreateRequest,
) -> dict[str, object]:
    proposal = service.create_proposal(
        title=payload.title,
        description=payload.description,
        source_agent_id=payload.source_agent_id,
        goal_id=payload.goal_id,
        task_id=payload.task_id,
        agent_id=payload.agent_id,
        target_layer=payload.target_layer,
        evidence_refs=payload.evidence_refs,
    )
    return proposal.model_dump(mode="json")


@router.post("/proposals/{proposal_id}/accept", response_model=dict[str, object])
async def accept_proposal(
    service: LearningServiceDep,
    proposal_id: str,
) -> dict[str, object]:
    try:
        proposal = service.accept_proposal(proposal_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    return proposal.model_dump(mode="json")


@router.post("/proposals/{proposal_id}/reject", response_model=dict[str, object])
async def reject_proposal(
    service: LearningServiceDep,
    proposal_id: str,
) -> dict[str, object]:
    try:
        proposal = service.reject_proposal(proposal_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    return proposal.model_dump(mode="json")


@router.get("/acquisition/proposals", response_model=list[dict[str, object]])
async def list_acquisition_proposals(
    service: LearningServiceDep,
    industry_instance_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    target_agent_id: str | None = Query(default=None),
    target_role_id: str | None = Query(default=None),
    acquisition_kind: str | None = Query(default=None),
) -> list[dict[str, object]]:
    proposals = service.list_acquisition_proposals(
        industry_instance_id=industry_instance_id,
        status=status,
        target_agent_id=target_agent_id,
        target_role_id=target_role_id,
        acquisition_kind=acquisition_kind,
        limit=None,
    )
    return [item.model_dump(mode="json") for item in proposals]


@router.get("/acquisition/proposals/{proposal_id}", response_model=dict[str, object])
async def get_acquisition_proposal(
    service: LearningServiceDep,
    proposal_id: str,
) -> dict[str, object]:
    try:
        proposal = service.get_acquisition_proposal(proposal_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    return proposal.model_dump(mode="json")


@router.post("/acquisition/proposals/{proposal_id}/approve", response_model=dict[str, object])
async def approve_acquisition_proposal(
    service: LearningServiceDep,
    proposal_id: str,
    payload: PatchActionRequest,
) -> dict[str, object]:
    try:
        proposal = service.get_acquisition_proposal(proposal_id)
        dispatcher = getattr(service, "_kernel_dispatcher", None)
        kernel_result_payload: dict[str, object] | None = None
        if (
            dispatcher is not None
            and proposal.status == "open"
            and proposal.decision_request_id is not None
        ):
            kernel_result = await dispatcher.approve_decision(
                proposal.decision_request_id,
                resolution=f"Approved by {payload.actor}.",
            )
            result = await service.finalize_resolved_decision(
                proposal.decision_request_id,
                status="approved",
                actor=payload.actor,
            )
            kernel_result_payload = (
                _model_dump_or_dict(result.get("kernel_result"))
                or kernel_result.model_dump(mode="json")
            )
        else:
            result = await service.approve_acquisition_proposal(
                proposal_id,
                approved_by=payload.actor,
            )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return {
        "proposal": result["proposal"].model_dump(mode="json"),
        "plan": (
            result["plan"].model_dump(mode="json")
            if result.get("plan") is not None
            else None
        ),
        "onboarding_run": (
            result["onboarding_run"].model_dump(mode="json")
            if result.get("onboarding_run") is not None
            else None
        ),
        "decision_request": (
            result["decision_request"].model_dump(mode="json")
            if result.get("decision_request") is not None
            else None
        ),
        "kernel_result": kernel_result_payload,
    }


@router.post("/acquisition/proposals/{proposal_id}/reject", response_model=dict[str, object])
async def reject_acquisition_proposal(
    service: LearningServiceDep,
    proposal_id: str,
    payload: PatchActionRequest,
) -> dict[str, object]:
    try:
        proposal = service.get_acquisition_proposal(proposal_id)
        dispatcher = getattr(service, "_kernel_dispatcher", None)
        kernel_result_payload: dict[str, object] | None = None
        if (
            dispatcher is not None
            and proposal.status == "open"
            and proposal.decision_request_id is not None
        ):
            kernel_result = dispatcher.reject_decision(
                proposal.decision_request_id,
                resolution=f"Rejected by {payload.actor}.",
            )
            result = await service.finalize_resolved_decision(
                proposal.decision_request_id,
                status="rejected",
                actor=payload.actor,
            )
            kernel_result_payload = (
                _model_dump_or_dict(result.get("kernel_result"))
                or kernel_result.model_dump(mode="json")
            )
        else:
            result = service.reject_acquisition_proposal(
                proposal_id,
                rejected_by=payload.actor,
            )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return {
        "proposal": result["proposal"].model_dump(mode="json"),
        "decision_request": (
            result["decision_request"].model_dump(mode="json")
            if result.get("decision_request") is not None
            else None
        ),
        "kernel_result": kernel_result_payload,
    }


@router.get("/acquisition/plans", response_model=list[dict[str, object]])
async def list_install_binding_plans(
    service: LearningServiceDep,
    industry_instance_id: str | None = Query(default=None),
    proposal_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    target_agent_id: str | None = Query(default=None),
    target_role_id: str | None = Query(default=None),
) -> list[dict[str, object]]:
    plans = service.list_install_binding_plans(
        industry_instance_id=industry_instance_id,
        proposal_id=proposal_id,
        status=status,
        target_agent_id=target_agent_id,
        target_role_id=target_role_id,
        limit=None,
    )
    return [item.model_dump(mode="json") for item in plans]


@router.get("/acquisition/plans/{plan_id}", response_model=dict[str, object])
async def get_install_binding_plan(
    service: LearningServiceDep,
    plan_id: str,
) -> dict[str, object]:
    try:
        plan = service.get_install_binding_plan(plan_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    return plan.model_dump(mode="json")


@router.get("/acquisition/onboarding-runs", response_model=list[dict[str, object]])
async def list_onboarding_runs(
    service: LearningServiceDep,
    industry_instance_id: str | None = Query(default=None),
    proposal_id: str | None = Query(default=None),
    plan_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    target_agent_id: str | None = Query(default=None),
    target_role_id: str | None = Query(default=None),
) -> list[dict[str, object]]:
    runs = service.list_onboarding_runs(
        industry_instance_id=industry_instance_id,
        proposal_id=proposal_id,
        plan_id=plan_id,
        status=status,
        target_agent_id=target_agent_id,
        target_role_id=target_role_id,
        limit=None,
    )
    return [item.model_dump(mode="json") for item in runs]


@router.get("/acquisition/onboarding-runs/{run_id}", response_model=dict[str, object])
async def get_onboarding_run(
    service: LearningServiceDep,
    run_id: str,
) -> dict[str, object]:
    try:
        run = service.get_onboarding_run(run_id)
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    return run.model_dump(mode="json")


@router.post("/acquisition/run", response_model=dict[str, object])
async def run_industry_acquisition_cycle(
    service: LearningServiceDep,
    payload: IndustryAcquisitionRunRequest,
) -> dict[str, object]:
    return await service.run_industry_acquisition_cycle(
        industry_instance_id=payload.industry_instance_id,
        actor=payload.actor,
        rerun_existing=payload.rerun_existing,
    )


@router.get("/patches", response_model=list[dict[str, object]])
async def list_patches(
    service: LearningServiceDep,
    status: str | None = Query(default=None),
    goal_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
) -> list[dict[str, object]]:
    patches = service.list_patches(
        status=status,
        goal_id=goal_id,
        task_id=task_id,
        agent_id=agent_id,
    )
    return [p.model_dump(mode="json") for p in patches]


@router.post("/patches", response_model=dict[str, object])
async def create_patch(
    service: LearningServiceDep,
    payload: PatchCreateRequest,
) -> dict[str, object]:
    result = service.create_patch(
        kind=payload.kind,
        title=payload.title,
        description=payload.description,
        goal_id=payload.goal_id,
        task_id=payload.task_id,
        agent_id=payload.agent_id,
        workflow_template_id=payload.workflow_template_id,
        workflow_run_id=payload.workflow_run_id,
        workflow_step_id=payload.workflow_step_id,
        diff_summary=payload.diff_summary,
        patch_payload=payload.patch_payload,
        proposal_id=payload.proposal_id,
        evidence_refs=payload.evidence_refs,
        source_evidence_id=payload.source_evidence_id,
        risk_level=payload.risk_level,
        auto_apply=payload.auto_apply,
    )
    patch = result.get("patch")
    decision = result.get("decision_request")
    applied_patch = result.get("applied_patch")
    return {
        "patch": patch.model_dump(mode="json") if patch else None,
        "decision_request": (
            decision.model_dump(mode="json") if decision else None
        ),
        "auto_applied": bool(result.get("auto_applied")),
        "applied_patch": (
            applied_patch.model_dump(mode="json") if applied_patch else None
        ),
    }


@router.post("/automation/auto-apply", response_model=dict[str, object])
async def auto_apply_patches(
    service: LearningServiceDep,
    payload: LearningAutomationRequest,
) -> dict[str, object]:
    return service.auto_apply_low_risk_patches(
        limit=payload.limit,
        actor=payload.actor,
    )


@router.post("/automation/strategy", response_model=dict[str, object])
async def run_strategy_cycle(
    service: LearningServiceDep,
    payload: LearningStrategyRequest,
) -> dict[str, object]:
    return service.run_strategy_cycle(
        actor=payload.actor,
        limit=payload.limit,
        auto_apply=payload.auto_apply,
        auto_rollback=payload.auto_rollback,
        failure_threshold=payload.failure_threshold,
        confirm_threshold=payload.confirm_threshold,
        max_proposals=payload.max_proposals,
    )


@router.get("/growth", response_model=list[dict[str, object]])
async def list_growth(
    service: LearningServiceDep,
    agent_id: str | None = Query(default=None),
    goal_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    source_patch_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, object]]:
    events = service.list_growth(
        agent_id=agent_id,
        goal_id=goal_id,
        task_id=task_id,
        source_patch_id=source_patch_id,
        limit=limit,
    )
    return [e.model_dump(mode="json") for e in events]
