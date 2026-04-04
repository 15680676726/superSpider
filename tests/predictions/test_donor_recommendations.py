# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.predictions.service_recommendations import rank_donor_recommendation_candidates


def test_rank_donor_recommendation_candidates_prefers_replacement_and_external_first() -> None:
    ranked = rank_donor_recommendation_candidates(
        [
            SimpleNamespace(
                candidate_source_kind="local_authored",
                replacement_relation=None,
                metadata={"confidence_score": 0.9, "source_hit_count": 1},
                title="Local authored fallback",
            ),
            SimpleNamespace(
                candidate_source_kind="external_remote",
                replacement_relation=None,
                metadata={"confidence_score": 0.6, "source_hit_count": 2},
                title="External growth candidate",
            ),
            SimpleNamespace(
                candidate_source_kind="external_remote",
                replacement_relation="replace_requested",
                metadata={"confidence_score": 0.7, "source_hit_count": 2},
                title="External replacement candidate",
            ),
        ]
    )

    assert [item.title for item in ranked] == [
        "External replacement candidate",
        "External growth candidate",
        "Local authored fallback",
    ]

