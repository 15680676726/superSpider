# -*- coding: utf-8 -*-
from __future__ import annotations

from hashlib import sha1
from html import unescape
import re
from typing import Any, Literal, Mapping

from .models import (
    BaiduAdapterResult,
    BaiduCollectedSource,
    BaiduFinding,
    BaiduPageContractResult,
    LoginStateResult,
    ResearchLink,
)

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
_READY_HINTS = (
    "开启新对话",
    "知识库",
    "对话历史",
    "收藏夹",
)
_ANSWER_STOP_HINTS = (
    "内容由AI生成",
    "深度思考",
    "AI生图",
    "AI写作",
    "AI PPT",
    "AI编程",
    "深入研究",
    "AI翻译",
    "更多",
)
_SEARCH_RESULT_HINTS = (
    "全球搜检索",
    "search results",
)
_DOMAIN_HINTS = (
    "www.",
    ".com",
    ".cn",
    ".net",
    ".org",
    "github",
    "app store",
    "csdn",
)
_NOISE_LINK_LABELS = {
    "个人中心",
    "账号设置",
    "百度首页",
    "通知",
    "网页",
    "图片",
    "更多",
    "收藏夹",
    "反馈",
    "快捷入口",
}
_TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}$")
_RESULT_INDEX_RE = re.compile(r"^\d+\.$")


def _clean_text(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", str(raw_html or ""))
    text = unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _normalize_plain_line(raw_text: object) -> str:
    normalized = (
        str(raw_text or "")
        .replace("\u200b", " ")
        .replace("\u200c", " ")
        .replace("\ufeff", " ")
    )
    return _WHITESPACE_RE.sub(" ", unescape(normalized)).strip()


def _plain_lines(raw_text: object) -> list[str]:
    return [
        line
        for line in (_normalize_plain_line(item) for item in str(raw_text or "").splitlines())
        if line
    ]


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _text(value: object | None) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: object) -> str:
    normalized = "|".join(_text(part) for part in parts if _text(part))
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def detect_login_state(page_text: str) -> LoginStateResult:
    normalized = _clean_text(page_text)
    lowered = normalized.casefold()
    if any(hint.casefold() in lowered for hint in _READY_HINTS):
        return LoginStateResult(state="ready", reason="authenticated-ui")
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


def _should_keep_link(url: str, label: str) -> bool:
    normalized_label = _normalize_plain_line(label)
    lowered_url = str(url or "").strip().lower()
    if not lowered_url or lowered_url.startswith(("javascript:", "#")):
        return False
    if normalized_label in _NOISE_LINK_LABELS:
        return False
    if lowered_url.startswith("//www.baidu.com/my/"):
        return False
    if lowered_url.startswith("//passport.baidu.com"):
        return False
    return True


def _looks_like_search_result_line(line: str) -> bool:
    lowered = line.casefold()
    if _RESULT_INDEX_RE.match(line):
        return True
    if any(hint.casefold() in lowered for hint in _SEARCH_RESULT_HINTS):
        return True
    if any(hint in lowered for hint in _DOMAIN_HINTS):
        return True
    return False


def _looks_like_ui_noise_line(line: str) -> bool:
    lowered = line.casefold()
    if any(hint.casefold() == lowered for hint in _ANSWER_STOP_HINTS):
        return True
    if any(hint.casefold() == lowered for hint in _READY_HINTS):
        return True
    if _TIMESTAMP_RE.match(line):
        return True
    return False


