# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from copaw.capabilities import CapabilityService
from copaw.capabilities.models import CapabilityMount
from copaw.config.config import Config, ExternalCapabilityPackageConfig
from copaw.kernel import KernelTask


def test_external_packages_are_loaded_as_first_class_capabilities() -> None:
    config = Config(
        external_capability_packages={
            "project:black": ExternalCapabilityPackageConfig(
                capability_id="project:black",
                name="black",
                summary="Python formatter package",
                kind="project-package",
                source_kind="project",
                source_url="https://github.com/psf/black",
                package_ref="git+https://github.com/psf/black.git",
                package_kind="git-repo",
                package_version="stable",
                enabled=True,
                execution_mode="shell",
                execute_command='python -m black --version',
                healthcheck_command='python -m black --version',
                runtime_kind="cli",
                supported_actions=["describe", "run"],
                scope_policy="session",
                ready_probe_kind="none",
                stop_strategy="terminate",
                startup_entry_ref="module:black",
            ),
            "adapter:pywinauto": ExternalCapabilityPackageConfig(
                capability_id="adapter:pywinauto",
                name="pywinauto",
                summary="Windows desktop automation adapter",
                kind="adapter",
                source_kind="adapter",
                source_url="https://github.com/pywinauto/pywinauto",
                package_ref="git+https://github.com/pywinauto/pywinauto.git",
                package_kind="git-repo",
                enabled=True,
                execution_mode="shell",
                execute_command=(
                    'python -c "import pywinauto; print(getattr(pywinauto, \'__name__\', \'pywinauto\'))"'
                ),
                runtime_kind="cli",
                supported_actions=["describe", "run"],
                scope_policy="seat",
                ready_probe_kind="none",
                stop_strategy="terminate",
                startup_entry_ref="module:pywinauto",
            ),
            "runtime:flask": ExternalCapabilityPackageConfig(
                capability_id="runtime:flask",
                name="flask",
                summary="Flask runtime component",
                kind="runtime-component",
                source_kind="runtime",
                source_url="https://github.com/pallets/flask",
                package_ref="git+https://github.com/pallets/flask.git",
                package_kind="git-repo",
                enabled=True,
                execution_mode="shell",
                execute_command='python -m flask --version',
                healthcheck_command='python -m flask --version',
                runtime_kind="service",
                supported_actions=[
                    "describe",
                    "start",
                    "healthcheck",
                    "stop",
                    "restart",
                ],
                scope_policy="session",
                ready_probe_kind="command",
                ready_probe_config={
                    "predicted_default_port": 5000,
                    "predicted_health_path": "/",
                },
                stop_strategy="terminate",
                startup_entry_ref="module:flask",
            ),
        },
    )

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
        patch(
            "copaw.capabilities.sources.external_packages.load_config",
            return_value=config,
        ),
    ):
        service = CapabilityService()
        mounts = {mount.id: mount for mount in service.list_capabilities()}

    assert mounts["project:black"].kind == "project-package"
    assert mounts["project:black"].source_kind == "project"
    assert mounts["adapter:pywinauto"].kind == "adapter"
    assert mounts["adapter:pywinauto"].source_kind == "adapter"
    assert mounts["runtime:flask"].kind == "runtime-component"
    assert mounts["runtime:flask"].source_kind == "runtime"
    assert mounts["runtime:flask"].metadata["runtime_contract"]["runtime_kind"] == "service"
    assert mounts["runtime:flask"].metadata["runtime_contract"]["supported_actions"] == [
        "describe",
        "start",
        "healthcheck",
        "stop",
        "restart",
    ]
    assert mounts["runtime:flask"].metadata["runtime_contract"]["predicted_default_port"] == 5000
    assert mounts["runtime:flask"].metadata["runtime_contract"]["predicted_health_path"] == "/"
    assert mounts["runtime:flask"].evidence_contract == ["shell-command", "runtime-event"]


def test_external_package_capability_executes_through_unified_execution_surface() -> None:
    config = Config(
        external_capability_packages={
            "project:black": ExternalCapabilityPackageConfig(
                capability_id="project:black",
                name="black",
                summary="Python formatter package",
                kind="project-package",
                source_kind="project",
                source_url="https://github.com/psf/black",
                package_ref="git+https://github.com/psf/black.git",
                package_kind="git-repo",
                enabled=True,
                execution_mode="shell",
                execute_command="python -m black --version",
                healthcheck_command="python -m black --version",
                runtime_kind="cli",
                supported_actions=["describe", "run"],
                scope_policy="session",
                ready_probe_kind="none",
                stop_strategy="terminate",
                startup_entry_ref="module:black",
            ),
        },
    )

    async def _fake_execute_shell_command(*, command: str, timeout: int, cwd=None):
        _ = cwd
        return {
            "success": True,
            "summary": f"Ran {command}",
            "output": "black, 25.0.0",
            "timed_out": False,
        }

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
        patch(
            "copaw.capabilities.sources.external_packages.load_config",
            return_value=config,
        ),
        patch(
            "copaw.capabilities.execution.execute_shell_command",
            side_effect=_fake_execute_shell_command,
        ),
    ):
        service = CapabilityService()
        result = asyncio.run(
            service.execute_task(
                KernelTask(
                    id="task-external-project",
                    title="Run black version",
                    capability_ref="project:black",
                    owner_agent_id="copaw-operator",
                    payload={"action": "run"},
                ),
            ),
        )

    assert result["success"] is True
    assert result["capability_id"] == "project:black"
    assert "black --version" in result["summary"]
