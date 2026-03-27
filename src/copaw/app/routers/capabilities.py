# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...capabilities import CapabilityMount, CapabilitySummary
from .governed_mutations import dispatch_governed_mutation, get_capability_service

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


class CapabilityMutationRequest(BaseModel):
    actor: str = Field(default="copaw-operator")


def _get_capability_service(request: Request):
    return get_capability_service(request)


@router.get("", response_model=list[CapabilityMount])
async def list_capabilities(
    request: Request,
    kind: str | None = Query(default=None),
    enabled_only: bool = Query(default=False),
) -> list[CapabilityMount]:
    service = _get_capability_service(request)
    return service.list_public_capabilities(kind=kind, enabled_only=enabled_only)


@router.get("/summary", response_model=CapabilitySummary)
async def get_capability_summary(request: Request) -> CapabilitySummary:
    service = _get_capability_service(request)
    return service.summarize_public()


@router.patch("/{capability_id:path}/toggle", response_model=dict[str, object])
async def toggle_capability(
    request: Request,
    capability_id: str,
    payload: CapabilityMutationRequest | None = None,
) -> dict[str, object]:
    service = _get_capability_service(request)
    mount = service.get_public_capability(capability_id)
    if mount is None:
        raise HTTPException(404, detail=f"Capability '{capability_id}' not found")

    desired_enabled = not mount.enabled
    result = await dispatch_governed_mutation(
        request,
        capability_ref="system:set_capability_enabled",
        title=f"Set capability {capability_id} enabled={desired_enabled}",
        environment_ref="config:capabilities",
        fallback_risk="guarded",
        payload={
            "capability_id": capability_id,
            "enabled": desired_enabled,
            "actor": payload.actor if payload is not None else "copaw-operator",
        },
    )
    if result.get("success"):
        result.update(
            {
                "toggled": True,
                "id": capability_id,
                "enabled": desired_enabled,
            },
        )
    return result


@router.delete("/{capability_id:path}", response_model=dict[str, object])
async def delete_capability(
    request: Request,
    capability_id: str,
    payload: CapabilityMutationRequest | None = None,
) -> dict[str, object]:
    service = _get_capability_service(request)
    mount = service.get_public_capability(capability_id)
    if mount is None:
        raise HTTPException(404, detail=f"Capability '{capability_id}' not found")

    result = await dispatch_governed_mutation(
        request,
        capability_ref="system:delete_capability",
        title=f"Delete capability {capability_id}",
        environment_ref="config:capabilities",
        fallback_risk="confirm",
        payload={
            "capability_id": capability_id,
            "actor": payload.actor if payload is not None else "copaw-operator",
        },
    )
    if result.get("success"):
        result.update(
            {
                "deleted": True,
                "id": capability_id,
            },
        )
    return result


@router.get("/{capability_id:path}", response_model=CapabilityMount)
async def get_capability(
    request: Request,
    capability_id: str,
) -> CapabilityMount:
    service = _get_capability_service(request)
    mount = service.get_public_capability(capability_id)
    if mount is None:
        raise HTTPException(404, detail=f"Capability '{capability_id}' not found")
    return mount
