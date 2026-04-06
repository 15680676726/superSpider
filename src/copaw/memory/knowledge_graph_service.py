# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .activation_service import MemoryActivationService
from .knowledge_graph_models import KnowledgeGraphPath, TaskSubgraph
from .knowledge_writeback_service import KnowledgeWritebackService
from .subgraph_activation_service import SubgraphActivationService


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: object | None) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _unique_strings(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, list):
            candidates = value
        else:
            candidates = []
        for candidate in candidates:
            text = _string(candidate)
            if text is None or text in seen:
                continue
            seen.add(text)
            items.append(text)
    return items


def _node_titles(subgraph: TaskSubgraph, *, node_type: str) -> list[str]:
    return _unique_strings(
        [
            getattr(node, "title", None)
            for node in list(subgraph.nodes or [])
            if getattr(node, "node_type", None) == node_type
        ],
    )


def _path_summaries(paths: object | None) -> list[str]:
    summaries: list[object] = []
    for path in list(paths or []) if isinstance(paths, list) else []:
        if isinstance(path, KnowledgeGraphPath):
            summaries.append(getattr(path, "summary", None))
            continue
        if isinstance(path, dict):
            summaries.append(path.get("summary"))
            continue
        summaries.append(path)
    return _unique_strings(summaries)


class KnowledgeGraphService:
    def __init__(
        self,
        *,
        knowledge_service: object | None = None,
        derived_index_service: object | None = None,
        strategy_memory_service: object | None = None,
        memory_activation_service: object | None = None,
        subgraph_activation_service: object | None = None,
        knowledge_writeback_service: object | None = None,
    ) -> None:
        self._knowledge_service = knowledge_service
        self._memory_activation_service = memory_activation_service
        if self._memory_activation_service is None and derived_index_service is not None:
            self._memory_activation_service = MemoryActivationService(
                derived_index_service=derived_index_service,
                strategy_memory_service=strategy_memory_service,
            )
        self._subgraph_activation_service = subgraph_activation_service
        if (
            self._subgraph_activation_service is None
            and self._memory_activation_service is not None
        ):
            self._subgraph_activation_service = SubgraphActivationService(
                memory_activation_service=self._memory_activation_service,
            )
        self._knowledge_writeback_service = (
            knowledge_writeback_service
            or KnowledgeWritebackService(knowledge_service=knowledge_service)
        )

    def activate_for_query(self, **kwargs) -> object | None:
        service = self._memory_activation_service
        activate = getattr(service, "activate_for_query", None)
        if not callable(activate):
            return None
        return activate(**kwargs)

    def activate_task_subgraph(self, **kwargs) -> TaskSubgraph | None:
        service = self._subgraph_activation_service
        activate = getattr(service, "activate_for_query", None)
        if not callable(activate):
            return None
        result = activate(**kwargs)
        return self._coerce_task_subgraph(result)

    def activate_request_task_subgraph(
        self,
        *,
        request: Any,
        intake_contract: object | None = None,
        current_phase: str | None = None,
        limit: int = 12,
    ) -> TaskSubgraph | None:
        query = _string(getattr(intake_contract, "message_text", None)) or _string(
            getattr(request, "message_text", None),
        )
        if query is None:
            return None
        return self.activate_task_subgraph(
            query=query,
            task_id=_string(getattr(request, "task_id", None)),
            work_context_id=_string(getattr(request, "work_context_id", None)),
            owner_agent_id=_string(
                getattr(request, "agent_id", None),
            )
            or _string(getattr(request, "owner_agent_id", None)),
            industry_instance_id=_string(getattr(request, "industry_instance_id", None)),
            current_phase=_string(current_phase) or "main-brain-intake",
            limit=limit,
        )

    def summarize_task_subgraph(self, task_subgraph: object | None) -> dict[str, Any]:
        compact_summary = self._coerce_compact_task_subgraph_summary(task_subgraph)
        if compact_summary is not None:
            return compact_summary
        subgraph = self._coerce_task_subgraph(task_subgraph)
        if subgraph is None:
            return {}
        metadata = _mapping(subgraph.metadata)
        relation_summaries = _unique_strings(
            metadata.get("top_relations"),
            [
                _mapping(getattr(relation, "metadata", None)).get("summary")
                for relation in list(subgraph.relations or [])
            ],
        )
        relation_kinds = _unique_strings(
            metadata.get("top_relation_kinds"),
            [getattr(relation, "relation_type", None) for relation in list(subgraph.relations or [])],
        )
        top_entities = _unique_strings(
            metadata.get("top_entities"),
            [
                key
                for node in list(subgraph.nodes or [])
                if getattr(node, "node_type", None) == "entity"
                for key in list(getattr(node, "entity_keys", []) or [])
            ],
        )
        top_opinions = _unique_strings(
            metadata.get("top_opinions"),
            [
                key
                for node in list(subgraph.nodes or [])
                if getattr(node, "node_type", None) in {"opinion", "constraint", "preference"}
                for key in list(getattr(node, "opinion_keys", []) or [])
            ],
        )
        return {
            "source": "task-subgraph",
            "scope_type": subgraph.scope.scope_type,
            "scope_id": subgraph.scope.scope_id,
            "seed_refs": list(subgraph.seed_refs or []),
            "focus_node_ids": list(subgraph.focus_node_ids or []),
            "constraint_refs": list(subgraph.top_constraint_refs or []),
            "evidence_refs": list(subgraph.top_evidence_refs or []),
            "node_count": len(list(subgraph.nodes or [])),
            "relation_count": len(list(subgraph.relations or [])),
            "node_types": _unique_strings(
                [getattr(node, "node_type", None) for node in list(subgraph.nodes or [])],
            ),
            "top_entities": top_entities,
            "top_opinions": top_opinions,
            "top_relations": relation_summaries,
            "top_relation_kinds": relation_kinds,
            "capability_labels": _node_titles(subgraph, node_type="capability"),
            "environment_labels": _node_titles(subgraph, node_type="environment"),
            "failure_patterns": _node_titles(subgraph, node_type="failure_pattern"),
            "recovery_patterns": _node_titles(subgraph, node_type="recovery_pattern"),
            "support_paths": _path_summaries(subgraph.support_paths),
            "contradiction_paths": _path_summaries(subgraph.contradiction_paths),
            "dependency_paths": _path_summaries(subgraph.dependency_paths),
            "blocker_paths": _path_summaries(subgraph.blocker_paths),
            "recovery_paths": _path_summaries(subgraph.recovery_paths),
        }

    def extract_task_subgraph_from_kernel_metadata(
        self,
        kernel_metadata: dict[str, Any] | None,
    ) -> TaskSubgraph | None:
        payload = _mapping(kernel_metadata)
        candidates = [
            _mapping(_mapping(_mapping(payload.get("payload")).get("task_seed")).get("assignment_sidecar_plan")).get(
                "knowledge_subgraph",
            ),
            _mapping(_mapping(payload.get("payload")).get("assignment_sidecar_plan")).get(
                "knowledge_subgraph",
            ),
            _mapping(_mapping(_mapping(payload.get("payload")).get("compiler")).get("assignment_sidecar_plan")).get(
                "knowledge_subgraph",
            ),
            _mapping(_mapping(payload.get("task_seed")).get("assignment_sidecar_plan")).get(
                "knowledge_subgraph",
            ),
            _mapping(payload.get("task_subgraph")) or payload.get("task_subgraph"),
        ]
        for candidate in candidates:
            subgraph = self._coerce_task_subgraph(candidate)
            if subgraph is not None:
                return subgraph
        return None

    def summarize_kernel_task_subgraph(
        self,
        kernel_metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        subgraph = self.extract_task_subgraph_from_kernel_metadata(kernel_metadata)
        summary = self.summarize_task_subgraph(subgraph)
        if summary:
            return summary
        payload = _mapping(kernel_metadata)
        candidates = [
            _mapping(_mapping(_mapping(payload.get("payload")).get("task_seed")).get("assignment_sidecar_plan")).get(
                "knowledge_subgraph",
            ),
            _mapping(_mapping(payload.get("payload")).get("assignment_sidecar_plan")).get(
                "knowledge_subgraph",
            ),
            _mapping(_mapping(_mapping(payload.get("payload")).get("compiler")).get("assignment_sidecar_plan")).get(
                "knowledge_subgraph",
            ),
            _mapping(_mapping(payload.get("task_seed")).get("assignment_sidecar_plan")).get(
                "knowledge_subgraph",
            ),
            _mapping(payload.get("task_subgraph")) or payload.get("task_subgraph"),
        ]
        for candidate in candidates:
            summary = self._coerce_compact_task_subgraph_summary(candidate)
            if summary is not None:
                return summary
        return summary or None

    def build_human_boundary_writeback(self, **kwargs) -> object:
        return self._knowledge_writeback_service.build_human_boundary_writeback(**kwargs)

    def build_execution_outcome_writeback_change(self, **kwargs) -> object:
        return self._knowledge_writeback_service.build_execution_outcome_writeback(**kwargs)

    def build_report_synthesis_writeback_change(self, **kwargs) -> object:
        return self._knowledge_writeback_service.build_report_synthesis_writeback(**kwargs)

    def apply_change(self, change: object) -> object | None:
        apply_change = getattr(self._knowledge_writeback_service, "apply_change", None)
        if not callable(apply_change):
            return None
        return apply_change(change)

    def summarize_change(self, change: object) -> dict[str, Any] | None:
        summarize = getattr(self._knowledge_writeback_service, "summarize_change", None)
        if not callable(summarize):
            return None
        payload = summarize(change)
        return dict(payload) if isinstance(payload, dict) else None

    @staticmethod
    def _coerce_task_subgraph(value: object | None) -> TaskSubgraph | None:
        if isinstance(value, TaskSubgraph):
            return value
        if not isinstance(value, dict):
            return None
        try:
            return TaskSubgraph.model_validate(value)
        except Exception:
            return None

    @staticmethod
    def _coerce_compact_task_subgraph_summary(
        value: object | None,
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        scope_type = _string(value.get("scope_type"))
        scope_id = _string(value.get("scope_id"))
        if scope_type is None or scope_id is None:
            return None
        if not any(
            key in value
            for key in (
                "dependency_paths",
                "blocker_paths",
                "recovery_paths",
                "top_relations",
                "top_entities",
                "capability_labels",
                "environment_labels",
            )
        ):
            return None
        return {
            "source": _string(value.get("source")) or "task-subgraph",
            "scope_type": scope_type,
            "scope_id": scope_id,
            "seed_refs": _unique_strings(value.get("seed_refs")),
            "focus_node_ids": _unique_strings(value.get("focus_node_ids")),
            "constraint_refs": _unique_strings(value.get("constraint_refs")),
            "evidence_refs": _unique_strings(value.get("evidence_refs")),
            "node_count": _int(value.get("node_count")),
            "relation_count": _int(value.get("relation_count")),
            "node_types": _unique_strings(value.get("node_types")),
            "top_entities": _unique_strings(value.get("top_entities")),
            "top_opinions": _unique_strings(value.get("top_opinions")),
            "top_relations": _unique_strings(value.get("top_relations")),
            "top_relation_kinds": _unique_strings(value.get("top_relation_kinds")),
            "capability_labels": _unique_strings(value.get("capability_labels")),
            "environment_labels": _unique_strings(value.get("environment_labels")),
            "failure_patterns": _unique_strings(value.get("failure_patterns")),
            "recovery_patterns": _unique_strings(value.get("recovery_patterns")),
            "support_paths": _path_summaries(value.get("support_paths")),
            "contradiction_paths": _path_summaries(value.get("contradiction_paths")),
            "dependency_paths": _path_summaries(value.get("dependency_paths")),
            "blocker_paths": _path_summaries(value.get("blocker_paths")),
            "recovery_paths": _path_summaries(value.get("recovery_paths")),
        }


__all__ = ["KnowledgeGraphService"]
