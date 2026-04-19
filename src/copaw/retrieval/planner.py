# -*- coding: utf-8 -*-
from __future__ import annotations

from .contracts import RetrievalPlan


def build_retrieval_plan(
    *,
    intent: str,
    requested_sources: list[str] | None,
    latest_required: bool,
) -> RetrievalPlan:
    normalized_sources = [str(source).strip() for source in list(requested_sources or []) if str(source).strip()]
    if intent == "repo-trace":
        return RetrievalPlan(
            intent=intent,
            source_sequence=normalized_sources or ["local_repo"],
            mode_sequence=["symbol", "exact", "semantic"],
            allow_second_pass=True,
        )
    if intent == "external-latest":
        return RetrievalPlan(
            intent=intent,
            source_sequence=normalized_sources or ["github", "web"],
            mode_sequence=["exact", "semantic"],
            allow_second_pass=latest_required,
        )
    return RetrievalPlan(
        intent=intent,
        source_sequence=normalized_sources or ["web"],
        mode_sequence=["exact"],
        allow_second_pass=False,
    )


__all__ = ["build_retrieval_plan"]
