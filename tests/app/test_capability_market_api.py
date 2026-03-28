# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.capability_market import (
    CapabilityMarketCapabilityAssignmentResult,
    router as capability_market_router,
)
from copaw.capabilities import CapabilityMount, CapabilityService, CapabilitySummary
from copaw.capabilities.capability_discovery import (
    CapabilityDiscoveryService,
    _RemoteRecommendationAccumulator,
)
from copaw.capabilities.mcp_registry import (
    MaterializedMcpRegistryInstallPlan,
    McpRegistryCatalogDetailResponse,
    McpRegistryCatalogItem,
    McpRegistryCatalogSearchResponse,
    McpRegistryCategory,
    McpRegistryInstallOption,
)
from copaw.capabilities.remote_skill_catalog import (
    CuratedSkillCatalogEntry,
    CuratedSkillCatalogSearchResponse,
    CuratedSkillCatalogSource,
    clear_curated_skill_catalog_cache,
    search_curated_skill_catalog,
)
from copaw.config.config import MCPClientConfig, MCPRegistryProvenance
from copaw.evidence import EvidenceLedger
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.app.runtime_events import RuntimeEventBus
from copaw.industry import IndustryProfile, IndustryRoleBlueprint
from copaw.kernel import KernelDispatcher, KernelTaskStore
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


class FakeCapabilityService(CapabilityService):
    def __init__(self) -> None:
        super().__init__()
        self._mounts = [
            CapabilityMount(
                id="system:dispatch_query",
                name="Dispatch Query",
                summary="Run a managed query through the kernel.",
                kind="system-op",
                source_kind="system",
                risk_level="auto",
                environment_requirements=["session"],
                evidence_contract=["runtime-event"],
                role_access_policy=["execution-core"],
            ),
            CapabilityMount(
                id="skill:research",
                name="Research Skill",
                summary="Research the current topic.",
                kind="skill-bundle",
                source_kind="skill",
                risk_level="guarded",
            ),
        ]

    def list_capabilities(self, *, kind: str | None = None, enabled_only: bool = False):
        mounts = list(self._mounts)
        if kind is not None:
            mounts = [mount for mount in mounts if mount.kind == kind]
        if enabled_only:
            mounts = [mount for mount in mounts if mount.enabled]
        return mounts

    def summarize(self) -> CapabilitySummary:
        return CapabilitySummary(
            total=2,
            enabled=2,
            by_kind={"system-op": 1, "skill-bundle": 1},
            by_source={"system": 1, "skill": 1},
        )

    def list_skill_specs(self, *, enabled_only: bool = False):
        return [
            {
                "name": "research",
                "content": "# skill",
                "source": "customized",
                "path": "/tmp/research",
                "enabled": True,
                "references": {},
                "scripts": {},
            },
        ]

    def list_available_skill_specs(self):
        return self.list_skill_specs(enabled_only=True)

    def list_mcp_client_infos(self):
        return [
            {
                "key": "browser",
                "name": "Browser MCP",
                "description": "Remote browser automation",
                "enabled": True,
                "transport": "stdio",
                "url": "",
                "headers": {},
                "command": "browser-mcp",
                "args": ["--serve"],
                "env": {},
                "cwd": "",
                "registry": None,
            },
        ]


class DriftingCapabilityService(FakeCapabilityService):
    """Simulate a registry that changes between independent reads."""

    def __init__(self) -> None:
        super().__init__()
        self._public_read_count = 0

    def list_public_capabilities(
        self,
        *,
        kind: str | None = None,
        enabled_only: bool = False,
    ):
        self._public_read_count += 1
        mounts = super().list_capabilities(kind=kind, enabled_only=enabled_only)
        public_mounts = [mount for mount in mounts if mount.source_kind != "system"]
        if self._public_read_count >= 2:
            public_mounts.append(
                CapabilityMount(
                    id="mcp:filesystem-drifted",
                    name="Filesystem Drifted",
                    summary="A late-arriving capability should not desync the overview snapshot.",
                    kind="remote-mcp",
                    source_kind="mcp",
                    risk_level="guarded",
                ),
            )
        return public_mounts

    def summarize_public(self) -> CapabilitySummary:
        mounts = self.list_public_capabilities()
        by_kind: dict[str, int] = {}
        by_source: dict[str, int] = {}
        enabled = 0
        for mount in mounts:
            by_kind[mount.kind] = by_kind.get(mount.kind, 0) + 1
            by_source[mount.source_kind] = by_source.get(mount.source_kind, 0) + 1
            if mount.enabled:
                enabled += 1
        return CapabilitySummary(
            total=len(mounts),
            enabled=enabled,
            by_kind=by_kind,
            by_source=by_source,
        )


