# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_record_id() -> str:
    return str(uuid4())


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_text_list(value: object) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


class StateRecord(BaseModel):
    """Base class for state records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator(
        "created_at",
        "updated_at",
        "last_run_at",
        "next_run_at",
        "started_at",
        "completed_at",
        "processed_at",
        "source_updated_at",
        "last_reflected_at",
        "resolved_at",
        "expires_at",
        mode="after",
        check_fields=False,
    )
    @classmethod
    def _normalize_datetime_fields(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_datetime(value)


class CreatedRecord(StateRecord):
    """Base record with creation timestamp."""

    created_at: datetime = Field(default_factory=_utc_now)


class UpdatedRecord(CreatedRecord):
    """Base record with creation and update timestamps."""

    updated_at: datetime | None = None

    @model_validator(mode="after")
    def _default_updated_at(self) -> "UpdatedRecord":
        if self.updated_at is None:
            self.updated_at = self.created_at
        return self
