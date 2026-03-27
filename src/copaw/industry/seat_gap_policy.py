# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from .identity import EXECUTION_CORE_ROLE_ID
from .models import IndustryRoleBlueprint, IndustryTeamBlueprint

_LONG_TERM_PATTERNS = (
    re.compile(r"(?:以后|今后|长期|长期地).{0,8}(?:负责|跟进|运营|执行)", re.IGNORECASE),
    re.compile(r"(?:新增|增加|补一个|加一个).{0,8}(?:岗位|职位|角色|执行位)", re.IGNORECASE),
    re.compile(r"(?:专门|长期|固定|常驻).{0,8}(?:岗位|执行位|角色|负责人)", re.IGNORECASE),
)
_HIGH_RISK_TERMS = (
    "下单",
    "投放",
    "支付",
    "付款",
    "转账",
    "交易",
    "购买",
    "发给客户",
    "发送给客户",
    "正式发布",
)


@dataclass(slots=True)
class SeatGapResolution:
    kind: Literal[
        "existing-role",
        "temporary-seat-auto",
        "temporary-seat-proposal",
        "career-seat-proposal",
        "routing-pending",
    ]
    target_role_id: str | None = None
    target_agent_id: str | None = None
    role: IndustryRoleBlueprint | None = None
    requires_confirmation: bool = False
    reason: str = ""
    requested_surfaces: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def resolve_chat_writeback_seat_gap(
    *,
    message_text: str,
    requested_surfaces: list[str],
    matched_role: IndustryRoleBlueprint | None,
    team: IndustryTeamBlueprint,
) -> SeatGapResolution:
    normalized_surfaces = _normalize_surfaces(requested_surfaces)
    long_term = _looks_like_long_term_seat_request(message_text)
    high_risk = _looks_like_high_risk_leaf_work(
        message_text,
        requested_surfaces=normalized_surfaces,
    )
    metadata = {
        "requested_surfaces": list(normalized_surfaces),
        "long_term": long_term,
        "high_risk": high_risk,
    }

    if long_term:
        role = _build_gap_role(
            team=team,
            requested_surfaces=normalized_surfaces,
            employment_mode="career",
        )
        return SeatGapResolution(
            kind="career-seat-proposal",
            target_role_id=role.role_id,
            target_agent_id=role.agent_id,
            role=role,
            requires_confirmation=True,
            reason="Long-term seat addition must be governed before the main brain changes the permanent roster.",
            requested_surfaces=list(normalized_surfaces),
            metadata=metadata,
        )

    if matched_role is not None:
        if not _role_covers_requested_surfaces(
            matched_role,
            requested_surfaces=normalized_surfaces,
        ):
            metadata["matched_role_surface_gap"] = {
                "role_id": matched_role.role_id,
                "missing_surfaces": _missing_role_surfaces(
                    matched_role,
                    requested_surfaces=normalized_surfaces,
                ),
            }
        else:
            return SeatGapResolution(
                kind="existing-role",
                target_role_id=matched_role.role_id,
                target_agent_id=matched_role.agent_id,
                role=matched_role,
                requested_surfaces=list(normalized_surfaces),
                reason="Existing specialist match",
                metadata=metadata,
            )

    if not normalized_surfaces:
        return SeatGapResolution(
            kind="routing-pending",
            requested_surfaces=[],
            reason="No concrete execution surface was requested, so the main brain should keep it in planning/backlog review.",
            metadata=metadata,
        )

    if _is_low_risk_local_work(
        message_text,
        requested_surfaces=normalized_surfaces,
    ):
        role = _build_gap_role(
            team=team,
            requested_surfaces=normalized_surfaces,
            employment_mode="temporary",
        )
        return SeatGapResolution(
            kind="temporary-seat-auto",
            target_role_id=role.role_id,
            target_agent_id=role.agent_id,
            role=role,
            requested_surfaces=list(normalized_surfaces),
            reason="Low-risk local work can be auto-covered by a temporary seat.",
            metadata=metadata,
        )

    if high_risk or "browser" in normalized_surfaces:
        role = _build_gap_role(
            team=team,
            requested_surfaces=normalized_surfaces,
            employment_mode="temporary",
        )
        return SeatGapResolution(
            kind="temporary-seat-proposal",
            target_role_id=role.role_id,
            target_agent_id=role.agent_id,
            role=role,
            requires_confirmation=True,
            requested_surfaces=list(normalized_surfaces),
            reason="High-risk or externally acting leaf work requires a governed temporary seat proposal.",
            metadata=metadata,
        )

    return SeatGapResolution(
        kind="routing-pending",
        requested_surfaces=list(normalized_surfaces),
        reason="No safe specialist or governed seat proposal rule matched this request.",
        metadata=metadata,
    )