class FakeMcpRegistryCatalog:
    def __init__(self) -> None:
        self.catalog_version = "1.0.0"
        self.upgrade_version = "1.1.0"
        self.last_input_values: dict[str, object] = {}

    def list_catalog(
        self,
        *,
        installed_clients: dict[str, MCPClientConfig] | None = None,
        **_kwargs,
    ) -> McpRegistryCatalogSearchResponse:
        item = self._item(
            version=self.catalog_version,
            installed_clients=installed_clients,
        )
        return McpRegistryCatalogSearchResponse(
            items=[item],
            categories=[
                McpRegistryCategory(key="all", label="全部"),
                McpRegistryCategory(key="filesystem", label="文件"),
            ],
            cursor=None,
            next_cursor="next-cursor",
            has_more=True,
            page_size=12,
            warnings=[],
        )

    def get_catalog_detail(
        self,
        server_name: str,
        *,
        installed_clients: dict[str, MCPClientConfig] | None = None,
        **_kwargs,
    ) -> McpRegistryCatalogDetailResponse:
        return McpRegistryCatalogDetailResponse(
            item=self._item(
                version=self.catalog_version,
                server_name=server_name,
                installed_clients=installed_clients,
            ),
            install_options=[
                McpRegistryInstallOption(
                    key="package:test",
                    label="Filesystem / npm / 1.0.0",
                    summary="npm @scope/filesystem",
                    install_kind="package",
                    transport="stdio",
                    supported=True,
                    registry_type="npm",
                    identifier="@scope/filesystem",
                    version=self.catalog_version,
                    runtime_command="npx",
                    input_fields=[],
                ),
            ],
            categories=[
                McpRegistryCategory(key="all", label="全部"),
                McpRegistryCategory(key="filesystem", label="文件"),
            ],
        )

    def materialize_install_plan(
        self,
        server_name: str,
        *,
        option_key: str,
        input_values: dict[str, object] | None = None,
        client_key: str | None = None,
        enabled: bool = True,
        existing_client: MCPClientConfig | None = None,
    ) -> MaterializedMcpRegistryInstallPlan:
        version = self.catalog_version
        if existing_client is not None and existing_client.registry is not None:
            version = self.upgrade_version
        self.last_input_values = dict(input_values or {})
        registry = MCPRegistryProvenance(
            server_name=server_name,
            version=version,
            option_key=option_key,
            install_kind="package",
            input_values=dict(input_values or {}),
            package_identifier="@scope/filesystem",
            package_registry_type="npm",
            catalog_categories=["filesystem"],
        )
        client = MCPClientConfig(
            name="Filesystem MCP",
            description="Official filesystem server",
            enabled=enabled,
            transport="stdio",
            command="npx",
            args=["-y", "@scope/filesystem@" + version],
            env={},
            registry=registry,
        )
        return MaterializedMcpRegistryInstallPlan(
            client_key=client_key or "io_github_example_filesystem",
            client=client,
            registry=registry,
            summary=f"{server_name} -> {version}",
            version_changed=bool(existing_client and existing_client.registry and existing_client.registry.version != version),
            previous_version=(
                existing_client.registry.version
                if existing_client is not None and existing_client.registry is not None
                else ""
            ),
        )

    def _item(
        self,
        *,
        version: str,
        server_name: str = "io.github/example-filesystem",
        installed_clients: dict[str, MCPClientConfig] | None = None,
    ) -> McpRegistryCatalogItem:
        installed_client_key = None
        installed_version = ""
        installed_via_registry = False
        update_available = False
        for client_key, client in dict(installed_clients or {}).items():
            registry = getattr(client, "registry", None)
            if registry is None:
                continue
            if getattr(registry, "server_name", None) != server_name:
                continue
            installed_client_key = client_key
            installed_version = str(getattr(registry, "version", "") or "")
            installed_via_registry = True
            update_available = bool(installed_version and installed_version != version)
            break
        return McpRegistryCatalogItem(
            server_name=server_name,
            title="Filesystem MCP",
            description="Official filesystem server",
            version=version,
            source_url="https://registry.modelcontextprotocol.io/v0/servers/io.github%2Fexample-filesystem/versions/latest",
            repository_url="https://github.com/example/filesystem",
            website_url="",
            category_keys=["filesystem"],
            transport_types=["stdio"],
            suggested_client_key="io_github_example_filesystem",
            option_count=1,
            supported_option_count=1,
            install_supported=True,
            installed_client_key=installed_client_key,
            installed_via_registry=installed_via_registry,
            installed_version=installed_version,
            update_available=update_available,
            routes={
                "detail": "/api/capability-market/mcp/catalog/io.github/example-filesystem",
                "install": "/api/capability-market/mcp/catalog/io.github/example-filesystem/install",
            },
        )


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(capability_market_router)
    app.state.capability_service = FakeCapabilityService()
    app.state.mcp_registry_catalog = FakeMcpRegistryCatalog()
    return app


def build_runtime_app(tmp_path) -> FastAPI:
    app = FastAPI()
    app.include_router(capability_market_router)
    state_store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    environment_repository = EnvironmentRepository(state_store)
    session_mount_repository = SessionMountRepository(state_store)
    environment_registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_mount_repository,
    )
    environment_service = EnvironmentService(registry=environment_registry)
    environment_service.set_session_repository(session_mount_repository)
    runtime_event_bus = RuntimeEventBus()
    environment_service.set_runtime_event_bus(runtime_event_bus)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    capability_service = CapabilityService()
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        capability_service=capability_service,
        task_store=task_store,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    app.state.decision_request_repository = decision_request_repository
    app.state.state_store = state_store
    app.state.environment_service = environment_service
    app.state.runtime_event_bus = runtime_event_bus
    app.state.mcp_registry_catalog = FakeMcpRegistryCatalog()
    return app


def _fake_tool_response(payload: str):
    return type(
        "FakeToolResponse",
        (),
        {"content": [{"text": payload}]},
    )()


