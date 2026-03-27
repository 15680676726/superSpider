# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any, Callable

from ..industry.identity import normalize_industry_role_id
from .models import CapabilityMount, CapabilitySummary
from .registry import CapabilityRegistry
from .skill_service import CapabilitySkillService

if TYPE_CHECKING:
    from ..kernel.agent_profile import AgentProfile
    from ..kernel.agent_profile_service import AgentProfileService
    from ..state.repositories import (
        SqliteAgentProfileOverrideRepository,
        SqliteCapabilityOverrideRepository,
    )


class CapabilityCatalogFacade:
    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        load_config_fn: Callable[[], Any],
        save_config_fn: Callable[[Any], None],
        skill_service: CapabilitySkillService,
        override_repository: "SqliteCapabilityOverrideRepository | None" = None,
        agent_profile_service: "AgentProfileService | None" = None,
        agent_profile_override_repository: "SqliteAgentProfileOverrideRepository | None" = None,
    ) -> None:
        self._registry = registry
        self._load_config = load_config_fn
        self._save_config = save_config_fn
        self._skill_service = skill_service
        self._override_repository = override_repository
        self._agent_profile_service = agent_profile_service
        self._agent_profile_override_repository = agent_profile_override_repository

    def set_override_repository(
        self,
        override_repository: "SqliteCapabilityOverrideRepository | None",
    ) -> None:
        self._override_repository = override_repository

    def set_agent_profile_service(
        self,
        agent_profile_service: "AgentProfileService | None",
    ) -> None:
        self._agent_profile_service = agent_profile_service

    def set_agent_profile_override_repository(
        self,
        override_repository: "SqliteAgentProfileOverrideRepository | None",
    ) -> None:
        self._agent_profile_override_repository = override_repository

    def list_capabilities(
        self,
        *,
        kind: str | None = None,
        enabled_only: bool = False,
    ) -> list[CapabilityMount]:
        mounts = self._apply_overrides(self._registry.list_capabilities())
        if kind:
            mounts = [mount for mount in mounts if mount.kind == kind]
        if enabled_only:
            mounts = [mount for mount in mounts if mount.enabled]
        return mounts

    def list_public_capabilities(
        self,
        *,
        kind: str | None = None,
        enabled_only: bool = False,
    ) -> list[CapabilityMount]:
        return [
            mount
            for mount in self.list_capabilities(kind=kind, enabled_only=enabled_only)
            if _is_public_mount(mount)
        ]

    def get_capability(self, capability_id: str) -> CapabilityMount | None:
        for mount in self.list_capabilities():
            if mount.id == capability_id:
                return mount
        return None

    def get_public_capability(self, capability_id: str) -> CapabilityMount | None:
        mount = self.get_capability(capability_id)
        if mount is None or not _is_public_mount(mount):
            return None
        return mount

    def summarize(self) -> CapabilitySummary:
        mounts = self.list_capabilities()
        by_kind = Counter(mount.kind for mount in mounts)
        by_source = Counter(mount.source_kind for mount in mounts)
        enabled = sum(1 for mount in mounts if mount.enabled)
        return CapabilitySummary(
            total=len(mounts),
            enabled=enabled,
            by_kind=dict(sorted(by_kind.items())),
            by_source=dict(sorted(by_source.items())),
        )

    def summarize_public(self) -> CapabilitySummary:
        mounts = self.list_public_capabilities()
        by_kind = Counter(mount.kind for mount in mounts)
        by_source = Counter(mount.source_kind for mount in mounts)
        enabled = sum(1 for mount in mounts if mount.enabled)
        return CapabilitySummary(
            total=len(mounts),
            enabled=enabled,
            by_kind=dict(sorted(by_kind.items())),
            by_source=dict(sorted(by_source.items())),
        )

    def list_accessible_capabilities(
        self,
        *,
        agent_id: str | None,
        kind: str | None = None,
        enabled_only: bool = False,
    ) -> list[CapabilityMount]:
        mounts = self.list_capabilities(kind=kind, enabled_only=enabled_only)
        profile = self._resolve_agent_profile(agent_id)
        explicit_allowlist = self._resolve_explicit_capability_allowlist(agent_id)
        return [
            mount
            for mount in mounts
            if self._is_mount_accessible(
                mount,
                agent_id=agent_id,
                profile=profile,
                explicit_allowlist=explicit_allowlist,
            )
        ]

    def toggle_capability(self, capability_id: str) -> dict[str, object]:
        mount = self.get_capability(capability_id)
        if mount is None:
            return {"toggled": False, "error": f"Capability '{capability_id}' not found"}
        return self.set_capability_enabled(capability_id, enabled=not mount.enabled)

    def set_capability_enabled(
        self,
        capability_id: str,
        *,
        enabled: bool,
    ) -> dict[str, object]:
        mount = self.get_capability(capability_id)
        if mount is None:
            return {"toggled": False, "error": f"Capability '{capability_id}' not found"}

        if mount.source_kind == "skill":
            name = _capability_name_from_id(capability_id, prefix="skill:")
            if enabled:
                self._skill_service.enable_skill(name)
            else:
                self._skill_service.disable_skill(name)
            return {"toggled": True, "id": capability_id, "enabled": enabled}

        if mount.source_kind == "mcp":
            key = _capability_name_from_id(capability_id, prefix="mcp:")
            config = self._load_config()
            client = config.mcp.clients.get(key)
            if client is None:
                return {"toggled": False, "error": f"MCP client '{key}' not found in config"}
            client.enabled = enabled
            self._save_config(config)
            return {"toggled": True, "id": capability_id, "enabled": enabled}

        return {"toggled": False, "error": f"Toggle not supported for source_kind '{mount.source_kind}'"}

    def delete_capability(self, capability_id: str) -> dict[str, object]:
        mount = self.get_capability(capability_id)
        if mount is None:
            return {"deleted": False, "error": f"Capability '{capability_id}' not found"}

        if mount.source_kind == "skill":
            name = _capability_name_from_id(capability_id, prefix="skill:")
            result = self._skill_service.delete_skill(name)
            return {"deleted": bool(result), "id": capability_id}

        if mount.source_kind == "mcp":
            key = _capability_name_from_id(capability_id, prefix="mcp:")
            config = self._load_config()
            if key not in config.mcp.clients:
                return {"deleted": False, "error": f"MCP client '{key}' not found in config"}
            del config.mcp.clients[key]
            self._save_config(config)
            return {"deleted": True, "id": capability_id}

        return {"deleted": False, "error": f"Delete not supported for source_kind '{mount.source_kind}'"}

    def list_skill_specs(self, *, enabled_only: bool = False) -> list[dict[str, object]]:
        mounts = self.list_capabilities(kind="skill-bundle", enabled_only=enabled_only)
        all_skills = {skill.name: skill for skill in self._skill_service.list_all_skills()}
        enabled_names = set(self._skill_service.list_available_skill_names())
        payload: list[dict[str, object]] = []
        for mount in mounts:
            skill_name = _capability_name_from_id(mount.id, prefix="skill:")
            skill = all_skills.get(skill_name)
            if skill is None:
                continue
            payload.append(
                {
                    "name": skill.name,
                    "content": skill.content,
                    "source": skill.source,
                    "path": skill.path,
                    "references": skill.references,
                    "scripts": skill.scripts,
                    "enabled": skill.name in enabled_names,
                },
            )
        return payload

    def list_available_skill_specs(self) -> list[dict[str, object]]:
        mounts = self.list_capabilities(kind="skill-bundle", enabled_only=True)
        active_skills = {
            skill.name: skill for skill in self._skill_service.list_available_skills()
        }
        payload: list[dict[str, object]] = []
        for mount in mounts:
            skill_name = _capability_name_from_id(mount.id, prefix="skill:")
            skill = active_skills.get(skill_name)
            if skill is None:
                continue
            payload.append(
                {
                    "name": skill.name,
                    "content": skill.content,
                    "source": skill.source,
                    "path": skill.path,
                    "references": skill.references,
                    "scripts": skill.scripts,
                    "enabled": True,
                },
            )
        return payload

    def list_mcp_client_infos(self) -> list[dict[str, object]]:
        config = self._load_config()
        allowed_keys = {
            _capability_name_from_id(mount.id, prefix="mcp:")
            for mount in self.list_capabilities(kind="remote-mcp")
        }
        payload: list[dict[str, object]] = []
        for key, client in config.mcp.clients.items():
            if key not in allowed_keys:
                continue
            client_registry = getattr(client, "registry", None)
            payload.append(
                {
                    "key": key,
                    "name": client.name,
                    "description": client.description,
                    "enabled": client.enabled,
                    "transport": client.transport,
                    "url": client.url,
                    "headers": _mask_mapping(client.headers),
                    "command": client.command,
                    "args": list(client.args),
                    "env": _mask_mapping(client.env),
                    "cwd": client.cwd,
                    "registry": (
                        client_registry.model_dump(mode="json")
                        if client_registry is not None
                        else None
                    ),
                },
            )
        return payload

    def get_mcp_client_info(self, client_key: str) -> dict[str, object] | None:
        for client in self.list_mcp_client_infos():
            if client.get("key") == client_key:
                return client
        return None

    def _apply_overrides(
        self,
        mounts: list[CapabilityMount],
    ) -> list[CapabilityMount]:
        if self._override_repository is None:
            return mounts
        overrides = {
            override.capability_id: override
            for override in self._override_repository.list_overrides()
        }
        if not overrides:
            return mounts
        updated: list[CapabilityMount] = []
        for mount in mounts:
            override = overrides.get(mount.id)
            if override is None:
                updated.append(mount)
                continue
            payload = override.model_dump(mode="json")
            metadata = {**mount.metadata, "override": payload}
            update: dict[str, object] = {"metadata": metadata}
            if override.enabled is not None:
                update["enabled"] = override.enabled
            if override.forced_risk_level:
                update["risk_level"] = override.forced_risk_level
            updated.append(mount.model_copy(update=update))
        return updated

    def _resolve_agent_profile(self, agent_id: str | None) -> "AgentProfile | None":
        if self._agent_profile_service is None or not agent_id:
            return None
        getter = getattr(self._agent_profile_service, "get_agent", None)
        if not callable(getter):
            return None
        return getter(agent_id)

    def _resolve_explicit_capability_allowlist(
        self,
        agent_id: str | None,
    ) -> set[str] | None:
        if self._agent_profile_override_repository is None or not agent_id:
            return None
        override = self._agent_profile_override_repository.get_override(agent_id)
        if override is None or override.capabilities is None:
            return None
        return {
            str(capability_id).strip()
            for capability_id in override.capabilities
            if str(capability_id).strip()
        }

    def _is_mount_accessible(
        self,
        mount: CapabilityMount,
        *,
        agent_id: str | None,
        profile: "AgentProfile | None",
        explicit_allowlist: set[str] | None,
    ) -> bool:
        if explicit_allowlist is not None:
            return mount.id in explicit_allowlist
        policies = {
            str(policy).strip().lower()
            for policy in mount.role_access_policy
            if str(policy).strip()
        }
        if not policies or "all" in policies:
            return True

        access_tags = self._agent_access_tags(agent_id=agent_id, profile=profile)
        if policies & access_tags:
            return True
        if "skill-enabled" in policies and mount.source_kind == "skill" and mount.enabled:
            return True
        if "skill-available" in policies and mount.source_kind == "skill":
            return True
        if "mcp-enabled" in policies and mount.source_kind == "mcp" and mount.enabled:
            return True
        if "mcp-disabled" in policies and mount.source_kind == "mcp" and not mount.enabled:
            return True
        return False

    def _agent_access_tags(
        self,
        *,
        agent_id: str | None,
        profile: "AgentProfile | None",
    ) -> set[str]:
        tags = {"all"}
        raw_values = [
            agent_id,
            getattr(profile, "agent_id", None),
            getattr(profile, "name", None),
            getattr(profile, "role_name", None),
            getattr(profile, "role_summary", None),
            getattr(profile, "industry_role_id", None),
        ]
        normalized_values = {
            str(value).strip().lower()
            for value in raw_values
            if isinstance(value, str) and value.strip()
        }
        normalized_role_id = normalize_industry_role_id(
            getattr(profile, "industry_role_id", None) if profile is not None else None,
        )
        if normalized_role_id:
            normalized_values.add(normalized_role_id)
        tags.update(normalized_values)
        combined = " ".join(sorted(normalized_values))
        if (
            any(value.startswith("copaw-") for value in normalized_values)
            or any(
                keyword in combined
                for keyword in (
                    "operator",
                    "operations",
                    "ops",
                    "runtime",
                    "governance",
                    "scheduler",
                    "planner",
                    "执行",
                    "治理",
                    "调度",
                    "运营",
                )
            )
        ):
            tags.add("operator")
        return tags


def _capability_name_from_id(capability_id: str, *, prefix: str) -> str:
    if capability_id.startswith(prefix):
        return capability_id[len(prefix) :]
    return capability_id


def _mask_mapping(value: dict[str, str] | None) -> dict[str, str]:
    if not value:
        return {}
    return {key: _mask_secret(secret) for key, secret in value.items()}


def _mask_secret(value: str) -> str:
    if not value:
        return value
    if len(value) <= 8:
        return "*" * len(value)
    prefix_len = 3 if len(value) > 2 and value[2] == "-" else 2
    prefix = value[:prefix_len]
    suffix = value[-4:]
    masked_len = max(len(value) - prefix_len - 4, 4)
    return f"{prefix}{'*' * masked_len}{suffix}"


def _is_public_mount(mount: CapabilityMount) -> bool:
    return str(mount.metadata.get("visibility") or "public").strip().lower() != "internal"
