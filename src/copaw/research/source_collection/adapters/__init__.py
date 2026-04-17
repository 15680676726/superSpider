# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable

from ..contracts import ResearchAdapterResult, ResearchBrief
from .artifact import collect_artifact
from .github import collect_github
from .search import collect_search
from .web_page import collect_web_page

SourceCollectionAdapter = Callable[[ResearchBrief], ResearchAdapterResult]


def build_source_collection_adapters() -> dict[str, SourceCollectionAdapter]:
    return {
        "search": collect_search,
        "web_page": collect_web_page,
        "github": collect_github,
        "artifact": collect_artifact,
    }


__all__ = [
    "SourceCollectionAdapter",
    "build_source_collection_adapters",
    "collect_artifact",
    "collect_github",
    "collect_search",
    "collect_web_page",
]
