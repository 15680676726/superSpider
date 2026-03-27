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


def _build_facade(
    mounts: list[CapabilityMount],
    *,
    override_repository=None,
    agent_profile_override_repository=None,
) -> CapabilityCatalogFacade:
    skill_service = SimpleNamespace(
        list_all_skills=lambda: [],
        list_available_skill_names=lambda: [],
        list_available_skills=lambda: [],
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
        agent_profile_service=None,
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
