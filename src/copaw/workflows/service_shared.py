# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any

from ..capabilities.install_templates import (
    list_install_templates,
    match_install_template_capability_ids,
)
from ..evidence import EvidenceLedger
from ..goals import GoalService
from ..industry.identity import EXECUTION_CORE_AGENT_ID, EXECUTION_CORE_ROLE_ID
from ..state import (
    GoalOverrideRecord,
    ScheduleRecord,
    WorkflowPresetRecord,
    WorkflowRunRecord,
    WorkflowTemplateRecord,
)
from ..state.repositories import (
    SqliteAgentProfileOverrideRepository,
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteIndustryInstanceRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteWorkflowPresetRepository,
    SqliteWorkflowRunRepository,
    SqliteWorkflowTemplateRepository,
)
from ..state.strategy_memory_service import resolve_strategy_payload
from ..workflows.models import (
    WorkflowTemplateAgentBudgetStatus,
    WorkflowLaunchRequest,
    WorkflowPreviewRequest,
    WorkflowRunDiagnosis,
    WorkflowRunDetail,
    WorkflowStepExecutionDetail,
    WorkflowStepExecutionRecord,
    WorkflowTemplateDependencyStatus,
    WorkflowTemplateInstallTemplateRef,
    WorkflowTemplateLaunchBlocker,
    WorkflowTemplatePreview,
    WorkflowTemplateStepPreview,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _SafeDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _unique_strings(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                items.append(normalized)
            continue
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                items.append(normalized)
    return items


def _workflow_step_execution_seed(run: WorkflowRunRecord) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in list(dict(run.metadata or {}).get("step_execution_seed") or [])
        if isinstance(item, dict)
    ]


def _workflow_linked_resource_ids(
    run: WorkflowRunRecord,
    *,
    key: str,
) -> list[str]:
    return _unique_strings(
        *[
            [
                str(item)
                for item in list(seed.get(key) or [])
                if str(item).strip()
            ]
            for seed in _workflow_step_execution_seed(run)
        ],
    )


def _workflow_goal_ids_by_step(
    run: WorkflowRunRecord,
    *,
    goal_override_repository: SqliteGoalOverrideRepository | None,
) -> dict[str, list[str]]:
    ids_by_step: dict[str, list[str]] = {}
    for seed in _workflow_step_execution_seed(run):
        step_id = _string(seed.get("step_id"))
        if step_id is None:
            continue
        legacy_ids = [
            str(item)
            for item in list(seed.get("linked_goal_ids") or [])
            if str(item).strip()
        ]
        if legacy_ids:
            ids_by_step[step_id] = _unique_strings(legacy_ids)
    if goal_override_repository is None:
        return ids_by_step
    list_overrides = getattr(goal_override_repository, "list_overrides", None)
    if not callable(list_overrides):
        return ids_by_step
    for override in list_overrides() or []:
        goal_id = _string(getattr(override, "goal_id", None))
        compiler_context = dict(getattr(override, "compiler_context", None) or {})
        workflow_run_id = _string(compiler_context.get("workflow_run_id"))
        workflow_step_id = _string(compiler_context.get("workflow_step_id"))
        if workflow_run_id != run.run_id or workflow_step_id is None or goal_id is None:
            continue
        ids_by_step[workflow_step_id] = _unique_strings(
            ids_by_step.get(workflow_step_id, []),
            [goal_id],
        )
    return ids_by_step


def _workflow_step_schedule_id(
    run: WorkflowRunRecord,
    *,
    step_id: str,
    payload_preview: dict[str, Any] | None = None,
) -> str:
    payload = dict(payload_preview or {})
    return _string(payload.get("id")) or f"{run.run_id}:{step_id}"


def _workflow_schedule_ids_for_preview(
    run: WorkflowRunRecord,
    preview: WorkflowTemplatePreview,
) -> list[str]:
    return _unique_strings(
        [
        _workflow_step_schedule_id(
            run,
            step_id=step.step_id,
            payload_preview=dict(step.payload_preview or {}),
        )
        for step in preview.steps
        if step.kind == "schedule"
        ],
    )


def _render_text(template: object | None, context: dict[str, Any]) -> str:
    if template is None:
        return ""
    text = str(template)
    return text.format_map(_SafeDict(context)).strip()



__all__ = [name for name in globals() if not name.startswith("__")]
