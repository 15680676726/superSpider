# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..kernel.models import KernelTask
from .models import CapabilityMount


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object | None) -> list[str]:
    if not isinstance(value, list):
        return []
    resolved: list[str] = []
    for item in value:
        text = _string(item)
        if text is None or text in resolved:
            continue
        resolved.append(text)
    return resolved


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _response_output(response: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(response.get("output"))


def _response_success(response: Mapping[str, Any]) -> bool:
    if isinstance(response.get("success"), bool):
        return bool(response.get("success"))
    output = _response_output(response)
    if isinstance(output.get("success"), bool):
        return bool(output.get("success"))
    outcome = (_string(output.get("outcome")) or "").lower()
    status = (_string(output.get("status")) or "").lower()
    return outcome in {"success", "succeeded"} or status in {"ready", "stopped"}


def _response_summary(response: Mapping[str, Any]) -> str:
    return _string(response.get("summary")) or _string(response.get("error")) or ""


def _response_evidence_id(response: Mapping[str, Any]) -> str | None:
    return _string(response.get("evidence_id"))


def _response_provider_resolution_status(
    response: Mapping[str, Any],
    *,
    fallback: str,
) -> str:
    output = _response_output(response)
    provider_injection = _mapping(output.get("provider_injection"))
    return (
        _string(response.get("provider_resolution_status"))
        or _string(output.get("provider_resolution_status"))
        or _string(provider_injection.get("provider_resolution_status"))
        or fallback
    )


def _response_runtime_id(response: Mapping[str, Any]) -> str | None:
    output = _response_output(response)
    evidence_metadata = _mapping(response.get("evidence_metadata"))
    output_evidence_metadata = _mapping(output.get("evidence_metadata"))
    return (
        _string(response.get("runtime_id"))
        or _string(output.get("runtime_id"))
        or _string(evidence_metadata.get("runtime_id"))
        or _string(output_evidence_metadata.get("runtime_id"))
    )


def _runtime_supported_actions(mount: CapabilityMount) -> list[str]:
    metadata = _mapping(getattr(mount, "metadata", None))
    runtime_contract = _mapping(metadata.get("runtime_contract"))
    return [item.lower() for item in _string_list(runtime_contract.get("supported_actions"))]


def _adapter_actions(mount: CapabilityMount) -> list[dict[str, Any]]:
    metadata = _mapping(getattr(mount, "metadata", None))
    adapter_contract = _mapping(metadata.get("adapter_contract"))
    actions = adapter_contract.get("actions")
    if not isinstance(actions, list):
        return []
    resolved: list[dict[str, Any]] = []
    for item in actions:
        if isinstance(item, Mapping):
            resolved.append(dict(item))
    return resolved


def _pick_adapter_probe_action_id(actions: list[dict[str, Any]]) -> str | None:
    action_ids = [
        _string(item.get("action_id"))
        for item in actions
        if _string(item.get("action_id")) is not None
    ]
    preferred = ("status", "healthcheck", "ping", "execute_task", "run")
    for candidate in preferred:
        if candidate in action_ids:
            return candidate
    return action_ids[0] if action_ids else None


class DonorProbeService:
    def __init__(self, *, capability_service: object) -> None:
        self._capability_service = capability_service

    async def probe_capability(
        self,
        *,
        capability_id: str,
        owner_agent_id: str,
        session_mount_id: str | None = None,
        work_context_id: str | None = None,
        environment_ref: str | None = None,
        verified_stage: str | None = None,
        provider_resolution_status: str | None = None,
        compatibility_status: str | None = None,
    ) -> dict[str, Any]:
        mount = self._get_capability(capability_id)
        fallback_verified_stage = _string(verified_stage) or _string(
            _mapping(getattr(mount, "metadata", None)).get("verified_stage"),
        ) or "installed"
        fallback_provider_resolution_status = _string(
            provider_resolution_status,
        ) or _string(_mapping(getattr(mount, "metadata", None)).get("provider_resolution_status")) or "pending"
        fallback_compatibility_status = _string(
            compatibility_status,
        ) or _string(_mapping(getattr(mount, "metadata", None)).get("compatibility_status")) or "unknown"
        if mount is None:
            return {
                "attempted": False,
                "success": False,
                "summary": f"Capability '{capability_id}' is not available for probe.",
                "verified_stage": fallback_verified_stage,
                "provider_resolution_status": fallback_provider_resolution_status,
                "compatibility_status": fallback_compatibility_status,
                "probe_outcome": "not_attempted",
                "probe_error_type": "capability_not_found",
                "probe_evidence_refs": [],
                "probe_runtime_id": None,
                "selected_adapter_action_id": None,
            }
        if mount.kind == "runtime-component":
            return await self._probe_runtime_component(
                mount=mount,
                owner_agent_id=owner_agent_id,
                session_mount_id=session_mount_id,
                work_context_id=work_context_id,
                environment_ref=environment_ref,
                verified_stage=fallback_verified_stage,
                provider_resolution_status=fallback_provider_resolution_status,
                compatibility_status=fallback_compatibility_status,
            )
        if mount.kind == "adapter":
            return await self._probe_adapter(
                mount=mount,
                owner_agent_id=owner_agent_id,
                session_mount_id=session_mount_id,
                work_context_id=work_context_id,
                environment_ref=environment_ref,
                verified_stage=fallback_verified_stage,
                provider_resolution_status=fallback_provider_resolution_status,
                compatibility_status=fallback_compatibility_status,
            )
        return {
            "attempted": False,
            "success": False,
            "summary": f"Capability '{mount.id}' has no formal probe path.",
            "verified_stage": fallback_verified_stage,
            "provider_resolution_status": fallback_provider_resolution_status,
            "compatibility_status": fallback_compatibility_status,
            "probe_outcome": "not_attempted",
            "probe_error_type": None,
            "probe_evidence_refs": [],
            "probe_runtime_id": None,
            "selected_adapter_action_id": None,
        }

    def _get_capability(self, capability_id: str) -> CapabilityMount | None:
        getter = getattr(self._capability_service, "get_capability", None)
        if not callable(getter):
            return None
        mount = getter(capability_id)
        return mount if isinstance(mount, CapabilityMount) else None

    async def _execute_task(
        self,
        *,
        capability_id: str,
        owner_agent_id: str,
        title: str,
        risk_level: str,
        session_mount_id: str | None,
        work_context_id: str | None,
        environment_ref: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        executor = getattr(self._capability_service, "execute_task", None)
        if not callable(executor):
            return {
                "success": False,
                "summary": "Capability service does not support probe execution.",
                "error_type": "capability_service_missing_execute_task",
            }
        task = KernelTask(
            title=title,
            capability_ref=capability_id,
            owner_agent_id=owner_agent_id,
            work_context_id=work_context_id,
            environment_ref=environment_ref,
            risk_level=risk_level if risk_level in {"auto", "guarded", "confirm"} else "guarded",
            payload={
                **payload,
                "owner_agent_id": owner_agent_id,
                "session_mount_id": session_mount_id,
                "work_context_id": work_context_id,
                "environment_ref": environment_ref,
            },
        )
        result = await executor(task)
        return dict(result) if isinstance(result, Mapping) else {}

    async def _probe_runtime_component(
        self,
        *,
        mount: CapabilityMount,
        owner_agent_id: str,
        session_mount_id: str | None,
        work_context_id: str | None,
        environment_ref: str | None,
        verified_stage: str,
        provider_resolution_status: str,
        compatibility_status: str,
    ) -> dict[str, Any]:
        supported_actions = _runtime_supported_actions(mount)
        if "start" not in supported_actions or "stop" not in supported_actions:
            return {
                "attempted": False,
                "success": False,
                "summary": f"Runtime capability '{mount.id}' does not expose the formal start/stop probe contract.",
                "verified_stage": verified_stage,
                "provider_resolution_status": provider_resolution_status,
                "compatibility_status": compatibility_status,
                "probe_outcome": "not_attempted",
                "probe_error_type": None,
                "probe_evidence_refs": [],
                "probe_runtime_id": None,
                "selected_adapter_action_id": None,
            }
        evidence_refs: list[str] = []
        start_response = await self._execute_task(
            capability_id=mount.id,
            owner_agent_id=owner_agent_id,
            title=f"Probe runtime capability {mount.id}",
            risk_level=mount.risk_level,
            session_mount_id=session_mount_id,
            work_context_id=work_context_id,
            environment_ref=environment_ref,
            payload={"action": "start"},
        )
        start_evidence_id = _response_evidence_id(start_response)
        if start_evidence_id is not None:
            evidence_refs.append(start_evidence_id)
        resolved_provider_status = _response_provider_resolution_status(
            start_response,
            fallback=provider_resolution_status,
        )
        runtime_id = _response_runtime_id(start_response)
        if not _response_success(start_response):
            return {
                "attempted": True,
                "success": False,
                "summary": _response_summary(start_response) or f"Runtime probe failed for '{mount.id}'.",
                "verified_stage": verified_stage,
                "provider_resolution_status": resolved_provider_status,
                "compatibility_status": compatibility_status,
                "probe_outcome": "failed",
                "probe_error_type": _string(start_response.get("error_type")),
                "probe_evidence_refs": evidence_refs,
                "probe_runtime_id": runtime_id,
                "selected_adapter_action_id": None,
            }
        stop_payload: dict[str, Any] = {"action": "stop"}
        if runtime_id is not None:
            stop_payload["runtime_id"] = runtime_id
        stop_response = await self._execute_task(
            capability_id=mount.id,
            owner_agent_id=owner_agent_id,
            title=f"Finalize runtime probe {mount.id}",
            risk_level=mount.risk_level,
            session_mount_id=session_mount_id,
            work_context_id=work_context_id,
            environment_ref=environment_ref,
            payload=stop_payload,
        )
        stop_evidence_id = _response_evidence_id(stop_response)
        if stop_evidence_id is not None:
            evidence_refs.append(stop_evidence_id)
        if not _response_success(stop_response):
            return {
                "attempted": True,
                "success": False,
                "summary": _response_summary(stop_response) or f"Runtime stop probe failed for '{mount.id}'.",
                "verified_stage": verified_stage,
                "provider_resolution_status": resolved_provider_status,
                "compatibility_status": compatibility_status,
                "probe_outcome": "failed",
                "probe_error_type": _string(stop_response.get("error_type")),
                "probe_evidence_refs": evidence_refs,
                "probe_runtime_id": runtime_id,
                "selected_adapter_action_id": None,
            }
        return {
            "attempted": True,
            "success": True,
            "summary": f"Runtime capability '{mount.id}' passed formal operability probe.",
            "verified_stage": "runtime_operable",
            "provider_resolution_status": resolved_provider_status,
            "compatibility_status": compatibility_status,
            "probe_outcome": "runtime_operable",
            "probe_error_type": None,
            "probe_evidence_refs": evidence_refs,
            "probe_runtime_id": runtime_id,
            "selected_adapter_action_id": None,
        }

    async def _probe_adapter(
        self,
        *,
        mount: CapabilityMount,
        owner_agent_id: str,
        session_mount_id: str | None,
        work_context_id: str | None,
        environment_ref: str | None,
        verified_stage: str,
        provider_resolution_status: str,
        compatibility_status: str,
    ) -> dict[str, Any]:
        actions = _adapter_actions(mount)
        selected_action_id = _pick_adapter_probe_action_id(actions)
        if selected_action_id is None:
            return {
                "attempted": False,
                "success": False,
                "summary": f"Adapter capability '{mount.id}' exposes no formal actions for probe.",
                "verified_stage": verified_stage,
                "provider_resolution_status": provider_resolution_status,
                "compatibility_status": compatibility_status,
                "probe_outcome": "not_attempted",
                "probe_error_type": None,
                "probe_evidence_refs": [],
                "probe_runtime_id": None,
                "selected_adapter_action_id": None,
            }
        response = await self._execute_task(
            capability_id=mount.id,
            owner_agent_id=owner_agent_id,
            title=f"Probe adapter capability {mount.id}:{selected_action_id}",
            risk_level=mount.risk_level,
            session_mount_id=session_mount_id,
            work_context_id=work_context_id,
            environment_ref=environment_ref,
            payload={"action": selected_action_id},
        )
        evidence_refs: list[str] = []
        evidence_id = _response_evidence_id(response)
        if evidence_id is not None:
            evidence_refs.append(evidence_id)
        resolved_provider_status = _response_provider_resolution_status(
            response,
            fallback=provider_resolution_status,
        )
        if not _response_success(response):
            return {
                "attempted": True,
                "success": False,
                "summary": _response_summary(response) or f"Adapter probe failed for '{mount.id}'.",
                "verified_stage": verified_stage,
                "provider_resolution_status": resolved_provider_status,
                "compatibility_status": compatibility_status,
                "probe_outcome": "failed",
                "probe_error_type": _string(response.get("error_type")),
                "probe_evidence_refs": evidence_refs,
                "probe_runtime_id": None,
                "selected_adapter_action_id": selected_action_id,
            }
        verified_result_stage = (
            "primary_action_verified"
            if len(actions) == 1
            else "adapter_probe_passed"
        )
        return {
            "attempted": True,
            "success": True,
            "summary": f"Adapter capability '{mount.id}' passed formal probe via '{selected_action_id}'.",
            "verified_stage": verified_result_stage,
            "provider_resolution_status": resolved_provider_status,
            "compatibility_status": compatibility_status,
            "probe_outcome": "succeeded",
            "probe_error_type": None,
            "probe_evidence_refs": evidence_refs,
            "probe_runtime_id": None,
            "selected_adapter_action_id": selected_action_id,
        }


__all__ = ["DonorProbeService"]