def test_capability_market_overview_aggregates_existing_sources() -> None:
    client = TestClient(build_app())

    response = client.get("/capability-market/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total"] == len(payload["installed"])
    assert payload["summary"]["by_kind"]["skill-bundle"] >= 1
    assert payload["summary"]["by_kind"]["remote-mcp"] >= 1
    assert any(item["source_kind"] == "skill" for item in payload["installed"])
    assert any(item["name"] == "research" for item in payload["skills"])
    assert any(item["key"] == "browser" for item in payload["mcp_clients"])
    assert payload["routes"]["capabilities"] == "/api/capability-market/capabilities"
    assert payload["routes"]["skills"] == "/api/capability-market/skills"
    assert payload["routes"]["mcp"] == "/api/capability-market/mcp"
    assert payload["routes"]["mcp_catalog"] == "/api/capability-market/mcp/catalog"
    assert (
        payload["routes"]["install_templates"]
        == "/api/capability-market/install-templates"
    )


def test_capability_market_overview_uses_one_public_snapshot_for_summary() -> None:
    app = FastAPI()
    app.include_router(capability_market_router)
    app.state.capability_service = DriftingCapabilityService()
    app.state.mcp_registry_catalog = FakeMcpRegistryCatalog()
    client = TestClient(app)

    response = client.get("/capability-market/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total"] == len(payload["installed"])
    assert payload["summary"]["by_kind"] == {"skill-bundle": 1}
    assert payload["summary"]["by_source"] == {
        "skill": 1,
    }
    assert [item["id"] for item in payload["installed"]] == ["skill:research"]
    assert (
        payload["routes"]["curated_catalog"]
        == "/api/capability-market/curated-catalog"
    )
    assert payload["routes"]["hub_install"] == "/api/capability-market/hub/install"


def test_capability_market_read_surfaces_expose_canonical_lists() -> None:
    client = TestClient(build_app())

    capabilities = client.get("/capability-market/capabilities", params={"kind": "skill-bundle"})
    summary = client.get("/capability-market/capabilities/summary")
    skills = client.get("/capability-market/skills")
    mcp = client.get("/capability-market/mcp")

    assert capabilities.status_code == 200
    capability_items = capabilities.json()
    assert capability_items
    assert all(item["kind"] == "skill-bundle" for item in capability_items)
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["total"] == sum(summary_payload["by_kind"].values())
    assert summary_payload["by_kind"]["skill-bundle"] == len(capability_items)
    assert skills.status_code == 200
    assert any(item["name"] == "research" and item["source"] == "customized" for item in skills.json())
    assert mcp.status_code == 200
    assert any(item["key"] == "browser" and item["transport"] == "stdio" for item in mcp.json())


def test_capability_market_mcp_catalog_exposes_registry_search_and_detail() -> None:
    client = TestClient(build_app())

    listing = client.get(
        "/capability-market/mcp/catalog",
        params={"q": "filesystem", "category": "filesystem"},
    )
    detail = client.get("/capability-market/mcp/catalog/io.github/example-filesystem")

    assert listing.status_code == 200
    listing_payload = listing.json()
    assert listing_payload["items"][0]["server_name"] == "io.github/example-filesystem"
    assert listing_payload["items"][0]["install_supported"] is True
    assert listing_payload["has_more"] is True
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["item"]["title"] == "Filesystem MCP"
    assert detail_payload["install_options"][0]["key"] == "package:test"


def test_capability_discovery_query_mode_returns_official_mcp_catalog() -> None:
    service = CapabilityDiscoveryService()
    service.set_mcp_registry_catalog(FakeMcpRegistryCatalog())

    with patch(
        "copaw.capabilities.capability_discovery.load_config",
        return_value=SimpleNamespace(mcp=SimpleNamespace(clients={})),
    ):
        payload = asyncio.run(
            service.discover(
                {
                    "queries": ["filesystem mcp"],
                    "providers": ["mcp-registry"],
                },
            ),
        )

    assert payload["success"] is True
    assert payload["mode"] == "query"
    assert payload["mcp_catalog"]
    assert payload["mcp_catalog"][0]["server_name"] == "io.github/example-filesystem"


def test_capability_discovery_role_mode_returns_actionable_mcp_registry_upgrade() -> None:
    service = CapabilityDiscoveryService()
    service.set_mcp_registry_catalog(FakeMcpRegistryCatalog())
    config = SimpleNamespace(
        mcp=SimpleNamespace(
            clients={
                "io_github_example_filesystem": MCPClientConfig(
                    name="Filesystem MCP",
                    enabled=True,
                    transport="stdio",
                    command="npx",
                    args=["-y", "@scope/filesystem@0.9.0"],
                    env={},
                    registry=MCPRegistryProvenance(
                        server_name="io.github/example-filesystem",
                        version="0.9.0",
                        option_key="package:test",
                        install_kind="package",
                        input_values={},
                    ),
                ),
            },
        ),
    )
    profile = IndustryProfile(
        industry="Customer Operations",
        company_name="Northwind Robotics",
        product="Filesystem-based onboarding sync",
        goals=["Use filesystem MCP to sync onboarding files"],
    )
    role = IndustryRoleBlueprint(
        role_id="operations-lead",
        agent_id="industry-operations-lead-northwind",
        name="Northwind Operations Lead",
        role_name="Operations Lead",
        role_summary="Owns filesystem sync and workspace automation.",
        mission="Use filesystem MCP to sync local files and shared assets.",
        goal_kind="operations",
        agent_class="business",
        risk_level="guarded",
        allowed_capabilities=[],
        evidence_expectations=["filesystem sync note"],
    )

    with patch(
        "copaw.capabilities.capability_discovery.load_config",
        return_value=config,
    ):
        payload = asyncio.run(
            service.discover(
                {
                    "industry_profile": profile.model_dump(mode="json"),
                    "role": role.model_dump(mode="json"),
                    "goal_context": [
                        "Need filesystem access to read and update onboarding files.",
                    ],
                    "providers": ["mcp-registry"],
                },
            ),
        )

    assert payload["success"] is True
    assert payload["mode"] == "role"
    recommendation = next(
        item
        for item in payload["recommendations"]
        if item["install_kind"] == "mcp-registry"
    )
    assert recommendation["template_id"] == "io.github/example-filesystem"
    assert recommendation["install_option_key"] == "package:test"
    assert recommendation["default_client_key"] == "io_github_example_filesystem"
    assert recommendation["installed"] is False
    assert recommendation["governance_path"][1] == "system:update_mcp_client"


