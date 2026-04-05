# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


def _human_assist_task_from_row(row: Any) -> HumanAssistTaskRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["acceptance_spec"] = _decode_json_mapping(payload.pop("acceptance_spec_json", None))
    payload["reward_preview"] = _decode_json_mapping(payload.pop("reward_preview_json", None))
    payload["reward_result"] = _decode_json_mapping(payload.pop("reward_result_json", None))
    payload["block_evidence_refs"] = _decode_json_list(
        payload.pop("block_evidence_refs_json", None),
    ) or []
    payload["submission_evidence_refs"] = _decode_json_list(
        payload.pop("submission_evidence_refs_json", None),
    ) or []
    payload["verification_evidence_refs"] = _decode_json_list(
        payload.pop("verification_evidence_refs_json", None),
    ) or []
    payload["submission_payload"] = _decode_json_mapping(payload.pop("submission_payload_json", None))
    payload["verification_payload"] = _decode_json_mapping(
        payload.pop("verification_payload_json", None),
    )
    return HumanAssistTaskRecord.model_validate(payload)


class SqliteHumanAssistTaskRepository(BaseHumanAssistTaskRepository):
    """SQLite-backed repository for host-side human assist tasks."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_task(self, task_id: str) -> HumanAssistTaskRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM human_assist_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return _human_assist_task_from_row(row)

    def list_tasks(
        self,
        *,
        profile_id: str | None = None,
        chat_thread_id: str | None = None,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[HumanAssistTaskRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if profile_id is not None:
            clauses.append("profile_id = ?")
            params.append(profile_id)
        if chat_thread_id is not None:
            clauses.append("chat_thread_id = ?")
            params.append(chat_thread_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if assignment_id is not None:
            clauses.append("assignment_id = ?")
            params.append(assignment_id)
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM human_assist_tasks"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if limit is not None and limit >= 0:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_human_assist_task_from_row(row) for row in rows]

    def upsert_task(self, task: HumanAssistTaskRecord) -> HumanAssistTaskRecord:
        payload = _payload(task)
        payload["acceptance_spec_json"] = _encode_json(task.acceptance_spec)
        payload["reward_preview_json"] = _encode_json(task.reward_preview)
        payload["reward_result_json"] = _encode_json(task.reward_result)
        payload["block_evidence_refs_json"] = _encode_json(task.block_evidence_refs)
        payload["submission_evidence_refs_json"] = _encode_json(task.submission_evidence_refs)
        payload["verification_evidence_refs_json"] = _encode_json(task.verification_evidence_refs)
        payload["submission_payload_json"] = _encode_json(task.submission_payload)
        payload["verification_payload_json"] = _encode_json(task.verification_payload)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO human_assist_tasks (
                    id,
                    profile_id,
                    industry_instance_id,
                    assignment_id,
                    task_id,
                    chat_thread_id,
                    title,
                    summary,
                    task_type,
                    reason_code,
                    reason_summary,
                    required_action,
                    submission_mode,
                    acceptance_mode,
                    acceptance_spec_json,
                    resume_checkpoint_ref,
                    status,
                    reward_preview_json,
                    reward_result_json,
                    block_evidence_refs_json,
                    submission_evidence_refs_json,
                    verification_evidence_refs_json,
                    submission_text,
                    submission_payload_json,
                    verification_payload_json,
                    issued_at,
                    submitted_at,
                    verified_at,
                    closed_at,
                    expires_at,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :profile_id,
                    :industry_instance_id,
                    :assignment_id,
                    :task_id,
                    :chat_thread_id,
                    :title,
                    :summary,
                    :task_type,
                    :reason_code,
                    :reason_summary,
                    :required_action,
                    :submission_mode,
                    :acceptance_mode,
                    :acceptance_spec_json,
                    :resume_checkpoint_ref,
                    :status,
                    :reward_preview_json,
                    :reward_result_json,
                    :block_evidence_refs_json,
                    :submission_evidence_refs_json,
                    :verification_evidence_refs_json,
                    :submission_text,
                    :submission_payload_json,
                    :verification_payload_json,
                    :issued_at,
                    :submitted_at,
                    :verified_at,
                    :closed_at,
                    :expires_at,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    industry_instance_id = excluded.industry_instance_id,
                    assignment_id = excluded.assignment_id,
                    task_id = excluded.task_id,
                    chat_thread_id = excluded.chat_thread_id,
                    title = excluded.title,
                    summary = excluded.summary,
                    task_type = excluded.task_type,
                    reason_code = excluded.reason_code,
                    reason_summary = excluded.reason_summary,
                    required_action = excluded.required_action,
                    submission_mode = excluded.submission_mode,
                    acceptance_mode = excluded.acceptance_mode,
                    acceptance_spec_json = excluded.acceptance_spec_json,
                    resume_checkpoint_ref = excluded.resume_checkpoint_ref,
                    status = excluded.status,
                    reward_preview_json = excluded.reward_preview_json,
                    reward_result_json = excluded.reward_result_json,
                    block_evidence_refs_json = excluded.block_evidence_refs_json,
                    submission_evidence_refs_json = excluded.submission_evidence_refs_json,
                    verification_evidence_refs_json = excluded.verification_evidence_refs_json,
                    submission_text = excluded.submission_text,
                    submission_payload_json = excluded.submission_payload_json,
                    verification_payload_json = excluded.verification_payload_json,
                    issued_at = excluded.issued_at,
                    submitted_at = excluded.submitted_at,
                    verified_at = excluded.verified_at,
                    closed_at = excluded.closed_at,
                    expires_at = excluded.expires_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return task

    def delete_task(self, task_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute("DELETE FROM human_assist_tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0
