# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from typing import Any

from ..evidence import EvidenceRecord
from ..kernel.persistence import decode_kernel_task_metadata
from ..state import TaskRecord
from .models import GrowthEvent, Patch

_MAIN_BRAIN_ACTOR = "copaw-main-brain"


class LearningRuntimeDelegate:
    """Delegate object that transparently reads state from the runtime core."""

    def __init__(self, core: object) -> None:
        self._core = core

    def __getattr__(self, name: str) -> object:
        return getattr(self._core, name)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_failure_record(record: EvidenceRecord) -> bool:
    if record.status == "failed":
        return True
    summary = f"{record.action_summary} {record.result_summary}".lower()
    return "failed" in summary or "error" in summary


def _is_strategy_actionable_failure_record(record: EvidenceRecord) -> bool:
    if not _is_failure_record(record):
        return False
    capability_ref = str(record.capability_ref or "").strip().lower()
    # Ignore learning's own derived bookkeeping failures here; those belong to
    # acquisition/onboarding governance, not the generic capability strategy loop.
    if capability_ref.startswith("learning:"):
        return False
    return True


def _parse_strategy_metadata(diff_summary: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for chunk in diff_summary.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            metadata[key] = value
    return metadata


def _list_like(value: object | None) -> list[object]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _mcp_trial_tool_entries(payload: object) -> list[object]:
    if isinstance(payload, dict):
        return _list_like(payload.get("tools"))
    tools = getattr(payload, "tools", None)
    return _list_like(tools)


def _mcp_trial_tool_name(tool: object) -> str:
    if isinstance(tool, dict):
        for key in ("name", "tool_name"):
            value = str(tool.get(key) or "").strip()
            if value:
                return value
        return ""
    for attr in ("name", "tool_name"):
        value = str(getattr(tool, attr, "") or "").strip()
        if value:
            return value
    return ""


def _mcp_trial_tool_required_args(tool: object) -> list[str]:
    schema: object | None = None
    if isinstance(tool, dict):
        schema = tool.get("inputSchema") or tool.get("input_schema") or tool.get(
            "parameters",
        )
    else:
        schema = (
            getattr(tool, "inputSchema", None)
            or getattr(tool, "input_schema", None)
            or getattr(tool, "parameters", None)
        )
    if isinstance(schema, dict):
        return [
            str(item).strip()
            for item in list(schema.get("required") or [])
            if str(item).strip()
        ]
    return [
        str(item).strip()
        for item in list(getattr(schema, "required", []) or [])
        if str(item).strip()
    ]


def _pick_safe_mcp_trial_tool_name(tool_entries: list[object]) -> str | None:
    safe_suffixes = ("ping", "health", "status", "version", "about", "info")
    for tool in tool_entries:
        name = _mcp_trial_tool_name(tool)
        if not name or _mcp_trial_tool_required_args(tool):
            continue
        normalized = name.lower()
        if any(
            normalized == suffix
            or normalized.endswith(f".{suffix}")
            or normalized.endswith(f"_{suffix}")
            or normalized.endswith(f"-{suffix}")
            for suffix in safe_suffixes
        ):
            return name
    return None


def _resolve_growth_agent_id(
    patch: Patch,
    *,
    execution: dict[str, object],
    fallback: str,
) -> str:
    target_agent_id = execution.get("target_agent_id")
    if isinstance(target_agent_id, str) and target_agent_id:
        return target_agent_id
    metadata = _parse_strategy_metadata(patch.diff_summary)
    for key in ("target_agent", "agent_id", "agent", "owner_agent_id"):
        value = metadata.get(key)
        if value:
            return value
    return fallback


async def _maybe_await(value: object) -> object:
    if hasattr(value, "__await__"):
        return await value  # type: ignore[misc]
    return value


def _normalize_optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _compact_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    compacted = {
        str(key): value
        for key, value in metadata.items()
        if value not in (None, "", [], {}, ())
    }
    return compacted or None


def _stable_learning_id(prefix: str, key: str) -> str:
    digest = sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


def _strategy_target_layer(capability_ref: str) -> str:
    if capability_ref.startswith("tool:"):
        return "capabilities"
    if capability_ref.startswith("mcp:"):
        return "mcp"
    if capability_ref.startswith("skill:"):
        return "skills"
    return "runtime"


def _patch_matches(
    patch: Patch,
    *,
    goal_id: str | None,
    task_id: str | None,
    agent_id: str | None,
    evidence_id: str | None,
) -> bool:
    if goal_id is not None and patch.goal_id != goal_id:
        return False
    if task_id is not None and patch.task_id != task_id:
        return False
    if agent_id is not None and patch.agent_id != agent_id:
        return False
    if evidence_id is None:
        return True
    if patch.source_evidence_id == evidence_id:
        return True
    return evidence_id in patch.evidence_refs


def _growth_matches(
    event: GrowthEvent,
    *,
    agent_id: str | None,
    goal_id: str | None,
    task_id: str | None,
    source_patch_id: str | None,
    source_evidence_id: str | None,
) -> bool:
    if agent_id is not None and event.agent_id != agent_id:
        return False
    if goal_id is not None and event.goal_id != goal_id:
        return False
    if task_id is not None and event.task_id != task_id:
        return False
    if source_patch_id is not None and event.source_patch_id != source_patch_id:
        return False
    if (
        source_evidence_id is not None
        and event.source_evidence_id != source_evidence_id
    ):
        return False
    return True


def _acquisition_constraints_summary(
    title: str,
    *,
    risk_level: str,
    acquisition_kind: str,
) -> str:
    return (
        f"risk={risk_level}; acquisition_kind={acquisition_kind}; "
        f"title={title}"
    )


def _acquisition_acceptance_criteria(title: str, *, acquisition_kind: str) -> str:
    return f"{title}: {acquisition_kind} onboarding passes with recorded evidence."


def _patch_constraints_summary(patch: Patch) -> str | None:
    metadata = _parse_strategy_metadata(patch.diff_summary)
    if not metadata:
        return None
    return "; ".join(f"{key}={value}" for key, value in metadata.items())


def _patch_acceptance_criteria(patch: Patch) -> str:
    if patch.risk_level == "confirm":
        return f"Patch {patch.title} must be approved before apply."
    return f"Patch {patch.title} can be applied with recorded evidence."


def _compiler_context_snapshot(task: TaskRecord) -> dict[str, Any] | None:
    encoded_metadata = getattr(task, "metadata", None)
    if encoded_metadata in (None, ""):
        encoded_metadata = getattr(task, "acceptance_criteria", None)
    payload = _compact_metadata(decode_kernel_task_metadata(encoded_metadata))
    if not payload:
        return None

    kernel_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else None
    compiler = kernel_payload.get("compiler") if isinstance(kernel_payload, dict) else None
    task_segment = payload.get("task_segment") if isinstance(payload.get("task_segment"), dict) else None
    if isinstance(compiler, dict):
        unit_id = _normalize_optional_str(compiler.get("unit_id") or compiler.get("source_unit_id"))
        if unit_id is not None:
            return {
                "unit_id": unit_id,
                "step_order": _coerce_step_order(
                    compiler.get("step_order"),
                    compiler.get("step_index"),
                    task_segment.get("index") if isinstance(task_segment, dict) else None,
                ),
                "compiled_at_key": _normalize_optional_str(compiler.get("compiled_at")) or "",
                "evidence_refs": _merge_string_lists(
                    compiler.get("evidence_refs"),
                    kernel_payload.get("request_context", {}).get("evidence_refs")
                    if isinstance(kernel_payload.get("request_context"), dict)
                    else None,
                    getattr(task, "evidence_refs", None),
                ),
                "task": task,
            }

    compiler_seed = payload.get("compiler_seed")
    if not isinstance(compiler_seed, dict):
        return None
    unit_id = _normalize_optional_str(compiler_seed.get("unit_id"))
    if unit_id is None:
        return None
    return {
        "unit_id": unit_id,
        "step_order": _coerce_step_order(
            compiler_seed.get("step_order"),
            compiler_seed.get("step_index"),
        ),
        "compiled_at_key": _normalize_optional_str(compiler_seed.get("compiled_at"))
        or "",
        "evidence_refs": _merge_string_lists(
            compiler_seed.get("evidence_refs"),
            task.evidence_refs if hasattr(task, "evidence_refs") else None,
        ),
        "task": task,
    }


def _coerce_step_order(*values: object) -> int:
    for value in values:
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _merge_string_lists(*values: object) -> list[str]:
    merged: list[str] = []
    for value in values:
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple, set)):
            items = list(value)
        elif value is None:
            items = []
        else:
            items = [value]
        for item in items:
            normalized = _normalize_optional_str(item)
            if normalized is None or normalized in merged:
                continue
            merged.append(normalized)
    return merged


__all__ = [
    "_MAIN_BRAIN_ACTOR",
    "LearningRuntimeDelegate",
    "_acquisition_acceptance_criteria",
    "_acquisition_constraints_summary",
    "_compact_metadata",
    "_compiler_context_snapshot",
    "_coerce_step_order",
    "_growth_matches",
    "_is_failure_record",
    "_is_strategy_actionable_failure_record",
    "_list_like",
    "_maybe_await",
    "_mcp_trial_tool_entries",
    "_mcp_trial_tool_name",
    "_mcp_trial_tool_required_args",
    "_merge_string_lists",
    "_normalize_optional_str",
    "_parse_strategy_metadata",
    "_patch_acceptance_criteria",
    "_patch_constraints_summary",
    "_patch_matches",
    "_pick_safe_mcp_trial_tool_name",
    "_resolve_growth_agent_id",
    "_stable_learning_id",
    "_strategy_target_layer",
    "_utc_now",
]
