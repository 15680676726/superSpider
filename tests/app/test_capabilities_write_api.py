# -*- coding: utf-8 -*-
"""Tests for the unified capability toggle and delete endpoints."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.runtime_center import Phase1StateQueryService
from copaw.app.routers.agent import router as agent_router
from copaw.app.routers.capability_market import router as capability_market_router
from copaw.app.routers.capabilities import router as capabilities_router
from copaw.app.routers.config import router as config_router
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.capabilities import CapabilityMount, CapabilityService
from copaw.capabilities.sources.system import (
    list_system_capabilities as list_builtin_system_capabilities,
)
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelDispatcher, KernelTaskStore
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def build_app(tmp_path) -> FastAPI:
    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(capability_market_router)
    app.include_router(capabilities_router)
    app.include_router(config_router)
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )

    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    app.state.state_query_service = Phase1StateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=schedule_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    return app


_SKILL_MOUNT = CapabilityMount(
    id="skill:research",
    name="research",
    summary="Research workflow",
    kind="skill-bundle",
    source_kind="skill",
    risk_level="guarded",
    enabled=True,
    tags=["skill"],
)

_MCP_MOUNT = CapabilityMount(
    id="mcp:browser",
    name="browser",
    summary="Remote browser MCP",
    kind="remote-mcp",
    source_kind="mcp",
    risk_level="guarded",
    enabled=True,
    tags=["mcp"],
)

_DESKTOP_MCP_MOUNT = CapabilityMount(
    id="mcp:desktop_windows",
    name="desktop_windows",
    summary="Local Windows desktop MCP",
    kind="remote-mcp",
    source_kind="mcp",
    risk_level="guarded",
    enabled=True,
    tags=["mcp", "desktop"],
)

_TOOL_MOUNT = CapabilityMount(
    id="tool:execute_shell_command",
    name="execute_shell_command",
    summary="Run shell commands.",
    kind="local-tool",
    source_kind="tool",
    risk_level="guarded",
    tags=["shell"],
)


def _patch_loaders(
    monkeypatch,
    *,
    skill_mounts: list[CapabilityMount] | None = None,
    use_real_skill_mounts: bool = False,
    mcp_mounts: list[CapabilityMount] | None = None,
):
    from copaw.capabilities import catalog as catalog_module
    from copaw.capabilities import registry as registry_module
    from copaw.capabilities.sources.skills import (
        list_skill_capabilities as list_real_skill_capabilities,
    )

    monkeypatch.setattr(
        registry_module,
        "list_tool_capabilities",
        lambda: [_TOOL_MOUNT],
    )

    def _resolved_skill_mounts() -> list[CapabilityMount]:
        mounts = (
            list_real_skill_capabilities()
            if use_real_skill_mounts
            else list(skill_mounts or [_SKILL_MOUNT])
        )
        if use_real_skill_mounts and (
            not mounts
            or not any(bool(getattr(mount, "enabled", False)) for mount in mounts)
        ):
            return [_SKILL_MOUNT]
        return mounts

    monkeypatch.setattr(
        registry_module,
        "list_skill_capabilities",
        lambda: list(_resolved_skill_mounts()),
    )
    monkeypatch.setattr(
        registry_module,
        "list_mcp_capabilities",
        lambda: list(mcp_mounts or [_MCP_MOUNT]),
    )
    monkeypatch.setattr(
        registry_module,
        "list_external_package_capabilities",
        lambda: [],
    )
    monkeypatch.setattr(
        registry_module,
        "list_cooperative_capabilities",
        lambda: [],
    )
    monkeypatch.setattr(
        registry_module,
        "list_system_capabilities",
        list_builtin_system_capabilities,
    )
    monkeypatch.setattr(
        catalog_module,
        "build_skill_capabilities",
        lambda _skill_service: list(_resolved_skill_mounts()),
    )


def _first_enabled_skill_mount(app: FastAPI) -> CapabilityMount:
    mounts = app.state.capability_service.list_public_capabilities(
        kind="skill-bundle",
        enabled_only=True,
    )
    if not mounts:
        raise AssertionError("expected at least one enabled skill capability in catalog")
    return mounts[0]


def test_toggle_skill_capability(monkeypatch, tmp_path) -> None:
    """PATCH /capabilities/{id}/toggle dispatches through the canonical skill service."""
    _patch_loaders(monkeypatch)
    app = build_app(tmp_path)
    client = TestClient(app)
    skill_mount = _first_enabled_skill_mount(app)
    skill_id = skill_mount.id
    skill_name = skill_id.removeprefix("skill:")

    with patch("copaw.capabilities.skill_service.default_skill_service.disable_skill") as mock_disable:
        response = client.patch(f"/capabilities/{skill_id}/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["phase"] == "completed"
        assert data["toggled"] is True
        assert data["id"] == skill_id
        assert data["enabled"] is False
        mock_disable.assert_called_once_with(skill_name)


def test_toggle_mcp_capability(monkeypatch, tmp_path) -> None:
    """PATCH /capabilities/{id}/toggle dispatches to config for MCP."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config") as mock_save,
    ):
        # Create a mock config with a browser client
        class MockMCPClient:
            enabled = True

        class MockMCPConfig:
            clients = {"browser": MockMCPClient()}

        class MockConfig:
            mcp = MockMCPConfig()

        mock_load.return_value = MockConfig()

        response = client.patch("/capabilities/mcp:browser/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["phase"] == "completed"
        assert data["toggled"] is True
        assert data["id"] == "mcp:browser"
        assert data["enabled"] is False
        mock_save.assert_called_once()


def test_toggle_nonexistent_capability(monkeypatch, tmp_path) -> None:
    """PATCH /capabilities/{id}/toggle returns 404 for unknown capability."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    response = client.patch("/capabilities/skill:nonexistent/toggle")
    assert response.status_code == 404


def test_toggle_tool_capability_unsupported(monkeypatch, tmp_path) -> None:
    """PATCH /capabilities/{id}/toggle returns a kernel failure for tools."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    response = client.patch("/capabilities/tool:execute_shell_command/toggle")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["phase"] == "failed"
    assert "Toggle not supported" in data["error"]


def test_delete_skill_capability(monkeypatch, tmp_path) -> None:
    """DELETE /capabilities/{id} now auto-adjudicates through the main-brain governance chain."""
    _patch_loaders(monkeypatch)
    app = build_app(tmp_path)
    client = TestClient(app)
    skill_mount = _first_enabled_skill_mount(app)
    skill_id = skill_mount.id
    skill_name = skill_id.removeprefix("skill:")

    with patch("copaw.capabilities.skill_service.default_skill_service.delete_skill", return_value=True) as mock_delete:
        admitted = client.delete(f"/capabilities/{skill_id}")
        assert admitted.status_code == 200
        admitted_payload = admitted.json()
        assert admitted_payload["success"] is True
        assert admitted_payload["phase"] == "completed"
        decision_id = admitted_payload["decision_request_id"]
        assert decision_id

        detail = client.get(f"/runtime-center/decisions/{decision_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["status"] == "approved"
        assert detail_payload["requested_by"] == "copaw-main-brain"
        assert detail_payload["requires_human_confirmation"] is False
        mock_delete.assert_called_once_with(skill_name)


def test_delete_mcp_capability(monkeypatch, tmp_path) -> None:
    """DELETE /capabilities/{id} keeps MCP deletion on the main-brain governance chain too."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config") as mock_save,
    ):
        class MockMCPClient:
            enabled = True

        class MockMCPConfig:
            clients = {"browser": MockMCPClient()}

        class MockConfig:
            mcp = MockMCPConfig()

        mock_load.return_value = MockConfig()

        admitted = client.delete("/capabilities/mcp:browser")
        assert admitted.status_code == 200
        admitted_payload = admitted.json()
        assert admitted_payload["success"] is True
        assert admitted_payload["phase"] == "completed"
        decision_id = admitted_payload["decision_request_id"]
        assert decision_id

        detail = client.get(f"/runtime-center/decisions/{decision_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["status"] == "approved"
        assert detail_payload["requested_by"] == "copaw-main-brain"
        assert detail_payload["requires_human_confirmation"] is False
        mock_save.assert_called_once()


def test_delete_nonexistent_capability(monkeypatch, tmp_path) -> None:
    """DELETE /capabilities/{id} returns 404 for unknown capability."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    response = client.delete("/capabilities/skill:nonexistent")
    assert response.status_code == 404


def test_config_channel_update_route_uses_kernel_governance(monkeypatch, tmp_path) -> None:
    """PUT /config/channels/{name} now writes through a system capability."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config") as mock_save,
    ):
        mock_load.return_value = SimpleNamespace(
            channels=SimpleNamespace(),
            agents=SimpleNamespace(
                defaults=SimpleNamespace(heartbeat=None),
                running=None,
                llm_routing=None,
            ),
            mcp=SimpleNamespace(clients={}),
        )

        response = client.put(
            "/config/channels/console",
            json={"enabled": True, "bot_prefix": "!"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["enabled"] is True
        assert payload["bot_prefix"] == "!"
        mock_save.assert_called_once()


def test_agent_running_config_route_uses_kernel_governance(monkeypatch, tmp_path) -> None:
    """PUT /agent/running-config now reuses the kernel-governed config write path."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config") as mock_save,
    ):
        mock_load.return_value = SimpleNamespace(
            channels=SimpleNamespace(),
            agents=SimpleNamespace(
                defaults=SimpleNamespace(heartbeat=None),
                running=None,
                llm_routing=None,
            ),
            mcp=SimpleNamespace(clients={}),
        )

        response = client.put(
            "/agent/running-config",
            json={"max_iters": 12, "max_input_length": 4096},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["max_iters"] == 12
        assert payload["max_input_length"] == 4096
        mock_save.assert_called_once()


def test_capability_market_skill_create_route_uses_kernel_governance(
    monkeypatch,
    tmp_path,
) -> None:
    """POST /capability-market/skills creates customized skills through system capability execution."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    with patch("copaw.capabilities.skill_service.default_skill_service.create_skill", return_value=True) as mock_create:
        response = client.post(
            "/capability-market/skills",
            json={
                "name": "research-pack",
                "content": "---\nname: research-pack\ndescription: Research pack\n---\n",
            },
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["success"] is True
        assert payload["created"] is True
        assert payload["name"] == "research-pack"
        mock_create.assert_called_once()


def test_capability_market_hub_install_route_uses_kernel_governance(
    monkeypatch,
    tmp_path,
) -> None:
    """POST /capability-market/hub/install runs through the system install capability."""
    from copaw import constant as constant_module
    from copaw import skill_service as skill_service_module

    active_skills_dir = Path(tmp_path) / "active_skills"
    customized_skills_dir = Path(tmp_path) / "customized_skills"
    active_skills_dir.mkdir(parents=True, exist_ok=True)
    customized_skills_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(constant_module, "ACTIVE_SKILLS_DIR", active_skills_dir)
    monkeypatch.setattr(
        constant_module,
        "CUSTOMIZED_SKILLS_DIR",
        customized_skills_dir,
    )
    monkeypatch.setattr(
        skill_service_module,
        "ACTIVE_SKILLS_DIR",
        active_skills_dir,
    )
    monkeypatch.setattr(
        skill_service_module,
        "CUSTOMIZED_SKILLS_DIR",
        customized_skills_dir,
    )
    _patch_loaders(monkeypatch, use_real_skill_mounts=True)
    app = build_app(tmp_path)
    client = TestClient(app)
    skill_service = app.state.capability_service._skill_service

    def _fake_install_skill_from_hub(
        *,
        bundle_url: str,
        version: str = "1.0.0",
        enable: bool = True,
        overwrite: bool = False,
    ):
        skill_service.create_skill(
            name="research-pack",
            content=(
                "---\n"
                "name: research-pack\n"
                "description: Research pack\n"
                "---\n"
                f"Installed from {bundle_url} ({version})"
            ),
            overwrite=True,
        )
        if enable:
            skill_service.enable_skill("research-pack")
        return SimpleNamespace(
            name="research-pack",
            enabled=enable,
            source_url=bundle_url,
        )

    with patch(
        "copaw.capabilities.skill_service.default_skill_service.install_skill_from_hub",
        side_effect=_fake_install_skill_from_hub,
    ) as mock_install:
        response = client.post(
            "/capability-market/hub/install",
            json={
                "bundle_url": "https://example.com/research-pack",
                "version": "1.0.0",
                "enable": True,
                "overwrite": False,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["installed"] is True
        assert payload["name"] == "research-pack"
        assert payload["enabled"] is True
        assert payload["source_url"] == "https://example.com/research-pack"
        assert payload["assigned_capability_ids"] == ["skill:research-pack"]
        assert payload["assignment_results"] == []
        mock_install.assert_called_once()


def test_capability_market_mcp_create_route_uses_kernel_governance(
    monkeypatch,
    tmp_path,
) -> None:
    """POST /capability-market/mcp creates clients through the canonical market write surface."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config") as mock_save,
    ):
        config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
        mock_load.return_value = config

        response = client.post(
            "/capability-market/mcp",
            json={
                "client_key": "browser",
                "client": {
                    "name": "Browser",
                    "description": "Remote browser",
                    "enabled": True,
                    "transport": "stdio",
                    "command": "browser",
                    "args": [],
                    "env": {},
                    "cwd": "",
                },
            },
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["key"] == "browser"
        assert payload["name"] == "Browser"
        mock_save.assert_called_once()


def test_capability_market_mcp_update_route_uses_kernel_governance(
    monkeypatch,
    tmp_path,
) -> None:
    """PUT /capability-market/mcp/{key} updates clients through the canonical market write surface."""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app(tmp_path))

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config") as mock_save,
    ):
        existing = SimpleNamespace(
            name="Browser",
            description="Remote browser",
            enabled=True,
            transport="stdio",
            url="",
            headers={},
            command="browser",
            args=[],
            env={"TOKEN": "old"},
            cwd="",
            model_dump=lambda mode="json": {
                "name": "Browser",
                "description": "Remote browser",
                "enabled": True,
                "transport": "stdio",
                "url": "",
                "headers": {},
                "command": "browser",
                "args": [],
                "env": {"TOKEN": "old"},
                "cwd": "",
            },
        )
        config = SimpleNamespace(mcp=SimpleNamespace(clients={"browser": existing}))
        mock_load.return_value = config

        response = client.put(
            "/capability-market/mcp/browser",
            json={"description": "Updated browser", "env": {"TOKEN": "new"}},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["key"] == "browser"
        assert payload["description"] == "Updated browser"
        mock_save.assert_called_once()


def test_capability_market_install_template_install_route_uses_kernel_governance(
    monkeypatch,
    tmp_path,
) -> None:
    """POST /capability-market/install-templates/{id}/install stays on the governed MCP write path."""
    _patch_loaders(
        monkeypatch,
        mcp_mounts=[_MCP_MOUNT, _DESKTOP_MCP_MOUNT],
    )
    client = TestClient(build_app(tmp_path))

    with (
        patch("copaw.capabilities.service.load_config") as mock_load,
        patch("copaw.capabilities.service.save_config") as mock_save,
    ):
        config = SimpleNamespace(mcp=SimpleNamespace(clients={}))
        mock_load.return_value = config

        response = client.post(
            "/capability-market/install-templates/desktop-windows/install",
            json={},
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["template_id"] == "desktop-windows"
        assert payload["target_ref"] == "desktop_windows"
        assert payload["assigned_capability_ids"] == ["mcp:desktop_windows"]
        assert payload["routes"]["install"] == (
            "/api/capability-market/install-templates/desktop-windows/install"
        )
        mock_save.assert_called_once()


def test_capability_market_toggle_route_uses_kernel_governance(
    monkeypatch,
    tmp_path,
) -> None:
    """PATCH /capability-market/capabilities/{id}/toggle reuses the canonical governed write path."""
    _patch_loaders(monkeypatch)
    app = build_app(tmp_path)
    client = TestClient(app)
    skill_mount = _first_enabled_skill_mount(app)
    skill_id = skill_mount.id
    skill_name = skill_id.removeprefix("skill:")

    with patch("copaw.capabilities.skill_service.default_skill_service.disable_skill") as mock_disable:
        response = client.patch(f"/capability-market/capabilities/{skill_id}/toggle")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["toggled"] is True
        assert payload["enabled"] is False
        mock_disable.assert_called_once_with(skill_name)


def test_capability_market_delete_route_requires_confirmation(
    monkeypatch,
    tmp_path,
) -> None:
    """DELETE /capability-market/capabilities/{id} preserves the main-brain audit trail."""
    _patch_loaders(monkeypatch)
    app = build_app(tmp_path)
    client = TestClient(app)
    skill_mount = _first_enabled_skill_mount(app)
    skill_id = skill_mount.id
    skill_name = skill_id.removeprefix("skill:")

    with patch("copaw.capabilities.skill_service.default_skill_service.delete_skill", return_value=True) as mock_delete:
        admitted = client.delete(f"/capability-market/capabilities/{skill_id}")
        assert admitted.status_code == 200
        admitted_payload = admitted.json()
        assert admitted_payload["success"] is True
        assert admitted_payload["phase"] == "completed"
        decision_id = admitted_payload["decision_request_id"]
        assert decision_id

        detail = client.get(f"/runtime-center/decisions/{decision_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["status"] == "approved"
        assert detail_payload["requested_by"] == "copaw-main-brain"
        assert detail_payload["requires_human_confirmation"] is False
        mock_delete.assert_called_once_with(skill_name)
