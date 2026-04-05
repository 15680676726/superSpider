# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from ..agents.skills_hub import search_hub_skills
from ..capabilities.mcp_registry import McpRegistryCatalog
from ..capabilities.remote_skill_catalog import search_curated_skill_catalog
from .models import DiscoveryHit, OpportunityRadarItem

_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_HTTP_TIMEOUT_SECONDS = 20.0


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text(value: object | None) -> str:
    return " ".join(str(value or "").strip().split())


def _query_terms(query: str) -> tuple[str, ...]:
    seen: set[str] = set()
    items: list[str] = []
    for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", query.lower()):
        if token in seen:
            continue
        seen.add(token)
        items.append(token)
    return tuple(items)


def _direct_github_repo_query(query: str) -> tuple[str, str] | None:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return None
    parsed = urlparse(normalized_query)
    if parsed.scheme in {"http", "https"}:
        host = (parsed.netloc or "").strip().lower()
        if host not in {"github.com", "www.github.com"}:
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return None
        return parts[0], parts[1]
    match = re.fullmatch(
        r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)",
        normalized_query,
    )
    if match is None:
        return None
    return match.group("owner"), match.group("repo")


def _unique_strings(*groups: object) -> tuple[str, ...]:
    seen: set[str] = set()
    values: list[str] = []
    for group in groups:
        if isinstance(group, str):
            iterable = [group]
        else:
            iterable = list(group or [])
        for item in iterable:
            text = _string(item)
            if text is None:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            values.append(text)
    return tuple(values)


