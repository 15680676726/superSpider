# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.predictions.service_recommendations import (
    _PredictionServiceRecommendationMixin,
    rank_donor_recommendation_candidates,
)


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


class _RecordingLifecycleDecisionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list_decisions(self, *, candidate_id: str | None = None, limit: int | None = None):
        _ = (candidate_id, limit)
        return []

    def create_decision(self, **kwargs):
        self.calls.append(dict(kwargs))


class _RecommendationHarness(_PredictionServiceRecommendationMixin):
    def __init__(self) -> None:
        self._skill_lifecycle_decision_service = _RecordingLifecycleDecisionService()


def test_lifecycle_decision_proposal_carries_adapter_attribution_metadata() -> None:
    service = _RecommendationHarness()

    service._register_lifecycle_decision_proposal(
        metadata={
            "candidate_id": "cand-1",
            "gap_kind": "capability_rollout",
            "source_recommendation_id": "rec-1",
            "trial_scope": "single-seat",
            "selected_seat_ref": "seat-primary",
            "protocol_surface_kind": "native_mcp",
            "transport_kind": "mcp",
            "compiled_adapter_id": "adapter:demo",
            "compiled_action_ids": ["execute_task"],
            "adapter_blockers": [],
        },
    )

    [created] = service._skill_lifecycle_decision_service.calls
    assert created["candidate_id"] == "cand-1"
    assert created["metadata"]["protocol_surface_kind"] == "native_mcp"
    assert created["metadata"]["transport_kind"] == "mcp"
    assert created["metadata"]["compiled_adapter_id"] == "adapter:demo"
    assert created["metadata"]["compiled_action_ids"] == ["execute_task"]
