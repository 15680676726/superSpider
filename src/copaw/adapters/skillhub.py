# -*- coding: utf-8 -*-
"""SkillHub store adapter for remote skill discovery."""
from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_DEFAULT_SEARCH_URL = "https://lightmake.site/api/v1/search"
_DEFAULT_DOWNLOAD_URL_TEMPLATE = (
    "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/{slug}.zip"
)
_DEFAULT_TIMEOUT_SECONDS = 15.0


@dataclass
class SkillHubSearchResult:
    slug: str
    name: str
    description: str = ""
    version: str = ""
    source_url: str = ""
    source_label: str = "SkillHub 商店"
    score: float = 0.0
    updated_at: int | None = None


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def skillhub_enabled() -> bool:
    return _bool_env("COPAW_SKILLHUB_ENABLED", True)


def skillhub_source_label() -> str:
    return (
        os.environ.get("COPAW_SKILLHUB_SOURCE_LABEL", "SkillHub 商店").strip()
        or "SkillHub 商店"
    )


def _skillhub_timeout() -> float:
    raw = os.environ.get("COPAW_SKILLHUB_TIMEOUT_SECONDS", "").strip()
    try:
        return max(3.0, float(raw))
    except Exception:
        return _DEFAULT_TIMEOUT_SECONDS


def _skillhub_search_url() -> str:
    return os.environ.get("COPAW_SKILLHUB_SEARCH_URL", "").strip() or _DEFAULT_SEARCH_URL


def _skillhub_download_url_template() -> str:
    return (
        os.environ.get("COPAW_SKILLHUB_DOWNLOAD_URL_TEMPLATE", "").strip()
        or _DEFAULT_DOWNLOAD_URL_TEMPLATE
    )


def _http_json_get(url: str, params: dict[str, Any] | None = None) -> Any:
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"
    request = Request(
        full_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "copaw-skillhub-adapter/1.0",
        },
    )
    with urlopen(request, timeout=_skillhub_timeout()) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def _http_bytes_get(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "*/*",
            "User-Agent": "copaw-skillhub-adapter/1.0",
        },
    )
    with urlopen(request, timeout=_skillhub_timeout()) as response:
        return response.read()


def _skillhub_download_url(slug: str) -> str:
    template = _skillhub_download_url_template()
    return template.replace("{slug}", slug)


def _search_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        if isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _presentation_helpers():
    from ..capabilities.remote_skill_presentation import (
        present_remote_skill_name,
        present_remote_skill_source_label,
        present_remote_skill_summary,
    )

    return (
        present_remote_skill_name,
        present_remote_skill_source_label,
        present_remote_skill_summary,
    )


def search_skillhub_skills(query: str, limit: int = 20) -> list[SkillHubSearchResult]:
    normalized_query = str(query or "").strip()
    if not skillhub_enabled():
        return []
    (
        present_remote_skill_name,
        present_remote_skill_source_label,
        present_remote_skill_summary,
    ) = _presentation_helpers()
    payload = _http_json_get(
        _skillhub_search_url(),
        {
            "q": normalized_query,
            "limit": max(1, int(limit)),
        },
    )
    results: list[SkillHubSearchResult] = []
    for item in _search_items(payload):
        slug = str(item.get("slug") or item.get("name") or "").strip()
        if not slug:
            continue
        raw_name = str(item.get("displayName") or item.get("name") or slug).strip() or slug
        raw_summary = str(item.get("summary") or item.get("description") or "").strip()
        updated_at_raw = str(item.get("updatedAt") or "").strip()
        results.append(
            SkillHubSearchResult(
                slug=slug,
                name=present_remote_skill_name(
                    slug=slug,
                    name=raw_name,
                    summary=raw_summary,
                ),
                description=present_remote_skill_summary(
                    slug=slug,
                    name=raw_name,
                    summary=raw_summary,
                ),
                version=str(item.get("version") or "").strip(),
                source_url=_skillhub_download_url(slug),
                source_label=present_remote_skill_source_label(curated=False),
                score=float(item.get("score") or 0.0),
                updated_at=int(updated_at_raw) if updated_at_raw else None,
            ),
        )
    return results


def is_skillhub_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.netloc or "").lower()
    return host in {
        "skillhub-1388575217.cos.ap-guangzhou.myqcloud.com",
        "lightmake.site",
    }


def bundle_url_to_skillhub_slug(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.netloc or "").lower()
    if host == "lightmake.site":
        return str(parse_qs(parsed.query).get("slug", [""])[0]).strip()
    if host == "skillhub-1388575217.cos.ap-guangzhou.myqcloud.com":
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[-1].endswith(".zip"):
            return parts[-1][: -len(".zip")].strip()
    return ""


def load_skillhub_bundle_from_url(bundle_url: str) -> tuple[dict[str, Any], str]:
    payload = _bundle_payload_from_zip_bytes(_http_bytes_get(bundle_url))
    return payload, bundle_url


def _normalize_zip_files(file_map: dict[str, str]) -> dict[str, str]:
    if not file_map:
        return {}
    root_prefix = ""
    roots = {path.split("/", 1)[0] for path in file_map if "/" in path}
    if len(roots) == 1:
        only_root = next(iter(roots))
        if all(path == only_root or path.startswith(f"{only_root}/") for path in file_map):
            root_prefix = f"{only_root}/"
    normalized: dict[str, str] = {}
    for path, content in file_map.items():
        rel = path[len(root_prefix) :] if root_prefix and path.startswith(root_prefix) else path
        rel = rel.strip("/")
        if not rel:
            continue
        normalized[rel] = content
    return normalized


def _bundle_payload_from_zip_bytes(data: bytes) -> dict[str, Any]:
    file_map: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = str(info.filename or "").strip().replace("\\", "/")
            if not path:
                continue
            file_map[path] = archive.read(info).decode("utf-8", errors="replace")
    normalized_files = _normalize_zip_files(file_map)
    if "SKILL.md" not in normalized_files:
        raise ValueError("SkillHub bundle missing SKILL.md")
    return {"files": normalized_files}
