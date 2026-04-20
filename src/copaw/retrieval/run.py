# -*- coding: utf-8 -*-
from __future__ import annotations

from .contracts import RetrievalHit, RetrievalRun


def select_retrieval_hits(
    *,
    run: RetrievalRun,
    ranked_hits: list[RetrievalHit],
    top_k: int,
) -> RetrievalRun:
    return run.model_copy(
        update={
            "selected_hits": ranked_hits[:top_k],
            "dropped_hits": ranked_hits[top_k:],
        }
    )


__all__ = ["select_retrieval_hits"]
