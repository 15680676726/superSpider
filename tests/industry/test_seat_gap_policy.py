# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.industry.identity import EXECUTION_CORE_ROLE_ID
from copaw.industry.models import IndustryRoleBlueprint, IndustryTeamBlueprint
from copaw.industry.seat_gap_policy import resolve_chat_writeback_seat_gap


def _role(
    *,
    role_id: str,
    agent_id: str,
    role_name: str,
    role_summary: str,
    mission: str,
    goal_kind: str,
    allowed_capabilities: list[str] | None = None,
    employment_mode: str = "career",
    activation_mode: str = "persistent",
) -> IndustryRoleBlueprint:
    return IndustryRoleBlueprint(
        role_id=role_id,
        agent_id=agent_id,
        name=role_name,
        role_name=role_name,
        role_summary=role_summary,
        mission=mission,
        goal_kind=goal_kind,
        employment_mode=employment_mode,
        activation_mode=activation_mode,
        reports_to=EXECUTION_CORE_ROLE_ID,
        risk_level="guarded",
        allowed_capabilities=list(allowed_capabilities or []),
        environment_constraints=[],
        evidence_expectations=["report completion back to the main brain"],
    )


def _team(*roles: IndustryRoleBlueprint) -> IndustryTeamBlueprint:
    return IndustryTeamBlueprint(
        team_id="industry-v1-demo",
        label="Demo Team",
        summary="Demo industry team",
        agents=list(roles),
    )


def test_resolve_gap_prefers_existing_specialist_when_role_covers_requested_surfaces() -> None:
    existing_role = _role(
        role_id="solution-lead",
        agent_id="solution-lead-agent",
        role_name="Local Ops Specialist",
        role_summary="Handles local desktop and file operations.",
        mission="Own low-risk local execution work and report back.",
        goal_kind="solution-lead",
        allowed_capabilities=[
            "mcp:desktop_windows",
            "tool:desktop_screenshot",
            "tool:read_file",
            "tool:write_file",
            "tool:edit_file",
        ],
    )

    resolution = resolve_chat_writeback_seat_gap(
        message_text="整理桌面上的 text 文件并归档到工作目录",
        requested_surfaces=["file", "desktop"],
        matched_role=existing_role,
        team=_team(existing_role),
    )

    assert resolution.kind == "existing-role"
    assert resolution.target_role_id == existing_role.role_id
    assert resolution.role == existing_role


def test_resolve_gap_creates_temporary_seat_when_partial_match_misses_surface() -> None:
    file_only_role = _role(
        role_id="solution-lead",
        agent_id="solution-lead-agent",
        role_name="Solution Lead",
        role_summary="Handles local file operations and structured delivery work.",
        mission="Own low-risk local execution work and report back.",
        goal_kind="solution-lead",
        allowed_capabilities=["tool:read_file", "tool:write_file", "tool:edit_file"],
    )

    resolution = resolve_chat_writeback_seat_gap(
        message_text="整理桌面上的 text 文件并归档到工作目录",
        requested_surfaces=["file", "desktop"],
        matched_role=file_only_role,
        team=_team(file_only_role),
    )

    assert resolution.kind == "temporary-seat-auto"
    assert resolution.role is not None
    assert resolution.role.role_id == "temporary-local-ops-worker"


def test_resolve_gap_builds_auto_temporary_seat_for_low_risk_local_work() -> None:
    resolution = resolve_chat_writeback_seat_gap(
        message_text="整理桌面下载区并把文件分类到项目目录",
        requested_surfaces=["file", "desktop"],
        matched_role=None,
        team=_team(),
    )

    assert resolution.kind == "temporary-seat-auto"
    assert resolution.role is not None
    assert resolution.role.employment_mode == "temporary"
    assert resolution.role.activation_mode == "on-demand"
    assert resolution.role.reports_to == EXECUTION_CORE_ROLE_ID
    assert "tool:write_file" in resolution.role.allowed_capabilities


def test_resolve_gap_normalizes_requested_surfaces_for_local_seat_requests() -> None:
    resolution = resolve_chat_writeback_seat_gap(
        message_text="Organize the desktop files into the project folder.",
        requested_surfaces=["FILE", "desktop", "file", " desktop "],
        matched_role=None,
        team=_team(),
    )

    assert resolution.kind == "temporary-seat-auto"
    assert resolution.requested_surfaces == ["file", "desktop"]
    assert resolution.metadata["requested_surfaces"] == ["file", "desktop"]
    assert resolution.role is not None
    assert resolution.role.employment_mode == "temporary"


def test_resolve_gap_requires_governance_for_long_term_browser_seat() -> None:
    resolution = resolve_chat_writeback_seat_gap(
        message_text="以后长期负责平台投放并直接下单执行",
        requested_surfaces=["browser"],
        matched_role=None,
        team=_team(),
    )

    assert resolution.kind == "career-seat-proposal"
    assert resolution.requires_confirmation is True
    assert resolution.role is not None
    assert resolution.role.employment_mode == "career"
    assert resolution.target_role_id == resolution.role.role_id


def test_resolve_gap_requires_governed_temporary_seat_for_browser_leaf_work() -> None:
    resolution = resolve_chat_writeback_seat_gap(
        message_text="Please publish the customer notice in the browser and send the receipt.",
        requested_surfaces=["browser"],
        matched_role=None,
        team=_team(),
    )

    assert resolution.kind == "temporary-seat-proposal"
    assert resolution.requires_confirmation is True
    assert resolution.requested_surfaces == ["browser"]
    assert resolution.metadata["requested_surfaces"] == ["browser"]
    assert resolution.role is not None
    assert resolution.role.employment_mode == "temporary"
    assert resolution.role.activation_mode == "on-demand"
    assert resolution.role.risk_level == "guarded"
