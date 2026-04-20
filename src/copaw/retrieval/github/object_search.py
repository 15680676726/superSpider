# -*- coding: utf-8 -*-
from __future__ import annotations

from ...discovery.provider_search import search_github_repository_donors
from ..contracts import RetrievalHit
from ..utils import extract_first_url, text
from .normalization import github_metadata


def search_github_objects(*, query: str, limit: int = 5) -> list[RetrievalHit]:
    direct_url = extract_first_url(query)
    if direct_url and "github.com/" in direct_url.casefold():
        metadata = github_metadata(direct_url)
        return [
            RetrievalHit(
                source_kind="github",
                provider_kind="object",
                hit_kind=metadata["github_target_kind"],
                ref=direct_url,
                normalized_ref=metadata["normalized_ref"],
                title=metadata["repository"] or direct_url,
                snippet=metadata["github_target_kind"],
                score=0.95,
                relevance_score=0.95,
                answerability_score=0.85,
                credibility_score=0.95,
                freshness_score=0.0,
                structural_score=0.7,
                why_matched="direct GitHub target reference",
                metadata={
                    "repository": metadata["repository"],
                    "github_target_kind": metadata["github_target_kind"],
                },
            )
        ]
    hits = search_github_repository_donors(query, limit=limit)
    results: list[RetrievalHit] = []
    for hit in hits:
        source_ref = text(getattr(hit, "candidate_source_ref", None))
        if not source_ref:
            continue
        metadata = github_metadata(source_ref)
        results.append(
            RetrievalHit(
                source_kind="github",
                provider_kind="object",
                hit_kind=metadata["github_target_kind"],
                ref=source_ref,
                normalized_ref=metadata["normalized_ref"],
                title=text(getattr(hit, "display_name", None)) or metadata["repository"],
                snippet=text(getattr(hit, "summary", None)),
                score=0.85,
                relevance_score=0.85,
                answerability_score=0.7,
                credibility_score=0.9,
                freshness_score=0.0,
                structural_score=0.5,
                why_matched="GitHub donor search match",
                metadata={
                    "repository": metadata["repository"],
                    "github_target_kind": metadata["github_target_kind"],
                },
            )
        )
    return results


__all__ = ["search_github_objects"]