def _extract_answer_from_text(raw_text: object) -> str:
    lines = _plain_lines(raw_text)
    line_counts = {line: lines.count(line) for line in set(lines)}
    answer_lines: list[str] = []
    collecting = False
    has_numbered_results = any(_RESULT_INDEX_RE.match(line) for line in lines)
    saw_numbered_results = False
    for line in lines:
        lowered = line.casefold()
        if _RESULT_INDEX_RE.match(line):
            saw_numbered_results = True
            if collecting and answer_lines:
                break
            continue
        if has_numbered_results and not saw_numbered_results:
            continue
        if _looks_like_search_result_line(line):
            if collecting and answer_lines:
                break
            continue
        if has_numbered_results and len(line) < 20:
            continue
        if not collecting:
            if _looks_like_ui_noise_line(line):
                continue
            if lowered.startswith("http"):
                continue
            if line.startswith("要不要我帮你"):
                continue
            if line_counts.get(line, 0) > 1:
                continue
            if not saw_numbered_results and ("?" in line or "？" in line):
                continue
            if has_numbered_results and not line.endswith(("。", ".", "：", ":", "！", "!", "？", "?")):
                continue
            if len(line) < 20:
                continue
            collecting = True
            answer_lines.append(line)
            continue
        if _looks_like_ui_noise_line(line):
            break
        if line.startswith("要不要我帮你"):
            break
        if has_numbered_results and not line.endswith(("。", ".", "：", ":", "！", "!", "？", "?")):
            break
        answer_lines.append(line)
    return "\n\n".join(answer_lines).strip()


def _collection_action(page_href: str) -> Literal["read", "interact"]:
    if "chat.baidu.com/search" in _text(page_href).lower():
        return "interact"
    return "read"


def _build_adapter_result(
    *,
    payload: Mapping[str, Any],
    login_state: str,
    answer_text: str,
    links: list[ResearchLink],
) -> BaiduAdapterResult:
    page_href = _text(payload.get("href"))
    collected_sources: list[BaiduCollectedSource] = []
    source_ids: list[str] = []
    for link in links:
        source_id = _stable_id("baidu-source", link.url, link.kind)
        source_ids.append(source_id)
        collected_sources.append(
            BaiduCollectedSource(
                source_id=source_id,
                source_kind=link.kind or "link",
                collection_action="read",
                source_ref=link.url,
                normalized_ref=link.url,
                title=link.label,
                snippet=answer_text[:240],
                metadata={"provider": "baidu-page"},
            )
        )
    summary = answer_text.splitlines()[0].strip() if answer_text.strip() else ""
    findings: list[BaiduFinding] = []
    if summary:
        findings.append(
            BaiduFinding(
                finding_id=_stable_id("baidu-finding", summary, page_href),
                finding_type="answer",
                summary=summary,
                supporting_source_ids=source_ids,
                metadata={"provider": "baidu-page"},
            )
        )
    if login_state == "login-required":
        status: Literal["succeeded", "partial", "blocked"] = "blocked"
    elif summary or collected_sources:
        status = "succeeded"
    else:
        status = "partial"
    return BaiduAdapterResult(
        adapter_kind="baidu_page",
        collection_action=_collection_action(page_href),
        status=status,
        summary=summary,
        collected_sources=collected_sources,
        findings=findings,
        gaps=[] if summary or collected_sources else ["No normalized answer or source was extracted."],
        metadata={
            "provider": "baidu-page",
            "login_state": login_state,
            "page_href": page_href,
            "page_title": _text(payload.get("title")),
        },
    )


def extract_answer_contract(snapshot_text: str | Mapping[str, object]) -> BaiduPageContractResult:
    payload = _mapping(snapshot_text)
    raw_html = str(payload.get("html") or snapshot_text or "")
    body_text = str(payload.get("bodyText") or payload.get("body_text") or "")
    login_result = detect_login_state(body_text or raw_html)
    answer_match = _ANSWER_BLOCK_RE.search(raw_html)
    answer_text = _clean_text(answer_match.group("body")) if answer_match else ""
    if not answer_text and body_text:
        answer_text = _extract_answer_from_text(body_text)
    links: list[ResearchLink] = []
    for match in _LINK_RE.finditer(raw_html):
        url = str(match.group("href") or "").strip()
        if not url:
            continue
        label = _clean_text(match.group("label"))
        if not _should_keep_link(url, label):
            continue
        links.append(ResearchLink(url=url, label=label, kind=_link_kind(url, label)))
    login_state = login_result.state
    if answer_text or links:
        login_state = "ready"
    return BaiduPageContractResult(
        login_state=login_state,
        answer_text=answer_text,
        links=links,
        adapter_result=_build_adapter_result(
            payload=payload,
            login_state=login_state,
            answer_text=answer_text,
            links=links,
        ),
    )


__all__ = ["detect_login_state", "extract_answer_contract"]