def _normalize_surfaces(requested_surfaces: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in requested_surfaces:
        value = str(item or "").strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _role_covers_requested_surfaces(
    role: IndustryRoleBlueprint,
    *,
    requested_surfaces: list[str],
) -> bool:
    return not _missing_role_surfaces(role, requested_surfaces=requested_surfaces)


def _missing_role_surfaces(
    role: IndustryRoleBlueprint,
    *,
    requested_surfaces: list[str],
) -> list[str]:
    capability_ids = {
        str(capability or "").strip().lower()
        for capability in list(role.allowed_capabilities or [])
        if str(capability or "").strip()
    }
    missing: list[str] = []
    for surface in requested_surfaces:
        if surface == "browser" and not any(
            "browser" in capability_id or "web" in capability_id
            for capability_id in capability_ids
        ):
            missing.append(surface)
        elif surface == "desktop" and not any(
            "desktop" in capability_id or capability_id.startswith("mcp:desktop")
            for capability_id in capability_ids
        ):
            missing.append(surface)
        elif surface == "file" and not any(
            capability_id in {"tool:read_file", "tool:write_file", "tool:edit_file"}
            for capability_id in capability_ids
        ):
            missing.append(surface)
    return missing


def _looks_like_long_term_seat_request(message_text: str) -> bool:
    text = str(message_text or "").strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _LONG_TERM_PATTERNS)


def _looks_like_high_risk_leaf_work(
    message_text: str,
    *,
    requested_surfaces: list[str],
) -> bool:
    text = str(message_text or "").strip().lower()
    if not text:
        return False
    if any(term in text for term in _HIGH_RISK_TERMS):
        return True
    return "browser" in requested_surfaces and any(
        term in text for term in ("广告", "campaign", "checkout", "publish")
    )


def _is_low_risk_local_work(
    message_text: str,
    *,
    requested_surfaces: list[str],
) -> bool:
    if not requested_surfaces:
        return False
    if not set(requested_surfaces).issubset({"file", "desktop"}):
        return False
    if _looks_like_long_term_seat_request(message_text):
        return False
    if _looks_like_high_risk_leaf_work(
        message_text,
        requested_surfaces=requested_surfaces,
    ):
        return False
    return True


