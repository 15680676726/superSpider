# -*- coding: utf-8 -*-
from __future__ import annotations

import re

from .knowledge_graph_models import KnowledgeGraphPath

RELATION_FAMILY_PRIORITY = {
    "execution": 1,
    "judgment": 2,
    "causal": 3,
    "temporal": 4,
    "structural": 5,
}

_RELATION_FAMILY_MAP = {
    "belongs_to": "structural",
    "part_of": "structural",
    "instance_of": "structural",
    "located_in": "structural",
    "follows": "temporal",
    "updates": "temporal",
    "replaces": "temporal",
    "causes": "causal",
    "affects": "causal",
    "indicates": "causal",
    "supports": "judgment",
    "contradicts": "judgment",
    "suggests": "judgment",
    "depends_on": "execution",
    "blocks": "execution",
    "uses": "execution",
    "produces": "execution",
    "recovers_with": "execution",
    "constrained_by": "execution",
}

_PATH_TYPE_MAP = {
    "supports": "support",
    "contradicts": "contradiction",
    "depends_on": "dependency",
    "blocks": "blocker",
    "recovers_with": "recovery",
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_-]{1,}")


def relation_family_for_kind(relation_kind: str) -> str:
    normalized = str(relation_kind or "").strip()
    return _RELATION_FAMILY_MAP.get(normalized, "judgment")


def path_type_for_relation_kind(relation_kind: str) -> str | None:
    normalized = str(relation_kind or "").strip()
    return _PATH_TYPE_MAP.get(normalized)


def traversal_score(
    *,
    relation_kind: str,
    summary: str,
    source_node_id: str | None,
    target_node_id: str | None,
    seed_terms: list[str],
    confidence: float,
    scope_match: bool,
) -> float:
    family = relation_family_for_kind(relation_kind)
    family_priority = RELATION_FAMILY_PRIORITY.get(family, 99)
    tokens = set(
        _TOKEN_RE.findall(
            " ".join(
                part for part in [summary, relation_kind, source_node_id, target_node_id] if part
            ).lower(),
        ),
    )
    match_count = sum(1 for term in seed_terms if term in tokens)
    score = 0.0
    if scope_match:
        score += 10.0
    score += match_count * 4.0
    score += max(0.0, 6.0 - float(family_priority))
    score += float(confidence or 0.0) * 5.0
    return score


def pack_relation_paths(
    *,
    scored_relations: list[tuple[float, object]],
    per_type_limit: int = 2,
) -> dict[str, list[KnowledgeGraphPath]]:
    grouped = {
        "support": [],
        "contradiction": [],
        "dependency": [],
        "blocker": [],
        "recovery": [],
    }
    for score, relation in scored_relations:
        relation_kind = str(getattr(relation, "relation_kind", "") or "").strip()
        path_type = path_type_for_relation_kind(relation_kind)
        if path_type is None:
            continue
        grouped[path_type].append(
            KnowledgeGraphPath(
                path_type=path_type,
                score=score,
                node_ids=[
                    value
                    for value in [
                        getattr(relation, "source_node_id", None),
                        getattr(relation, "target_node_id", None),
                    ]
                    if isinstance(value, str) and value.strip()
                ],
                relation_ids=[str(getattr(relation, "relation_id"))],
                relation_kinds=[relation_kind],
                summary=str(getattr(relation, "summary", "") or ""),
                evidence_refs=list(getattr(relation, "source_refs", []) or []),
                source_refs=list(getattr(relation, "source_refs", []) or []),
            ),
        )
    for path_type, items in grouped.items():
        grouped[path_type] = sorted(
            items,
            key=lambda item: (item.score, item.summary.lower(), item.relation_ids),
            reverse=True,
        )[:per_type_limit]
    return grouped
