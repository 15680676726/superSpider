# -*- coding: utf-8 -*-
"""Derived internal-exception absorption helpers for the main brain."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


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


@dataclass(frozen=True, slots=True)
class AbsorptionAction:
    kind: str
    case_kind: str
    recovery_rung: str
    owner_agent_id: str | None
    scope_ref: str | None
    summary: str | None = None
    replan_decision_kind: str | None = None
    replan_decision: dict[str, object] = field(default_factory=dict)
    human_required: bool = False
    human_action_summary: str | None = None
    human_action_contract: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AbsorptionContinuityContext:
    chat_thread_id: str | None = None
    control_thread_id: str | None = None
    session_id: str | None = None
    industry_instance_id: str | None = None
    assignment_id: str | None = None
    task_id: str | None = None
    work_context_id: str | None = None
    environment_ref: str | None = None
    profile_id: str | None = None
    channel: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "chat_thread_id": self.chat_thread_id,
            "control_thread_id": self.control_thread_id,
            "session_id": self.session_id,
            "industry_instance_id": self.industry_instance_id,
            "assignment_id": self.assignment_id,
            "task_id": self.task_id,
            "work_context_id": self.work_context_id,
            "environment_ref": self.environment_ref,
            "profile_id": self.profile_id,
            "channel": self.channel,
        }


def _first_non_empty(*values: object | None) -> str | None:
    for value in values:
        if (text := _string(value)) is not None:
            return text
    return None


def _match_action_subject(action: AbsorptionAction, candidate: object) -> bool:
    candidate_agent_id = _string(_field(candidate, "agent_id"))
    if action.owner_agent_id is not None and candidate_agent_id == action.owner_agent_id:
        return True
    return _first_non_empty(
        _field(candidate, "task_id"),
        _field(candidate, "work_context_id"),
        _field(candidate, "conversation_thread_id"),
        _metadata(candidate).get("blocked_scope_ref"),
        _metadata(candidate).get("assignment_id"),
        _metadata(candidate).get("work_context_id"),
        _metadata(candidate).get("environment_ref"),
    ) == _string(action.scope_ref)


def _apply_context(
    context: dict[str, str | None],
    *,
    primary: dict[str, object],
    metadata: dict[str, object],
    nested_payload: dict[str, object],
) -> None:
    context["chat_thread_id"] = _first_non_empty(
        context.get("chat_thread_id"),
        primary.get("conversation_thread_id"),
        primary.get("chat_thread_id"),
        primary.get("control_thread_id"),
        primary.get("session_id"),
        metadata.get("conversation_thread_id"),
        metadata.get("chat_thread_id"),
        metadata.get("control_thread_id"),
        metadata.get("session_id"),
        nested_payload.get("conversation_thread_id"),
        nested_payload.get("chat_thread_id"),
        nested_payload.get("control_thread_id"),
        nested_payload.get("session_id"),
    )
    context["control_thread_id"] = _first_non_empty(
        context.get("control_thread_id"),
        primary.get("control_thread_id"),
        metadata.get("control_thread_id"),
        nested_payload.get("control_thread_id"),
        context.get("chat_thread_id"),
    )
    context["session_id"] = _first_non_empty(
        context.get("session_id"),
        primary.get("session_id"),
        metadata.get("session_id"),
        nested_payload.get("session_id"),
        context.get("chat_thread_id"),
    )
    context["industry_instance_id"] = _first_non_empty(
        context.get("industry_instance_id"),
        primary.get("industry_instance_id"),
        metadata.get("industry_instance_id"),
        nested_payload.get("industry_instance_id"),
    )
    context["assignment_id"] = _first_non_empty(
        context.get("assignment_id"),
        primary.get("assignment_id"),
        metadata.get("assignment_id"),
        nested_payload.get("assignment_id"),
    )
    context["task_id"] = _first_non_empty(
        context.get("task_id"),
        primary.get("task_id"),
        metadata.get("task_id"),
        nested_payload.get("task_id"),
    )
    context["work_context_id"] = _first_non_empty(
        context.get("work_context_id"),
        primary.get("work_context_id"),
        metadata.get("work_context_id"),
        nested_payload.get("work_context_id"),
    )
    context["environment_ref"] = _first_non_empty(
        context.get("environment_ref"),
        primary.get("environment_ref"),
        metadata.get("environment_ref"),
        nested_payload.get("environment_ref"),
    )
    context["profile_id"] = _first_non_empty(
        context.get("profile_id"),
        primary.get("buddy_profile_id"),
        primary.get("profile_id"),
        metadata.get("buddy_profile_id"),
        metadata.get("profile_id"),
        nested_payload.get("buddy_profile_id"),
        nested_payload.get("profile_id"),
    )
    context["channel"] = _first_non_empty(
        context.get("channel"),
        primary.get("channel"),
        metadata.get("channel"),
        nested_payload.get("channel"),
    )


def resolve_absorption_continuity_context(
    action: AbsorptionAction,
    *,
    runtimes: list[object] | tuple[object, ...],
    mailbox_items: list[object] | tuple[object, ...],
) -> AbsorptionContinuityContext:
    context: dict[str, str | None] = {
        "chat_thread_id": None,
        "control_thread_id": None,
        "session_id": None,
        "industry_instance_id": None,
        "assignment_id": None,
        "task_id": None,
        "work_context_id": None,
        "environment_ref": None,
        "profile_id": None,
        "channel": None,
    }
    for runtime in list(runtimes or []):
        if not _match_action_subject(action, runtime):
            continue
        primary = _mapping(runtime)
        _apply_context(
            context,
            primary=primary,
            metadata=_metadata(runtime),
            nested_payload=_mapping(primary.get("payload")),
        )
    for item in list(mailbox_items or []):
        if not _match_action_subject(action, item):
            continue
        primary = _mapping(item)
        _apply_context(
            context,
            primary=primary,
            metadata=_metadata(item),
            nested_payload=_mapping(primary.get("payload")),
        )
    return AbsorptionContinuityContext(**context)


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

    def absorb(
        self,
        *,
        runtimes: list[object] | tuple[object, ...],
        mailbox_items: list[object] | tuple[object, ...],
        human_assist_tasks: list[object] | tuple[object, ...],
        now: datetime,
        report_replan_engine: object | None = None,
        human_assist_contract_builder: object | None = None,
    ) -> AbsorptionAction | None:
        summary = self.scan(
            runtimes=runtimes,
            mailbox_items=mailbox_items,
            human_assist_tasks=human_assist_tasks,
            now=now,
        )
        active_human_assist_count = self._count_active_human_assist_tasks(human_assist_tasks)
        human_case = next((case for case in summary.active_cases if case.human_required), None)
        if human_case is not None and active_human_assist_count <= 0:
            contract = self._build_human_action_contract(
                case=human_case,
                human_assist_contract_builder=human_assist_contract_builder,
            )
            return AbsorptionAction(
                kind="human-assist",
                case_kind=human_case.case_kind,
                recovery_rung=human_case.recovery_rung,
                owner_agent_id=human_case.owner_agent_id,
                scope_ref=human_case.scope_ref,
                summary=human_case.summary,
                human_required=True,
                human_action_summary=(
                    _string(contract.get("required_action"))
                    or _string(contract.get("summary"))
                    or human_case.summary
                ),
                human_action_contract=contract,
            )
        structural_case = next(
            (
                case
                for case in summary.active_cases
                if case.case_kind in {"repeated-blocker-same-scope", "progressless-runtime", "retry-loop"}
            ),
            None,
        )
        if structural_case is None:
            return None
        replan_decision_payload: dict[str, Any] = {}
        replan_decision_kind: str | None = None
        compiler = getattr(report_replan_engine, "compile_exception_absorption_replan", None)
        if callable(compiler):
            decision = compiler(
                case_kind=structural_case.case_kind,
                scope_ref=structural_case.scope_ref,
                owner_agent_id=structural_case.owner_agent_id,
                summary=structural_case.summary,
            )
            model_dump = getattr(decision, "model_dump", None)
            if callable(model_dump):
                payload = model_dump(mode="json", exclude_none=True)
                if isinstance(payload, dict):
                    replan_decision_payload = payload
            replan_decision_kind = _string(
                replan_decision_payload.get("strategy_change_decision")
                or replan_decision_payload.get("decision_kind"),
            )
        if replan_decision_kind is None:
            replan_decision_kind = {
                "repeated-blocker-same-scope": "cycle_rebalance",
                "progressless-runtime": "cycle_rebalance",
                "retry-loop": "lane_reweight",
            }.get(structural_case.case_kind, "follow_up_backlog")
        return AbsorptionAction(
            kind="replan",
            case_kind=structural_case.case_kind,
            recovery_rung=structural_case.recovery_rung,
            owner_agent_id=structural_case.owner_agent_id,
            scope_ref=structural_case.scope_ref,
            summary=structural_case.summary,
            replan_decision_kind=replan_decision_kind,
            replan_decision=replan_decision_payload,
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
                    summary="重复写冲突正在阻塞同一执行面。",
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
                    summary="重复阻塞压力正在命中同一执行范围。",
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
                    summary="运行时正在反复重试，但始终没有清掉阻塞。",
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
                    summary="运行时虽然仍然存活，但还没有产生有效进展。",
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
                        summary="有一条租约占用过久，但对应工作仍未收口。",
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
            summary="一个绑定确认的人类步骤已经超过安全等待窗口，仍然处于阻塞状态。",
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
                    "主脑当前没有活跃的内部异常压力，但仍有未关闭的人类协助检查点。"
                )
            return "主脑当前没有活跃的内部异常压力。"
        if human_required_case_count > 0:
            return (
                "主脑正在吸收内部执行压力，且至少有一个案例现在需要受治理的人类动作。"
            )
        return "主脑正在吸收内部执行压力，并在升级前继续尝试自主恢复。"

    def _count_active_human_assist_tasks(
        self,
        human_assist_tasks: list[object] | tuple[object, ...],
    ) -> int:
        return sum(
            1
            for task in list(human_assist_tasks or [])
            if _string(_field(task, "status")) not in {"resume_queued", "closed", "expired", "cancelled"}
        )

    def _build_human_action_contract(
        self,
        *,
        case: AbsorptionCase,
        human_assist_contract_builder: object | None,
    ) -> dict[str, object]:
        builder = human_assist_contract_builder if callable(human_assist_contract_builder) else None
        if builder is not None:
            try:
                payload = builder(
                    case_kind=case.case_kind,
                    scope_ref=case.scope_ref,
                    summary=case.summary,
                )
            except TypeError:
                payload = builder(case.case_kind, case.scope_ref, case.summary)
            if isinstance(payload, dict):
                return dict(payload)
        anchor = _string(case.scope_ref) or "human-return"
        return {
            "title": "补一个必要确认" if case.case_kind == "waiting-confirm-orphan" else "补一个必要人类动作",
            "summary": _string(case.summary)
            or "主脑已经完成内部恢复，当前需要一个明确的人类动作才能继续。",
            "required_action": (
                f"请在聊天里完成并确认 “{anchor}” 对应的人类步骤，系统收到后会继续自动恢复。"
            ),
            "acceptance_spec": {
                "version": "v1",
                "hard_anchors": [anchor],
            },
            "resume_checkpoint_ref": anchor,
        }


__all__ = [
    "AbsorptionAction",
    "AbsorptionCase",
    "AbsorptionContinuityContext",
    "AbsorptionSummary",
    "MainBrainExceptionAbsorptionService",
    "resolve_absorption_continuity_context",
]
