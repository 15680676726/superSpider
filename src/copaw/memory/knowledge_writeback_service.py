# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha1
from typing import Any

from .knowledge_graph_models import (
    KnowledgeGraphNode,
    KnowledgeGraphRelation,
    KnowledgeGraphScope,
    KnowledgeGraphWritebackChange,
)
from ..state import AgentReportRecord

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
