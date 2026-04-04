# -*- coding: utf-8 -*-
"""SkillHub-backed curated remote skill catalog."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import quote, unquote

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..adapters.skillhub import (
    SkillHubSearchResult,
    search_skillhub_skills,
    skillhub_bundle_is_installable,
)
from .remote_skill_presentation import (
    present_remote_skill_name,
    present_remote_skill_source_label,
    present_remote_skill_summary,
)

_DEFAULT_ALLOWED_BUNDLE_HOSTS = [
    "lightmake.site",
    "skillhub-1388575217.cos.ap-guangzhou.myqcloud.com",
]

_DEFAULT_CATALOG_URL = "https://lightmake.site"
_CACHE_TTL = timedelta(minutes=10)
_CATALOG_CACHE: dict[str, tuple[datetime, list["CuratedSkillCatalogEntry"], list[str]]] = {}

_DEFAULT_SOURCES = [
    {
        "source_id": "skillhub-featured-core",
        "label": "SkillHub 精选·通用执行",
        "source_kind": "skillhub-curated",
        "query": "automation",
        "max_items": 20,
        "notes": [
            "来自 SkillHub 商店的通用精选，用于补齐基础执行能力。",
        ],
    },
    {
        "source_id": "skillhub-featured-browser",
        "label": "SkillHub 精选·网页执行",
        "source_kind": "skillhub-curated",
        "query": "browser automation",
        "max_items": 20,
        "notes": [
            "面向网页登录、网页操作、抓取与页面自动化场景。",
        ],
    },
    {
        "source_id": "skillhub-featured-research",
        "label": "SkillHub 精选·研究分析",
        "source_kind": "skillhub-curated",
        "query": "industry research",
        "max_items": 20,
        "notes": [
            "面向研究、监测、信息整理和趋势分析场景。",
        ],
    },
    {
        "source_id": "skillhub-featured-content",
        "label": "SkillHub 精选·内容处理",
        "source_kind": "skillhub-curated",
        "query": "content strategy",
        "max_items": 20,
        "notes": [
            "面向内容策划、文案整理和内容产出场景。",
        ],
    },
    {
        "source_id": "skillhub-featured-image",
        "label": "SkillHub 精选·图像素材",
        "source_kind": "skillhub-curated",
        "query": "image",
        "max_items": 20,
        "notes": [
            "面向图片处理、OCR 识别和素材加工场景。",
        ],
    },
    {
        "source_id": "skillhub-featured-customer",
        "label": "SkillHub 精选·客户协作",
        "source_kind": "skillhub-curated",
        "query": "customer service",
        "max_items": 20,
        "notes": [
            "面向客服、客户跟进和客户协作场景。",
        ],
    },
    {
        "source_id": "skillhub-featured-data",
        "label": "SkillHub 精选·数据协作",
        "source_kind": "skillhub-curated",
        "query": "excel",
        "max_items": 20,
        "notes": [
            "面向表格、结构化数据与协作整理场景。",
        ],
    },
    {
        "source_id": "skillhub-featured-workflow",
        "label": "SkillHub 精选·流程自动化",
        "source_kind": "skillhub-curated",
        "query": "workflow automation",
        "max_items": 20,
        "notes": [
            "面向 SOP、流程编排和通用自动化场景。",
        ],
    },
    {
        "source_id": "skillhub-featured-code",
        "label": "SkillHub 精选·代码协作",
        "source_kind": "skillhub-curated",
        "query": "github",
        "max_items": 20,
        "notes": [
            "面向代码仓库、问题跟踪和自动化协作场景。",
        ],
    },
]


def _normalize_curated_source_kind(value: object | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "github-curated":
        return "skillhub-curated"
    return normalized or "skillhub-curated"


def _normalize_curated_discovery_kind(value: object | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "readme-link":
        return "skillhub-search"
    return normalized or "skillhub-preset"


def _normalize_curated_manifest_status(value: object | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "legacy-readme":
        return "skillhub-curated"
    return normalized or "skillhub-curated"


class CuratedSkillCatalogSource(BaseModel):
    source_id: str
    label: str
    source_kind: Literal["skillhub-curated"] = "skillhub-curated"
    query: str = ""
    max_items: int = Field(default=6, ge=1, le=500)
    notes: list[str] = Field(default_factory=list)
    allowed_bundle_hosts: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_ALLOWED_BUNDLE_HOSTS),
    )


class CuratedSkillCatalogEntry(BaseModel):
    candidate_id: str
    source_id: str
    source_label: str
    source_kind: Literal["skillhub-curated"] = "skillhub-curated"
    source_repo_url: str = ""
    discovery_kind: Literal["skillhub-preset", "skillhub-search", "manifest"] = (
        "skillhub-preset"
    )
    manifest_status: Literal["skillhub-curated", "verified"] = (
        "skillhub-curated"
    )
    title: str
    description: str = ""
    bundle_url: str
    version: str = ""
    install_name: str = ""
    tags: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    review_required: bool = False
    review_summary: str = ""
    review_notes: list[str] = Field(default_factory=list)
    routes: dict[str, str] = Field(default_factory=dict)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object | None) -> str:
        return _normalize_curated_source_kind(value)

    @field_validator("discovery_kind", mode="before")
    @classmethod
    def _normalize_discovery_kind(cls, value: object | None) -> str:
        return _normalize_curated_discovery_kind(value)

    @field_validator("manifest_status", mode="before")
    @classmethod
    def _normalize_manifest_status(cls, value: object | None) -> str:
        return _normalize_curated_manifest_status(value)


class CuratedSkillCatalogSearchResponse(BaseModel):
    sources: list[CuratedSkillCatalogSource] = Field(default_factory=list)
    items: list[CuratedSkillCatalogEntry] = Field(default_factory=list)
    total: int = 0
    warnings: list[str] = Field(default_factory=list)


def clear_curated_skill_catalog_cache() -> None:
    _CATALOG_CACHE.clear()


def list_curated_skill_sources() -> list[CuratedSkillCatalogSource]:
    configured = os.environ.get("COPAW_CURATED_SKILL_CATALOG_SOURCES", "").strip()
    disable_defaults = os.environ.get(
        "COPAW_CURATED_SKILL_CATALOG_DISABLE_DEFAULTS",
        "",
    ).strip().lower() in {"1", "true", "yes", "on"}
    raw_items: list[dict[str, Any]] = []
    if configured:
        try:
            decoded = json.loads(configured)
        except json.JSONDecodeError:
            decoded = []
        if isinstance(decoded, list):
            raw_items.extend(item for item in decoded if isinstance(item, dict))
    if not disable_defaults:
        raw_items.extend(item for item in _DEFAULT_SOURCES if isinstance(item, dict))
    sources: list[CuratedSkillCatalogSource] = []
    seen_ids: set[str] = set()
    for item in raw_items:
        try:
            source = CuratedSkillCatalogSource.model_validate(item)
        except ValidationError:
            continue
        if source.source_id in seen_ids:
            continue
        seen_ids.add(source.source_id)
        sources.append(source)
    return sources


def search_curated_skill_catalog(
    query: str = "",
    *,
    limit: int = 20,
) -> CuratedSkillCatalogSearchResponse:
    normalized_query = " ".join(str(query or "").strip().split())
    normalized_limit = max(1, min(int(limit), 500))
    warnings: list[str] = []
    if normalized_query:
        source = _dynamic_query_source(normalized_query, limit=normalized_limit)
        items, source_warnings = _load_source_entries(source)
        warnings.extend(source_warnings)
        return CuratedSkillCatalogSearchResponse(
            sources=[source],
            items=items[:normalized_limit],
            total=len(items),
            warnings=_unique_strings(warnings),
        )

    sources = list_curated_skill_sources()
    aggregated: list[CuratedSkillCatalogEntry] = []
    seen_keys: set[str] = set()
    for source in sources:
        source_items, source_warnings = _load_source_entries(source)
        warnings.extend(source_warnings)
        for item in source_items:
            key = _entry_key(item)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            aggregated.append(item)
    return CuratedSkillCatalogSearchResponse(
        sources=sources,
        items=aggregated[:normalized_limit],
        total=len(aggregated),
        warnings=_unique_strings(warnings),
    )


def get_curated_skill_catalog_entry(
    source_id: str,
    candidate_id: str,
) -> CuratedSkillCatalogEntry | None:
    source = _find_source(source_id)
    if source is None:
        return None
    items, _warnings = _load_source_entries(source)
    for item in items:
        if item.candidate_id == candidate_id:
            return item
    return None


def _find_source(source_id: str) -> CuratedSkillCatalogSource | None:
    for source in list_curated_skill_sources():
        if source.source_id == source_id:
            return source
    if source_id.startswith("skillhub-search:"):
        query = unquote(source_id.split(":", 1)[1]).strip()
        return _dynamic_query_source(query, limit=12)
    return None


def _dynamic_query_source(query: str, *, limit: int) -> CuratedSkillCatalogSource:
    normalized_query = " ".join(query.strip().split())
    return CuratedSkillCatalogSource(
        source_id=f"skillhub-search:{quote(normalized_query, safe='')}",
        label="SkillHub 精选检索",
        source_kind="skillhub-curated",
        query=normalized_query,
        max_items=max(6, min(max(1, limit), 200)),
        notes=["按当前检索词从 SkillHub 商店挑选高相关技能包。"],
    )


def _load_source_entries(
    source: CuratedSkillCatalogSource,
) -> tuple[list[CuratedSkillCatalogEntry], list[str]]:
    cache_key = _source_cache_key(source)
    cached = _CATALOG_CACHE.get(cache_key)
    now = datetime.now(timezone.utc)
    if cached is not None and cached[0] >= now:
        return list(cached[1]), list(cached[2])
    try:
        results = search_skillhub_skills(source.query, limit=source.max_items)
    except Exception as exc:
        warnings = [f"{source.label} 当前不可用：{exc}"]
        _CATALOG_CACHE[cache_key] = (
            now + _CACHE_TTL,
            [],
            warnings,
        )
        return [], warnings

    installable_results: list[SkillHubSearchResult] = []
    suppressed_count = 0
    for item in results:
        bundle_url = str(item.source_url or "").strip()
        if not bundle_url or not skillhub_bundle_is_installable(bundle_url):
            suppressed_count += 1
            continue
        installable_results.append(item)

    entries = _entries_from_skillhub_results(source, installable_results)
    warnings: list[str] = []
    if suppressed_count > 0:
        warnings.append(
            f"{source.label} 已抑制 {suppressed_count} 个不可安装的 SkillHub bundle 结果。",
        )
    _CATALOG_CACHE[cache_key] = (
        now + _CACHE_TTL,
        list(entries),
        list(warnings),
    )
    return entries, warnings


def _entries_from_skillhub_results(
    source: CuratedSkillCatalogSource,
    results: list[SkillHubSearchResult],
) -> list[CuratedSkillCatalogEntry]:
    entries: list[tuple[float, CuratedSkillCatalogEntry]] = []
    seen_keys: set[str] = set()
    for result in results:
        candidate_id = _slugify(result.slug or result.name or result.source_url)
        if not candidate_id:
            continue
        entry = CuratedSkillCatalogEntry(
            candidate_id=candidate_id,
            source_id=source.source_id,
            source_label=source.label or present_remote_skill_source_label(curated=True),
            source_kind="skillhub-curated",
            source_repo_url=_DEFAULT_CATALOG_URL,
            discovery_kind=(
                "skillhub-search"
                if source.source_id.startswith("skillhub-search:")
                else "skillhub-preset"
            ),
            manifest_status="skillhub-curated",
            title=present_remote_skill_name(
                slug=result.slug,
                name=result.name,
                summary=result.description,
                curated=True,
            ),
            description=present_remote_skill_summary(
                slug=result.slug,
                name=result.name,
                summary=result.description,
            ),
            bundle_url=result.source_url,
            version=result.version,
            install_name=_slugify(result.slug or result.name),
            capability_tags=_unique_strings(
                ["skill", "hub", "remote", "skillhub-curated"],
            ),
            review_required=False,
            review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
            review_notes=_unique_strings(list(source.notes or [])),
            routes={
                "catalog": (
                    f"/api/capability-market/curated-catalog?q={quote(source.query)}"
                    if source.query
                    else "/api/capability-market/curated-catalog"
                ),
                "hub_search": (
                    f"/api/capability-market/hub/search?q={quote(source.query)}"
                    if source.query
                    else "/api/capability-market/hub/search?q="
                ),
                "source": result.source_url,
            },
        )
        key = _entry_key(entry)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        entries.append((float(result.score or 0.0), entry))
    entries.sort(key=lambda item: (-item[0], item[1].title.lower()))
    return [entry for _score, entry in entries]


def _entry_key(item: CuratedSkillCatalogEntry) -> str:
    return (item.bundle_url or item.candidate_id or item.title).strip().lower()


def _slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in normalized)
    normalized = "-".join(part for part in normalized.split("-") if part)
    if normalized:
        return normalized
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _source_cache_key(source: CuratedSkillCatalogSource) -> str:
    payload = source.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def _unique_strings(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                items.append(normalized)
            continue
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                items.append(normalized)
    return items
