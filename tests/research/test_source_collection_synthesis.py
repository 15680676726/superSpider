# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.research.source_collection.contracts import (
    CollectedSource,
    ResearchAdapterResult,
    ResearchFinding,
)
from copaw.research.source_collection.synthesis import synthesize_collection_results


def test_synthesize_findings_dedupes_duplicate_sources() -> None:
    duplicate = CollectedSource(
        source_id="source-1",
        source_kind="repo",
        collection_action="read",
        source_ref="https://github.com/example/project",
        normalized_ref="https://github.com/example/project",
        title="example/project",
    )

    merged = synthesize_collection_results(
        [
            ResearchAdapterResult(
                adapter_kind="github",
                collection_action="read",
                status="succeeded",
                collected_sources=[duplicate],
            ),
            ResearchAdapterResult(
                adapter_kind="web_page",
                collection_action="read",
                status="succeeded",
                collected_sources=[duplicate],
            ),
        ],
    )

    assert len(merged.collected_sources) == 1


def test_synthesize_findings_marks_conflicts_and_gaps() -> None:
    merged = synthesize_collection_results(
        [
            ResearchAdapterResult(
                adapter_kind="search",
                collection_action="discover",
                status="succeeded",
                findings=[
                    ResearchFinding(
                        finding_id="finding-1",
                        finding_type="constraint",
                        summary="Use the twelve-house model.",
                    ),
                ],
                conflicts=["Need source-of-truth confirmation."],
                gaps=["Still missing one official reference."],
            ),
        ],
    )

    assert merged.findings
    assert merged.conflicts == ["Need source-of-truth confirmation."]
    assert merged.gaps == ["Still missing one official reference."]
