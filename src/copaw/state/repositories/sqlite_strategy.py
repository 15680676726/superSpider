# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


def _jsonable_model_list(values: object | None) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    items: list[dict[str, Any]] = []
    for item in values:
        if isinstance(item, dict):
            items.append(dict(item))
            continue
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            items.append(model_dump(mode="json"))
    return items


class SqliteStrategyMemoryRepository(BaseStrategyMemoryRepository):
    """SQLite-backed repository for formal strategy memory records."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_strategy(self, strategy_id: str) -> StrategyMemoryRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM strategy_memories WHERE strategy_id = ?",
                (strategy_id,),
            ).fetchone()
        return _strategy_memory_from_row(row)

    def list_strategies(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[StrategyMemoryRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)

        query = "SELECT * FROM strategy_memories"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            record
            for record in (_strategy_memory_from_row(row) for row in rows)
            if record is not None
        ]

    def upsert_strategy(self, record: StrategyMemoryRecord) -> StrategyMemoryRecord:
        record = StrategyMemoryRecord.model_validate(record.model_dump(mode="python"))
        payload = _payload(record)
        payload["priority_order_json"] = json.dumps(record.priority_order, sort_keys=True)
        payload["thinking_axes_json"] = json.dumps(record.thinking_axes, sort_keys=True)
        payload["delegation_policy_json"] = json.dumps(
            record.delegation_policy,
            sort_keys=True,
        )
        payload["direct_execution_policy_json"] = json.dumps(
            record.direct_execution_policy,
            sort_keys=True,
        )
        payload["execution_constraints_json"] = json.dumps(
            record.execution_constraints,
            sort_keys=True,
        )
        payload["evidence_requirements_json"] = json.dumps(
            record.evidence_requirements,
            sort_keys=True,
        )
        payload["active_goal_ids_json"] = json.dumps(
            record.active_goal_ids,
            sort_keys=True,
        )
        payload["active_goal_titles_json"] = json.dumps(
            record.active_goal_titles,
            sort_keys=True,
        )
        payload["teammate_contracts_json"] = json.dumps(
            record.teammate_contracts,
            sort_keys=True,
        )
        payload["lane_weights_json"] = _encode_json(record.lane_weights)
        payload["strategic_uncertainties_json"] = json.dumps(
            _jsonable_model_list(record.strategic_uncertainties),
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["lane_budgets_json"] = json.dumps(
            _jsonable_model_list(record.lane_budgets),
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["strategy_trigger_rules_json"] = json.dumps(
            _jsonable_model_list(record.strategy_trigger_rules),
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["planning_policy_json"] = json.dumps(
            record.planning_policy,
            sort_keys=True,
        )
        payload["current_focuses_json"] = json.dumps(
            record.current_focuses,
            sort_keys=True,
        )
        payload["paused_lane_ids_json"] = json.dumps(
            record.paused_lane_ids,
            sort_keys=True,
        )
        payload["review_rules_json"] = json.dumps(
            record.review_rules,
            sort_keys=True,
        )
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO strategy_memories (
                    strategy_id,
                    scope_type,
                    scope_id,
                    owner_agent_id,
                    owner_scope,
                    industry_instance_id,
                    title,
                    summary,
                    mission,
                    north_star,
                    priority_order_json,
                    thinking_axes_json,
                    delegation_policy_json,
                    direct_execution_policy_json,
                    execution_constraints_json,
                    evidence_requirements_json,
                    active_goal_ids_json,
                    active_goal_titles_json,
                    teammate_contracts_json,
                    lane_weights_json,
                    strategic_uncertainties_json,
                    lane_budgets_json,
                    strategy_trigger_rules_json,
                    planning_policy_json,
                    current_focuses_json,
                    paused_lane_ids_json,
                    review_rules_json,
                    source_ref,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :strategy_id,
                    :scope_type,
                    :scope_id,
                    :owner_agent_id,
                    :owner_scope,
                    :industry_instance_id,
                    :title,
                    :summary,
                    :mission,
                    :north_star,
                    :priority_order_json,
                    :thinking_axes_json,
                    :delegation_policy_json,
                    :direct_execution_policy_json,
                    :execution_constraints_json,
                    :evidence_requirements_json,
                    :active_goal_ids_json,
                    :active_goal_titles_json,
                    :teammate_contracts_json,
                    :lane_weights_json,
                    :strategic_uncertainties_json,
                    :lane_budgets_json,
                    :strategy_trigger_rules_json,
                    :planning_policy_json,
                    :current_focuses_json,
                    :paused_lane_ids_json,
                    :review_rules_json,
                    :source_ref,
                    :status,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(strategy_id) DO UPDATE SET
                    scope_type = excluded.scope_type,
                    scope_id = excluded.scope_id,
                    owner_agent_id = excluded.owner_agent_id,
                    owner_scope = excluded.owner_scope,
                    industry_instance_id = excluded.industry_instance_id,
                    title = excluded.title,
                    summary = excluded.summary,
                    mission = excluded.mission,
                    north_star = excluded.north_star,
                    priority_order_json = excluded.priority_order_json,
                    thinking_axes_json = excluded.thinking_axes_json,
                    delegation_policy_json = excluded.delegation_policy_json,
                    direct_execution_policy_json = excluded.direct_execution_policy_json,
                    execution_constraints_json = excluded.execution_constraints_json,
                    evidence_requirements_json = excluded.evidence_requirements_json,
                    active_goal_ids_json = excluded.active_goal_ids_json,
                    active_goal_titles_json = excluded.active_goal_titles_json,
                    teammate_contracts_json = excluded.teammate_contracts_json,
                    lane_weights_json = excluded.lane_weights_json,
                    strategic_uncertainties_json = excluded.strategic_uncertainties_json,
                    lane_budgets_json = excluded.lane_budgets_json,
                    strategy_trigger_rules_json = excluded.strategy_trigger_rules_json,
                    planning_policy_json = excluded.planning_policy_json,
                    current_focuses_json = excluded.current_focuses_json,
                    paused_lane_ids_json = excluded.paused_lane_ids_json,
                    review_rules_json = excluded.review_rules_json,
                    source_ref = excluded.source_ref,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_strategy(self, strategy_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM strategy_memories WHERE strategy_id = ?",
                (strategy_id,),
            )
        return cursor.rowcount > 0


def _strategy_memory_from_row(
    row: sqlite3.Row | None,
) -> StrategyMemoryRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["priority_order"] = _decode_json_list(payload.pop("priority_order_json", None)) or []
    payload["thinking_axes"] = _decode_json_list(payload.pop("thinking_axes_json", None)) or []
    payload["delegation_policy"] = _decode_json_list(
        payload.pop("delegation_policy_json", None),
    ) or []
    payload["direct_execution_policy"] = _decode_json_list(
        payload.pop("direct_execution_policy_json", None),
    ) or []
    payload["execution_constraints"] = _decode_json_list(
        payload.pop("execution_constraints_json", None),
    ) or []
    payload["evidence_requirements"] = _decode_json_list(
        payload.pop("evidence_requirements_json", None),
    ) or []
    payload["active_goal_ids"] = _decode_json_list(
        payload.pop("active_goal_ids_json", None),
    ) or []
    payload["active_goal_titles"] = _decode_json_list(
        payload.pop("active_goal_titles_json", None),
    ) or []
    payload["teammate_contracts"] = _decode_any_json(
        payload.pop("teammate_contracts_json", None),
    )
    if not isinstance(payload["teammate_contracts"], list):
        payload["teammate_contracts"] = []
    payload["lane_weights"] = _decode_json_mapping(payload.pop("lane_weights_json", None))
    payload["strategic_uncertainties"] = _decode_any_json(
        payload.pop("strategic_uncertainties_json", None),
    ) or []
    payload["lane_budgets"] = _decode_any_json(
        payload.pop("lane_budgets_json", None),
    ) or []
    payload["strategy_trigger_rules"] = _decode_any_json(
        payload.pop("strategy_trigger_rules_json", None),
    ) or []
    payload["planning_policy"] = _decode_json_list(
        payload.pop("planning_policy_json", None),
    ) or []
    payload["current_focuses"] = _decode_json_list(
        payload.pop("current_focuses_json", None),
    ) or []
    payload["paused_lane_ids"] = _decode_json_list(
        payload.pop("paused_lane_ids_json", None),
    ) or []
    payload["review_rules"] = _decode_json_list(
        payload.pop("review_rules_json", None),
    ) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return StrategyMemoryRecord.model_validate(payload)


class SqliteKnowledgeChunkRepository(BaseKnowledgeChunkRepository):
    """SQLite-backed repository for formal knowledge chunks."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_chunk(self, chunk_id: str) -> KnowledgeChunkRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_chunks WHERE id = ?",
                (chunk_id,),
            ).fetchone()
        return _knowledge_chunk_from_row(row)

    def list_chunks(
        self,
        *,
        document_id: str | None = None,
    ) -> list[KnowledgeChunkRecord]:
        clauses: list[str] = []
        params: list[Any] = []

        if document_id is not None:
            clauses.append("document_id = ?")
            params.append(document_id)

        query = "SELECT * FROM knowledge_chunks"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, chunk_index ASC"

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            chunk
            for chunk in (_knowledge_chunk_from_row(row) for row in rows)
            if chunk is not None
        ]

    def upsert_chunk(self, chunk: KnowledgeChunkRecord) -> KnowledgeChunkRecord:
        payload = _payload(chunk)
        payload["role_bindings_json"] = json.dumps(
            chunk.role_bindings,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["tags_json"] = json.dumps(
            chunk.tags,
            ensure_ascii=False,
            sort_keys=True,
        )
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_chunks (
                    id,
                    document_id,
                    title,
                    content,
                    summary,
                    source_ref,
                    chunk_index,
                    role_bindings_json,
                    tags_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :document_id,
                    :title,
                    :content,
                    :summary,
                    :source_ref,
                    :chunk_index,
                    :role_bindings_json,
                    :tags_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    document_id = excluded.document_id,
                    title = excluded.title,
                    content = excluded.content,
                    summary = excluded.summary,
                    source_ref = excluded.source_ref,
                    chunk_index = excluded.chunk_index,
                    role_bindings_json = excluded.role_bindings_json,
                    tags_json = excluded.tags_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return chunk

    def delete_chunk(self, chunk_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM knowledge_chunks WHERE id = ?",
                (chunk_id,),
            )
        return cursor.rowcount > 0


def _knowledge_chunk_from_row(
    row: sqlite3.Row | None,
) -> KnowledgeChunkRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["role_bindings"] = _decode_json_list(
        payload.pop("role_bindings_json", None),
    ) or []
    payload["tags"] = _decode_json_list(payload.pop("tags_json", None)) or []
    return KnowledgeChunkRecord.model_validate(payload)
