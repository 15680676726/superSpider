# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
import re
from urllib.parse import urlencode

from ..contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding
from ._shared import fetch_url_payload, normalize_ref, text


_RESULT_LINK_PATTERN = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_RESULT_SNIPPET_PATTERN = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>.*?</a>.*?<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>|'
    r'<a[^>]+class="result__a"[^>]+href="(?P<url2>[^"]+)"[^>]*>.*?</a>.*?<div[^>]+class="result__snippet"[^>]*>(?P<snippet2>.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_SEARCH_ENDPOINT = "https://duckduckgo.com/html/"
_BING_SEARCH_ENDPOINT = "https://www.bing.com/search"
_BING_LINK_PATTERN = re.compile(
    r'<li[^>]+class="b_algo"[^>]*>.*?<h2[^>]*>\s*<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a></h2>.*?(?:<p[^>]*>(?P<snippet>.*?)</p>)?',
    re.IGNORECASE | re.DOTALL,
)


def _parse_duckduckgo_hits(body: str, limit: int) -> list[dict[str, str]]:
    snippets_by_url: dict[str, str] = {}
    for match in _RESULT_SNIPPET_PATTERN.finditer(body):
        url = text(match.group("url") or match.group("url2"))
        snippet = text(match.group("snippet") or match.group("snippet2"))
        if url and snippet and url not in snippets_by_url:
            snippets_by_url[url] = snippet
    hits: list[dict[str, str]] = []
    for match in _RESULT_LINK_PATTERN.finditer(body):
        url = text(match.group("url"))
        title = re.sub(r"<[^>]+>", " ", text(match.group("title")))
        if not url:
            continue
        hits.append(
            {
                "title": " ".join(title.split()),
                "url": url,
                "snippet": snippets_by_url.get(url, ""),
            }
        )
        if len(hits) >= max(1, int(limit)):
            break
    return hits


def _search_duckduckgo(query: str, limit: int) -> list[dict[str, str]]:
    payload = fetch_url_payload(f"{_SEARCH_ENDPOINT}?{urlencode({'q': query})}")
    return _parse_duckduckgo_hits(payload.get("body", ""), limit)


def _search_bing(query: str, limit: int) -> list[dict[str, str]]:
    payload = fetch_url_payload(f"{_BING_SEARCH_ENDPOINT}?{urlencode({'q': query})}")
    body = payload.get("body", "")
    hits: list[dict[str, str]] = []
    for match in _BING_LINK_PATTERN.finditer(body):
        url = text(match.group("url"))
        title = re.sub(r"<[^>]+>", " ", text(match.group("title")))
        snippet = re.sub(r"<[^>]+>", " ", text(match.group("snippet")))
        if not url:
            continue
        hits.append(
            {
                "title": " ".join(title.split()),
                "url": url,
                "snippet": " ".join(snippet.split()),
            }
        )
        if len(hits) >= max(1, int(limit)):
            break
    return hits


def _search_live(query: str, limit: int = 5) -> list[dict[str, str]]:
    query_text = text(query)
    if not query_text:
        return []
    for provider in (_search_duckduckgo, _search_bing):
        try:
            hits = provider(query_text, limit)
        except Exception:
            hits = []
        if hits:
            return hits
    return []


def collect_search(brief: ResearchBrief) -> ResearchAdapterResult:
    raw_hits = brief.metadata.get("search_hits")
    hits = raw_hits if isinstance(raw_hits, list) else _search_live(brief.question, limit=5)
    collected_sources: list[CollectedSource] = []

    for index, item in enumerate(hits, start=1):
        if not isinstance(item, Mapping):
            continue
        source_ref = text(item.get("url") or item.get("source_ref"))
        if not source_ref:
            continue
        collected_sources.append(
            CollectedSource(
                source_id=f"search-hit-{index}",
                source_kind="search_hit",
                collection_action="discover",
                source_ref=source_ref,
                normalized_ref=normalize_ref(source_ref),
                title=text(item.get("title")),
                snippet=text(item.get("snippet")),
                access_status="discovered",
                metadata={"rank": index},
            )
        )

    if not collected_sources:
        return ResearchAdapterResult(
            adapter_kind="search",
            collection_action="discover",
            status="partial",
            summary="Search adapter returned no discovered hits.",
            gaps=["search provider returned no hits for the brief"],
        )

    return ResearchAdapterResult(
        adapter_kind="search",
        collection_action="discover",
        status="succeeded",
        collected_sources=collected_sources,
        findings=[
            ResearchFinding(
                finding_id="search-discovery-1",
                finding_type="candidate-source-set",
                summary=f"Discovered {len(collected_sources)} candidate sources for the brief.",
                supporting_source_ids=[source.source_id for source in collected_sources],
            )
        ],
        summary=f"Discovered {len(collected_sources)} search hit(s).",
    )


__all__ = ["collect_search"]