def test_remote_recommendation_accumulator_merges_queries_signals_and_families() -> None:
    accumulator = _RemoteRecommendationAccumulator(
        per_role_match_limit=1,
        family_coverage_target=2,
    )
    role_a = SimpleNamespace(agent_id="agent-a")
    role_b = SimpleNamespace(agent_id="agent-b")

    assert accumulator.accepts(
        key="hub:skill-a",
        candidate_family="browser",
    )
    entry = accumulator.merge(
        key="hub:skill-a",
        seed_entry={"result": "skill-a"},
        role=role_a,
        signals=["explicit-query"],
        query="browser login automation",
        candidate_family="browser",
        matched_families=["browser", "workflow"],
    )

    assert entry["queries"] == ["browser login automation"]
    assert entry["signals"] == ["explicit-query"]
    assert entry["matched_families"] == ["browser", "workflow"]
    assert len(entry["matched_roles"]) == 1
    assert not accumulator.is_saturated()

    merged = accumulator.merge(
        key="hub:skill-a",
        seed_entry={"result": "skill-a"},
        role=role_b,
        signals=["goal-match"],
        query="browser data sync",
        candidate_family="workflow",
        matched_families=["workflow"],
    )

    assert merged is entry
    assert entry["queries"] == ["browser login automation", "browser data sync"]
    assert entry["signals"] == ["explicit-query", "goal-match"]
    assert entry["matched_families"] == ["browser", "workflow"]
    assert [item[0].agent_id for item in entry["matched_roles"]] == ["agent-a", "agent-b"]
    assert accumulator.accepted_keys == {"hub:skill-a"}
    assert accumulator.accepted_families == {"browser", "workflow"}
    assert accumulator.is_saturated()


def test_capability_market_install_templates_expose_productized_surface() -> None:
    client = TestClient(build_app())

    templates = client.get("/capability-market/install-templates")
    detail = client.get("/capability-market/install-templates/desktop-windows")

    assert templates.status_code == 200
    payload = templates.json()
    assert payload[0]["id"] == "desktop-windows"
    assert payload[0]["install_kind"] == "mcp-template"
    assert payload[0]["default_assignment_policy"] == "selected-agents-only"
    assert payload[0]["routes"]["detail"] == (
        "/api/capability-market/install-templates/desktop-windows"
    )
    assert payload[0]["routes"]["install"] == (
        "/api/capability-market/install-templates/desktop-windows/install"
    )
    assert "mcp_template" not in payload[0]["routes"]
    assert any(item["id"] == "browser-local" for item in payload)
    assert any(item["id"] == "browser-companion" for item in payload)
    assert any(item["id"] == "document-office-bridge" for item in payload)
    assert any(item["id"] == "host-watchers" for item in payload)
    assert any(item["id"] == "windows-app-adapters" for item in payload)

    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["platform"] == "windows"
    assert detail_payload["installed"] is False
    assert detail_payload["manifest"]["capability_ids"] == ["mcp:desktop_windows"]
    assert "legacy_install" not in detail_payload["routes"]


def test_capability_market_cooperative_adapter_templates_expose_phase2_runtime_surface(
    tmp_path,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))

    templates = client.get("/capability-market/install-templates")
    browser_companion = client.get("/capability-market/install-templates/browser-companion")
    document_bridge = client.get("/capability-market/install-templates/document-office-bridge")
    host_watchers = client.get("/capability-market/install-templates/host-watchers")
    windows_apps = client.get("/capability-market/install-templates/windows-app-adapters")

    assert templates.status_code == 200
    payload = {item["id"]: item for item in templates.json()}
    assert payload["browser-companion"]["install_kind"] == "builtin-runtime"
    assert payload["browser-companion"]["source_kind"] == "system"
    assert payload["document-office-bridge"]["default_capability_id"] == (
        "system:document_bridge_runtime"
    )
    assert payload["host-watchers"]["default_capability_id"] == "system:host_watchers_runtime"
    assert payload["windows-app-adapters"]["default_capability_id"] == (
        "system:windows_app_adapter_runtime"
    )

    assert browser_companion.status_code == 200
    assert browser_companion.json()["routes"]["doctor"] == (
        "/api/capability-market/install-templates/browser-companion/doctor"
    )
    assert browser_companion.json()["routes"]["example_run"] == (
        "/api/capability-market/install-templates/browser-companion/example-run"
    )
    assert browser_companion.json()["manifest"]["capability_ids"] == [
        "system:browser_companion_runtime"
    ]

    assert document_bridge.status_code == 200
    assert document_bridge.json()["manifest"]["capability_ids"] == [
        "system:document_bridge_runtime"
    ]
    assert document_bridge.json()["config_schema"]["scope"] == "runtime"

    assert host_watchers.status_code == 200
    assert host_watchers.json()["manifest"]["capability_ids"] == [
        "system:host_watchers_runtime"
    ]

    assert windows_apps.status_code == 200
    assert windows_apps.json()["manifest"]["capability_ids"] == [
        "system:windows_app_adapter_runtime"
    ]


