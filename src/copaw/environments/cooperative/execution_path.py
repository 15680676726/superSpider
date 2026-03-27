# -*- coding: utf-8 -*-
"""Shared execution-path policy for cooperative environment surfaces."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


DEFAULT_PREFERRED_EXECUTION_PATH = "cooperative-native-first"
DEFAULT_UI_FALLBACK_MODE = "ui-fallback-last"

COOPERATIVE_NATIVE_PATH = "cooperative-native"
SEMANTIC_OPERATOR_PATH = "semantic-operator"
UI_FALLBACK_PATH = "ui-fallback"


@dataclass(frozen=True)
class ExecutionPathResolution:
    """Resolved runtime path for a browser, document, or Windows app surface."""

    surface_kind: str
    preferred_execution_path: str
    ui_fallback_mode: str
    selected_path: str | None
    selected_channel: str | None
    selected_ref: str | None
    blocked: bool
    fallback_applied: bool
    current_gap_or_blocker: str | None
    attempted_paths: tuple[str, ...]
    resolution_reason: str


def resolve_preferred_execution_path(
    *,
    surface_kind: str,
    cooperative_available: bool,
    cooperative_refs: Sequence[str] | None = None,
    cooperative_blocker: str | None = None,
    semantic_available: bool,
    semantic_channel: str = SEMANTIC_OPERATOR_PATH,
    semantic_ref: str | None = None,
    ui_available: bool,
    ui_channel: str = UI_FALLBACK_PATH,
    ui_ref: str | None = None,
    preferred_execution_path: str = DEFAULT_PREFERRED_EXECUTION_PATH,
    ui_fallback_mode: str = DEFAULT_UI_FALLBACK_MODE,
) -> ExecutionPathResolution:
    """Pick the runtime path in cooperative/native -> semantic -> UI order."""

    attempted_paths = (
        COOPERATIVE_NATIVE_PATH,
        SEMANTIC_OPERATOR_PATH,
        UI_FALLBACK_PATH,
    )
    cooperative_ref = _first_ref(cooperative_refs)
    blocker = _normalize_string(cooperative_blocker)
    normalized_surface_kind = _normalize_string(surface_kind) or "unknown"

    if cooperative_available:
        return ExecutionPathResolution(
            surface_kind=normalized_surface_kind,
            preferred_execution_path=preferred_execution_path,
            ui_fallback_mode=ui_fallback_mode,
            selected_path=COOPERATIVE_NATIVE_PATH,
            selected_channel=COOPERATIVE_NATIVE_PATH,
            selected_ref=cooperative_ref or COOPERATIVE_NATIVE_PATH,
            blocked=False,
            fallback_applied=False,
            current_gap_or_blocker=blocker,
            attempted_paths=attempted_paths,
            resolution_reason=(
                f"{normalized_surface_kind} selected the cooperative/native path first."
            ),
        )

    if semantic_available:
        return ExecutionPathResolution(
            surface_kind=normalized_surface_kind,
            preferred_execution_path=preferred_execution_path,
            ui_fallback_mode=ui_fallback_mode,
            selected_path=SEMANTIC_OPERATOR_PATH,
            selected_channel=semantic_channel,
            selected_ref=_normalize_string(semantic_ref) or semantic_channel,
            blocked=False,
            fallback_applied=True,
            current_gap_or_blocker=blocker,
            attempted_paths=attempted_paths,
            resolution_reason=_fallback_reason(
                normalized_surface_kind,
                selected_path=SEMANTIC_OPERATOR_PATH,
                blocker=blocker,
            ),
        )

    if ui_available:
        return ExecutionPathResolution(
            surface_kind=normalized_surface_kind,
            preferred_execution_path=preferred_execution_path,
            ui_fallback_mode=ui_fallback_mode,
            selected_path=UI_FALLBACK_PATH,
            selected_channel=ui_channel,
            selected_ref=_normalize_string(ui_ref) or ui_channel,
            blocked=False,
            fallback_applied=True,
            current_gap_or_blocker=blocker,
            attempted_paths=attempted_paths,
            resolution_reason=_fallback_reason(
                normalized_surface_kind,
                selected_path=UI_FALLBACK_PATH,
                blocker=blocker,
            ),
        )

    return ExecutionPathResolution(
        surface_kind=normalized_surface_kind,
        preferred_execution_path=preferred_execution_path,
        ui_fallback_mode=ui_fallback_mode,
        selected_path=None,
        selected_channel=None,
        selected_ref=None,
        blocked=True,
        fallback_applied=False,
        current_gap_or_blocker=blocker,
        attempted_paths=attempted_paths,
        resolution_reason=(
            f"{normalized_surface_kind} has no cooperative/native, semantic, or UI path available."
        ),
    )


def _fallback_reason(
    surface_kind: str,
    *,
    selected_path: str,
    blocker: str | None,
) -> str:
    if blocker:
        return (
            f"{surface_kind} fell back to {selected_path} because the cooperative/native "
            f"path is blocked: {blocker}."
        )
    return f"{surface_kind} fell back to {selected_path} because earlier paths are unavailable."


def _first_ref(values: Sequence[str] | None) -> str | None:
    if values is None:
        return None
    for value in values:
        normalized = _normalize_string(value)
        if normalized is not None:
            return normalized
    return None


def _normalize_string(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return None
