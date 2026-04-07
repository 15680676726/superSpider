# -*- coding: utf-8 -*-
"""Derived internal-exception absorption helpers for the main brain."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime, timedelta


def _mapping(value: object | None) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if value is not None and is_dataclass(value):
        payload = asdict(value)
        if isinstance(payload, dict):
            return dict(payload)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: object | None, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = _string(value)
    if text is None:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _datetime(value: object | None) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    text = _string(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _metadata(item: object | None) -> dict[str, object]:
    payload = _mapping(item)
    raw_metadata = payload.get("metadata")
    if isinstance(raw_metadata, dict):
        return dict(raw_metadata)
    return {}


def _field(item: object | None, name: str) -> object | None:
    payload = _mapping(item)
    if name in payload:
        return payload.get(name)
    metadata = _metadata(item)
    if name in metadata:
        return metadata.get(name)
    return getattr(item, name, None)


@dataclass(frozen=True, slots=True)
class AbsorptionCase:
    case_kind: str
    owner_agent_id: str | None
    scope_ref: str | None
    recovery_rung: str
    human_required: bool = False
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class AbsorptionSummary:
    active_cases: list[AbsorptionCase] = field(default_factory=list)
    case_counts: dict[str, int] = field(default_factory=dict)
    recovery_counts: dict[str, int] = field(default_factory=dict)
    main_brain_summary: str = ""
    human_required_case_count: int = 0

    @property
    def case_count(self) -> int:
        return len(self.active_cases)


@dataclass(slots=True)
class MainBrainExceptionAbsorptionService:
    retry_loop_threshold: int = 3
    stale_lease_after: timedelta = timedelta(minutes=15)
    waiting_confirm_orphan_after: timedelta = timedelta(minutes=15)
    progressless_runtime_after: timedelta = timedelta(minutes=20)
    repeated_blocker_threshold: int = 2

    def scan(
        self,
        *,
        runtimes: list[object] | tuple[object, ...],
        mailbox_items: list[object] | tuple[object, ...],
        human_assist_tasks: list[object] | tuple[object, ...],
        now: datetime,
    ) -> AbsorptionSummary:
        resolved_now = now.astimezone(UTC) if now.tzinfo is not None else now.replace(tzinfo=UTC)
        active_cases: list[AbsorptionCase] = []

        for runtime in list(runtimes or []):
            active_cases.extend(self._scan_runtime(runtime=runtime, now=resolved_now))

        for item in list(mailbox_items or []):
            case = self._scan_mailbox_item(item=item, now=resolved_now)
            if case is not None:
                active_cases.append(case)

        case_counts = dict(Counter(case.case_kind for case in active_cases))
        recovery_counts = dict(Counter(case.recovery_rung for case in active_cases))
        human_required_case_count = sum(1 for case in active_cases if case.human_required)
        active_human_assist_count = sum(
            1
            for task in list(human_assist_tasks or [])
            if _string(_field(task, "status")) not in {"resume_queued", "closed", "expired", "cancelled"}
        )

        summary = self._build_main_brain_summary(
            active_cases=active_cases,
            human_required_case_count=human_required_case_count,
            active_human_assist_count=active_human_assist_count,
        )
        return AbsorptionSummary(
            active_cases=active_cases,
            case_counts=case_counts,
            recovery_counts=recovery_counts,
            main_brain_summary=summary,
            human_required_case_count=human_required_case_count,
        )

    def _scan_runtime(self, *, runtime: object, now: datetime) -> list[AbsorptionCase]:
        metadata = _metadata(runtime)
        agent_id = _string(_field(runtime, "agent_id"))
        runtime_status = _string(_field(runtime, "runtime_status")) or "idle"
        cases: list[AbsorptionCase] = []

        writer_conflict_count = _int(
            metadata.get("writer_conflict_count") or metadata.get("shared_writer_conflict_count"),
        )
        if writer_conflict_count >= 2:
            cases.append(
                AbsorptionCase(
                    case_kind="writer-contention",
                    owner_agent_id=agent_id,
                    scope_ref=(
                        _string(metadata.get("writer_lock_scope"))
                        or _string(metadata.get("blocked_scope_ref"))
                    ),
                    recovery_rung="cleanup",
                    summary="Repeated writer conflicts are blocking the same surface.",
                )
            )

        repeated_blocker_count = _int(metadata.get("repeated_blocker_count"))
        if repeated_blocker_count >= self.repeated_blocker_threshold:
            cases.append(
                AbsorptionCase(
                    case_kind="repeated-blocker-same-scope",
                    owner_agent_id=agent_id,
                    scope_ref=(
                        _string(metadata.get("blocked_scope_ref"))
                        or _string(metadata.get("assignment_id"))
                        or _string(metadata.get("lane_id"))
                    ),
                    recovery_rung="replan",
                    summary="Repeated blocker pressure is hitting the same execution scope.",
                )
            )

        retry_count = _int(metadata.get("retry_count"))
        if retry_count >= self.retry_loop_threshold:
            cases.append(
                AbsorptionCase(
                    case_kind="retry-loop",
                    owner_agent_id=agent_id,
                    scope_ref=_string(metadata.get("blocked_scope_ref")) or _string(metadata.get("assignment_id")),
                    recovery_rung="retry",
                    summary="The runtime is retrying repeatedly without clearing the blocker.",
                )
            )

        last_progress_at = _datetime(
            metadata.get("last_progress_at")
            or metadata.get("progress_at")
            or metadata.get("last_heartbeat_at"),
        )
        if (
            runtime_status in {"running", "waiting", "executing", "claimed"}
            and last_progress_at is not None
            and now - last_progress_at >= self.progressless_runtime_after
        ):
            cases.append(
                AbsorptionCase(
                    case_kind="progressless-runtime",
                    owner_agent_id=agent_id,
                    scope_ref=_string(metadata.get("work_context_id")) or _string(metadata.get("assignment_id")),
                    recovery_rung="replan",
                    summary="The runtime is still alive but has not made useful progress.",
                )
            )

        lease_started_at = _datetime(
            metadata.get("lease_started_at")
            or metadata.get("lease_acquired_at")
            or metadata.get("actor_lease_started_at"),
        )
        if runtime_status in {"claimed", "waiting", "running"} and lease_started_at is not None:
            if now - lease_started_at >= self.stale_lease_after:
                cases.append(
                    AbsorptionCase(
                        case_kind="stale-lease",
                        owner_agent_id=agent_id,
                        scope_ref=_string(metadata.get("environment_ref")) or _string(metadata.get("work_context_id")),
                        recovery_rung="cleanup",
                        summary="A lease has been held too long without resolving the work.",
                    )
                )

        return cases

    def _scan_mailbox_item(self, *, item: object, now: datetime) -> AbsorptionCase | None:
        metadata = _metadata(item)
        task_phase = _string(_field(item, "task_phase")) or _string(metadata.get("task_phase"))
        updated_at = _datetime(_field(item, "updated_at")) or _datetime(metadata.get("updated_at"))
        if task_phase != "waiting-confirm" or updated_at is None:
            return None
        if now - updated_at < self.waiting_confirm_orphan_after:
            return None
        return AbsorptionCase(
            case_kind="waiting-confirm-orphan",
            owner_agent_id=_string(_field(item, "agent_id")),
            scope_ref=_string(_field(item, "task_id")) or _string(metadata.get("checkpoint_id")),
            recovery_rung="escalate",
            human_required=True,
            summary="A confirmation-bound task has remained blocked past its safe waiting window.",
        )

    def _build_main_brain_summary(
        self,
        *,
        active_cases: list[AbsorptionCase],
        human_required_case_count: int,
        active_human_assist_count: int,
    ) -> str:
        if not active_cases:
            if active_human_assist_count > 0:
                return (
                    "Main brain is clear of active internal exception pressure, "
                    "but there are still open human-assist checkpoints."
                )
            return "Main brain is clear of active internal exception pressure."
        if human_required_case_count > 0:
            return (
                "Main brain is absorbing internal execution pressure and at least one case "
                "now requires a governed human step."
            )
        return (
            "Main brain is absorbing internal execution pressure and is still attempting "
            "autonomous recovery before escalating."
        )


__all__ = [
    "AbsorptionCase",
    "AbsorptionSummary",
    "MainBrainExceptionAbsorptionService",
]
