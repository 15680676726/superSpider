# -*- coding: utf-8 -*-
from __future__ import annotations

from ..industry.models import IndustryCapabilityRecommendation


def build_remote_skill_recommendation(
    *,
    recommendation_id: str,
    install_kind: str,
    template_id: str,
    title: str,
    description: str,
    default_client_key: str,
    capability_ids: list[str],
    capability_tags: list[str],
    capability_families: list[str],
    suggested_role_ids: list[str],
    target_agent_ids: list[str],
    installed: bool,
    source_kind: str,
    source_label: str,
    source_url: str,
    version: str,
    review_required: bool,
    review_summary: str,
    review_notes: list[str],
    notes: list[str],
    discovery_queries: list[str],
    match_signals: list[str],
    governance_path: list[str],
    routes: dict[str, str],
) -> IndustryCapabilityRecommendation:
    return IndustryCapabilityRecommendation(
        recommendation_id=recommendation_id,
        install_kind=install_kind,
        template_id=template_id,
        title=title,
        description=description,
        default_client_key=default_client_key,
        capability_ids=capability_ids,
        capability_tags=capability_tags,
        capability_families=capability_families,
        suggested_role_ids=suggested_role_ids,
        target_agent_ids=target_agent_ids,
        default_enabled=True,
        installed=installed,
        selected=not installed,
        required=False,
        risk_level="guarded",
        capability_budget_cost=1,
        source_kind=source_kind,
        source_label=source_label,
        source_url=source_url,
        version=version,
        review_required=review_required,
        review_summary=review_summary,
        review_notes=review_notes,
        notes=notes,
        discovery_queries=discovery_queries,
        match_signals=match_signals,
        governance_path=governance_path,
        routes=routes,
    )


__all__ = ["build_remote_skill_recommendation"]
