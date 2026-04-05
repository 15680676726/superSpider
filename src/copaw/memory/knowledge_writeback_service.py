# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any

from .knowledge_graph_models import (
    KnowledgeGraphNode,
    KnowledgeGraphRelation,
    KnowledgeGraphScope,
    KnowledgeGraphWritebackChange,
)
from ..state import (
    AgentReportRecord,
    KnowledgeChunkRecord,
    MemoryFactIndexRecord,
)
from ..state.models_memory import MemoryRelationViewRecord

_VERIFIED_REPORT_RESULTS = {"completed", "success"}
_FAILURE_OUTCOMES = {"failed", "blocked", "cancelled", "timeout"}
_HUMAN_BOUNDARY_NODE_TYPES = {
    "instruction",
    "approval",
    "rejection",
    "discussion",
    "consensus",
    "preference",
}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _unique_strings(*collections: object) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for collection in collections:
        if isinstance(collection, str):
            items = [collection]
        elif isinstance(collection, Sequence):
            items = list(collection)
        else:
            items = []
        for item in items:
            text = _string(item)
            if text is None or text in seen:
                continue
            seen.add(text)
            values.append(text)
    return values


def _stable_suffix(*parts: object) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:12]


class KnowledgeWritebackService:
    def __init__(
        self,
        *,
        knowledge_service: object | None = None,
        derived_index_service: object | None = None,
        relation_view_repository: object | None = None,
        reflection_service: object | None = None,
    ) -> None:
        self._knowledge_service = knowledge_service
        self._knowledge_repository = getattr(knowledge_service, "_repository", None)
        self._derived_index_service = (
            derived_index_service
            or getattr(knowledge_service, "_derived_index_service", None)
        )
        self._fact_index_repository = getattr(
            self._derived_index_service,
            "_fact_index_repository",
            None,
        )
        self._relation_view_repository = (
            relation_view_repository
            or getattr(self._derived_index_service, "_relation_view_repository", None)
        )
        self._reflection_service = (
            reflection_service
            or getattr(knowledge_service, "_reflection_service", None)
        )

    def apply_change(
        self,
        change: KnowledgeGraphWritebackChange,
    ) -> dict[str, Any]:
        if not isinstance(change, KnowledgeGraphWritebackChange):
            return {}
        now = datetime.now(timezone.utc)
        for node in change.upsert_nodes:
            self._upsert_node_chunk(node=node, now=now)
            self._upsert_fact_entry(node=node, now=now)
        for relation in change.upsert_relations:
            self._upsert_relation_chunk(relation=relation, now=now)
            self._upsert_relation_view(relation=relation, now=now)
        for node_id in list(change.invalidate_node_ids or []):
            self._invalidate_node(node_id=node_id, now=now)
        for relation_id in list(change.invalidate_relation_ids or []):
            self._invalidate_relation(relation_id=relation_id, now=now)
        self._reflect_scope(change.scope)
        return self.summarize_change(change)

    def build_report_writeback(
        self,
        *,
        report: AgentReportRecord,
        activation_result: object | None = None,
    ) -> KnowledgeGraphWritebackChange:
        _ = activation_result
        scope = self._scope_from_report(report)
        evidence_refs = _unique_strings(report.evidence_ids)
        source_ref = f"agent-report:{report.id}"
        upsert_nodes: list[KnowledgeGraphNode] = []
        upsert_relations: list[KnowledgeGraphRelation] = []

        report_node = KnowledgeGraphNode(
            node_id=f"report:{report.id}",
            node_type="report",
            scope=scope,
            title=report.headline,
            summary=report.summary,
            evidence_refs=evidence_refs,
            source_refs=[source_ref],
            metadata={
                "report_id": report.id,
                "assignment_id": report.assignment_id,
                "task_id": report.task_id,
                "lane_id": report.lane_id,
                "owner_agent_id": report.owner_agent_id,
                "result": report.result,
                "status": report.status,
            },
        )
        upsert_nodes.append(report_node)

        outcome_event = KnowledgeGraphNode(
            node_id=f"report-event:{report.id}",
            node_type="event",
            scope=scope,
            title=f"{report.headline} outcome",
            summary=report.summary or report.headline,
            evidence_refs=evidence_refs,
            source_refs=[source_ref],
            metadata={
                "report_id": report.id,
                "result": report.result,
                "status": report.status,
            },
        )
        upsert_nodes.append(outcome_event)
        upsert_relations.append(
            self._relation(
                relation_type="produces",
                source_id=report_node.node_id,
                target_id=outcome_event.node_id,
                scope=scope,
                evidence_refs=evidence_refs,
                source_refs=[source_ref],
            ),
        )

        evidence_nodes = self._build_evidence_nodes(
            evidence_refs=evidence_refs,
            scope=scope,
            title_prefix=report.headline,
        )
        upsert_nodes.extend(evidence_nodes)

        findings_verified = self._report_findings_verified(report)
        for index, finding in enumerate(list(report.findings or []), start=1):
            finding_node = KnowledgeGraphNode(
                node_id=f"report-finding:{report.id}:{index}",
                node_type="fact" if findings_verified else "opinion",
                scope=scope,
                title=f"{report.headline} finding {index}",
                summary=str(finding),
                evidence_refs=evidence_refs,
                source_refs=[source_ref],
                metadata={
                    "source_kind": "finding",
                    "report_id": report.id,
                    "verified": findings_verified,
                },
            )
            upsert_nodes.append(finding_node)
            upsert_relations.append(
                self._relation(
                    relation_type="produces",
                    source_id=report_node.node_id,
                    target_id=finding_node.node_id,
                    scope=scope,
                    evidence_refs=evidence_refs,
                    source_refs=[source_ref],
                ),
            )
            upsert_relations.extend(
                self._derive_from_evidence_relations(
                    node_id=finding_node.node_id,
                    evidence_nodes=evidence_nodes,
                    scope=scope,
                    source_refs=[source_ref],
                ),
            )

        for index, uncertainty in enumerate(list(report.uncertainties or []), start=1):
            uncertainty_node = KnowledgeGraphNode(
                node_id=f"report-uncertainty:{report.id}:{index}",
                node_type="opinion",
                scope=scope,
                title=f"{report.headline} uncertainty {index}",
                summary=str(uncertainty),
                evidence_refs=evidence_refs,
                source_refs=[source_ref],
                metadata={
                    "source_kind": "uncertainty",
                    "report_id": report.id,
                },
            )
            upsert_nodes.append(uncertainty_node)
            upsert_relations.append(
                self._relation(
                    relation_type="produces",
                    source_id=report_node.node_id,
                    target_id=uncertainty_node.node_id,
                    scope=scope,
                    evidence_refs=evidence_refs,
                    source_refs=[source_ref],
                ),
            )
            upsert_relations.extend(
                self._derive_from_evidence_relations(
                    node_id=uncertainty_node.node_id,
                    evidence_nodes=evidence_nodes,
                    scope=scope,
                    source_refs=[source_ref],
                ),
            )

        recommendation = _string(report.recommendation)
        if recommendation is not None:
            recommendation_node = KnowledgeGraphNode(
                node_id=f"report-recommendation:{report.id}",
                node_type="opinion",
                scope=scope,
                title=f"{report.headline} recommendation",
                summary=recommendation,
                evidence_refs=evidence_refs,
                source_refs=[source_ref],
                metadata={
                    "source_kind": "recommendation",
                    "report_id": report.id,
                },
            )
            upsert_nodes.append(recommendation_node)
            upsert_relations.append(
                self._relation(
                    relation_type="produces",
                    source_id=report_node.node_id,
                    target_id=recommendation_node.node_id,
                    scope=scope,
                    evidence_refs=evidence_refs,
                    source_refs=[source_ref],
                ),
            )
            upsert_relations.extend(
                self._derive_from_evidence_relations(
                    node_id=recommendation_node.node_id,
                    evidence_nodes=evidence_nodes,
                    scope=scope,
                    source_refs=[source_ref],
                ),
            )

        return KnowledgeGraphWritebackChange(
            scope=scope,
            upsert_nodes=upsert_nodes,
            upsert_relations=upsert_relations,
            metadata={
                "source": "agent-report",
                "report_id": report.id,
            },
        )

    def build_report_synthesis_writeback(
        self,
        *,
        reports: Sequence[AgentReportRecord],
        activation_result: object | None = None,
    ) -> KnowledgeGraphWritebackChange:
        changes = [
            self.build_report_writeback(report=report, activation_result=activation_result)
            for report in reports
            if isinstance(report, AgentReportRecord)
        ]
        return self.merge_changes(*changes)

    def build_execution_outcome_writeback(
        self,
        *,
        scope_type: str,
        scope_id: str,
        outcome_ref: str,
        outcome: str,
        summary: str,
        capability_ref: str | None = None,
        evidence_refs: list[str] | None = None,
        recovery_summary: str | None = None,
    ) -> KnowledgeGraphWritebackChange:
        scope = self._scope(scope_type=scope_type, scope_id=scope_id)
        normalized_outcome = (_string(outcome) or "failed").lower()
        normalized_summary = _string(summary) or normalized_outcome
        normalized_evidence_refs = _unique_strings(evidence_refs)

        runtime_outcome_node = KnowledgeGraphNode(
            node_id=f"runtime-outcome:{outcome_ref}",
            node_type="runtime_outcome",
            scope=scope,
            title=f"Runtime outcome {outcome_ref}",
            summary=normalized_summary,
            evidence_refs=normalized_evidence_refs,
            source_refs=[f"runtime-outcome:{outcome_ref}"],
            metadata={
                "outcome": normalized_outcome,
                "capability_ref": capability_ref,
            },
        )
        upsert_nodes = [runtime_outcome_node]
        upsert_relations: list[KnowledgeGraphRelation] = []

        if normalized_outcome in _FAILURE_OUTCOMES:
            failure_node = KnowledgeGraphNode(
                node_id=f"failure-pattern:{_stable_suffix(scope_type, scope_id, capability_ref, normalized_summary)}",
                node_type="failure_pattern",
                scope=scope,
                title=f"{capability_ref or 'runtime'} failure pattern",
                summary=normalized_summary,
                evidence_refs=normalized_evidence_refs,
                source_refs=[f"runtime-outcome:{outcome_ref}"],
                metadata={"outcome": normalized_outcome},
            )
            upsert_nodes.append(failure_node)
            upsert_relations.append(
                self._relation(
                    relation_type="indicates",
                    source_id=runtime_outcome_node.node_id,
                    target_id=failure_node.node_id,
                    scope=scope,
                    evidence_refs=normalized_evidence_refs,
                    source_refs=[f"runtime-outcome:{outcome_ref}"],
                ),
            )
            if recovery_summary:
                recovery_node = KnowledgeGraphNode(
                    node_id=f"recovery-pattern:{_stable_suffix(scope_type, scope_id, capability_ref, recovery_summary)}",
                    node_type="recovery_pattern",
                    scope=scope,
                    title=f"{capability_ref or 'runtime'} recovery pattern",
                    summary=str(recovery_summary),
                    evidence_refs=normalized_evidence_refs,
                    source_refs=[f"runtime-outcome:{outcome_ref}"],
                )
                upsert_nodes.append(recovery_node)
                upsert_relations.append(
                    self._relation(
                        relation_type="recovers_with",
                        source_id=runtime_outcome_node.node_id,
                        target_id=recovery_node.node_id,
                        scope=scope,
                        evidence_refs=normalized_evidence_refs,
                        source_refs=[f"runtime-outcome:{outcome_ref}"],
                    ),
                )

        return KnowledgeGraphWritebackChange(
            scope=scope,
            upsert_nodes=upsert_nodes,
            upsert_relations=upsert_relations,
            metadata={
                "source": "execution-outcome",
                "outcome_ref": outcome_ref,
            },
        )

    def build_human_boundary_writeback(
        self,
        *,
        scope_type: str,
        scope_id: str,
        boundary_kind: str,
        summary: str,
        evidence_refs: list[str] | None = None,
        source_refs: list[str] | None = None,
    ) -> KnowledgeGraphWritebackChange:
        normalized_kind = (_string(boundary_kind) or "").lower()
        if normalized_kind not in _HUMAN_BOUNDARY_NODE_TYPES:
            raise ValueError(f"unsupported human boundary kind: {boundary_kind}")
        scope = self._scope(scope_type=scope_type, scope_id=scope_id)
        node = KnowledgeGraphNode(
            node_id=f"{normalized_kind}:{_stable_suffix(scope_type, scope_id, summary)}",
            node_type=normalized_kind,
            scope=scope,
            title=f"{normalized_kind.title()} boundary",
            summary=summary,
            evidence_refs=_unique_strings(evidence_refs),
            source_refs=_unique_strings(source_refs),
        )
        return KnowledgeGraphWritebackChange(
            scope=scope,
            upsert_nodes=[node],
            metadata={"source": "human-boundary"},
        )

    def summarize_change(
        self,
        change: KnowledgeGraphWritebackChange,
    ) -> dict[str, Any]:
        return {
            "scope_type": change.scope.scope_type,
            "scope_id": change.scope.scope_id,
            "node_ids": [item.node_id for item in change.upsert_nodes],
            "node_types": _unique_strings([item.node_type for item in change.upsert_nodes]),
            "relation_ids": [item.relation_id for item in change.upsert_relations],
            "relation_types": _unique_strings([item.relation_type for item in change.upsert_relations]),
            "evidence_refs": _unique_strings(
                *[item.evidence_refs for item in change.upsert_nodes],
                *[item.evidence_refs for item in change.upsert_relations],
            ),
            "nodes": [
                {
                    "node_id": item.node_id,
                    "node_type": item.node_type,
                    "title": item.title,
                    "source_refs": list(item.source_refs),
                    "evidence_refs": list(item.evidence_refs),
                }
                for item in change.upsert_nodes
            ],
            "relations": [
                {
                    "relation_id": item.relation_id,
                    "relation_type": item.relation_type,
                    "source_id": item.source_id,
                    "target_id": item.target_id,
                    "source_refs": list(item.source_refs),
                    "evidence_refs": list(item.evidence_refs),
                }
                for item in change.upsert_relations
            ],
            "invalidate_node_ids": list(change.invalidate_node_ids),
            "invalidate_relation_ids": list(change.invalidate_relation_ids),
        }

    def merge_changes(
        self,
        *changes: KnowledgeGraphWritebackChange,
    ) -> KnowledgeGraphWritebackChange:
        valid_changes = [change for change in changes if isinstance(change, KnowledgeGraphWritebackChange)]
        if not valid_changes:
            return KnowledgeGraphWritebackChange(
                scope=KnowledgeGraphScope(scope_type="global", scope_id="runtime"),
            )
        scope = valid_changes[0].scope
        nodes_by_id: dict[str, KnowledgeGraphNode] = {}
        relations_by_id: dict[str, KnowledgeGraphRelation] = {}
        invalidate_node_ids: list[str] = []
        invalidate_relation_ids: list[str] = []
        metadata: dict[str, Any] = {}
        for change in valid_changes:
            for node in change.upsert_nodes:
                nodes_by_id[node.node_id] = node
            for relation in change.upsert_relations:
                relations_by_id[relation.relation_id] = relation
            invalidate_node_ids = _unique_strings(invalidate_node_ids, change.invalidate_node_ids)
            invalidate_relation_ids = _unique_strings(
                invalidate_relation_ids,
                change.invalidate_relation_ids,
            )
            metadata.update(dict(change.metadata or {}))
        return KnowledgeGraphWritebackChange(
            scope=scope,
            upsert_nodes=list(nodes_by_id.values()),
            upsert_relations=list(relations_by_id.values()),
            invalidate_node_ids=invalidate_node_ids,
            invalidate_relation_ids=invalidate_relation_ids,
            metadata=metadata,
        )

    def _upsert_node_chunk(
        self,
        *,
        node: KnowledgeGraphNode,
        now: datetime,
    ) -> None:
        repository = self._knowledge_repository
        if repository is None:
            return
        chunk_id = self._node_chunk_id(node.node_id)
        existing = repository.get_chunk(chunk_id) if hasattr(repository, "get_chunk") else None
        document_id = self._memory_document_id(node.scope)
        chunk_index = (
            int(getattr(existing, "chunk_index", 0) or 0)
            if existing is not None
            else self._next_chunk_index(document_id=document_id)
        )
        repository.upsert_chunk(
            KnowledgeChunkRecord(
                id=chunk_id,
                document_id=document_id,
                title=node.title,
                content=self._node_chunk_content(node),
                summary=node.summary or node.title,
                source_ref=chunk_id,
                chunk_index=chunk_index,
                role_bindings=[],
                tags=_unique_strings(
                    "knowledge-graph",
                    "graph-node",
                    f"node-type:{node.node_type}",
                    f"status:{node.status}",
                    node.tags,
                ),
                created_at=getattr(existing, "created_at", None) or now,
                updated_at=now,
            ),
        )

    def _upsert_relation_chunk(
        self,
        *,
        relation: KnowledgeGraphRelation,
        now: datetime,
    ) -> None:
        repository = self._knowledge_repository
        if repository is None:
            return
        chunk_id = self._relation_chunk_id(relation.relation_id)
        existing = repository.get_chunk(chunk_id) if hasattr(repository, "get_chunk") else None
        document_id = self._memory_document_id(relation.scope)
        chunk_index = (
            int(getattr(existing, "chunk_index", 0) or 0)
            if existing is not None
            else self._next_chunk_index(document_id=document_id)
        )
        repository.upsert_chunk(
            KnowledgeChunkRecord(
                id=chunk_id,
                document_id=document_id,
                title=self._relation_title(relation),
                content=self._relation_chunk_content(relation),
                summary=self._relation_summary(relation),
                source_ref=chunk_id,
                chunk_index=chunk_index,
                role_bindings=[],
                tags=_unique_strings(
                    "knowledge-graph",
                    "graph-relation",
                    f"relation-type:{relation.relation_type}",
                    f"status:{relation.status}",
                ),
                created_at=getattr(existing, "created_at", None) or now,
                updated_at=now,
            ),
        )

    def _upsert_fact_entry(
        self,
        *,
        node: KnowledgeGraphNode,
        now: datetime,
    ) -> None:
        repository = self._fact_index_repository
        if repository is None:
            return
        existing = repository.get_entry(node.node_id) if hasattr(repository, "get_entry") else None
        repository.upsert_entry(
            MemoryFactIndexRecord(
                id=node.node_id,
                source_type="knowledge_graph_node",
                source_ref=node.node_id,
                scope_type=node.scope.scope_type,
                scope_id=node.scope.scope_id,
                owner_agent_id=node.scope.owner_agent_id,
                industry_instance_id=node.scope.industry_instance_id,
                title=node.title,
                summary=node.summary or node.title,
                content_excerpt=node.content_excerpt or node.summary or node.title,
                content_text=node.content_excerpt or node.summary or node.title,
                entity_keys=list(node.entity_keys),
                opinion_keys=list(node.opinion_keys),
                tags=_unique_strings(
                    "knowledge-graph",
                    f"node-type:{node.node_type}",
                    node.tags,
                ),
                evidence_refs=list(node.evidence_refs),
                confidence=node.confidence,
                quality_score=node.quality_score or node.confidence,
                memory_type=self._node_memory_type(node.node_type),
                relation_kind="references",
                is_latest=node.status not in {"superseded", "expired"},
                valid_from=now,
                expires_at=now if node.status in {"superseded", "expired"} else None,
                source_updated_at=now,
                metadata={
                    **dict(node.metadata or {}),
                    "knowledge_graph_node_type": node.node_type,
                    "knowledge_graph_status": node.status,
                    "knowledge_graph_source_refs": list(node.source_refs),
                    "knowledge_graph_evidence_refs": list(node.evidence_refs),
                    "knowledge_graph_chunk_id": self._node_chunk_id(node.node_id),
                },
                created_at=getattr(existing, "created_at", None) or now,
                updated_at=now,
            ),
        )

    def _upsert_relation_view(
        self,
        *,
        relation: KnowledgeGraphRelation,
        now: datetime,
    ) -> None:
        repository = self._relation_view_repository
        if repository is None:
            return
        existing = repository.get_view(relation.relation_id) if hasattr(repository, "get_view") else None
        repository.upsert_view(
            MemoryRelationViewRecord(
                relation_id=relation.relation_id,
                source_node_id=relation.source_id,
                target_node_id=relation.target_id,
                relation_kind=relation.relation_type,
                scope_type=relation.scope.scope_type,
                scope_id=relation.scope.scope_id,
                owner_agent_id=relation.scope.owner_agent_id,
                industry_instance_id=relation.scope.industry_instance_id,
                summary=self._relation_summary(relation),
                confidence=relation.confidence,
                source_refs=_unique_strings(relation.source_refs, relation.evidence_refs),
                metadata={
                    **dict(relation.metadata or {}),
                    "status": relation.status,
                    "valid_from": relation.valid_from.isoformat() if relation.valid_from is not None else None,
                    "valid_to": relation.valid_to.isoformat() if relation.valid_to is not None else None,
                    "evidence_refs": list(relation.evidence_refs),
                    "source_refs": list(relation.source_refs),
                    "knowledge_graph_chunk_id": self._relation_chunk_id(relation.relation_id),
                },
                created_at=getattr(existing, "created_at", None) or now,
                updated_at=now,
            ),
        )

    def _invalidate_node(
        self,
        *,
        node_id: str,
        now: datetime,
    ) -> None:
        repository = self._fact_index_repository
        if repository is None:
            return
        existing = repository.get_entry(node_id) if hasattr(repository, "get_entry") else None
        if existing is None:
            return
        metadata = {
            **dict(existing.metadata or {}),
            "knowledge_graph_status": "superseded",
            "invalidated_at": now.isoformat(),
        }
        repository.upsert_entry(
            existing.model_copy(
                update={
                    "is_latest": False,
                    "expires_at": now,
                    "metadata": metadata,
                    "updated_at": now,
                },
            ),
        )
        self._mark_chunk_status(
            chunk_id=self._node_chunk_id(node_id),
            status="superseded",
            now=now,
        )

    def _invalidate_relation(
        self,
        *,
        relation_id: str,
        now: datetime,
    ) -> None:
        repository = self._relation_view_repository
        if repository is None:
            return
        existing = repository.get_view(relation_id) if hasattr(repository, "get_view") else None
        if existing is None:
            return
        metadata = {
            **dict(existing.metadata or {}),
            "status": "superseded",
            "valid_to": now.isoformat(),
            "invalidated_at": now.isoformat(),
        }
        repository.upsert_view(
            existing.model_copy(
                update={
                    "metadata": metadata,
                    "updated_at": now,
                },
            ),
        )
        self._mark_chunk_status(
            chunk_id=self._relation_chunk_id(relation_id),
            status="superseded",
            now=now,
        )

    def _mark_chunk_status(
        self,
        *,
        chunk_id: str,
        status: str,
        now: datetime,
    ) -> None:
        repository = self._knowledge_repository
        if repository is None or not hasattr(repository, "get_chunk"):
            return
        existing = repository.get_chunk(chunk_id)
        if existing is None:
            return
        tags = [
            tag
            for tag in list(existing.tags or [])
            if not str(tag).startswith("status:")
        ]
        repository.upsert_chunk(
            existing.model_copy(
                update={
                    "tags": _unique_strings(tags, f"status:{status}"),
                    "updated_at": now,
                },
            ),
        )

    def _reflect_scope(self, scope: KnowledgeGraphScope) -> None:
        reflect = getattr(self._reflection_service, "reflect", None)
        if not callable(reflect):
            return
        try:
            reflect(
                scope_type=scope.scope_type,
                scope_id=scope.scope_id,
                owner_agent_id=scope.owner_agent_id,
                industry_instance_id=scope.industry_instance_id,
                trigger_kind="knowledge-writeback",
                create_learning_proposals=False,
            )
        except Exception:
            return

    def _next_chunk_index(self, *, document_id: str) -> int:
        repository = self._knowledge_repository
        if repository is None or not hasattr(repository, "list_chunks"):
            return 0
        chunks = repository.list_chunks(document_id=document_id)
        return max((int(getattr(item, "chunk_index", 0) or 0) for item in chunks), default=-1) + 1

    def _node_chunk_id(self, node_id: str) -> str:
        return f"knowledge-graph-node:{node_id}"

    def _relation_chunk_id(self, relation_id: str) -> str:
        return f"knowledge-graph-relation:{relation_id}"

    def _memory_document_id(self, scope: KnowledgeGraphScope) -> str:
        return f"memory:{scope.scope_type}:{scope.scope_id}"

    def _node_chunk_content(self, node: KnowledgeGraphNode) -> str:
        parts = [
            f"Node type: {node.node_type}",
            f"Node id: {node.node_id}",
            f"Status: {node.status}",
            node.summary,
            node.content_excerpt,
        ]
        if node.evidence_refs:
            parts.append(f"Evidence refs: {', '.join(node.evidence_refs)}")
        if node.source_refs:
            parts.append(f"Source refs: {', '.join(node.source_refs)}")
        return "\n".join(part for part in parts if part).strip()

    def _relation_title(self, relation: KnowledgeGraphRelation) -> str:
        return f"{relation.relation_type} relation"

    def _relation_summary(self, relation: KnowledgeGraphRelation) -> str:
        return _string(relation.metadata.get("summary")) or " ".join(
            part
            for part in (
                relation.source_id,
                relation.relation_type,
                relation.target_id,
            )
            if _string(part)
        )

    def _relation_chunk_content(self, relation: KnowledgeGraphRelation) -> str:
        parts = [
            f"Relation type: {relation.relation_type}",
            f"Relation id: {relation.relation_id}",
            f"Source: {relation.source_id}",
            f"Target: {relation.target_id}",
            f"Status: {relation.status}",
            self._relation_summary(relation),
        ]
        if relation.evidence_refs:
            parts.append(f"Evidence refs: {', '.join(relation.evidence_refs)}")
        if relation.source_refs:
            parts.append(f"Source refs: {', '.join(relation.source_refs)}")
        return "\n".join(part for part in parts if part).strip()

    def _node_memory_type(self, node_type: str) -> str:
        normalized = str(node_type or "").strip().lower()
        if normalized in {"event", "runtime_outcome", "report", "cycle", "assignment", "backlog"}:
            return "episode"
        if normalized in {
            "opinion",
            "failure_pattern",
            "recovery_pattern",
            "instruction",
            "approval",
            "rejection",
            "discussion",
            "consensus",
            "preference",
        }:
            return "inference"
        return "fact"

    def _scope_from_report(self, report: AgentReportRecord) -> KnowledgeGraphScope:
        if _string(report.work_context_id):
            return self._scope(scope_type="work_context", scope_id=report.work_context_id)
        if _string(report.industry_instance_id):
            return self._scope(scope_type="industry", scope_id=report.industry_instance_id)
        if _string(report.owner_agent_id):
            return self._scope(scope_type="agent", scope_id=report.owner_agent_id)
        return self._scope(scope_type="global", scope_id="runtime")

    def _scope(self, *, scope_type: str, scope_id: str | None) -> KnowledgeGraphScope:
        return KnowledgeGraphScope(
            scope_type=str(scope_type or "global").strip().lower() or "global",
            scope_id=_string(scope_id) or "runtime",
        )

    def _report_findings_verified(self, report: AgentReportRecord) -> bool:
        marker = report.metadata.get("verified_findings") if isinstance(report.metadata, dict) else None
        if isinstance(marker, bool):
            return marker
        return (_string(report.result) or "").lower() in _VERIFIED_REPORT_RESULTS

    def _build_evidence_nodes(
        self,
        *,
        evidence_refs: list[str],
        scope: KnowledgeGraphScope,
        title_prefix: str,
    ) -> list[KnowledgeGraphNode]:
        return [
            KnowledgeGraphNode(
                node_id=f"evidence:{evidence_id}",
                node_type="evidence",
                scope=scope,
                title=f"{title_prefix} evidence {index}",
                summary=f"Evidence ref {evidence_id}",
                evidence_refs=[evidence_id],
                source_refs=[evidence_id],
            )
            for index, evidence_id in enumerate(evidence_refs, start=1)
        ]

    def _derive_from_evidence_relations(
        self,
        *,
        node_id: str,
        evidence_nodes: Sequence[KnowledgeGraphNode],
        scope: KnowledgeGraphScope,
        source_refs: list[str],
    ) -> list[KnowledgeGraphRelation]:
        return [
            self._relation(
                relation_type="derived_from",
                source_id=node_id,
                target_id=evidence_node.node_id,
                scope=scope,
                evidence_refs=evidence_node.evidence_refs,
                source_refs=source_refs,
            )
            for evidence_node in evidence_nodes
        ]

    def _relation(
        self,
        *,
        relation_type: str,
        source_id: str,
        target_id: str,
        scope: KnowledgeGraphScope,
        evidence_refs: list[str] | None = None,
        source_refs: list[str] | None = None,
    ) -> KnowledgeGraphRelation:
        return KnowledgeGraphRelation(
            relation_id=f"relation:{_stable_suffix(relation_type, source_id, target_id)}",
            relation_type=relation_type,
            source_id=source_id,
            target_id=target_id,
            scope=scope,
            evidence_refs=_unique_strings(evidence_refs),
            source_refs=_unique_strings(source_refs),
        )
