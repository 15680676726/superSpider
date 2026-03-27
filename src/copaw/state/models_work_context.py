# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id

WorkContextStatus = Literal["active", "paused", "completed", "archived"]


class WorkContextRecord(UpdatedRecord):
    """Formal continuous work boundary shared across tasks, reports, and recall."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    context_type: str = Field(default="generic", min_length=1)
    status: WorkContextStatus = "active"
    context_key: str | None = None
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    primary_thread_id: str | None = None
    source_kind: str | None = None
    source_ref: str | None = None
    parent_work_context_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
