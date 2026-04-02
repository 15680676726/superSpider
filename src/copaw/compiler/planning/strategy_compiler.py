# -*- coding: utf-8 -*-
"""Compile persisted strategy memory into formal planning constraints."""
from __future__ import annotations

from ...state import StrategyMemoryRecord
from .models import PlanningStrategyConstraints


class StrategyPlanningCompiler:
    """Pure compiler layer from strategy truth to planning constraints."""

    def compile(
        self,
        strategy: StrategyMemoryRecord | None,
    ) -> PlanningStrategyConstraints:
        if strategy is None:
            return PlanningStrategyConstraints()
        return PlanningStrategyConstraints(
            mission=strategy.mission,
            north_star=strategy.north_star,
            priority_order=list(strategy.priority_order or []),
            lane_weights={
                str(lane_id): float(weight)
                for lane_id, weight in dict(strategy.lane_weights or {}).items()
                if str(lane_id).strip()
            },
            planning_policy=list(strategy.planning_policy or []),
            review_rules=list(strategy.review_rules or []),
            paused_lane_ids=list(strategy.paused_lane_ids or []),
            current_focuses=list(strategy.current_focuses or []),
        )
