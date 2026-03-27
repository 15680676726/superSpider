# -*- coding: utf-8 -*-
"""Resolve teammate identifiers using industry roster + live agent profiles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TeammateResolution:
    agent_id: str | None
    role_id: str | None = None
    role_name: str | None = None
    name: str | None = None
    error_code: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.agent_id is not None and self.error_code is None


def resolve_teammate_target(
    *,
    candidate_agent_id: str | None,
    target_role_id: str | None,
    target_role_name: str | None,
    industry_instance_id: str | None,
    industry_service: object | None,
    agent_profile_service: object | None,
) -> TeammateResolution:
    roster = _collect_team_roster(
        industry_instance_id=industry_instance_id,
        industry_service=industry_service,
        agent_profile_service=agent_profile_service,
    )
    has_roster = bool(roster)
    requires_roster = industry_instance_id is not None

    if requires_roster and not has_roster and any(
        (candidate_agent_id, target_role_id, target_role_name),
    ):
        return TeammateResolution(
            agent_id=None,
            error_code="target_not_found",
            error="Team roster is unavailable for teammate resolution.",
        )

    def _match(field: str, value: str) -> list[dict[str, str | None]]:
        normalized = _normalize(value)
        if not normalized:
            return []
        return [
            entry
            for entry in roster
            if _normalize(entry.get(field)) == normalized
        ]

    def _resolve_match(field: str, value: str) -> TeammateResolution | None:
        matches = _match(field, value)
        if len(matches) == 1:
            entry = matches[0]
            return TeammateResolution(
                agent_id=_string(entry.get("agent_id")),
                role_id=_string(entry.get("role_id")),
                role_name=_string(entry.get("role_name")),
                name=_string(entry.get("name")),
            )
        if len(matches) > 1:
            options = ", ".join(
                _string(entry.get("agent_id")) or "unknown"
                for entry in matches[:6]
            )
            return TeammateResolution(
                agent_id=None,
                error_code="target_ambiguous",
                error=(
                    f"Target '{value}' matches multiple teammates ({options}). "
                    "Specify agent_id or role_id."
                ),
            )
        return None

    if candidate_agent_id:
        match = _resolve_match("agent_id", candidate_agent_id)
        if match is not None:
            return match
        if has_roster:
            match = _resolve_match("role_id", candidate_agent_id)
            if match is not None:
                return match
            match = _resolve_match("role_name", candidate_agent_id)
            if match is not None:
                return match

    if target_role_id:
        match = _resolve_match("role_id", target_role_id)
        if match is not None:
            return match

    if target_role_name:
        match = _resolve_match("role_name", target_role_name)
        if match is not None:
            return match

    if not has_roster and candidate_agent_id:
        return TeammateResolution(agent_id=candidate_agent_id)

    if not has_roster and (target_role_id or target_role_name):
        return TeammateResolution(
            agent_id=None,
            error_code="target_not_found",
            error="Team roster is unavailable for role-based resolution.",
        )

    if any((candidate_agent_id, target_role_id, target_role_name)):
        return TeammateResolution(
            agent_id=None,
            error_code="target_not_found",
            error="Target teammate was not found in the current team roster.",
        )

    return TeammateResolution(agent_id=None)


def _collect_team_roster(
    *,
    industry_instance_id: str | None,
    industry_service: object | None,
    agent_profile_service: object | None,
) -> list[dict[str, str | None]]:
    if not industry_instance_id:
        return []
    entries_by_id: dict[str, dict[str, str | None]] = {}

    def _upsert(agent_id: str | None, role_id: str | None, role_name: str | None, name: str | None) -> None:
        normalized = _string(agent_id)
        if not normalized:
            return
        entry = entries_by_id.setdefault(
            normalized,
            {"agent_id": normalized, "role_id": None, "role_name": None, "name": None},
        )
        if role_id and not entry.get("role_id"):
            entry["role_id"] = role_id
        if role_name and not entry.get("role_name"):
            entry["role_name"] = role_name
        if name and not entry.get("name"):
            entry["name"] = name

    detail = _load_industry_detail(industry_service, industry_instance_id)
    if detail is not None:
        team = _field_value(detail, "team")
        team_agents = _field_value(team, "agents")
        if isinstance(team_agents, list):
            for role in team_agents:
                _upsert(
                    _string(_field_value(role, "agent_id", "id")),
                    _string(_field_value(role, "role_id", "industry_role_id")),
                    _string(_field_value(role, "role_name")),
                    _string(_field_value(role, "name")),
                )
        runtime_agents = _field_value(detail, "agents")
        if isinstance(runtime_agents, list):
            for agent in runtime_agents:
                _upsert(
                    _string(_field_value(agent, "agent_id", "id")),
                    _string(_field_value(agent, "industry_role_id", "role_id")),
                    _string(_field_value(agent, "role_name")),
                    _string(_field_value(agent, "name")),
                )

    profiles = _list_agent_profiles(agent_profile_service)
    for profile in profiles:
        if _string(_field_value(profile, "industry_instance_id")) != industry_instance_id:
            continue
        _upsert(
            _string(_field_value(profile, "agent_id")),
            _string(_field_value(profile, "industry_role_id")),
            _string(_field_value(profile, "role_name")),
            _string(_field_value(profile, "name")),
        )

    return list(entries_by_id.values())


def _load_industry_detail(industry_service: object | None, instance_id: str) -> Any | None:
    if industry_service is None:
        return None
    for method_name in ("get_instance_detail", "get_instance_record"):
        getter = getattr(industry_service, method_name, None)
        if callable(getter):
            try:
                detail = getter(instance_id)
            except Exception:
                return None
            if detail is not None:
                return detail
    return None


def _list_agent_profiles(agent_profile_service: object | None) -> list[Any]:
    if agent_profile_service is None:
        return []
    lister = getattr(agent_profile_service, "list_agents", None)
    if not callable(lister):
        return []
    try:
        return list(lister())
    except Exception:
        return []


def _field_value(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value.get(name)
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _normalize(value: Any) -> str | None:
    text = _string(value)
    return text.lower() if text else None


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["TeammateResolution", "resolve_teammate_target"]
