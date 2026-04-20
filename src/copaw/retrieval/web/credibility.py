# -*- coding: utf-8 -*-
from __future__ import annotations

from urllib.parse import urlparse


def score_web_credibility(source_ref: str) -> float:
    host = urlparse(source_ref).netloc.casefold()
    if not host:
        return 0.2
    if host.startswith("docs.") or host.startswith("developer.") or host.startswith("developers."):
        return 0.95
    if host.endswith(".gov") or host.endswith(".edu"):
        return 0.95
    if "github.com" in host:
        return 0.9
    if host.count(".") >= 1:
        return 0.75
    return 0.5


__all__ = ["score_web_credibility"]
