# -*- coding: utf-8 -*-
from __future__ import annotations

from pydantic import BaseModel


class RepositoryIndexSnapshot(BaseModel):
    workspace_root: str
    file_count: int = 0
    chunk_count: int = 0
    symbol_count: int = 0
    commit_ref: str | None = None
    indexed_at: str | None = None
    index_version: str = "phase1"


class CodeSymbolRecord(BaseModel):
    symbol_name: str
    symbol_kind: str
    file_path: str
    line: int
    container_name: str
    language: str
    signature: str = ""
    reference_count: int = 0


__all__ = ["CodeSymbolRecord", "RepositoryIndexSnapshot"]
