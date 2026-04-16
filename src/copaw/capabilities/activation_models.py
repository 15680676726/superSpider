# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

ACTIVATION_STATUSES = (
    "installed",
    "activating",
    "ready",
    "healing",
    "waiting_human",
    "blocked",
)
ACTIVATION_REASONS = (
    "dependency_missing",
    "adapter_offline",
    "session_unbound",
    "host_unavailable",
    "token_expired",
    "scope_unbound",
    "runtime_unavailable",
    "policy_retryable_block",
    "human_auth_required",
    "captcha_required",
    "two_factor_required",
    "explicit_human_confirm_required",
    "host_open_required",
    "policy_blocked",
    "unsupported_host",
    "invalid_capability_contract",
    "broken_installation",
)

ActivationStatus = Literal[
    "installed",
    "activating",
    "ready",
    "healing",
    "waiting_human",
    "blocked",
]
ActivationReason = Literal[
    "dependency_missing",
    "adapter_offline",
    "session_unbound",
    "host_unavailable",
    "token_expired",
    "scope_unbound",
    "runtime_unavailable",
    "policy_retryable_block",
    "human_auth_required",
    "captcha_required",
    "two_factor_required",
    "explicit_human_confirm_required",
    "host_open_required",
    "policy_blocked",
    "unsupported_host",
    "invalid_capability_contract",
    "broken_installation",
]
ActivationClass = Literal[
    "stateless",
    "auth-bound",
    "host-attached",
    "workspace-bound",
]


def normalize_activation_reason(value: str | None) -> ActivationReason | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in ACTIVATION_REASONS:
        raise ValueError(f"Unsupported activation reason '{value}'")
    return cast(ActivationReason, normalized)


def normalize_activation_status(value: str | None) -> ActivationStatus:
    normalized = str(value or "").strip().lower()
    if normalized not in ACTIVATION_STATUSES:
        raise ValueError(f"Unsupported activation status '{value}'")
    return cast(ActivationStatus, normalized)


class ActivationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject_id: str
    activation_class: ActivationClass
    allow_heal: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActivationState(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: ActivationStatus
    reason: ActivationReason | None = None
    summary: str = ""
    required_action: str | None = None
    auto_heal_supported: bool = False
    retryable: bool | None = None
    environment_id: str | None = None
    session_mount_id: str | None = None
    scope_ref: str | None = None
    runtime: dict[str, Any] = Field(default_factory=dict)
    support: dict[str, Any] = Field(default_factory=dict)
    operations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class ActivationResult(ActivationState):
    subject_id: str
    activation_class: ActivationClass
    auto_heal_attempted: bool = False
