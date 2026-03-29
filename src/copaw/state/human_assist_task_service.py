# -*- coding: utf-8 -*-
"""Formal service for chat-first host-side assist tasks."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ..evidence import EvidenceLedger, EvidenceRecord
from .models import HumanAssistTaskRecord
from .repositories import BaseHumanAssistTaskRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _merge_resume_state(
    verification_payload: object | None,
    *,
    status: str,
    summary: str | None = None,
    reason: str | None = None,
    resume_payload: Mapping[str, Any] | None = None,
    updated_at: datetime,
) -> dict[str, Any]:
    payload = _mapping(verification_payload)
    resume_state = _mapping(payload.get("resume"))
    resume_state["status"] = status
    resume_state["updated_at"] = updated_at.isoformat()
    summary_text = _string(summary)
    if summary_text is not None:
        resume_state["summary"] = summary_text
    reason_text = _string(reason)
    if reason_text is not None:
        resume_state["reason"] = reason_text
    normalized_resume_payload = _mapping(resume_payload)
    if normalized_resume_payload:
        resume_state["result"] = normalized_resume_payload
    payload["resume"] = resume_state
    return payload


def _string_list(value: object | None) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, (list, tuple, set)) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


def _flatten_sources(*values: object) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if text:
                parts.append(text)
            continue
        if isinstance(value, (list, tuple, set)):
            parts.extend(_string_list(value))
            continue
        payload = _mapping(value)
        if payload:
            parts.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return "\n".join(parts).lower()


def _match_anchors(anchors: Sequence[str], source_text: str) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    missing: list[str] = []
    for anchor in _string_list(list(anchors)):
        if anchor.lower() in source_text:
            matched.append(anchor)
        else:
            missing.append(anchor)
    return matched, missing


@dataclass(slots=True)
class HumanAssistVerificationResult:
    outcome: str
    task: HumanAssistTaskRecord
    message: str
    matched_hard_anchors: list[str]
    matched_result_anchors: list[str]
    missing_hard_anchors: list[str]
    missing_result_anchors: list[str]
    matched_negative_anchors: list[str]
    resume_queued: bool


class HumanAssistTaskService:
    """Manage issue, submit, verify, and resume-ready state for host tasks."""

    _TERMINAL_STATUSES = frozenset({"resume_queued", "closed", "expired", "cancelled"})

    def __init__(
        self,
        *,
        repository: BaseHumanAssistTaskRepository,
        evidence_ledger: EvidenceLedger | None = None,
        runtime_event_bus: object | None = None,
    ) -> None:
        self._repository = repository
        self._evidence_ledger = evidence_ledger
        self._runtime_event_bus = runtime_event_bus

    def get_task(self, task_id: str) -> HumanAssistTaskRecord | None:
        return self._repository.get_task(task_id)

    def upsert_task(self, task: HumanAssistTaskRecord) -> HumanAssistTaskRecord:
        return self._repository.upsert_task(task)

    def list_tasks(
        self,
        *,
        chat_thread_id: str | None = None,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[HumanAssistTaskRecord]:
        return self._repository.list_tasks(
            chat_thread_id=chat_thread_id,
            industry_instance_id=industry_instance_id,
            assignment_id=assignment_id,
            task_id=task_id,
            status=status,
            limit=limit,
        )

    def get_current_task(self, *, chat_thread_id: str) -> HumanAssistTaskRecord | None:
        for task in self._repository.list_tasks(chat_thread_id=chat_thread_id, limit=50):
            if task.status not in self._TERMINAL_STATUSES:
                return task
        return None

    def issue_task(self, task: HumanAssistTaskRecord) -> HumanAssistTaskRecord:
        spec = _mapping(task.acceptance_spec)
        hard_anchors = _string_list(spec.get("hard_anchors"))
        result_anchors = _string_list(spec.get("result_anchors"))
        if not hard_anchors and not result_anchors:
            raise ValueError("HumanAssistTask requires an acceptance contract with anchors")
        now = _utc_now()
        issued = task.model_copy(
            update={
                "status": "issued" if task.status == "created" else task.status,
                "issued_at": task.issued_at or now,
                "reward_preview": task.reward_preview or {"协作值": 1, "同调经验": 1},
                "updated_at": now,
            },
        )
        persisted = self._repository.upsert_task(issued)
        self._append_evidence(
            persisted,
            action_summary="issue human assist task",
            result_summary=persisted.summary or persisted.required_action or persisted.title,
            metadata={"status": persisted.status, "chat_thread_id": persisted.chat_thread_id},
        )
        return persisted

    def ensure_host_handoff_task(
        self,
        *,
        chat_thread_id: str,
        title: str,
        summary: str,
        required_action: str,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        resume_checkpoint_ref: str | None = None,
        verification_anchor: str | None = None,
        block_evidence_refs: Sequence[str] | None = None,
    ) -> HumanAssistTaskRecord:
        normalized_thread_id = _string(chat_thread_id)
        if normalized_thread_id is None:
            raise ValueError("Host handoff human assist task requires a chat thread id")
        normalized_task_id = _string(task_id)
        for existing in self._repository.list_tasks(chat_thread_id=normalized_thread_id, limit=50):
            if existing.status in self._TERMINAL_STATUSES:
                continue
            if existing.task_type != "host-handoff-return":
                continue
            if normalized_task_id is not None and existing.task_id not in {None, normalized_task_id}:
                continue
            return existing

        anchor = (
            _string(verification_anchor)
            or _string(resume_checkpoint_ref)
            or "human-return"
        )
        anchor_hint = f"“{anchor}”" if anchor else "完成返回条件"
        record = HumanAssistTaskRecord(
            industry_instance_id=_string(industry_instance_id),
            assignment_id=_string(assignment_id),
            task_id=normalized_task_id,
            chat_thread_id=normalized_thread_id,
            title=_string(title) or "Return host handoff",
            summary=_string(summary) or "Runtime handoff is blocking automatic continuation.",
            task_type="host-handoff-return",
            reason_code="host-handoff-active",
            reason_summary=(
                _string(summary)
                or "Runtime handoff is still active and needs host-side confirmation."
            ),
            required_action=(
                _string(required_action)
                or f"完成宿主侧处理后，请在聊天里回报并包含 {anchor_hint}。"
            ),
            submission_mode="chat-message",
            acceptance_mode="anchor_verified",
            acceptance_spec={
                "version": "v1",
                "hard_anchors": [anchor],
                "failure_hint": (
                    f"还需要宿主返回确认，请在聊天里说明已完成并包含 {anchor_hint}。"
                ),
            },
            resume_checkpoint_ref=_string(resume_checkpoint_ref) or anchor,
            block_evidence_refs=_string_list(block_evidence_refs),
        )
        return self.issue_task(record)

    def submit_task(
        self,
        task_id: str,
        *,
        submission_text: str | None = None,
        submission_evidence_refs: Sequence[str] | None = None,
        submission_payload: Mapping[str, Any] | None = None,
    ) -> HumanAssistTaskRecord:
        current = self._require_task(task_id)
        now = _utc_now()
        updated = current.model_copy(
            update={
                "status": "submitted",
                "submission_text": _string(submission_text),
                "submission_evidence_refs": _string_list(submission_evidence_refs),
                "submission_payload": _mapping(submission_payload),
                "submitted_at": now,
                "updated_at": now,
            },
        )
        persisted = self._repository.upsert_task(updated)
        self._append_evidence(
            persisted,
            action_summary="submit human assist task",
            result_summary=_string(submission_text) or "host submitted completion proof",
            metadata={
                "status": persisted.status,
                "submission_evidence_refs": list(persisted.submission_evidence_refs),
            },
        )
        return persisted

    def verify_task(
        self,
        task_id: str,
        *,
        observed_text: str | None = None,
        observed_evidence_refs: Sequence[str] | None = None,
        observed_payload: Mapping[str, Any] | None = None,
    ) -> HumanAssistVerificationResult:
        current = self._require_task(task_id)
        verifying = current.model_copy(update={"status": "verifying", "updated_at": _utc_now()})
        current = self._repository.upsert_task(verifying)

        spec = _mapping(current.acceptance_spec)
        source_text = _flatten_sources(
            current.submission_text,
            observed_text,
            current.submission_evidence_refs,
            observed_evidence_refs,
            current.submission_payload,
            observed_payload,
        )
        matched_hard, missing_hard = _match_anchors(spec.get("hard_anchors") or [], source_text)
        matched_result, missing_result = _match_anchors(
            spec.get("result_anchors") or [],
            source_text,
        )
        matched_negative, _ = _match_anchors(spec.get("negative_anchors") or [], source_text)

        if matched_negative:
            return self._finalize_verification(
                current,
                outcome="rejected",
                status="rejected",
                action_summary="reject human assist task",
                message="检测到不通过锚点，当前提交未通过验收。",
                matched_hard_anchors=matched_hard,
                matched_result_anchors=matched_result,
                missing_hard_anchors=missing_hard,
                missing_result_anchors=missing_result,
                matched_negative_anchors=matched_negative,
                resume_queued=False,
            )

        if missing_hard or missing_result:
            failure_hint = _string(spec.get("failure_hint")) or "请补充更多可验证证据后再提交。"
            return self._finalize_verification(
                current,
                outcome="need_more_evidence",
                status="need_more_evidence",
                action_summary="request more evidence for human assist task",
                message=failure_hint,
                matched_hard_anchors=matched_hard,
                matched_result_anchors=matched_result,
                missing_hard_anchors=missing_hard,
                missing_result_anchors=missing_result,
                matched_negative_anchors=[],
                resume_queued=False,
            )

        reward_result = dict(current.reward_preview or {"协作值": 1, "同调经验": 1})
        reward_result["granted"] = True
        accepted = current.model_copy(
            update={
                "status": "accepted",
                "reward_result": reward_result,
                "verification_payload": {
                    "matched_hard_anchors": matched_hard,
                    "matched_result_anchors": matched_result,
                    "matched_negative_anchors": [],
                },
                "verified_at": _utc_now(),
                "updated_at": _utc_now(),
            },
        )
        persisted = self._repository.upsert_task(accepted)
        self._append_evidence(
            persisted,
            action_summary="accept human assist task",
            result_summary="human assist task accepted",
            metadata={"status": persisted.status, "reward_result": persisted.reward_result},
        )
        return HumanAssistVerificationResult(
            outcome="accepted",
            task=persisted,
            message="验收通过，已记录奖励并准备恢复执行。",
            matched_hard_anchors=matched_hard,
            matched_result_anchors=matched_result,
            missing_hard_anchors=[],
            missing_result_anchors=[],
            matched_negative_anchors=[],
            resume_queued=False,
        )

    def submit_and_verify(
        self,
        task_id: str,
        *,
        submission_text: str | None = None,
        submission_evidence_refs: Sequence[str] | None = None,
        submission_payload: Mapping[str, Any] | None = None,
    ) -> HumanAssistVerificationResult:
        self.submit_task(
            task_id,
            submission_text=submission_text,
            submission_evidence_refs=submission_evidence_refs,
            submission_payload=submission_payload,
        )
        return self.verify_task(
            task_id,
            observed_text=submission_text,
            observed_evidence_refs=submission_evidence_refs,
            observed_payload=submission_payload,
        )

    def mark_resume_queued(self, task_id: str) -> HumanAssistTaskRecord:
        current = self._require_task(task_id)
        now = _utc_now()
        updated = current.model_copy(
            update={
                "status": "resume_queued",
                "verification_payload": _merge_resume_state(
                    current.verification_payload,
                    status="resume_queued",
                    summary="系统已排队继续原流程。",
                    updated_at=now,
                ),
                "updated_at": now,
            },
        )
        persisted = self._repository.upsert_task(updated)
        self._append_evidence(
            persisted,
            action_summary="queue human assist resume",
            result_summary="human assist task queued for resume",
            metadata={"status": persisted.status},
        )
        return persisted

    def mark_closed(
        self,
        task_id: str,
        *,
        summary: str | None = None,
        resume_payload: Mapping[str, Any] | None = None,
    ) -> HumanAssistTaskRecord:
        current = self._require_task(task_id)
        now = _utc_now()
        result_summary = _string(summary) or "系统已继续原流程。"
        updated = current.model_copy(
            update={
                "status": "closed",
                "verification_payload": _merge_resume_state(
                    current.verification_payload,
                    status="closed",
                    summary=result_summary,
                    resume_payload=resume_payload,
                    updated_at=now,
                ),
                "closed_at": now,
                "updated_at": now,
            },
        )
        persisted = self._repository.upsert_task(updated)
        self._append_evidence(
            persisted,
            action_summary="close human assist task",
            result_summary=result_summary,
            metadata={"status": persisted.status},
        )
        return persisted

    def mark_handoff_blocked(
        self,
        task_id: str,
        *,
        reason: str | None = None,
        resume_payload: Mapping[str, Any] | None = None,
    ) -> HumanAssistTaskRecord:
        current = self._require_task(task_id)
        now = _utc_now()
        reason_text = _string(reason) or "系统暂时没接上后续流程。"
        updated = current.model_copy(
            update={
                "status": "handoff_blocked",
                "verification_payload": _merge_resume_state(
                    current.verification_payload,
                    status="handoff_blocked",
                    reason=reason_text,
                    resume_payload=resume_payload,
                    updated_at=now,
                ),
                "updated_at": now,
            },
        )
        persisted = self._repository.upsert_task(updated)
        self._append_evidence(
            persisted,
            action_summary="block human assist resume",
            result_summary=reason_text,
            metadata={"status": persisted.status},
        )
        return persisted

    def _finalize_verification(
        self,
        task: HumanAssistTaskRecord,
        *,
        outcome: str,
        status: str,
        action_summary: str,
        message: str,
        matched_hard_anchors: list[str],
        matched_result_anchors: list[str],
        missing_hard_anchors: list[str],
        missing_result_anchors: list[str],
        matched_negative_anchors: list[str],
        resume_queued: bool,
    ) -> HumanAssistVerificationResult:
        now = _utc_now()
        updated = task.model_copy(
            update={
                "status": status,
                "verification_payload": {
                    "matched_hard_anchors": matched_hard_anchors,
                    "matched_result_anchors": matched_result_anchors,
                    "missing_hard_anchors": missing_hard_anchors,
                    "missing_result_anchors": missing_result_anchors,
                    "matched_negative_anchors": matched_negative_anchors,
                    "outcome": outcome,
                },
                "verified_at": now,
                "updated_at": now,
            },
        )
        persisted = self._repository.upsert_task(updated)
        self._append_evidence(
            persisted,
            action_summary=action_summary,
            result_summary=message,
            metadata={
                "status": persisted.status,
                "outcome": outcome,
                "missing_hard_anchors": missing_hard_anchors,
                "missing_result_anchors": missing_result_anchors,
            },
        )
        return HumanAssistVerificationResult(
            outcome=outcome,
            task=persisted,
            message=message,
            matched_hard_anchors=matched_hard_anchors,
            matched_result_anchors=matched_result_anchors,
            missing_hard_anchors=missing_hard_anchors,
            missing_result_anchors=missing_result_anchors,
            matched_negative_anchors=matched_negative_anchors,
            resume_queued=resume_queued,
        )

    def _require_task(self, task_id: str) -> HumanAssistTaskRecord:
        task = self._repository.get_task(task_id)
        if task is None:
            raise KeyError(f"HumanAssistTask '{task_id}' not found")
        return task

    def _append_evidence(
        self,
        task: HumanAssistTaskRecord,
        *,
        action_summary: str,
        result_summary: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if self._evidence_ledger is None:
            return
        try:
            self._evidence_ledger.append(
                EvidenceRecord(
                    task_id=task.task_id or task.id,
                    actor_ref="human-assist-task-service",
                    capability_ref="human_assist_task",
                    risk_level="auto",
                    action_summary=action_summary,
                    result_summary=result_summary,
                    metadata={
                        "human_assist_task_id": task.id,
                        "chat_thread_id": task.chat_thread_id,
                        **dict(metadata or {}),
                    },
                ),
            )
        except Exception:
            return


__all__ = ["HumanAssistTaskService", "HumanAssistVerificationResult"]
