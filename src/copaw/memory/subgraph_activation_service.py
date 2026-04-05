# -*- coding: utf-8 -*-
from __future__ import annotations

from .knowledge_graph_models import TaskSubgraph


class SubgraphActivationService:
    def __init__(self, *, memory_activation_service) -> None:
        self._memory_activation_service = memory_activation_service

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
        seed_refs: list[str] | None = None,
        limit: int = 12,
    ) -> TaskSubgraph:
        result = self._memory_activation_service.activate_for_query(
            query=query,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            task_id=task_id,
            work_context_id=work_context_id,
            agent_id=agent_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            global_scope_id=global_scope_id,
            capability_ref=capability_ref,
            environment_ref=environment_ref,
            risk_level=risk_level,
            current_phase=current_phase,
            include_strategy=include_strategy,
            include_reports=include_reports,
            limit=limit,
        )
        subgraph = result.to_task_subgraph(seed_refs=seed_refs)
        metadata = dict(subgraph.metadata or {})
        if result.seed_terms:
            metadata["seed_terms"] = list(result.seed_terms)
        if result.top_entities:
            metadata["top_entities"] = list(result.top_entities)
        if result.top_opinions:
            metadata["top_opinions"] = list(result.top_opinions)
        if result.top_relations:
            metadata["top_relations"] = list(result.top_relations)
        if result.top_relation_kinds:
            metadata["top_relation_kinds"] = list(result.top_relation_kinds)
        relation_paths = {
            "support_paths": [item.model_dump(mode="json", exclude_none=True) for item in list(result.support_paths or [])],
            "contradiction_paths": [item.model_dump(mode="json", exclude_none=True) for item in list(result.contradiction_paths or [])],
            "dependency_paths": [item.model_dump(mode="json", exclude_none=True) for item in list(result.dependency_paths or [])],
            "blocker_paths": [item.model_dump(mode="json", exclude_none=True) for item in list(result.blocker_paths or [])],
            "recovery_paths": [item.model_dump(mode="json", exclude_none=True) for item in list(result.recovery_paths or [])],
        }
        if any(relation_paths.values()):
            metadata["relation_paths"] = {key: value for key, value in relation_paths.items() if value}
        if result.strategy_refs:
            metadata["strategy_refs"] = list(result.strategy_refs)
        if result.contradictions:
            metadata["contradiction_node_ids"] = [
                item.neuron_id
                for item in result.contradictions
            ]
        subgraph.metadata = metadata
        return subgraph
