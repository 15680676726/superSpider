# -*- coding: utf-8 -*-
"""Helpers for Runtime Center overview surface assembly."""
from __future__ import annotations

from .models import RuntimeCenterSurfaceInfo, RuntimeOverviewCard


def compute_surface_status(cards: list[RuntimeOverviewCard]) -> str:
    statuses = {card.status for card in cards}
    if statuses == {"state-service"}:
        return "state-service"

    effective_cards = [
        card
        for card in cards
        if not (
            card.status == "unavailable" and card.key in {"governance", "predictions"}
        )
    ]
    effective_statuses = {card.status for card in effective_cards}
    if effective_statuses == {"state-service"}:
        return "state-service"
    if "state-service" in effective_statuses:
        return "degraded"
    return "unavailable"


def build_runtime_surface(cards: list[RuntimeOverviewCard]) -> RuntimeCenterSurfaceInfo:
    return RuntimeCenterSurfaceInfo(
        status=compute_surface_status(cards),
        source=", ".join(dict.fromkeys(card.source for card in cards)),
    )


__all__ = ["build_runtime_surface", "compute_surface_status"]
