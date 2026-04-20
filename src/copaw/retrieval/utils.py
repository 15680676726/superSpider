# -*- coding: utf-8 -*-
from __future__ import annotations

from html import unescape
import re
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

_HTTP_TIMEOUT_SECONDS = 8.0
_USER_AGENT = "copaw-retrieval/1.0"
_DIRECT_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
_HTML_TITLE_PATTERN = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_DESCRIPTION_PATTERN = re.compile(
    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'](?P<content>.*?)[\"']",
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_STYLE_PATTERN = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_DUCKDUCKGO_LINK_PATTERN = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_DUCKDUCKGO_SNIPPET_PATTERN = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>.*?</a>.*?<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>|'
    r'<a[^>]+class="result__a"[^>]+href="(?P<url2>[^"]+)"[^>]*>.*?</a>.*?<div[^>]+class="result__snippet"[^>]*>(?P<snippet2>.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_BING_LINK_PATTERN = re.compile(
    r'<li[^>]+class="b_algo"[^>]*>.*?<h2[^>]*>\s*<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a></h2>.*?(?:<p[^>]*>(?P<snippet>.*?)</p>)?',
    re.IGNORECASE | re.DOTALL,
)
_SEARCH_ENDPOINT = "https://duckduckgo.com/html/"
_BING_SEARCH_ENDPOINT = "https://www.bing.com/search"


def text(value: object) -> str:
    return str(value or "").strip()


def extract_first_url(*values: object) -> str:
    for value in values:
        match = _DIRECT_URL_PATTERN.search(text(value))
        if match is not None:
            return match.group(0).rstrip(").,;")
    return ""


def normalize_ref(value: str) -> str:
    return value.split("#", 1)[0].strip()


def clean_html_text(value: str) -> str:
    return " ".join(unescape(value or "").strip().split())


def strip_html(value: str) -> str:
    without_scripts = _SCRIPT_STYLE_PATTERN.sub(" ", value or "")
    without_tags = _TAG_PATTERN.sub(" ", without_scripts)
    return clean_html_text(without_tags)


def fetch_url_payload(source_ref: str) -> dict[str, str]:
    request = Request(
        source_ref,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8", errors="replace")
        content_type = response.headers.get_content_type()
        final_url = response.geturl()
    return {
        "url": final_url,
        "content_type": content_type,
        "body": body,
    }


def summarize_html_page(source_ref: str) -> dict[str, str]:
    payload = fetch_url_payload(source_ref)
    body = payload.get("body", "")
    title_match = _HTML_TITLE_PATTERN.search(body)
    description_match = _META_DESCRIPTION_PATTERN.search(body)
    stripped = strip_html(body)
    title = clean_html_text(title_match.group("title")) if title_match is not None else ""
    description = clean_html_text(description_match.group("content")) if description_match is not None else ""
    summary = description or stripped[:320]
    snippet = description or stripped[:180]
    return {
        "url": payload.get("url", source_ref),
        "title": title,
        "snippet": snippet,
        "summary": summary,
        "content_type": payload.get("content_type", ""),
    }


def _parse_duckduckgo_hits(body: str, limit: int) -> list[dict[str, str]]:
    snippets_by_url: dict[str, str] = {}
    for match in _DUCKDUCKGO_SNIPPET_PATTERN.finditer(body):
        url = text(match.group("url") or match.group("url2"))
        snippet = text(match.group("snippet") or match.group("snippet2"))
        if url and snippet and url not in snippets_by_url:
            snippets_by_url[url] = snippet
    hits: list[dict[str, str]] = []
    for match in _DUCKDUCKGO_LINK_PATTERN.finditer(body):
        url = text(match.group("url"))
        title = re.sub(r"<[^>]+>", " ", text(match.group("title")))
        if not url:
            continue
        hits.append({"title": " ".join(title.split()), "url": url, "snippet": snippets_by_url.get(url, "")})
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
        hits.append({"title": " ".join(title.split()), "url": url, "snippet": " ".join(snippet.split())})
        if len(hits) >= max(1, int(limit)):
            break
    return hits


def search_live_web(query: str, limit: int = 5) -> list[dict[str, str]]:
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


__all__ = [
    "extract_first_url",
    "fetch_url_payload",
    "normalize_ref",
    "search_live_web",
    "summarize_html_page",
    "text",
]
