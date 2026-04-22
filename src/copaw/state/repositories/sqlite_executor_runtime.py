# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from typing import Any

from ..models_executor_runtime import (
    ExecutionPolicyRecord,
    ExecutorEventRecord,
    ExecutorProviderRecord,
    ExecutorRuntimeInstanceRecord,
    ExecutorThreadBindingRecord,
    ExecutorTurnRecord,
    ModelInvocationPolicyRecord,
    ProjectProfileRecord,
    RoleContractRecord,
    RoleExecutorBindingRecord,
)
from ..store import SQLiteStateStore
from .base import BaseExecutorRuntimeRepository
from .sqlite_shared import _decode_any_json, _encode_json, _payload


class SqliteExecutorRuntimeRepository(BaseExecutorRuntimeRepository):
    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_runtime(self, runtime_id: str) -> ExecutorRuntimeInstanceRecord | None:
        return _get_single(
            store=self._store,
            table_name="executor_runtime_instances",
            key_name="runtime_id",
            key_value=runtime_id,
            model_type=ExecutorRuntimeInstanceRecord,
            json_fields=("metadata",),
        )

    def list_runtimes(
        self,
        *,
        executor_id: str | None = None,
        assignment_id: str | None = None,
        role_id: str | None = None,
        runtime_status: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorRuntimeInstanceRecord]:
        return _list_records(
            store=self._store,
            table_name="executor_runtime_instances",
            model_type=ExecutorRuntimeInstanceRecord,
            order_by="updated_at DESC, created_at DESC",
            limit=limit,
            json_fields=("metadata",),
            filters=(
                ("executor_id", executor_id),
                ("assignment_id", assignment_id),
                ("role_id", role_id),
                ("runtime_status", runtime_status),
            ),
        )

    def upsert_runtime(
        self,
        record: ExecutorRuntimeInstanceRecord,
    ) -> ExecutorRuntimeInstanceRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_runtime_instances",
            key_name="runtime_id",
            record=record,
            json_fields=("metadata",),
        )
        return record

    def get_role_contract(self, role_id: str) -> RoleContractRecord | None:
        return _get_single(
            store=self._store,
            table_name="executor_role_contracts",
            key_name="role_id",
            key_value=role_id,
            model_type=RoleContractRecord,
            json_fields=(
                "responsibilities",
                "escalation_rules",
                "default_skill_set",
                "metadata",
            ),
        )

    def upsert_role_contract(self, record: RoleContractRecord) -> RoleContractRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_role_contracts",
            key_name="role_id",
            record=record,
            json_fields=("responsibilities", "escalation_rules", "default_skill_set", "metadata"),
        )
        return record

    def get_project_profile(self, project_profile_id: str) -> ProjectProfileRecord | None:
        return _get_single(
            store=self._store,
            table_name="executor_project_profiles",
            key_name="project_profile_id",
            key_value=project_profile_id,
            model_type=ProjectProfileRecord,
        )

    def upsert_project_profile(self, record: ProjectProfileRecord) -> ProjectProfileRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_project_profiles",
            key_name="project_profile_id",
            record=record,
            json_fields=("metadata",),
        )
        return record

    def get_execution_policy(self, policy_id: str) -> ExecutionPolicyRecord | None:
        return _get_single(
            store=self._store,
            table_name="executor_execution_policies",
            key_name="policy_id",
            key_value=policy_id,
            model_type=ExecutionPolicyRecord,
        )

    def upsert_execution_policy(self, record: ExecutionPolicyRecord) -> ExecutionPolicyRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_execution_policies",
            key_name="policy_id",
            record=record,
            json_fields=("metadata",),
        )
        return record

    def get_executor_provider(self, provider_id: str) -> ExecutorProviderRecord | None:
        return _get_single(
            store=self._store,
            table_name="executor_providers",
            key_name="provider_id",
            key_value=provider_id,
            model_type=ExecutorProviderRecord,
        )

    def upsert_executor_provider(self, record: ExecutorProviderRecord) -> ExecutorProviderRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_providers",
            key_name="provider_id",
            record=record,
            json_fields=("metadata",),
        )
        return record

    def list_executor_providers(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorProviderRecord]:
        return _list_records(
            store=self._store,
            table_name="executor_providers",
            model_type=ExecutorProviderRecord,
            order_by="updated_at DESC, created_at DESC",
            limit=limit,
            json_fields=("metadata",),
            filters=(("status", status),),
        )

    def get_role_executor_binding(self, role_id: str) -> RoleExecutorBindingRecord | None:
        return _get_single(
            store=self._store,
            table_name="executor_role_bindings",
            key_name="role_id",
            key_value=role_id,
            model_type=RoleExecutorBindingRecord,
        )

    def upsert_role_executor_binding(
        self,
        record: RoleExecutorBindingRecord,
    ) -> RoleExecutorBindingRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_role_bindings",
            key_name="role_id",
            record=record,
            json_fields=("metadata",),
        )
        return record

    def get_model_invocation_policy(
        self,
        policy_id: str,
    ) -> ModelInvocationPolicyRecord | None:
        return _get_single(
            store=self._store,
            table_name="executor_model_invocation_policies",
            key_name="policy_id",
            key_value=policy_id,
            model_type=ModelInvocationPolicyRecord,
            json_fields=("role_overrides", "metadata"),
        )

    def upsert_model_invocation_policy(
        self,
        record: ModelInvocationPolicyRecord,
    ) -> ModelInvocationPolicyRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_model_invocation_policies",
            key_name="policy_id",
            record=record,
            json_fields=("role_overrides", "metadata"),
        )
        return record

    def list_thread_bindings(
        self,
        *,
        runtime_id: str | None = None,
        thread_id: str | None = None,
        role_id: str | None = None,
        assignment_id: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorThreadBindingRecord]:
        return _list_records(
            store=self._store,
            table_name="executor_thread_bindings",
            model_type=ExecutorThreadBindingRecord,
            order_by="updated_at DESC, created_at DESC",
            limit=limit,
            json_fields=("metadata",),
            filters=(
                ("runtime_id", runtime_id),
                ("thread_id", thread_id),
                ("role_id", role_id),
                ("assignment_id", assignment_id),
            ),
        )

    def upsert_thread_binding(
        self,
        record: ExecutorThreadBindingRecord,
    ) -> ExecutorThreadBindingRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_thread_bindings",
            key_name="binding_id",
            record=record,
            json_fields=("metadata",),
        )
        return record

    def list_turn_records(
        self,
        *,
        runtime_id: str | None = None,
        thread_id: str | None = None,
        assignment_id: str | None = None,
        turn_id: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorTurnRecord]:
        return _list_records(
            store=self._store,
            table_name="executor_turn_records",
            model_type=ExecutorTurnRecord,
            order_by="updated_at DESC, created_at DESC",
            limit=limit,
            json_fields=("metadata",),
            filters=(
                ("runtime_id", runtime_id),
                ("thread_id", thread_id),
                ("assignment_id", assignment_id),
                ("turn_id", turn_id),
            ),
        )

    def upsert_turn_record(self, record: ExecutorTurnRecord) -> ExecutorTurnRecord:
        _upsert_updated_record(
            store=self._store,
            table_name="executor_turn_records",
            key_name="turn_record_id",
            record=record,
            json_fields=("metadata",),
        )
        return record

    def list_event_records(
        self,
        *,
        runtime_id: str | None = None,
        thread_id: str | None = None,
        assignment_id: str | None = None,
        turn_id: str | None = None,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutorEventRecord]:
        return _list_records(
            store=self._store,
            table_name="executor_event_records",
            model_type=ExecutorEventRecord,
            order_by="created_at DESC",
            limit=limit,
            json_fields=("payload", "metadata"),
            filters=(
                ("runtime_id", runtime_id),
                ("thread_id", thread_id),
                ("assignment_id", assignment_id),
                ("turn_id", turn_id),
                ("event_type", event_type),
            ),
        )

    def upsert_event_record(self, record: ExecutorEventRecord) -> ExecutorEventRecord:
        _upsert_created_record(
            store=self._store,
            table_name="executor_event_records",
            key_name="event_id",
            record=record,
            json_fields=("payload", "metadata"),
        )
        return record


