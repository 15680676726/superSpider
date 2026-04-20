# -*- coding: utf-8 -*-
from __future__ import annotations

from urllib.parse import urlparse

from ..utils import normalize_ref


def github_metadata(source_ref: str) -> dict[str, str]:
    parsed = urlparse(source_ref)
    segments = [segment for segment in parsed.path.split("/") if segment]
    repository = "/".join(segments[:2]) if len(segments) >= 2 else ""
    target_kind = "repository"
    if len(segments) >= 3:
        segment = segments[2].lower()
        if segment == "issues":
            target_kind = "issue"
        elif segment in {"pull", "pulls"}:
            target_kind = "pull_request"
        elif segment == "commit":
            target_kind = "commit"
        elif segment == "blob":
            target_kind = "blob"
        elif segment == "tree":
            target_kind = "tree"
        elif segment == "discussions":
            target_kind = "discussion"
        else:
            target_kind = segment
    return {
        "repository": repository,
        "github_target_kind": target_kind,
        "normalized_ref": normalize_ref(source_ref),
    }


__all__ = ["github_metadata"]
