# -*- coding: utf-8 -*-
"""SkillHub store adapter for remote skill discovery."""
from __future__ import annotations

import copy
import io
import json
import logging
import os
import time
import zipfile
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_DEFAULT_SEARCH_URL = "https://lightmake.site/api/v1/search"
_DEFAULT_DOWNLOAD_URL_TEMPLATE = (
    "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/{slug}.zip"
)
_DEFAULT_CLAWHUB_BASE_URL = "https://clawhub.ai"
_DEFAULT_TIMEOUT_SECONDS = 15.0
_DEFAULT_RETRY_ATTEMPTS = 3
_DEFAULT_RETRY_BACKOFF_SECONDS = 0.6
_BUNDLE_VALIDATION_CACHE_TTL_SECONDS = 600.0
_BUNDLE_VALIDATION_CACHE: dict[str, tuple[float, bool]] = {}
_BUNDLE_PAYLOAD_CACHE: dict[str, tuple[float, tuple[dict[str, Any], str]]] = {}


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


def _skillhub_retry_attempts() -> int:
    raw = os.environ.get("COPAW_SKILLHUB_RETRY_ATTEMPTS", "").strip()
    try:
        return max(1, int(raw))
    except Exception:
        return _DEFAULT_RETRY_ATTEMPTS


def _skillhub_retry_backoff_seconds() -> float:
    raw = os.environ.get("COPAW_SKILLHUB_RETRY_BACKOFF_SECONDS", "").strip()
    try:
        return max(0.1, float(raw))
    except Exception:
        return _DEFAULT_RETRY_BACKOFF_SECONDS


def _skillhub_search_url() -> str:
    return os.environ.get("COPAW_SKILLHUB_SEARCH_URL", "").strip() or _DEFAULT_SEARCH_URL


def _skillhub_download_url_template() -> str:
    return (
        os.environ.get("COPAW_SKILLHUB_DOWNLOAD_URL_TEMPLATE", "").strip()
        or _DEFAULT_DOWNLOAD_URL_TEMPLATE
    )


def _clawhub_base_url() -> str:
    return (
        os.environ.get("COPAW_SKILLS_HUB_BASE_URL", "").strip()
        or _DEFAULT_CLAWHUB_BASE_URL
    )


def _clawhub_detail_path() -> str:
    return os.environ.get(
        "COPAW_SKILLS_HUB_DETAIL_PATH",
        "/api/v1/skills/{slug}",
    )


def _clawhub_version_path() -> str:
    return os.environ.get(
        "COPAW_SKILLS_HUB_VERSION_PATH",
        "/api/v1/skills/{slug}/versions/{version}",
    )


def _clawhub_file_path() -> str:
    return os.environ.get(
        "COPAW_SKILLS_HUB_FILE_PATH",
        "/api/v1/skills/{slug}/file",
    )


def _join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _get_cached_bundle_payload(bundle_url: str) -> tuple[dict[str, Any], str] | None:
    cached = _BUNDLE_PAYLOAD_CACHE.get(bundle_url)
    if cached is None:
        return None
    now = time.time()
    if (now - cached[0]) > _BUNDLE_VALIDATION_CACHE_TTL_SECONDS:
        _BUNDLE_PAYLOAD_CACHE.pop(bundle_url, None)
        return None
    payload, source_url = cached[1]
    return copy.deepcopy(payload), source_url


def _store_cached_bundle_payload(
    bundle_url: str,
    payload: dict[str, Any],
    source_url: str,
) -> None:
    _BUNDLE_PAYLOAD_CACHE[bundle_url] = (
        time.time(),
        (copy.deepcopy(payload), source_url),
    )


def _is_retryable_http_error(exc: HTTPError) -> bool:
    return int(getattr(exc, "code", 0) or 0) in {429, 500, 502, 503, 504}


def _retry_after_seconds(exc: HTTPError) -> float | None:
    headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    raw = str(headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        return max(0.1, float(raw))
    except Exception:
        return None


def _urlopen_with_retry(request: Request):
    attempts = _skillhub_retry_attempts()
    backoff = _skillhub_retry_backoff_seconds()
    for attempt in range(attempts):
        try:
            return urlopen(request, timeout=_skillhub_timeout())
        except HTTPError as exc:
            if not _is_retryable_http_error(exc) or attempt + 1 >= attempts:
                raise
            sleep_seconds = _retry_after_seconds(exc) or (backoff * (2**attempt))
            logger.warning(
                "SkillHub request rate-limited or unavailable (%s). Retrying %s/%s for %s in %.2fs",
                getattr(exc, "code", "error"),
                attempt + 1,
                attempts - 1,
                request.full_url,
                sleep_seconds,
            )
            if getattr(exc, "fp", None) is not None:
                try:
                    exc.fp.close()
                except Exception:
                    pass
            time.sleep(sleep_seconds)
    raise RuntimeError(f"SkillHub request retry loop exhausted for {request.full_url}")


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
    with _urlopen_with_retry(request) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def _http_text_get(url: str, params: dict[str, Any] | None = None) -> str:
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params)}"
    request = Request(
        full_url,
        headers={
            "Accept": "text/plain, text/markdown, */*",
            "User-Agent": "copaw-skillhub-adapter/1.0",
        },
    )
    with _urlopen_with_retry(request) as response:
        return response.read().decode("utf-8", errors="replace")