def test_capability_market_browser_local_surface_exposes_runtime_contract() -> None:
    client = TestClient(build_app())

    with (
        patch(
            "copaw.capabilities.install_templates.get_browser_support_snapshot",
            return_value={
                "running": False,
                "playwright_ready": True,
                "playwright_error": "",
                "container_mode": False,
                "default_browser_kind": "chromium",
                "default_browser_path": "C:/Program Files/Browser/browser.exe",
            },
        ),
        patch(
            "copaw.capabilities.install_templates.get_browser_runtime_snapshot",
            return_value={
                "running": False,
                "headless": True,
                "current_page_id": None,
                "page_count": 0,
                "page_ids": [],
            },
        ),
    ):
        detail = client.get("/capability-market/install-templates/browser-local")

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["install_kind"] == "builtin-runtime"
    assert payload["source_kind"] == "tool"
    assert payload["default_capability_id"] == "tool:browser_use"
    assert payload["routes"]["doctor"] == (
        "/api/capability-market/install-templates/browser-local/doctor"
    )
    assert payload["routes"]["example_run"] == (
        "/api/capability-market/install-templates/browser-local/example-run"
    )


def test_capability_market_install_template_doctor_and_example_run() -> None:
    client = TestClient(build_app())

    with (
        patch(
            "copaw.capabilities.install_templates.get_browser_support_snapshot",
            return_value={
                "running": False,
                "playwright_ready": True,
                "playwright_error": "",
                "container_mode": False,
                "default_browser_kind": "chromium",
                "default_browser_path": "",
            },
        ),
        patch(
            "copaw.capabilities.install_templates.get_browser_runtime_snapshot",
            side_effect=[
                {
                    "running": False,
                    "headless": True,
                    "current_page_id": None,
                    "page_count": 0,
                    "page_ids": [],
                },
                {
                    "running": False,
                    "headless": True,
                    "current_page_id": None,
                    "page_count": 0,
                    "page_ids": [],
                },
                {
                    "running": False,
                    "headless": True,
                    "current_page_id": None,
                    "page_count": 0,
                    "page_ids": [],
                },
            ],
        ),
        patch(
            "copaw.capabilities.install_templates.browser_use",
        ) as mocked_browser_use,
    ):
        mocked_browser_use.side_effect = [
            type(
                "FakeToolResponse",
                (),
                {"content": [{"text": '{"ok": true, "message": "Browser started"}'}]},
            )(),
            type(
                "FakeToolResponse",
                (),
                {"content": [{"text": '{"ok": true, "message": "Browser stopped"}'}]},
            )(),
        ]
        doctor = client.get("/capability-market/install-templates/browser-local/doctor")
        example = client.post("/capability-market/install-templates/browser-local/example-run")

    assert doctor.status_code == 200
    assert doctor.json()["template_id"] == "browser-local"
    assert example.status_code == 200
    payload = example.json()
    assert payload["template_id"] == "browser-local"
    assert payload["status"] == "success"
    assert payload["operations"] == ["start", "stop"]


def test_capability_market_hub_search_proxies_skill_hub() -> None:
    client = TestClient(build_app())

    with patch("copaw.app.routers.capability_market.search_hub_skills") as mocked:
        mocked.return_value = [
            type(
                "HubResult",
                (),
                {
                    "slug": "research-pack",
                    "name": "Research Pack",
                    "description": "Collected research helpers",
                    "version": "1.0.0",
                    "source_url": "https://example.com/research-pack",
                },
            )(),
        ]
        response = client.get("/capability-market/hub/search?q=research")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["slug"] == "research-pack"
    assert payload[0]["source_url"] == "https://example.com/research-pack"


def test_capability_market_curated_catalog_exposes_allowlisted_sources() -> None:
    client = TestClient(build_app())

    response_payload = CuratedSkillCatalogSearchResponse(
        sources=[
            CuratedSkillCatalogSource(
                source_id="skillhub-featured-research",
                label="SkillHub 精选·研究分析",
                source_kind="skillhub-curated",
                query="research",
                notes=["来自 SkillHub 商店的研究分析精选。"],
            ),
        ],
        items=[
            CuratedSkillCatalogEntry(
                candidate_id="research-pack",
                source_id="skillhub-featured-research",
                source_label="SkillHub 精选·研究分析",
                source_kind="skillhub-curated",
                source_repo_url="https://lightmake.site",
                discovery_kind="skillhub-preset",
                manifest_status="skillhub-curated",
                title="研究分析工具",
                description="Curated research workflow skill",
                bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/research-pack.zip",
                version="1.0.0",
                install_name="research_pack",
                tags=["research"],
                capability_tags=["skill", "skillhub-curated"],
                review_required=False,
                review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
                review_notes=["研究分析精选。"],
                routes={},
            ),
        ],
        warnings=[],
    )

    with patch(
        "copaw.app.routers.capability_market.search_curated_skill_catalog",
        return_value=response_payload,
    ):
        response = client.get("/capability-market/curated-catalog?q=salesforce")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"][0]["source_id"] == "skillhub-featured-research"
    assert payload["items"][0]["source_kind"] == "skillhub-curated"
    assert payload["items"][0]["manifest_status"] == "skillhub-curated"
    assert payload["warnings"] == []


