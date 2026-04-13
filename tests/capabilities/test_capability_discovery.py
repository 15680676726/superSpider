import asyncio
import time

import pytest

from copaw.capabilities.capability_discovery import CapabilityDiscoveryService
from copaw.capabilities.remote_skill_catalog import (
    CuratedSkillCatalogEntry,
    CuratedSkillCatalogSearchResponse,
)
from copaw.industry.models import IndustryProfile, IndustryRoleBlueprint


def test_search_hub_skills_cached_times_out_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CapabilityDiscoveryService()

    def _slow_search(_query: str, _limit: int = 6):
        time.sleep(0.2)
        return []

    monkeypatch.setattr(
        "copaw.capabilities.capability_discovery.search_hub_skills",
        _slow_search,
    )
    monkeypatch.setattr(
        "copaw.capabilities.capability_discovery._hub_search_timeout_seconds",
        lambda: 0.01,
    )

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(
            service._search_hub_skills_cached(
                query="stock research automation",
                limit=6,
            ),
        )
    assert service._hub_search_cache == {}


def test_build_curated_skill_recommendations_times_out_with_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CapabilityDiscoveryService()

    def _slow_search(_query: str, limit: int = 8):
        time.sleep(0.2)
        return CuratedSkillCatalogSearchResponse(
            sources=[],
            items=[
                CuratedSkillCatalogEntry(
                    candidate_id="slow-curated",
                    source_id="skillhub-search:slow",
                    source_label="SkillHub Curated",
                    source_kind="skillhub-curated",
                    source_repo_url="https://example.com/catalog.json",
                    discovery_kind="skillhub-search",
                    manifest_status="skillhub-curated",
                    title="Slow Curated Skill",
                    description="slow",
                    bundle_url="https://example.com/slow.zip",
                    version="1.0.0",
                    install_name="slow_curated_skill",
                    capability_tags=["skill"],
                    review_required=False,
                    review_summary="",
                    review_notes=[],
                    routes={},
                )
            ],
            total=1,
            warnings=[],
        )

    monkeypatch.setattr(
        "copaw.capabilities.capability_discovery.search_curated_skill_catalog",
        _slow_search,
    )
    monkeypatch.setattr(
        "copaw.capabilities.capability_discovery._curated_search_timeout_seconds",
        lambda: 0.01,
    )

    profile = IndustryProfile(
        industry="Trading",
        company_name="Northwind",
        product="Stock workflow",
        goals=["Build a stock research workflow"],
    )
    role = IndustryRoleBlueprint(
        role_id="researcher",
        agent_id="agent-researcher",
        name="Researcher",
        role_name="Researcher",
        role_summary="Builds stock research workflows.",
        mission="Research and organize stock templates.",
        goal_kind="research",
        risk_level="guarded",
        allowed_capabilities=["tool:write_file"],
        environment_constraints=[],
        evidence_expectations=["report back"],
    )

    items, warnings = asyncio.run(
        service.build_curated_skill_recommendations(
            profile=profile,
            target_roles=[role],
            goal_context_by_agent={"agent-researcher": ["stock research template"]},
        ),
    )

    assert items == []
    assert warnings == [
        "Curated discovery is temporarily unavailable; continuing without that source.",
    ]
