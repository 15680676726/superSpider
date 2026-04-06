# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field

from .external_adapter_contracts import HostCompatibilityRequirements


def _normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_set(values: object | None) -> set[str]:
    if isinstance(values, str):
        items = [values]
    elif isinstance(values, (list, tuple, set, frozenset)):
        items = list(values)
    else:
        items = []
    normalized: set[str] = set()
    for item in items:
        text = _normalize_text(item)
        if text is not None:
            normalized.add(text.casefold())
    return normalized


@dataclass(slots=True)
class HostCompatibilityContext:
    os_name: str | None = None
    architecture: str | None = None
    available_runtimes: list[str] = field(default_factory=list)
    provider_contract_kind: str | None = None
    available_surfaces: list[str] = field(default_factory=list)
    env_keys: list[str] = field(default_factory=list)
    config_locations: list[str] = field(default_factory=list)
    workspace_policy: str | None = None


@dataclass(slots=True)
class HostCompatibilityBridgeCatalog:
    env_key_aliases: dict[str, list[str]] = field(default_factory=dict)
    config_location_aliases: dict[str, list[str]] = field(default_factory=dict)
    provider_contract_aliases: dict[str, list[str]] = field(default_factory=dict)
    runtime_aliases: dict[str, list[str]] = field(default_factory=dict)
    surface_aliases: dict[str, list[str]] = field(default_factory=dict)
    workspace_policy_aliases: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class HostCompatibilityResult:
    status: str
    blockers: list[str] = field(default_factory=list)
    bridge_reasons: list[str] = field(default_factory=list)


def _matches_or_bridges(
    requirement: str,
    *,
    available: set[str],
    aliases: dict[str, list[str]],
    bridge_label: str,
) -> tuple[bool, str | None]:
    normalized_requirement = requirement.casefold()
    if normalized_requirement in available:
        return True, None
    for alias in aliases.get(requirement, []):
        normalized_alias = _normalize_text(alias)
        if normalized_alias is not None and normalized_alias.casefold() in available:
            return True, f"{bridge_label}:{requirement}"
    return False, None


def _resolve_blocked_status(blockers: list[str]) -> str:
    if any(item.startswith("provider-contract:") for item in blockers):
        return "blocked_missing_provider_contract"
    if any(item.startswith("os:") or item.startswith("arch:") for item in blockers):
        return "blocked_unsupported_host"
    if any(
        item.startswith("env:")
        or item.startswith("config:")
        or item.startswith("workspace:")
        for item in blockers
    ):
        return "blocked_contract_violation"
    return "blocked_missing_dependency"


def evaluate_donor_host_compatibility(
    *,
    requirements: HostCompatibilityRequirements,
    context: HostCompatibilityContext,
    bridges: HostCompatibilityBridgeCatalog | None = None,
) -> HostCompatibilityResult:
    bridge_catalog = bridges or HostCompatibilityBridgeCatalog()
    blockers: list[str] = []
    bridge_reasons: list[str] = []

    supported_os = _normalize_set(requirements.supported_os)
    os_name = _normalize_text(context.os_name)
    if supported_os and (os_name is None or os_name.casefold() not in supported_os):
        blockers.append(f"os:{os_name or 'unknown'}")

    supported_architectures = _normalize_set(requirements.supported_architectures)
    architecture = _normalize_text(context.architecture)
    if supported_architectures and (
        architecture is None or architecture.casefold() not in supported_architectures
    ):
        blockers.append(f"arch:{architecture or 'unknown'}")

    provider_contract_kind = _normalize_text(requirements.required_provider_contract_kind)
    if provider_contract_kind is not None:
        matched, bridge_reason = _matches_or_bridges(
            provider_contract_kind,
            available=_normalize_set([context.provider_contract_kind]),
            aliases=bridge_catalog.provider_contract_aliases,
            bridge_label="provider-alias",
        )
        if not matched:
            blockers.append(f"provider-contract:{provider_contract_kind}")
        elif bridge_reason is not None:
            bridge_reasons.append(bridge_reason)

    available_runtimes = _normalize_set(context.available_runtimes)
    for runtime in requirements.required_runtimes:
        normalized_runtime = _normalize_text(runtime)
        if normalized_runtime is None:
            continue
        matched, bridge_reason = _matches_or_bridges(
            normalized_runtime,
            available=available_runtimes,
            aliases=bridge_catalog.runtime_aliases,
            bridge_label="runtime-alias",
        )
        if not matched:
            blockers.append(f"runtime:{normalized_runtime}")
        elif bridge_reason is not None:
            bridge_reasons.append(bridge_reason)

    available_surfaces = _normalize_set(context.available_surfaces)
    for surface in requirements.required_surfaces:
        normalized_surface = _normalize_text(surface)
        if normalized_surface is None:
            continue
        matched, bridge_reason = _matches_or_bridges(
            normalized_surface,
            available=available_surfaces,
            aliases=bridge_catalog.surface_aliases,
            bridge_label="surface-alias",
        )
        if not matched:
            blockers.append(f"surface:{normalized_surface}")
        elif bridge_reason is not None:
            bridge_reasons.append(bridge_reason)

    env_keys = _normalize_set(context.env_keys)
    for env_key in requirements.required_env_keys:
        normalized_env_key = _normalize_text(env_key)
        if normalized_env_key is None:
            continue
        matched, bridge_reason = _matches_or_bridges(
            normalized_env_key,
            available=env_keys,
            aliases=bridge_catalog.env_key_aliases,
            bridge_label="env-alias",
        )
        if not matched:
            blockers.append(f"env:{normalized_env_key}")
        elif bridge_reason is not None:
            bridge_reasons.append(bridge_reason)

    config_locations = _normalize_set(context.config_locations)
    for config_location in requirements.config_location_expectations:
        normalized_location = _normalize_text(config_location)
        if normalized_location is None:
            continue
        matched, bridge_reason = _matches_or_bridges(
            normalized_location,
            available=config_locations,
            aliases=bridge_catalog.config_location_aliases,
            bridge_label="config-alias",
        )
        if not matched:
            blockers.append(f"config:{normalized_location}")
        elif bridge_reason is not None:
            bridge_reasons.append(bridge_reason)

    workspace_policy = _normalize_text(requirements.workspace_policy)
    if workspace_policy is not None:
        matched, bridge_reason = _matches_or_bridges(
            workspace_policy,
            available=_normalize_set([context.workspace_policy]),
            aliases=bridge_catalog.workspace_policy_aliases,
            bridge_label="workspace-alias",
        )
        if not matched:
            blockers.append(f"workspace:{workspace_policy}")
        elif bridge_reason is not None:
            bridge_reasons.append(bridge_reason)

    if blockers:
        return HostCompatibilityResult(
            status=_resolve_blocked_status(blockers),
            blockers=blockers,
            bridge_reasons=bridge_reasons,
        )
    if bridge_reasons:
        return HostCompatibilityResult(
            status="compatible_via_bridge",
            blockers=[],
            bridge_reasons=bridge_reasons,
        )
    return HostCompatibilityResult(
        status="compatible_native",
        blockers=[],
        bridge_reasons=[],
    )


__all__ = [
    "HostCompatibilityBridgeCatalog",
    "HostCompatibilityContext",
    "HostCompatibilityResult",
    "evaluate_donor_host_compatibility",
]