def test_search_curated_skill_catalog_uses_skillhub_dynamic_source() -> None:
    clear_curated_skill_catalog_cache()
    with patch(
        "copaw.capabilities.remote_skill_catalog.search_skillhub_skills",
        return_value=[
            SimpleNamespace(
                slug="research-pack",
                name="Research Pack",
                description="Collect research signals and summarize findings.",
                version="1.0.0",
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/research-pack.zip",
                source_label="SkillHub 商店",
                score=9.7,
            ),
        ],
    ):
        payload = search_curated_skill_catalog("salesforce", limit=8)

    assert payload.warnings == []
    assert payload.sources[0].source_id.startswith("skillhub-search:")
    assert payload.items[0].manifest_status == "skillhub-curated"
    assert payload.items[0].source_kind == "skillhub-curated"
    assert payload.items[0].bundle_url.endswith("/skills/research-pack.zip")
    clear_curated_skill_catalog_cache()


def test_search_curated_skill_catalog_aggregates_skillhub_featured_sources() -> None:
    clear_curated_skill_catalog_cache()
    def _fake_search(query: str, limit: int = 20):
        _ = limit
        mapping = {
            "automation": [
                SimpleNamespace(
                    slug="find-skills",
                    name="Find Skills",
                    description="Discover remote skills by task.",
                    version="1.0.0",
                    source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/find-skills.zip",
                    source_label="SkillHub 商店",
                    score=10.0,
                )
            ],
            "browser automation": [
                SimpleNamespace(
                    slug="browser-use",
                    name="Browser Use",
                    description="Automate browser login and form actions.",
                    version="1.0.0",
                    source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/browser-use.zip",
                    source_label="SkillHub 商店",
                    score=9.3,
                )
            ],
        }
        return mapping.get(query, [])

    with patch(
        "copaw.capabilities.remote_skill_catalog.search_skillhub_skills",
        side_effect=_fake_search,
    ):
        payload = search_curated_skill_catalog("excel", limit=8)

    with patch(
        "copaw.capabilities.remote_skill_catalog.search_skillhub_skills",
        side_effect=_fake_search,
    ):
        featured_payload = search_curated_skill_catalog("", limit=8)

    assert payload.warnings == []
    assert payload.items == []
    assert featured_payload.warnings == []
    assert any(item.source_id == "skillhub-featured-core" for item in featured_payload.items)
    assert any(item.source_id == "skillhub-featured-browser" for item in featured_payload.items)
    clear_curated_skill_catalog_cache()


def test_capability_market_curated_install_requires_review_ack(tmp_path) -> None:
    client = TestClient(build_runtime_app(tmp_path))

    candidate = CuratedSkillCatalogEntry(
        candidate_id="research-pack",
        source_id="skillhub-featured-research",
        source_label="SkillHub 精选·研究分析",
        source_kind="skillhub-curated",
        source_repo_url="https://lightmake.site",
        discovery_kind="skillhub-preset",
        manifest_status="skillhub-curated",
        title="研究分析工具",
        description="Curated research workflow skill",
        bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/research-pack.zip",
        version="1.0.0",
        install_name="research_pack",
        tags=["research"],
        capability_tags=["skill", "skillhub-curated"],
        review_required=True,
        review_summary="Review before install",
        review_notes=["Curated review gate"],
        routes={},
    )

    with patch(
        "copaw.app.routers.capability_market.get_curated_skill_catalog_entry",
        return_value=candidate,
    ):
        response = client.post(
            "/capability-market/curated-catalog/install",
            json={
                "source_id": "skillhub-featured-research",
                "candidate_id": "research-pack",
                "review_acknowledged": False,
            },
        )

    assert response.status_code == 400
    assert "安装前需要操作方确认" in response.json()["detail"]


