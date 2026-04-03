# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..state import (
    AgentProfileOverrideRecord,
    CapabilityOverrideRecord,
    GoalOverrideRecord,
)
from ..state.repositories import (
    SqliteAgentProfileOverrideRepository,
    SqliteCapabilityOverrideRepository,
    SqliteGoalOverrideRepository,
)
from .models import Patch


class PatchExecutor:
    """Apply and rollback patches with real side-effects."""

    def __init__(
        self,
        *,
        capability_override_repository: SqliteCapabilityOverrideRepository | None = None,
        agent_profile_override_repository: SqliteAgentProfileOverrideRepository | None = None,
        goal_override_repository: SqliteGoalOverrideRepository | None = None,
        override_repository: SqliteCapabilityOverrideRepository | None = None,
    ) -> None:
        self._capability_override_repo = (
            capability_override_repository or override_repository
        )
        self._agent_profile_override_repo = agent_profile_override_repository
        self._goal_override_repo = goal_override_repository

    def apply(self, patch: Patch, *, actor: str) -> dict[str, object]:
        if patch.kind == "capability_patch":
            return self._apply_capability_patch(patch, actor=actor)
        if patch.kind in {"profile_patch", "role_patch"}:
            return self._apply_agent_profile_patch(patch, actor=actor)
        if patch.kind == "plan_patch":
            return self._apply_goal_patch(patch, actor=actor)
        return {
            "success": False,
            "summary": f"Unsupported patch kind '{patch.kind}'.",
            "error": f"Unsupported patch kind '{patch.kind}'",
        }

    def rollback(self, patch: Patch, *, actor: str) -> dict[str, object]:
        if patch.kind == "capability_patch":
            return self._rollback_capability_patch(patch, actor=actor)
        if patch.kind in {"profile_patch", "role_patch"}:
            return self._rollback_agent_profile_patch(patch, actor=actor)
        if patch.kind == "plan_patch":
            return self._rollback_goal_patch(patch, actor=actor)
        return {
            "success": False,
            "summary": f"Unsupported patch kind '{patch.kind}'.",
            "error": f"Unsupported patch kind '{patch.kind}'",
        }

    def _apply_capability_patch(
        self,
        patch: Patch,
        *,
        actor: str,
    ) -> dict[str, object]:
        if self._capability_override_repo is None:
            return {
                "success": False,
                "summary": "Capability override repository is missing.",
                "error": "Capability override repository is missing.",
            }
        metadata = _parse_diff_summary(patch.diff_summary)
        capability_id = _first_non_empty(
            metadata,
            "target_capability",
            "capability_id",
            "capability",
        )
        if not capability_id:
            return _missing_target("capability_id", "capability_patch")

        enabled_flag = _parse_enabled_flag(metadata)
        forced_risk_level = _normalize_risk_level(
            metadata.get("risk_level") or metadata.get("forced_risk_level"),
        )
        if enabled_flag is None and forced_risk_level is None:
            forced_risk_level = "confirm"

        override = CapabilityOverrideRecord(
            capability_id=capability_id,
            enabled=enabled_flag,
            forced_risk_level=forced_risk_level,
            reason=patch.description or patch.title,
            source_patch_id=patch.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._capability_override_repo.upsert_override(override)
        summary = f"Capability override applied for {capability_id}."
        if enabled_flag is False:
            summary = f"Capability '{capability_id}' disabled via patch."
        elif enabled_flag is True:
            summary = f"Capability '{capability_id}' enabled via patch."
        elif forced_risk_level:
            summary = (
                f"Capability '{capability_id}' risk level forced to "
                f"{forced_risk_level}."
            )
        return {
            "success": True,
            "summary": summary,
            "capability_id": capability_id,
            "override": override.model_dump(mode="json"),
            "actor": actor,
        }

    def _rollback_capability_patch(
        self,
        patch: Patch,
        *,
        actor: str,
    ) -> dict[str, object]:
        if self._capability_override_repo is None:
            return {
                "success": False,
                "summary": "Capability override repository is missing.",
                "error": "Capability override repository is missing.",
            }
        metadata = _parse_diff_summary(patch.diff_summary)
        capability_id = _first_non_empty(
            metadata,
            "target_capability",
            "capability_id",
            "capability",
        )
        if not capability_id:
            return _missing_target("capability_id", "capability_patch")
        existing = self._capability_override_repo.get_override(capability_id)
        if existing is None:
            return {
                "success": True,
                "summary": f"No override found for {capability_id}; nothing to rollback.",
                "capability_id": capability_id,
                "actor": actor,
            }
        if existing.source_patch_id and existing.source_patch_id != patch.id:
            return _foreign_override(capability_id, existing.source_patch_id)
        self._capability_override_repo.delete_override(capability_id)
        return {
            "success": True,
            "summary": f"Capability override removed for {capability_id}.",
            "capability_id": capability_id,
            "actor": actor,
        }

    def _apply_agent_profile_patch(
        self,
        patch: Patch,
        *,
        actor: str,
    ) -> dict[str, object]:
        if self._agent_profile_override_repo is None:
            return {
                "success": False,
                "summary": "Agent profile override repository is missing.",
                "error": "Agent profile override repository is missing.",
            }
        metadata = _parse_diff_summary(patch.diff_summary)
        agent_id = _first_non_empty(
            metadata,
            "target_agent",
            "agent_id",
            "agent",
            "owner_agent_id",
        )
        if not agent_id:
            return _missing_target("agent_id", patch.kind)

        override = AgentProfileOverrideRecord(
            agent_id=agent_id,
            name=metadata.get("name"),
            role_name=metadata.get("role_name"),
            role_summary=metadata.get("role_summary") or metadata.get("summary"),
            status=metadata.get("status"),
            risk_level=_normalize_risk_level(metadata.get("risk_level")),
            current_focus_kind=metadata.get("current_focus_kind"),
            current_focus_id=metadata.get("current_focus_id"),
            current_focus=metadata.get("current_focus"),
            current_task_id=metadata.get("current_task_id"),
            environment_summary=metadata.get("environment_summary"),
            today_output_summary=metadata.get("today_output_summary"),
            latest_evidence_summary=metadata.get("latest_evidence_summary"),
            capabilities=_parse_string_list(
                metadata.get("capabilities") or metadata.get("capability_ids"),
            ),
            reason=patch.description or patch.title,
            source_patch_id=patch.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        if patch.kind == "role_patch" and override.role_name is None:
            override = override.model_copy(update={"role_name": patch.title})
        self._agent_profile_override_repo.upsert_override(override)
        return {
            "success": True,
            "summary": f"Agent profile override applied for {agent_id}.",
            "target_agent_id": agent_id,
            "override": override.model_dump(mode="json"),
            "actor": actor,
        }

    def _rollback_agent_profile_patch(
        self,
        patch: Patch,
        *,
        actor: str,
    ) -> dict[str, object]:
        if self._agent_profile_override_repo is None:
            return {
                "success": False,
                "summary": "Agent profile override repository is missing.",
                "error": "Agent profile override repository is missing.",
            }
        metadata = _parse_diff_summary(patch.diff_summary)
        agent_id = _first_non_empty(
            metadata,
            "target_agent",
            "agent_id",
            "agent",
            "owner_agent_id",
        )
        if not agent_id:
            return _missing_target("agent_id", patch.kind)
        existing = self._agent_profile_override_repo.get_override(agent_id)
        if existing is None:
            return {
                "success": True,
                "summary": f"No override found for {agent_id}; nothing to rollback.",
                "target_agent_id": agent_id,
                "actor": actor,
            }
        if existing.source_patch_id and existing.source_patch_id != patch.id:
            return _foreign_override(agent_id, existing.source_patch_id)
        self._agent_profile_override_repo.delete_override(agent_id)
        return {
            "success": True,
            "summary": f"Agent profile override removed for {agent_id}.",
            "target_agent_id": agent_id,
            "actor": actor,
        }

    def _apply_goal_patch(
        self,
        patch: Patch,
        *,
        actor: str,
    ) -> dict[str, object]:
        if self._goal_override_repo is None:
            return {
                "success": False,
                "summary": "Goal override repository is missing.",
                "error": "Goal override repository is missing.",
            }
        metadata = _parse_diff_summary(patch.diff_summary)
        goal_id = _first_non_empty(
            metadata,
            "goal_id",
            "target_goal",
            "goal",
        )
        if not goal_id:
            return _missing_target("goal_id", patch.kind)

        compiler_context = _parse_json_mapping(
            metadata.get("compiler_context") or metadata.get("context"),
        )
        override = GoalOverrideRecord(
            goal_id=goal_id,
            title=metadata.get("title"),
            summary=metadata.get("summary"),
            status=metadata.get("status"),
            priority=_parse_int(metadata.get("priority")),
            owner_scope=metadata.get("owner_scope"),
            plan_steps=_parse_string_list(
                metadata.get("plan_steps") or metadata.get("steps"),
            ),
            compiler_context=compiler_context,
            reason=patch.description or patch.title,
            source_patch_id=patch.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._goal_override_repo.upsert_override(override)
        return {
            "success": True,
            "summary": f"Goal override applied for {goal_id}.",
            "goal_id": goal_id,
            "override": override.model_dump(mode="json"),
            "actor": actor,
        }

    def _rollback_goal_patch(
        self,
        patch: Patch,
        *,
        actor: str,
    ) -> dict[str, object]:
        if self._goal_override_repo is None:
            return {
                "success": False,
                "summary": "Goal override repository is missing.",
                "error": "Goal override repository is missing.",
            }
        metadata = _parse_diff_summary(patch.diff_summary)
        goal_id = _first_non_empty(metadata, "goal_id", "target_goal", "goal")
        if not goal_id:
            return _missing_target("goal_id", patch.kind)
        existing = self._goal_override_repo.get_override(goal_id)
        if existing is None:
            return {
                "success": True,
                "summary": f"No override found for {goal_id}; nothing to rollback.",
                "goal_id": goal_id,
                "actor": actor,
            }
        if existing.source_patch_id and existing.source_patch_id != patch.id:
            return _foreign_override(goal_id, existing.source_patch_id)
        self._goal_override_repo.delete_override(goal_id)
        return {
            "success": True,
            "summary": f"Goal override removed for {goal_id}.",
            "goal_id": goal_id,
            "actor": actor,
        }


def _missing_target(field_name: str, patch_kind: str) -> dict[str, object]:
    return {
        "success": False,
        "error": f"{field_name} is required to apply {patch_kind}",
        "summary": f"Missing {field_name} target for patch",
    }


def _foreign_override(target_id: str, source_patch_id: str) -> dict[str, object]:
    return {
        "success": False,
        "error": f"Override for {target_id} belongs to {source_patch_id}",
        "summary": f"Override for {target_id} owned by another patch.",
    }


def _parse_diff_summary(diff_summary: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for chunk in (diff_summary or "").split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            payload[key] = value
    return payload


def _first_non_empty(metadata: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value:
            return value
    return None


def _normalize_risk_level(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if lowered in {"auto", "guarded", "confirm"}:
        return lowered
    return None


def _parse_enabled_flag(metadata: dict[str, str]) -> bool | None:
    for key in ("enabled", "enable", "disabled", "disable"):
        if key in metadata:
            value = metadata[key].strip().lower()
            if value in {"true", "1", "yes", "enable", "enabled"}:
                return True
            if value in {"false", "0", "no", "disable", "disabled"}:
                return False

    action = metadata.get("action") or metadata.get("mode")
    if action:
        action = action.strip().lower()
        if action in {"enable", "on"}:
            return True
        if action in {"disable", "off"}:
            return False
    return None


def _parse_string_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.startswith("["):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            return [str(item) for item in payload if item is not None]
    separator = "|" if "|" in raw else ","
    items = [item.strip() for item in raw.split(separator) if item.strip()]
    return items or None


def _parse_json_mapping(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


__all__ = ["PatchExecutor"]
