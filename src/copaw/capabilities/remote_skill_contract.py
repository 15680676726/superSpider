# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable, Literal
from urllib.parse import quote, urlparse

from pydantic import BaseModel, ConfigDict, Field

from ..agents.skills_hub import HubSkillResult, search_hub_skills
from .remote_skill_catalog import (
    CuratedSkillCatalogEntry,
    get_curated_skill_catalog_entry,
    list_curated_skill_sources,
    search_curated_skill_catalog,
)

_BUSINESS_AGENT_EXTRA_CAPABILITY_LIMIT = 12


class RemoteSkillCandidate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    candidate_key: str
    source_kind: Literal["curated", "hub"]
    source_label: str
    title: str
    description: str = ""
    bundle_url: str
    source_url: str = ""
    source_id: str | None = None
    candidate_id: str | None = None
    slug: str | None = None
    version: str = ""
    install_name: str = ""
    capability_ids: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    review_required: bool = False
    review_summary: str = ""
    review_notes: list[str] = Field(default_factory=list)
    manifest_status: str = ""
    installed: bool = False
    installed_capability_ids: list[str] = Field(default_factory=list)
    search_query: str = ""
    routes: dict[str, str] = Field(default_factory=dict)


class RemoteSkillPreflightCheck(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str
    label: str
    status: Literal["pass", "warn", "fail"] = "pass"
    detail: str = ""


class RemoteSkillTrialPlan(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    target_agent_id: str | None = None
    capability_assignment_mode: Literal["merge", "replace"] = "merge"
    predicted_capability_ids: list[str] = Field(default_factory=list)
    replacement_capability_ids: list[str] = Field(default_factory=list)
    rollout_scope: Literal["single-agent"] = "single-agent"


class RemoteSkillPreflightReport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    ready: bool = False
    risk_level: Literal["guarded", "confirm"] = "guarded"
    summary: str = ""
    review_required: bool = False
    checks: list[RemoteSkillPreflightCheck] = Field(default_factory=list)
    trial_plan: RemoteSkillTrialPlan | None = None


def search_allowlisted_remote_skill_candidates(
    query: str,
    *,
    limit: int = 8,
    include_curated: bool = True,
    include_hub: bool = True,
    get_capability_fn: Callable[[str], object | None] | None = None,
) -> list[RemoteSkillCandidate]:
    normalized_query = query.strip()
    if not normalized_query:
        return []
    candidates: list[RemoteSkillCandidate] = []
    seen: set[str] = set()
    if include_curated:
        response = search_curated_skill_catalog(normalized_query, limit=limit)
        for item in response.items:
            candidate = _candidate_from_curated(
                item,
                query=normalized_query,
                get_capability_fn=get_capability_fn,
            )
            if candidate.candidate_key in seen:
                continue
            seen.add(candidate.candidate_key)
            candidates.append(candidate)
    if include_hub:
        for item in search_hub_skills(normalized_query, limit=limit):
            candidate = _candidate_from_hub(
                item,
                query=normalized_query,
                get_capability_fn=get_capability_fn,
            )
            if candidate is None or candidate.candidate_key in seen:
                continue
            seen.add(candidate.candidate_key)
            candidates.append(candidate)
    candidates.sort(
        key=lambda item: (
            item.source_kind != "curated",
            item.review_required,
            not item.installed,
            item.manifest_status not in {"verified", "skillhub-curated"},
            item.title.lower(),
        ),
    )
    return candidates[: max(1, limit)]


def resolve_remote_skill_candidate(
    payload: dict[str, Any] | None,
    *,
    get_capability_fn: Callable[[str], object | None] | None = None,
) -> RemoteSkillCandidate | None:
    source_kind = str((payload or {}).get("source_kind") or "").strip().lower()
    if source_kind == "curated":
        source_id = str((payload or {}).get("source_id") or "").strip()
        candidate_id = str((payload or {}).get("candidate_id") or "").strip()
        if not source_id or not candidate_id:
            return None
        entry = get_curated_skill_catalog_entry(source_id, candidate_id)
        if entry is None:
            return None
        return _candidate_from_curated(
            entry,
            query=str((payload or {}).get("search_query") or ""),
            get_capability_fn=get_capability_fn,
        )
    if source_kind != "hub":
        return None
    bundle_url = str((payload or {}).get("bundle_url") or "").strip()
    if not bundle_url or not _is_allowlisted_remote_url(bundle_url):
        return None
    source_url = str((payload or {}).get("source_url") or bundle_url).strip()
    slug = str((payload or {}).get("slug") or "").strip() or None
    install_name = str((payload or {}).get("install_name") or "").strip()
    capability_ids = _unique_strings(
        list((payload or {}).get("capability_ids") or []),
        [_skill_capability_id(install_name)] if install_name else [],
    )
    installed_capability_ids = _existing_capability_ids(
        capability_ids,
        get_capability_fn=get_capability_fn,
    )
    return RemoteSkillCandidate(
        candidate_key=f"hub:{slug or bundle_url}",
        source_kind="hub",
        source_label=str((payload or {}).get("source_label") or "SkillHub 商店"),
        title=str((payload or {}).get("title") or slug or bundle_url),
        description=str((payload or {}).get("description") or ""),
        bundle_url=bundle_url,
        source_url=source_url,
        slug=slug,
        version=str((payload or {}).get("version") or ""),
        install_name=install_name,
        capability_ids=capability_ids,
        capability_tags=_unique_strings(list((payload or {}).get("capability_tags") or []), ["skill", "hub", "remote"]),
        review_required=bool((payload or {}).get("review_required", False)),
        review_summary=str((payload or {}).get("review_summary") or ""),
        review_notes=_string_list((payload or {}).get("review_notes")),
        installed=bool(installed_capability_ids),
        installed_capability_ids=installed_capability_ids,
        search_query=str((payload or {}).get("search_query") or ""),
        routes=_string_dict((payload or {}).get("routes")),
    )


def resolve_candidate_capability_ids(
    candidate: RemoteSkillCandidate,
    *,
    installed_name: str = "",
    requested_capability_ids: list[str] | None = None,
) -> list[str]:
    normalized_requested = _unique_strings(list(requested_capability_ids or []))
    if normalized_requested:
        return normalized_requested
    if installed_name.strip():
        return [_skill_capability_id(installed_name)]
    if candidate.installed_capability_ids:
        return list(candidate.installed_capability_ids)
    if candidate.capability_ids:
        return list(candidate.capability_ids)
    if candidate.install_name:
        return [_skill_capability_id(candidate.install_name)]
    return []


def build_remote_skill_preflight(
    *,
    candidate: RemoteSkillCandidate,
    target_agent_id: str | None,
    capability_assignment_mode: Literal["merge", "replace"],
    replacement_capability_ids: list[str] | None = None,
    requested_capability_ids: list[str] | None = None,
    get_capability_fn: Callable[[str], object | None] | None = None,
    agent_profile_service: object | None = None,
) -> RemoteSkillPreflightReport:
    checks: list[RemoteSkillPreflightCheck] = []
    predicted_capability_ids = resolve_candidate_capability_ids(
        candidate,
        requested_capability_ids=requested_capability_ids,
    )
    replacement_ids = _unique_strings(list(replacement_capability_ids or []))

    source_allowed = _is_allowlisted_remote_url(candidate.bundle_url)
    checks.append(
        RemoteSkillPreflightCheck(
            code="source-allowlist",
            label="Allowlisted source",
            status="pass" if source_allowed else "fail",
            detail=(
                f"Candidate source '{candidate.bundle_url}' is allowlisted."
                if source_allowed
                else f"Candidate source '{candidate.bundle_url}' is outside the allowlist."
            ),
        ),
    )

    target_agent = _get_agent(agent_profile_service, target_agent_id)
    if target_agent_id:
        checks.append(
            RemoteSkillPreflightCheck(
                code="target-agent",
                label="目标智能体",
                status="pass" if target_agent is not None else "fail",
                detail=(
                    f"目标智能体“{target_agent_id}”可用。"
                    if target_agent is not None
                    else f"目标智能体“{target_agent_id}”不可用。"
                ),
            ),
        )

    if predicted_capability_ids:
        checks.append(
            RemoteSkillPreflightCheck(
                code="capability-resolution",
                label="能力解析",
                status="pass",
                detail="试装会通过已安装的技能包解析能力 ID。",
            ),
        )
    else:
        checks.append(
            RemoteSkillPreflightCheck(
                code="capability-resolution",
                label="能力解析",
                status="warn",
                detail="该候选项还没有显式声明能力 ID，系统会在安装后再自动识别。",
            ),
        )

    if replacement_ids:
        missing_replacement_ids = [
            capability_id
            for capability_id in replacement_ids
            if get_capability_fn is not None and get_capability_fn(capability_id) is None
        ]
        checks.append(
            RemoteSkillPreflightCheck(
                code="replacement-capability",
                label="Replacement target",
                status="pass" if not missing_replacement_ids else "fail",
                detail=(
                    "Replacement target capability is available."
                    if not missing_replacement_ids
                    else "Replacement capability is missing: "
                    + ", ".join(sorted(missing_replacement_ids))
                ),
            ),
        )

    budget_check = _budget_check(
        agent_profile_service=agent_profile_service,
        target_agent_id=target_agent_id,
        capability_assignment_mode=capability_assignment_mode,
        predicted_capability_ids=predicted_capability_ids,
        replacement_capability_ids=replacement_ids,
    )
    if budget_check is not None:
        checks.append(budget_check)

    risk_level: Literal["guarded", "confirm"] = (
        "confirm" if candidate.review_required or replacement_ids else "guarded"
    )
    ready = all(item.status != "fail" for item in checks)
    summary_parts: list[str] = []
    if candidate.review_required:
        summary_parts.append(candidate.review_summary or "该候选项需要人工审查。")
    if replacement_ids:
        summary_parts.append("试装会先在单个智能体上替换当前能力。")
    else:
        summary_parts.append("试装会被限制在单个智能体内。")
    if not ready:
        summary_parts.append("预检发现阻塞问题，需要先处理后再继续。")
    return RemoteSkillPreflightReport(
        ready=ready,
        risk_level=risk_level,
        summary=" ".join(part.strip() for part in summary_parts if part.strip()),
        review_required=candidate.review_required,
        checks=checks,
        trial_plan=RemoteSkillTrialPlan(
            target_agent_id=target_agent_id,
            capability_assignment_mode=capability_assignment_mode,
            predicted_capability_ids=predicted_capability_ids,
            replacement_capability_ids=replacement_ids,
        ),
    )


def _candidate_from_curated(
    item: CuratedSkillCatalogEntry,
    *,
    query: str,
    get_capability_fn: Callable[[str], object | None] | None = None,
) -> RemoteSkillCandidate:
    resolved_capability_ids = _unique_strings(
        [_skill_capability_id(item.install_name)] if item.install_name else [],
    )
    installed_capability_ids = _existing_capability_ids(
        resolved_capability_ids,
        get_capability_fn=get_capability_fn,
    )
    return RemoteSkillCandidate(
        candidate_key=f"curated:{item.source_id}:{item.candidate_id}",
        source_kind="curated",
        source_label=item.source_label,
        title=item.title,
        description=item.description,
        bundle_url=item.bundle_url,
        source_url=item.source_repo_url,
        source_id=item.source_id,
        candidate_id=item.candidate_id,
        version=item.version,
        install_name=item.install_name,
        capability_ids=resolved_capability_ids,
        capability_tags=_unique_strings(list(item.capability_tags or []), ["curated"]),
        review_required=bool(item.review_required),
        review_summary=item.review_summary,
        review_notes=_string_list(item.review_notes),
        manifest_status=item.manifest_status,
        installed=bool(installed_capability_ids),
        installed_capability_ids=installed_capability_ids,
        search_query=query,
        routes={
            **_string_dict(item.routes),
            "catalog": (
                f"/api/capability-market/curated-catalog?q={quote(query)}"
                if query
                else "/api/capability-market/curated-catalog"
            ),
        },
    )


def _candidate_from_hub(
    item: HubSkillResult,
    *,
    query: str,
    get_capability_fn: Callable[[str], object | None] | None = None,
) -> RemoteSkillCandidate | None:
    bundle_url = str(item.source_url or "").strip()
    if not bundle_url or not _is_allowlisted_remote_url(bundle_url):
        return None
    install_name = _guess_hub_install_name(item)
    predicted_capability_ids = (
        [_skill_capability_id(install_name)]
        if install_name
        else []
    )
    installed_capability_ids = _existing_capability_ids(
        predicted_capability_ids,
        get_capability_fn=get_capability_fn,
    )
    return RemoteSkillCandidate(
        candidate_key=f"hub:{item.slug or bundle_url}",
        source_kind="hub",
        source_label=str(item.source_label or "SkillHub 商店"),
        title=item.name,
        description=item.description,
        bundle_url=bundle_url,
        source_url=bundle_url,
        slug=item.slug,
        version=item.version,
        install_name=install_name,
        capability_ids=predicted_capability_ids,
        capability_tags=["skill", "hub", "remote"],
        review_required=False,
        installed=bool(installed_capability_ids),
        installed_capability_ids=installed_capability_ids,
        search_query=query,
        routes={
            "hub_search": f"/api/capability-market/hub/search?q={quote(query)}",
            "source": bundle_url,
        },
    )


def _existing_capability_ids(
    capability_ids: list[str],
    *,
    get_capability_fn: Callable[[str], object | None] | None = None,
) -> list[str]:
    if get_capability_fn is None:
        return []
    return [
        capability_id
        for capability_id in capability_ids
        if get_capability_fn(capability_id) is not None
    ]


def _get_agent(agent_profile_service: object | None, agent_id: str | None) -> object | None:
    if not agent_id or agent_profile_service is None:
        return None
    getter = getattr(agent_profile_service, "get_agent", None)
    if not callable(getter):
        return None
    return getter(agent_id)


def _budget_check(
    *,
    agent_profile_service: object | None,
    target_agent_id: str | None,
    capability_assignment_mode: Literal["merge", "replace"],
    predicted_capability_ids: list[str],
    replacement_capability_ids: list[str],
) -> RemoteSkillPreflightCheck | None:
    if not target_agent_id or agent_profile_service is None:
        return None
    getter = getattr(agent_profile_service, "get_capability_surface", None)
    if not callable(getter):
        return None
    surface = getter(target_agent_id)
    if not isinstance(surface, dict):
        return None
    baseline_capability_ids = _string_list(surface.get("baseline_capabilities"))
    effective_capability_ids = _string_list(surface.get("effective_capabilities"))
    target_agent = _get_agent(agent_profile_service, target_agent_id)
    extra_limit = (
        _BUSINESS_AGENT_EXTRA_CAPABILITY_LIMIT
        if _string(getattr(target_agent, "agent_class", None)) == "business"
        else None
    )
    if extra_limit is None:
        return None
    effective_extras = {
        capability_id
        for capability_id in effective_capability_ids
        if capability_id not in baseline_capability_ids
    }
    planned_extras = set(effective_extras)
    if capability_assignment_mode == "replace":
        planned_extras.difference_update(replacement_capability_ids)
    planned_extras.update(
        capability_id
        for capability_id in predicted_capability_ids
        if capability_id not in baseline_capability_ids
    )
    over_limit_by = max(len(planned_extras) - extra_limit, 0)
    return RemoteSkillPreflightCheck(
        code="capability-budget",
        label="Capability budget",
        status="pass" if over_limit_by <= 0 else "fail",
        detail=(
            f"Planned extra capability count {len(planned_extras)}/{extra_limit} stays within budget."
            if over_limit_by <= 0
            else f"Planned extra capability count exceeds the business-agent budget by {over_limit_by}."
        ),
    )


def _is_allowlisted_remote_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().lower()
    if not host:
        return False
    return host in _allowlisted_hosts()


def _allowlisted_hosts() -> set[str]:
    hosts = {
        "github.com",
        "www.github.com",
        "skills.sh",
        "www.skills.sh",
        "lightmake.site",
        "skillhub-1388575217.cos.ap-guangzhou.myqcloud.com",
        "skillsmp.com",
        "www.skillsmp.com",
    }
    for source in list_curated_skill_sources():
        hosts.update(
            (host or "").strip().lower()
            for host in getattr(source, "allowed_bundle_hosts", []) or []
            if (host or "").strip()
        )
        repo_host = (urlparse(getattr(source, "repo_url", "") or "").hostname or "").strip().lower()
        if repo_host:
            hosts.add(repo_host)
    return hosts


def _guess_hub_install_name(item: HubSkillResult) -> str:
    slug = str(item.slug or "").strip()
    if slug:
        return slug.split("/")[-1].strip()
    return ""


def _skill_capability_id(skill_name: str) -> str:
    return f"skill:{skill_name.strip()}"


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return _unique_strings([str(item).strip() for item in value if str(item).strip()])


def _string_dict(value: object | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = _string(key)
        normalized_value = _string(item)
        if normalized_key and normalized_value:
            result[normalized_key] = normalized_value
    return result


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
            normalized = str(entry).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                items.append(normalized)
    return items