def test_capability_market_curated_install_assigns_capabilities_to_target_agents(
    tmp_path,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))

    candidate = CuratedSkillCatalogEntry(
        candidate_id="research-pack",
        source_id="skillhub-featured-research",
        source_label="SkillHub 精选·研究分析",
        source_kind="skillhub-curated",
        source_repo_url="https://lightmake.site",
        discovery_kind="skillhub-preset",
        manifest_status="skillhub-curated",
        title="研究分析工具",
        description="Curated research workflow skill",
        bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/research-pack.zip",
        version="1.0.0",
        install_name="research_pack",
        tags=["research"],
        capability_tags=["skill", "skillhub-curated"],
        review_required=True,
        review_summary="Review before install",
        review_notes=["Curated review gate"],
        routes={},
    )

    with (
        patch(
            "copaw.app.routers.capability_market.get_curated_skill_catalog_entry",
            return_value=candidate,
        ),
        patch(
            "copaw.app.routers.capability_market._resolve_remote_skill_capability_ids",
            return_value=["skill:salesforce"],
        ),
        patch(
            "copaw.app.routers.capability_market._dispatch_market_mutation",
            return_value={
                "success": True,
                "installed": True,
                "name": "research_pack",
                "enabled": True,
                "source_url": "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/research-pack.zip",
                "summary": "Installed skill 'research_pack' from hub.",
            },
        ),
        patch(
            "copaw.app.routers.capability_market._assign_capabilities_to_agents",
            return_value=[
                CapabilityMarketCapabilityAssignmentResult(
                    agent_id="agent-sales",
                    capability_ids=["skill:salesforce"],
                    mode="merge",
                    success=True,
                    summary="assigned",
                    routes={"agent": "/api/runtime-center/agents/agent-sales"},
                ),
            ],
        ),
    ):
        response = client.post(
            "/capability-market/curated-catalog/install",
            json={
                "source_id": "skillhub-featured-research",
                "candidate_id": "research-pack",
                "review_acknowledged": True,
                "target_agent_ids": ["agent-sales"],
                "capability_assignment_mode": "merge",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["installed"] is True
    assert payload["assigned_capability_ids"] == ["skill:salesforce"]
    assert payload["assignment_results"][0]["agent_id"] == "agent-sales"


def test_capability_market_install_template_config_is_applied_to_desktop_install(
    tmp_path,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))
    config = SimpleNamespace(mcp=SimpleNamespace(clients={}))

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
    ):
        response = client.post(
            "/capability-market/install-templates/desktop-windows/install",
            json={
                "config": {
                    "command": "pwsh",
                    "args": ["-File", "desktop-host.ps1"],
                    "enabled": True,
                },
            },
        )
        mcp_listing = client.get("/capability-market/mcp")

    assert response.status_code == 201
    payload = response.json()
    assert payload["template_id"] == "desktop-windows"
    assert payload["install_status"] == "installed"
    assert payload["target_ref"] == "desktop_windows"

    assert mcp_listing.status_code == 200
    desktop_client = next(
        item for item in mcp_listing.json() if item["key"] == "desktop_windows"
    )
    assert desktop_client["command"] == "pwsh"
    assert desktop_client["args"] == ["-File", "desktop-host.ps1"]
    assert desktop_client["enabled"] is True


def test_capability_market_mcp_registry_install_persists_registry_provenance(
    tmp_path,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))
    config = SimpleNamespace(mcp=SimpleNamespace(clients={}))

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
        patch("copaw.app.routers.capability_market.load_config", return_value=config),
    ):
        response = client.post(
            "/capability-market/mcp/catalog/io.github/example-filesystem/install",
            json={
                "option_key": "package:test",
                "input_values": {"environment:WORKSPACE_ROOT": "D:/workspace"},
            },
        )
        listing = client.get("/capability-market/mcp")

    assert response.status_code == 201
    payload = response.json()
    assert payload["install_status"] == "installed"
    assert payload["server_name"] == "io.github/example-filesystem"
    assert payload["registry_version"] == "1.0.0"

    assert listing.status_code == 200
    installed = next(
        item
        for item in listing.json()
        if item["key"] == "io_github_example_filesystem"
    )
    assert installed["registry"]["server_name"] == "io.github/example-filesystem"
    assert installed["registry"]["version"] == "1.0.0"


def test_capability_market_mcp_registry_upgrade_updates_version(
    tmp_path,
) -> None:
    app = build_runtime_app(tmp_path)
    client = TestClient(app)
    config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
    registry_catalog = app.state.mcp_registry_catalog

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
        patch("copaw.app.routers.capability_market.load_config", return_value=config),
    ):
        installed = client.post(
            "/capability-market/mcp/catalog/io.github/example-filesystem/install",
            json={"option_key": "package:test"},
        )
        assert installed.status_code == 201

        registry_catalog.catalog_version = "1.1.0"
        registry_catalog.upgrade_version = "1.1.0"

        upgraded = client.post(
            "/capability-market/mcp/io_github_example_filesystem/upgrade",
            json={},
        )
        listing = client.get("/capability-market/mcp")

    assert upgraded.status_code == 200
    payload = upgraded.json()
    assert payload["upgraded"] is True
    assert payload["previous_version"] == "1.0.0"
    assert payload["registry_version"] == "1.1.0"

    installed = next(
        item
        for item in listing.json()
        if item["key"] == "io_github_example_filesystem"
    )
    assert installed["registry"]["version"] == "1.1.0"


