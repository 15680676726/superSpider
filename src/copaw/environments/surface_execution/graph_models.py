# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SurfaceGraphNode(BaseModel):
    node_id: str
    node_kind: str = ""
    label: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SurfaceGraphEdge(BaseModel):
    edge_id: str
    relation_kind: str = "contains"
    source_node_id: str = ""
    target_node_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SurfaceGraphSnapshot(BaseModel):
    surface_kind: str
    regions: list[SurfaceGraphNode] = Field(default_factory=list)
    controls: list[SurfaceGraphNode] = Field(default_factory=list)
    results: list[SurfaceGraphNode] = Field(default_factory=list)
    blockers: list[SurfaceGraphNode] = Field(default_factory=list)
    entities: list[SurfaceGraphNode] = Field(default_factory=list)
    relations: list[SurfaceGraphEdge] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


__all__ = [
    "SurfaceGraphEdge",
    "SurfaceGraphNode",
    "SurfaceGraphSnapshot",
]
