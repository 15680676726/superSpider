# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Iterable

from .activation_models import (
    ActivationInput,
    ActivationRelationEvidence,
    ActivationResult,
    KnowledgeNeuron,
)
from ..state.strategy_memory_service import resolve_strategy_payload

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}")


def _tokenize(text: object | None) -> list[str]:
    raw = str(text or "").strip().lower()
    if not raw:
        return []
    return [token for token in _TOKEN_RE.findall(raw) if len(token) > 1]


def _dedupe(values: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


class MemoryActivationService:
    def __init__(self, *, derived_index_service, strategy_memory_service=None) -> None:
        self._derived_index_service = derived_index_service
        self._strategy_memory_service = strategy_memory_service

    def activate_for_query(
        self,
        *,
        query: str,
        role: str | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        agent_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        global_scope_id: str | None = None,
        capability_ref: str | None = None,
        environment_ref: str | None = None,
        risk_level: str | None = None,
        current_phase: str | None = None,
        include_strategy: bool = True,
        include_reports: bool = True,
        limit: int = 12,
    ) -> ActivationResult:
        _ = (role, scope_type, scope_id, global_scope_id)
        activation_input = ActivationInput(
            query_text=query,
            work_context_id=work_context_id,
            task_id=task_id,
            agent_id=agent_id or owner_agent_id,
            industry_instance_id=industry_instance_id,
            owner_agent_id=owner_agent_id,
            capability_ref=capability_ref,
            environment_ref=environment_ref,
            risk_level=risk_level,
            current_phase=current_phase,
            include_strategy=include_strategy,
            include_reports=include_reports,
            limit=limit,
        )
        resolved_scope_type = self._resolve_scope_type(activation_input)
        resolved_scope_id = self._resolve_scope_id(activation_input)
        fact_entries = []
        list_fact_entries = getattr(self._derived_index_service, "list_fact_entries", None)
        if callable(list_fact_entries):
            fact_entries = list(
                list_fact_entries(
                    scope_type=resolved_scope_type,
                    scope_id=resolved_scope_id,
                    owner_agent_id=owner_agent_id,
                    industry_instance_id=industry_instance_id,
                    limit=max(limit * 2, 12),
                )
                or [],
            )
        entity_views = self._list_derived_views(
            method_name="list_entity_views",
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            limit=max(limit, 12),
        )
        opinion_views = self._list_derived_views(
            method_name="list_opinion_views",
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            limit=max(limit, 12),
        )
        relation_views = self._list_derived_views(
            method_name="list_relation_views",
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            limit=max(limit, 12),
        )
        strategy_payload = self._resolve_strategy_payload(
            activation_input=activation_input,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
        )
        return self.activate(
            activation_input,
            fact_entries=fact_entries,
            entity_views=entity_views,
            opinion_views=opinion_views,
            relation_views=relation_views,
            profile_view=None,
            episode_views=[],
            strategy_payload=strategy_payload,
        )

    def activate(
        self,
        activation_input: ActivationInput,
        *,
        fact_entries,
        entity_views,
        opinion_views,
        relation_views=None,
        profile_view,
        episode_views,
        strategy_payload,
    ) -> ActivationResult:
        seed_terms = _tokenize(activation_input.query_text)
        neurons = [
            *[self._materialize_fact(entry) for entry in fact_entries],
            *[self._materialize_entity(view) for view in entity_views],
            *[self._materialize_opinion(view) for view in opinion_views],
        ]
        if profile_view is not None:
            neurons.append(self._materialize_profile(profile_view))
        neurons.extend(self._materialize_episode(view) for view in episode_views)
        if strategy_payload and activation_input.include_strategy:
            neurons.append(self._materialize_strategy(strategy_payload, activation_input))

        for neuron in neurons:
            neuron.activation_score = self._score_neuron(neuron, activation_input, seed_terms)

        self._spread_relations(neurons)
        top_relations, top_relation_kinds, top_relation_evidence = self._summarize_relations(
            relation_views=relation_views or [],
            activation_input=activation_input,
            seed_terms=seed_terms,
        )

        activated_neurons = sorted(
            neurons,
            key=lambda item: (item.activation_score, item.kind == "fact", item.title.lower()),
            reverse=True,
        )[: activation_input.limit]

        contradictions = [
            neuron
            for neuron in activated_neurons
            if neuron.metadata.get("contradicting_refs")
        ]
        support_refs = _dedupe(
            ref
            for neuron in activated_neurons
            for ref in [
                *list(neuron.metadata.get("supporting_refs") or []),
                *list(neuron.source_refs),
            ]
        )
        evidence_refs = _dedupe(
            ref
            for neuron in activated_neurons
            for ref in neuron.evidence_refs
        )
        strategy_refs = _dedupe(
            ref
            for neuron in activated_neurons
            if neuron.kind == "strategy"
            for ref in [neuron.neuron_id, *neuron.source_refs]
        )

        return ActivationResult(
            query=activation_input.query_text,
            scope_type=self._resolve_scope_type(activation_input),
            scope_id=self._resolve_scope_id(activation_input),
            seed_terms=seed_terms,
            activated_neurons=activated_neurons,
            contradictions=contradictions,
            support_refs=support_refs,
            evidence_refs=evidence_refs,
            strategy_refs=strategy_refs,
            top_entities=self._collect_top_terms(activated_neurons, attribute="entity_keys"),
            top_opinions=self._collect_top_terms(activated_neurons, attribute="opinion_keys"),
            top_relations=top_relations,
            top_relation_kinds=top_relation_kinds,
            top_relation_evidence=top_relation_evidence,
            top_constraints=_dedupe((strategy_payload or {}).get("execution_constraints") or []),
            top_next_actions=_dedupe((strategy_payload or {}).get("current_focuses") or []),
            metadata={
                "seed_term_count": len(seed_terms),
                "activated_count": len(activated_neurons),
                "top_relations": top_relations,
                "top_relation_kinds": top_relation_kinds,
                "top_relation_evidence": [
                    item.model_dump(mode="json", exclude_none=True)
                    for item in top_relation_evidence
                ],
            },
        )

    def _materialize_fact(self, entry: object) -> KnowledgeNeuron:
        return KnowledgeNeuron(
            neuron_id=str(getattr(entry, "id")),
            kind="fact",
            scope_type=str(getattr(entry, "scope_type", "global")),
            scope_id=str(getattr(entry, "scope_id", "runtime")),
            owner_agent_id=self._optional_text(getattr(entry, "owner_agent_id", None)),
            industry_instance_id=self._optional_text(getattr(entry, "industry_instance_id", None)),
            title=str(getattr(entry, "title", "")),
            summary=str(getattr(entry, "summary", "")),
            content_excerpt=str(getattr(entry, "content_excerpt", "")),
            entity_keys=list(getattr(entry, "entity_keys", []) or []),
            opinion_keys=list(getattr(entry, "opinion_keys", []) or []),
            tags=list(getattr(entry, "tags", []) or []),
            source_refs=_dedupe([str(getattr(entry, "source_ref", "") or "")]),
            evidence_refs=list(getattr(entry, "evidence_refs", []) or []),
            confidence=float(getattr(entry, "confidence", 0.0) or 0.0),
            quality_score=float(getattr(entry, "quality_score", 0.0) or 0.0),
            freshness_score=self._freshness_score(getattr(entry, "source_updated_at", None)),
            metadata=dict(getattr(entry, "metadata", {}) or {}),
        )

    def _materialize_entity(self, view: object) -> KnowledgeNeuron:
        return KnowledgeNeuron(
            neuron_id=str(getattr(view, "entity_id")),
            kind="entity",
            scope_type=str(getattr(view, "scope_type", "global")),
            scope_id=str(getattr(view, "scope_id", "runtime")),
            owner_agent_id=self._optional_text(getattr(view, "owner_agent_id", None)),
            industry_instance_id=self._optional_text(getattr(view, "industry_instance_id", None)),
            title=str(getattr(view, "display_name", getattr(view, "entity_key", ""))),
            summary=str(getattr(view, "summary", "")),
            content_excerpt=str(getattr(view, "summary", "")),
            entity_keys=_dedupe(
                [
                    str(getattr(view, "entity_key", "") or ""),
                    *list(getattr(view, "related_entities", []) or []),
                ]
            ),
            tags=[str(getattr(view, "entity_type", "concept"))],
            source_refs=list(getattr(view, "source_refs", []) or []),
            confidence=float(getattr(view, "confidence", 0.0) or 0.0),
            quality_score=float(getattr(view, "confidence", 0.0) or 0.0),
            metadata={
                **dict(getattr(view, "metadata", {}) or {}),
                "supporting_refs": list(getattr(view, "supporting_refs", []) or []),
                "contradicting_refs": list(getattr(view, "contradicting_refs", []) or []),
            },
        )

    def _materialize_opinion(self, view: object) -> KnowledgeNeuron:
        return KnowledgeNeuron(
            neuron_id=str(getattr(view, "opinion_id")),
            kind="opinion",
            scope_type=str(getattr(view, "scope_type", "global")),
            scope_id=str(getattr(view, "scope_id", "runtime")),
            owner_agent_id=self._optional_text(getattr(view, "owner_agent_id", None)),
            industry_instance_id=self._optional_text(getattr(view, "industry_instance_id", None)),
            title=str(getattr(view, "opinion_key", "")),
            summary=str(getattr(view, "summary", "")),
            content_excerpt=str(getattr(view, "summary", "")),
            entity_keys=list(getattr(view, "entity_keys", []) or []),
            opinion_keys=_dedupe(
                [
                    str(getattr(view, "opinion_key", "") or ""),
                    str(getattr(view, "subject_key", "") or ""),
                ]
            ),
            tags=[str(getattr(view, "stance", "neutral"))],
            source_refs=list(getattr(view, "source_refs", []) or []),
            confidence=float(getattr(view, "confidence", 0.0) or 0.0),
            quality_score=float(getattr(view, "confidence", 0.0) or 0.0),
            metadata={
                **dict(getattr(view, "metadata", {}) or {}),
                "supporting_refs": list(getattr(view, "supporting_refs", []) or []),
                "contradicting_refs": list(getattr(view, "contradicting_refs", []) or []),
            },
        )

    def _materialize_profile(self, view: object) -> KnowledgeNeuron:
        return KnowledgeNeuron(
            neuron_id=str(getattr(view, "profile_id", "memory-profile")),
            kind="profile",
            scope_type=str(getattr(view, "scope_type", "global")),
            scope_id=str(getattr(view, "scope_id", "runtime")),
            owner_agent_id=self._optional_text(getattr(view, "owner_agent_id", None)),
            industry_instance_id=self._optional_text(getattr(view, "industry_instance_id", None)),
            title="Memory Profile",
            summary=str(getattr(view, "current_focus_summary", "")),
            content_excerpt=str(getattr(view, "dynamic_profile", "")),
            tags=["profile"],
            source_refs=list(getattr(view, "source_refs", []) or []),
        )

    def _materialize_episode(self, view: object) -> KnowledgeNeuron:
        return KnowledgeNeuron(
            neuron_id=str(getattr(view, "episode_id")),
            kind="episode",
            scope_type=str(getattr(view, "scope_type", "global")),
            scope_id=str(getattr(view, "scope_id", "runtime")),
            owner_agent_id=self._optional_text(getattr(view, "owner_agent_id", None)),
            industry_instance_id=self._optional_text(getattr(view, "industry_instance_id", None)),
            title=str(getattr(view, "headline", "")),
            summary=str(getattr(view, "summary", "")),
            content_excerpt=str(getattr(view, "summary", "")),
            tags=["episode"],
            source_refs=list(getattr(view, "source_refs", []) or []),
            evidence_refs=list(getattr(view, "evidence_refs", []) or []),
        )

    def _materialize_strategy(
        self,
        strategy_payload: dict[str, Any],
        activation_input: ActivationInput,
    ) -> KnowledgeNeuron:
        strategy_id = str(
            strategy_payload.get("strategy_id")
            or strategy_payload.get("id")
            or f"strategy:{self._resolve_scope_type(activation_input)}:{self._resolve_scope_id(activation_input)}"
        )
        return KnowledgeNeuron(
            neuron_id=strategy_id,
            kind="strategy",
            scope_type=str(strategy_payload.get("scope_type") or self._resolve_scope_type(activation_input)),
            scope_id=str(strategy_payload.get("scope_id") or self._resolve_scope_id(activation_input)),
            owner_agent_id=self._optional_text(strategy_payload.get("owner_agent_id")),
            industry_instance_id=self._optional_text(strategy_payload.get("industry_instance_id")),
            title=str(strategy_payload.get("title") or "Strategy Memory"),
            summary=str(strategy_payload.get("summary") or ""),
            content_excerpt=str(strategy_payload.get("mission") or ""),
            tags=["strategy"],
            source_refs=_dedupe([str(strategy_payload.get("source_ref") or "")]),
            metadata=dict(strategy_payload),
        )

    def _score_neuron(
        self,
        neuron: KnowledgeNeuron,
        activation_input: ActivationInput,
        seed_terms: list[str],
    ) -> float:
        score = self._scope_score(neuron, activation_input)
        score += neuron.confidence * 15.0
        score += neuron.quality_score * 10.0
        score += neuron.freshness_score * 5.0
        score += self._query_overlap_score(neuron, seed_terms)
        if neuron.kind == "fact":
            score += 2.0
        return round(score, 4)

    def _spread_relations(self, neurons: list[KnowledgeNeuron]) -> None:
        fact_neurons = [neuron for neuron in neurons if neuron.kind == "fact"]
        if not fact_neurons:
            return
        fact_refs = {
            ref
            for neuron in fact_neurons
            for ref in [neuron.neuron_id, *neuron.source_refs]
        }
        fact_entities = {
            entity
            for neuron in fact_neurons
            for entity in neuron.entity_keys
        }
        fact_opinions = {
            opinion
            for neuron in fact_neurons
            for opinion in neuron.opinion_keys
        }
        for neuron in neurons:
            if neuron.kind == "fact":
                continue
            support_refs = set(neuron.metadata.get("supporting_refs") or [])
            contradiction_refs = set(neuron.metadata.get("contradicting_refs") or [])
            overlap_entities = fact_entities.intersection(neuron.entity_keys)
            overlap_opinions = fact_opinions.intersection(neuron.opinion_keys)
            if support_refs.intersection(fact_refs):
                neuron.activation_score += 18.0
            if overlap_entities:
                neuron.activation_score += 8.0 + float(len(overlap_entities))
            if overlap_opinions:
                neuron.activation_score += 10.0 + float(len(overlap_opinions))
            if contradiction_refs:
                neuron.activation_score += 3.0

    def _query_overlap_score(self, neuron: KnowledgeNeuron, seed_terms: list[str]) -> float:
        if not seed_terms:
            return 0.0
        corpus = set(
            _tokenize(neuron.title)
            + _tokenize(neuron.summary)
            + _tokenize(neuron.content_excerpt)
            + [item.lower() for item in neuron.entity_keys]
            + [item.lower() for item in neuron.opinion_keys]
            + [item.lower() for item in neuron.tags]
        )
        overlap = sum(1 for term in seed_terms if term in corpus)
        return float(overlap * 4)

    def _scope_score(self, neuron: KnowledgeNeuron, activation_input: ActivationInput) -> float:
        if (
            activation_input.work_context_id
            and neuron.scope_type == "work_context"
            and neuron.scope_id == activation_input.work_context_id
        ):
            return 40.0
        if activation_input.task_id and neuron.scope_type == "task" and neuron.scope_id == activation_input.task_id:
            return 34.0
        if (
            activation_input.industry_instance_id
            and neuron.scope_type == "industry"
            and neuron.scope_id == activation_input.industry_instance_id
        ):
            return 26.0
        if activation_input.agent_id and neuron.scope_type == "agent" and neuron.scope_id == activation_input.agent_id:
            return 22.0
        if neuron.scope_type == "global":
            return 12.0
        return 0.0

    def _resolve_strategy_payload(
        self,
        *,
        activation_input: ActivationInput,
        owner_agent_id: str | None,
        industry_instance_id: str | None,
    ) -> dict[str, Any] | None:
        strategy_payload = resolve_strategy_payload(
            service=self._strategy_memory_service,
            scope_type=(
                "industry"
                if industry_instance_id
                else "global"
            ),
            scope_id=industry_instance_id or "runtime",
            owner_agent_id=owner_agent_id,
        )
        if strategy_payload is not None:
            return strategy_payload
        return {
            "scope_type": self._resolve_scope_type(activation_input),
            "scope_id": self._resolve_scope_id(activation_input),
        }

    def _freshness_score(self, value: object | None) -> float:
        if not isinstance(value, datetime):
            return 0.0
        updated_at = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        age_days = max((datetime.now(UTC) - updated_at).total_seconds() / 86400.0, 0.0)
        return max(0.0, min(1.0, 1.0 - min(age_days / 30.0, 1.0)))

    def _resolve_scope_type(self, activation_input: ActivationInput) -> str:
        if activation_input.work_context_id:
            return "work_context"
        if activation_input.task_id:
            return "task"
        if activation_input.industry_instance_id:
            return "industry"
        if activation_input.agent_id:
            return "agent"
        return "global"

    def _resolve_scope_id(self, activation_input: ActivationInput) -> str:
        return (
            activation_input.work_context_id
            or activation_input.task_id
            or activation_input.industry_instance_id
            or activation_input.agent_id
            or "runtime"
        )

    def _list_derived_views(
        self,
        *,
        method_name: str,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None,
        industry_instance_id: str | None,
        limit: int,
    ) -> list[object]:
        getter = getattr(self._derived_index_service, method_name, None)
        if not callable(getter):
            return []
        return list(
            getter(
                scope_type=scope_type,
                scope_id=scope_id,
                owner_agent_id=owner_agent_id,
                industry_instance_id=industry_instance_id,
                limit=limit,
            )
            or [],
        )

    def _collect_top_terms(
        self,
        neurons: list[KnowledgeNeuron],
        *,
        attribute: str,
    ) -> list[str]:
        counter: Counter[str] = Counter()
        for neuron in neurons:
            counter.update(getattr(neuron, attribute, []) or [])
        return [value for value, _count in counter.most_common(6)]

    def _summarize_relations(
        self,
        *,
        relation_views: Iterable[object],
        activation_input: ActivationInput,
        seed_terms: list[str],
    ) -> tuple[list[str], list[str], list[ActivationRelationEvidence]]:
        scored: list[tuple[float, ActivationRelationEvidence]] = []
        for relation in list(relation_views or []):
            relation_kind = self._optional_text(getattr(relation, "relation_kind", None)) or "references"
            summary = self._optional_text(getattr(relation, "summary", None)) or " ".join(
                part
                for part in (
                    getattr(relation, "source_node_id", None),
                    relation_kind,
                    getattr(relation, "target_node_id", None),
                )
                if self._optional_text(part)
            )
            if not summary:
                continue
            evidence = ActivationRelationEvidence(
                relation_id=str(getattr(relation, "relation_id")),
                relation_kind=relation_kind,
                summary=summary,
                source_node_id=self._optional_text(getattr(relation, "source_node_id", None)),
                target_node_id=self._optional_text(getattr(relation, "target_node_id", None)),
                confidence=float(getattr(relation, "confidence", 0.0) or 0.0),
                source_refs=_dedupe(getattr(relation, "source_refs", []) or []),
            )
            score = 0.0
            if (
                self._optional_text(getattr(relation, "scope_type", None))
                == self._resolve_scope_type(activation_input)
                and self._optional_text(getattr(relation, "scope_id", None))
                == self._resolve_scope_id(activation_input)
            ):
                score += 10.0
            score += float(
                sum(
                    1
                    for term in seed_terms
                    if term in set(
                        _tokenize(summary)
                        + _tokenize(relation_kind)
                        + _tokenize(evidence.source_node_id)
                        + _tokenize(evidence.target_node_id)
                    )
                )
                * 4
            )
            score += evidence.confidence * 5.0
            scored.append((score, evidence))
        scored.sort(
            key=lambda item: (
                item[0],
                item[1].summary.lower(),
                item[1].relation_id,
            ),
            reverse=True,
        )
        top_relation_evidence = [evidence for _score, evidence in scored[:6]]
        return (
            _dedupe(item.summary for item in top_relation_evidence),
            _dedupe(item.relation_kind for item in top_relation_evidence),
            top_relation_evidence,
        )

    def _optional_text(self, value: object | None) -> str | None:
        text = str(value or "").strip()
        return text or None