def test_capability_market_browser_local_install_persists_profile_and_sessions(
    tmp_path,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))

    installed = client.post(
        "/capability-market/install-templates/browser-local/install",
        json={
            "config": {
                "profile_id": "sales-browser",
                "profile_label": "Sales Browser",
                "entry_url": "https://example.com/login",
                "headed": True,
                "reuse_running_session": False,
                "persist_login_state": True,
            },
        },
    )
    assert installed.status_code == 201
    install_payload = installed.json()
    assert install_payload["template_id"] == "browser-local"
    assert install_payload["target_ref"] == "sales-browser"
    assert install_payload["ready"] is True

    profiles = client.get("/capability-market/install-templates/browser-local/profiles")
    assert profiles.status_code == 200
    profile = next(
        item for item in profiles.json() if item["profile_id"] == "sales-browser"
    )
    assert profile["label"] == "Sales Browser"
    assert profile["entry_url"] == "https://example.com/login"
    assert profile["headed"] is True
    assert profile["reuse_running_session"] is False
    assert profile["persist_login_state"] is True
    assert profile["is_default"] is True

    detail = client.get("/capability-market/install-templates/browser-local")
    assert detail.status_code == 200
    assert detail.json()["support"]["profile_count"] == 1

    with (
        patch(
            "copaw.capabilities.browser_runtime.get_browser_runtime_snapshot",
            side_effect=[
                {
                    "running": False,
                    "headless": False,
                    "current_session_id": None,
                    "session_count": 0,
                    "sessions": [],
                    "current_page_id": None,
                    "page_count": 0,
                    "page_ids": [],
                },
                {
                    "running": True,
                    "headless": False,
                    "current_session_id": "market-browser-session",
                    "session_count": 1,
                    "sessions": [
                        {
                            "session_id": "market-browser-session",
                            "profile_id": "sales-browser",
                            "entry_url": "https://example.com/login",
                            "persist_login_state": True,
                            "current_page_id": "page-1",
                            "page_count": 1,
                            "page_ids": ["page-1"],
                        }
                    ],
                    "current_page_id": "page-1",
                    "page_count": 1,
                    "page_ids": ["page-1"],
                },
            ],
        ),
        patch(
            "copaw.capabilities.browser_runtime.browser_use",
            return_value=_fake_tool_response('{"ok": true, "message": "started"}'),
        ) as mocked_browser_use,
    ):
        started = client.post(
            "/capability-market/install-templates/browser-local/sessions/start",
            json={"session_id": "market-browser-session"},
        )

    assert started.status_code == 200
    started_payload = started.json()
    assert started_payload["status"] == "started"
    assert started_payload["profile_id"] == "sales-browser"
    assert mocked_browser_use.call_args.kwargs["profile_id"] == "sales-browser"
    assert mocked_browser_use.call_args.kwargs["headed"] is True
    assert (
        mocked_browser_use.call_args.kwargs["entry_url"]
        == "https://example.com/login"
    )
    assert mocked_browser_use.call_args.kwargs["persist_login_state"] is True

    with (
        patch(
            "copaw.capabilities.browser_runtime.attach_browser_session",
            return_value={"ok": True, "session_id": "market-browser-session"},
        ) as mocked_attach,
        patch(
            "copaw.capabilities.browser_runtime.get_browser_runtime_snapshot",
            return_value={
                "running": True,
                "headless": False,
                "current_session_id": "market-browser-session",
                "session_count": 1,
                "sessions": [
                    {
                        "session_id": "market-browser-session",
                        "profile_id": "sales-browser",
                        "entry_url": "https://example.com/login",
                        "persist_login_state": True,
                        "current_page_id": "page-1",
                        "page_count": 1,
                        "page_ids": ["page-1"],
                    }
                ],
                "current_page_id": "page-1",
                "page_count": 1,
                "page_ids": ["page-1"],
            },
        ),
    ):
        attached = client.post(
            "/capability-market/install-templates/browser-local/sessions/market-browser-session/attach",
        )

    assert attached.status_code == 200
    assert attached.json()["result"]["ok"] is True
    mocked_attach.assert_called_once_with("market-browser-session")

    with (
        patch(
            "copaw.capabilities.browser_runtime.browser_use",
            return_value=_fake_tool_response('{"ok": true, "message": "stopped"}'),
        ) as mocked_stop,
        patch(
            "copaw.capabilities.browser_runtime.get_browser_runtime_snapshot",
            return_value={
                "running": False,
                "headless": False,
                "current_session_id": None,
                "session_count": 0,
                "sessions": [],
                "current_page_id": None,
                "page_count": 0,
                "page_ids": [],
            },
        ),
    ):
        stopped = client.post(
            "/capability-market/install-templates/browser-local/sessions/market-browser-session/stop",
        )

    assert stopped.status_code == 200
    assert stopped.json()["result"]["ok"] is True
    assert mocked_stop.call_args.kwargs["action"] == "stop"
    assert mocked_stop.call_args.kwargs["session_id"] == "market-browser-session"

    with patch(
        "copaw.capabilities.browser_runtime.get_browser_runtime_snapshot",
        return_value={
            "running": False,
            "headless": False,
            "current_session_id": None,
            "session_count": 0,
            "sessions": [],
            "current_page_id": None,
            "page_count": 0,
            "page_ids": [],
        },
    ):
        sessions = client.get("/capability-market/install-templates/browser-local/sessions")

    assert sessions.status_code == 200
    sessions_payload = sessions.json()
    assert sessions_payload["session_count"] == 0
    assert sessions_payload["profiles"][0]["profile_id"] == "sales-browser"


def test_capability_market_browser_local_install_defaults_to_visible_profile(
    tmp_path,
) -> None:
    client = TestClient(build_runtime_app(tmp_path))

    installed = client.post("/capability-market/install-templates/browser-local/install", json={})

    assert installed.status_code == 201

    profiles = client.get("/capability-market/install-templates/browser-local/profiles")
    assert profiles.status_code == 200
    profile = next(
        item for item in profiles.json() if item["profile_id"] == "browser-local-default"
    )
    assert profile["headed"] is True
