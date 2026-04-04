# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import sys
from typing import Any
from urllib.parse import quote

from ..agents.skills_hub import HubSkillResult, search_hub_skills
from ..config import load_config
from ..config.config import MCPClientConfig
from ..industry.models import (
    IndustryCapabilityRecommendation,
    IndustryProfile,
    IndustryRoleBlueprint,
)
from ..industry.service_recommendation_pack import (
    _install_template_capability_ids,
    _install_template_default_ref,
    _install_template_gap_notes,
    _install_template_recommendation_satisfied,
)
from ..industry.service_recommendation_search import (
    _build_browser_match_signals,
    _build_curated_match_signals,
    _build_desktop_match_signals,
    _build_hub_match_signals,
    _build_recommendation_reason_notes,
    _build_skillhub_query_candidates,
    _curated_entry_key,
    _fallback_query_signals,
    _hub_result_key,
    _matched_capability_family_ids,
    _recommendation_capability_families,
    _remote_skill_matches_guardrails,
    _expand_role_capability_family_ids,
    _role_capability_family_ids,
    _search_blob,
    _skill_capability_id,
    _string,
    _unique_strings,
)
from .mcp_registry import McpRegistryCatalog
from ..state import SQLiteStateStore
from .browser_runtime import BrowserRuntimeService
from .install_templates import list_install_templates
from .recommendation_builders import build_remote_skill_recommendation
from .remote_skill_catalog import CuratedSkillCatalogEntry, search_curated_skill_catalog
from .remote_skill_contract import (
    RemoteSkillCandidate,
    resolve_candidate_capability_ids,
    search_allowlisted_remote_skill_candidates,
)

_REMOTE_RECOMMENDATION_ROLE_LIMIT = 12
_CURATED_RECOMMENDATION_MATCHES_PER_ROLE = 4
_HUB_RECOMMENDATION_MATCHES_PER_ROLE = 5
_CURATED_RECOMMENDATION_MAX_ITEMS = 12
_HUB_RECOMMENDATION_MAX_ITEMS = 16
_MCP_REGISTRY_RECOMMENDATION_MATCHES_PER_ROLE = 4
_MCP_REGISTRY_RECOMMENDATION_MAX_ITEMS = 12
_MCP_REGISTRY_QUERY_MAX_ITEMS = 8
_NATIVE_SEARCH_HUB_SKILLS = search_hub_skills
_NATIVE_SEARCH_CURATED_SKILL_CATALOG = search_curated_skill_catalog
_NATIVE_SEARCH_ALLOWLISTED_REMOTE_SKILL_CANDIDATES = (
    search_allowlisted_remote_skill_candidates
)
_MCP_REGISTRY_FAMILY_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    "browser": ("browser", "search"),
    "research": ("search", "data"),
    "workflow": ("automation", "developer"),
    "content": ("communication", "data"),
    "image": ("ai", "data"),
    "data": ("data", "database"),
    "crm": ("communication", "data"),
    "email": ("communication",),
    "github": ("developer",),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_industry_discovery_attr(
    name: str,
    default: object,
    native_default: object,
) -> object:
    facade = sys.modules.get("copaw.industry.service")
    if facade is not None:
        facade_value = getattr(facade, name, default)
        if default is native_default or facade_value is not native_default:
            return facade_value
    return default


def _get_prediction_discovery_attr(
    name: str,
    default: object,
    native_default: object,
) -> object:
    facade = sys.modules.get("copaw.predictions.service")
    if facade is not None:
        facade_value = getattr(facade, name, default)
        if default is native_default or facade_value is not native_default:
            return facade_value
    return default


def _hub_recommendation_output_limit(target_roles: list[IndustryRoleBlueprint]) -> int:
    return max(6, min(_HUB_RECOMMENDATION_MAX_ITEMS, max(1, len(target_roles)) * 3))


def _curated_recommendation_output_limit(
    target_roles: list[IndustryRoleBlueprint],
) -> int:
    return max(
        4,
        min(_CURATED_RECOMMENDATION_MAX_ITEMS, max(1, len(target_roles)) * 3),
    )


def _mcp_registry_recommendation_output_limit(
    target_roles: list[IndustryRoleBlueprint],
) -> int:
    return max(
        4,
        min(_MCP_REGISTRY_RECOMMENDATION_MAX_ITEMS, max(1, len(target_roles)) * 3),
    )


def _list(value: object | None) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _governance_path_for_recommendation(
    *,
    install_kind: str,
    installed: bool,
    review_required: bool,
    action_kind: str | None = None,
) -> list[str]:
    lifecycle_action = "system:apply_capability_lifecycle"
    if install_kind == "hub-skill":
        path: list[str] = []
        if review_required:
            path.append("review")
        if not installed:
            path.append("system:install_hub_skill")
        path.append(lifecycle_action)
        return path
    if install_kind == "mcp-registry":
        selected_action = (
            action_kind
            or ("system:create_mcp_client" if not installed else lifecycle_action)
        )
        path = ["official-mcp-registry", selected_action]
        if selected_action != lifecycle_action:
            path.append(lifecycle_action)
        return path
    if install_kind == "builtin-runtime":
        return ["runtime-ready", lifecycle_action]
    return ["install-template", lifecycle_action]


