# -*- coding: utf-8 -*-
from __future__ import annotations

from pydantic import BaseModel, Field

from .contracts import CollectedSource, ResearchAdapterResult, ResearchFinding


class SynthesizedCollectionResult(BaseModel):
    adapter_results: list[ResearchAdapterResult] = Field(default_factory=list)
    collected_sources: list[CollectedSource] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


def _source_key(source: CollectedSource) -> str:
    return source.normalized_ref or source.source_ref or source.source_id


def synthesize_collection_results(
    results: list[ResearchAdapterResult],
) -> SynthesizedCollectionResult:
    deduped_sources: dict[str, CollectedSource] = {}
    deduped_findings: dict[str, ResearchFinding] = {}
    conflicts: list[str] = []
    gaps: list[str] = []

    for result in results:
        for source in result.collected_sources:
            deduped_sources.setdefault(_source_key(source), source)
        for finding in result.findings:
            deduped_findings.setdefault(finding.finding_id, finding)
        for conflict in result.conflicts:
            if conflict not in conflicts:
                conflicts.append(conflict)
        for gap in result.gaps:
            if gap not in gaps:
                gaps.append(gap)

    return SynthesizedCollectionResult(
        adapter_results=list(results),
        collected_sources=list(deduped_sources.values()),
        findings=list(deduped_findings.values()),
        conflicts=conflicts,
        gaps=gaps,
    )


__all__ = ["SynthesizedCollectionResult", "synthesize_collection_results"]