def _build_gap_role(
    *,
    team: IndustryTeamBlueprint,
    requested_surfaces: list[str],
    employment_mode: Literal["career", "temporary"],
) -> IndustryRoleBlueprint:
    surface_key = _surface_key(requested_surfaces)
    if employment_mode == "career":
        role_id = f"{surface_key}-specialist"
        role_name = _career_role_name(requested_surfaces)
        role_summary = (
            "Dedicated specialist seat proposed by the main brain because the request expands the long-term roster boundary."
        )
        mission = (
            "Own this specialist execution lane long term, keep external actions governed, and report structured results back to the main brain."
        )
        activation_mode = "persistent"
        risk_level: Literal["auto", "guarded", "confirm"] = (
            "confirm" if "browser" in requested_surfaces else "guarded"
        )
    else:
        role_id = f"temporary-{surface_key}-worker"
        role_name = _temporary_role_name(requested_surfaces)
        role_summary = (
            "Short-lived specialist seat created to keep leaf execution off the main brain."
        )
        mission = (
            "Handle the assigned local execution step, capture evidence, and hand the result back to the main brain immediately."
        )
        activation_mode = "on-demand"
        risk_level = "guarded"

    normalized_team_id = _slug(team.team_id or "industry")
    agent_id = f"{normalized_team_id}-{role_id}"
    capability_ids = _capability_ids_for_surfaces(requested_surfaces)
    environment_constraints = _environment_constraints_for_surfaces(requested_surfaces)
    evidence_expectations = _evidence_expectations_for_surfaces(requested_surfaces)
    preferred_families = [item for item in requested_surfaces if item in {"browser", "desktop", "file"}]
    actor_key = f"{normalized_team_id}:{role_id}"
    actor_fingerprint = f"seat-gap:{role_id}:{','.join(requested_surfaces) or 'general'}:{employment_mode}"
    return IndustryRoleBlueprint(
        role_id=role_id,
        agent_id=agent_id,
        actor_key=actor_key,
        actor_fingerprint=actor_fingerprint,
        name=role_name,
        role_name=role_name,
        role_summary=role_summary,
        mission=mission,
        goal_kind=role_id,
        agent_class="business",
        employment_mode=employment_mode,
        activation_mode=activation_mode,
        suspendable=employment_mode == "temporary",
        reports_to=EXECUTION_CORE_ROLE_ID,
        risk_level=risk_level,
        environment_constraints=environment_constraints,
        allowed_capabilities=capability_ids,
        preferred_capability_families=preferred_families,
        evidence_expectations=evidence_expectations,
    )


def _surface_key(requested_surfaces: list[str]) -> str:
    if "browser" in requested_surfaces:
        return "browser-ops"
    if "desktop" in requested_surfaces and "file" in requested_surfaces:
        return "local-ops"
    if "desktop" in requested_surfaces:
        return "desktop-ops"
    if "file" in requested_surfaces:
        return "file-ops"
    return "general-ops"


def _temporary_role_name(requested_surfaces: list[str]) -> str:
    if "desktop" in requested_surfaces and "file" in requested_surfaces:
        return "Temporary Local Ops"
    if "desktop" in requested_surfaces:
        return "Temporary Desktop Ops"
    if "browser" in requested_surfaces:
        return "Temporary Browser Ops"
    if "file" in requested_surfaces:
        return "Temporary File Ops"
    return "Temporary Specialist"


def _career_role_name(requested_surfaces: list[str]) -> str:
    if "browser" in requested_surfaces:
        return "Browser Operations Specialist"
    if "desktop" in requested_surfaces:
        return "Desktop Operations Specialist"
    if "file" in requested_surfaces:
        return "File Operations Specialist"
    return "Execution Specialist"


def _capability_ids_for_surfaces(requested_surfaces: list[str]) -> list[str]:
    capability_ids: list[str] = []
    if "browser" in requested_surfaces:
        capability_ids.append("tool:browser_use")
    if "desktop" in requested_surfaces:
        capability_ids.extend(["mcp:desktop_windows", "tool:desktop_screenshot"])
    if "file" in requested_surfaces:
        capability_ids.extend(["tool:read_file", "tool:write_file", "tool:edit_file"])
    return capability_ids


def _environment_constraints_for_surfaces(requested_surfaces: list[str]) -> list[str]:
    constraints: list[str] = []
    if "browser" in requested_surfaces:
        constraints.extend(["browser", "interactive-session"])
    if "desktop" in requested_surfaces:
        constraints.extend(["desktop", "interactive-session"])
    if "file" in requested_surfaces:
        constraints.append("workspace")
    return constraints


def _evidence_expectations_for_surfaces(requested_surfaces: list[str]) -> list[str]:
    expectations = [
        "Return a structured completion summary to the main brain.",
    ]
    if "browser" in requested_surfaces:
        expectations.append("Keep browser evidence or page outcomes attached to the assignment.")
    if "desktop" in requested_surfaces:
        expectations.append("Capture desktop-visible evidence for the completed step when possible.")
    if "file" in requested_surfaces:
        expectations.append("Describe the file changes or updated artifacts in the report back.")
    return expectations


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "industry"
