from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any


def collect_recent_execution_feedback(
    *,
    tasks: Iterable[object],
    task_runtime_repository: Any | None = None,
    evidence_ledger: Any | None = None,
    evidence_limit: int = 80,
) -> dict[str, object]:
    task_list = list(tasks)
    if not task_list:
        return {}

    runtimes = {
        getattr(task, "id", None): (
            task_runtime_repository.get_runtime(getattr(task, "id", None))
            if task_runtime_repository is not None and getattr(task, "id", None)
            else None
        )
        for task in task_list
    }
    latest_task = max(
        task_list,
        key=lambda item: _sort_datetime_value(
            getattr(runtimes.get(getattr(item, "id", None)), "updated_at", None),
            getattr(item, "updated_at", None),
        ),
    )
    latest_runtime = runtimes.get(getattr(latest_task, "id", None))
    latest_stage = (
        str(getattr(latest_runtime, "current_phase", "") or "").strip()
        or str(getattr(latest_task, "status", "") or "").strip()
    )
    latest_title = str(getattr(latest_task, "title", "") or "").strip()
    current_stage = (
        f"{latest_title} [{latest_stage}]"
        if latest_stage and latest_title
        else latest_stage or None
    )

    if evidence_ledger is None:
        return {"current_stage": current_stage} if current_stage else {}

    task_ids = {
        str(getattr(task, "id", "") or "").strip()
        for task in task_list
        if str(getattr(task, "id", "") or "").strip()
    }
    if not task_ids:
        return {"current_stage": current_stage} if current_stage else {}

    recent_records = [
        record
        for record in evidence_ledger.list_recent(limit=max(1, int(evidence_limit)))
        if str(getattr(record, "task_id", "") or "").strip() in task_ids
    ]
    recent_records.sort(
        key=lambda item: _sort_datetime_value(getattr(item, "created_at", None)),
        reverse=True,
    )

    recent_failures: list[str] = []
    effective_actions: list[str] = []
    evidence_refs: list[str] = []
    repeated_failures: dict[str, dict[str, object]] = {}

    for record in recent_records:
        line = _execution_feedback_line(record)
        if line is None:
            continue
        record_id = str(getattr(record, "id", "") or "").strip()
        if record_id:
            evidence_refs = _merge_string_lists(evidence_refs, [record_id])
        if _is_failure_evidence(record):
            if line not in recent_failures and len(recent_failures) < 4:
                recent_failures.append(line)
            pattern_key = (
                f"{getattr(record, 'capability_ref', '') or ''}::"
                f"{getattr(record, 'action_summary', '') or ''}"
            ).strip().lower() or line.lower()
            bucket = repeated_failures.setdefault(
                pattern_key,
                {"count": 0, "sample": line},
            )
            bucket["count"] = int(bucket["count"]) + 1
        else:
            if line not in effective_actions and len(effective_actions) < 4:
                effective_actions.append(line)

    avoid_repeats = [
        f"{bucket['sample']} (failed {bucket['count']} times)"
        for bucket in sorted(
            repeated_failures.values(),
            key=lambda item: int(item.get("count", 0)),
            reverse=True,
        )
        if int(bucket.get("count", 0)) >= 2
    ][:4]

    if not any([current_stage, recent_failures, effective_actions, avoid_repeats, evidence_refs]):
        return {}
    return {
        "current_stage": current_stage,
        "recent_failures": recent_failures,
        "effective_actions": effective_actions,
        "avoid_repeats": avoid_repeats,
        "evidence_refs": evidence_refs,
    }


def _merge_string_lists(*values: object) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in values:
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple, set, frozenset)):
            items = list(value)
        else:
            items = []
        for item in items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def _sort_datetime_value(*values: object) -> str:
    for value in values:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_failure_evidence(record: object) -> bool:
    if getattr(record, "status", None) == "failed":
        return True
    summary = (
        f"{getattr(record, 'action_summary', '')} {getattr(record, 'result_summary', '')}"
    ).lower()
    return "failed" in summary or "error" in summary


def _execution_feedback_line(record: object) -> str | None:
    capability = str(getattr(record, "capability_ref", "") or "").strip()
    action = str(getattr(record, "action_summary", "") or "").strip()
    result = str(getattr(record, "result_summary", "") or "").strip()
    label = " / ".join(part for part in (capability, action) if part)
    text = f"{label}: {result}" if label and result else result or label
    text = text.replace("\n", " ").strip()
    if not text:
        return None
    if len(text) > 220:
        return f"{text[:217].rstrip()}..."
    return text
