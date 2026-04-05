# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.memory.knowledge_graph_models import (
    KnowledgeGraphPath,
    KnowledgeGraphScope,
)
from copaw.memory.relation_traversal import (
    RELATION_FAMILY_PRIORITY,
    path_type_for_relation_kind,
    relation_family_for_kind,
)


def test_relation_traversal_maps_core_relation_kinds_to_families_and_path_types() -> None:
    assert relation_family_for_kind("depends_on") == "execution"
    assert relation_family_for_kind("blocks") == "execution"
    assert relation_family_for_kind("supports") == "judgment"
    assert relation_family_for_kind("contradicts") == "judgment"
    assert relation_family_for_kind("causes") == "causal"
    assert relation_family_for_kind("follows") == "temporal"
    assert relation_family_for_kind("belongs_to") == "structural"

    assert path_type_for_relation_kind("depends_on") == "dependency"
    assert path_type_for_relation_kind("blocks") == "blocker"
    assert path_type_for_relation_kind("supports") == "support"
    assert path_type_for_relation_kind("contradicts") == "contradiction"
    assert path_type_for_relation_kind("recovers_with") == "recovery"

    assert RELATION_FAMILY_PRIORITY["execution"] < RELATION_FAMILY_PRIORITY["judgment"]
    assert RELATION_FAMILY_PRIORITY["judgment"] < RELATION_FAMILY_PRIORITY["causal"]


def test_knowledge_graph_path_keeps_runtime_path_contract_minimal_and_explicit() -> None:
    path = KnowledgeGraphPath(
        path_type="dependency",
        score=9.5,
        node_ids=["assignment:1", "capability:browser"],
        relation_ids=["relation-dep-1"],
        relation_kinds=["depends_on"],
        summary="The assignment depends on the governed browser capability.",
        evidence_refs=["evidence-1"],
        source_refs=["memory:dependency-1"],
    )

    assert path.path_type == "dependency"
    assert path.score == 9.5
    assert path.node_ids == ["assignment:1", "capability:browser"]
    assert path.relation_ids == ["relation-dep-1"]
    assert path.relation_kinds == ["depends_on"]
    assert path.evidence_refs == ["evidence-1"]
    assert path.source_refs == ["memory:dependency-1"]

