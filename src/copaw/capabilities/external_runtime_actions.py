# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import CapabilityMount


class _RuntimeActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    owner_agent_id: str | None = None
    session_mount_id: str | None = None
    work_context_id: str | None = None
    environment_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunExternalRuntimePayload(_RuntimeActionBase):
    action: Literal["run"] = "run"
    args: list[str] = Field(default_factory=list)
    timeout_sec: int | None = None


class StartExternalRuntimePayload(_RuntimeActionBase):
    action: Literal["start"] = "start"
    args: list[str] = Field(default_factory=list)
    retention_policy: str | None = None
    port_override: int | None = None
    health_path_override: str | None = None


class ExistingRuntimeActionPayload(_RuntimeActionBase):
    runtime_id: str


class HealthcheckExternalRuntimePayload(ExistingRuntimeActionPayload):
    action: Literal["healthcheck"] = "healthcheck"


class StopExternalRuntimePayload(ExistingRuntimeActionPayload):
    action: Literal["stop"] = "stop"


class RestartExternalRuntimePayload(ExistingRuntimeActionPayload):
    action: Literal["restart"] = "restart"
    args: list[str] = Field(default_factory=list)
    retention_policy: str | None = None
    port_override: int | None = None
    health_path_override: str | None = None


def _runtime_contract(mount: CapabilityMount | None) -> dict[str, Any]:
    metadata = dict(getattr(mount, "metadata", {}) or {})
    contract = metadata.get("runtime_contract")
    return dict(contract) if isinstance(contract, dict) else {}


def _supported_actions(contract: dict[str, Any]) -> list[str]:
    items = contract.get("supported_actions")
    if not isinstance(items, list):
        return []
    return [str(item).strip().lower() for item in items if str(item).strip()]


def parse_external_runtime_action_payload(
    *,
    mount: CapabilityMount,
    action: str,
    payload: dict[str, object] | None,
) -> tuple[BaseModel | None, str | None]:
    contract = _runtime_contract(mount)
    runtime_kind = str(contract.get("runtime_kind") or "").strip().lower()
    if runtime_kind not in {"cli", "service"}:
        return None, "External capability is missing a formal runtime contract."
    resolved_action = str(action or "").strip().lower() or "describe"
    supported_actions = _supported_actions(contract)
    if resolved_action != "describe" and resolved_action not in supported_actions:
        return (
            None,
            (
                f"External capability '{mount.id}' does not support action '{resolved_action}'. "
                f"Supported actions: {supported_actions or ['describe']}."
            ),
        )
    if resolved_action == "describe":
        return None, None
    raw_payload = dict(payload or {})
    raw_payload["action"] = resolved_action
    model_type: type[BaseModel] | None = None
    if runtime_kind == "cli" and resolved_action == "run":
        model_type = RunExternalRuntimePayload
    elif runtime_kind == "service" and resolved_action == "start":
        model_type = StartExternalRuntimePayload
    elif runtime_kind == "service" and resolved_action == "healthcheck":
        model_type = HealthcheckExternalRuntimePayload
    elif runtime_kind == "service" and resolved_action == "stop":
        model_type = StopExternalRuntimePayload
    elif runtime_kind == "service" and resolved_action == "restart":
        model_type = RestartExternalRuntimePayload
    else:
        return (
            None,
            f"External capability '{mount.id}' does not support typed action '{resolved_action}'.",
        )
    try:
        return model_type.model_validate(raw_payload), None
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field_name = ".".join(str(item) for item in first_error.get("loc") or [])
        message = first_error.get("msg", "invalid payload")
        if field_name:
            message = f"{field_name}: {message}"
        return (
            None,
            f"External capability '{mount.id}' requires a typed runtime action payload: {message}",
        )
