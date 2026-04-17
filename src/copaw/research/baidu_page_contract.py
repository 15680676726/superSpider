# -*- coding: utf-8 -*-
from __future__ import annotations

from html import unescape
import re

from .models import BaiduPageContractResult, LoginStateResult, ResearchLink

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_ANSWER_BLOCK_RE = re.compile(
    r"<(?P<tag>div|section|main)[^>]*class=[\"'][^\"']*answer[^\"']*[\"'][^>]*>(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
_LINK_RE = re.compile(
    r"<a[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<label>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_LOGIN_HINTS = (
    "登录",
    "立即登录",
    "请登录",
    "扫码登录",
    "sign in",
    "log in",
    "login",
)


def _clean_text(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", str(raw_html or ""))
    text = unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def detect_login_state(page_text: str) -> LoginStateResult:
    normalized = _clean_text(page_text)
    lowered = normalized.casefold()
    for hint in _LOGIN_HINTS:
        if hint.casefold() in lowered:
            return LoginStateResult(state="login-required", reason=hint)
    if normalized:
        return LoginStateResult(state="ready", reason="")
    return LoginStateResult(state="unknown", reason="empty-page")


def _link_kind(url: str, label: str) -> str:
    lowered_url = str(url or "").strip().lower()
    lowered_label = str(label or "").strip().lower()
    if lowered_url.endswith(".pdf") or ".pdf?" in lowered_url or "pdf" in lowered_label:
        return "pdf"
    return "link"


def extract_answer_contract(snapshot_text: str) -> BaiduPageContractResult:
    login_result = detect_login_state(snapshot_text)
    answer_match = _ANSWER_BLOCK_RE.search(str(snapshot_text or ""))
    answer_text = _clean_text(answer_match.group("body")) if answer_match else ""
    links: list[ResearchLink] = []
    for match in _LINK_RE.finditer(str(snapshot_text or "")):
        url = str(match.group("href") or "").strip()
        if not url:
            continue
        label = _clean_text(match.group("label"))
        links.append(ResearchLink(url=url, label=label, kind=_link_kind(url, label)))
    login_state = login_result.state
    if login_state != "login-required" and (answer_text or links):
        login_state = "ready"
    return BaiduPageContractResult(
        login_state=login_state,
        answer_text=answer_text,
        links=links,
    )


__all__ = ["detect_login_state", "extract_answer_contract"]