@dataclass(slots=True)
class _RemoteRecommendationAccumulator:
    per_role_match_limit: int
    family_coverage_target: int
    aggregated: dict[str, dict[str, object]] = field(default_factory=dict)
    accepted_keys: set[str] = field(default_factory=set)
    accepted_families: set[str] = field(default_factory=set)

    def accepts(
        self,
        *,
        key: str,
        candidate_family: str | None,
    ) -> bool:
        if key in self.accepted_keys:
            return True
        if len(self.accepted_keys) < self.per_role_match_limit:
            return True
        return candidate_family is not None and candidate_family not in self.accepted_families

    def merge(
        self,
        *,
        key: str,
        seed_entry: dict[str, object],
        role: IndustryRoleBlueprint,
        signals: list[str],
        query: str,
        candidate_family: str | None,
        matched_families: list[str],
    ) -> dict[str, object]:
        resolved_families = _unique_strings(
            [candidate_family] if candidate_family is not None else [],
            matched_families,
        )
        entry = self.aggregated.get(key)
        if entry is None:
            entry = {
                **dict(seed_entry),
                "matched_roles": [(role, signals)],
                "matched_families": resolved_families,
                "queries": [query],
                "signals": list(signals),
            }
            self.aggregated[key] = entry
        else:
            matched_roles = list(entry.get("matched_roles") or [])
            matched_roles.append((role, signals))
            entry["matched_roles"] = matched_roles
            entry["queries"] = _unique_strings(
                list(entry.get("queries") or []),
                [query],
            )
            entry["signals"] = _unique_strings(
                list(entry.get("signals") or []),
                signals,
            )
            entry["matched_families"] = _unique_strings(
                list(entry.get("matched_families") or []),
                resolved_families,
            )
        self.accepted_keys.add(key)
        if candidate_family is not None:
            self.accepted_families.add(candidate_family)
        return entry

    def is_saturated(self) -> bool:
        return (
            len(self.accepted_keys) >= self.per_role_match_limit
            and len(self.accepted_families) >= self.family_coverage_target
        )


def _build_remote_recommendation_role_inputs(
    *,
    profile: IndustryProfile,
    role: IndustryRoleBlueprint,
    goal_context_by_agent: dict[str, list[str]],
) -> tuple[list[str], list[str], list[Any], int]:
    goal_context = goal_context_by_agent.get(role.agent_id, [])
    role_family_ids = _expand_role_capability_family_ids(
        role=role,
        goal_context=goal_context,
        family_ids=_role_capability_family_ids(
            profile=profile,
            role=role,
            goal_context=goal_context,
        ),
    )
    query_candidates = _build_skillhub_query_candidates(
        profile=profile,
        role=role,
        goal_context=goal_context,
    )
    family_coverage_target = min(len(role_family_ids[:4]), 3)
    return goal_context, role_family_ids, query_candidates, family_coverage_target


