# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..state import ExecutionRoutineRecord, RoutineRunRecord

ROUTINE_FAILURE_CLASSES = (
    "precondition-miss",
    "page-drift",
    "auth-expired",
    "lock-conflict",
    "confirmation-required",
    "modal-interruption",
    "executor-unavailable",
    "execution-error",
    "host-unsupported",
)
ROUTINE_FALLBACK_MODES = (
    "retry-same-session",
    "reattach-or-recover-session",
    "pause-for-confirm",
    "return-to-llm-replan",
    "hard-fail",
)
SUPPORTED_ROUTINE_EVIDENCE_ACTIONS = (
    "open",
    "navigate",
    "click",
    "screenshot",
)
ROUTINE_RESOURCE_SCOPE_TYPES = (
    "browser-profile",
    "browser-session",
    "domain-account",
    "page-tab",
    "artifact-target",
)
SUPPORTED_BROWSER_ROUTINE_ACTIONS = (
    "open",
    "navigate",
    "click",
    "type",
    "wait_for",
    "tabs",
    "file_upload",
    "fill_form",
    "screenshot",
    "pdf",
)
SUPPORTED_DESKTOP_ROUTINE_ACTIONS = (
    "list_windows",
    "get_foreground_window",
    "launch_application",
    "wait_for_window",
    "focus_window",
    "verify_window_focus",
    "list_controls",
    "click",
    "type_text",
    "press_keys",
    "set_control_text",
    "invoke_control",
    "invoke_dialog_action",
    "close_window",
    "write_document_file",
    "edit_document_file",
)


class RoutineCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    routine_key: str
    name: str
    summary: str = ""
    status: str = "active"
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    source_capability_id: str | None = None
    trigger_kind: str = "manual"
    engine_kind: str = "browser"
    environment_kind: str = "browser"
    session_requirements: dict[str, Any] = Field(default_factory=dict)
    isolation_policy: dict[str, Any] = Field(default_factory=dict)
    lock_scope: list[dict[str, Any]] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[dict[str, Any]] = Field(default_factory=list)
    expected_observations: list[dict[str, Any]] = Field(default_factory=list)
    action_contract: list[dict[str, Any]] = Field(default_factory=list)
    success_signature: dict[str, Any] = Field(default_factory=dict)
    drift_signals: list[dict[str, Any]] = Field(default_factory=list)
    replay_policy: dict[str, Any] = Field(default_factory=dict)
    fallback_policy: dict[str, Any] = Field(default_factory=dict)
    risk_baseline: str = "guarded"
    evidence_expectations: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutineCreateFromEvidenceRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    evidence_ids: list[str] = Field(default_factory=list)
    routine_key: str | None = None
    name: str | None = None
    summary: str = ""
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    source_capability_id: str | None = None
    trigger_kind: str = "evidence"
    engine_kind: str = "browser"
    environment_kind: str = "browser"
    session_requirements: dict[str, Any] = Field(default_factory=dict)
    isolation_policy: dict[str, Any] = Field(default_factory=dict)
    lock_scope: list[dict[str, Any]] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    replay_policy: dict[str, Any] = Field(default_factory=dict)
    fallback_policy: dict[str, Any] = Field(default_factory=dict)
    risk_baseline: str = "guarded"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutineReplayRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_type: str = "manual"
    source_ref: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    owner_agent_id: str | None = None
    owner_scope: str | None = None
    session_id: str | None = None
    request_context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutineFailureSummary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    run_id: str
    failure_class: str
    status: str
    output_summary: str | None = None
    fallback_mode: str | None = None
    completed_at: str | None = None


class RoutineDiagnosis(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    routine_id: str
    last_run_id: str | None = None
    status: str = "active"
    drift_status: str = "stable"
    selector_health: str = "unknown"
    session_health: str = "unknown"
    lock_health: str = "unknown"
    evidence_health: str = "unknown"
    verification_status: str = "unknown"
    verification_summary: dict[str, Any] = Field(default_factory=dict)
    recent_failures: list[dict[str, Any]] = Field(default_factory=list)
    fallback_summary: dict[str, Any] = Field(default_factory=dict)
    resource_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    last_verified_at: str | None = None


class RoutineRunDetail(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    run: RoutineRunRecord
    routine: ExecutionRoutineRecord
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    routes: dict[str, str] = Field(default_factory=dict)


class RoutineDetail(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    routine: ExecutionRoutineRecord
    last_run: RoutineRunRecord | None = None
    recent_runs: list[RoutineRunRecord] = Field(default_factory=list)
    recent_evidence: list[dict[str, Any]] = Field(default_factory=list)
    diagnosis: RoutineDiagnosis
    routes: dict[str, str] = Field(default_factory=dict)


class RoutineReplayResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    run: RoutineRunRecord
    diagnosis: RoutineDiagnosis
    routes: dict[str, str] = Field(default_factory=dict)
