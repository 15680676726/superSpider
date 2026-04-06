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


def _merge_submission_payload(
    existing: object | None,
    incoming: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = _mapping(existing)
    payload = _mapping(incoming)
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                merged[key] = normalized
            continue
        if isinstance(value, dict):
            nested = _merge_submission_payload(merged.get(key), value)
            if nested:
                merged[key] = nested
            continue
        if isinstance(value, (list, tuple, set)):
            if value:
                merged[key] = list(value)
            continue
        merged[key] = value
    return merged


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


def _spec_string_list(spec: Mapping[str, Any], *keys: str) -> list[str]:
    for key in keys:
        values = _string_list(spec.get(key))
        if values:
            return values
    return []


def _coerce_positive_int(value: object | None, *, default: int) -> int:
    try:
        resolved = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return resolved if resolved > 0 else default


def _resolve_mapping_path(payload: Mapping[str, Any], path: str) -> object | None:
    current: object = payload
    for part in [segment.strip() for segment in str(path).split(".") if segment.strip()]:
        if isinstance(current, Mapping):
            current = current.get(part)
            continue
        if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            if not part.isdigit():
                return None
            index = int(part)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _collect_state_contract(
    payload: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    required_state_paths = _spec_string_list(
        spec,
        "required_state_paths",
        "state_change_paths",
        "required_state_fields",
        "state_paths",
    )
    resolved_state_values: dict[str, Any] = {}
    missing_state_paths: list[str] = []
    for path in required_state_paths:
        value = _resolve_mapping_path(payload, path)
        if value in (None, "", [], {}, ()):
            missing_state_paths.append(path)
            continue
        resolved_state_values[path] = value

    contract_payload: dict[str, Any] = {}
    for key in (
        "state_change",
        "state_changes",
        "state_contract",
        "state_delta",
        "state_update",
        "state_updates",
        "verification_state",
        "resume",
    ):
        value = payload.get(key)
        if isinstance(value, dict):
            contract_payload[key] = dict(value)
            continue
        if isinstance(value, (list, tuple, set)):
            items = _string_list(value)
            if items:
                contract_payload[key] = items
            continue
        text = _string(value)
        if text is not None:
            contract_payload[key] = text
    state_refs = _string_list(
        [
            *_string_list(payload.get("state_refs")),
            *_string_list(payload.get("state_change_refs")),
            *_string_list(payload.get("verification_state_refs")),
        ],
    )
    if state_refs:
        contract_payload["state_refs"] = state_refs
    if resolved_state_values:
        contract_payload["required_state_values"] = resolved_state_values

    if required_state_paths:
        contract_present = not missing_state_paths
    else:
        contract_present = bool(contract_payload)
    return {
        "required_state_paths": required_state_paths,
        "missing_state_paths": missing_state_paths,
        "contract_payload": contract_payload,
        "contract_present": contract_present,
    }


def _build_verification_payload(
    *,
    acceptance_mode: str,
    outcome: str,
    matched_hard_anchors: Sequence[str],
    matched_result_anchors: Sequence[str],
    missing_hard_anchors: Sequence[str],
    missing_result_anchors: Sequence[str],
    matched_negative_anchors: Sequence[str],
    verification_evidence_refs: Sequence[str],
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "acceptance_mode": acceptance_mode,
        "matched_hard_anchors": list(matched_hard_anchors),
        "matched_result_anchors": list(matched_result_anchors),
        "missing_hard_anchors": list(missing_hard_anchors),
        "missing_result_anchors": list(missing_result_anchors),
        "matched_negative_anchors": list(matched_negative_anchors),
        "verification_evidence_refs": list(verification_evidence_refs),
        "outcome": outcome,
    }
    if contract:
        payload["contract"] = dict(contract)
    return payload


def _resolve_verification_evidence_refs(
    *evidence_groups: object | None,
    payloads: Sequence[Mapping[str, Any] | None] = (),
) -> list[str]:
    refs: list[str] = []
    for group in evidence_groups:
        refs.extend(_string_list(group))
    for payload in payloads:
        mapping = _mapping(payload)
        refs.extend(
            _string_list(
                [
                    *list(mapping.get("media_analysis_ids") or []),
                    *list(mapping.get("evidence_refs") or []),
                    *list(mapping.get("verification_evidence_refs") or []),
                ],
            ),
        )
    return _string_list(refs)


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
        profile_id: str | None = None,
        chat_thread_id: str | None = None,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[HumanAssistTaskRecord]:
        return self._repository.list_tasks(
            profile_id=profile_id,
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
        profile_id: str | None = None,
        title: str,
        summary: str,
        required_action: str,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        resume_checkpoint_ref: str | None = None,
        verification_anchor: str | None = None,
        block_evidence_refs: Sequence[str] | None = None,
        continuation_context: Mapping[str, Any] | None = None,
    ) -> HumanAssistTaskRecord:
        normalized_thread_id = _string(chat_thread_id)
        if normalized_thread_id is None:
            raise ValueError("Host handoff human assist task requires a chat thread id")
        normalized_task_id = _string(task_id)
        merged_block_evidence_refs = _string_list(block_evidence_refs)
        for existing in self._repository.list_tasks(chat_thread_id=normalized_thread_id, limit=50):
            if existing.status in self._TERMINAL_STATUSES:
                continue
            if existing.task_type != "host-handoff-return":
                continue
            if _string(existing.profile_id) != _string(profile_id):
                continue
            if normalized_task_id is not None and existing.task_id not in {None, normalized_task_id}:
                continue
            updated = existing.model_copy(
                update={
                    "profile_id": _string(profile_id),
                    "submission_payload": _merge_submission_payload(
                        existing.submission_payload,
                        continuation_context,
                    ),
                    "block_evidence_refs": _string_list(
                        [*list(existing.block_evidence_refs), *merged_block_evidence_refs],
                    ),
                    "updated_at": _utc_now(),
                },
            )
            return self._repository.upsert_task(updated)

        anchor = (
            _string(verification_anchor)
            or _string(resume_checkpoint_ref)
            or "human-return"
        )
        anchor_hint = f"“{anchor}”" if anchor else "完成返回条件"
        record = HumanAssistTaskRecord(
            profile_id=_string(profile_id),
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
            block_evidence_refs=merged_block_evidence_refs,
            submission_payload=_merge_submission_payload({}, continuation_context),
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
                "submission_payload": _merge_submission_payload(
                    current.submission_payload,
                    submission_payload,
                ),
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
        previous = self._require_task(task_id)
        observed_submission_present = (
            _string(observed_text) is not None
            or bool(_string_list(observed_evidence_refs))
            or bool(_mapping(observed_payload))
        )
        submission_snapshot = previous
        if observed_submission_present:
            now = _utc_now()
            submission_snapshot = previous.model_copy(
                update={
                    "status": "submitted",
                    "submission_text": (
                        _string(observed_text)
                        if _string(observed_text) is not None
                        else previous.submission_text
                    ),
                    "submission_evidence_refs": _string_list(
                        [
                            *list(previous.submission_evidence_refs or []),
                            *_string_list(observed_evidence_refs),
                        ],
                    ),
                    "submission_payload": _merge_submission_payload(
                        previous.submission_payload,
                        observed_payload,
                    ),
                    "submitted_at": previous.submitted_at or now,
                    "updated_at": now,
                },
            )
            submission_snapshot = self._repository.upsert_task(submission_snapshot)
        fallback_status = submission_snapshot.status
        verifying = submission_snapshot.model_copy(
            update={"status": "verifying", "updated_at": _utc_now()},
        )
        current = self._repository.upsert_task(verifying)

        spec = _mapping(current.acceptance_spec)
        acceptance_mode = _string(current.acceptance_mode) or "anchor_verified"
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
        verification_evidence_refs = _resolve_verification_evidence_refs(
            current.submission_evidence_refs,
            observed_evidence_refs,
            payloads=[current.submission_payload, observed_payload],
        )
        state_contract = _collect_state_contract(
            _merge_submission_payload(current.submission_payload, observed_payload),
            spec,
        )
        contract_payload: dict[str, Any] | None = None
        contract_requirements_missing: list[str] = []
        if acceptance_mode == "evidence_verified":
            if not verification_evidence_refs:
                contract_requirements_missing.append("formal_evidence_refs")
            contract_payload = {
                "required_evidence_refs": max(
                    1,
                    _coerce_positive_int(spec.get("required_evidence_count"), default=1),
                ),
                "observed_evidence_refs": verification_evidence_refs,
                "missing_requirements": list(contract_requirements_missing),
            }
        elif acceptance_mode == "state_change_verified":
            if not verification_evidence_refs:
                contract_requirements_missing.append("formal_evidence_refs")
            if not bool(state_contract["contract_present"]):
                contract_requirements_missing.append("state_change_contract")
            contract_payload = {
                "required_state_paths": list(state_contract["required_state_paths"]),
                "missing_state_paths": list(state_contract["missing_state_paths"]),
                "state_payload": dict(state_contract["contract_payload"]),
                "missing_requirements": list(contract_requirements_missing),
            }

        if matched_negative:
            return self._finalize_verification(
                previous,
                outcome="rejected",
                status="rejected",
                action_summary="reject human assist task",
                message="检测到不通过锚点，当前提交未通过验收。",
                acceptance_mode=acceptance_mode,
                matched_hard_anchors=matched_hard,
                matched_result_anchors=matched_result,
                missing_hard_anchors=missing_hard,
                missing_result_anchors=missing_result,
                matched_negative_anchors=matched_negative,
                verification_evidence_refs=verification_evidence_refs,
                contract_payload=contract_payload,
                fallback_status=fallback_status,
                resume_queued=False,
            )

        if missing_hard or missing_result or contract_requirements_missing:
            failure_hint = _string(spec.get("failure_hint")) or "请补充更多可验证证据后再提交。"
            return self._finalize_verification(
                previous,
                outcome="need_more_evidence",
                status="need_more_evidence",
                action_summary="request more evidence for human assist task",
                message=failure_hint,
                acceptance_mode=acceptance_mode,
                matched_hard_anchors=matched_hard,
                matched_result_anchors=matched_result,
                missing_hard_anchors=missing_hard,
                missing_result_anchors=missing_result,
                matched_negative_anchors=[],
                verification_evidence_refs=verification_evidence_refs,
                contract_payload=contract_payload,
                fallback_status=fallback_status,
                resume_queued=False,
            )

        reward_result = dict(current.reward_preview or {"协作值": 1, "同调经验": 1})
        reward_result["granted"] = True
        verification_payload = _build_verification_payload(
            acceptance_mode=acceptance_mode,
            outcome="accepted",
            matched_hard_anchors=matched_hard,
            matched_result_anchors=matched_result,
            missing_hard_anchors=[],
            missing_result_anchors=[],
            matched_negative_anchors=[],
            verification_evidence_refs=verification_evidence_refs,
            contract=contract_payload,
        )
        accepted = current.model_copy(
            update={
                "status": "accepted",
                "reward_result": reward_result,
                "verification_evidence_refs": verification_evidence_refs,
                "verification_payload": verification_payload,
                "verified_at": _utc_now(),
                "updated_at": _utc_now(),
            },
        )
        persisted = self._repository.upsert_task(accepted)
        if not self._append_evidence(
            persisted,
            action_summary="accept human assist task",
            result_summary="human assist task accepted",
            metadata={"status": persisted.status, "reward_result": persisted.reward_result},
        ):
            return self._verification_record_failed(
                previous,
                pending_outcome="accepted",
                pending_payload=verification_payload,
                verification_evidence_refs=verification_evidence_refs,
                fallback_status=fallback_status,
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
        acceptance_mode: str,
        matched_hard_anchors: list[str],
        matched_result_anchors: list[str],
        missing_hard_anchors: list[str],
        missing_result_anchors: list[str],
        matched_negative_anchors: list[str],
        verification_evidence_refs: list[str],
        contract_payload: Mapping[str, Any] | None,
        fallback_status: str,
        resume_queued: bool,
    ) -> HumanAssistVerificationResult:
        now = _utc_now()
        verification_payload = _build_verification_payload(
            acceptance_mode=acceptance_mode,
            outcome=outcome,
            matched_hard_anchors=matched_hard_anchors,
            matched_result_anchors=matched_result_anchors,
            missing_hard_anchors=missing_hard_anchors,
            missing_result_anchors=missing_result_anchors,
            matched_negative_anchors=matched_negative_anchors,
            verification_evidence_refs=verification_evidence_refs,
            contract=contract_payload,
        )
        updated = task.model_copy(
            update={
                "status": status,
                "verification_evidence_refs": verification_evidence_refs,
                "verification_payload": verification_payload,
                "verified_at": now,
                "updated_at": now,
            },
        )
        persisted = self._repository.upsert_task(updated)
        if not self._append_evidence(
            persisted,
            action_summary=action_summary,
            result_summary=message,
            metadata={
                "status": persisted.status,
                "outcome": outcome,
                "missing_hard_anchors": missing_hard_anchors,
                "missing_result_anchors": missing_result_anchors,
            },
        ):
            return self._verification_record_failed(
                task,
                pending_outcome=outcome,
                pending_payload=verification_payload,
                verification_evidence_refs=verification_evidence_refs,
                fallback_status=fallback_status,
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

    def _verification_record_failed(
        self,
        task: HumanAssistTaskRecord,
        *,
        pending_outcome: str,
        pending_payload: Mapping[str, Any],
        verification_evidence_refs: Sequence[str],
        fallback_status: str,
    ) -> HumanAssistVerificationResult:
        now = _utc_now()
        failure_payload = dict(pending_payload)
        failure_payload["outcome"] = "verification_record_failed"
        failure_payload["pending_outcome"] = pending_outcome
        failure_payload["error"] = "evidence-ledger-unavailable"
        updated = task.model_copy(
            update={
                "status": fallback_status,
                "verification_evidence_refs": list(verification_evidence_refs),
                "verification_payload": failure_payload,
                "updated_at": now,
            },
        )
        persisted = self._repository.upsert_task(updated)
        return HumanAssistVerificationResult(
            outcome="verification_record_failed",
            task=persisted,
            message="验收结果未能正式落证，任务保持原状态。",
            matched_hard_anchors=_string_list(
                _mapping(pending_payload).get("matched_hard_anchors"),
            ),
            matched_result_anchors=_string_list(
                _mapping(pending_payload).get("matched_result_anchors"),
            ),
            missing_hard_anchors=_string_list(
                _mapping(pending_payload).get("missing_hard_anchors"),
            ),
            missing_result_anchors=_string_list(
                _mapping(pending_payload).get("missing_result_anchors"),
            ),
            matched_negative_anchors=_string_list(
                _mapping(pending_payload).get("matched_negative_anchors"),
            ),
            resume_queued=False,
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
    ) -> bool:
        if self._evidence_ledger is None:
            return True
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
            return False
        return True


__all__ = ["HumanAssistTaskService", "HumanAssistVerificationResult"]