class CapabilityDiscoveryService:
    """Shared discovery kernel for role recommendations and capability-gap search."""

    def __init__(
        self,
        *,
        capability_service: object | None = None,
        agent_profile_service: object | None = None,
        state_store: SQLiteStateStore | None = None,
    ) -> None:
        self._capability_service = capability_service
        self._agent_profile_service = agent_profile_service
        self._state_store = state_store
        self._fixed_sop_service: object | None = None
        self._browser_runtime_service: BrowserRuntimeService | None = None
        self._mcp_registry_catalog: object | None = None
        self._hub_search_cache: dict[
            tuple[str, int],
            tuple[datetime, list[HubSkillResult]],
        ] = {}

    def set_capability_service(self, capability_service: object | None) -> None:
        self._capability_service = capability_service

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_state_store(self, state_store: SQLiteStateStore | None) -> None:
        self._state_store = state_store
        self._browser_runtime_service = None

    def set_fixed_sop_service(self, fixed_sop_service: object | None) -> None:
        self._fixed_sop_service = fixed_sop_service

    def set_mcp_registry_catalog(self, mcp_registry_catalog: object | None) -> None:
        self._mcp_registry_catalog = mcp_registry_catalog

    def _get_mcp_registry_catalog(self) -> object | None:
        catalog = self._mcp_registry_catalog
        if catalog is not None and all(
            callable(getattr(catalog, attr, None))
            for attr in ("list_catalog", "get_catalog_detail", "materialize_install_plan")
        ):
            return catalog
        catalog = McpRegistryCatalog()
        self._mcp_registry_catalog = catalog
        return catalog

    def _load_installed_mcp_clients(self) -> dict[str, MCPClientConfig]:
        try:
            raw_clients = dict(load_config().mcp.clients or {})
        except Exception:
            return {}
        installed: dict[str, MCPClientConfig] = {}
        for key, value in raw_clients.items():
            normalized_key = _string(key)
            if not normalized_key:
                continue
            try:
                installed[normalized_key] = (
                    value
                    if isinstance(value, MCPClientConfig)
                    else MCPClientConfig.model_validate(value)
                )
            except Exception:
                continue
        return installed

    def _find_installed_registry_client(
        self,
        *,
        server_name: str,
        installed_clients: dict[str, MCPClientConfig],
    ) -> tuple[str, MCPClientConfig] | None:
        for client_key, client in installed_clients.items():
            registry = getattr(client, "registry", None)
            if registry is None:
                continue
            if _string(getattr(registry, "server_name", None)) == server_name:
                return client_key, client
        return None

    def _mcp_registry_categories_for_family_ids(
        self,
        family_ids: list[str],
    ) -> list[str]:
        categories: list[str] = []
        for family_id in family_ids:
            categories.extend(_MCP_REGISTRY_FAMILY_CATEGORY_MAP.get(family_id, ()))
        return _unique_strings(categories)[:3]

    def _mcp_registry_option_is_auto_ready(
        self,
        option: object,
        *,
        existing_client: MCPClientConfig | None = None,
    ) -> bool:
        if existing_client is not None and getattr(existing_client, "registry", None) is not None:
            return True
        input_fields = list(getattr(option, "input_fields", []) or [])
        for field in input_fields:
            if not bool(getattr(field, "required", False)):
                continue
            if getattr(field, "default_value", None) not in (None, ""):
                continue
            return False
        return True

    def _select_mcp_registry_install_option(
        self,
        detail: object,
        *,
        existing_client: MCPClientConfig | None = None,
    ) -> object | None:
        options = [
            option
            for option in list(getattr(detail, "install_options", []) or [])
            if bool(getattr(option, "supported", False))
        ]
        if not options:
            return None
        existing_option_key = (
            _string(getattr(getattr(existing_client, "registry", None), "option_key", None))
            if existing_client is not None
            else ""
        )
        if existing_option_key:
            matched = next(
                (option for option in options if _string(getattr(option, "key", None)) == existing_option_key),
                None,
            )
            if matched is not None:
                return matched
        return next(
            (
                option
                for option in options
                if self._mcp_registry_option_is_auto_ready(
                    option,
                    existing_client=existing_client,
                )
            ),
            None,
        )

    def _build_mcp_registry_queries(
        self,
        *,
        profile: IndustryProfile,
        role: IndustryRoleBlueprint,
        goal_context: list[str],
    ) -> list[str]:
        candidates = _build_skillhub_query_candidates(
            profile=profile,
            role=role,
            goal_context=goal_context,
        )
        preferred = [
            candidate.query
            for candidate in candidates
            if candidate.kind in {"explicit", "role", "goal", "profile", "family"}
        ]
        return _unique_strings(preferred)[:4]

    def _get_browser_runtime_service(self) -> BrowserRuntimeService | None:
        if self._browser_runtime_service is None and self._state_store is not None:
            self._browser_runtime_service = BrowserRuntimeService(self._state_store)
        return self._browser_runtime_service

    def _build_install_template_discovery_queries(
        self,
        *,
        template_id: str,
        profile: IndustryProfile,
        matched_roles: list[tuple[IndustryRoleBlueprint, list[str]]],
        goal_context_by_agent: dict[str, list[str]],
    ) -> list[str]:
        if template_id != "browser-local":
            return []
        queries: list[str] = []
        for role, _signals in matched_roles:
            candidates = _build_skillhub_query_candidates(
                profile=profile,
                role=role,
                goal_context=goal_context_by_agent.get(role.agent_id, []),
            )
            preferred_queries = [
                candidate.query
                for candidate in candidates
                if candidate.kind in {"role", "goal", "profile"}
            ]
            family_queries = [
                candidate.query
                for candidate in candidates
                if candidate.kind == "family"
            ]
            queries.extend(preferred_queries[:2] or family_queries[:1])
            if len(queries) >= 4:
                break
        return _unique_strings(queries)[:4]

    def build_install_template_recommendations(
        self,
        *,
        profile: IndustryProfile,
        target_roles: list[IndustryRoleBlueprint],
        goal_context_by_agent: dict[str, list[str]],
    ) -> list[IndustryCapabilityRecommendation]:
        items: list[IndustryCapabilityRecommendation] = []
        browser_runtime_service = self._get_browser_runtime_service()
        for template in list_install_templates(
            capability_service=self._capability_service,
            browser_runtime_service=browser_runtime_service,
            include_runtime=False,
        ):
            template_id = str(template.id or "").strip()
            capability_ids = _install_template_capability_ids(template)
            if not capability_ids:
                continue
            matched_roles: list[tuple[IndustryRoleBlueprint, list[str]]] = []
            for role in target_roles:
                goal_context = goal_context_by_agent.get(role.agent_id, [])
                if template_id == "desktop-windows":
                    signals = _build_desktop_match_signals(
                        role=role,
                        goal_context=goal_context,
                        client_key=str(template.default_client_key or "").strip(),
                        template_tags=list(template.capability_tags or []),
                    )
                elif template_id == "browser-local":
                    signals = _build_browser_match_signals(
                        role=role,
                        goal_context=goal_context,
                    )
                else:
                    signals = []
                if signals:
                    matched_roles.append((role, signals))
            if not matched_roles:
                continue
            installed = _install_template_recommendation_satisfied(
                template,
                browser_runtime_service=browser_runtime_service,
            )
            default_ref = _install_template_default_ref(
                template,
                browser_runtime_service=browser_runtime_service,
            )
            discovery_queries = self._build_install_template_discovery_queries(
                template_id=template_id,
                profile=profile,
                matched_roles=matched_roles,
                goal_context_by_agent=goal_context_by_agent,
            )
            items.append(
                IndustryCapabilityRecommendation(
                    recommendation_id=f"{template_id}:{default_ref or template_id}",
                    install_kind=str(template.install_kind or "mcp-template"),
                    template_id=template_id,
                    title=template.name,
                    description=template.description,
                    default_client_key=default_ref,
                    capability_ids=capability_ids,
                    capability_tags=list(template.capability_tags or []),
                    capability_families=_recommendation_capability_families(
                        profile=profile,
                        matched_roles=matched_roles,
                        goal_context_by_agent=goal_context_by_agent,
                    ),
                    suggested_role_ids=[role.role_id for role, _signals in matched_roles],
                    target_agent_ids=[role.agent_id for role, _signals in matched_roles],
                    default_enabled=True if template.enabled is None else bool(template.enabled),
                    installed=installed,
                    selected=not installed,
                    required=False,
                    risk_level=str(template.risk_level or "guarded"),
                    capability_budget_cost=int(
                        template.capability_budget_cost or len(capability_ids),
                    ),
                    source_kind="install-template",
                    source_label="Capability Market",
                    review_required=False,
                    review_summary="",
                    review_notes=[],
                    notes=_unique_strings(
                        list(template.notes or []),
                        _build_recommendation_reason_notes(matched_roles),
                        _install_template_gap_notes(
                            template,
                            browser_runtime_service=browser_runtime_service,
                        ),
                    ),
                    discovery_queries=discovery_queries,
                    match_signals=_unique_strings(
                        *[signals for _role, signals in matched_roles],
                    ),
                    governance_path=_governance_path_for_recommendation(
                        install_kind=str(template.install_kind or "mcp-template"),
                        installed=installed,
                        review_required=False,
                    ),
                    routes=dict(template.routes or {}),
                ),
            )
        return items

    async def search_mcp_registry_catalog_for_queries(
        self,
        *,
        queries: list[str],
        limit: int = _MCP_REGISTRY_QUERY_MAX_ITEMS,
    ) -> list[dict[str, Any]]:
        catalog = self._get_mcp_registry_catalog()
        if catalog is None:
            return []
        installed_clients = self._load_installed_mcp_clients()
        aggregated: dict[str, Any] = {}
        for query in _unique_strings(queries)[:2]:
            try:
                response = await asyncio.to_thread(
                    getattr(catalog, "list_catalog"),
                    query=query,
                    category="all",
                    limit=min(max(1, limit), 8),
                    installed_clients=installed_clients,
                )
            except Exception:
                continue
            for item in list(getattr(response, "items", []) or []):
                server_name = _string(getattr(item, "server_name", None))
                if not server_name:
                    continue
                existing = aggregated.get(server_name)
                if existing is None or (
                    not bool(getattr(existing, "update_available", False))
                    and bool(getattr(item, "update_available", False))
                ):
                    aggregated[server_name] = item
        items = list(aggregated.values())
        items.sort(
            key=lambda item: (
                not bool(getattr(item, "update_available", False)),
                not bool(getattr(item, "install_supported", False)),
                bool(getattr(item, "installed_client_key", None))
                and not bool(getattr(item, "update_available", False)),
                _string(getattr(item, "title", None)).lower(),
            ),
        )
        return [
            item.model_dump(mode="json")
            for item in items[: max(1, limit)]
            if hasattr(item, "model_dump")
        ]

    async def build_mcp_registry_recommendations(
        self,
        *,
        profile: IndustryProfile,
        target_roles: list[IndustryRoleBlueprint],
        goal_context_by_agent: dict[str, list[str]],
    ) -> tuple[list[IndustryCapabilityRecommendation], list[str]]:
        catalog = self._get_mcp_registry_catalog()
        if catalog is None:
            return [], []
        installed_clients = self._load_installed_mcp_clients()
        search_cache: dict[tuple[str, str], Any] = {}
        detail_cache: dict[str, Any] = {}
        warnings: list[str] = []
        warning_emitted = False
        aggregated: dict[str, dict[str, Any]] = {}

        for role in target_roles[:_REMOTE_RECOMMENDATION_ROLE_LIMIT]:
            goal_context = goal_context_by_agent.get(role.agent_id, [])
            family_ids = _expand_role_capability_family_ids(
                role=role,
                goal_context=goal_context,
                family_ids=_role_capability_family_ids(
                    profile=profile,
                    role=role,
                    goal_context=goal_context,
                ),
            )
            categories = self._mcp_registry_categories_for_family_ids(family_ids)
            queries = self._build_mcp_registry_queries(
                profile=profile,
                role=role,
                goal_context=goal_context,
            )
            search_specs = [
                (category, query)
                for category in (categories or ["all"])[:2]
                for query in (queries or [""])[:2]
            ] or [("all", "")]
            for category, query in search_specs[:4]:
                cache_key = (category, query)
                if cache_key not in search_cache:
                    try:
                        search_cache[cache_key] = await asyncio.to_thread(
                            getattr(catalog, "list_catalog"),
                            query=query,
                            category=category,
                            limit=6,
                            installed_clients=installed_clients,
                        )
                    except Exception:
                        search_cache[cache_key] = None
                        if not warning_emitted:
                            warnings.append(
                                "Official MCP Registry search is temporarily unavailable."
                            )
                            warning_emitted = True
                response = search_cache.get(cache_key)
                if response is None:
                    continue
                for item in list(getattr(response, "items", []) or [])[
                    :_MCP_REGISTRY_RECOMMENDATION_MATCHES_PER_ROLE
                ]:
                    server_name = _string(getattr(item, "server_name", None))
                    if not server_name:
                        continue
                    item_blob = _search_blob(
                        [
                            _string(getattr(item, "title", None)),
                            _string(getattr(item, "description", None)),
                            _string(getattr(item, "repository_url", None)),
                            _string(getattr(item, "website_url", None)),
                            *list(getattr(item, "category_keys", []) or []),
                            *list(getattr(item, "transport_types", []) or []),
                        ],
                    )
                    matched_families = _matched_capability_family_ids(family_ids, item_blob)
                    query_terms = [
                        term
                        for term in query.lower().split()
                        if len(term) >= 3
                    ]
                    query_hit = not query_terms or any(term in item_blob for term in query_terms)
                    category_hit = category == "all" or category in set(
                        list(getattr(item, "category_keys", []) or [])
                    )
                    if not matched_families and not query_hit and not category_hit:
                        continue
                    entry = aggregated.setdefault(
                        server_name,
                        {
                            "item": item,
                            "target_agent_ids": set(),
                            "suggested_role_ids": set(),
                            "capability_families": set(),
                            "queries": set(),
                            "signals": set(),
                        },
                    )
                    existing_item = entry["item"]
                    if (
                        not bool(getattr(existing_item, "update_available", False))
                        and bool(getattr(item, "update_available", False))
                    ):
                        entry["item"] = item
                    entry["target_agent_ids"].add(role.agent_id)
                    if role.role_id:
                        entry["suggested_role_ids"].add(role.role_id)
                    entry["capability_families"].update(matched_families or family_ids)
                    if query:
                        entry["queries"].add(query)
                    if category != "all":
                        entry["signals"].add(f"registry-category:{category}")
                    for family_id in matched_families:
                        entry["signals"].add(f"family:{family_id}")
                    if query_hit and query:
                        entry["signals"].add(f"query:{query}")

        recommendations: list[IndustryCapabilityRecommendation] = []
        for server_name, entry in aggregated.items():
            if server_name not in detail_cache:
                try:
                    detail_cache[server_name] = await asyncio.to_thread(
                        getattr(catalog, "get_catalog_detail"),
                        server_name,
                        installed_clients=installed_clients,
                    )
                except Exception:
                    detail_cache[server_name] = None
            detail = detail_cache.get(server_name)
            if detail is None:
                continue
            item = entry["item"]
            existing_pair = self._find_installed_registry_client(
                server_name=server_name,
                installed_clients=installed_clients,
            )
            existing_client_key = existing_pair[0] if existing_pair is not None else ""
            existing_client = existing_pair[1] if existing_pair is not None else None
            selected_option = self._select_mcp_registry_install_option(
                detail,
                existing_client=existing_client,
            )
            if selected_option is None:
                continue
            update_available = bool(getattr(item, "update_available", False))
            actionable_existing = bool(existing_client_key) and update_available
            if existing_client_key and not actionable_existing:
                continue
            if (
                not actionable_existing
                and not self._mcp_registry_option_is_auto_ready(
                    selected_option,
                    existing_client=existing_client,
                )
            ):
                continue
            client_key = existing_client_key or _string(
                getattr(item, "suggested_client_key", None),
            )
            if not client_key:
                continue
            option_label = _string(getattr(selected_option, "label", None)) or server_name
            option_summary = _string(getattr(selected_option, "summary", None))
            action_kind = (
                "system:update_mcp_client"
                if actionable_existing
                else "system:create_mcp_client"
            )
            notes = _unique_strings(
                [option_summary] if option_summary else [],
                [f"Official MCP Registry match: {option_label}."],
                (
                    [
                        f"Installed client '{client_key}' has a newer registry version available."
                    ]
                    if actionable_existing
                    else []
                ),
                (
                    [
                        f"Transport: {_string(getattr(selected_option, 'transport', None))}."
                    ]
                    if _string(getattr(selected_option, "transport", None))
                    else []
                ),
            )
            recommendations.append(
                IndustryCapabilityRecommendation(
                    recommendation_id=(
                        f"mcp-registry:{server_name}:"
                        f"{_string(getattr(selected_option, 'key', None)) or 'default'}"
                    ),
                    install_kind="mcp-registry",
                    template_id=server_name,
                    install_option_key=_string(getattr(selected_option, "key", None)),
                    title=_string(getattr(item, "title", None)) or server_name,
                    description=_string(getattr(item, "description", None)),
                    default_client_key=client_key,
                    capability_ids=[f"mcp:{client_key}"],
                    capability_tags=_unique_strings(
                        ["mcp"],
                        list(getattr(item, "category_keys", []) or []),
                        list(getattr(item, "transport_types", []) or []),
                    ),
                    capability_families=_unique_strings(
                        list(entry["capability_families"]),
                    ),
                    suggested_role_ids=_unique_strings(list(entry["suggested_role_ids"])),
                    target_agent_ids=_unique_strings(list(entry["target_agent_ids"])),
                    default_enabled=(
                        bool(getattr(existing_client, "enabled", True))
                        if existing_client is not None
                        else True
                    ),
                    installed=False,
                    selected=True,
                    required=False,
                    risk_level="guarded",
                    capability_budget_cost=1,
                    source_kind="mcp-registry",
                    source_label=_string(getattr(item, "source_label", None))
                    or "Official MCP Registry",
                    source_url=(
                        _string(getattr(item, "repository_url", None))
                        or _string(getattr(item, "source_url", None))
                        or _string(getattr(item, "website_url", None))
                    ),
                    version=_string(getattr(item, "version", None)),
                    review_required=False,
                    review_summary="",
                    review_notes=[],
                    notes=notes,
                    discovery_queries=_unique_strings(list(entry["queries"])),
                    match_signals=_unique_strings(list(entry["signals"])),
                    governance_path=_governance_path_for_recommendation(
                        install_kind="mcp-registry",
                        installed=bool(existing_client_key),
                        review_required=False,
                        action_kind=action_kind,
                    ),
                    routes=dict(getattr(item, "routes", {}) or {}),
                ),
            )
        recommendations.sort(
            key=lambda item: (
                "system:update_mcp_client" not in set(item.governance_path),
                len(item.target_agent_ids or []),
                item.title.lower(),
            ),
        )
        return (
            recommendations[: _mcp_registry_recommendation_output_limit(target_roles)],
            _unique_strings(warnings),
        )

    async def build_hub_skill_recommendations(
        self,
        *,
        profile: IndustryProfile,
        target_roles: list[IndustryRoleBlueprint],
        goal_context_by_agent: dict[str, list[str]],
    ) -> tuple[list[IndustryCapabilityRecommendation], list[str]]:
        installed_skills = self._list_installed_skill_specs()
        warnings: list[str] = []
        aggregated: dict[str, dict[str, object]] = {}
        for role in target_roles[:_REMOTE_RECOMMENDATION_ROLE_LIMIT]:
            (
                goal_context,
                role_family_ids,
                query_candidates,
                family_coverage_target,
            ) = _build_remote_recommendation_role_inputs(
                profile=profile,
                role=role,
                goal_context_by_agent=goal_context_by_agent,
            )
            if not query_candidates:
                continue
            accumulator = _RemoteRecommendationAccumulator(
                aggregated=aggregated,
                per_role_match_limit=_HUB_RECOMMENDATION_MATCHES_PER_ROLE,
                family_coverage_target=family_coverage_target,
            )
            for candidate in query_candidates:
                try:
                    results = await self._search_hub_skills_cached(
                        query=candidate.query,
                        limit=8,
                    )
                except Exception:
                    warnings.append(
                        "Remote hub discovery is temporarily unavailable; only local matches remain available.",
                    )
                    break
                for result in results:
                    signals = _build_hub_match_signals(
                        profile=profile,
                        role=role,
                        goal_context=goal_context,
                        result=result,
                    )
                    result_blob = _search_blob(
                        [
                            result.slug,
                            result.name,
                            result.description,
                        ],
                    )
                    matched_families = _matched_capability_family_ids(
                        role_family_ids,
                        result_blob,
                    )
                    explicit_match = next(
                        (
                            capability.split(":", 1)[1].strip().lower()
                            for capability in role.allowed_capabilities
                            if capability.strip().lower().startswith("skill:")
                            and capability.split(":", 1)[1].strip().lower()
                            in result_blob
                        ),
                        None,
                    )
                    if not _remote_skill_matches_guardrails(
                        profile=profile,
                        role=role,
                        goal_context=goal_context,
                        candidate_blob=result_blob,
                        matched_families=matched_families,
                        explicit_match=explicit_match,
                    ):
                        continue
                    if (
                        candidate.kind == "family"
                        and candidate.family_id is not None
                        and candidate.family_id not in matched_families
                    ):
                        continue
                    if not signals and candidate.kind == "explicit":
                        signals = _fallback_query_signals(candidate.query)
                    if not signals:
                        continue
                    key = _hub_result_key(result)
                    if not key:
                        continue
                    candidate_family = candidate.family_id or (
                        matched_families[0] if matched_families else None
                    )
                    if not accumulator.accepts(
                        key=key,
                        candidate_family=candidate_family,
                    ):
                        continue
                    installed_match = self._find_installed_skill_match(
                        result=result,
                        installed_skills=installed_skills,
                    )
                    installed_name = (
                        _string(installed_match.get("name"))
                        if installed_match is not None
                        else ""
                    ) or ""
                    capability_id = _skill_capability_id(installed_name)
                    accumulator.merge(
                        key=key,
                        seed_entry={
                            "result": result,
                            "installed": installed_match is not None,
                            "default_client_key": installed_name,
                            "capability_ids": [capability_id] if capability_id else [],
                        },
                        role=role,
                        signals=signals,
                        query=candidate.query,
                        candidate_family=candidate_family,
                        matched_families=matched_families,
                    )
                    if accumulator.is_saturated():
                        break
                if accumulator.is_saturated():
                    break
        items: list[IndustryCapabilityRecommendation] = []
        for entry in sorted(
            aggregated.values(),
            key=lambda item: (
                bool(item.get("installed")),
                -len(item.get("matched_roles") or []),
                str(getattr(item.get("result"), "name", "") or ""),
            ),
        )[: _hub_recommendation_output_limit(target_roles)]:
            result = entry.get("result")
            if not isinstance(result, HubSkillResult):
                continue
            matched_roles = list(entry.get("matched_roles") or [])
            capability_ids = list(entry.get("capability_ids") or [])
            default_client_key = str(entry.get("default_client_key") or "")
            installed = bool(entry.get("installed"))
            discovery_queries = list(entry.get("queries") or [])
            source_url = _string(result.source_url) or ""
            version = _string(result.version) or ""
            items.append(
                build_remote_skill_recommendation(
                    recommendation_id=f"hub-skill:{result.slug or result.name}",
                    install_kind="hub-skill",
                    template_id=result.slug or result.name,
                    title=result.name,
                    description=result.description,
                    default_client_key=default_client_key,
                    capability_ids=capability_ids,
                    capability_tags=["skill", "hub", "remote"],
                    capability_families=_recommendation_capability_families(
                        profile=profile,
                        matched_roles=matched_roles,
                        goal_context_by_agent=goal_context_by_agent,
                        matched_family_ids=list(entry.get("matched_families") or []),
                    ),
                    suggested_role_ids=[role.role_id for role, _signals in matched_roles],
                    target_agent_ids=[role.agent_id for role, _signals in matched_roles],
                    installed=installed,
                    source_kind="hub-search",
                    source_label=str(result.source_label or "SkillHub"),
                    source_url=source_url,
                    version=version,
                    review_required=False,
                    review_summary="",
                    review_notes=[],
                    notes=_unique_strings(
                        (
                            [
                                "This skill already exists locally and can be assigned directly."
                            ]
                            if installed
                            else [
                                "The skill will be installed from the remote hub before governed assignment."
                            ]
                        ),
                        [f"Source: {source_url}"] if source_url else [],
                        [f"Version: {version}"] if version else [],
                        _build_recommendation_reason_notes(matched_roles),
                    ),
                    discovery_queries=discovery_queries,
                    match_signals=list(entry.get("signals") or []),
                    governance_path=_governance_path_for_recommendation(
                        install_kind="hub-skill",
                        installed=installed,
                        review_required=False,
                    ),
                    routes={
                        "hub_search": (
                            f"/api/capability-market/hub/search?q={quote(discovery_queries[0])}"
                            if discovery_queries
                            else ""
                        ),
                        "market_skills": "/api/capability-market/skills",
                        "hub_source": source_url,
                    },
                ),
            )
        return items, _unique_strings(warnings)

    async def build_curated_skill_recommendations(
        self,
        *,
        profile: IndustryProfile,
        target_roles: list[IndustryRoleBlueprint],
        goal_context_by_agent: dict[str, list[str]],
    ) -> tuple[list[IndustryCapabilityRecommendation], list[str]]:
        aggregated: dict[str, dict[str, object]] = {}
        warnings: list[str] = []
        for role in target_roles[:_REMOTE_RECOMMENDATION_ROLE_LIMIT]:
            (
                goal_context,
                role_family_ids,
                query_candidates,
                family_coverage_target,
            ) = _build_remote_recommendation_role_inputs(
                profile=profile,
                role=role,
                goal_context_by_agent=goal_context_by_agent,
            )
            if not query_candidates:
                continue
            accumulator = _RemoteRecommendationAccumulator(
                aggregated=aggregated,
                per_role_match_limit=_CURATED_RECOMMENDATION_MATCHES_PER_ROLE,
                family_coverage_target=family_coverage_target,
            )
            for candidate in query_candidates:
                try:
                    search_curated = _get_industry_discovery_attr(
                        "search_curated_skill_catalog",
                        search_curated_skill_catalog,
                        _NATIVE_SEARCH_CURATED_SKILL_CATALOG,
                    )
                    search_response = await asyncio.to_thread(
                        search_curated,
                        candidate.query,
                        limit=8,
                    )
                except Exception:
                    warnings.append(
                        "Curated discovery is temporarily unavailable; continuing without that source.",
                    )
                    break
                warnings.extend(search_response.warnings or [])
                for item in search_response.items:
                    signals = _build_curated_match_signals(
                        profile=profile,
                        role=role,
                        goal_context=goal_context,
                        item=item,
                    )
                    item_blob = _search_blob(
                        [
                            item.title,
                            item.description,
                            item.bundle_url,
                            *list(item.tags or []),
                            *list(item.capability_tags or []),
                        ],
                    )
                    matched_families = _matched_capability_family_ids(
                        role_family_ids,
                        item_blob,
                    )
                    explicit_match = next(
                        (
                            capability.split(":", 1)[1].strip().lower()
                            for capability in role.allowed_capabilities
                            if capability.strip().lower().startswith("skill:")
                            and capability.split(":", 1)[1].strip().lower()
                            in item_blob
                        ),
                        None,
                    )
                    if not _remote_skill_matches_guardrails(
                        profile=profile,
                        role=role,
                        goal_context=goal_context,
                        candidate_blob=item_blob,
                        matched_families=matched_families,
                        explicit_match=explicit_match,
                    ):
                        continue
                    if (
                        candidate.kind == "family"
                        and candidate.family_id is not None
                        and candidate.family_id not in matched_families
                    ):
                        continue
                    if not signals and candidate.kind == "explicit":
                        signals = _fallback_query_signals(candidate.query)
                    if not signals:
                        continue
                    key = _curated_entry_key(item)
                    if not key:
                        continue
                    candidate_family = candidate.family_id or (
                        matched_families[0] if matched_families else None
                    )
                    if not accumulator.accepts(
                        key=key,
                        candidate_family=candidate_family,
                    ):
                        continue
                    accumulator.merge(
                        key=key,
                        seed_entry={"item": item},
                        role=role,
                        signals=signals,
                        query=candidate.query,
                        candidate_family=candidate_family,
                        matched_families=matched_families,
                    )
                    if accumulator.is_saturated():
                        break
                if accumulator.is_saturated():
                    break
        items: list[IndustryCapabilityRecommendation] = []
        for entry in sorted(
            aggregated.values(),
            key=lambda item: (
                getattr(item.get("item"), "manifest_status", "")
                not in {"verified", "skillhub-curated"},
                -len(item.get("matched_roles") or []),
                str(getattr(item.get("item"), "title", "") or ""),
            ),
        )[: _curated_recommendation_output_limit(target_roles)]:
            item = entry.get("item")
            if not isinstance(item, CuratedSkillCatalogEntry):
                continue
            matched_roles = list(entry.get("matched_roles") or [])
            capability_id = _skill_capability_id(item.install_name)
            items.append(
                build_remote_skill_recommendation(
                    recommendation_id=f"curated-skill:{item.source_id}:{item.candidate_id}",
                    install_kind="hub-skill",
                    template_id=item.candidate_id,
                    title=item.title,
                    description=item.description,
                    default_client_key=item.install_name,
                    capability_ids=[capability_id] if capability_id else [],
                    capability_tags=_unique_strings(
                        list(item.capability_tags or []),
                        [item.manifest_status],
                    ),
                    capability_families=_recommendation_capability_families(
                        profile=profile,
                        matched_roles=matched_roles,
                        goal_context_by_agent=goal_context_by_agent,
                        matched_family_ids=list(entry.get("matched_families") or []),
                    ),
                    suggested_role_ids=[role.role_id for role, _signals in matched_roles],
                    target_agent_ids=[role.agent_id for role, _signals in matched_roles],
                    installed=False,
                    source_kind="skillhub-curated",
                    source_label=item.source_label,
                    source_url=item.bundle_url,
                    version=item.version,
                    review_required=bool(item.review_required),
                    review_summary=item.review_summary,
                    review_notes=list(item.review_notes or []),
                    notes=_unique_strings(
                        _build_recommendation_reason_notes(matched_roles),
                        (
                            ["Verified curated source."]
                            if item.manifest_status == "verified"
                            else ["Curated source with governed install path."]
                        ),
                    ),
                    discovery_queries=list(entry.get("queries") or []),
                    match_signals=list(entry.get("signals") or []),
                    governance_path=_governance_path_for_recommendation(
                        install_kind="hub-skill",
                        installed=False,
                        review_required=bool(item.review_required),
                    ),
                    routes=dict(item.routes or {}),
                ),
            )
        return items, _unique_strings(warnings)

    def build_prediction_queries(
        self,
        *,
        role_name: str | None,
        role_summary: str | None,
        mission: str | None,
        capability_hint: str | None,
        goal_titles: list[str] | None = None,
        workflow_titles: list[str] | None = None,
        task_titles: list[str] | None = None,
        task_summaries: list[str] | None = None,
    ) -> list[str]:
        primary = self._compose_query(
            role_name,
            capability_hint,
            *(workflow_titles or []),
            *(goal_titles or []),
        )
        secondary = self._compose_query(
            capability_hint,
            role_summary,
            mission,
            *(task_titles or []),
            *(task_summaries or []),
        )
        return _unique_strings([primary, secondary])

    def search_remote_skill_candidates_for_queries(
        self,
        *,
        queries: list[str],
        current_capability_id: str | None = None,
        include_curated: bool = True,
        include_hub: bool = False,
    ) -> list[RemoteSkillCandidate]:
        if not (include_curated or include_hub):
            return []
        get_capability_fn = self._resolve_capability_getter()
        candidates_by_key: dict[str, RemoteSkillCandidate] = {}
        for query in queries[:2]:
            try:
                search_remote = _get_prediction_discovery_attr(
                    "search_allowlisted_remote_skill_candidates",
                    search_allowlisted_remote_skill_candidates,
                    _NATIVE_SEARCH_ALLOWLISTED_REMOTE_SKILL_CANDIDATES,
                )
                candidates = search_remote(
                    query,
                    limit=6,
                    include_curated=include_curated,
                    include_hub=include_hub,
                    get_capability_fn=get_capability_fn,
                )
            except Exception:
                continue
            for candidate in candidates:
                resolved_capability_ids = resolve_candidate_capability_ids(candidate)
                if current_capability_id and current_capability_id in resolved_capability_ids:
                    continue
                if (
                    current_capability_id
                    and candidate.install_name
                    and _skill_capability_id(candidate.install_name)
                    == current_capability_id
                ):
                    continue
                existing = candidates_by_key.get(candidate.candidate_key)
                if existing is None or (
                    existing.source_kind != "curated"
                    and candidate.source_kind == "curated"
                ):
                    candidates_by_key[candidate.candidate_key] = candidate
        items = list(candidates_by_key.values())
        items.sort(
            key=lambda item: (
                item.source_kind != "curated",
                item.review_required,
                not item.installed,
                item.title.lower(),
            ),
        )
        return items[:4]

    async def discover(
        self,
        payload: dict[str, object] | None,
    ) -> dict[str, object]:
        resolved_payload = dict(payload or {})
        raw_queries = resolved_payload.get("queries")
        queries = _unique_strings(raw_queries if isinstance(raw_queries, list) else [])
        providers = {
            str(item).strip().lower()
            for item in list(resolved_payload.get("providers") or [])
            if str(item).strip()
        }
        if queries:
            candidates = (
                self.search_remote_skill_candidates_for_queries(
                    queries=queries,
                    current_capability_id=_string(
                        resolved_payload.get("current_capability_id"),
                    ),
                    include_curated=(
                        not providers or "curated-skill" in providers or "remote" in providers
                    ),
                    include_hub="hub-skill" in providers,
                )
                if (
                    not providers
                    or "curated-skill" in providers
                    or "remote" in providers
                    or "hub-skill" in providers
                )
                else []
            )
            mcp_catalog = (
                await self.search_mcp_registry_catalog_for_queries(queries=queries)
                if not providers or "mcp-registry" in providers or "mcp" in providers
                else []
            )
            search_sop_templates = getattr(
                self._fixed_sop_service,
                "search_templates",
                None,
            )
            sop_templates = (
                search_sop_templates(
                    query=" ".join(queries),
                    owner_role_id=_string(resolved_payload.get("owner_role_id")),
                    industry_tags=_list(resolved_payload.get("industry_tags")),
                    capability_tags=_list(resolved_payload.get("capability_tags")),
                    limit=8,
                )
                if callable(search_sop_templates)
                else []
            )
            return {
                "success": True,
                "summary": (
                    f"Discovered {len(candidates)} remote skill candidates and "
                    f"{len(mcp_catalog)} MCP registry matches."
                ),
                "mode": "query",
                "queries": queries,
                "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
                "mcp_catalog": mcp_catalog,
                "sop_templates": [item.model_dump(mode="json") for item in sop_templates],
                "warnings": [],
            }

        profile_payload = resolved_payload.get("industry_profile")
        role_payload = resolved_payload.get("role")
        if not isinstance(profile_payload, dict) or not isinstance(role_payload, dict):
            return {
                "success": False,
                "error": "queries or the pair industry_profile + role is required",
            }
        profile = IndustryProfile.model_validate(profile_payload)
        role = IndustryRoleBlueprint.model_validate(role_payload)
        goal_context = _unique_strings(
            list(resolved_payload.get("goal_context") or []),
        )
        goal_context_by_agent = {role.agent_id: goal_context}
        recommendations: list[IndustryCapabilityRecommendation] = []
        warnings: list[str] = []
        if not providers or "install-template" in providers or "builtin-runtime" in providers:
            recommendations.extend(
                self.build_install_template_recommendations(
                    profile=profile,
                    target_roles=[role],
                    goal_context_by_agent=goal_context_by_agent,
                ),
            )
        if not providers or "curated-skill" in providers or "remote" in providers:
            curated_items, curated_warnings = await self.build_curated_skill_recommendations(
                profile=profile,
                target_roles=[role],
                goal_context_by_agent=goal_context_by_agent,
            )
            recommendations.extend(curated_items)
            warnings.extend(curated_warnings)
        if not providers or "mcp-registry" in providers or "mcp" in providers:
            mcp_items, mcp_warnings = await self.build_mcp_registry_recommendations(
                profile=profile,
                target_roles=[role],
                goal_context_by_agent=goal_context_by_agent,
            )
            recommendations.extend(mcp_items)
            warnings.extend(mcp_warnings)
        if "hub-skill" in providers:
            hub_items, hub_warnings = await self.build_hub_skill_recommendations(
                profile=profile,
                target_roles=[role],
                goal_context_by_agent=goal_context_by_agent,
            )
            recommendations.extend(hub_items)
            warnings.extend(hub_warnings)
        search_sop_templates = getattr(
            self._fixed_sop_service,
            "search_templates",
            None,
        )
        sop_templates = (
            search_sop_templates(
                query=self._compose_query(
                    profile.primary_label(),
                    profile.industry,
                    role.role_name,
                    " ".join(goal_context[:3]),
                ),
                owner_role_id=role.role_id,
                industry_tags=[profile.industry, profile.sub_industry],
                capability_tags=_role_capability_family_ids(
                    profile=profile,
                    role=role,
                    goal_context=goal_context,
                ),
                limit=8,
            )
            if callable(search_sop_templates)
            else []
        )
        return {
            "success": True,
            "summary": f"Discovered {len(recommendations)} capability recommendations.",
            "mode": "role",
            "recommendations": [
                item.model_dump(mode="json") for item in recommendations
            ],
            "sop_templates": [item.model_dump(mode="json") for item in sop_templates],
            "warnings": _unique_strings(warnings),
        }

    def _resolve_capability_getter(self):
        getter = getattr(self._capability_service, "get_capability", None)
        return getter if callable(getter) else None

    def _list_installed_skill_specs(self) -> list[dict[str, str]]:
        lister = getattr(self._capability_service, "list_skill_specs", None)
        if not callable(lister):
            return []
        try:
            payload = lister()
        except Exception:
            return []
        installed: list[dict[str, str]] = []
        if not isinstance(payload, list):
            return installed
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = _string(item.get("name"))
            if not name:
                continue
            installed.append(
                {
                    "name": name,
                    "source": _string(item.get("source")) or "",
                },
            )
        return installed

    def _find_installed_skill_match(
        self,
        *,
        result: HubSkillResult,
        installed_skills: list[dict[str, str]],
    ) -> dict[str, str] | None:
        source_url = (_string(result.source_url) or "").rstrip("/").lower()
        result_name = (_string(result.name) or "").lower()
        slug_tail = (_string(result.slug) or "").split("/")[-1].strip().lower()
        result_key = _hub_result_key(result)
        for skill in installed_skills:
            source = (_string(skill.get("source")) or "").rstrip("/").lower()
            name = (_string(skill.get("name")) or "").lower()
            if source_url and source == source_url:
                return skill
            if result_name and name == result_name:
                return skill
            if slug_tail and name == slug_tail:
                return skill
            if result_key and source and result_key in source:
                return skill
        return None

    async def _search_hub_skills_cached(
        self,
        *,
        query: str,
        limit: int = 6,
    ) -> list[HubSkillResult]:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return []
        cache_key = (normalized_query.lower(), limit)
        cached = self._hub_search_cache.get(cache_key)
        now = _utc_now()
        if cached is not None and cached[0] >= now:
            return list(cached[1])
        search_hub = _get_industry_discovery_attr(
            "search_hub_skills",
            search_hub_skills,
            _NATIVE_SEARCH_HUB_SKILLS,
        )
        results = await asyncio.to_thread(
            search_hub,
            normalized_query,
            limit,
        )
        self._hub_search_cache[cache_key] = (
            now + timedelta(minutes=10),
            list(results),
        )
        return list(results)

    def _compose_query(self, *parts: object) -> str:
        values = [
            str(part).strip()
            for part in parts
            if isinstance(part, str) and str(part).strip()
        ]
        if not values:
            return ""
        return " ".join(values)[:180].strip()