def _http_bytes_get(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "*/*",
            "User-Agent": "copaw-skillhub-adapter/1.0",
        },
    )
    with _urlopen_with_retry(request) as response:
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


def search_skillhub_skills(
    query: str,
    limit: int = 20,
    *,
    search_url: str | None = None,
) -> list[SkillHubSearchResult]:
    normalized_query = str(query or "").strip()
    if not skillhub_enabled():
        return []
    (
        present_remote_skill_name,
        present_remote_skill_source_label,
        present_remote_skill_summary,
    ) = _presentation_helpers()
    payload = _http_json_get(
        str(search_url or "").strip() or _skillhub_search_url(),
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
        "clawhub.ai",
        "www.clawhub.ai",
    }


def bundle_url_to_skillhub_slug(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.netloc or "").lower()
    if host in {"clawhub.ai", "www.clawhub.ai"}:
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            return parts[-1].strip()
    if host == "lightmake.site":
        return str(parse_qs(parsed.query).get("slug", [""])[0]).strip()
    if host == "skillhub-1388575217.cos.ap-guangzhou.myqcloud.com":
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[-1].endswith(".zip"):
            return parts[-1][: -len(".zip")].strip()
    return ""


def _extract_clawhub_version_hint(detail_payload: Any) -> str:
    if not isinstance(detail_payload, dict):
        return ""
    latest = detail_payload.get("latestVersion")
    if isinstance(latest, dict):
        version = str(latest.get("version") or "").strip()
        if version:
            return version
    skill = detail_payload.get("skill")
    if isinstance(skill, dict):
        tags = skill.get("tags")
        if isinstance(tags, dict):
            version = str(tags.get("latest") or "").strip()
            if version:
                return version
    return ""


def _load_skillhub_bundle_from_clawhub_slug(
    slug: str,
) -> tuple[dict[str, Any], str]:
    normalized_slug = str(slug or "").strip()
    if not normalized_slug:
        raise ValueError("SkillHub slug is required")
    base_url = _clawhub_base_url()
    detail_url = _join_url(
        base_url,
        _clawhub_detail_path().format(slug=normalized_slug),
    )
    detail_payload = _http_json_get(detail_url)
    version = _extract_clawhub_version_hint(detail_payload)
    if not version:
        raise ValueError(
            f"SkillHub bundle '{normalized_slug}' did not expose a downloadable version",
        )
    version_url = _join_url(
        base_url,
        _clawhub_version_path().format(
            slug=normalized_slug,
            version=version,
        ),
    )
    version_payload = _http_json_get(version_url)
    version_object = (
        version_payload.get("version")
        if isinstance(version_payload, dict)
        else None
    )
    files_meta = (
        version_object.get("files")
        if isinstance(version_object, dict)
        else None
    )
    if not isinstance(files_meta, list):
        raise ValueError(
            f"SkillHub bundle '{normalized_slug}' did not expose file metadata",
        )
    file_url = _join_url(
        base_url,
        _clawhub_file_path().format(slug=normalized_slug),
    )
    files: dict[str, str] = {}
    for item in files_meta:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        files[path] = _http_text_get(
            file_url,
            params={"path": path, "version": version},
        )
    if not isinstance(files.get("SKILL.md"), str) or not files["SKILL.md"].strip():
        raise ValueError(
            f"SkillHub bundle '{normalized_slug}' is missing SKILL.md content",
        )
    return {
        "files": files,
    }, detail_url


def load_skillhub_bundle_from_url(bundle_url: str) -> tuple[dict[str, Any], str]:
    normalized_url = str(bundle_url or "").strip()
    cached = _get_cached_bundle_payload(normalized_url)
    if cached is not None:
        return cached
    try:
        payload = _bundle_payload_from_zip_bytes(_http_bytes_get(normalized_url))
        _store_cached_bundle_payload(normalized_url, payload, normalized_url)
        return copy.deepcopy(payload), normalized_url
    except Exception as exc:
        slug = bundle_url_to_skillhub_slug(normalized_url)
        if not slug:
            raise
        try:
            payload, source_url = _load_skillhub_bundle_from_clawhub_slug(slug)
            _store_cached_bundle_payload(normalized_url, payload, source_url)
            return copy.deepcopy(payload), source_url
        except Exception as fallback_exc:
            raise fallback_exc from exc


def skillhub_bundle_is_installable(bundle_url: str) -> bool:
    normalized_url = str(bundle_url or "").strip()
    if not normalized_url:
        return False
    cached = _BUNDLE_VALIDATION_CACHE.get(normalized_url)
    now = time.time()
    if cached is not None and (now - cached[0]) <= _BUNDLE_VALIDATION_CACHE_TTL_SECONDS:
        return bool(cached[1])
    try:
        load_skillhub_bundle_from_url(normalized_url)
    except Exception as exc:  # pragma: no cover - network/runtime variability
        logger.warning("SkillHub bundle validation failed for %s: %s", normalized_url, exc)
        _BUNDLE_VALIDATION_CACHE[normalized_url] = (now, False)
        return False
    _BUNDLE_VALIDATION_CACHE[normalized_url] = (now, True)
    return True


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
