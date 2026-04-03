# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from copaw.memory import DerivedMemoryIndexService
from copaw.memory.activation_models import ActivationInput
from copaw.memory.activation_service import MemoryActivationService


def _fact_entry(
    entry_id: str,
    *,
    scope_type: str,
    scope_id: str,
    title: str,
    summary: str,
    content_excerpt: str | None = None,
    entity_keys: list[str] | None = None,
    opinion_keys: list[str] | None = None,
    tags: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    confidence: float = 0.8,
    quality_score: float = 0.7,
    source_ref: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=entry_id,
        source_type="knowledge_chunk",
        source_ref=source_ref or f"chunk:{entry_id}",
        scope_type=scope_type,
        scope_id=scope_id,
        title=title,
        summary=summary,
        content_excerpt=content_excerpt or summary,
        entity_keys=list(entity_keys or []),
        opinion_keys=list(opinion_keys or []),
        tags=list(tags or []),
        evidence_refs=list(evidence_refs or []),
        confidence=confidence,
        quality_score=quality_score,
        source_updated_at=None,
        metadata={},
    )


def _entity_view(
    entity_id: str,
    *,
    entity_key: str,
    scope_type: str,
    scope_id: str,
    summary: str,
    supporting_refs: list[str] | None = None,
    contradicting_refs: list[str] | None = None,
    related_entities: list[str] | None = None,
    confidence: float = 0.8,
) -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=entity_id,
        entity_key=entity_key,
        scope_type=scope_type,
        scope_id=scope_id,
        owner_agent_id=None,
        industry_instance_id=None,
        display_name=entity_key.replace("-", " ").title(),
        entity_type="concept",
        summary=summary,
        confidence=confidence,
        supporting_refs=list(supporting_refs or []),
        contradicting_refs=list(contradicting_refs or []),
        related_entities=list(related_entities or []),
        source_refs=list(supporting_refs or []),
        metadata={},
    )


def _opinion_view(
    opinion_id: str,
    *,
    subject_key: str,
    opinion_key: str,
    scope_type: str,
    scope_id: str,
    summary: str,
    supporting_refs: list[str] | None = None,
    contradicting_refs: list[str] | None = None,
    entity_keys: list[str] | None = None,
    confidence: float = 0.75,
) -> SimpleNamespace:
    return SimpleNamespace(
        opinion_id=opinion_id,
        subject_key=subject_key,
        scope_type=scope_type,
        scope_id=scope_id,
        owner_agent_id=None,
        industry_instance_id=None,
        opinion_key=opinion_key,
        stance="caution",
        summary=summary,
        confidence=confidence,
        supporting_refs=list(supporting_refs or []),
        contradicting_refs=list(contradicting_refs or []),
        entity_keys=list(entity_keys or []),
        source_refs=list(supporting_refs or []),
        metadata={},
    )


def _relation_view(
    relation_id: str,
    *,
    relation_kind: str,
    scope_type: str,
    scope_id: str,
    summary: str,
    source_refs: list[str] | None = None,
    confidence: float = 0.8,
    source_node_id: str = "fact-1",
    target_node_id: str = "entity-1",
) -> SimpleNamespace:
    return SimpleNamespace(
        relation_id=relation_id,
        relation_kind=relation_kind,
        scope_type=scope_type,
        scope_id=scope_id,
        summary=summary,
        confidence=confidence,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        source_refs=list(source_refs or []),
    )


