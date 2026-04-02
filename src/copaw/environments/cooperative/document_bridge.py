# -*- coding: utf-8 -*-
"""Runtime helpers for cooperative Office/document-chain bridges."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..models import EnvironmentMount, SessionMount
from ..repository import EnvironmentRepository, SessionMountRepository

_READY_STATUSES = frozenset({"ready", "available", "healthy", "attached"})
_KNOWN_FAMILY_ALIASES = {
    "doc": "documents",
    "docx": "documents",
    "document": "documents",
    "documents": "documents",
    "ppt": "presentations",
    "pptx": "presentations",
    "presentation": "presentations",
    "presentations": "presentations",
    "slide": "presentations",
    "slides": "presentations",
    "spreadsheet": "spreadsheets",
    "spreadsheets": "spreadsheets",
    "xls": "spreadsheets",
    "xlsm": "spreadsheets",
    "xlsx": "spreadsheets",
    "csv": "spreadsheets",
    "tsv": "spreadsheets",
}
_KNOWN_DOCUMENT_FAMILIES = frozenset(_KNOWN_FAMILY_ALIASES.values())
_SHARED_OPERATOR_ABORT_STATE_KEY = "operator_abort_state"


def _normalize_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _resolve_shared_operator_abort_state(
    *,
    session_metadata: dict[str, object],
    environment_metadata: dict[str, object],
) -> dict[str, object]:
    raw = session_metadata.get(_SHARED_OPERATOR_ABORT_STATE_KEY)
    if not isinstance(raw, dict):
        raw = environment_metadata.get(_SHARED_OPERATOR_ABORT_STATE_KEY)
    if not isinstance(raw, dict):
        return {}
    channel = _normalize_string(
        raw.get("channel"),
    ) or _normalize_string(raw.get("operator_abort_channel"))
    requested = bool(
        raw.get("requested")
        if "requested" in raw
        else raw.get("operator_abort_requested"),
    )
    requested_at = _normalize_string(raw.get("requested_at"))
    reason = (
        _normalize_string(raw.get("reason"))
        or _normalize_string(raw.get("abort_reason"))
        or channel
    )
    state: dict[str, object] = {}
    if channel is not None:
        state["channel"] = channel
    if requested:
        state["requested"] = True
    if reason is not None:
        state["reason"] = reason
    if requested_at is not None:
        state["requested_at"] = requested_at
    return state


def _abort_channels_match(
    *,
    guardrail_channel: object,
    shared_channel: object,
) -> bool:
    normalized_guardrail_channel = _normalize_string(guardrail_channel)
    normalized_shared_channel = _normalize_string(shared_channel)
    if normalized_guardrail_channel is None or normalized_shared_channel is None:
        return True
    return normalized_guardrail_channel == normalized_shared_channel


def _merge_execution_guardrails(
    *,
    guardrails: object,
    session_metadata: dict[str, object],
    environment_metadata: dict[str, object],
) -> dict[str, object]:
    merged = dict(guardrails) if isinstance(guardrails, dict) else {}
    shared_abort_state = _resolve_shared_operator_abort_state(
        session_metadata=session_metadata,
        environment_metadata=environment_metadata,
    )
    if not shared_abort_state.get("requested"):
        return merged
    if not _abort_channels_match(
        guardrail_channel=merged.get("operator_abort_channel"),
        shared_channel=shared_abort_state.get("channel"),
    ):
        return merged
    if shared_abort_state.get("channel") is not None and _normalize_string(
        merged.get("operator_abort_channel"),
    ) is None:
        merged["operator_abort_channel"] = shared_abort_state["channel"]
    merged["operator_abort_requested"] = True
    reason = _normalize_string(merged.get("abort_reason")) or _normalize_string(
        shared_abort_state.get("reason"),
    )
    if reason is not None:
        merged["abort_reason"] = reason
    if shared_abort_state.get("requested_at") is not None:
        merged.setdefault("operator_abort_requested_at", shared_abort_state["requested_at"])
    return merged


class DocumentBridgeRuntime:
    """Persists cooperative document bridge state through canonical metadata fields."""

    def __init__(
        self,
        *,
        environment_repository: EnvironmentRepository,
        session_repository: SessionMountRepository,
    ) -> None:
        self._environment_repository = environment_repository
        self._session_repository = session_repository

    def register_bridge(
        self,
        *,
        session_mount_id: str,
        bridge_ref: str,
        status: str | None = None,
        supported_families: Iterable[str] | None = None,
        available: bool | None = None,
        execution_guardrails: dict[str, object] | None = None,
    ) -> SessionMount:
        session = self._require_session(session_mount_id)
        families = self._merge_supported_families(
            existing=self._current_supported_families(session),
            incoming=supported_families,
        )
        patch = {
            "document_bridge_ref": bridge_ref,
            "document_bridge_status": status,
            "document_bridge_available": self._resolve_available(
                bridge_ref=bridge_ref,
                status=status,
                available=available,
            ),
            "document_bridge_supported_families": families,
            "preferred_execution_path": "cooperative-native-first",
            "ui_fallback_mode": "ui-fallback-last",
            "adapter_gap_or_blocker": None,
        }
        environment = self._environment_repository.get_environment(session.environment_id)
        existing_guardrails = session.metadata.get("document_execution_guardrails")
        if not isinstance(existing_guardrails, dict) and environment is not None:
            existing_guardrails = environment.metadata.get("document_execution_guardrails")
        if execution_guardrails is not None:
            patch["document_execution_guardrails"] = dict(execution_guardrails)
        elif isinstance(existing_guardrails, dict):
            patch["document_execution_guardrails"] = dict(existing_guardrails)
        return self._persist_metadata_patch(session=session, patch=patch)

    def clear_bridge(
        self,
        *,
        session_mount_id: str,
    ) -> SessionMount:
        session = self._require_session(session_mount_id)
        patch = {
            "document_bridge_ref": None,
            "document_bridge_status": None,
            "document_bridge_available": False,
            "document_bridge_supported_families": [],
            "adapter_gap_or_blocker": "Document bridge runtime is not registered.",
        }
        environment = self._environment_repository.get_environment(session.environment_id)
        existing_guardrails = session.metadata.get("document_execution_guardrails")
        if not isinstance(existing_guardrails, dict) and environment is not None:
            existing_guardrails = environment.metadata.get("document_execution_guardrails")
        if isinstance(existing_guardrails, dict):
            patch["document_execution_guardrails"] = dict(existing_guardrails)
        return self._persist_metadata_patch(session=session, patch=patch)

    def snapshot(
        self,
        *,
        session_mount_id: str,
        document_family: str | None,
    ) -> dict[str, object]:
        session = self._require_session(session_mount_id)
        environment = self._environment_repository.get_environment(session.environment_id)
        environment_metadata = (
            dict(environment.metadata)
            if environment is not None and isinstance(environment.metadata, dict)
            else {}
        )
        resolved_family = self._normalize_family(document_family)
        supported = self._current_supported_families(session)
        bridge_ready = self._bridge_is_ready(session)

        preferred_execution_path = "cooperative-native-first"
        ui_fallback_mode = "ui-fallback-last"
        blocker: str | None = None
        if resolved_family is None:
            blocker = "Document family is required for cooperative document path selection."
        elif resolved_family not in _KNOWN_DOCUMENT_FAMILIES:
            blocker = (
                f"Document family '{resolved_family}' is not mapped to a cooperative document bridge family."
            )
        elif not bridge_ready:
            blocker = "Document bridge runtime is not ready."
        elif supported and resolved_family not in supported:
            blocker = (
                f"Document bridge does not advertise support for family '{resolved_family}'."
            )

        patch = {
            "preferred_execution_path": preferred_execution_path,
            "ui_fallback_mode": ui_fallback_mode,
            "adapter_gap_or_blocker": blocker,
        }
        self._persist_metadata_patch(session=session, patch=patch)
        return {
            "document_family": resolved_family,
            "preferred_execution_path": preferred_execution_path,
            "ui_fallback_mode": ui_fallback_mode,
            "adapter_gap_or_blocker": blocker,
            "execution_guardrails": (
                _merge_execution_guardrails(
                    guardrails=session.metadata.get("document_execution_guardrails"),
                    session_metadata=dict(session.metadata),
                    environment_metadata=environment_metadata,
                )
            ),
        }

    def _persist_metadata_patch(
        self,
        *,
        session: SessionMount,
        patch: dict[str, object],
    ) -> SessionMount:
        updated_session = self._session_repository.touch_session(
            session_mount_id=session.id,
            environment_id=session.environment_id,
            channel=session.channel,
            session_id=session.session_id,
            user_id=session.user_id,
            status=session.status,
            metadata=patch,
            last_active_at=session.last_active_at,
        )
        environment = self._environment_repository.get_environment(session.environment_id)
        if environment is not None:
            self._touch_environment(environment=environment, patch=patch)
        return updated_session

    def _touch_environment(
        self,
        *,
        environment: EnvironmentMount,
        patch: dict[str, object],
    ) -> EnvironmentMount:
        return self._environment_repository.touch_environment(
            env_id=environment.id,
            kind=environment.kind,
            display_name=environment.display_name,
            ref=environment.ref,
            status=environment.status,
            metadata=patch,
            last_active_at=environment.last_active_at,
            evidence_delta=0,
        )

    def _require_session(self, session_mount_id: str) -> SessionMount:
        session = self._session_repository.get_session(session_mount_id)
        if session is None:
            raise ValueError(f"Session mount '{session_mount_id}' was not found.")
        return session

    def _current_supported_families(self, session: SessionMount) -> list[str]:
        families = session.metadata.get("document_bridge_supported_families")
        if not isinstance(families, list):
            return []
        normalized: list[str] = []
        for value in families:
            family = self._normalize_family(value)
            if family is None or family in normalized:
                continue
            normalized.append(family)
        return normalized

    def _bridge_is_ready(self, session: SessionMount) -> bool:
        bridge_ref = session.metadata.get("document_bridge_ref")
        status = session.metadata.get("document_bridge_status")
        available = session.metadata.get("document_bridge_available")
        if isinstance(available, bool):
            return available
        if isinstance(status, str) and status.strip().lower() in _READY_STATUSES:
            return True
        return isinstance(bridge_ref, str) and bool(bridge_ref.strip())

    @staticmethod
    def _merge_supported_families(
        *,
        existing: Iterable[str],
        incoming: Iterable[str] | None,
    ) -> list[str]:
        ordered: list[str] = []
        for source in (existing, incoming or ()):
            for value in source:
                family = DocumentBridgeRuntime._normalize_family(value)
                if family is None or family in ordered:
                    continue
                ordered.append(family)
        return ordered

    @staticmethod
    def _normalize_family(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        return _KNOWN_FAMILY_ALIASES.get(normalized, normalized)

    @staticmethod
    def _resolve_available(
        *,
        bridge_ref: str | None,
        status: str | None,
        available: bool | None,
    ) -> bool:
        if isinstance(available, bool):
            return available
        if isinstance(status, str) and status.strip().lower() in _READY_STATUSES:
            return True
        return bool(bridge_ref)
