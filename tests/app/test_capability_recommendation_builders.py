# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.capabilities.recommendation_builders import (
    build_remote_skill_recommendation,
)


def test_build_remote_skill_recommendation_preserves_shared_contract() -> None:
    recommendation = build_remote_skill_recommendation(
        recommendation_id="hub-skill:test-skill",
        install_kind="hub-skill",
        template_id="test-skill",
        title="Test Skill",
        description="Do a thing.",
        default_client_key="test_skill",
        capability_ids=["skill:test_skill"],
        capability_tags=["skill", "hub"],
        capability_families=["workflow"],
        suggested_role_ids=["ops-lead"],
        target_agent_ids=["agent-1"],
        installed=False,
        source_kind="hub-search",
        source_label="SkillHub",
        source_url="https://example.com/test-skill",
        version="1.2.3",
        review_required=False,
        review_summary="",
        review_notes=[],
        notes=["Install before assignment."],
        discovery_queries=["workflow automation"],
        match_signals=["goal-match"],
        governance_path=["system:discover_capabilities", "system:install_hub_skill"],
        routes={"market_skills": "/api/capability-market/skills"},
    )

    assert recommendation.recommendation_id == "hub-skill:test-skill"
    assert recommendation.install_kind == "hub-skill"
    assert recommendation.default_client_key == "test_skill"
    assert recommendation.capability_ids == ["skill:test_skill"]
    assert recommendation.source_label == "SkillHub"
    assert recommendation.discovery_queries == ["workflow automation"]
    assert recommendation.match_signals == ["goal-match"]
    assert recommendation.governance_path[-1] == "system:install_hub_skill"
