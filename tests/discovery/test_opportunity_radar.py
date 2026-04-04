# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from copaw.discovery.models import OpportunityRadarItem
from copaw.discovery.opportunity_radar import OpportunityRadarService


def test_opportunity_radar_collects_bounded_allowlisted_items() -> None:
    service = OpportunityRadarService(
        feeds={
            "weekly": lambda: [
                OpportunityRadarItem(
                    item_id="item-1",
                    title="Browser Pilot",
                    summary="Weekly trending browser donor.",
                    canonical_package_id="pkg:browser-pilot",
                    source_ref="https://github.com/acme/browser-pilot",
                    ecosystem="github",
                    score=0.82,
                    published_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
                    capability_keys=("browser", "automation"),
                ),
                OpportunityRadarItem(
                    item_id="item-dup",
                    title="Browser Pilot Mirror",
                    summary="Mirror duplicate.",
                    canonical_package_id="pkg:browser-pilot",
                    source_ref="https://mirror.example/browser-pilot",
                    ecosystem="mirror",
                    score=0.75,
                    published_at=datetime(2026, 4, 3, tzinfo=timezone.utc),
                    capability_keys=("browser", "automation"),
                ),
            ],
            "releases": lambda: [
                OpportunityRadarItem(
                    item_id="item-2",
                    title="Research Relay",
                    summary="Fresh research donor release.",
                    canonical_package_id="pkg:research-relay",
                    source_ref="https://github.com/acme/research-relay",
                    ecosystem="github",
                    score=0.78,
                    published_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
                    capability_keys=("research", "search"),
                ),
            ],
        }
    )

    items = service.collect(
        limit=2,
        ecosystem_allowlist=["github"],
    )

    assert [item.canonical_package_id for item in items] == [
        "pkg:browser-pilot",
        "pkg:research-relay",
    ]
    assert items[0].score >= items[1].score
    assert all(item.ecosystem == "github" for item in items)

