# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..state import FixedSopBindingRecord, FixedSopTemplateRecord, WorkflowRunRecord


class FixedSopNodeKind(str, Enum):
    TRIGGER = "trigger"
    GUARD = "guard"
    HTTP_REQUEST = "http_request"
    CAPABILITY_CALL = "capability_call"
    ROUTINE_CALL = "routine_call"
    WAIT_CALLBACK = "wait_callback"
    WRITEBACK = "writeback"


class FixedSopTemplateSummary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template: FixedSopTemplateRecord
    binding_count: int = 0
    routes: dict[str, str] = Field(default_factory=dict)


class FixedSopTemplateListResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    items: list[FixedSopTemplateSummary] = Field(default_factory=list)
    total: int = 0


class FixedSopBindingCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template_id: str
    binding_name: str | None = None
    status: str = "draft"
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    workflow_template_id: str | None = None
    trigger_mode: str = "manual"
    trigger_ref: str | None = None
    input_mapping: dict[str, Any] = Field(default_factory=dict)
    output_mapping: dict[str, Any] = Field(default_factory=dict)
    timeout_policy: dict[str, Any] = Field(default_factory=dict)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    risk_baseline: str = "guarded"
    metadata: dict[str, Any] = Field(default_factory=dict)


class FixedSopBindingDetail(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    binding: FixedSopBindingRecord
    template: FixedSopTemplateRecord
    routes: dict[str, str] = Field(default_factory=dict)


class FixedSopDoctorCheck(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    key: str
    label: str
    status: Literal["pass", "warn", "fail", "info"] = "info"
    message: str


class FixedSopDoctorReport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    binding_id: str
    template_id: str
    status: Literal["ready", "degraded", "blocked"] = "blocked"
    summary: str = ""
    checks: list[FixedSopDoctorCheck] = Field(default_factory=list)
    environment_id: str | None = None
    session_mount_id: str | None = None
    host_requirement: dict[str, Any] = Field(default_factory=dict)
    host_preflight: dict[str, Any] = Field(default_factory=dict)
    routes: dict[str, str] = Field(default_factory=dict)


class FixedSopRunRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    input_payload: dict[str, Any] = Field(default_factory=dict)
    workflow_run_id: str | None = None
    owner_agent_id: str | None = None
    owner_scope: str | None = None
    environment_id: str | None = None
    session_mount_id: str | None = None
    dry_run: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class FixedSopRunResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    binding_id: str
    status: Literal["success", "error"] = "success"
    summary: str = ""
    workflow_run_id: str | None = None
    evidence_id: str | None = None
    routes: dict[str, str] = Field(default_factory=dict)


class FixedSopRunDetail(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    run: WorkflowRunRecord
    binding: FixedSopBindingRecord | None = None
    template: FixedSopTemplateRecord | None = None
    environment_id: str | None = None
    session_mount_id: str | None = None
    host_requirement: dict[str, Any] = Field(default_factory=dict)
    host_preflight: dict[str, Any] = Field(default_factory=dict)
