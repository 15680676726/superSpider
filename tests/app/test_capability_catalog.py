from __future__ import annotations

from types import SimpleNamespace

from copaw.capabilities.catalog import CapabilityCatalogFacade
from copaw.capabilities.models import CapabilityMount
from copaw.capabilities.registry import CapabilityRegistry


class _FakeRegistry(CapabilityRegistry):
    def __init__(self, mounts: list[CapabilityMount]) -> None:
        self._mounts = mounts

    def list_capabilities(self) -> list[CapabilityMount]:
        return list(self._mounts)


class _DriftingRegistry(CapabilityRegistry):
    def __init__(self, mounts: list[CapabilityMount], drift_mount: CapabilityMount) -> None:
        self._mounts = mounts
        self._drift_mount = drift_mount
        self.read_count = 0

    def list_capabilities(self) -> list[CapabilityMount]:
        self.read_count += 1
        mounts = list(self._mounts)
        if self.read_count >= 2:
            mounts.append(self._drift_mount)
        return mounts


class _Override:
    def __init__(
        self,
        capability_id: str,
        *,
        enabled: bool | None = None,
        forced_risk_level: str | None = None,
    ) -> None:
        self.capability_id = capability_id
        self.enabled = enabled
        self.forced_risk_level = forced_risk_level

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "enabled": self.enabled,
            "forced_risk_level": self.forced_risk_level,
        }


class _OverrideRepository:
    def __init__(self, overrides: list[_Override]) -> None:
        self._overrides = overrides

    def list_overrides(self) -> list[_Override]:
        return list(self._overrides)


class _AgentOverrideRepository:
    def __init__(self, capabilities: list[str] | None) -> None:
        self._capabilities = capabilities

    def get_override(self, _agent_id: str):
        if self._capabilities is None:
            return None
        return SimpleNamespace(capabilities=list(self._capabilities))


class _AgentProfileService:
    def __init__(self, profile) -> None:
        self._profile = profile

    def get_agent(self, _agent_id: str):
        return self._profile


def _build_facade(
    mounts: list[CapabilityMount],
    *,
    override_repository=None,
    agent_profile_override_repository=None,
    agent_profile_service=None,
) -> CapabilityCatalogFacade:
    skill_service = SimpleNamespace(
        list_all_skills=lambda: [],
        list_available_skill_names=lambda: [],
        list_available_skills=lambda: [],
        read_skill_package_binding=lambda _skill: {
            "package_ref": None,
            "package_kind": None,
            "package_version": None,
        },
        enable_skill=lambda _name: None,
        disable_skill=lambda _name: None,
        delete_skill=lambda _name: True,
    )
    return CapabilityCatalogFacade(
        registry=_FakeRegistry(mounts),
        load_config_fn=lambda: SimpleNamespace(mcp=SimpleNamespace(clients={})),
        save_config_fn=lambda _config: None,
        skill_service=skill_service,
        override_repository=override_repository,
        agent_profile_service=agent_profile_service,
        agent_profile_override_repository=agent_profile_override_repository,
    )


def test_capability_catalog_summary_respects_overrides() -> None:
    facade = _build_facade(
        [
            CapabilityMount(
                id="tool:a",
                name="a",
                summary="A",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                enabled=True,
            ),
            CapabilityMount(
                id="tool:b",
                name="b",
                summary="B",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                enabled=True,
            ),
        ],
        override_repository=_OverrideRepository(
            [_Override("tool:b", enabled=False, forced_risk_level="confirm")],
        ),
    )

    summary = facade.summarize()
    mount = facade.get_capability("tool:b")

    assert summary.total == 2
    assert summary.enabled == 1
    assert mount is not None
    assert mount.enabled is False
    assert mount.risk_level == "confirm"
    assert mount.metadata["override"]["capability_id"] == "tool:b"


def test_capability_catalog_access_prefers_explicit_allowlist() -> None:
    facade = _build_facade(
        [
            CapabilityMount(
                id="tool:allowed",
                name="allowed",
                summary="Allowed",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                enabled=True,
                role_access_policy=["all"],
            ),
            CapabilityMount(
                id="tool:hidden",
                name="hidden",
                summary="Hidden",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                enabled=True,
                role_access_policy=["all"],
            ),
        ],
        agent_profile_override_repository=_AgentOverrideRepository(["tool:allowed"]),
    )

    mounts = facade.list_accessible_capabilities(
        agent_id="agent-1",
        enabled_only=True,
    )

    assert [mount.id for mount in mounts] == ["tool:allowed"]


def test_capability_catalog_access_prefers_merged_profile_capabilities_over_raw_override() -> None:
    facade = _build_facade(
        [
            CapabilityMount(
                id="tool:read_file",
                name="read_file",
                summary="Read file",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                enabled=True,
                role_access_policy=["all"],
            ),
            CapabilityMount(
                id="system:dispatch_query",
                name="dispatch_query",
                summary="Dispatch query",
                kind="system-op",
                source_kind="system",
                risk_level="guarded",
                enabled=True,
                role_access_policy=["operator"],
            ),
        ],
        agent_profile_override_repository=_AgentOverrideRepository(
            ["system:dispatch_query"],
        ),
        agent_profile_service=_AgentProfileService(
            SimpleNamespace(
                agent_id="copaw-agent-runner",
                capabilities=["system:dispatch_query", "tool:read_file"],
            ),
        ),
    )

    mounts = facade.list_accessible_capabilities(
        agent_id="copaw-agent-runner",
        enabled_only=True,
    )

    assert {mount.id for mount in mounts} == {
        "system:dispatch_query",
        "tool:read_file",
    }


