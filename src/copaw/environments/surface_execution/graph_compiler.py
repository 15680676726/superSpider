# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from .graph_models import SurfaceGraphEdge, SurfaceGraphNode, SurfaceGraphSnapshot

if TYPE_CHECKING:
    from .browser.contracts import BrowserObservation
    from .desktop.contracts import DesktopObservation
    from .document.contracts import DocumentObservation


def _edge(edge_id: str, source_node_id: str, target_node_id: str) -> SurfaceGraphEdge:
    return SurfaceGraphEdge(
        edge_id=edge_id,
        relation_kind="contains",
        source_node_id=source_node_id,
        target_node_id=target_node_id,
    )


def compile_browser_observation_to_graph(
    observation: BrowserObservation,
) -> SurfaceGraphSnapshot:
    root_id = "region:browser:root"
    regions = [
        SurfaceGraphNode(
            node_id=root_id,
            node_kind="region",
            label=observation.page_title or observation.page_summary.headline or "browser-surface",
            summary=observation.page_summary.primary_text or observation.snapshot_text,
        )
    ]
    controls: list[SurfaceGraphNode] = []
    for index, candidate in enumerate(observation.interactive_targets):
        node_id = (
            f"control:browser:{candidate.action_ref}"
            if candidate.action_ref
            else f"control:browser:{candidate.action_selector or index}"
        )
        controls.append(
            SurfaceGraphNode(
                node_id=node_id,
                node_kind="control",
                label=candidate.scope_anchor or candidate.target_kind,
                summary=candidate.reason,
                metadata={
                    "target_kind": candidate.target_kind,
                    "element_kind": candidate.element_kind,
                },
            )
        )
    results: list[SurfaceGraphNode] = []
    primary_text = observation.page_summary.primary_text or observation.snapshot_text
    if primary_text.strip():
        results.append(
            SurfaceGraphNode(
                node_id="result:browser:page-summary",
                node_kind="result",
                label=observation.page_summary.headline or "page-summary",
                summary=primary_text,
            )
        )
    blockers = [
        SurfaceGraphNode(
            node_id=f"blocker:browser:{index}",
            node_kind="blocker",
            label=blocker,
            summary=blocker,
        )
        for index, blocker in enumerate(observation.blockers)
    ]
    entities = [
        SurfaceGraphNode(
            node_id="entity:browser:page",
            node_kind="entity",
            label=observation.page_title or observation.page_summary.headline or "browser-page",
            summary=observation.page_url,
            metadata={"page_url": observation.page_url},
        )
    ]
    relations = [_edge(f"edge:browser:root:{index}", root_id, node.node_id) for index, node in enumerate(controls)]
    relations.extend(
        _edge(f"edge:browser:result:{index}", root_id, node.node_id)
        for index, node in enumerate(results)
    )
    relations.extend(
        _edge(f"edge:browser:blocker:{index}", root_id, node.node_id)
        for index, node in enumerate(blockers)
    )
    relations.extend(
        _edge(f"edge:browser:entity:{index}", root_id, node.node_id)
        for index, node in enumerate(entities)
    )
    confidence = 0.9 if controls or results else 0.4
    return SurfaceGraphSnapshot(
        surface_kind="browser",
        regions=regions,
        controls=controls,
        results=results,
        blockers=blockers,
        entities=entities,
        relations=relations,
        confidence=confidence,
    )


def compile_document_observation_to_graph(
    observation: DocumentObservation,
) -> SurfaceGraphSnapshot:
    root_id = "region:document:root"
    regions = [
        SurfaceGraphNode(
            node_id=root_id,
            node_kind="region",
            label=observation.document_family or "document",
            summary=observation.document_path,
        )
    ]
    results = [
        SurfaceGraphNode(
            node_id="result:document:content",
            node_kind="result",
            label="document-content",
            summary=observation.content_text,
            metadata={"revision_token": observation.revision_token},
        )
    ]
    blockers = [
        SurfaceGraphNode(
            node_id=f"blocker:document:{index}",
            node_kind="blocker",
            label=blocker,
            summary=blocker,
        )
        for index, blocker in enumerate(observation.blockers)
    ]
    entities = [
        SurfaceGraphNode(
            node_id="entity:document:file",
            node_kind="entity",
            label=observation.document_path,
            summary=observation.document_family,
        )
    ]
    relations = [_edge("edge:document:content", root_id, "result:document:content")]
    relations.extend(
        _edge(f"edge:document:blocker:{index}", root_id, node.node_id)
        for index, node in enumerate(blockers)
    )
    relations.extend(
        _edge(f"edge:document:entity:{index}", root_id, node.node_id)
        for index, node in enumerate(entities)
    )
    return SurfaceGraphSnapshot(
        surface_kind="document",
        regions=regions,
        results=results,
        blockers=blockers,
        entities=entities,
        relations=relations,
        confidence=0.9 if observation.content_text.strip() else 0.4,
    )


def compile_desktop_observation_to_graph(
    observation: DesktopObservation,
) -> SurfaceGraphSnapshot:
    root_id = "region:desktop:root"
    regions = [
        SurfaceGraphNode(
            node_id=root_id,
            node_kind="region",
            label=observation.window_title or observation.app_identity or "desktop-surface",
            summary=observation.app_identity,
        )
    ]
    controls: list[SurfaceGraphNode] = []
    for slot_name, candidates in observation.slot_candidates.items():
        for index, candidate in enumerate(candidates):
            controls.append(
                SurfaceGraphNode(
                    node_id=f"control:desktop:{slot_name}:{index}",
                    node_kind="control",
                    label=candidate.label or slot_name,
                    summary=candidate.action_selector,
                    metadata={
                        "target_kind": candidate.target_kind,
                        "scope_anchor": candidate.scope_anchor,
                    },
                )
            )
    results = [
        SurfaceGraphNode(
            node_id=f"result:desktop:{key}",
            node_kind="result",
            label=key,
            summary=value,
        )
        for key, value in observation.readback.items()
    ]
    blockers = [
        SurfaceGraphNode(
            node_id=f"blocker:desktop:{index}",
            node_kind="blocker",
            label=blocker,
            summary=blocker,
        )
        for index, blocker in enumerate(observation.blockers)
    ]
    relations = [_edge(f"edge:desktop:control:{index}", root_id, node.node_id) for index, node in enumerate(controls)]
    relations.extend(
        _edge(f"edge:desktop:result:{index}", root_id, node.node_id)
        for index, node in enumerate(results)
    )
    relations.extend(
        _edge(f"edge:desktop:blocker:{index}", root_id, node.node_id)
        for index, node in enumerate(blockers)
    )
    return SurfaceGraphSnapshot(
        surface_kind="desktop",
        regions=regions,
        controls=controls,
        results=results,
        blockers=blockers,
        relations=relations,
        confidence=0.9 if controls or results else 0.4,
    )


__all__ = [
    "compile_browser_observation_to_graph",
    "compile_desktop_observation_to_graph",
    "compile_document_observation_to_graph",
]