def _github_api_json(
    query: str,
    limit: int = 10,
    *,
    search_url: str | None = None,
) -> dict[str, Any]:
    request = Request(
        f"{str(search_url or '').strip() or _GITHUB_SEARCH_URL}?{urlencode({'q': _normalize_text(query), 'sort': 'stars', 'order': 'desc', 'per_page': max(1, min(int(limit), 25))})}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "copaw-donor-discovery/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if github_token:
        request.add_header("Authorization", f"Bearer {github_token}")
    with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
        payload = response.read().decode("utf-8", errors="replace")
    decoded = json.loads(payload)
    return decoded if isinstance(decoded, dict) else {}


def search_github_repository_donors(
    query: str,
    *,
    limit: int = 10,
    search_url: str | None = None,
) -> list[DiscoveryHit]:
    direct_repo = _direct_github_repo_query(query)
    if direct_repo is not None:
        owner, repo = direct_repo
        source_url = f"https://github.com/{owner}/{repo}"
        return [
            DiscoveryHit(
                source_id="github-repo",
                source_kind="github-repo",
                source_alias="github",
                candidate_kind="project",
                display_name=f"{owner}/{repo}",
                summary="GitHub donor repository",
                candidate_source_ref=source_url,
                candidate_source_version="",
                candidate_source_lineage=f"donor:github:{owner.lower()}/{repo.lower()}",
                canonical_package_id=f"pkg:github:{owner.lower()}/{repo.lower()}",
                capability_keys=_query_terms(f"{owner} {repo}"),
                metadata={
                    "provider": "github-repo",
                    "install_supported": True,
                    "repository_url": source_url,
                    "direct_query": True,
                    "materialization_strategy": "github-python-project",
                    "install_transport_chain": [
                        "git",
                        "codeload-tar-gz",
                        "github-archive-zip",
                    ],
                },
            ),
        ]
    payload = _github_api_json(query, limit=limit, search_url=search_url)
    query_tokens = _query_terms(query)
    hits: list[DiscoveryHit] = []
    for item in list(payload.get("items") or []):
        if not isinstance(item, dict):
            continue
        full_name = _normalize_text(item.get("full_name"))
        html_url = _normalize_text(item.get("html_url"))
        if not full_name or not html_url:
            continue
        default_branch = _normalize_text(item.get("default_branch")) or "main"
        topics = _unique_strings(item.get("topics") or [])
        capability_keys = _unique_strings(
            query_tokens,
            topics,
            [_normalize_text(item.get("language")).lower()] if _normalize_text(item.get("language")) else [],
        )
        stars = int(item.get("stargazers_count") or 0)
        pushed_at = _normalize_text(item.get("updated_at"))
        hits.append(
            DiscoveryHit(
                source_id="github-repo",
                source_kind="github-repo",
                source_alias="github",
                candidate_kind="project",
                display_name=full_name,
                summary=_normalize_text(item.get("description")) or "GitHub donor repository",
                candidate_source_ref=html_url,
                candidate_source_version=default_branch,
                candidate_source_lineage=f"donor:github:{full_name.lower()}",
                canonical_package_id=f"pkg:github:{full_name.lower()}",
                capability_keys=capability_keys,
                metadata={
                    "provider": "github-repo",
                    "install_supported": True,
                    "repository_url": html_url,
                    "stars": stars,
                    "topics": list(topics),
                    "updated_at": pushed_at,
                    "materialization_strategy": "github-python-project",
                    "install_transport_chain": [
                        "git",
                        "codeload-tar-gz",
                        "github-archive-zip",
                    ],
                },
            ),
        )
    return hits[: max(1, int(limit))]


def search_skillhub_discovery_hits(
    query: str,
    *,
    limit: int = 10,
    search_url: str | None = None,
) -> list[DiscoveryHit]:
    hits: list[DiscoveryHit] = []
    for item in search_hub_skills(query, limit=limit, search_url=search_url):
        slug = _string(getattr(item, "slug", None))
        source_url = _string(getattr(item, "source_url", None))
        if slug is None or source_url is None:
            continue
        hits.append(
            DiscoveryHit(
                source_id="skillhub-catalog",
                source_kind="skillhub-catalog",
                source_alias="skillhub",
                candidate_kind="skill",
                display_name=_string(getattr(item, "name", None)) or slug,
                summary=_string(getattr(item, "description", None)) or "SkillHub donor skill",
                candidate_source_ref=source_url,
                candidate_source_version=_string(getattr(item, "version", None)),
                candidate_source_lineage=f"donor:skillhub:{slug.lower()}",
                canonical_package_id=f"pkg:skillhub:{slug.lower()}",
                capability_keys=_query_terms(query),
                metadata={"provider": "skillhub-catalog", "slug": slug},
            ),
        )
    return hits[: max(1, int(limit))]


def search_curated_discovery_hits(
    query: str,
    *,
    limit: int = 10,
    search_url: str | None = None,
) -> list[DiscoveryHit]:
    response = search_curated_skill_catalog(
        query,
        limit=limit,
        skillhub_search_url=search_url,
    )
    hits: list[DiscoveryHit] = []
    for item in list(response.items or []):
        source_ref = _string(item.bundle_url)
        if source_ref is None:
            continue
        package_id = _string(item.candidate_id) or _normalize_text(item.title).lower().replace(" ", "-")
        hits.append(
            DiscoveryHit(
                source_id="skillhub-curated",
                source_kind="skillhub-curated",
                source_alias=_string(item.source_id) or "curated",
                candidate_kind="skill",
                display_name=_string(item.title) or package_id,
                summary=_string(item.description) or "Curated donor skill",
                candidate_source_ref=source_ref,
                candidate_source_version=_string(item.version),
                candidate_source_lineage=f"donor:curated:{package_id.lower()}",
                canonical_package_id=f"pkg:curated:{package_id.lower()}",
                capability_keys=_unique_strings(item.capability_tags, _query_terms(query)),
                metadata={
                    "provider": "skillhub-curated",
                    "source_id": item.source_id,
                    "candidate_id": item.candidate_id,
                },
            ),
        )
    return hits[: max(1, int(limit))]


def search_mcp_registry_discovery_hits(
    query: str,
    *,
    limit: int = 10,
    base_url: str | None = None,
) -> list[DiscoveryHit]:
    catalog = McpRegistryCatalog(base_url=base_url)
    response = catalog.list_catalog(query=query, limit=limit)
    hits: list[DiscoveryHit] = []
    for item in list(response.items or []):
        server_name = _string(item.server_name)
        source_ref = _string(item.source_url)
        if server_name is None or source_ref is None:
            continue
        hits.append(
            DiscoveryHit(
                source_id="mcp-registry",
                source_kind="mcp-registry",
                source_alias="official-mcp-registry",
                candidate_kind="mcp-bundle",
                display_name=_string(item.title) or server_name,
                summary=_string(item.description) or "Official MCP registry package",
                candidate_source_ref=source_ref,
                candidate_source_version=_string(item.version),
                candidate_source_lineage=f"donor:mcp-registry:{server_name.lower()}",
                canonical_package_id=f"pkg:mcp-registry:{server_name.lower()}",
                capability_keys=_unique_strings(item.category_keys, item.transport_types, _query_terms(query)),
                metadata={
                    "provider": "mcp-registry",
                    "server_name": server_name,
                    "install_supported": bool(item.install_supported),
                },
            ),
        )
    return hits[: max(1, int(limit))]


def github_opportunity_radar_items(
    queries: list[str] | tuple[str, ...],
    *,
    per_query_limit: int = 2,
) -> list[OpportunityRadarItem]:
    items: list[OpportunityRadarItem] = []
    for query in list(queries or []):
        for hit in search_github_repository_donors(query, limit=per_query_limit):
            updated_at_raw = _string(hit.metadata.get("updated_at")) if isinstance(hit.metadata, dict) else None
            try:
                published_at = (
                    datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
                    if updated_at_raw
                    else datetime.now(timezone.utc)
                )
            except ValueError:
                published_at = datetime.now(timezone.utc)
            score = float(hit.metadata.get("stars") or 0.0) if isinstance(hit.metadata, dict) else 0.0
            items.append(
                OpportunityRadarItem(
                    item_id=_string(hit.canonical_package_id) or _string(hit.candidate_source_ref) or "github-item",
                    title=_string(hit.display_name) or "GitHub donor",
                    summary=hit.summary,
                    canonical_package_id=hit.canonical_package_id,
                    source_ref=hit.candidate_source_ref,
                    ecosystem="github",
                    score=score,
                    published_at=published_at,
                    capability_keys=hit.capability_keys,
                    query_hint=query,
                    metadata=dict(hit.metadata),
                ),
            )
    return items


def mcp_registry_opportunity_radar_items(
    queries: list[str] | tuple[str, ...],
    *,
    per_query_limit: int = 2,
) -> list[OpportunityRadarItem]:
    items: list[OpportunityRadarItem] = []
    for query in list(queries or []):
        for hit in search_mcp_registry_discovery_hits(query, limit=per_query_limit):
            items.append(
                OpportunityRadarItem(
                    item_id=_string(hit.canonical_package_id) or _string(hit.candidate_source_ref) or "mcp-item",
                    title=_string(hit.display_name) or "MCP donor",
                    summary=hit.summary,
                    canonical_package_id=hit.canonical_package_id,
                    source_ref=hit.candidate_source_ref,
                    ecosystem="mcp-registry",
                    score=1.0,
                    published_at=datetime.now(timezone.utc),
                    capability_keys=hit.capability_keys,
                    query_hint=query,
                    metadata=dict(hit.metadata),
                ),
            )
    return items


__all__ = [
    "github_opportunity_radar_items",
    "mcp_registry_opportunity_radar_items",
    "search_curated_discovery_hits",
    "search_github_repository_donors",
    "search_mcp_registry_discovery_hits",
    "search_skillhub_discovery_hits",
]
