# -*- coding: utf-8 -*-
from __future__ import annotations

from html import unescape
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_HTTP_TIMEOUT_SECONDS = 8.0
_USER_AGENT = "copaw-source-collection/1.0"
_DIRECT_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
_WINDOWS_PATH_PATTERN = re.compile(
    r"(?P<path>[A-Za-z]:[\\/][^\\/:*?\"<>|\r\n]+(?:[\\/][^\\/:*?\"<>|\r\n]+)+)"
)
_HTML_TITLE_PATTERN = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_DESCRIPTION_PATTERN = re.compile(
    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'](?P<content>.*?)[\"']",
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_STYLE_PATTERN = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_PATTERN = re.compile(r"<[^>]+>")


def text(value: object) -> str:
    return str(value or "").strip()


def extract_first_url(*values: object) -> str:
    for value in values:
        match = _DIRECT_URL_PATTERN.search(text(value))
        if match is not None:
            return match.group(0).rstrip(").,;")
    return ""


def extract_first_windows_path(*values: object) -> str:
    for value in values:
        match = _WINDOWS_PATH_PATTERN.search(text(value))
        if match is not None:
            return match.group("path")
        candidate = text(value)
        if candidate and Path(candidate).exists():
            return candidate
    return ""


def normalize_ref(value: str) -> str:
    return value.split("#", 1)[0].strip()


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
    description = (
        clean_html_text(description_match.group("content"))
        if description_match is not None
        else ""
    )
    summary = description or stripped[:320]
    snippet = description or stripped[:180]
    return {
        "url": payload.get("url", source_ref),
        "title": title,
        "snippet": snippet,
        "summary": summary,
        "content_type": payload.get("content_type", ""),
    }


def clean_html_text(value: str) -> str:
    return " ".join(unescape(value or "").strip().split())


def strip_html(value: str) -> str:
    without_scripts = _SCRIPT_STYLE_PATTERN.sub(" ", value or "")
    without_tags = _TAG_PATTERN.sub(" ", without_scripts)
    return clean_html_text(without_tags)


def guess_title_from_ref(source_ref: str) -> str:
    parsed = urlparse(source_ref)
    if parsed.scheme in {"http", "https"}:
        return (parsed.path.rstrip("/").split("/")[-1] or parsed.netloc).strip()
    return Path(source_ref).name