class _RelationViewRepository:
    def __init__(self) -> None:
        self.records: list[object] = []
        self.clear_calls: list[tuple[str | None, str | None]] = []

    def clear(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        self.clear_calls.append((scope_type, scope_id))
        self.records = []
        return 0

    def upsert_view(self, record: object) -> object:
        relation_id = str(getattr(record, "relation_id"))
        self.records = [
            existing
            for existing in self.records
            if str(getattr(existing, "relation_id")) != relation_id
        ]
        self.records.append(record)
        return record

    def list_views(self, **kwargs: object) -> list[object]:
        records = list(self.records)
        for field in (
            "scope_type",
            "scope_id",
            "owner_agent_id",
            "industry_instance_id",
            "relation_kind",
            "source_node_id",
            "target_node_id",
        ):
            value = kwargs.get(field)
            if value is None:
                continue
            records = [
                record
                for record in records
                if getattr(record, field, None) == value
            ]
        limit = kwargs.get("limit")
        if isinstance(limit, int):
            return records[:limit]
        return records


def test_activation_service_materializes_entity_and_opinion_neurons() -> None:
    service = MemoryActivationService(
        derived_index_service=SimpleNamespace(),
        strategy_memory_service=SimpleNamespace(),
    )

    result = service.activate(
        ActivationInput(
            query_text="outbound approval is blocked",
            work_context_id="ctx-1",
        ),
        fact_entries=[
            _fact_entry(
                "fact-1",
                scope_type="work_context",
                scope_id="ctx-1",
                title="Outbound approval blocked",
                summary="Approval is blocked pending evidence review.",
                entity_keys=["outbound", "approval"],
                opinion_keys=["approval:caution:evidence-review"],
                tags=["latest"],
                evidence_refs=["evidence-1"],
                source_ref="chunk-1",
            )
        ],
        entity_views=[
            _entity_view(
                "entity-1",
                entity_key="outbound",
                scope_type="work_context",
                scope_id="ctx-1",
                summary="Outbound is the current constrained execution lane.",
                supporting_refs=["fact-1", "chunk-1"],
            )
        ],
        opinion_views=[
            _opinion_view(
                "opinion-1",
                subject_key="approval",
                opinion_key="approval:caution:evidence-review",
                scope_type="work_context",
                scope_id="ctx-1",
                summary="Approval should wait for evidence review.",
                supporting_refs=["fact-1", "chunk-1"],
                entity_keys=["approval", "outbound"],
            )
        ],
        profile_view=None,
        episode_views=[],
        strategy_payload=None,
    )

    neuron_ids = {item.neuron_id for item in result.activated_neurons}
    assert {"fact-1", "entity-1", "opinion-1"} <= neuron_ids


def test_activation_service_prefers_work_context_scope_over_industry_scope() -> None:
    service = MemoryActivationService(
        derived_index_service=SimpleNamespace(),
        strategy_memory_service=SimpleNamespace(),
    )

    result = service.activate(
        ActivationInput(
            query_text="blocked outbound approval",
            work_context_id="ctx-1",
            industry_instance_id="industry-1",
        ),
        fact_entries=[
            _fact_entry(
                "fact-industry",
                scope_type="industry",
                scope_id="industry-1",
                title="Industry outbound approval",
                summary="Industry scope says outbound approval is blocked.",
                entity_keys=["outbound", "approval"],
                opinion_keys=["approval:caution:block"],
            ),
            _fact_entry(
                "fact-context",
                scope_type="work_context",
                scope_id="ctx-1",
                title="Current outbound approval",
                summary="This work context is blocked on outbound approval.",
                entity_keys=["outbound", "approval"],
                opinion_keys=["approval:caution:block"],
            ),
        ],
        entity_views=[],
        opinion_views=[],
        profile_view=None,
        episode_views=[],
        strategy_payload=None,
    )

    assert result.activated_neurons
    assert result.activated_neurons[0].scope_type == "work_context"
    assert result.activated_neurons[0].scope_id == "ctx-1"


def test_activation_service_scores_scope_match_higher_than_global_fallback() -> None:
    service = MemoryActivationService(
        derived_index_service=SimpleNamespace(),
        strategy_memory_service=SimpleNamespace(),
    )

    result = service.activate(
        ActivationInput(
            query_text="review outbound execution failure",
            work_context_id="ctx-1",
        ),
        fact_entries=[
            _fact_entry(
                "fact-global",
                scope_type="global",
                scope_id="runtime",
                title="Outbound execution failure",
                summary="Global note on outbound execution failure.",
                entity_keys=["outbound", "execution"],
                confidence=0.95,
                quality_score=0.95,
            ),
            _fact_entry(
                "fact-context",
                scope_type="work_context",
                scope_id="ctx-1",
                title="Context execution failure",
                summary="The current work context hit an outbound execution failure.",
                entity_keys=["outbound", "execution"],
                confidence=0.6,
                quality_score=0.6,
            ),
        ],
        entity_views=[],
        opinion_views=[],
        profile_view=None,
        episode_views=[],
        strategy_payload=None,
    )

    assert result.activated_neurons[0].scope_id == "ctx-1"
    assert result.activated_neurons[0].activation_score > result.activated_neurons[1].activation_score


def test_activation_service_collects_support_and_contradiction_refs() -> None:
    service = MemoryActivationService(
        derived_index_service=SimpleNamespace(),
        strategy_memory_service=SimpleNamespace(),
    )

    result = service.activate(
        ActivationInput(
            query_text="approval blocked pending evidence review",
            work_context_id="ctx-1",
        ),
        fact_entries=[
            _fact_entry(
                "fact-1",
                scope_type="work_context",
                scope_id="ctx-1",
                title="Approval blocked",
                summary="Approval is blocked pending evidence review.",
                entity_keys=["approval"],
                opinion_keys=["approval:caution:evidence-review"],
                evidence_refs=["evidence-1"],
                source_ref="chunk-1",
            )
        ],
        entity_views=[
            _entity_view(
                "entity-1",
                entity_key="approval",
                scope_type="work_context",
                scope_id="ctx-1",
                summary="Approval is the constrained decision point.",
                supporting_refs=["fact-1", "chunk-1"],
                contradicting_refs=["fact-legacy"],
            )
        ],
        opinion_views=[
            _opinion_view(
                "opinion-1",
                subject_key="approval",
                opinion_key="approval:caution:evidence-review",
                scope_type="work_context",
                scope_id="ctx-1",
                summary="Approval should wait for evidence review.",
                supporting_refs=["fact-1", "chunk-1"],
                contradicting_refs=["fact-legacy"],
                entity_keys=["approval"],
            )
        ],
        profile_view=None,
        episode_views=[],
        strategy_payload=None,
    )

    assert "evidence-1" in result.evidence_refs
    assert "fact-1" in result.support_refs
    assert result.contradictions


def test_activation_service_activate_for_query_pulls_entity_and_opinion_views() -> None:
    calls: dict[str, list[dict[str, object]]] = {
        "fact": [],
        "entity": [],
        "opinion": [],
    }

    def _list_fact_entries(**kwargs: object) -> list[object]:
        calls["fact"].append(dict(kwargs))
        return [
            _fact_entry(
                "fact-1",
                scope_type="industry",
                scope_id="industry-1",
                title="Outbound approval blocked",
                summary="Approval is blocked pending outbound evidence review.",
                entity_keys=["outbound", "approval"],
                opinion_keys=["approval:caution:evidence-review"],
                source_ref="chunk-1",
            ),
        ]

    def _list_entity_views(**kwargs: object) -> list[object]:
        calls["entity"].append(dict(kwargs))
        return [
            _entity_view(
                "entity-1",
                entity_key="outbound",
                scope_type="industry",
                scope_id="industry-1",
                summary="Outbound is the constrained execution lane.",
                supporting_refs=["fact-1", "chunk-1"],
            ),
        ]

    def _list_opinion_views(**kwargs: object) -> list[object]:
        calls["opinion"].append(dict(kwargs))
        return [
            _opinion_view(
                "opinion-1",
                subject_key="approval",
                opinion_key="approval:caution:evidence-review",
                scope_type="industry",
                scope_id="industry-1",
                summary="Approval should wait for evidence review.",
                supporting_refs=["fact-1", "chunk-1"],
                entity_keys=["approval", "outbound"],
            ),
        ]

    service = MemoryActivationService(
        derived_index_service=SimpleNamespace(
            list_fact_entries=_list_fact_entries,
            list_entity_views=_list_entity_views,
            list_opinion_views=_list_opinion_views,
        ),
        strategy_memory_service=SimpleNamespace(),
    )

    result = service.activate_for_query(
        query="blocked outbound approval",
        industry_instance_id="industry-1",
        owner_agent_id="agent-main-brain",
        limit=6,
    )

    neuron_ids = {item.neuron_id for item in result.activated_neurons}
    assert {"fact-1", "entity-1", "opinion-1"} <= neuron_ids
    assert "outbound" in result.top_entities
    assert "approval:caution:evidence-review" in result.top_opinions
    assert calls["fact"][0]["scope_type"] == "industry"
    assert calls["entity"][0]["scope_id"] == "industry-1"
    assert calls["opinion"][0]["owner_agent_id"] == "agent-main-brain"


def test_activation_service_activate_for_query_uses_shared_strategy_resolver_and_relation_views() -> None:
    calls: dict[str, list[dict[str, object]]] = {
        "relation": [],
    }

    def _list_relation_views(**kwargs: object) -> list[object]:
        calls["relation"].append(dict(kwargs))
        return [
            _relation_view(
                "relation-1",
                relation_kind="contradicts",
                scope_type="industry",
                scope_id="industry-1",
                summary="Approval evidence contradicts the current warehouse release assumption.",
                source_refs=["chunk-approval-1"],
            ),
            _relation_view(
                "relation-2",
                relation_kind="supports",
                scope_type="industry",
                scope_id="industry-1",
                summary="Inventory evidence supports the weekend staffing caution.",
                source_refs=["chunk-weekend-1"],
            ),
        ]

    strategy_service = SimpleNamespace(
        get_active_strategy=lambda **_: (_ for _ in ()).throw(
            AssertionError("activate_for_query should use resolve_strategy_payload helper"),
        ),
    )
    service = MemoryActivationService(
        derived_index_service=SimpleNamespace(
            list_fact_entries=lambda **_: [],
            list_entity_views=lambda **_: [],
            list_opinion_views=lambda **_: [],
            list_relation_views=_list_relation_views,
        ),
        strategy_memory_service=strategy_service,
    )

    with patch(
        "copaw.memory.activation_service.resolve_strategy_payload",
        return_value={
            "strategy_id": "strategy:industry:industry-1:agent-main-brain",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "title": "Industry strategy",
            "summary": "Protect release quality before expanding the lane.",
            "execution_constraints": ["Do not release until contradictions are resolved."],
            "current_focuses": ["Resolve warehouse approval contradiction."],
        },
    ) as resolve_strategy_payload_mock:
        result = service.activate_for_query(
            query="warehouse approval contradiction",
            industry_instance_id="industry-1",
            owner_agent_id="agent-main-brain",
            limit=6,
        )

    resolve_strategy_payload_mock.assert_called_once()
    assert calls["relation"][0]["scope_type"] == "industry"
    assert calls["relation"][0]["scope_id"] == "industry-1"
    assert result.metadata["top_relation_kinds"] == ["contradicts", "supports"]
    assert result.metadata["top_relations"] == [
        "Approval evidence contradicts the current warehouse release assumption.",
        "Inventory evidence supports the weekend staffing caution.",
    ]
    assert [item.relation_id for item in result.top_relation_evidence] == [
        "relation-1",
        "relation-2",
    ]
    assert result.top_relation_evidence[0].relation_kind == "contradicts"
    assert result.top_relation_evidence[0].source_refs == ["chunk-approval-1"]


def test_derived_index_service_persists_relation_views_from_fact_entity_links() -> None:
    fact_entries = [
        _fact_entry(
            "fact-1",
            scope_type="work_context",
            scope_id="ctx-1",
            title="Approval remains blocked",
            summary="Approval remains blocked pending evidence review by finance.",
            entity_keys=["approval", "finance"],
            opinion_keys=["approval:caution:evidence-review"],
            source_ref="chunk-1",
        )
    ]
    entity_views = [
        _entity_view(
            "entity-approval",
            entity_key="approval",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval is the constrained decision point.",
            supporting_refs=["fact-1", "chunk-1"],
            related_entities=["finance"],
        ),
        _entity_view(
            "entity-finance",
            entity_key="finance",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Finance owns the evidence review queue.",
            supporting_refs=["fact-1", "chunk-1"],
        ),
    ]
    opinion_views = [
        _opinion_view(
            "opinion-1",
            subject_key="approval",
            opinion_key="approval:caution:evidence-review",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval should wait for evidence review.",
            supporting_refs=["fact-1", "chunk-1"],
            entity_keys=["approval", "finance"],
        )
    ]
    relation_repository = _RelationViewRepository()
    service = DerivedMemoryIndexService(
        fact_index_repository=SimpleNamespace(
            list_entries=lambda **_: fact_entries,
        ),
        entity_view_repository=SimpleNamespace(
            list_views=lambda **_: entity_views,
        ),
        opinion_view_repository=SimpleNamespace(
            list_views=lambda **_: opinion_views,
        ),
        relation_view_repository=relation_repository,
    )

    relation_views = service.rebuild_relation_views(
        scope_type="work_context",
        scope_id="ctx-1",
    )

    assert relation_repository.clear_calls == [("work_context", "ctx-1")]
    assert relation_views
    assert any(
        view.source_node_id == "fact-1"
        and view.target_node_id == "entity-approval"
        and view.relation_kind == "mentions"
        for view in relation_views
    )
    assert any(
        view.source_node_id == "fact-1"
        and view.target_node_id == "opinion-1"
        and view.relation_kind == "supports"
        for view in relation_views
    )
    assert any(
        view.source_node_id == "opinion-1"
        and view.target_node_id == "entity-approval"
        and view.relation_kind in {"mentions", "supports"}
        for view in relation_views
    )
    assert service.list_relation_views(
        scope_type="work_context",
        scope_id="ctx-1",
    ) == relation_views


def test_derived_index_service_list_relation_views_normalizes_scope_filters() -> None:
    fact_entries = [
        _fact_entry(
            "fact-1",
            scope_type="work_context",
            scope_id="ctx-1",
            title="Approval remains blocked",
            summary="Approval remains blocked pending evidence review.",
            entity_keys=["approval"],
            opinion_keys=["approval:caution:evidence-review"],
            source_ref="chunk-1",
        )
    ]
    entity_views = [
        _entity_view(
            "entity-approval",
            entity_key="approval",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval is the constrained decision point.",
            supporting_refs=["fact-1", "chunk-1"],
        )
    ]
    opinion_views = [
        _opinion_view(
            "opinion-1",
            subject_key="approval",
            opinion_key="approval:caution:evidence-review",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval should wait for evidence review.",
            supporting_refs=["fact-1", "chunk-1"],
            entity_keys=["approval"],
        )
    ]
    relation_repository = _RelationViewRepository()
    service = DerivedMemoryIndexService(
        fact_index_repository=SimpleNamespace(
            list_entries=lambda **_: fact_entries,
        ),
        entity_view_repository=SimpleNamespace(
            list_views=lambda **_: entity_views,
        ),
        opinion_view_repository=SimpleNamespace(
            list_views=lambda **_: opinion_views,
        ),
        relation_view_repository=relation_repository,
    )

    service.rebuild_relation_views(
        scope_type="work_context",
        scope_id="ctx-1",
    )

    filtered = service.list_relation_views(
        scope_type=" Work_Context ",
        scope_id=" ctx-1 ",
        relation_kind="supports",
        target_node_id="opinion-1",
    )

    assert len(filtered) == 1
    assert filtered[0].relation_kind == "supports"
    assert filtered[0].scope_type == "work_context"
    assert filtered[0].scope_id == "ctx-1"


def test_derived_index_service_relation_views_do_not_cross_scope_boundaries() -> None:
    fact_entries = [
        _fact_entry(
            "fact-ctx-1",
            scope_type="work_context",
            scope_id="ctx-1",
            title="Approval remains blocked",
            summary="Approval remains blocked pending evidence review.",
            entity_keys=["approval"],
            opinion_keys=["approval:caution:evidence-review"],
            source_ref="chunk-ctx-1",
        ),
        _fact_entry(
            "fact-ctx-2",
            scope_type="work_context",
            scope_id="ctx-2",
            title="Approval is clear",
            summary="Approval is clear in the second context.",
            entity_keys=["approval"],
            opinion_keys=["approval:caution:evidence-review"],
            source_ref="chunk-ctx-2",
        ),
    ]
    entity_views = [
        _entity_view(
            "entity-approval-ctx-1",
            entity_key="approval",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval in ctx-1.",
            supporting_refs=["fact-ctx-1", "chunk-ctx-1"],
        ),
        _entity_view(
            "entity-approval-ctx-2",
            entity_key="approval",
            scope_type="work_context",
            scope_id="ctx-2",
            summary="Approval in ctx-2.",
            supporting_refs=["fact-ctx-2", "chunk-ctx-2"],
        ),
    ]
    opinion_views = [
        _opinion_view(
            "opinion-ctx-1",
            subject_key="approval",
            opinion_key="approval:caution:evidence-review",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval in ctx-1 should wait for evidence review.",
            supporting_refs=["fact-ctx-1", "chunk-ctx-1"],
            entity_keys=["approval"],
        ),
        _opinion_view(
            "opinion-ctx-2",
            subject_key="approval",
            opinion_key="approval:caution:evidence-review",
            scope_type="work_context",
            scope_id="ctx-2",
            summary="Approval in ctx-2 is already clear.",
            supporting_refs=["fact-ctx-2", "chunk-ctx-2"],
            entity_keys=["approval"],
        ),
    ]
    relation_repository = _RelationViewRepository()
    service = DerivedMemoryIndexService(
        fact_index_repository=SimpleNamespace(
            list_entries=lambda **_: fact_entries,
        ),
        entity_view_repository=SimpleNamespace(
            list_views=lambda **_: entity_views,
        ),
        opinion_view_repository=SimpleNamespace(
            list_views=lambda **_: opinion_views,
        ),
        relation_view_repository=relation_repository,
    )

    relation_views = service.rebuild_relation_views()

    relation_pairs = {
        (view.source_node_id, view.target_node_id)
        for view in relation_views
    }
    assert relation_pairs == {
        ("fact-ctx-1", "entity-approval-ctx-1"),
        ("fact-ctx-1", "opinion-ctx-1"),
        ("opinion-ctx-1", "entity-approval-ctx-1"),
        ("fact-ctx-2", "entity-approval-ctx-2"),
        ("fact-ctx-2", "opinion-ctx-2"),
        ("opinion-ctx-2", "entity-approval-ctx-2"),
    }


def test_derived_index_service_relation_views_use_evidence_refs_for_support_trace() -> None:
    fact_entries = [
        _fact_entry(
            "fact-1",
            scope_type="work_context",
            scope_id="ctx-1",
            title="Approval remains blocked",
            summary="Approval remains blocked pending evidence review.",
            entity_keys=["approval"],
            opinion_keys=["approval:caution:evidence-review"],
            evidence_refs=["evidence-1"],
            source_ref="chunk-1",
        )
    ]
    entity_views = [
        _entity_view(
            "entity-approval",
            entity_key="approval",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval is the constrained decision point.",
            supporting_refs=["evidence-1"],
        )
    ]
    opinion_views = [
        _opinion_view(
            "opinion-1",
            subject_key="approval",
            opinion_key="approval:caution:evidence-review",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval should wait for evidence review.",
            supporting_refs=["evidence-1"],
            entity_keys=["approval"],
        )
    ]
    relation_repository = _RelationViewRepository()
    service = DerivedMemoryIndexService(
        fact_index_repository=SimpleNamespace(
            list_entries=lambda **_: fact_entries,
        ),
        entity_view_repository=SimpleNamespace(
            list_views=lambda **_: entity_views,
        ),
        opinion_view_repository=SimpleNamespace(
            list_views=lambda **_: opinion_views,
        ),
        relation_view_repository=relation_repository,
    )

    relation_views = service.rebuild_relation_views(
        scope_type="work_context",
        scope_id="ctx-1",
    )

    fact_to_opinion = next(
        view
        for view in relation_views
        if view.source_node_id == "fact-1" and view.target_node_id == "opinion-1"
    )
    assert fact_to_opinion.relation_kind == "supports"
    assert "chunk-1" in fact_to_opinion.source_refs
    assert "evidence-1" in fact_to_opinion.source_refs
