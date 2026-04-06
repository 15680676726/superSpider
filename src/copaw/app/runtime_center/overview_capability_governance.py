# -*- coding: utf-8 -*-
"""Capability governance projection helpers for Runtime Center overview surfaces."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import RuntimeCenterAppStateView


async def build_capability_governance_projection(
    support: object,
    app_state: RuntimeCenterAppStateView,
) -> dict[str, Any]:
    capability_service = app_state.capability_service
    if capability_service is None:
        return {
            "status": "unavailable",
            "degraded": False,
            "degraded_components": [],
            "delta": {},
        }
    mounts = await support._call_list_method(capability_service, "list_capabilities")
    missing_sentinel = getattr(support, "_missing_sentinel", object())
    if mounts is missing_sentinel:
        mounts = []
    summary = support._normalize_capability_summary(
        await support._call_optional_method(capability_service, "summarize"),
        mounts,
    )
    skills = list(
        await support._call_optional_method(
            capability_service,
            "list_skill_specs",
        )
        or []
    )
    mcps = list(
        await support._call_optional_method(
            capability_service,
            "list_mcp_client_infos",
        )
        or []
    )
    prediction_service = app_state.prediction_service
    state_query_service = getattr(app_state, "state_query_service", None)
    optimization_overview = {}
    get_runtime_capability_optimization_overview = getattr(
        prediction_service,
        "get_runtime_capability_optimization_overview",
        None,
    )
    if callable(get_runtime_capability_optimization_overview):
        optimization_overview = support._mapping(
            get_runtime_capability_optimization_overview(),
        ) or {}
    delta = support._mapping(optimization_overview.get("summary")) or {}
    discovery = support._mapping(optimization_overview.get("discovery")) or {}
    portfolio_summary = support._mapping(optimization_overview.get("portfolio")) or {}
    if state_query_service is not None:
        get_capability_portfolio_summary = getattr(
            state_query_service,
            "get_capability_portfolio_summary",
            None,
        )
        if callable(get_capability_portfolio_summary):
            portfolio_summary = {
                **portfolio_summary,
                **(support._mapping(
                    get_capability_portfolio_summary(),
                ) or {}),
            }
    if not portfolio_summary:
        portfolio_summary = {}
    portfolio_service = getattr(app_state, "capability_portfolio_service", None)
    get_runtime_portfolio_summary = getattr(
        portfolio_service,
        "get_runtime_portfolio_summary",
        None,
    )
    if callable(get_runtime_portfolio_summary):
        portfolio_summary = {
            **portfolio_summary,
            **(support._mapping(get_runtime_portfolio_summary()) or {}),
        }
    else:
        summarize_portfolio = getattr(portfolio_service, "summarize_portfolio", None)
        if callable(summarize_portfolio):
            portfolio_summary = {
                **portfolio_summary,
                **(support._mapping(summarize_portfolio()) or {}),
            }
    if not discovery and state_query_service is not None:
        get_capability_discovery_summary = getattr(
            state_query_service,
            "get_capability_discovery_summary",
            None,
        )
        if callable(get_capability_discovery_summary):
            discovery = support._mapping(get_capability_discovery_summary()) or {}
    package_bound_skill_count = sum(
        1
        for item in skills
        if support._string(support._get_field(item, "package_ref"))
    )
    package_bound_mcp_count = sum(
        1
        for item in mcps
        if support._string(support._get_field(item, "package_ref"))
    )
    governance_route = "/api/runtime-center/governance/capability-optimizations"
    degraded_components: list[dict[str, Any]] = []
    missing_capability_count = support._int(delta.get("missing_capability_count"), 0)
    underperforming_capability_count = support._int(
        delta.get("underperforming_capability_count"),
        0,
    )
    degraded_donor_count = support._int(portfolio_summary.get("degraded_donor_count"), 0)
    over_budget_scope_count = support._int(
        portfolio_summary.get("over_budget_scope_count"),
        0,
    )
    waiting_confirm_count = support._int(delta.get("waiting_confirm_count"), 0)
    manual_only_count = support._int(delta.get("manual_only_count"), 0)
    if missing_capability_count > 0:
        degraded_components.append(
            {
                "component": "capability-coverage",
                "status": "degraded",
                "summary": (
                    f"{missing_capability_count} 个 capability gap 仍待补齐或治理决策。"
                ),
                "route": governance_route,
            },
        )
    if underperforming_capability_count > 0:
        degraded_components.append(
            {
                "component": "capability-performance",
                "status": "degraded",
                "summary": (
                    f"{underperforming_capability_count} underperforming capability recommendations need operator review."
                ),
                "route": governance_route,
            },
        )
    if waiting_confirm_count > 0:
        degraded_components.append(
            {
                "component": "capability-approval-backlog",
                "status": "degraded",
                "summary": (
                    f"{waiting_confirm_count} capability actions are waiting for confirmation."
                ),
                "route": governance_route,
            },
        )
    if manual_only_count > 0:
        degraded_components.append(
            {
                "component": "capability-manual-operations",
                "status": "degraded",
                "summary": (
                    f"{manual_only_count} capability actions are still manual-only."
                ),
                "route": governance_route,
            },
        )
    if degraded_donor_count > 0:
        degraded_components.append(
            {
                "component": "donor-trust",
                "status": "degraded",
                "summary": (
                    f"{degraded_donor_count} active donor profiles are degraded or carry replacement pressure."
                ),
                "route": governance_route,
            },
        )
    replace_pressure_count = support._int(
        portfolio_summary.get("replace_pressure_count"),
        0,
    )
    retire_pressure_count = support._int(
        portfolio_summary.get("retire_pressure_count"),
        0,
    )
    revision_pressure_count = support._int(
        portfolio_summary.get("revision_pressure_count"),
        0,
    )
    if replace_pressure_count > 0:
        degraded_components.append(
            {
                "component": "replacement-pressure",
                "status": "degraded",
                "summary": (
                    f"{replace_pressure_count} active donor profiles are carrying formal replacement pressure."
                ),
                "route": governance_route,
            },
        )
    if retire_pressure_count > 0:
        degraded_components.append(
            {
                "component": "retirement-pressure",
                "status": "degraded",
                "summary": (
                    f"{retire_pressure_count} active donor profiles are carrying formal retirement pressure."
                ),
                "route": governance_route,
            },
        )
    if over_budget_scope_count > 0:
        degraded_components.append(
            {
                "component": "portfolio-density",
                "status": "degraded",
                "summary": (
                    f"{over_budget_scope_count} scopes exceeded the governed donor density budget."
                ),
                "route": governance_route,
            },
        )
    governance_actions = list(
        portfolio_summary.get("governance_actions")
        if isinstance(portfolio_summary.get("governance_actions"), list)
        else []
    )
    return {
        "status": "degraded" if degraded_components else "ready",
        "route": governance_route,
        "total": support._int(summary.get("total"), len(mounts)),
        "enabled": support._int(summary.get("enabled"), support._enabled_count(mounts)),
        "by_kind": support._normalize_int_map(summary.get("by_kind")),
        "by_source": support._normalize_int_map(summary.get("by_source")),
        "skill_count": len(skills),
        "enabled_skill_count": sum(
            1 for item in skills if bool(support._get_field(item, "enabled"))
        ),
        "package_bound_skill_count": package_bound_skill_count,
        "mcp_count": len(mcps),
        "enabled_mcp_count": sum(
            1 for item in mcps if bool(support._get_field(item, "enabled"))
        ),
        "package_bound_mcp_count": package_bound_mcp_count,
        "delta": {
            "total_items": support._int(delta.get("total_items"), 0),
            "history_count": support._int(delta.get("history_count"), 0),
            "case_count": support._int(delta.get("case_count"), 0),
            "missing_capability_count": missing_capability_count,
            "underperforming_capability_count": underperforming_capability_count,
            "trial_count": support._int(delta.get("trial_count"), 0),
            "rollout_count": support._int(delta.get("rollout_count"), 0),
            "retire_count": support._int(delta.get("retire_count"), 0),
            "waiting_confirm_count": waiting_confirm_count,
            "manual_only_count": manual_only_count,
            "executed_count": support._int(delta.get("executed_count"), 0),
            "actionable_count": support._int(delta.get("actionable_count"), 0),
        },
        "portfolio": {
            "donor_count": support._int(portfolio_summary.get("donor_count"), 0),
            "active_donor_count": support._int(
                portfolio_summary.get("active_donor_count"),
                0,
            ),
            "candidate_donor_count": support._int(
                portfolio_summary.get("candidate_donor_count"),
                0,
            ),
            "trial_donor_count": support._int(
                portfolio_summary.get("trial_donor_count"),
                0,
            ),
            "trusted_source_count": support._int(
                portfolio_summary.get("trusted_source_count"),
                0,
            ),
            "watchlist_source_count": support._int(
                portfolio_summary.get("watchlist_source_count"),
                0,
            ),
            "degraded_donor_count": degraded_donor_count,
            "replace_pressure_count": replace_pressure_count,
            "retire_pressure_count": retire_pressure_count,
            "revision_pressure_count": revision_pressure_count,
            "over_budget_scope_count": over_budget_scope_count,
            "planning_actions": list(
                portfolio_summary.get("planning_actions")
                if isinstance(portfolio_summary.get("planning_actions"), list)
                else []
            ),
            "governance_actions": governance_actions,
        },
        "discovery": {
            "status": support._string(discovery.get("status")) or "unknown",
            "summary": support._string(discovery.get("summary")),
            "source_profile_count": support._int(
                discovery.get("source_profile_count"),
                0,
            ),
            "active_source_count": support._int(
                discovery.get("active_source_count"),
                0,
            ),
            "trusted_source_count": support._int(
                discovery.get("trusted_source_count"),
                0,
            ),
            "watchlist_source_count": support._int(
                discovery.get("watchlist_source_count"),
                0,
            ),
            "fallback_only_source_count": support._int(
                discovery.get("fallback_only_source_count"),
                0,
            ),
            "by_source_kind": support._normalize_int_map(
                discovery.get("by_source_kind"),
            ),
            "routes": dict(discovery.get("routes") or {})
            if isinstance(discovery.get("routes"), Mapping)
            else {},
        },
        "degraded": bool(degraded_components),
        "degraded_components": degraded_components,
    }