def _get_single(
    *,
    store: SQLiteStateStore,
    table_name: str,
    key_name: str,
    key_value: str,
    model_type: type,
    json_fields: tuple[str, ...] = ("metadata",),
):
    with store.connection() as conn:
        row = conn.execute(
            f"SELECT * FROM {table_name} WHERE {key_name} = ?",
            (key_value,),
        ).fetchone()
    return _model_from_row(model_type, row, json_fields=json_fields)


def _list_records(
    *,
    store: SQLiteStateStore,
    table_name: str,
    model_type: type,
    order_by: str,
    limit: int | None,
    json_fields: tuple[str, ...],
    filters: tuple[tuple[str, object | None], ...],
):
    clauses: list[str] = []
    params: list[Any] = []
    for field_name, value in filters:
        if value is None:
            continue
        clauses.append(f"{field_name} = ?")
        params.append(value)
    query = f"SELECT * FROM {table_name}"
    if clauses:
        query = f"{query} WHERE {' AND '.join(clauses)}"
    query = f"{query} ORDER BY {order_by}"
    if isinstance(limit, int) and limit > 0:
        query = f"{query} LIMIT ?"
        params.append(limit)
    with store.connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [
        item
        for item in (_model_from_row(model_type, row, json_fields=json_fields) for row in rows)
        if item is not None
    ]


def _upsert_updated_record(
    *,
    store: SQLiteStateStore,
    table_name: str,
    key_name: str,
    record: Any,
    json_fields: tuple[str, ...],
) -> None:
    payload = _payload(record)
    for field_name in json_fields:
        payload[f"{field_name}_json"] = _encode_json(getattr(record, field_name))
        payload.pop(field_name, None)
    fields = list(payload.keys())
    assignments = ", ".join(
        f"{field} = excluded.{field}"
        for field in fields
        if field != key_name
    )
    with store.connection() as conn:
        conn.execute(
            f"""
            INSERT INTO {table_name} ({", ".join(fields)})
            VALUES ({", ".join(f":{field}" for field in fields)})
            ON CONFLICT({key_name}) DO UPDATE SET
                {assignments}
            """,
            payload,
        )


def _upsert_created_record(
    *,
    store: SQLiteStateStore,
    table_name: str,
    key_name: str,
    record: Any,
    json_fields: tuple[str, ...],
) -> None:
    _upsert_updated_record(
        store=store,
        table_name=table_name,
        key_name=key_name,
        record=record,
        json_fields=json_fields,
    )


def _model_from_row(
    model_type: type,
    row: sqlite3.Row | None,
    *,
    json_fields: tuple[str, ...] = ("metadata",),
):
    if row is None:
        return None
    payload = dict(row)
    for field_name in json_fields:
        payload[field_name] = _decode_any_json(payload.pop(f"{field_name}_json", None))
    return model_type.model_validate(payload)