def test_capability_catalog_public_inventory_uses_one_snapshot() -> None:
    drift_mount = CapabilityMount(
        id="mcp:drifted",
        name="drifted",
        summary="Drifted",
        kind="remote-mcp",
        source_kind="mcp",
        risk_level="guarded",
        enabled=True,
    )
    registry = _DriftingRegistry(
        [
            CapabilityMount(
                id="skill:research",
                name="research",
                summary="Research",
                kind="skill-bundle",
                source_kind="skill",
                risk_level="auto",
                enabled=True,
            ),
            CapabilityMount(
                id="system:hidden",
                name="hidden",
                summary="Hidden",
                kind="system-op",
                source_kind="system",
                risk_level="auto",
                enabled=True,
                metadata={"visibility": "internal"},
            ),
            CapabilityMount(
                id="system:browser_companion_runtime",
                name="browser_companion_runtime",
                summary="Browser companion runtime",
                kind="system-op",
                source_kind="system",
                risk_level="guarded",
                enabled=True,
            ),
        ],
        drift_mount=drift_mount,
    )
    skill_service = SimpleNamespace(
        list_all_skills=lambda: [],
        list_available_skill_names=lambda: [],
        list_available_skills=lambda: [],
        read_skill_package_binding=lambda _skill: {
            "package_ref": None,
            "package_kind": None,
            "package_version": None,
        },
        enable_skill=lambda _name: None,
        disable_skill=lambda _name: None,
        delete_skill=lambda _name: True,
    )
    facade = CapabilityCatalogFacade(
        registry=registry,
        load_config_fn=lambda: SimpleNamespace(mcp=SimpleNamespace(clients={})),
        save_config_fn=lambda _config: None,
        skill_service=skill_service,
        override_repository=None,
        agent_profile_service=None,
        agent_profile_override_repository=None,
    )

    mounts, summary = facade.list_public_capability_inventory()

    assert registry.read_count == 1
    assert [mount.id for mount in mounts] == ["skill:research"]
    assert summary.total == 1
    assert summary.enabled == 1
    assert summary.by_source == {"skill": 1}


def test_capability_catalog_binds_formal_package_fields() -> None:
    skill_content = """---
name: research
description: Research skill
package_ref: https://example.com/research-pack.zip
package_kind: hub-bundle
package_version: 1.2.3
---
# Research
"""
    skill_service = SimpleNamespace(
        list_all_skills=lambda: [
            SimpleNamespace(
                name="research",
                content=skill_content,
                source="customized",
                path="/tmp/research",
                references={},
                scripts={},
            ),
        ],
        list_available_skill_names=lambda: ["research"],
        list_available_skills=lambda: [],
        read_skill_package_binding=lambda _skill: {
            "package_ref": "https://example.com/research-pack.zip",
            "package_kind": "hub-bundle",
            "package_version": "1.2.3",
        },
        enable_skill=lambda _name: None,
        disable_skill=lambda _name: None,
        delete_skill=lambda _name: True,
    )
    config = SimpleNamespace(
        mcp=SimpleNamespace(
            clients={
                "filesystem": SimpleNamespace(
                    name="Filesystem MCP",
                    description="Filesystem tools",
                    enabled=True,
                    transport="stdio",
                    url="",
                    headers={},
                    command="npx",
                    args=["-y", "@scope/filesystem@1.0.0"],
                    env={},
                    cwd="",
                    registry=SimpleNamespace(
                        install_kind="package",
                        package_identifier="@scope/filesystem",
                        package_registry_type="npm",
                        remote_url="",
                        version="1.0.0",
                    ),
                ),
            },
        ),
    )
    facade = CapabilityCatalogFacade(
        registry=_FakeRegistry(
            [
                CapabilityMount(
                    id="skill:research",
                    name="research",
                    summary="Research",
                    kind="skill-bundle",
                    source_kind="skill",
                    risk_level="guarded",
                    enabled=True,
                ),
                CapabilityMount(
                    id="mcp:filesystem",
                    name="filesystem",
                    summary="Filesystem tools",
                    kind="remote-mcp",
                    source_kind="mcp",
                    risk_level="guarded",
                    enabled=True,
                ),
            ],
        ),
        load_config_fn=lambda: config,
        save_config_fn=lambda _config: None,
        skill_service=skill_service,
        override_repository=None,
        agent_profile_service=None,
        agent_profile_override_repository=None,
    )

    mounts = {mount.id: mount for mount in facade.list_capabilities()}

    assert mounts["skill:research"].package_ref == "https://example.com/research-pack.zip"
    assert mounts["skill:research"].package_kind == "hub-bundle"
    assert mounts["skill:research"].package_version == "1.2.3"
    assert mounts["mcp:filesystem"].package_ref == "@scope/filesystem"
    assert mounts["mcp:filesystem"].package_kind == "npm"
    assert mounts["mcp:filesystem"].package_version == "1.0.0"
