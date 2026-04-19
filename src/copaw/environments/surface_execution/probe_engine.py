# -*- coding: utf-8 -*-
from __future__ import annotations

from pydantic import BaseModel

from .graph_models import SurfaceGraphNode, SurfaceGraphSnapshot


class SurfaceProbeDecision(BaseModel):
    surface_kind: str
    probe_action: str
    target_region: str = ""
    reason: str = ""


class SurfaceDiscoveryCandidate(BaseModel):
    discovery_kind: str
    discovery_fingerprint: str
    node_id: str = ""
    node_kind: str = ""
    label: str = ""
    region_ref: str = ""
    candidate_capability: str = ""


def decide_surface_probe(
    graph: SurfaceGraphSnapshot | None,
    *,
    intent_kind: str = "",
    target_slot: str = "",
    target_resolved: bool = True,
) -> SurfaceProbeDecision | None:
    if graph is None:
        return SurfaceProbeDecision(
            surface_kind="unknown",
            probe_action="refresh-local-region",
            target_region="",
            reason="missing-graph",
        )
    target_region = _primary_region_id(graph)
    if not target_resolved and intent_kind != "press":
        _ = target_slot
        return SurfaceProbeDecision(
            surface_kind=graph.surface_kind,
            probe_action="refresh-local-region",
            target_region=target_region,
            reason="target-unresolved",
        )
    if graph.confidence < 0.75:
        return SurfaceProbeDecision(
            surface_kind=graph.surface_kind,
            probe_action="refresh-local-region",
            target_region=target_region,
            reason="low-confidence-graph",
        )
    return None


def collect_surface_discoveries(
    before_graph: SurfaceGraphSnapshot | None,
    after_graph: SurfaceGraphSnapshot | None,
    *,
    candidate_capability: str = "",
) -> list[SurfaceDiscoveryCandidate]:
    if after_graph is None:
        return []
    before_node_ids = set(_all_node_ids(before_graph))
    discoveries: list[SurfaceDiscoveryCandidate] = []
    region_ref = _primary_region_id(after_graph)
    for bucket_name, nodes in _graph_buckets(after_graph):
        for node in nodes:
            if node.node_id in before_node_ids:
                continue
            discoveries.append(
                SurfaceDiscoveryCandidate(
                    discovery_kind=f"new-{bucket_name[:-1]}",
                    discovery_fingerprint=_fingerprint(after_graph.surface_kind, node),
                    node_id=node.node_id,
                    node_kind=node.node_kind,
                    label=node.label,
                    region_ref=region_ref,
                    candidate_capability=candidate_capability,
                )
            )
    return discoveries


def _graph_buckets(
    graph: SurfaceGraphSnapshot,
) -> list[tuple[str, list[SurfaceGraphNode]]]:
    return [
        ("regions", list(graph.regions)),
        ("controls", list(graph.controls)),
        ("results", list(graph.results)),
        ("blockers", list(graph.blockers)),
        ("entities", list(graph.entities)),
    ]


def _all_node_ids(graph: SurfaceGraphSnapshot | None) -> list[str]:
    if graph is None:
        return []
    node_ids: list[str] = []
    for _, nodes in _graph_buckets(graph):
        node_ids.extend(node.node_id for node in nodes)
    return node_ids


def _primary_region_id(graph: SurfaceGraphSnapshot | None) -> str:
    if graph is None or not graph.regions:
        return ""
    return str(graph.regions[0].node_id or "")


def _fingerprint(surface_kind: str, node: SurfaceGraphNode) -> str:
    return f"{surface_kind}:{node.node_kind}:{node.node_id}"


__all__ = [
    "SurfaceDiscoveryCandidate",
    "SurfaceProbeDecision",
    "collect_surface_discoveries",
    "decide_surface_probe",
]
