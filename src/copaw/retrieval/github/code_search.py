# -*- coding: utf-8 -*-
from __future__ import annotations

from ..contracts import RetrievalHit
from .object_search import search_github_objects


def search_github_code(*, query: str, limit: int = 5) -> list[RetrievalHit]:
    return search_github_objects(query=query, limit=limit)


__all__ = ["search_github_code"]
