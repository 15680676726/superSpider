# -*- coding: utf-8 -*-
from __future__ import annotations

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id


class KnowledgeChunkRecord(UpdatedRecord):
    """Formal persisted knowledge chunk for V2 knowledge retrieval."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    document_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    summary: str = ""
    source_ref: str | None = None
    chunk_index: int = Field(default=0, ge=0)
    role_bindings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
