# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from ..environments.models import SessionMount
from .main_brain_execution_planner import MainBrainExecutionPlan

_LIVE_ENVIRONMENT_KINDS = {"desktop", "browser", "resource-slot", "session"}


def _non_empty_str(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


def _resolve_request_environment_ref(request: Any) -> str | None:
    return (
        _non_empty_str(getattr(request, "environment_ref", None))
        or _non_empty_str(getattr(request, "active_environment_id", None))
        or _non_empty_str(getattr(request, "current_environment_id", None))
    )


def _resolve_environment_session_id(request: Any) -> str | None:
    return (
        _non_empty_str(getattr(request, "environment_session_id", None))
        or _non_empty_str(getattr(request, "active_environment_session_id", None))
        or _non_empty_str(getattr(request, "current_environment_session_id", None))
    )


def _resolve_request_continuity_token(request: Any) -> str | None:
    return (
        _non_empty_str(getattr(request, "continuity_token", None))
        or _non_empty_str(getattr(request, "environment_continuity_token", None))
    )

def _classify_environment_kind(environment_ref: str | None) -> str:
    normalized = _non_empty_str(environment_ref)
    if normalized is None:
        return "none"
    prefix = normalized.split(":", 1)[0].strip().lower()
    if prefix in {"desktop", "browser", "resource-slot", "session", "workspace"}:
        return prefix
    return "external"


def _session_mount_candidates(
    *,
    environment_ref: str | None,
    environment_session_id: str | None,
) -> tuple[str, ...]:
    candidates: list[str] = []
    for value in (environment_session_id, environment_ref):
        normalized = _non_empty_str(value)
        if normalized is None or not normalized.startswith("session:"):
            continue
        if normalized not in candidates:
            candidates.append(normalized)
    return tuple(candidates)


def _lease_expired(expires_at) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


@dataclass(slots=True)
class MainBrainEnvironmentBinding:
    environment_ref: str | None
    binding_kind: str
    environment_session_id: str | None
    environment_kind: str
    environment_lease_token: str | None
    continuity_token: str | None
    continuity_source: str
    live_session_bound: bool
    resume_ready: bool


class MainBrainEnvironmentCoordinator:
    def __init__(self, environment_service: Any | None = None) -> None:
        self._environment_service = environment_service

    def set_environment_service(self, environment_service: Any | None) -> None:
        self._environment_service = environment_service

    def coordinate(
        self,
        *,
        request: Any,
        execution_plan: MainBrainExecutionPlan,
    ) -> MainBrainEnvironmentBinding:
        environment_ref = _resolve_request_environment_ref(request)
        environment_session_id = _resolve_environment_session_id(request)
        binding_kind = "none"
        if environment_ref is not None:
            binding_kind = "request-environment"
        elif execution_plan.execution_mode == "environment-bound":
            binding_kind = "missing"
        environment_kind = _classify_environment_kind(environment_ref)
        explicit_continuity_token = _resolve_request_continuity_token(request)
        persisted_session = self._resolve_persisted_session(
            environment_ref=environment_ref,
            environment_session_id=environment_session_id,
        )
        if persisted_session is not None:
            environment_session_id = persisted_session.id
        live_session_bound = (
            persisted_session is not None
            and environment_kind in _LIVE_ENVIRONMENT_KINDS
            and persisted_session.lease_status == "leased"
            and _non_empty_str(persisted_session.live_handle_ref) is not None
            and not _lease_expired(persisted_session.lease_expires_at)
        )
        environment_lease_token = (
            _non_empty_str(persisted_session.lease_token)
            if live_session_bound and persisted_session is not None
            else None
        )
        if environment_lease_token is not None:
            continuity_source = "session-lease"
        elif live_session_bound:
            continuity_source = "session-live-handle"
        elif explicit_continuity_token is not None:
            continuity_source = "continuity-token"
        elif environment_session_id is not None:
            continuity_source = "environment-session"
        elif environment_ref is not None:
            continuity_source = "environment-ref"
        else:
            continuity_source = "none"
        continuity_token = (
            explicit_continuity_token
            or environment_lease_token
            or environment_session_id
            or environment_ref
        )
        resume_ready = live_session_bound
        return MainBrainEnvironmentBinding(
            environment_ref=environment_ref,
            binding_kind=binding_kind,
            environment_session_id=environment_session_id,
            environment_kind=environment_kind,
            environment_lease_token=environment_lease_token,
            continuity_token=continuity_token,
            continuity_source=continuity_source,
            live_session_bound=live_session_bound,
            resume_ready=resume_ready,
        )

    def _resolve_persisted_session(
        self,
        *,
        environment_ref: str | None,
        environment_session_id: str | None,
    ) -> SessionMount | None:
        service = self._environment_service
        if service is None:
            return None
        get_session = getattr(service, "get_session", None)
        if not callable(get_session):
            return None
        for candidate in _session_mount_candidates(
            environment_ref=environment_ref,
            environment_session_id=environment_session_id,
        ):
            try:
                session = get_session(candidate)
            except Exception:
                session = None
            if session is not None:
                return session
        return None


__all__ = [
    "MainBrainEnvironmentBinding",
    "MainBrainEnvironmentCoordinator",
]
