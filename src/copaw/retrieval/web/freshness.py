# -*- coding: utf-8 -*-
from __future__ import annotations


def score_web_freshness(metadata: dict[str, object] | None = None) -> float:
    return 0.0 if not metadata else float(metadata.get("freshness_score") or 0.0)


__all__ = ["score_web_freshness"]
