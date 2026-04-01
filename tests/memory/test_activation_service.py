# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

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
