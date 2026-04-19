# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .graph_models import SurfaceGraphNode, SurfaceGraphSnapshot


class SurfaceTransitionDelta(BaseModel):
    before_graph_ref: str = ""
    after_graph_ref: str = ""
    changed_nodes: list[str] = Field(default_factory=list)
    new_blockers: list[str] = Field(default_factory=list)
    resolved_blockers: list[str] = Field(default_factory=list)
    result_summary: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


def mine_transition(
    before_graph: SurfaceGraphSnapshot | None,
    after_graph: SurfaceGraphSnapshot | None,
    *,
    action_kind: str,
    evidence_refs: list[str] | None = None,
) -> SurfaceTransitionDelta:
    before_nodes = _node_map(before_graph)
    after_nodes = _node_map(after_graph)
    changed_nodes = sorted(
        {
            *set(before_nodes).symmetric_difference(after_nodes),
            *{
                node_id
                for node_id in set(before_nodes).intersection(after_nodes)
                if before_nodes[node_id] != after_nodes[node_id]
            },
        }
    )
    before_blockers = {node.node_id for node in _nodes(before_graph, "blockers")}
    after_blockers = {node.node_id for node in _nodes(after_graph, "blockers")}
    new_blockers = sorted(after_blockers - before_blockers)
    resolved_blockers = sorted(before_blockers - after_blockers)
    return SurfaceTransitionDelta(
        before_graph_ref=_graph_ref(before_graph),
        after_graph_ref=_graph_ref(after_graph),
        changed_nodes=changed_nodes,
        new_blockers=new_blockers,
        resolved_blockers=resolved_blockers,
        result_summary=summarize_transition(
            action_kind=action_kind,
            changed_nodes=changed_nodes,
            new_blockers=new_blockers,
            resolved_blockers=resolved_blockers,
        ),
        evidence_refs=list(evidence_refs or []),
    )


def summarize_transition(
    *,
    action_kind: str,
    changed_nodes: list[str],
    new_blockers: list[str],
    resolved_blockers: list[str],
) -> str:
    return (
        f"{action_kind} changed {len(changed_nodes)} node(s), "
        f"added {len(new_blockers)} blocker(s), "
        f"resolved {len(resolved_blockers)} blocker(s)"
    )


def _graph_ref(graph: SurfaceGraphSnapshot | None) -> str:
    if graph is None:
        return "missing-graph"
    return (
        f"{graph.surface_kind}:"
        f"{len(graph.regions)}:{len(graph.controls)}:{len(graph.results)}:"
        f"{len(graph.blockers)}:{len(graph.entities)}:{graph.confidence:.2f}"
    )


def _node_map(graph: SurfaceGraphSnapshot | None) -> dict[str, dict[str, Any]]:
    node_map: dict[str, dict[str, Any]] = {}
    for bucket_name in ("regions", "controls", "results", "blockers", "entities"):
        for node in _nodes(graph, bucket_name):
            node_map[node.node_id] = {
                "bucket": bucket_name,
                "label": node.label,
                "summary": node.summary,
                "metadata": dict(node.metadata),
            }
    return node_map


def _nodes(
    graph: SurfaceGraphSnapshot | None,
    bucket_name: str,
) -> list[SurfaceGraphNode]:
    if graph is None:
        return []
    bucket = getattr(graph, bucket_name, [])
    return list(bucket or [])


__all__ = [
    "SurfaceTransitionDelta",
    "mine_transition",
    "summarize_transition",
]
